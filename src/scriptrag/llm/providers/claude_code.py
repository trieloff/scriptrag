"""Claude Code SDK provider for local development."""

import asyncio
import contextlib
import json
import os
import time

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)

logger = get_logger(__name__)


class ClaudeCodeProvider(BaseLLMProvider):
    """Claude Code SDK provider for local development."""

    provider_type = LLMProvider.CLAUDE_CODE

    def __init__(self) -> None:
        """Initialize Claude Code provider."""
        self.sdk_available = False
        self._check_sdk()

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
            from claude_code_sdk import ClaudeCodeOptions  # noqa: F401

            # If import succeeds, we have SDK access
            return True
        except ImportError:
            # SDK not available, check for environment markers as fallback
            # But only if we think SDK is available (which shouldn't happen)
            pass
        except Exception as e:
            logger.debug(f"Claude Code SDK check failed: {e}")

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
        """List available Claude models."""
        # TODO: Implement dynamic model discovery when Claude Code SDK supports it
        # Currently the SDK doesn't provide a way to list available models,
        # so we return a static list that may become outdated.
        # This should be updated when the SDK adds model enumeration support.
        return [
            Model(
                id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
            Model(
                id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using Claude Code SDK."""
        try:
            from claude_code_sdk import ClaudeCodeOptions, Message, query

            # Convert messages to prompt
            prompt = self._messages_to_prompt(request.messages)

            # If response_format is specified, add JSON instructions to the prompt
            if hasattr(request, "response_format") and request.response_format:
                schema_info = self._extract_schema_info(request.response_format)
                if schema_info:
                    prompt = self._add_json_instructions(prompt, schema_info)

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
                        schema_info = self._extract_schema_info(request.response_format)
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

            return CompletionResponse(
                id=f"claude-code-{os.getpid()}",
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                provider=self.provider_type,
            )

        except ImportError as e:
            # SDK not available, even though environment suggests we're in Claude Code
            logger.debug(f"Claude Code SDK not available for completion: {e}")
            raise RuntimeError(
                "Claude Code environment detected but SDK not available. "
                "Please use GitHub Models or OpenAI-compatible provider instead."
            ) from e
        except Exception as e:
            logger.error(f"Claude Code completion failed: {e}")
            raise

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

    def _extract_schema_info(self, response_format: dict) -> dict | None:
        """Extract schema information from response_format.

        Args:
            response_format: The response format specification

        Returns:
            Schema info dict or None
        """
        if not response_format:
            return None

        # Handle different response_format structures
        if response_format.get("type") == "json_schema":
            # OpenAI-style with nested json_schema
            json_schema = response_format.get("json_schema", {})
            return {
                "name": json_schema.get("name", "response"),
                "schema": json_schema.get("schema", {}),
            }
        if response_format.get("type") == "json_object":
            # Simple JSON object without schema
            return {"name": "response", "schema": {}}
        if "schema" in response_format:
            # Direct schema format
            return {
                "name": response_format.get("name", "response"),
                "schema": response_format["schema"],
            }

        return None

    def _add_json_instructions(self, prompt: str, schema_info: dict) -> str:
        """Add JSON output instructions to the prompt.

        Args:
            prompt: Original prompt
            schema_info: Schema information dict

        Returns:
            Modified prompt with JSON instructions
        """
        schema = schema_info.get("schema", {})

        # Build JSON instruction
        json_instruction = (
            "\n\nIMPORTANT: You must respond with valid JSON only, no other text."
        )

        if schema and "properties" in schema:
            props = schema["properties"]
            required = schema.get("required", [])

            json_instruction += "\n\nThe JSON response must have these properties:"
            for prop, details in props.items():
                prop_type = details.get("type", "any")
                desc = details.get("description", "")
                is_required = prop in required

                json_instruction += f"\n- {prop} ({prop_type})"
                if is_required:
                    json_instruction += " [REQUIRED]"
                if desc:
                    json_instruction += f": {desc}"

            # Add example if possible
            example = self._generate_example_from_schema(schema)
            if example:
                json_instruction += (
                    f"\n\nExample JSON structure:\n```json\n"
                    f"{json.dumps(example, indent=2)}\n```"
                )

        return prompt + json_instruction

    def _generate_example_from_schema(self, schema: dict) -> dict | None:
        """Generate an example JSON object from schema.

        Args:
            schema: JSON schema

        Returns:
            Example dict or None
        """
        if not schema or "properties" not in schema:
            return None

        example = {}
        props = schema["properties"]

        for prop, details in props.items():
            prop_type = details.get("type", "string")

            if prop_type == "array":
                items_type = details.get("items", {}).get("type", "string")
                if items_type == "object":
                    # For complex objects, provide a single example
                    example[prop] = [
                        self._generate_object_example(details.get("items", {}))
                    ]
                else:
                    example[prop] = []
            elif prop_type == "object":
                example[prop] = self._generate_object_example(details)
            elif prop_type == "number" or prop_type == "integer":
                example[prop] = 0
            elif prop_type == "boolean":
                example[prop] = False
            else:  # string or unknown
                example[prop] = ""

        return example

    def _generate_object_example(self, obj_schema: dict) -> dict:
        """Generate example for object type.

        Args:
            obj_schema: Object schema

        Returns:
            Example object
        """
        if "properties" in obj_schema:
            result = {}
            for key, val in obj_schema["properties"].items():
                prop_type = val.get("type", "string")
                if prop_type == "string":
                    result[key] = ""
                elif prop_type in ["number", "integer"]:
                    result[key] = 0
                elif prop_type == "boolean":
                    result[key] = False
                elif prop_type == "array":
                    result[key] = []
                elif prop_type == "object":
                    result[key] = {}
            return result
        return {}
