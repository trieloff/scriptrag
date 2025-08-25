"""Character bible extraction module."""

from __future__ import annotations

from dataclasses import dataclass

from scriptrag.api.bible.utils import CHARACTER_KEYWORDS, LLMResponseParser
from scriptrag.config import get_logger
from scriptrag.llm import LLMClient
from scriptrag.parser.bible_parser import BibleParser, ParsedBible

logger = get_logger(__name__)


@dataclass
class BibleCharacter:
    """Represents a character extracted from a script Bible.

    Contains all information about a character including their canonical name,
    alternative names or titles they might be referred to by, optional
    categorization tags, and descriptive notes.

    This data structure is used to store LLM-extracted character information
    before it's converted to the final metadata format for database storage
    and use by the relationships analyzer.

    Attributes:
        canonical: The primary/official character name, typically as it would
                  appear in dialogue headers (e.g., "JANE SMITH", "DETECTIVE JONES")
        aliases: List of alternative names, nicknames, or titles this character
                might be referenced by (e.g., ["JANE", "MS. SMITH", "THE DETECTIVE"])
        tags: Optional list of character categories or roles
             (e.g., ["protagonist", "detective", "supporting"])
        notes: Optional free-form description or notes about the character
               from the Bible content

    Example:
        >>> character = BibleCharacter(
        ...     canonical="JANE SMITH",
        ...     aliases=["JANE", "DETECTIVE SMITH", "MS. SMITH"],
        ...     tags=["protagonist", "detective"],
        ...     notes="Lead investigator with 15 years experience"
        ... )
    """

    canonical: str
    aliases: list[str]
    tags: list[str] | None = None
    notes: str | None = None


class BibleCharacterExtractor:
    """Extracts character names and aliases from script Bible files using LLM.

    This class orchestrates the process of analyzing script Bible markdown files
    to identify character information and extract structured data about character
    names, aliases, and relationships. It uses LLM analysis to understand
    natural language descriptions and convert them to structured character data
    suitable for use in relationship analysis.

    The extractor works by:
    1. Parsing Bible markdown files to identify character-related sections
    2. Using LLM prompts to extract structured character information
    3. Normalizing and validating the extracted data
    4. Returning standardized metadata for database storage

    Example:
        >>> extractor = BibleCharacterExtractor()
        >>> result = await extractor.extract_characters_from_bible(
        ...     Path("my_script_bible.md")
        ... )
        >>> print(f"Found {len(result['characters'])} characters")
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize Bible character extractor.

        Args:
            llm_client: LLM client for extraction
        """
        self.llm_client = llm_client or LLMClient()
        self.bible_parser = BibleParser()

    def find_character_chunks(self, parsed_bible: ParsedBible) -> list[str]:
        r"""Find Bible chunks likely to contain character information.

        Uses keyword-based heuristics to identify sections that mention
        characters, protagonists, cast members, or character roles. This
        pre-filtering reduces the content sent to the LLM for extraction,
        improving both accuracy and cost-effectiveness.

        The method checks both section headings and content for character-related
        keywords, combining headings with content to provide context for the
        LLM extraction process.

        Args:
            parsed_bible: Parsed Bible data containing chunks with headings
                         and content from the BibleParser

        Returns:
            List of text strings, each containing a heading (if present)
            followed by chunk content that likely describes characters.
            Returns empty list if no character-related chunks are found.

        Example:
            For a Bible chunk with heading "Main Characters" and content
            describing "Jane Smith is the detective...", this would return
            a list containing "Main Characters\n\nJane Smith is the detective..."
        """
        character_chunks = []

        for chunk in parsed_bible.chunks:
            # Check if heading suggests character content
            heading_lower = (chunk.heading or "").lower()
            if any(keyword in heading_lower for keyword in CHARACTER_KEYWORDS):
                # Include heading with content for context
                chunk_text = (
                    f"{chunk.heading}\n{chunk.content}"
                    if chunk.heading
                    else chunk.content
                )
                character_chunks.append(chunk_text)
                continue

            # Check if content has character mentions (quick heuristic)
            content_lower = chunk.content.lower()
            if any(keyword in content_lower for keyword in CHARACTER_KEYWORDS[:4]):
                # Include heading with content for context
                chunk_text = (
                    f"{chunk.heading}\n{chunk.content}"
                    if chunk.heading
                    else chunk.content
                )
                character_chunks.append(chunk_text)

        return character_chunks

    async def extract_via_llm(self, chunks: list[str]) -> list[BibleCharacter]:
        r"""Extract character data from Bible content using LLM analysis.

        Sends carefully crafted prompts to the LLM to extract structured
        character information from Bible content chunks. The prompt includes
        specific formatting rules and examples to ensure consistent output.

        The extraction process:
        1. Combines chunks with separators for context
        2. Sends detailed prompt with extraction rules and JSON schema
        3. Parses LLM response to extract JSON character data
        4. Converts to BibleCharacter objects with validation

        Args:
            chunks: List of text chunks from Bible sections that likely contain
                   character information, typically including section headings
                   and descriptions

        Returns:
            List of BibleCharacter objects with canonical names, aliases,
            tags, and notes as extracted by the LLM. Returns empty list
            if extraction fails or no valid characters are found.

        Example:
            Input chunks: ["## Characters\n\nJane Smith is the detective..."]
            Output: [BibleCharacter(canonical="JANE SMITH",
                                   aliases=["JANE", "DETECTIVE SMITH"],
                                   tags=["protagonist", "detective"])]

        Note:
            All LLM communication errors are caught and logged. The method
            gracefully handles API failures, invalid responses, and parsing
            errors by returning an empty list rather than raising exceptions.
        """
        # Combine chunks for context
        combined_text = "\n\n---\n\n".join(chunks)

        prompt = (
            "Extract all character names and their aliases from the following "
            "screenplay bible content.\n\n"
            "For each character, identify:\n"
            "1. The canonical/primary name (uppercase, as it would appear in "
            "dialogue headers)\n"
            "2. All aliases, nicknames, or alternative references (also uppercase)\n"
            "3. Any tags or categories (e.g., 'protagonist', 'villain', 'supporting')\n"
            "4. Brief notes if provided\n\n"
            "Rules:\n"
            "- All names and aliases must be UPPERCASE\n"
            "- Exclude generic nouns like 'MAN', 'WOMAN', 'COP' unless they are "
            "specific characters\n"
            "- Include parenthetical disambiguations if needed "
            "(e.g., 'JOHN (YOUNG)', 'JOHN (OLD)')\n"
            "- For characters with titles, include both full and shortened versions "
            "(e.g., 'DETECTIVE SMITH' and 'SMITH')\n\n"
            f"Content:\n{combined_text}\n\n"
            "Return a JSON array with this structure:\n"
            "[\n"
            "  {\n"
            '    "canonical": "JANE SMITH",\n'
            '    "aliases": ["JANE", "MS. SMITH", "DETECTIVE SMITH"],\n'
            '    "tags": ["protagonist", "detective"],\n'
            '    "notes": "Lead detective investigating the case"\n'
            "  }\n"
            "]\n\n"
            "Only return the JSON array, no other text."
        )

        try:
            # Format prompt as messages for LLM client
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.complete(messages)
            # Extract JSON from response text
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            characters_data = LLMResponseParser.extract_json_array(response_text)

            # Convert to BibleCharacter objects
            characters = []
            for char_dict in characters_data:
                if not isinstance(char_dict, dict):
                    continue

                canonical = char_dict.get("canonical", "").upper()
                if not canonical:
                    continue

                aliases = [
                    alias.upper()
                    for alias in char_dict.get("aliases", [])
                    if isinstance(alias, str)
                ]

                character = BibleCharacter(
                    canonical=canonical,
                    aliases=aliases,
                    tags=char_dict.get("tags"),
                    notes=char_dict.get("notes"),
                )
                characters.append(character)

            return characters

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []
