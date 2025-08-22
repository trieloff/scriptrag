"""Unit tests for enhanced MCP protocol implementation."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from scriptrag.mcp.protocol import (
    CacheConfig,
    PerformanceMetrics,
    QueryCache,
    RateLimitConfig,
    RateLimiter,
    SessionManager,
    StreamingHandler,
    StreamingMode,
)


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    def test_init(self):
        """Test metrics initialization."""
        metrics = PerformanceMetrics()

        assert metrics.total_requests == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.rate_limit_hits == 0
        assert len(metrics.operation_times) == 0
        assert len(metrics.error_counts) == 0

    def test_record_operation(self):
        """Test recording operation times."""
        metrics = PerformanceMetrics()

        metrics.record_operation("test_op", 0.5)
        metrics.record_operation("test_op", 0.3)
        metrics.record_operation("other_op", 1.0)

        assert metrics.total_requests == 3
        assert len(metrics.operation_times["test_op"]) == 2
        assert len(metrics.operation_times["other_op"]) == 1
        assert metrics.operation_times["test_op"] == [0.5, 0.3]

    def test_record_cache_operations(self):
        """Test recording cache hits and misses."""
        metrics = PerformanceMetrics()

        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()

        assert metrics.cache_hits == 2
        assert metrics.cache_misses == 1

    def test_get_stats(self):
        """Test getting statistics."""
        metrics = PerformanceMetrics()

        # Record some operations
        metrics.record_operation("op1", 0.5)
        metrics.record_operation("op1", 0.7)
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        metrics.record_rate_limit()

        stats = metrics.get_stats()

        assert stats["total_requests"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["rate_limit_hits"] == 1
        assert stats["cache_hit_ratio"] == 0.5

        # Check operation time stats
        assert "op1" in stats["operation_times"]
        op1_stats = stats["operation_times"]["op1"]
        assert op1_stats["avg"] == 0.6
        assert op1_stats["min"] == 0.5
        assert op1_stats["max"] == 0.7
        assert op1_stats["count"] == 2


class TestQueryCache:
    """Test query result caching."""

    def test_init(self):
        """Test cache initialization."""
        config = CacheConfig(ttl_seconds=300, max_size=100)
        cache = QueryCache(config)

        assert cache.config.ttl_seconds == 300
        assert cache.config.max_size == 100
        assert len(cache.cache) == 0

    def test_cache_key_generation(self):
        """Test consistent cache key generation."""
        cache = QueryCache(CacheConfig())

        # Same params in different order should generate same key
        key1 = cache._generate_key("op", {"a": 1, "b": 2})
        key2 = cache._generate_key("op", {"b": 2, "a": 1})

        assert key1 == key2

    def test_cache_set_and_get(self):
        """Test setting and getting cached values."""
        cache = QueryCache(CacheConfig(ttl_seconds=300))

        result = {"data": "test"}
        cache.set("search", {"query": "test"}, result)

        # Should retrieve cached result
        cached = cache.get("search", {"query": "test"})
        assert cached == result

        # Different params should not hit cache
        missed = cache.get("search", {"query": "other"})
        assert missed is None

    def test_cache_expiration(self):
        """Test cache TTL expiration."""
        cache = QueryCache(CacheConfig(ttl_seconds=1))

        result = {"data": "test"}
        cache.set("op", {}, result)

        # Should be in cache immediately
        assert cache.get("op", {}) == result

        # Mock time passing
        with patch("scriptrag.mcp.protocol.datetime") as mock_dt:
            # Set current time to 2 seconds later
            future = datetime.now() + timedelta(seconds=2)
            mock_dt.now.return_value = future

            # Should be expired
            assert cache.get("op", {}) is None

    def test_cache_size_limit(self):
        """Test cache size limiting."""
        cache = QueryCache(CacheConfig(max_size=2))

        # Add 3 items, should evict oldest
        cache.set("op", {"id": 1}, {"data": 1})
        cache.set("op", {"id": 2}, {"data": 2})

        # Access first item to make it more recent
        cache.get("op", {"id": 1})

        # Add third item, should evict id=2
        cache.set("op", {"id": 3}, {"data": 3})

        assert len(cache.cache) == 2
        assert cache.get("op", {"id": 1}) is not None
        assert cache.get("op", {"id": 2}) is None
        assert cache.get("op", {"id": 3}) is not None

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = QueryCache(CacheConfig())

        cache.set("op1", {}, {"data": 1})
        cache.set("op2", {}, {"data": 2})

        assert len(cache.cache) == 2

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.get("op1", {}) is None


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_init(self):
        """Test rate limiter initialization."""
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=1000,
        )
        limiter = RateLimiter(config)

        assert limiter.config.requests_per_minute == 60
        assert limiter.config.requests_per_hour == 1000

    def test_allow_requests_within_limit(self):
        """Test allowing requests within limits."""
        config = RateLimitConfig(requests_per_minute=10)
        limiter = RateLimiter(config)

        # Should allow first 10 requests
        for _ in range(10):
            allowed, wait = limiter.check_rate_limit("client1")
            assert allowed is True
            assert wait is None

    def test_rate_limit_per_minute(self):
        """Test per-minute rate limiting."""
        config = RateLimitConfig(
            requests_per_minute=2,
            cooldown_seconds=1,
        )
        limiter = RateLimiter(config)

        # Allow first 2 requests
        assert limiter.check_rate_limit("client1")[0] is True
        assert limiter.check_rate_limit("client1")[0] is True

        # Third request should be denied
        allowed, wait = limiter.check_rate_limit("client1")
        assert allowed is False
        assert wait == 1  # cooldown time

    def test_separate_client_limits(self):
        """Test that different clients have separate limits."""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = RateLimiter(config)

        # Client 1 makes a request
        assert limiter.check_rate_limit("client1")[0] is True
        assert limiter.check_rate_limit("client1")[0] is False

        # Client 2 should still be allowed
        assert limiter.check_rate_limit("client2")[0] is True

    def test_get_client_stats(self):
        """Test getting client statistics."""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
        )
        limiter = RateLimiter(config)

        # Make some requests
        limiter.check_rate_limit("client1")
        limiter.check_rate_limit("client1")

        stats = limiter.get_client_stats("client1")

        assert stats["minute_requests"] == 2
        assert stats["minute_limit"] == 10
        assert stats["hour_requests"] == 2
        assert stats["hour_limit"] == 100
        assert stats["in_cooldown"] is False


class TestSessionManager:
    """Test session management."""

    def test_create_session(self):
        """Test creating a new session."""
        manager = SessionManager()

        session = manager.create_session("client1")

        assert session.client_id == "client1"
        assert session.session_id is not None
        assert len(manager.sessions) == 1
        assert manager.client_sessions["client1"] == session.session_id

    def test_get_existing_session(self):
        """Test retrieving an existing session."""
        manager = SessionManager()

        # Create session
        original = manager.create_session("client1")

        # Get same session
        retrieved = manager.get_session("client1")

        assert retrieved.session_id == original.session_id
        assert len(manager.sessions) == 1

    def test_get_new_session_for_unknown_client(self):
        """Test that unknown client gets new session."""
        manager = SessionManager()

        session = manager.get_session("new_client")

        assert session is not None
        assert session.client_id == "new_client"
        assert len(manager.sessions) == 1

    def test_destroy_session(self):
        """Test destroying a session."""
        manager = SessionManager()

        session = manager.create_session("client1")
        session_id = session.session_id

        manager.destroy_session(session_id)

        assert len(manager.sessions) == 0
        assert "client1" not in manager.client_sessions

    def test_cleanup_old_sessions(self):
        """Test cleaning up old sessions."""
        manager = SessionManager()

        # Create sessions
        session1 = manager.create_session("client1")
        session2 = manager.create_session("client2")

        # Make session1 old
        with patch("scriptrag.mcp.protocol.datetime") as mock_dt:
            old_time = datetime.now() - timedelta(hours=25)
            session1.last_accessed = old_time

            # Current time for cleanup
            mock_dt.now.return_value = datetime.now()

            # Cleanup sessions older than 24 hours
            removed = manager.cleanup_old_sessions(max_age_hours=24)

            assert removed == 1
            assert len(manager.sessions) == 1
            assert session2.session_id in manager.sessions

    def test_session_state_persistence(self):
        """Test session state persistence."""
        manager = SessionManager()

        session = manager.create_session("client1")

        # Add to session state
        session.query_cache["key1"] = {"data": "value"}
        session.context["user_pref"] = "dark_mode"
        session.active_streams.add("stream1")

        # Retrieve session
        retrieved = manager.get_session("client1")

        assert retrieved.query_cache["key1"] == {"data": "value"}
        assert retrieved.context["user_pref"] == "dark_mode"
        assert "stream1" in retrieved.active_streams


@pytest.mark.asyncio
class TestStreamingHandler:
    """Test streaming functionality."""

    async def test_create_stream(self):
        """Test creating a stream."""
        handler = StreamingHandler()

        queue = await handler.create_stream("stream1", StreamingMode.CHUNKED)

        assert queue is not None
        assert "stream1" in handler.active_streams
        assert handler.stream_metadata["stream1"]["mode"] == StreamingMode.CHUNKED

    async def test_send_chunk(self):
        """Test sending chunks to stream."""
        handler = StreamingHandler()

        await handler.create_stream("stream1")
        await handler.send_chunk("stream1", {"data": "chunk1"})
        await handler.send_chunk("stream1", {"data": "chunk2"})

        assert handler.stream_metadata["stream1"]["chunks_sent"] == 2

    async def test_read_stream(self):
        """Test reading from stream."""
        handler = StreamingHandler()

        await handler.create_stream("stream1")

        # Send chunks before reading
        await handler.send_chunk("stream1", "chunk1")
        await handler.send_chunk("stream1", "chunk2")

        # Start reader task
        async def read_chunks():
            chunks = []
            async for chunk in handler.read_stream("stream1", timeout=0.5):
                chunks.append(chunk)
            return chunks

        # Start reading in background
        reader_task = asyncio.create_task(read_chunks())

        # Give reader time to start
        await asyncio.sleep(0.1)

        # Close stream to signal end
        await handler.close_stream("stream1")

        # Get results
        chunks = await reader_task
        assert chunks == ["chunk1", "chunk2"]

    async def test_stream_timeout(self):
        """Test stream reading with timeout."""
        handler = StreamingHandler()

        await handler.create_stream("stream1")

        # Read with short timeout (no chunks available)
        chunks = []
        async for chunk in handler.read_stream("stream1", timeout=0.1):
            chunks.append(chunk)

        assert len(chunks) == 0

    async def test_close_stream(self):
        """Test closing a stream."""
        handler = StreamingHandler()

        await handler.create_stream("stream1")
        await handler.close_stream("stream1")

        assert "stream1" not in handler.active_streams
        assert "stream1" not in handler.stream_metadata

    async def test_concurrent_streams(self):
        """Test handling multiple concurrent streams."""
        handler = StreamingHandler()

        # Create multiple streams
        await handler.create_stream("stream1")
        await handler.create_stream("stream2")

        # Send to different streams
        await handler.send_chunk("stream1", "s1_chunk")
        await handler.send_chunk("stream2", "s2_chunk")

        # Read from streams with tasks
        async def read_stream1():
            chunks = []
            async for chunk in handler.read_stream("stream1", timeout=0.5):
                chunks.append(chunk)
            return chunks

        async def read_stream2():
            chunks = []
            async for chunk in handler.read_stream("stream2", timeout=0.5):
                chunks.append(chunk)
            return chunks

        # Start reading tasks
        task1 = asyncio.create_task(read_stream1())
        task2 = asyncio.create_task(read_stream2())

        # Give readers time to start
        await asyncio.sleep(0.1)

        # Close streams
        await handler.close_stream("stream1")
        await handler.close_stream("stream2")

        # Get results
        chunks1 = await task1
        chunks2 = await task2

        assert chunks1 == ["s1_chunk"]
        assert chunks2 == ["s2_chunk"]


@pytest.mark.asyncio
class TestEnhancedMCPServer:
    """Test the enhanced MCP server."""

    async def test_server_initialization(self):
        """Test server initialization with custom configs."""
        from scriptrag.mcp.protocol import EnhancedMCPServer

        rate_config = RateLimitConfig(requests_per_minute=50)
        cache_config = CacheConfig(ttl_seconds=120)

        server = EnhancedMCPServer(
            name="test",
            rate_limit_config=rate_config,
            cache_config=cache_config,
        )

        assert server.mcp.name == "test"
        assert server.rate_limiter.config.requests_per_minute == 50
        assert server.cache.config.ttl_seconds == 120

    async def test_monitoring_tools_registration(self):
        """Test that monitoring tools are registered."""
        from scriptrag.mcp.protocol import EnhancedMCPServer

        server = EnhancedMCPServer(name="test")

        # Check tools are registered
        tools = await server.mcp.list_tools()
        tool_names = [t.name for t in tools]

        assert "scriptrag_mcp_stats" in tool_names
        assert "scriptrag_mcp_cache_clear" in tool_names
        assert "scriptrag_mcp_session_info" in tool_names

    async def test_wrap_tool_with_caching(self):
        """Test tool wrapping with caching enabled."""
        from scriptrag.mcp.protocol import EnhancedMCPServer

        server = EnhancedMCPServer(name="test")

        # Create a mock tool
        call_count = 0

        async def test_tool(param: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"success": True, "param": param, "count": call_count}

        # Wrap with caching
        wrapped = server.wrap_tool_with_features(test_tool, enable_cache=True)

        # First call should execute
        result1 = await wrapped(param="test")
        assert result1["count"] == 1

        # Second call with same params should use cache
        result2 = await wrapped(param="test")
        assert result2["count"] == 1  # Same count, from cache

        # Different params should execute again
        result3 = await wrapped(param="other")
        assert result3["count"] == 2

    async def test_wrap_tool_with_rate_limiting(self):
        """Test tool wrapping with rate limiting."""
        from scriptrag.mcp.protocol import EnhancedMCPServer

        rate_config = RateLimitConfig(
            requests_per_minute=2,
            cooldown_seconds=1,
        )
        server = EnhancedMCPServer(
            name="test",
            rate_limit_config=rate_config,
        )

        async def test_tool() -> dict:
            return {"success": True}

        wrapped = server.wrap_tool_with_features(test_tool)

        # First 2 calls should succeed
        result1 = await wrapped(client_id="test_client")
        assert result1["success"] is True

        result2 = await wrapped(client_id="test_client")
        assert result2["success"] is True

        # Third call should be rate limited
        result3 = await wrapped(client_id="test_client")
        assert result3["success"] is False
        assert "Rate limit exceeded" in result3["error"]

    async def test_cleanup(self):
        """Test server cleanup."""
        from scriptrag.mcp.protocol import EnhancedMCPServer

        server = EnhancedMCPServer(name="test")

        # Add some data
        server.cache.set("op", {}, {"data": "test"})
        server.session_manager.create_session("client1")

        # Cleanup
        await server.cleanup()

        # Cache should be cleared
        assert len(server.cache.cache) == 0
