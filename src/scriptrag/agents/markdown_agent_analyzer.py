"""Markdown-based agent analyzer implementation."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import jsonschema
from jsonschema import ValidationError

from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger
from scriptrag.utils import get_default_llm_client

if TYPE_CHECKING:
    from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


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
        self, scene: dict[str, Any], _context: dict[str, Any]
    ) -> dict[str, Any]:
        """Call the LLM with the analysis prompt.

        Args:
            scene: Scene data
            _context: Context data from query (currently unused)

        Returns:
            LLM response parsed as dictionary
        """
        # Build the prompt by processing the template
        prompt = self.spec.analysis_prompt

        # Format scene content
        scene_content = self._format_scene_content(scene)

        # Replace placeholder patterns
        # 1. Replace {{scene_content}} directly
        prompt = prompt.replace("{{scene_content}}", scene_content)

        # 2. Replace fountain code blocks containing {{scene_content}}
        fountain_pattern = r"```fountain\n\{\{scene_content\}\}\n```"
        if re.search(fountain_pattern, prompt):
            prompt = re.sub(
                fountain_pattern, f"```fountain\n{scene_content}\n```", prompt
            )

        # 3. Replace SQL block with context query results (empty for now)
        if self.spec.context_query and "```sql" in prompt:
            # Find and replace the SQL block with results
            sql_pattern = r"```sql\n.*?\n```"
            # For now, context query returns empty results
            context_results = (
                "-- Context query results (placeholder - not yet implemented)"
            )
            prompt = re.sub(
                sql_pattern, f"```\n{context_results}\n```", prompt, flags=re.DOTALL
            )

        # 4. Extract JSON schema block to use for structured output
        json_schema_match = re.search(r"```json\n(.*?)\n```", prompt, re.DOTALL)
        if json_schema_match:
            # Remove the JSON schema block from the prompt
            prompt = re.sub(r"```json\n.*?\n```", "", prompt, count=1, flags=re.DOTALL)

        try:
            if self.llm_client is None:
                raise RuntimeError("LLM client not initialized")

            # Call the LLM client - let it handle model selection
            # Pass model=None to let the client select the best available model
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                model=None,  # Let client auto-select
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
