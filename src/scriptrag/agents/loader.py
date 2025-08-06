"""Agent loader for markdown-based agent specifications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import jsonschema
from jsonschema import ValidationError

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
        property: str,  # noqa: A002
        description: str,
        version: str,
        requires_llm: bool,
        context_query: str,
        output_schema: dict[str, Any],
        analysis_prompt: str,
    ) -> None:
        """Initialize an agent specification.

        Args:
            name: Agent name
            property: Property name for storing results
            description: Agent description
            version: Agent version
            requires_llm: Whether the agent requires an LLM
            context_query: SQL query for context
            output_schema: JSON schema for output validation
            analysis_prompt: Prompt template for LLM
        """
        self.name = name
        self.property = property
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

        required_fields = ["name", "property", "description", "version"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field '{field}' in frontmatter")

        # Parse the content sections
        content = post.content
        sections = cls._parse_sections(content)

        # Extract required sections
        if "Context Query" not in sections:
            raise ValueError("Missing 'Context Query' section")
        if "Output Schema" not in sections:
            raise ValueError("Missing 'Output Schema' section")
        if "Analysis Prompt" not in sections:
            raise ValueError("Missing 'Analysis Prompt' section")

        # Parse the output schema JSON
        try:
            output_schema = json.loads(sections["Output Schema"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Output Schema: {e}") from e

        return cls(
            name=metadata["name"],
            property=metadata["property"],
            description=metadata["description"],
            version=str(metadata["version"]),  # Ensure version is string
            requires_llm=metadata.get("requires_llm", True),
            context_query=sections["Context Query"].strip(),
            output_schema=output_schema,
            analysis_prompt=sections["Analysis Prompt"].strip(),
        )

    @staticmethod
    def _parse_sections(content: str) -> dict[str, str]:
        """Parse markdown content into sections.

        Args:
            content: Markdown content

        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        current_section = None
        current_content: list[str] = []
        in_code_block = False
        code_block_content: list[str] = []

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Handle code blocks
            if line.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    # Skip the opening ``` line
                else:
                    # End of code block
                    in_code_block = False
                    if current_section:
                        # Add the code block content to the current section
                        current_content.extend(code_block_content)
                    code_block_content = []
            elif in_code_block:
                code_block_content.append(line)
            elif line.startswith("## "):
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

            i += 1

        # Save the last section
        if current_section:
            if code_block_content:
                current_content.extend(code_block_content)
            sections[current_section] = "\n".join(current_content).strip()

        return sections


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
        result["property"] = self.spec.property

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
                max_tokens=2000,
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
        """Parse LLM response as JSON.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary
        """
        response = response.strip()

        # Extract JSON from code blocks if present
        if "```json" in response:
            import re

            match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if match:
                response = match.group(1)
        elif "```" in response:
            import re

            match = re.search(r"```\n(.*?)\n```", response, re.DOTALL)
            if match:
                response = match.group(1)

        try:
            return dict(json.loads(response))
        except json.JSONDecodeError:
            # Try to find JSON object in response
            import re

            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                return dict(json.loads(match.group()))
            return {}


class AgentLoader:
    """Loads and manages markdown-based agents."""

    def __init__(self, agents_dir: Path | None = None) -> None:
        """Initialize the agent loader.

        Args:
            agents_dir: Directory containing agent markdown files
        """
        if agents_dir is None:
            # Default to src/scriptrag/agents/builtin
            from scriptrag import __file__ as pkg_file

            pkg_dir = Path(pkg_file).parent
            agents_dir = pkg_dir / "agents" / "builtin"

        self.agents_dir = agents_dir
        self._cache: dict[str, AgentSpec] = {}

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
        else:
            # Look for markdown file
            agent_file = self.agents_dir / f"{name}.md"
            if not agent_file.exists():
                raise ValueError(f"Agent '{name}' not found in {self.agents_dir}")

            # Load and cache the spec
            spec = AgentSpec.from_markdown(agent_file)
            self._cache[name] = spec

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
                spec = AgentSpec.from_markdown(path)
                agents.append(spec.name)
            except Exception as e:
                logger.warning(f"Failed to load agent from {path}: {e}")

        return sorted(agents)
