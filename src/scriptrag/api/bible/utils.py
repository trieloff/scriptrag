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
        # Use a more robust approach: find all potential JSON arrays and try to
        # parse them. This handles nested structures better than the previous regex
        # approach

        # Performance safeguards for pathological inputs
        max_nesting_depth = 100
        max_search_distance = 50000
        max_parse_attempts = 20

        # Find all bracket pairs that could be JSON arrays
        potential_arrays = []
        parse_attempts = 0

        # Look for array start positions
        start_positions = [m.start() for m in re.finditer(r"\[", response)]

        for start in start_positions:
            # Early termination if too many failed parse attempts
            if parse_attempts >= max_parse_attempts:
                logger.warning(
                    f"Reached max parse attempts ({max_parse_attempts}) "
                    "during JSON extraction"
                )
                break
            parse_attempts += 1

            # Find the matching closing bracket by counting nesting levels
            bracket_count = 0
            in_string = False
            escape_next = False

            for i, char in enumerate(response[start:], start):
                # Check performance limits
                if bracket_count > max_nesting_depth:
                    logger.warning(
                        f"Max nesting depth ({max_nesting_depth}) exceeded "
                        f"at position {i}"
                    )
                    break

                if i - start > max_search_distance:
                    logger.warning(
                        f"Max search distance ({max_search_distance}) exceeded "
                        f"from start position {start}"
                    )
                    break

                if escape_next:
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found matching closing bracket
                            potential_json = response[start : i + 1]
                            # Only consider arrays that contain objects
                            if "{" in potential_json:
                                potential_arrays.append(potential_json)
                            break

        # Try to parse each potential array, return the first valid one
        for potential_json in potential_arrays:
            try:
                result = json.loads(potential_json)
                if (
                    isinstance(result, list)
                    and len(result) > 0
                    and isinstance(result[0], dict)
                ):
                    return result
            except json.JSONDecodeError:
                continue

        logger.warning("Could not parse LLM response as JSON")
        return []
