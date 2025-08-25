"""Enhanced base class for LLM providers with common functionality."""

from abc import abstractmethod
from typing import Any

import httpx

from scriptrag.config import get_logger, get_settings
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import Model
from scriptrag.llm.rate_limiter import RateLimiter

logger = get_logger(__name__)

# HTTP timeout constants
DEFAULT_HTTP_TIMEOUT = 30.0  # seconds
DEFAULT_AVAILABILITY_CACHE_TTL = 300  # 5 minutes


class EnhancedBaseLLMProvider(BaseLLMProvider):
    """Enhanced base class with common functionality for LLM providers."""

    def __init__(
        self,
        token: str | None = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        base_url: str | None = None,
    ) -> None:
        """Initialize enhanced provider.

        Args:
            token: API token/key for authentication
            timeout: HTTP request timeout in seconds
            base_url: Base URL for API endpoints
        """
        self.token = token
        self.timeout = timeout
        self.base_url = base_url
        self.rate_limiter = RateLimiter()
        self.client: httpx.AsyncClient | None = None
        self._models_cache: list[Model] | None = None

    def _init_http_client(self) -> None:
        """Initialize HTTP client if not already initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self) -> "EnhancedBaseLLMProvider":
        """Enter async context manager."""
        self._init_http_client()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Exit async context manager and cleanup."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def is_available(self) -> bool:
        """Check if provider is available.

        Base implementation checks:
        1. Token/authentication is configured
        2. Not currently rate limited
        3. Cached availability status

        Subclasses should override to add provider-specific checks.
        """
        # Check if we have authentication
        if not self.token:
            logger.debug(
                f"{self.provider_type.value} not available: no token configured"
            )
            return False

        # Check if we're rate limited
        if self.rate_limiter.is_rate_limited():
            return False

        # Check cached availability
        cached = self.rate_limiter.check_availability_cache()
        if cached is not None:
            return cached

        # Subclasses should implement actual availability check
        return True

    def _validate_response_structure(
        self, data: Any, required_fields: list[str], response_type: str = "API response"
    ) -> None:
        """Validate that response data contains required fields.

        Args:
            data: Response data to validate
            required_fields: List of field names that must be present
            response_type: Type description for error messages

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(data, dict):
            raise ValueError(f"{response_type} must be a dictionary, got {type(data)}")

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(
                f"{response_type} missing required fields: {', '.join(missing_fields)}"
            )

    @abstractmethod
    async def _validate_availability(self) -> bool:
        """Validate provider availability with actual API call.

        Subclasses must implement this to check API accessibility.

        Returns:
            True if API is accessible, False otherwise
        """
        pass

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Default implementation for Bearer token.
        Subclasses can override for different auth schemes.

        Returns:
            Dictionary of auth headers with token masked for logging safety
        """
        if not self.token:
            return {"Content-Type": "application/json"}

        # Create a secure header dict that masks the token if accidentally logged
        class SecureHeaders(dict):
            def __str__(self) -> str:
                return str(
                    {
                        k: "Bearer [REDACTED]" if k == "Authorization" else v
                        for k, v in self.items()
                    }
                )

            def __repr__(self) -> str:
                return self.__str__()

        return SecureHeaders(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )

    def _handle_rate_limit(
        self, status_code: int, error_text: str, wait_seconds: int | None = None
    ) -> None:
        """Handle rate limit errors.

        Args:
            status_code: HTTP status code
            error_text: Error response text
            wait_seconds: Optional wait time in seconds
        """
        _ = error_text  # May be used by subclasses for parsing
        if status_code == 429 and wait_seconds:
            self.rate_limiter.set_rate_limit(wait_seconds, self.provider_type.value)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: Optional JSON payload
            headers: Optional additional headers

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: On network errors
            ValueError: On API errors
        """
        if not self.client:
            self._init_http_client()

        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        # Merge auth headers with custom headers
        request_headers = self._get_auth_headers()
        if headers:
            request_headers.update(headers)

        # Build full URL
        if not self.base_url:
            raise ValueError("Base URL not configured")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=request_headers)
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=request_headers, json=json_data
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return response

        except httpx.HTTPError as e:
            logger.error(
                f"{self.provider_type.value} request failed",
                error=str(e),
                endpoint=endpoint,
            )
            raise

    def _init_model_discovery(
        self,
        discovery_class: type,
        static_models: list[Model],
        **kwargs: Any,
    ) -> Any:
        """Initialize model discovery with common settings.

        Args:
            discovery_class: Model discovery class to instantiate
            static_models: Static model list
            **kwargs: Additional arguments for discovery class

        Returns:
            Initialized model discovery instance
        """
        settings = get_settings()

        return discovery_class(
            provider_name=self.provider_type.value,
            static_models=static_models,
            cache_ttl=(
                settings.llm_model_cache_ttl
                if settings.llm_model_cache_ttl > 0
                else None
            ),
            use_cache=settings.llm_model_cache_ttl > 0,
            force_static=settings.llm_force_static_models,
            **kwargs,
        )
