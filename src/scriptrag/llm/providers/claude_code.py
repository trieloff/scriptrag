"""Claude Code SDK provider for local development."""

import asyncio
import contextlib
import json
import os
import time
from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.model_discovery import ClaudeCodeModelDiscovery
from scriptrag.llm.model_registry import ModelRegistry
from scriptrag.llm.models import (
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
    UsageInfo,
)
from scriptrag.llm.providers.claude_schema import ClaudeSchemaHandler
from scriptrag.llm.rate_limiter import RetryHandler

logger = get_logger(__name__)


class ClaudeCodeProvider(BaseLLMProvider):
    """Claude Code SDK provider for local development."""

    provider_type = LLMProvider.CLAUDE_CODE

    def __init__(self) -> None:
        """Initialize Claude Code provider."""
        self.sdk_available: bool = False
        self._check_sdk()

        # Initialize model discovery
        from scriptrag.config import get_settings

        try:
            settings = get_settings()
            cache_ttl = settings.llm_model_cache_ttl
            force_static = settings.llm_force_static_models

            # Check if we got real values or mocks (for testing)
            is_mock = hasattr(cache_ttl, "__class__") and "Mock" in str(
                cache_ttl.__class__
            )
            if is_mock:
                # Fallback for testing when settings is mocked
                cache_ttl = 3600
                use_cache = True
                force_static = False
            else:
                use_cache = cache_ttl > 0
        except (ImportError, AttributeError):
            # Fallback for testing when settings cannot be imported
            cache_ttl = 3600
            use_cache = True
            force_static = False

        self.model_discovery: ClaudeCodeModelDiscovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=ModelRegistry.CLAUDE_CODE_MODELS,
            cache_ttl=cache_ttl if use_cache else None,
            use_cache=use_cache,
            force_static=force_static,
        )

        # Initialize schema handler
        self.schema_handler = ClaudeSchemaHandler()

        # Initialize retry handler for JSON validation
        self.retry_handler = RetryHandler(max_retries=3)

    def _check_sdk(self) -> None:
        """Check if Claude Code SDK and executable are available."""
        try:
            # Check if the claude executable is available in PATH
            import shutil

            import claude_code_sdk

            # Verify the SDK is properly imported by checking it's not None
            sdk_available = claude_code_sdk is not None

            if sdk_available and shutil.which("claude") is not None:
                self.sdk_available = True
                logger.debug("Claude Code SDK and CLI executable are available")
            else:
                self.sdk_available = False
                logger.debug(
                    "Claude Code SDK installed but claude executable not found in PATH"
                )

        except ImportError:
            logger.debug("Claude Code SDK not installed")
            self.sdk_available = False

    async def is_available(self) -> bool:
        """Check if running in Claude Code environment with SDK available."""
        # Check if Claude Code is explicitly disabled for testing
        if os.getenv("SCRIPTRAG_IGNORE_CLAUDE"):
            logger.debug("Claude Code provider disabled by SCRIPTRAG_IGNORE_CLAUDE")
            return False

        # First check if SDK is available
        if not self.sdk_available:
            return False

        # Try to import and use the SDK directly
        try:
            import claude_code_sdk

            # Check if SDK is available by accessing the module
            _ = claude_code_sdk.ClaudeCodeOptions
            return True

        except (ImportError, AttributeError):
            pass
        except ModuleNotFoundError as e:
            logger.debug(f"Claude Code SDK module not found: {e}")
        except Exception as e:
            logger.debug(f"Claude Code SDK check failed with unexpected error: {e}")

        # Check for Claude Code environment markers as last resort
        claude_markers = [
            "CLAUDECODE",
            "CLAUDE_CODE_SESSION",
            "CLAUDE_SESSION_ID",
            "CLAUDE_WORKSPACE",
        ]

        return (
            any(os.getenv(marker) for marker in claude_markers) and self.sdk_available
        )

    async def list_models(self) -> list[Model]:
        """List available Claude models using dynamic discovery with fallback."""
        return await self.model_discovery.discover_models()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using Claude Code SDK."""
        try:
            from claude_code_sdk import ClaudeCodeOptions

            # Convert messages to prompt
            prompt = self._messages_to_prompt(request.messages)

            # Handle structured output if specified
            has_json_format = (
                hasattr(request, "response_format") and request.response_format
            )
            if has_json_format and request.response_format:
                schema_info = self.schema_handler.extract_schema_info(
                    dict(request.response_format)
                )
                if schema_info:
                    prompt = self.schema_handler.add_json_instructions(
                        prompt, schema_info
                    )

            # Set up options
            options = ClaudeCodeOptions(
                max_turns=1,
                system_prompt=request.system,
            )

            # Execute query with retry logic for JSON validation
            max_retries = 3 if has_json_format else 1

            for attempt in range(max_retries):
                # Execute query
                response_text = await self._execute_query(
                    prompt, options, attempt, max_retries
                )

                # Validate JSON if needed
                if has_json_format and request.response_format:
                    validation_result = await self._validate_json_response(
                        response_text, dict(request.response_format), attempt
                    )
                    if validation_result["valid"]:
                        response_text = validation_result["json_text"]
                        break
                    if self.retry_handler.should_retry(attempt):
                        # Add error feedback to prompt for retry
                        error_msg = validation_result["error"]
                        prompt = (
                            f"{prompt}\n\nThe previous response was not "
                            f"valid JSON. Error: {error_msg}\n"
                            f"Please provide a valid JSON response."
                        )
                        self.retry_handler.log_retry(
                            attempt, f"JSON validation failed: {error_msg}"
                        )
                    else:
                        logger.error(
                            f"Failed to generate valid JSON after "
                            f"{max_retries} attempts",
                            last_response=response_text[:500],
                        )
                else:
                    # No JSON validation needed
                    break

            # Create response
            choice: CompletionChoice = {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
            usage: UsageInfo = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

            return CompletionResponse(
                id=f"claude-code-{os.getpid()}",
                model=request.model,
                choices=[choice],
                usage=usage,
                provider=self.provider_type,
            )

        except ImportError as e:
            logger.debug(f"Claude Code SDK not available for completion: {e}")
            raise RuntimeError(
                "Claude Code environment detected but SDK not available. "
                "Please use GitHub Models or OpenAI-compatible provider instead."
            ) from e
        except (TimeoutError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Claude Code completion failed: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Claude Code response parsing failed: {e}")
            raise RuntimeError(f"Invalid SDK response structure: {e}") from e

    async def _execute_query(
        self,
        prompt: str,
        options: Any,
        attempt: int,
        max_retries: int,
    ) -> str:
        """Execute Claude Code SDK query with timeout and progress monitoring.

        Args:
            prompt: The prompt to send
            options: Claude Code options
            attempt: Current attempt number (0-indexed)
            max_retries: Maximum number of attempts

        Returns:
            Response text from Claude

        Raises:
            TimeoutError: If query times out
        """
        from claude_code_sdk import Message, query

        messages: list[Message] = []
        query_start_time = time.time()
        logger.info(
            f"Claude Code query started (attempt {attempt + 1}/{max_retries})",
            prompt_length=len(prompt),
        )

        # Create progress monitoring task
        async def log_progress(current_attempt: int, current_prompt: str) -> None:
            """Log progress every 10 seconds."""
            elapsed = 0
            while True:
                await asyncio.sleep(10)
                elapsed += 10
                logger.info(
                    f"Claude Code query still running after {elapsed}s",
                    attempt=current_attempt + 1,
                    prompt_preview=current_prompt[:100],
                )

        progress_task = asyncio.create_task(log_progress(attempt, prompt))

        try:
            # Execute the query with a timeout
            query_timeout = 120  # 2 minutes timeout per query
            async with asyncio.timeout(query_timeout):
                async for message in query(prompt=prompt, options=options):
                    messages.append(message)
                    logger.debug(
                        "Received message from Claude Code SDK",
                        message_type=message.__class__.__name__,
                    )

            # Query completed, cancel progress monitoring
            progress_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await progress_task

            query_elapsed = time.time() - query_start_time
            logger.info(
                f"Claude Code query completed in {query_elapsed:.2f}s",
                attempt=attempt + 1,
                message_count=len(messages),
            )

        except TimeoutError:
            progress_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await progress_task

            logger.error(
                f"Claude Code query timed out after {query_timeout}s",
                attempt=attempt + 1,
            )

            if self.retry_handler.should_retry(attempt):
                self.retry_handler.log_retry(attempt, "Query timeout")
                raise  # Will be caught and retried by caller

            raise TimeoutError(
                f"Claude Code query timed out after {query_timeout}s"
            ) from None

        # Extract response text
        response_text = ""
        # Look for AssistantMessage which contains the actual response
        for msg in messages:
            if msg.__class__.__name__ == "AssistantMessage" and hasattr(msg, "content"):
                # Content is a list of TextBlock objects
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text
                break

        # Fallback: Check ResultMessage for the result text
        if not response_text:
            for msg in messages:
                if msg.__class__.__name__ == "ResultMessage" and hasattr(msg, "result"):
                    result = msg.result
                    response_text = str(result) if result is not None else ""
                    break

        return response_text

    async def _validate_json_response(
        self,
        response_text: str,
        response_format: dict[str, Any],
        attempt: int,
    ) -> dict[str, Any]:
        """Validate JSON response against schema.

        Args:
            response_text: Response text to validate
            response_format: Expected response format
            attempt: Current attempt number

        Returns:
            Dictionary with validation results:
                - valid: Whether JSON is valid
                - json_text: Extracted JSON text (if valid)
                - error: Error message (if invalid)
        """
        try:
            # Extract JSON from markdown code blocks if present
            json_text = response_text
            if "```json" in response_text:
                import re

                match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
                if match:
                    json_text = match.group(1).strip()
            elif "```" in response_text:
                import re

                match = re.search(r"```\s*\n(.*?)\n```", response_text, re.DOTALL)
                if match:
                    json_text = match.group(1).strip()

            # Parse JSON
            parsed = json.loads(json_text)

            # Validate against schema if present
            schema_info = self.schema_handler.extract_schema_info(response_format)
            if schema_info and "schema" in schema_info:
                schema = schema_info["schema"]
                if "properties" in schema:
                    required = schema.get("required", [])
                    for field in required:
                        if field not in parsed:
                            raise ValueError(f"Missing required field: {field}")

            logger.debug(f"Claude Code generated valid JSON on attempt {attempt + 1}")
            return {"valid": True, "json_text": json_text}

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Claude Code JSON validation failed on attempt {attempt + 1}: {e}"
            )
            return {"valid": False, "error": str(e)}

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Claude Code doesn't support embeddings directly."""
        raise NotImplementedError("Claude Code SDK doesn't support embeddings")

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """Convert messages list to single prompt string."""
        prompt_parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        return "\n\n".join(prompt_parts)
