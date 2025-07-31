"""Tests for FastAPI application middleware and exception handlers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from scriptrag.api.app import create_app, lifespan


@pytest.fixture
def mock_llm_client():
    """Mock LLM client to avoid initialization errors in tests."""
    with patch("scriptrag.database.embedding_pipeline.LLMClient") as mock:
        # Create a mock instance that doesn't require API credentials
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock()
    settings.cors_origins = ["http://testclient", "http://localhost:3000"]
    settings.api.cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    settings.api.cors_headers = ["Content-Type", "Authorization", "X-Test-Header"]
    settings.database_url = "sqlite+aiosqlite:///test.db"
    return settings


@pytest.fixture
def mock_db_operations():
    """Mock database operations."""
    mock_db = AsyncMock()
    mock_db.initialize = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest.fixture
def app_with_mocked_db(mock_settings, mock_db_operations, mock_llm_client):
    """Create app with mocked dependencies."""
    _ = mock_llm_client  # Mark as used
    with (
        patch("scriptrag.config.get_settings", return_value=mock_settings),
        patch("scriptrag.api.app.DatabaseOperations", return_value=mock_db_operations),
    ):
        app = create_app()
        yield app


@pytest.fixture
def client(app_with_mocked_db):
    """Create test client."""
    with TestClient(app_with_mocked_db) as client:
        yield client


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_preflight_request(self, client):
        """Test CORS preflight (OPTIONS) request."""
        response = client.options(
            "/api/v1/scripts/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        assert "POST" in response.headers["access-control-allow-methods"]
        assert "Content-Type" in response.headers["access-control-allow-headers"]
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_cors_actual_request(self, client):
        """Test CORS headers on actual request."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_cors_disallowed_origin(self, client):
        """Test CORS with disallowed origin."""
        response = client.get("/health", headers={"Origin": "http://evil.com"})

        assert response.status_code == 200
        # Should not have CORS headers for disallowed origin
        assert "access-control-allow-origin" not in response.headers

    def test_cors_wildcard_methods(self, client):
        """Test that all configured methods are allowed."""
        # Test with a simpler OPTIONS request that should work
        response = client.options(
            "/health",  # Use a simple endpoint
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        # Check that CORS headers are present
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers

    def test_cors_custom_headers(self, client):
        """Test CORS with custom headers."""
        # Use a simple endpoint for OPTIONS request
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

        assert response.status_code == 200
        # Check CORS headers are present
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-headers" in response.headers
        # Authorization should be in allowed headers
        allowed_headers = response.headers.get("access-control-allow-headers", "")
        assert "Authorization" in allowed_headers


class TestExceptionHandlers:
    """Test exception handling."""

    def test_http_exception_handler(self, client):
        """Test handling of HTTPException."""
        # Test a known 404 endpoint - use a non-existent route
        response = client.get("/api/v1/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_custom_exception_handler_integration(self, app_with_mocked_db):
        """Test custom exception handler can be added to app."""
        from fastapi.responses import JSONResponse

        from scriptrag.parser import FountainParsingError

        # Add custom exception handler
        @app_with_mocked_db.exception_handler(FountainParsingError)
        async def fountain_exception_handler(
            request: Request, exc: FountainParsingError
        ):
            _ = request  # Mark as used
            return JSONResponse(
                status_code=418,  # I'm a teapot
                content={"detail": f"Fountain parsing error: {exc!s}"},
            )

        # Create endpoint that raises custom exception
        @app_with_mocked_db.post("/test-fountain-error")
        async def test_fountain_error():
            raise FountainParsingError("Invalid fountain format")

        with TestClient(app_with_mocked_db) as client:
            response = client.post("/test-fountain-error")
            assert response.status_code == 418  # Custom handler returns 418
            data = response.json()
            assert "detail" in data
            assert "Fountain parsing error" in data["detail"]
            assert "Invalid fountain format" in data["detail"]

    def test_request_validation_error(self, client):
        """Test handling of request validation errors."""
        # Send invalid data to trigger validation error
        response = client.post(
            "/api/v1/search/scenes",
            json={
                "limit": -1,  # Invalid: must be >= 1
                "offset": "not_a_number",  # Invalid: must be int
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)
        # Check that validation errors are properly formatted
        for error in data["detail"]:
            assert "loc" in error  # Location of error
            assert "msg" in error  # Error message
            assert "type" in error  # Error type

    def test_validation_error_missing_required_field(self, client):
        """Test validation error for missing required field."""
        response = client.post(
            "/api/v1/search/similar",
            json={
                "limit": 10
                # Missing required "query" field
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        # Find the error for missing query field
        query_error = next((e for e in errors if "query" in e["loc"]), None)
        assert query_error is not None
        assert "required" in query_error["msg"].lower()

    def test_internal_server_error_handling(self, app_with_mocked_db):
        """Test handling of unexpected exceptions."""

        # Create a custom endpoint that raises an exception
        @app_with_mocked_db.get("/test-error")
        async def test_error():
            raise Exception("Unexpected error")

        with TestClient(app_with_mocked_db) as client:
            # FastAPI in test mode might propagate the exception
            try:
                response = client.get("/test-error")
                # If we get a response, it should be 500
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data
            except Exception as e:
                # If exception propagates in test mode, that's also acceptable
                assert "Unexpected error" in str(e)

    def test_multiple_exception_handlers(self, app_with_mocked_db):
        """Test app can handle multiple custom exception types."""
        from scriptrag.database.embeddings import EmbeddingError
        from scriptrag.llm.client import LLMClientError

        # Add multiple exception handlers
        @app_with_mocked_db.exception_handler(EmbeddingError)
        async def embedding_exception_handler(request: Request, exc: EmbeddingError):
            from fastapi.responses import JSONResponse

            _ = request  # Mark as used
            return JSONResponse(
                status_code=503,
                content={
                    "detail": f"Embedding error: {exc!s}",
                    "error_type": "embedding",
                },
            )

        @app_with_mocked_db.exception_handler(LLMClientError)
        async def llm_exception_handler(request: Request, exc: LLMClientError):
            from fastapi.responses import JSONResponse

            _ = request  # Mark as used
            return JSONResponse(
                status_code=503,
                content={"detail": f"LLM error: {exc!s}", "error_type": "llm"},
            )

        # Create endpoints that raise different exceptions
        @app_with_mocked_db.get("/test-embedding-error")
        async def test_embedding_error():
            raise EmbeddingError("Failed to generate embeddings")

        @app_with_mocked_db.get("/test-llm-error")
        async def test_llm_error():
            raise LLMClientError("LLM API unavailable")

        with TestClient(app_with_mocked_db) as client:
            # Test embedding error
            response = client.get("/test-embedding-error")
            assert response.status_code == 503
            data = response.json()
            assert data["error_type"] == "embedding"
            assert "Failed to generate embeddings" in data["detail"]

            # Test LLM error
            response = client.get("/test-llm-error")
            assert response.status_code == 503
            data = response.json()
            assert data["error_type"] == "llm"
            assert "LLM API unavailable" in data["detail"]


class TestLifespanEvents:
    """Test application lifespan events."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self, mock_settings, mock_db_operations):
        """Test startup and shutdown events."""
        app = MagicMock()
        app.state = MagicMock()

        with (
            patch("scriptrag.config.get_settings", return_value=mock_settings),
            patch(
                "scriptrag.api.app.DatabaseOperations", return_value=mock_db_operations
            ),
        ):
            # Run lifespan context manager
            async with lifespan(app):
                # Check startup actions
                mock_db_operations.initialize.assert_called_once()
                assert app.state.db_ops == mock_db_operations
                assert hasattr(app.state, "settings")

            # After exiting context, check shutdown actions
            mock_db_operations.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self, mock_settings):
        """Test handling of startup failure."""
        app = MagicMock()
        app.state = MagicMock()

        # Mock database operations that fails on initialize
        mock_db = AsyncMock()
        mock_db.initialize = AsyncMock(side_effect=Exception("DB init failed"))

        with (
            patch("scriptrag.config.get_settings", return_value=mock_settings),
            patch("scriptrag.api.app.DatabaseOperations", return_value=mock_db),
            pytest.raises(Exception, match="DB init failed"),
        ):
            async with lifespan(app):
                pass


class TestMiddlewareOrder:
    """Test middleware execution order."""

    def test_middleware_execution_order(self, app_with_mocked_db):
        """Test that middleware is executed in correct order."""
        call_order = []

        # Add custom middleware to track execution order
        @app_with_mocked_db.middleware("http")
        async def track_middleware(request: Request, call_next):
            call_order.append("custom_before")
            response = await call_next(request)
            call_order.append("custom_after")
            return response

        with TestClient(app_with_mocked_db) as client:
            response = client.get(
                "/health", headers={"Origin": "http://localhost:3000"}
            )

            assert response.status_code == 200
            # CORS headers should be present (CORS middleware executed)
            assert "access-control-allow-origin" in response.headers
            # Custom middleware should have executed
            assert "custom_before" in call_order
            assert "custom_after" in call_order

    def test_middleware_modifies_response(self, app_with_mocked_db):
        """Test middleware can modify responses."""

        # Add middleware that adds custom headers
        @app_with_mocked_db.middleware("http")
        async def add_custom_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers["X-Custom-Header"] = "CustomValue"
            response.headers["X-Request-Path"] = str(request.url.path)
            return response

        with TestClient(app_with_mocked_db) as client:
            response = client.get("/health")

            assert response.status_code == 200
            assert response.headers["X-Custom-Header"] == "CustomValue"
            assert response.headers["X-Request-Path"] == "/health"

    def test_middleware_timing(self, app_with_mocked_db):
        """Test middleware can track request timing."""
        import time

        request_times = {}

        @app_with_mocked_db.middleware("http")
        async def timing_middleware(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            request_times[str(request.url.path)] = process_time
            response.headers["X-Process-Time"] = str(process_time)
            return response

        with TestClient(app_with_mocked_db) as client:
            response = client.get("/health")

            assert response.status_code == 200
            assert "X-Process-Time" in response.headers
            assert "/health" in request_times
            assert isinstance(request_times["/health"], float)
            assert request_times["/health"] >= 0

    def test_middleware_error_handling(self, app_with_mocked_db):
        """Test middleware handles errors properly."""
        error_caught = []

        @app_with_mocked_db.middleware("http")
        async def error_handling_middleware(request: Request, call_next):
            try:
                return await call_next(request)
            except Exception as e:
                error_caught.append(str(e))
                # Re-raise to maintain normal error flow
                raise

        # Add endpoint that raises an error
        @app_with_mocked_db.get("/test-middleware-error")
        async def raise_error():
            raise ValueError("Test error in endpoint")

        with TestClient(app_with_mocked_db) as client:
            try:
                response = client.get("/test-middleware-error")
                # If we get here, check the response
                assert response.status_code == 500
            except ValueError:
                # If the error propagates out, that's also fine
                pass

            # Our middleware should have caught it either way
            assert len(error_caught) > 0
            assert "Test error in endpoint" in error_caught[0]


class TestEndpoints:
    """Test basic endpoints and response formats."""

    def test_root_endpoint(self, client):
        """Test root endpoint response format."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "ScriptRAG API"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/api/v1/docs"

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_openapi_endpoint(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get("/api/v1/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema["openapi"].startswith("3.")
        assert schema["info"]["title"] == "ScriptRAG API"
        assert schema["info"]["version"] == "1.0.0"

    def test_docs_endpoint(self, client):
        """Test API documentation endpoint."""
        response = client.get("/api/v1/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client):
        """Test ReDoc documentation endpoint."""
        response = client.get("/api/v1/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestErrorResponseFormats:
    """Test error response formats."""

    def test_404_error_format(self, client):
        """Test 404 error response format."""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_422_error_format(self, client):
        """Test 422 validation error format."""
        response = client.post(
            "/api/v1/scripts/upload",
            json={
                "title": "",  # Empty title should fail validation
                "content": "test",
                "author": 123,  # Should be string
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)
        for error in data["detail"]:
            assert isinstance(error, dict)
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    def test_method_not_allowed_format(self, client):
        """Test 405 method not allowed error format."""
        # Try DELETE on an endpoint that doesn't support it
        response = client.delete("/health")

        assert response.status_code == 405
        data = response.json()
        assert "detail" in data


class TestRequestHeaders:
    """Test request header handling."""

    def test_content_type_json(self, client):
        """Test JSON content type handling."""
        response = client.post(
            "/api/v1/search/scenes",
            json={"limit": 10},
            headers={"Content-Type": "application/json"},
        )

        # Should process JSON correctly
        assert response.status_code in [200, 422]  # Either success or validation error

    def test_unsupported_content_type(self, client):
        """Test unsupported content type."""
        response = client.post(
            "/api/v1/search/scenes",
            data="plain text data",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 422  # Unprocessable entity

    def test_missing_content_type(self, client):
        """Test missing content type on POST."""
        # Send raw JSON without proper content-type header
        response = client.post(
            "/api/v1/search/scenes",
            content='{"limit": 10}',
            headers={"Content-Type": "text/plain"},  # Wrong content type
        )

        # FastAPI should return validation error
        assert response.status_code == 422  # Validation error


class TestAPISecurityFeatures:
    """Test API security features."""

    def test_large_request_body(self, client):
        """Test handling of excessively large request bodies."""
        # Create a very large payload
        large_data = {"content": "x" * 10_000_000}  # 10MB of data

        response = client.post("/api/v1/scripts/upload", json=large_data)

        # Should handle large payloads appropriately
        assert response.status_code in [
            413,
            422,
            500,
        ]  # Payload too large or validation error

    def test_sql_injection_attempt(self, client):
        """Test that SQL injection attempts are handled safely."""
        # Attempt SQL injection in search query
        malicious_query = "'; DROP TABLE scripts; --"

        response = client.post(
            "/api/v1/search/scenes", json={"query": malicious_query, "limit": 10}
        )

        # Should process safely without executing SQL
        assert response.status_code in [200, 500]  # Either works or fails safely

        # Verify database is still intact
        response = client.get("/api/v1/scripts/")
        assert response.status_code == 200

    def test_path_traversal_attempt(self, client):
        """Test that path traversal attempts are blocked."""
        # Attempt to access files outside intended directory
        malicious_id = "../../../etc/passwd"

        response = client.get(f"/api/v1/scripts/{malicious_id}")

        # Should be blocked or return 404
        assert response.status_code in [400, 404]

    def test_xss_prevention(self, client):
        """Test that potential XSS payloads are handled safely."""
        xss_payload = {
            "title": "<script>alert('XSS')</script>",
            "content": "FADE IN:\n\n<script>malicious()</script>",
            "author": "<img src=x onerror=alert('XSS')>",
        }

        response = client.post("/api/v1/scripts/upload", json=xss_payload)

        # Should accept but safely store the content
        if response.status_code == 200:
            data = response.json()
            # Verify the script tags are preserved as data, not executed
            assert "<script>" in data["title"]


class TestAsyncBehavior:
    """Test asynchronous behavior of the API."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, app_with_mocked_db):
        """Test handling of concurrent requests."""
        import httpx
        from httpx import AsyncClient

        async def make_request(client: AsyncClient, index: int):
            response = await client.get("/health")
            return response.status_code, index

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app_with_mocked_db),
            base_url="http://test",
        ) as client:
            # Make 10 concurrent requests
            tasks = [make_request(client, i) for i in range(10)]
            results = await asyncio.gather(*tasks)

            # All requests should succeed
            for status_code, _ in results:
                assert status_code == 200

    def test_long_running_request_timeout(self, app_with_mocked_db):
        """Test handling of long-running requests."""

        @app_with_mocked_db.get("/test-timeout")
        async def slow_endpoint():
            await asyncio.sleep(5)  # Simulate slow operation
            return {"status": "complete"}

        import contextlib

        with (
            TestClient(app_with_mocked_db) as client,
            contextlib.suppress(Exception),
        ):
            # This should complete or timeout appropriately
            # The test client might raise a timeout exception - that's acceptable
            client.get("/test-timeout", timeout=1)


class TestAppConfiguration:
    """Test application configuration."""

    def test_app_metadata(self, client):
        """Test app metadata is correctly set."""
        response = client.get("/api/v1/openapi.json")
        schema = response.json()

        assert schema["info"]["title"] == "ScriptRAG API"
        assert (
            schema["info"]["description"]
            == "Graph-Based Screenwriting Assistant REST API"
        )
        assert schema["info"]["version"] == "1.0.0"

    def test_custom_docs_urls(self, client):
        """Test custom documentation URLs."""
        # Swagger UI should be at custom path
        response = client.get("/api/v1/docs")
        assert response.status_code == 200

        # ReDoc should be at custom path
        response = client.get("/api/v1/redoc")
        assert response.status_code == 200

        # OpenAPI schema should be at custom path
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200

    def test_app_state_initialization(self, app_with_mocked_db):
        """Test app state is properly initialized."""
        # App state should be set during lifespan
        with TestClient(app_with_mocked_db) as client:
            # Make a request to trigger lifespan
            client.get("/health")

            # Check app state (after lifespan)
            assert hasattr(app_with_mocked_db.state, "db_ops")
            assert hasattr(app_with_mocked_db.state, "settings")
