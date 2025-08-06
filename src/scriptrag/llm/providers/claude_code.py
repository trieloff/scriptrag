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
        """Check if running in Claude Code environment."""
        if not self.sdk_available:
            return False

        # Primary method: Try to import and use the SDK directly
        try:
            from claude_code_sdk import ClaudeCodeOptions  # noqa: F401

            # If import succeeds, we likely have SDK access
            return True
        except ImportError:
            pass  # SDK not available, try fallback detection
        except Exception as e:
            logger.debug(f"Claude Code SDK check failed: {e}")

        # Fallback method: Check for Claude Code environment markers
        # This is less reliable but kept for backward compatibility
        claude_markers = [
            "CLAUDE_CODE_SESSION",
            "CLAUDE_SESSION_ID",
            "CLAUDE_WORKSPACE",
        ]

        return any(os.getenv(marker) for marker in claude_markers)

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
            if messages:
                # Extract text content from last message
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    response_text = str(last_msg.content)

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
