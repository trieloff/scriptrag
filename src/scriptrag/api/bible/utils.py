"""Shared utilities for bible extraction modules."""

from __future__ import annotations

import json
import re
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)

# Constants for keyword-based filtering
CHARACTER_KEYWORDS = [
    "character",
    "protagonist",
    "antagonist",
    "cast",
    "role",
    "player",
    "person",
    "name",
]

SCENE_KEYWORDS = [
    "scene",
    "location",
    "setting",
    "place",
    "environment",
    "interior",
    "exterior",
    "stage",
]

# Constants for scene validation
VALID_SCENE_TYPES = ["INT", "EXT", "INT/EXT", "I/E"]


class LLMResponseParser:
    """Utilities for parsing LLM responses containing JSON data."""

    @staticmethod
    def extract_json_array(response: str) -> list[dict[str, Any]]:
        r"""Extract JSON array from potentially messy LLM response text.

        LLM responses often contain extra text, formatting, or code blocks
        around the requested JSON. This method uses multiple parsing strategies
        to reliably extract the data array:

        1. First attempts to parse the entire response as JSON
        2. Falls back to regex extraction of JSON array patterns
        3. Validates that the result is actually an array

        Args:
            response: Raw text response from LLM completion, which may contain
                     JSON wrapped in code blocks, explanatory text, or other
                     formatting that needs to be stripped

        Returns:
            List of data dictionaries extracted from the response.
            Returns empty list if no valid JSON array is found.

        Example:
            >>> response = '```json\n[{"name": "JANE"}]\n```'
            >>> LLMResponseParser.extract_json_array(response)
            [{'name': 'JANE'}]

        Note:
            All parsing errors are caught and logged as warnings. The method
            never raises exceptions, instead returning an empty list to allow
            the extraction process to continue gracefully.
        """
        # Try parsing the whole response first to avoid false positives
        try:
            result = json.loads(response)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in response
        # Enhanced pattern to match complete JSON arrays while avoiding embedded arrays
        # Look for arrays that contain objects, not just simple values
        json_match = re.search(
            r"(\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\])",
            response,
            re.DOTALL,
        )
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON")
        return []
