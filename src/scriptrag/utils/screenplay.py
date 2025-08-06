"""Screenplay-specific utility functions."""


class ScreenplayUtils:
    """Utility functions for screenplay processing."""

    @staticmethod
    def extract_location(heading: str) -> str | None:
        """Extract location from scene heading.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Extracted location or None
        """
        if not heading:
            return None

        # Remove scene type prefixes
        heading_upper = heading.upper()
        rest = heading

        if heading_upper.startswith("INT./EXT."):
            rest = heading[9:].strip()
        elif (
            heading_upper.startswith("INT.")
            or heading_upper.startswith("EXT.")
            or heading_upper.startswith("I/E.")
            or heading_upper.startswith("I/E ")
            or heading_upper.startswith("INT ")
            or heading_upper.startswith("EXT ")
        ):
            rest = heading[4:].strip()

        # Extract location (everything before " - " if present)
        if " - " in rest:
            location, _ = rest.rsplit(" - ", 1)
            location = location.strip()
            # If location is empty or just whitespace, return None
            return location if location else None

        # Handle case where rest starts with "- " (time only, no location)
        if rest.strip().startswith("- "):
            return None

        # If no " - " separator, the rest is the location
        rest = rest.strip()
        return rest if rest else None

    @staticmethod
    def extract_time(heading: str) -> str | None:
        """Extract time of day from scene heading.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Extracted time or None
        """
        if not heading:
            return None

        heading_upper = heading.upper()
        time_indicators = [
            "DAY",
            "NIGHT",
            "MORNING",
            "AFTERNOON",
            "EVENING",
            "DAWN",
            "DUSK",
            "CONTINUOUS",
            "LATER",
            "MOMENTS LATER",
            "SUNSET",
            "SUNRISE",
            "NOON",
            "MIDNIGHT",
        ]

        # Check if heading ends with time indicator
        for indicator in time_indicators:
            if heading_upper.endswith(indicator):
                return indicator
            if f"- {indicator}" in heading_upper:
                return indicator
            if f" {indicator}" in heading_upper.split(" - ")[-1]:
                return indicator

        return None

    @staticmethod
    def parse_scene_heading(heading: str) -> tuple[str, str | None, str | None]:
        """Parse a scene heading into its components.

        Args:
            heading: Scene heading text (e.g., "INT. COFFEE SHOP - DAY")

        Returns:
            Tuple of (scene_type, location, time_of_day)
        """
        if not heading:
            return "", None, None

        scene_type = ""
        heading_upper = heading.upper()

        # Determine scene type (check more specific patterns first)
        if heading_upper.startswith("INT./EXT.") or heading_upper.startswith("I/E"):
            scene_type = "INT/EXT"
        elif heading_upper.startswith("INT.") or heading_upper.startswith("INT "):
            scene_type = "INT"
        elif heading_upper.startswith("EXT.") or heading_upper.startswith("EXT "):
            scene_type = "EXT"

        location = ScreenplayUtils.extract_location(heading)
        time_of_day = ScreenplayUtils.extract_time(heading)

        return scene_type, location, time_of_day
