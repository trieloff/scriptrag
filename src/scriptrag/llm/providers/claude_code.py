"""Claude Code SDK provider for local development."""

import os

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
        """Check if Claude Code SDK is available."""
        try:
            import claude_code_sdk  # noqa: F401

            self.sdk_available = True
            logger.debug("Claude Code SDK is available")
        except ImportError:
            logger.debug("Claude Code SDK not installed")
            self.sdk_available = False

    async def is_available(self) -> bool:
        """Check if running in Claude Code environment with SDK available."""
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

            # Set up options
            options = ClaudeCodeOptions(
                max_turns=1,
                system_prompt=request.system,
            )

            # Execute query
            messages: list[Message] = []
            async for message in query(prompt=prompt, options=options):
                messages.append(message)

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
