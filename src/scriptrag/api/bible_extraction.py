"""Bible character extraction module using LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm import LLMClient
from scriptrag.parser.bible_parser import BibleParser

logger = get_logger(__name__)


@dataclass
class BibleCharacter:
    """Character entry from Bible extraction."""

    canonical: str
    aliases: list[str]
    tags: list[str] | None = None
    notes: str | None = None


class BibleCharacterExtractor:
    """Extracts character aliases from Bible files using LLM."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize Bible character extractor.

        Args:
            llm_client: LLM client for extraction
        """
        self.llm_client = llm_client or LLMClient()
        self.bible_parser = BibleParser()

    async def extract_characters_from_bible(self, bible_path: Path) -> dict[str, Any]:
        """Extract character names and aliases from a Bible file.

        Args:
            bible_path: Path to the Bible markdown file

        Returns:
            Dictionary with character extraction metadata
        """
        try:
            # Parse the Bible file
            parsed_bible = self.bible_parser.parse_file(bible_path)

            # Find character-related chunks
            character_chunks = self._find_character_chunks(parsed_bible)

            if not character_chunks:
                logger.info(f"No character sections found in {bible_path}")
                return self._create_empty_result()

            # Extract characters via LLM
            characters = await self._extract_via_llm(character_chunks)

            # Normalize and deduplicate
            normalized_characters = self._normalize_characters(characters)

            return {
                "version": 1,
                "extracted_at": datetime.now().isoformat(),
                "characters": [
                    {
                        "canonical": char.canonical,
                        "aliases": char.aliases,
                        "tags": char.tags,
                        "notes": char.notes,
                    }
                    for char in normalized_characters
                ],
            }

        except Exception as e:
            logger.error(f"Failed to extract characters from {bible_path}: {e}")
            return self._create_empty_result()

    def _find_character_chunks(self, parsed_bible: Any) -> list[str]:
        """Find chunks that likely contain character information.

        Args:
            parsed_bible: Parsed Bible data

        Returns:
            List of relevant chunk contents
        """
        character_chunks = []
        character_keywords = [
            "character",
            "protagonist",
            "antagonist",
            "cast",
            "role",
            "player",
            "person",
            "name",
        ]

        for chunk in parsed_bible.chunks:
            # Check if heading suggests character content
            heading_lower = (chunk.heading or "").lower()
            if any(keyword in heading_lower for keyword in character_keywords):
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
            if any(keyword in content_lower for keyword in character_keywords[:4]):
                # Include heading with content for context
                chunk_text = (
                    f"{chunk.heading}\n{chunk.content}"
                    if chunk.heading
                    else chunk.content
                )
                character_chunks.append(chunk_text)

        return character_chunks

    async def _extract_via_llm(self, chunks: list[str]) -> list[BibleCharacter]:
        """Extract characters from chunks using LLM.

        Args:
            chunks: List of text chunks containing character information

        Returns:
            List of extracted characters
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
            characters_data = self._extract_json(response_text)

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

    def _extract_json(self, response: str) -> list[dict[str, Any]]:
        """Extract JSON array from LLM response.

        Args:
            response: LLM response text

        Returns:
            Parsed JSON array
        """
        # Try parsing the whole response first to avoid false positives
        try:
            result = json.loads(response)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in response
        import re

        # Look for JSON array pattern at the start of a line or after whitespace
        json_match = re.search(r"(?:^|\s)(\[.*\])", response, re.DOTALL | re.MULTILINE)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON")
        return []

    def _normalize_characters(
        self, characters: list[BibleCharacter]
    ) -> list[BibleCharacter]:
        """Normalize and deduplicate characters.

        Args:
            characters: Raw extracted characters

        Returns:
            Normalized and deduplicated characters
        """
        seen_canonicals = set()
        normalized = []

        for char in characters:
            # Uppercase and strip
            char.canonical = char.canonical.upper().strip()

            # Skip if duplicate canonical
            if char.canonical in seen_canonicals:
                continue
            seen_canonicals.add(char.canonical)

            # Normalize aliases
            normalized_aliases = []
            seen_aliases = {char.canonical}  # Canonical is implicitly an alias

            # Get first name from canonical for comparison
            canonical_parts = char.canonical.split()
            first_name = canonical_parts[0] if canonical_parts else ""

            for alias in char.aliases:
                alias = alias.upper().strip()
                # Skip if:
                # - Empty or already seen
                # - Matches the full canonical name
                # - Is just the first name and canonical has multiple parts
                if not alias or alias in seen_aliases or alias == char.canonical:
                    continue

                # Skip first name only if canonical has multiple parts
                if alias == first_name and len(canonical_parts) > 1:
                    continue

                normalized_aliases.append(alias)
                seen_aliases.add(alias)

            char.aliases = normalized_aliases
            normalized.append(char)

        return normalized

    def _create_empty_result(self) -> dict[str, Any]:
        """Create an empty result structure.

        Returns:
            Empty character extraction result
        """
        return {
            "version": 1,
            "extracted_at": datetime.now().isoformat(),
            "characters": [],
        }
