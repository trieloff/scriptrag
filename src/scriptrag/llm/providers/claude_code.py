"""Claude Code SDK provider for local development."""

import asyncio
import contextlib
import json
import os
import time
from typing import Any, ClassVar

from scriptrag.config import get_logger, get_settings
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.model_discovery import ClaudeCodeModelDiscovery
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)
from scriptrag.llm.providers.claude_schema import ClaudeSchemaHandler

logger = get_logger(__name__)


class ClaudeCodeProvider(BaseLLMProvider):
    """Claude Code SDK provider for local development."""

    provider_type = LLMProvider.CLAUDE_CODE

    # Static model list as fallback - updated with latest models
    STATIC_MODELS: ClassVar[list[Model]] = [
        # Claude 3 models
        Model(
            id="claude-3-opus-20240229",
            name="Claude 3 Opus",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=4096,
        ),
        Model(
            id="claude-3-sonnet-20240229",
            name="Claude 3 Sonnet",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=4096,
        ),
        Model(
            id="claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=4096,
        ),
        # Claude 3.5 models
        Model(
            id="claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=8192,
        ),
        # Latest Claude models (model aliases)
        Model(
            id="sonnet",
            name="Claude Sonnet (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="opus",
            name="Claude Opus (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="haiku",
            name="Claude Haiku (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["completion", "chat"],
            context_window=200000,
            max_output_tokens=8192,
        ),
    ]

    def __init__(self) -> None:
        """Initialize Claude Code provider."""
        self.sdk_available: bool = False
        self._check_sdk()

        # Initialize model discovery
        settings = get_settings()

        self.model_discovery: ClaudeCodeModelDiscovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=self.STATIC_MODELS,
            cache_ttl=(
                settings.llm_model_cache_ttl
                if settings.llm_model_cache_ttl > 0
                else None
            ),
            use_cache=settings.llm_model_cache_ttl > 0,
            force_static=settings.llm_force_static_models,
        )

        # Initialize schema handler
        self.schema_handler = ClaudeSchemaHandler()

    def _check_sdk(self) -> None:
        """Check if Claude Code SDK and executable are available."""
        try:
            # Check if the claude executable is available in PATH
            import shutil

            import claude_code_sdk  # noqa: F401

            if shutil.which("claude") is not None:
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

        # We need BOTH the environment AND the SDK to be available
        # Just having the environment without SDK means we can't actually use it

        # First check if SDK is available
        if not self.sdk_available:
            # Even if we're in Claude Code environment, without SDK we can't do anything
            return False

        # Try to import and use the SDK directly
        try:
            import claude_code_sdk

            # Check if SDK is available by accessing the module
            _ = claude_code_sdk.ClaudeCodeOptions

            # If import succeeds, we have SDK access
            return True
        except (ImportError, AttributeError):
            # SDK not available, check for environment markers as fallback
            # But only if we think SDK is available (which shouldn't happen)
            pass
        except ModuleNotFoundError as e:
            # ModuleNotFoundError: SDK module not found
            logger.debug(f"Claude Code SDK module not found: {e}")
        except Exception as e:
            # Any other exception during SDK check - fallback to environment markers
            logger.debug(f"Claude Code SDK check failed with unexpected error: {e}")

        # Check for Claude Code environment markers as last resort
        # This shouldn't normally be reached if SDK detection works properly
        claude_markers = [
            "CLAUDECODE",  # Primary marker for Claude Code environment
            "CLAUDE_CODE_SESSION",
            "CLAUDE_SESSION_ID",
            "CLAUDE_WORKSPACE",
        ]

        # Only return True if we have markers AND SDK was detected earlier
        return (
            any(os.getenv(marker) for marker in claude_markers) and self.sdk_available
        )

    async def list_models(self) -> list[Model]:
        """List available Claude models using dynamic discovery with fallback."""
        return await self.model_discovery.discover_models()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using Claude Code SDK."""
        try:
            from claude_code_sdk import ClaudeCodeOptions, Message, query

            # Convert messages to prompt
            prompt = self._messages_to_prompt(request.messages)

            # If response_format is specified, add JSON instructions to the prompt
            if hasattr(request, "response_format") and request.response_format:
                schema_info = self.schema_handler.extract_schema_info(
                    request.response_format
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
            max_retries = (
                3
                if hasattr(request, "response_format") and request.response_format
                else 1
            )

            for attempt in range(max_retries):
                # Execute query with monitoring
                messages: list[Message] = []
                query_start_time = time.time()
                logger.info(
                    f"Claude Code query started (attempt {attempt + 1}/{max_retries})",
                    prompt_length=len(prompt),
                    has_system=bool(request.system),
                )

                # Create a task to monitor progress
                async def log_progress(
                    current_attempt: int, current_prompt: str
                ) -> None:
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

                # Start progress monitoring
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
                                has_content=hasattr(message, "content"),
                                has_result=hasattr(message, "result"),
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
                        prompt_length=len(prompt),
                    )

                    if attempt < max_retries - 1:
                        logger.info(
                            f"Retrying Claude Code query "
                            f"(attempt {attempt + 2}/{max_retries})"
                        )
                        continue
                    raise TimeoutError(
                        f"Claude Code query timed out after {query_timeout}s"
                    ) from None

                # Convert to response format
                response_text = ""
                # Look for AssistantMessage which contains the actual response
                for msg in messages:
                    if msg.__class__.__name__ == "AssistantMessage" and hasattr(
                        msg, "content"
                    ):
                        # Content is a list of TextBlock objects
                        for block in msg.content:
                            if hasattr(block, "text"):
                                response_text += block.text
                        break

                # Fallback: Check ResultMessage for the result text
                if not response_text:
                    for msg in messages:
                        if msg.__class__.__name__ == "ResultMessage" and hasattr(
                            msg, "result"
                        ):
                            # Ensure we convert Any type to string safely
                            result = msg.result
                            response_text = str(result) if result is not None else ""
                            break

                # If response_format is specified, validate the JSON
                if hasattr(request, "response_format") and request.response_format:
                    try:
                        # Extract JSON from markdown code blocks if present
                        json_text = response_text
                        if "```json" in response_text:
                            # Extract JSON from code block
                            import re

                            match = re.search(
                                r"```json\s*\n(.*?)\n```", response_text, re.DOTALL
                            )
                            if match:
                                json_text = match.group(1).strip()
                        elif "```" in response_text:
                            # Try any code block
                            import re

                            match = re.search(
                                r"```\s*\n(.*?)\n```", response_text, re.DOTALL
                            )
                            if match:
                                json_text = match.group(1).strip()

                        # Try to parse and validate JSON
                        parsed = json.loads(json_text)

                        # If we have a schema, validate against it
                        schema_info = self.schema_handler.extract_schema_info(
                            request.response_format
                        )
                        if schema_info and "schema" in schema_info:
                            # Basic validation - ensure required fields exist
                            schema = schema_info["schema"]
                            if "properties" in schema:
                                required = schema.get("required", [])
                                for field in required:
                                    if field not in parsed:
                                        raise ValueError(
                                            f"Missing required field: {field}"
                                        )

                        # JSON is valid, update response_text to be just the JSON
                        response_text = json_text
                        logger.debug(
                            f"Claude Code generated valid JSON on attempt {attempt + 1}"
                        )
                        break

                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(
                            f"Claude Code JSON validation failed on "
                            f"attempt {attempt + 1}: {e}"
                        )

                        if attempt < max_retries - 1:
                            # Add error feedback to prompt for retry
                            prompt = (
                                f"{prompt}\n\nThe previous response was not "
                                f"valid JSON. Error: {e}\nPlease provide a "
                                f"valid JSON response that matches the schema."
                            )
                        else:
                            # Final attempt failed, log the response for debugging
                            logger.error(
                                f"Claude Code failed to generate valid JSON "
                                f"after {max_retries} attempts",
                                last_response=response_text[:500],
                            )
                else:
                    # No response_format, accept any response
                    break

            choice: dict[str, Any] = {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
            usage: dict[str, int] = {
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
            # SDK not available, even though environment suggests we're in Claude Code
            logger.debug(f"Claude Code SDK not available for completion: {e}")
            raise RuntimeError(
                "Claude Code environment detected but SDK not available. "
                "Please use GitHub Models or OpenAI-compatible provider instead."
            ) from e
        except (TimeoutError, json.JSONDecodeError, ValueError) as e:
            # asyncio.TimeoutError: Query timeout
            # json.JSONDecodeError: Invalid JSON response
            # ValueError: JSON validation errors
            logger.error(f"Claude Code completion failed: {e}")
            raise
        except AttributeError as e:
            # AttributeError: SDK response object missing expected attributes
            logger.error(f"Claude Code response parsing failed: {e}")
            raise RuntimeError(f"Invalid SDK response structure: {e}") from e

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
