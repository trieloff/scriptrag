"""Built-in scene analyzers for ScriptRAG."""

import re
from typing import Any

from .base import BaseSceneAnalyzer


class EmotionalToneAnalyzer(BaseSceneAnalyzer):
    """Analyze emotional tone of scenes.

    This is a simple rule-based analyzer that doesn't require LLM.
    For more sophisticated analysis, this could be enhanced with LLM support.
    """

    name = "emotional_tone"

    # Emotion keywords for basic detection
    EMOTION_PATTERNS = {
        "anger": re.compile(
            r"\b(angry|furious|rage|yell|scream|shout|slam|pound)\b", re.IGNORECASE
        ),
        "joy": re.compile(
            r"\b(happy|joy|laugh|smile|celebrate|excited|cheer)\b", re.IGNORECASE
        ),
        "sadness": re.compile(
            r"\b(sad|cry|tears|weep|mourn|depressed|sorrow)\b", re.IGNORECASE
        ),
        "fear": re.compile(
            r"\b(afraid|scared|terrified|panic|nervous|anxious|fear)\b", re.IGNORECASE
        ),
        "tension": re.compile(
            r"\b(tense|awkward|uncomfortable|silence|pause|hesitate)\b", re.IGNORECASE
        ),
    }

    async def analyze(self, scene: dict) -> dict:
        """Detect emotional tone using simple pattern matching.

        Args:
            scene: Scene data including content and dialogue

        Returns:
            Dictionary with emotional analysis
        """
        content = scene.get("content", "")
        dialogue_text = " ".join(
            d.get("text", "") for d in scene.get("dialogue", [])
        )
        full_text = f"{content} {dialogue_text}"

        # Count emotion indicators
        emotion_scores = {}
        for emotion, pattern in self.EMOTION_PATTERNS.items():
            matches = pattern.findall(full_text)
            if matches:
                emotion_scores[emotion] = len(matches)

        # Determine primary emotion
        primary_emotion = "neutral"
        if emotion_scores:
            primary_emotion = max(emotion_scores, key=emotion_scores.get)

        # Calculate intensity (0-1)
        total_words = len(full_text.split())
        total_emotion_words = sum(emotion_scores.values())
        intensity = min(1.0, total_emotion_words / max(1, total_words) * 10)

        return {
            "primary_emotion": primary_emotion,
            "emotion_scores": emotion_scores,
            "intensity": round(intensity, 2),
        }


class ThemeAnalyzer(BaseSceneAnalyzer):
    """Analyze thematic elements in scenes."""

    name = "themes"

    # Theme keywords for detection
    THEME_PATTERNS = {
        "love": re.compile(r"\b(love|romance|kiss|heart|together)\b", re.IGNORECASE),
        "conflict": re.compile(
            r"\b(fight|argue|conflict|disagree|oppose)\b", re.IGNORECASE
        ),
        "discovery": re.compile(
            r"\b(find|discover|realize|understand|reveal)\b", re.IGNORECASE
        ),
        "loss": re.compile(r"\b(lose|lost|gone|miss|goodbye)\b", re.IGNORECASE),
        "friendship": re.compile(
            r"\b(friend|buddy|pal|companion|together)\b", re.IGNORECASE
        ),
        "betrayal": re.compile(
            r"\b(betray|lie|deceive|cheat|backstab)\b", re.IGNORECASE
        ),
        "redemption": re.compile(
            r"\b(forgive|redeem|sorry|apologize|amend)\b", re.IGNORECASE
        ),
    }

    async def analyze(self, scene: dict) -> dict:
        """Detect thematic elements.

        Args:
            scene: Scene data

        Returns:
            Dictionary with detected themes
        """
        content = scene.get("content", "")
        dialogue_text = " ".join(
            d.get("text", "") for d in scene.get("dialogue", [])
        )
        full_text = f"{content} {dialogue_text}"

        detected_themes = []
        theme_scores = {}

        for theme, pattern in self.THEME_PATTERNS.items():
            matches = pattern.findall(full_text)
            if matches:
                detected_themes.append(theme)
                theme_scores[theme] = len(matches)

        return {
            "detected_themes": detected_themes,
            "theme_scores": theme_scores,
            "primary_theme": (
                max(theme_scores, key=theme_scores.get) if theme_scores else None
            ),
        }


class CharacterAnalyzer(BaseSceneAnalyzer):
    """Analyze character interactions and presence."""

    name = "character_analysis"

    async def analyze(self, scene: dict) -> dict:
        """Analyze character interactions.

        Args:
            scene: Scene data

        Returns:
            Dictionary with character analysis
        """
        characters = scene.get("characters", [])
        dialogue = scene.get("dialogue", [])

        # Count dialogue per character
        dialogue_counts = {}
        for d in dialogue:
            char = d.get("character", "").upper()
            if char:
                dialogue_counts[char] = dialogue_counts.get(char, 0) + 1

        # Detect interactions (simplified - who talks after whom)
        interactions = []
        for i in range(1, len(dialogue)):
            char1 = dialogue[i - 1].get("character", "").upper()
            char2 = dialogue[i].get("character", "").upper()
            if char1 and char2 and char1 != char2:
                interaction = tuple(sorted([char1, char2]))
                if interaction not in interactions:
                    interactions.append(interaction)

        return {
            "character_count": len(characters),
            "dialogue_distribution": dialogue_counts,
            "speaking_characters": list(dialogue_counts.keys()),
            "interactions": [list(i) for i in interactions],  # Convert tuples to lists for JSON
            "dominant_character": (
                max(dialogue_counts, key=dialogue_counts.get)
                if dialogue_counts
                else None
            ),
        }


# Registry of built-in analyzers
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {
    "emotional_tone": EmotionalToneAnalyzer,
    "themes": ThemeAnalyzer,
    "character_analysis": CharacterAnalyzer,
}