"""Enhanced MCP protocol implementation with full feature support."""

import asyncio
import json
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from mcp.server import FastMCP
from pydantic import BaseModel, Field

from scriptrag.config import get_logger

logger = get_logger(__name__)


class SessionState(BaseModel):
    """MCP session state for persistence."""

    session_id: str
    client_id: str
    created_at: datetime
    last_accessed: datetime
    query_cache: dict[str, Any] = Field(default_factory=dict)
    rate_limit_counts: dict[str, list[datetime]] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    active_streams: set[str] = Field(default_factory=set)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration per client."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    cooldown_seconds: int = 60


class CacheConfig(BaseModel):
    """Cache configuration for query results."""

    ttl_seconds: int = 300  # 5 minutes default
    max_size: int = 100
    enable_compression: bool = True


class StreamingMode(str, Enum):
    """Streaming modes for long-running operations."""

    NONE = "none"
    CHUNKED = "chunked"
    PROGRESSIVE = "progressive"
    REALTIME = "realtime"


class PerformanceMetrics:
    """Performance monitoring for MCP operations."""

    def __init__(self) -> None:
        """Initialize performance metrics."""
        self.operation_times: dict[str, list[float]] = defaultdict(list)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.rate_limit_hits: int = 0
        self.total_requests: int = 0
        self.start_time: datetime = datetime.now()

    def record_operation(self, operation: str, duration: float) -> None:
        """Record an operation's execution time."""
        self.operation_times[operation].append(duration)
        self.total_requests += 1

    def record_error(self, operation: str) -> None:
        """Record an error for an operation."""
        self.error_counts[operation] += 1

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1

    def record_rate_limit(self) -> None:
        """Record a rate limit hit."""
        self.rate_limit_hits += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current performance statistics."""
        uptime = (datetime.now() - self.start_time).total_seconds()

        # Calculate averages
        avg_times = {}
        for op, times in self.operation_times.items():
            if times:
                avg_times[op] = {
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "count": len(times),
                }

        cache_ratio = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0
        )

        return {
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "requests_per_second": self.total_requests / uptime if uptime > 0 else 0,
            "operation_times": avg_times,
            "error_counts": dict(self.error_counts),
            "cache_hit_ratio": cache_ratio,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "rate_limit_hits": self.rate_limit_hits,
        }


class QueryCache:
    """LRU cache for query results with TTL support."""

    def __init__(self, config: CacheConfig) -> None:
        """Initialize query cache with configuration.

        Args:
            config: Cache configuration
        """
        self.config = config
        self.cache: dict[str, tuple[Any, datetime]] = {}
        self.access_times: dict[str, datetime] = {}

    def _generate_key(self, operation: str, params: dict[str, Any]) -> str:
        """Generate a cache key from operation and parameters."""
        # Sort params for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True)
        return f"{operation}:{sorted_params}"

    def get(self, operation: str, params: dict[str, Any]) -> Any | None:
        """Get a cached result if available and not expired."""
        key = self._generate_key(operation, params)

        if key in self.cache:
            result, timestamp = self.cache[key]
            age = (datetime.now() - timestamp).total_seconds()

            if age < self.config.ttl_seconds:
                self.access_times[key] = datetime.now()
                return result
            # Expired, remove from cache
            del self.cache[key]
            del self.access_times[key]

        return None

    def set(self, operation: str, params: dict[str, Any], result: Any) -> None:
        """Cache a result with TTL."""
        # Check cache size limit
        if len(self.cache) >= self.config.max_size and self.access_times:
            # Remove least recently accessed item
            oldest_key = min(
                self.access_times,
                key=lambda k: self.access_times.get(k, datetime.now()),
            )
            del self.cache[oldest_key]
            del self.access_times[oldest_key]

        key = self._generate_key(operation, params)
        self.cache[key] = (result, datetime.now())
        self.access_times[key] = datetime.now()

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()
        self.access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.config.max_size,
            "ttl_seconds": self.config.ttl_seconds,
            "keys": list(self.cache.keys()),
        }


class RateLimiter:
    """Token bucket rate limiter per client."""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter with configuration.

        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self.request_times: dict[str, list[datetime]] = defaultdict(list)
        self.cooldowns: dict[str, datetime] = {}

    def check_rate_limit(self, client_id: str) -> tuple[bool, int | None]:
        """Check if a client has exceeded rate limits.

        Returns:
            Tuple of (allowed, wait_seconds)
        """
        now = datetime.now()

        # Check if client is in cooldown
        if client_id in self.cooldowns:
            if now < self.cooldowns[client_id]:
                wait = (self.cooldowns[client_id] - now).total_seconds()
                return False, int(wait)
            del self.cooldowns[client_id]

        # Clean old request times
        hour_ago = now - timedelta(hours=1)
        minute_ago = now - timedelta(minutes=1)

        self.request_times[client_id] = [
            t for t in self.request_times[client_id] if t > hour_ago
        ]

        # Count requests
        minute_requests = sum(
            1 for t in self.request_times[client_id] if t > minute_ago
        )
        hour_requests = len(self.request_times[client_id])

        # Check limits
        if minute_requests >= self.config.requests_per_minute:
            # Apply cooldown
            self.cooldowns[client_id] = now + timedelta(
                seconds=self.config.cooldown_seconds
            )
            return False, self.config.cooldown_seconds

        if hour_requests >= self.config.requests_per_hour:
            # Apply cooldown
            self.cooldowns[client_id] = now + timedelta(
                seconds=self.config.cooldown_seconds
            )
            return False, self.config.cooldown_seconds

        # Allow request
        self.request_times[client_id].append(now)
        return True, None

    def get_client_stats(self, client_id: str) -> dict[str, Any]:
        """Get rate limit statistics for a client."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        minute_requests = sum(
            1 for t in self.request_times.get(client_id, []) if t > minute_ago
        )
        hour_requests = sum(
            1 for t in self.request_times.get(client_id, []) if t > hour_ago
        )

        return {
            "minute_requests": minute_requests,
            "minute_limit": self.config.requests_per_minute,
            "hour_requests": hour_requests,
            "hour_limit": self.config.requests_per_hour,
            "in_cooldown": client_id in self.cooldowns,
            "cooldown_until": (
                self.cooldowns[client_id].isoformat()
                if client_id in self.cooldowns
                else None
            ),
        }


class SessionManager:
    """Manage MCP client sessions with state persistence."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self.sessions: dict[str, SessionState] = {}
        self.client_sessions: dict[str, str] = {}  # client_id -> session_id

    def create_session(self, client_id: str) -> SessionState:
        """Create a new session for a client."""
        import uuid

        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            client_id=client_id,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )

        self.sessions[session_id] = session
        self.client_sessions[client_id] = session_id

        logger.info(f"Created session {session_id} for client {client_id}")
        return session

    def get_session(self, client_id: str) -> SessionState | None:
        """Get an existing session or create a new one."""
        if client_id in self.client_sessions:
            session_id = self.client_sessions[client_id]
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_accessed = datetime.now()
                return session

        # Create new session
        return self.create_session(client_id)

    def destroy_session(self, session_id: str) -> None:
        """Destroy a session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.client_id in self.client_sessions:
                del self.client_sessions[session.client_id]
            del self.sessions[session_id]
            logger.info(f"Destroyed session {session_id}")

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up sessions older than max_age_hours."""
        now = datetime.now()
        max_age = timedelta(hours=max_age_hours)

        to_remove = []
        for session_id, session in self.sessions.items():
            if now - session.last_accessed > max_age:
                to_remove.append(session_id)

        for session_id in to_remove:
            self.destroy_session(session_id)

        return len(to_remove)

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "active_sessions": len(self.sessions),
            "active_clients": len(self.client_sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "client_id": s.client_id,
                    "created_at": s.created_at.isoformat(),
                    "last_accessed": s.last_accessed.isoformat(),
                    "cache_size": len(s.query_cache),
                    "active_streams": len(s.active_streams),
                }
                for s in self.sessions.values()
            ],
        }


class StreamingHandler:
    """Handle streaming responses for long-running operations."""

    def __init__(self) -> None:
        """Initialize streaming handler."""
        self.active_streams: dict[str, asyncio.Queue[Any]] = {}
        self.stream_metadata: dict[str, dict[str, Any]] = {}

    async def create_stream(
        self, stream_id: str, mode: StreamingMode = StreamingMode.CHUNKED
    ) -> asyncio.Queue:
        """Create a new streaming channel."""
        if stream_id in self.active_streams:
            raise ValueError(f"Stream {stream_id} already exists")

        queue: asyncio.Queue[Any] = asyncio.Queue()
        self.active_streams[stream_id] = queue
        self.stream_metadata[stream_id] = {
            "mode": mode,
            "created_at": datetime.now(),
            "chunks_sent": 0,
        }

        logger.debug(f"Created stream {stream_id} with mode {mode}")
        return queue

    async def send_chunk(self, stream_id: str, chunk: Any) -> None:
        """Send a chunk to a stream."""
        if stream_id not in self.active_streams:
            raise ValueError(f"Stream {stream_id} not found")

        queue = self.active_streams[stream_id]
        await queue.put(chunk)
        self.stream_metadata[stream_id]["chunks_sent"] += 1

    async def close_stream(self, stream_id: str) -> None:
        """Close a streaming channel."""
        if stream_id in self.active_streams:
            queue = self.active_streams[stream_id]
            await queue.put(None)  # Signal end of stream
            del self.active_streams[stream_id]
            del self.stream_metadata[stream_id]
            logger.debug(f"Closed stream {stream_id}")

    async def read_stream(  # type: ignore[no-untyped-def]
        self, stream_id: str, timeout: float | None = None
    ):
        """Read from a stream (generator)."""
        if stream_id not in self.active_streams:
            raise ValueError(f"Stream {stream_id} not found")

        queue = self.active_streams[stream_id]

        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
                if chunk is None:
                    break
                yield chunk
            except TimeoutError:
                break

    def get_stats(self) -> dict[str, Any]:
        """Get streaming statistics."""
        return {
            "active_streams": len(self.active_streams),
            "streams": [
                {
                    "stream_id": sid,
                    "mode": meta["mode"],
                    "created_at": meta["created_at"].isoformat(),
                    "chunks_sent": meta["chunks_sent"],
                }
                for sid, meta in self.stream_metadata.items()
            ],
        }


class EnhancedMCPServer:
    """Enhanced MCP server with full protocol support."""

    def __init__(
        self,
        name: str = "scriptrag",
        rate_limit_config: RateLimitConfig | None = None,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """Initialize enhanced MCP server.

        Args:
            name: Server name
            rate_limit_config: Rate limiting configuration
            cache_config: Cache configuration
        """
        self.mcp = FastMCP(name)
        self.session_manager = SessionManager()
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())
        self.cache = QueryCache(cache_config or CacheConfig())
        self.streaming_handler = StreamingHandler()
        self.metrics = PerformanceMetrics()

        # Register monitoring tools
        self._register_monitoring_tools()

    def _register_monitoring_tools(self) -> None:
        """Register MCP tools for monitoring and introspection."""

        @self.mcp.tool()
        async def scriptrag_mcp_stats() -> dict[str, Any]:
            """Get MCP server statistics and performance metrics.

            Returns comprehensive statistics about server performance,
            cache usage, rate limiting, and active sessions.

            Returns:
                Dictionary containing server statistics
            """
            return {
                "success": True,
                "performance": self.metrics.get_stats(),
                "sessions": self.session_manager.get_stats(),
                "cache": self.cache.get_stats(),
                "streaming": self.streaming_handler.get_stats(),
            }

        @self.mcp.tool()
        async def scriptrag_mcp_cache_clear() -> dict[str, Any]:
            """Clear the MCP query cache.

            Removes all cached query results to force fresh data retrieval.

            Returns:
                Success status
            """
            self.cache.clear()
            return {
                "success": True,
                "message": "Cache cleared successfully",
            }

        @self.mcp.tool()
        async def scriptrag_mcp_session_info(client_id: str) -> dict[str, Any]:
            """Get session information for a specific client.

            Args:
                client_id: The client identifier

            Returns:
                Session information and rate limit status
            """
            session = self.session_manager.get_session(client_id)
            rate_stats = self.rate_limiter.get_client_stats(client_id)

            if session is None:
                return {
                    "success": False,
                    "error": f"No session found for client {client_id}",
                }

            return {
                "success": True,
                "session": {
                    "session_id": session.session_id,
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "cache_entries": len(session.query_cache),
                    "active_streams": list(session.active_streams),
                },
                "rate_limits": rate_stats,
            }

    def wrap_tool_with_features(
        self,
        tool_func: Callable,
        enable_cache: bool = True,
        enable_streaming: bool = False,
    ) -> Callable:
        """Wrap a tool function with caching, rate limiting, and monitoring."""

        async def wrapped_tool(client_id: str = "default", **kwargs):  # type: ignore[no-untyped-def]
            # Start timing
            start_time = time.time()
            operation = tool_func.__name__

            try:
                # Check rate limit
                allowed, wait_time = self.rate_limiter.check_rate_limit(client_id)
                if not allowed:
                    self.metrics.record_rate_limit()
                    return {
                        "success": False,
                        "error": "Rate limit exceeded",
                        "retry_after": wait_time,
                    }

                # Get session
                session = self.session_manager.get_session(client_id)
                if session is None:
                    return {
                        "success": False,
                        "error": f"Failed to get session for client {client_id}",
                    }

                # Check cache if enabled
                if enable_cache:
                    cached_result = self.cache.get(operation, kwargs)
                    if cached_result is not None:
                        self.metrics.record_cache_hit()
                        duration = time.time() - start_time
                        self.metrics.record_operation(operation, duration)
                        return cached_result
                    self.metrics.record_cache_miss()

                # Handle streaming if enabled
                if enable_streaming and kwargs.get("stream", False):
                    import uuid

                    stream_id = str(uuid.uuid4())
                    session.active_streams.add(stream_id)

                    # Create stream
                    await self.streaming_handler.create_stream(stream_id)

                    # Start async task for streaming execution
                    async def stream_executor() -> None:
                        try:
                            async for chunk in tool_func(**kwargs):
                                await self.streaming_handler.send_chunk(
                                    stream_id, chunk
                                )
                        finally:
                            await self.streaming_handler.close_stream(stream_id)
                            session.active_streams.discard(stream_id)

                    _ = asyncio.create_task(stream_executor())  # noqa: RUF006

                    return {
                        "success": True,
                        "stream_id": stream_id,
                        "message": "Streaming response initiated",
                    }

                # Execute tool normally
                result = await tool_func(**kwargs)

                # Cache result if enabled
                if enable_cache and result.get("success", False):
                    self.cache.set(operation, kwargs, result)

                # Record metrics
                duration = time.time() - start_time
                self.metrics.record_operation(operation, duration)

                return result

            except Exception as e:
                self.metrics.record_error(operation)
                logger.error(f"Tool {operation} failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                }

        wrapped_tool.__name__ = tool_func.__name__
        wrapped_tool.__doc__ = tool_func.__doc__
        return wrapped_tool

    def register_tool(
        self,
        tool_func: Callable,
        enable_cache: bool = True,
        enable_streaming: bool = False,
    ) -> None:
        """Register a tool with enhanced features."""
        wrapped = self.wrap_tool_with_features(
            tool_func, enable_cache, enable_streaming
        )
        self.mcp.tool()(wrapped)

    async def cleanup(self) -> None:
        """Clean up server resources."""
        # Clean old sessions
        removed = self.session_manager.cleanup_old_sessions()
        logger.info(f"Cleaned up {removed} old sessions")

        # Clear expired cache entries
        self.cache.clear()

    def get_mcp_instance(self) -> FastMCP:
        """Get the underlying FastMCP instance."""
        return self.mcp
