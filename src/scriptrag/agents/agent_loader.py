"""Agent loader for managing markdown-based agents."""

from __future__ import annotations

from pathlib import Path

from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.agents.markdown_agent_analyzer import MarkdownAgentAnalyzer
from scriptrag.config import get_logger

logger = get_logger(__name__)


class AgentLoader:
    """Loads and manages markdown-based agents."""

    def __init__(
        self,
        agents_dir: Path | None = None,
        max_cache_size: int = 100,
    ) -> None:
        """Initialize the agent loader.

        Args:
            agents_dir: Directory containing agent markdown files
            max_cache_size: Maximum number of agents to cache (default 100)
        """
        if agents_dir is None:
            # Default to src/scriptrag/agents/builtin
            from scriptrag import __file__ as pkg_file

            pkg_dir = Path(pkg_file).parent
            agents_dir = pkg_dir / "agents" / "builtin"

        self.agents_dir = agents_dir
        self._cache: dict[str, AgentSpec] = {}
        self._max_cache_size = max_cache_size
        self._cache_order: list[str] = []  # Track order for LRU eviction

    def load_agent(self, name: str) -> MarkdownAgentAnalyzer:
        """Load an agent by name.

        Args:
            name: Agent name

        Returns:
            MarkdownAgentAnalyzer instance

        Raises:
            ValueError: If agent not found
        """
        # Check cache first
        if name in self._cache:
            spec = self._cache[name]
            # Move to end of LRU order
            if name in self._cache_order:
                self._cache_order.remove(name)
                self._cache_order.append(name)
        else:
            # Look for markdown file
            agent_file = self.agents_dir / f"{name}.md"
            if not agent_file.exists():
                raise ValueError(f"Agent '{name}' not found in {self.agents_dir}")

            # Load and cache the spec with LRU eviction
            spec = AgentSpec.from_markdown(agent_file)

            # Implement LRU cache eviction
            if len(self._cache) >= self._max_cache_size and self._cache_order:
                # Remove least recently used item
                oldest = self._cache_order.pop(0)
                del self._cache[oldest]

            self._cache[name] = spec
            self._cache_order.append(name)

        return MarkdownAgentAnalyzer(spec)

    def list_agents(self) -> list[str]:
        """List available agents.

        Returns:
            List of agent names
        """
        if not self.agents_dir.exists():
            return []

        agents = []
        for path in self.agents_dir.glob("*.md"):
            try:
                # Use stem as agent name directly to avoid parsing all files
                agent_name = path.stem
                # Validate the name to prevent security issues
                if self._is_valid_agent_name(agent_name):
                    agents.append(agent_name)
                else:
                    logger.warning(f"Invalid agent name: {agent_name}")
            except Exception as e:
                logger.warning(f"Failed to process agent file {path}: {e}")

        # Sort with input validation
        return sorted(agents, key=lambda x: x.lower())

    @staticmethod
    def _is_valid_agent_name(name: str) -> bool:
        """Validate agent name for security.

        Args:
            name: Agent name to validate

        Returns:
            True if valid, False otherwise
        """
        # Only allow alphanumeric, underscore, and dash
        import re

        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name)) and len(name) < 100
