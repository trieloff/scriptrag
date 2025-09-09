"""Bible extraction orchestration module.

This module provides the main entry point for bible extraction functionality,
coordinating between character extraction, scene extraction, formatting,
and validation submodules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scriptrag.api.bible.character_bible import (
    BibleCharacter,
)
from scriptrag.api.bible.character_bible import (
    BibleCharacterExtractor as CharacterExtractor,
)
from scriptrag.api.bible.formatters import BibleFormatter
from scriptrag.api.bible.scene_bible import SceneBibleExtractor
from scriptrag.api.bible.validators import BibleValidator
from scriptrag.config import get_logger
from scriptrag.llm import LLMClient
from scriptrag.parser.bible_parser import BibleParser

logger = get_logger(__name__)


class BibleExtractor:
    """Orchestrates bible extraction from screenplay files.

    This class coordinates the extraction of character and scene information
    from Bible markdown files, using specialized extractors for each type
    of data and providing unified formatting and validation.

    The extractor combines:
    - Character extraction for names, aliases, and roles
    - Scene extraction for locations and settings
    - Output formatting for consistent results
    - Data validation and normalization

    Example:
        >>> extractor = BibleExtractor()
        >>> result = await extractor.extract_from_bible(Path("bible.md"))
        >>> print(f"Found {len(result['characters'])} characters")
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize Bible extractor.

        Args:
            llm_client: LLM client for extraction, shared across submodules
        """
        self.llm_client = llm_client or LLMClient()
        self.character_extractor = CharacterExtractor(self.llm_client)
        self.scene_extractor = SceneBibleExtractor(self.llm_client)
        self.bible_parser = BibleParser()
        self.formatter = BibleFormatter()
        self.validator = BibleValidator()

    async def extract_characters_from_bible(self, bible_path: Path) -> dict[str, Any]:
        """Extract character names and aliases from a script Bible file.

        This is the main entry point for Bible character extraction. The method
        orchestrates the complete extraction pipeline: parsing the Bible file,
        identifying character-related content, using LLM to extract structured
        data, and normalizing the results for consistency.

        The extraction pipeline:
        1. Parse Bible markdown file using BibleParser
        2. Find chunks likely to contain character information
        3. Extract characters via LLM with structured prompts
        4. Normalize and deduplicate character data
        5. Return standardized metadata structure

        Args:
            bible_path: Path to the Bible markdown file containing character
                       descriptions, world-building notes, or other screenplay
                       reference material

        Returns:
            Dictionary containing extraction metadata with standardized structure:
            {
                "version": 1,
                "extracted_at": "2024-01-15T10:30:00.123456",
                "characters": [
                    {
                        "canonical": "JANE SMITH",
                        "aliases": ["JANE", "DETECTIVE SMITH"],
                        "tags": ["protagonist"],
                        "notes": "Lead detective..."
                    }
                ]
            }

        Example:
            >>> extractor = BibleExtractor()
            >>> result = await extractor.extract_characters_from_bible(
            ...     Path("script_bible.md")
            ... )
            >>> len(result["characters"])
            5

        Note:
            All errors during the extraction process are caught and logged.
            If any step fails, an empty result with the same schema is returned
            to ensure consistent behavior for downstream processing.
        """
        try:
            # Parse the Bible file
            parsed_bible = self.bible_parser.parse_file(bible_path)

            # Find character-related chunks
            character_chunks = self.character_extractor.find_character_chunks(
                parsed_bible
            )

            if not character_chunks:
                logger.info(f"No character sections found in {bible_path}")
                return self.formatter.create_empty_result("characters")

            # Extract characters via LLM
            characters = await self.character_extractor.extract_via_llm(
                character_chunks
            )

            # Normalize and deduplicate
            normalized_characters = self.validator.normalize_characters(characters)

            # Format and return result
            return self.formatter.format_character_result(normalized_characters)

        except Exception as e:
            logger.error(f"Failed to extract characters from {bible_path}: {e}")
            return self.formatter.create_empty_result("characters")

    def _find_character_chunks(self, parsed_bible: Any) -> list[str]:
        """Find Bible chunks likely to contain character information.

        Legacy method for backward compatibility with tests.
        Delegates to the character extractor.
        """
        return self.character_extractor.find_character_chunks(parsed_bible)

    async def _extract_via_llm(self, chunks: list[str]) -> list[BibleCharacter]:
        """Extract character data from Bible content using LLM analysis.

        Legacy method for backward compatibility with tests.
        Delegates to the character extractor.
        """
        return await self.character_extractor.extract_via_llm(chunks)

    def _extract_json(self, response: str) -> list[dict[str, Any]]:
        """Extract JSON array from potentially messy LLM response text.

        Legacy method for backward compatibility with tests.
        Delegates to the shared utility.
        """
        from scriptrag.api.bible.utils import LLMResponseParser

        return LLMResponseParser.extract_json_array(response)

    def _normalize_characters(
        self, characters: list[BibleCharacter]
    ) -> list[BibleCharacter]:
        """Normalize and deduplicate extracted character data.

        Legacy method for backward compatibility with tests.
        Delegates to the validator.
        """
        return self.validator.normalize_characters(characters)

    def _create_empty_result(self) -> dict[str, Any]:
        """Create standardized empty result for failed extractions.

        Legacy method for backward compatibility with tests.
        """
        return self.formatter.create_empty_result("characters")

    async def extract_scenes_from_bible(self, bible_path: Path) -> dict[str, Any]:
        """Extract scene information from a script Bible file.

        Extracts location and setting information from Bible markdown files.

        Args:
            bible_path: Path to the Bible markdown file

        Returns:
            Dictionary containing scene extraction results
        """
        try:
            # Parse the Bible file
            parsed_bible = self.bible_parser.parse_file(bible_path)

            # Find scene-related chunks
            scene_chunks = self.scene_extractor.find_scene_chunks(parsed_bible)

            if not scene_chunks:
                logger.info(f"No scene sections found in {bible_path}")
                return self.formatter.create_empty_result("scenes")

            # Extract scenes via LLM (returns BibleScene objects)
            scenes = await self.scene_extractor.extract_scenes_via_llm(scene_chunks)

            # Filter valid scenes (now working with BibleScene objects)
            valid_scenes = [
                scene for scene in scenes if self.validator.validate_bible_scene(scene)
            ]

            # Format and return result
            return self.formatter.format_scene_result(valid_scenes)

        except Exception as e:
            logger.error(f"Failed to extract scenes from {bible_path}: {e}")
            return self.formatter.create_empty_result("scenes")

    async def extract_from_bible(
        self, bible_path: Path, extract_scenes: bool = False
    ) -> dict[str, Any]:
        """Extract all information from a script Bible file.

        Combines character and optionally scene extraction into a single result.

        Args:
            bible_path: Path to the Bible markdown file
            extract_scenes: Whether to also extract scene information

        Returns:
            Combined dictionary with character and scene data
        """
        # Always extract characters
        character_result = await self.extract_characters_from_bible(bible_path)

        # Optionally extract scenes
        scene_result = None
        if extract_scenes:
            scene_result = await self.extract_scenes_from_bible(bible_path)

        # Merge results
        return self.formatter.merge_results(character_result, scene_result)
