"""Markdown-based agent analyzer implementation."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import jsonschema
from jsonschema import ValidationError

from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.agents.context_query import (
    ContextParameters,
    ContextQueryExecutor,
    ContextResultFormatter,
)
from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger
from scriptrag.utils import get_default_llm_client
from scriptrag.utils.screenplay import ScreenplayUtils

if TYPE_CHECKING:
    from scriptrag.llm.client import LLMClient
    from scriptrag.parser import Script

logger = get_logger(__name__)


class MarkdownAgentAnalyzer(BaseSceneAnalyzer):
    """Analyzer that wraps a markdown-based agent specification."""

    def __init__(
        self,
        spec: AgentSpec,
        config: dict[str, Any] | None = None,
        script: Script | None = None,
    ) -> None:
        """Initialize the markdown agent analyzer.

        Args:
            spec: Agent specification
            config: Optional configuration
            script: Optional Script object for context
        """
        super().__init__(config)
        self.spec = spec
        self.llm_client: LLMClient | None = None
        self.script = script
        self.context_executor = ContextQueryExecutor()

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

        # Execute context query if defined in agent spec
        context = await self._execute_context_query(scene)

        # If LLM is required, call it with retry logic
        if self.spec.requires_llm:
            max_attempts = 3
            temperature_increment = 0.2

            for attempt in range(max_attempts):
                # Calculate temperature for this attempt
                # Start at 0.3 (default), then 0.5, then 0.7
                temperature = 0.3 + (attempt * temperature_increment)

                result = await self._call_llm(scene, context, temperature=temperature)

                # Validate the result against the schema
                try:
                    jsonschema.validate(result, self.spec.output_schema)
                    # Validation passed, break out of retry loop
                    break
                except ValidationError as e:
                    logger.error(
                        f"Agent {self.spec.name} validation failed "
                        f"({attempt + 1}/{max_attempts})",
                        error=str(e),
                        scene_heading=scene.get("heading", ""),
                        temperature=temperature,
                    )

                    # If this was the last attempt, raise exception
                    if attempt == max_attempts - 1:
                        raise ValidationError(
                            f"Agent {self.spec.name} validation failed after "
                            f"{max_attempts} attempts: {e}"
                        ) from e
                    # Log that we're retrying
                    logger.info(
                        f"Retrying {self.spec.name} with higher temperature",
                        next_temperature=temperature + temperature_increment,
                        attempt=attempt + 2,
                    )
        else:
            # For non-LLM agents, just return empty result
            # No validation needed for non-LLM agents since they don't generate content
            result = {}

        # Add metadata
        result["analyzer"] = self.name
        result["version"] = self.version
        result["property"] = self.name  # Property is same as name

        return result

    async def _execute_context_query(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Execute the context query for the scene.

        Args:
            scene: Scene data

        Returns:
            Context data from the query
        """
        if not self.spec.context_query:
            logger.debug(f"No context query defined for agent {self.spec.name}")
            return {"scene_data": scene}

        try:
            # Extract parameters from scene and script
            from scriptrag.config import get_settings

            settings = get_settings()

            parameters = ContextParameters.from_scene(
                scene=scene,
                script=self.script,
                settings=settings,
            )

            logger.debug(
                f"Executing context query for agent {self.spec.name}",
                params=parameters.to_dict(),
            )

            # Execute the query
            results = await self.context_executor.execute(
                query_sql=self.spec.context_query,
                parameters=parameters,
            )

            # Format results for the agent
            formatted_results = ContextResultFormatter.format_for_agent(
                rows=results,
                _agent_name=self.spec.name,
            )

            return {
                "scene_data": scene,
                "context_results": results,
                "formatted_context": formatted_results,
            }

        except Exception as e:
            logger.error(
                f"Context query failed for agent {self.spec.name}",
                error=str(e),
                scene_heading=scene.get("heading", ""),
            )
            # Return basic context on failure (graceful degradation)
            return {"scene_data": scene}

    async def _call_llm(
        self, scene: dict[str, Any], context: dict[str, Any], temperature: float = 0.3
    ) -> dict[str, Any]:
        """Call the LLM with the analysis prompt.

        Args:
            scene: Scene data
            context: Context data from query
            temperature: Temperature for LLM sampling (default: 0.3)

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

        # 3. Replace SQL block with context query results
        if self.spec.context_query and "```sql" in prompt:
            # Find and replace the SQL block with results
            sql_pattern = r"```sql\n.*?\n```"

            # Use formatted context if available, otherwise show raw results
            if "formatted_context" in context:
                context_results = context["formatted_context"]
            elif "context_results" in context:
                # Format raw results as a simple list
                results = context["context_results"]
                if results:
                    msg = f"-- Context query returned {len(results)} results:\n"
                    context_results = msg
                    context_results += ContextResultFormatter.format_as_table(results)
                else:
                    context_results = "-- Context query returned no results"
            else:
                context_results = "-- No context results available"

            prompt = re.sub(
                sql_pattern, f"```\n{context_results}\n```", prompt, flags=re.DOTALL
            )

        # 4. Extract JSON schema block to use for structured output
        response_format = None
        json_schema_match = re.search(r"```json\n(.*?)\n```", prompt, re.DOTALL)
        if json_schema_match:
            # Remove the JSON schema block from the prompt
            prompt = re.sub(r"```json\n.*?\n```", "", prompt, count=1, flags=re.DOTALL)
            # Use the output schema from the agent spec for response format
            # Different OpenAI-compatible APIs have different requirements:
            # - OpenAI uses type: "json_object" without schema
            # - Some implementations use type: "json_schema" with schema
            # We'll try json_schema format which seems more standard
            if self.spec.output_schema:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self.spec.name,
                        "schema": self.spec.output_schema,
                        "strict": False,  # Allow additional properties
                    },
                }
                logger.debug(
                    f"Using structured output for {self.spec.name}",
                    schema_keys=list(
                        self.spec.output_schema.get("properties", {}).keys()
                    ),
                )

        try:
            if self.llm_client is None:
                raise RuntimeError("LLM client not initialized")

            # Log the LLM request details
            scene_heading = scene.get("heading", "unknown")
            logger.info(
                f"Making LLM request for agent {self.spec.name}",
                scene_heading=scene_heading,
                prompt_length=len(prompt),
                scene_content_length=len(scene_content),
                has_response_format=bool(response_format),
                temperature=temperature,
            )
            logger.debug(
                f"LLM prompt preview for {self.spec.name}",
                prompt_preview=prompt[:500] if len(prompt) > 500 else prompt,
            )

            # Build the completion request
            from typing import cast

            from scriptrag.llm.models import CompletionRequest, ResponseFormat

            request = CompletionRequest(
                model="",  # Let client auto-select
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=10000,
                response_format=cast(ResponseFormat, response_format)
                if response_format
                else None,
            )

            # Call the LLM client
            response = await self.llm_client.complete(request)

            # Log the response details
            logger.info(
                f"LLM response received for agent {self.spec.name}",
                scene_heading=scene_heading,
                response_length=len(response.content),
                model_used=response.model,
                provider=response.provider.value if response.provider else "unknown",
                usage=response.usage,
            )
            logger.debug(
                f"LLM response preview for {self.spec.name}",
                response_preview=response.content[:500]
                if len(response.content) > 500
                else response.content,
            )

            # Parse the response
            parsed_result = self._parse_llm_response(response.content)

            # Log parsing result
            if parsed_result:
                logger.info(
                    f"Successfully parsed LLM response for {self.spec.name}",
                    scene_heading=scene_heading,
                    result_keys=list(parsed_result.keys()),
                )
            else:
                logger.warning(
                    f"Failed to parse LLM response for {self.spec.name}",
                    scene_heading=scene_heading,
                )

            return parsed_result

        except Exception as e:
            logger.error(
                f"LLM call failed for agent {self.spec.name}",
                error=str(e),
                scene_heading=scene.get("heading", ""),
                error_type=type(e).__name__,
            )
            import traceback

            logger.debug(
                f"LLM call traceback for {self.spec.name}",
                traceback=traceback.format_exc(),
            )
            return {}

    def _format_scene_content(self, scene: dict[str, Any]) -> str:
        """Format scene content for the prompt.

        Args:
            scene: Scene data

        Returns:
            Formatted scene content
        """
        return ScreenplayUtils.format_scene_for_prompt(scene)

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
