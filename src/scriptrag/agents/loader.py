"""Agent loader for markdown-based agent specifications."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import jsonschema
from jsonschema import ValidationError
from markdown_it import MarkdownIt

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger
from scriptrag.utils import get_default_llm_client

if TYPE_CHECKING:
    from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


class AgentSpec:
    """Represents a parsed agent specification from markdown."""

    def __init__(
        self,
        name: str,
        description: str,
        version: str,
        requires_llm: bool,
        context_query: str,
        output_schema: dict[str, Any],
        analysis_prompt: str,
    ) -> None:
        """Initialize an agent specification.

        Args:
            name: Agent name (derived from filename)
            description: Agent description
            version: Agent version
            requires_llm: Whether the agent requires an LLM
            context_query: SQL query for context
            output_schema: JSON schema for output validation
            analysis_prompt: Prompt template for LLM
        """
        self.name = name
        self.description = description
        self.version = version
        self.requires_llm = requires_llm
        self.context_query = context_query
        self.output_schema = output_schema
        self.analysis_prompt = analysis_prompt

    @classmethod
    def from_markdown(cls, markdown_path: Path) -> AgentSpec:
        """Load an agent specification from a markdown file.

        Args:
            markdown_path: Path to the markdown file

        Returns:
            Parsed AgentSpec instance

        Raises:
            ValueError: If the markdown file is invalid
        """
        if not markdown_path.exists():
            raise ValueError(f"Agent specification not found: {markdown_path}")

        # Parse the markdown file with frontmatter
        with markdown_path.open(encoding="utf-8") as f:
            post = frontmatter.load(f)

        # Extract metadata from frontmatter
        metadata = post.metadata
        if not metadata:
            raise ValueError(f"No frontmatter found in {markdown_path}")

        # Agent name is always derived from filename
        agent_name = markdown_path.stem

        # Check for required fields
        required_fields = ["description", "version"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field '{field}' in frontmatter")

        # Extract code blocks from content using proper markdown parser
        code_blocks = cls._extract_code_blocks(post.content)

        # Find context query block (SQL)
        context_query = ""
        for block in code_blocks:
            if block["lang"] == "sql":
                context_query = block["content"]
                break

        # Find output schema block (JSON)
        output_schema = {}
        for block in code_blocks:
            if block["lang"] == "json":
                try:
                    output_schema = json.loads(block["content"])
                    break
                except json.JSONDecodeError:
                    continue

        if not output_schema:
            raise ValueError("No valid JSON schema found in code blocks")

        # The full content becomes the analysis prompt
        analysis_prompt = post.content

        return cls(
            name=agent_name,
            description=metadata["description"],
            version=str(metadata["version"]),  # Ensure version is string
            requires_llm=metadata.get("requires_llm", True),
            context_query=context_query,
            output_schema=output_schema,
            analysis_prompt=analysis_prompt,
        )

    @staticmethod
    def _extract_code_blocks(content: str) -> list[dict[str, str]]:
        """Extract code blocks from markdown content using proper parser.

        Args:
            content: Markdown content

        Returns:
            List of code blocks with language and content
        """
        # Use markdown-it-py to parse the markdown
        md = MarkdownIt()
        tokens = md.parse(content)

        code_blocks = []
        for token in tokens:
            if token.type == "fence" and token.content:
                # Extract language from info string (e.g., "json" from "```json")
                lang = token.info.strip() if token.info else ""
                code_blocks.append({"lang": lang, "content": token.content.rstrip()})

        return code_blocks


class MarkdownAgentAnalyzer(BaseSceneAnalyzer):
    """Analyzer that wraps a markdown-based agent specification."""

    def __init__(self, spec: AgentSpec, config: dict[str, Any] | None = None) -> None:
        """Initialize the markdown agent analyzer.

        Args:
            spec: Agent specification
            config: Optional configuration
        """
        super().__init__(config)
        self.spec = spec
        self.llm_client: LLMClient | None = None

    @property
    def name(self) -> str:
        """Return the analyzer name."""
        return self.spec.name

    @property
    def version(self) -> str:
        """Return the analyzer version."""
        return self.spec.version

    @property
    def requires_llm(self) -> bool:
        """Return whether this analyzer requires an LLM."""
        return self.spec.requires_llm

    async def initialize(self) -> None:
        """Initialize the LLM client if needed."""
        if self.spec.requires_llm and self.llm_client is None:
            self.llm_client = await get_default_llm_client()
            logger.info(f"Initialized LLM client for agent {self.spec.name}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.llm_client = None

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene using the agent specification.

        Args:
            scene: Scene data

        Returns:
            Analysis results
        """
        if self.spec.requires_llm and not self.llm_client:
            await self.initialize()

        # Execute context query (placeholder for now)
        context = await self._execute_context_query(scene)

        # If LLM is required, call it
        if self.spec.requires_llm:
            result = await self._call_llm(scene, context)
        else:
            # For non-LLM agents, just return empty result
            result = {}

        # Validate the result against the schema
        try:
            jsonschema.validate(result, self.spec.output_schema)
        except ValidationError as e:
            logger.error(
                f"Agent {self.spec.name} output failed validation",
                error=str(e),
                scene_heading=scene.get("heading", ""),
            )
            # Return empty result on validation error
            return {
                "error": f"Output validation failed: {e.message}",
                "analyzer": self.name,
                "version": self.version,
            }

        # Add metadata
        result["analyzer"] = self.name
        result["version"] = self.version
        result["property"] = self.name  # Property is same as name

        return result

    async def _execute_context_query(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Execute the context query for the scene.

        This is a placeholder that will be implemented when scriptrag query
        is available.

        Args:
            scene: Scene data

        Returns:
            Context data from the query
        """
        # TODO: Implement actual SQL query execution once scriptrag query is ready
        # For now, return the scene data as context
        logger.debug(
            f"Context query placeholder for agent {self.spec.name}",
            query=self.spec.context_query,
        )
        return {"scene_data": scene}

    async def _call_llm(
        self, scene: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Call the LLM with the analysis prompt.

        Args:
            scene: Scene data
            context: Context data from query

        Returns:
            LLM response parsed as dictionary
        """
        # Format the prompt with scene content
        scene_content = self._format_scene_content(scene)
        prompt = self.spec.analysis_prompt.replace("{{scene_content}}", scene_content)

        # Add context if available
        if context:
            context_str = json.dumps(context, indent=2)
            prompt = prompt.replace("{{context}}", context_str)

        try:
            if self.llm_client is None:
                raise RuntimeError("LLM client not initialized")
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10000,
            )

            # Parse the response
            return self._parse_llm_response(response.content)

        except Exception as e:
            logger.error(
                f"LLM call failed for agent {self.spec.name}",
                error=str(e),
                scene_heading=scene.get("heading", ""),
            )
            return {}

    def _format_scene_content(self, scene: dict[str, Any]) -> str:
        """Format scene content for the prompt.

        Args:
            scene: Scene data

        Returns:
            Formatted scene content
        """
        parts = []

        if heading := scene.get("heading"):
            parts.append(f"SCENE HEADING: {heading}")

        if action := scene.get("action"):
            parts.append("ACTION:")
            for line in action:
                if line.strip():
                    parts.append(line)

        if dialogue := scene.get("dialogue"):
            parts.append("DIALOGUE:")
            for entry in dialogue:
                character = entry.get("character", "")
                text = entry.get("text", "")
                if character and text:
                    parts.append(f"{character}: {text}")

        if not parts and (content := scene.get("content")):
            parts.append(content)

        return "\n".join(parts)

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response as JSON with improved error handling.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary
        """
        response = response.strip()
        json_str = response

        # Strategy 1: Extract from markdown code blocks
        if "```" in response:
            # Look for ```json blocks first
            if "```json" in response:
                match = re.search(r"```json\s*\n?(.+?)\n?```", response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
            # Then try any code block
            else:
                match = re.search(r"```\s*\n?(.+?)\n?```", response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()

        # Strategy 2: Find JSON object in response
        if not json_str.startswith("{"):
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response, re.DOTALL)
            if match:
                json_str = match.group(0)

        # Try to parse the extracted string
        try:
            result = json.loads(json_str)
            # Ensure it's a dict
            if isinstance(result, dict):
                return result
            logger.warning(f"LLM response was not a dict for agent {self.spec.name}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM response as JSON for agent {self.spec.name}",
                error=str(e),
                response_preview=json_str[:500] if json_str else response[:500],
            )
            return {}


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
