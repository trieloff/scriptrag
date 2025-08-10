"""Agent loader for managing markdown-based agents."""

from __future__ import annotations

from pathlib import Path

from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.agents.markdown_agent_analyzer import MarkdownAgentAnalyzer
from scriptrag.common import FileSourceResolver
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
        self.custom_agents_dir = agents_dir
        self._cache: dict[str, AgentSpec] = {}
        self._max_cache_size = max_cache_size
        self._cache_order: list[str] = []  # Track order for LRU eviction

        # Initialize file source resolver for agents
        self._resolver = FileSourceResolver(
            file_type="agents",
            env_var="SCRIPTRAG_AGENTS_DIR",
            default_subdir="agents/builtin",
            file_extension="md",
        )

        # For backward compatibility, keep agents_dir property
        if agents_dir:
            self.agents_dir = agents_dir
        else:
            # Use first directory from resolver as default
            dirs = self._resolver.get_search_directories()
            self.agents_dir = dirs[0] if dirs else Path()

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
            # Look for agent file
            agent_file = None

            # If a custom directory was explicitly provided, search only there
            if self.custom_agents_dir and self.custom_agents_dir.exists():
                candidate = self.custom_agents_dir / f"{name}.md"
                if candidate.exists():
                    agent_file = candidate
                    logger.debug(f"Found agent '{name}' in {self.custom_agents_dir}")
            else:
                # Search in all directories from resolver
                dirs = self._resolver.get_search_directories(self.custom_agents_dir)
                for directory in dirs:
                    candidate = directory / f"{name}.md"
                    if candidate.exists():
                        agent_file = candidate
                        logger.debug(f"Found agent '{name}' in {directory}")
                        break

            if not agent_file:
                if self.custom_agents_dir:
                    raise ValueError(
                        f"Agent '{name}' not found in {self.custom_agents_dir}"
                    )
                search_dirs = self._resolver.get_search_directories(None)
                dirs_str = ", ".join(str(d) for d in search_dirs)
                raise ValueError(f"Agent '{name}' not found. Searched in: {dirs_str}")

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
        # If a custom directory was explicitly provided, only use that
        if self.custom_agents_dir and self.custom_agents_dir.exists():
            # Use only the custom directory, not the resolver's multiple directories
            agent_files = list(self.custom_agents_dir.glob("*.md"))
        else:
            # Discover all agent files using the resolver from multiple sources
            agent_files = self._resolver.discover_files(self.custom_agents_dir, "*.md")

        agents = []
        seen_names = set()

        for path in agent_files:
            try:
                # Use stem as agent name directly to avoid parsing all files
                agent_name = path.stem

                # Skip duplicates (resolver already handles priority)
                if agent_name in seen_names:
                    continue

                # Validate the name to prevent security issues
                if self._is_valid_agent_name(agent_name):
                    agents.append(agent_name)
                    seen_names.add(agent_name)
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
