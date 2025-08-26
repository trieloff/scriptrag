"""Scene bible extraction module."""

from __future__ import annotations

from dataclasses import dataclass

from scriptrag.api.bible.utils import SCENE_KEYWORDS, LLMResponseParser
from scriptrag.config import get_logger
from scriptrag.llm import LLMClient
from scriptrag.parser.bible_parser import BibleParser, ParsedBible

logger = get_logger(__name__)


@dataclass
class BibleScene:
    """Represents a scene extracted from a script Bible.

    Contains information about a scene location including its type
    (interior/exterior), time of day, and description.

    Attributes:
        location: The location name as it would appear in slug lines
        type: Interior/Exterior designation (INT, EXT, INT/EXT, I/E)
        time: Time of day if specified (DAY, NIGHT, etc.)
        description: Description or notes about the location
    """

    location: str
    type: str | None = None
    time: str | None = None
    description: str | None = None


class SceneBibleExtractor:
    """Extracts scene-related information from script Bible files using LLM.

    This class handles the extraction of scene-specific information such as
    locations, settings, and scene descriptions from Bible markdown files.
    It uses LLM analysis to understand natural language descriptions and
    convert them to structured scene data suitable for database storage.

    The extractor works by:
    1. Parsing Bible markdown files to identify scene-related sections
    2. Using LLM prompts to extract structured scene information
    3. Normalizing and validating the extracted data
    4. Returning standardized metadata for database storage

    Example:
        >>> extractor = SceneBibleExtractor()
        >>> result = await extractor.extract_scenes_from_bible(
        ...     Path("my_script_bible.md")
        ... )
        >>> print(f"Found {len(result['scenes'])} scene descriptions")
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize Bible scene extractor.

        Args:
            llm_client: LLM client for extraction
        """
        self.llm_client = llm_client or LLMClient()
        self.bible_parser = BibleParser()

    def find_scene_chunks(self, parsed_bible: ParsedBible) -> list[str]:
        """Find Bible chunks likely to contain scene information.

        Uses keyword-based heuristics to identify sections that mention
        locations, settings, scenes, or environments. This pre-filtering
        reduces the content sent to the LLM for extraction.

        Args:
            parsed_bible: Parsed Bible data containing chunks with headings
                         and content from the BibleParser

        Returns:
            List of text strings containing scene-related content.
            Returns empty list if no scene-related chunks are found.
        """
        scene_chunks = []

        for chunk in parsed_bible.chunks:
            # Check if heading suggests scene content
            heading_lower = (chunk.heading or "").lower()
            if any(keyword in heading_lower for keyword in SCENE_KEYWORDS):
                # Include heading with content for context
                chunk_text = (
                    f"{chunk.heading}\n{chunk.content}"
                    if chunk.heading
                    else chunk.content
                )
                scene_chunks.append(chunk_text)
                continue

            # Check if content has scene mentions (quick heuristic)
            content_lower = chunk.content.lower()
            if any(keyword in content_lower for keyword in SCENE_KEYWORDS[:4]):
                # Include heading with content for context
                chunk_text = (
                    f"{chunk.heading}\n{chunk.content}"
                    if chunk.heading
                    else chunk.content
                )
                scene_chunks.append(chunk_text)

        return scene_chunks

    async def extract_scenes_via_llm(self, chunks: list[str]) -> list[BibleScene]:
        """Extract scene data from Bible content using LLM analysis.

        Sends prompts to the LLM to extract structured scene information
        from Bible content chunks.

        Args:
            chunks: List of text chunks from Bible sections that likely contain
                   scene information

        Returns:
            List of BibleScene objects. Returns empty list
            if extraction fails or no valid scenes are found.
        """
        if not chunks:
            return []

        # Combine chunks for context
        combined_text = "\n\n---\n\n".join(chunks)

        prompt = (
            "Extract all scene locations and settings from the following "
            "screenplay bible content.\n\n"
            "For each location/scene, identify:\n"
            "1. The location name (as it would appear in slug lines)\n"
            "2. Interior/Exterior designation if mentioned\n"
            "3. Time of day if specified\n"
            "4. Description or notes about the location\n\n"
            f"Content:\n{combined_text}\n\n"
            "Return a JSON array with this structure:\n"
            "[\n"
            "  {\n"
            '    "location": "POLICE STATION",\n'
            '    "type": "INT",\n'
            '    "time": "DAY",\n'
            '    "description": "Modern downtown precinct"\n'
            "  }\n"
            "]\n\n"
            "Only return the JSON array, no other text."
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.complete(messages)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            scenes_data = LLMResponseParser.extract_json_array(response_text)

            # Convert to BibleScene objects
            scenes = []
            for scene_dict in scenes_data:
                if not isinstance(scene_dict, dict):
                    continue

                location = scene_dict.get("location", "").upper().strip()
                if not location:
                    continue

                scene = BibleScene(
                    location=location,
                    type=scene_dict.get("type"),
                    time=scene_dict.get("time"),
                    description=scene_dict.get("description"),
                )
                scenes.append(scene)

            return scenes

        except Exception as e:
            logger.error(f"Scene LLM extraction failed: {e}")
            return []
