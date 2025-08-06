"""Props Inventory Analyzer for ScriptRAG.

This analyzer identifies and categorizes all props mentioned or implied in
screenplay scenes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger
from scriptrag.utils import get_default_llm_client

if TYPE_CHECKING:
    from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


class PropsInventoryAnalyzer(BaseSceneAnalyzer):
    """Analyzer that extracts and categorizes props from screenplay scenes."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the props inventory analyzer.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        self.llm_client: LLMClient | None = None
        self._prompt_template = self._load_prompt_template()

    @property
    def name(self) -> str:
        """Return the analyzer name."""
        return "props_inventory"

    @property
    def version(self) -> str:
        """Return the analyzer version."""
        return "1.0.0"

    @property
    def requires_llm(self) -> bool:
        """Return whether this analyzer requires an LLM."""
        return True

    async def initialize(self) -> None:
        """Initialize the LLM client."""
        if self.llm_client is None:
            self.llm_client = await get_default_llm_client()
            logger.info("Initialized LLM client for props inventory analyzer")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.llm_client = None

    def _load_prompt_template(self) -> str:
        """Load the prompt template for props identification."""
        return """You are a professional script supervisor and prop master.
Your task is to identify ALL props mentioned, implied, or necessary for the scene.

### Scene Content
{scene_content}

### Instructions

1. **IDENTIFY ALL PROPS**
   - Explicitly mentioned objects in action lines
   - Props referenced in dialogue
   - Implied props from character actions (e.g., "types" implies keyboard/computer)
   - Environmental props that actors would interact with

2. **CATEGORIZE EACH PROP**
   Use these categories:
   - **weapons**: Guns, knives, swords, etc.
   - **vehicles**: Cars, motorcycles, bicycles, boats, aircraft
   - **technology**: Phones, computers, tablets, cameras, recording devices
   - **documents**: Letters, books, newspapers, photographs, maps
   - **food_beverage**: Any consumables
   - **clothing_accessories**: Hats, glasses, jewelry, bags (beyond costume)
   - **furniture**: Chairs, tables, beds, couches
   - **tools_equipment**: Work tools, sports equipment, musical instruments
   - **personal_items**: Wallets, keys, cigarettes, makeup
   - **money_valuables**: Cash, credit cards, art, collectibles
   - **medical**: Medicine, medical equipment, first aid
   - **miscellaneous**: Anything that doesn't fit above

3. **ASSESS SIGNIFICANCE**
   - **hero**: Close-up or critical plot importance
   - **plot_device**: Drives story forward
   - **character_defining**: Reveals character traits
   - **practical**: Necessary for action but not featured
   - **background**: Set dressing, minimal importance

4. **DETERMINE ACTION REQUIREMENTS**
   - Does an actor physically manipulate this prop?
   - Is it thrown, broken, or transformed?
   - Does it require special handling or effects?

5. **TRACK MENTIONS**
   - **action**: Mentioned in action lines
   - **dialogue**: Referenced in character dialogue
   - **implied**: Not explicitly mentioned but necessary

### Output Format

Return ONLY a valid JSON object with this structure:
{{
  "props": [
    {{
      "name": "prop name",
      "category": "category from list",
      "description": "brief description if provided",
      "significance": "hero|plot_device|character_defining|practical|background",
      "action_required": true/false,
      "quantity": 1,
      "mentions": ["action", "dialogue", or "implied"]
    }}
  ],
  "summary": {{
    "total_props": number,
    "hero_props": number,
    "requires_action": number,
    "categories": ["list", "of", "categories"]
  }}
}}

Be thorough but avoid duplicates. Return ONLY the JSON object, no other text."""

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene to extract props inventory.

        Args:
            scene: Scene data containing content, heading, dialogue, action, characters

        Returns:
            Dictionary containing identified props and metadata
        """
        if not self.llm_client:
            await self.initialize()

        # Build the scene content for analysis
        scene_content = self._build_scene_content(scene)

        # Create the prompt
        prompt = self._prompt_template.format(scene_content=scene_content)

        try:
            # Call the LLM
            if self.llm_client is None:
                raise RuntimeError("LLM client not initialized")
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temperature for more consistent extraction
                max_tokens=2000,
            )

            # Parse the JSON response
            result = self._parse_llm_response(response.content)

            # Add metadata
            result["analyzer"] = self.name
            result["version"] = self.version

            logger.info(
                "Props inventory analysis complete",
                scene_heading=scene.get("heading", ""),
                total_props=result.get("summary", {}).get("total_props", 0),
            )

            return result

        except Exception as e:
            logger.error(
                "Failed to analyze scene for props",
                error=str(e),
                scene_heading=scene.get("heading", ""),
            )
            # Return empty result on error
            return {
                "props": [],
                "summary": {
                    "total_props": 0,
                    "hero_props": 0,
                    "requires_action": 0,
                    "categories": [],
                },
                "analyzer": self.name,
                "version": self.version,
                "error": str(e),
            }

    def _build_scene_content(self, scene: dict[str, Any]) -> str:
        """Build a formatted scene content string for analysis.

        Args:
            scene: Scene data dictionary

        Returns:
            Formatted scene content string
        """
        parts = []

        # Add heading if present
        if heading := scene.get("heading"):
            parts.append(f"SCENE HEADING: {heading}")
            parts.append("")

        # Add action lines
        if action_lines := scene.get("action"):
            parts.append("ACTION:")
            for line in action_lines:
                if line.strip():
                    parts.append(line)
            parts.append("")

        # Add dialogue
        if dialogue := scene.get("dialogue"):
            parts.append("DIALOGUE:")
            for entry in dialogue:
                character = entry.get("character", "")
                text = entry.get("text", "")
                if character and text:
                    parts.append(f"{character}: {text}")
            parts.append("")

        # If we have raw content and no structured data, use it
        if not parts and (content := scene.get("content")):
            parts.append(content)

        return "\n".join(parts)

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse and validate the LLM response.

        Args:
            response: Raw LLM response string

        Returns:
            Parsed and validated props data

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValueError: If response doesn't match expected schema
        """
        # Try to extract JSON from the response
        response = response.strip()

        # If the response is wrapped in code blocks, extract it
        if response.startswith("```"):
            lines = response.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json"):
                    in_json = True
                elif line.startswith("```") and in_json:
                    break
                elif in_json and not line.startswith("```"):
                    json_lines.append(line)
            response = "\n".join(json_lines)

        # Parse the JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON", error=str(e))
            # Try to find JSON in the response
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise

        # Validate required fields
        if "props" not in data:
            data["props"] = []

        if "summary" not in data:
            # Calculate summary from props
            props = data["props"]
            categories = list({p.get("category") for p in props if p.get("category")})
            data["summary"] = {
                "total_props": len(props),
                "hero_props": sum(1 for p in props if p.get("significance") == "hero"),
                "requires_action": sum(
                    1 for p in props if p.get("action_required", False)
                ),
                "categories": categories,
            }

        # Ensure props have required fields
        for prop in data["props"]:
            if "name" not in prop:
                prop["name"] = "Unknown"
            if "category" not in prop:
                prop["category"] = "miscellaneous"
            if "significance" not in prop:
                prop["significance"] = "practical"
            if "action_required" not in prop:
                prop["action_required"] = False
            if "quantity" not in prop:
                prop["quantity"] = 1
            if "mentions" not in prop:
                prop["mentions"] = ["implied"]

        return dict(data)
