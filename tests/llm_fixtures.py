"""Common LLM response fixtures for testing.

This module provides pre-defined LLM responses for various screenplay analysis
scenarios to ensure consistent and fast testing without actual LLM calls.
"""

import json
from typing import Any

# Scene analysis responses
SCENE_ANALYSIS_RESPONSES = {
    "coffee_shop": {
        "location": "INT. COFFEE SHOP",
        "time_of_day": "MORNING",
        "characters_present": ["SARAH", "JAMES"],
        "props": ["laptop", "coffee", "table", "windows"],
        "mood": "energetic, hopeful",
        "key_actions": [
            "Sarah works on screenplay",
            "James offers coffee refill",
            "Morning routine interaction",
        ],
        "themes": ["creativity", "dedication", "support"],
        "emotional_beats": [
            {"beat": "focus", "character": "SARAH", "intensity": 0.8},
            {"beat": "gratitude", "character": "SARAH", "intensity": 0.6},
            {"beat": "helpful", "character": "JAMES", "intensity": 0.7},
        ],
    },
    "city_street": {
        "location": "EXT. CITY STREET",
        "time_of_day": "MORNING",
        "characters_present": ["SARAH"],
        "props": ["phone", "coffee"],
        "mood": "busy, determined",
        "key_actions": [
            "Sarah exits coffee shop",
            "Walking briskly",
            "Phone conversation",
        ],
        "themes": ["commitment", "deadline pressure"],
        "emotional_beats": [
            {"beat": "urgency", "character": "SARAH", "intensity": 0.7},
            {"beat": "professional", "character": "SARAH", "intensity": 0.8},
        ],
    },
    "apartment": {
        "location": "INT. SARAH'S APARTMENT",
        "time_of_day": "LATER",
        "characters_present": ["SARAH", "WHISKERS"],
        "props": ["desk", "books", "scripts", "computer"],
        "mood": "focused, satisfied",
        "key_actions": [
            "Typing furiously",
            "Cat interruption",
            "Completing screenplay",
        ],
        "themes": ["achievement", "persistence", "creative fulfillment"],
        "emotional_beats": [
            {"beat": "concentration", "character": "SARAH", "intensity": 0.9},
            {"beat": "satisfaction", "character": "SARAH", "intensity": 0.9},
            {"beat": "playful", "character": "WHISKERS", "intensity": 0.5},
        ],
    },
}

# Character analysis responses
CHARACTER_ANALYSIS_RESPONSES = {
    "SARAH": {
        "name": "SARAH",
        "age": "30s",
        "occupation": "Screenwriter",
        "personality_traits": [
            "creative",
            "dedicated",
            "focused",
            "grateful",
            "professional",
        ],
        "character_arc": "Working to complete screenplay against deadline",
        "relationships": {
            "JAMES": "friendly acquaintance, coffee shop regular",
            "WHISKERS": "pet owner, affectionate",
        },
        "key_dialogue_traits": [
            "self-talk when focused",
            "polite and grateful",
            "professional on phone",
        ],
        "motivation": "Complete screenplay on time",
        "obstacles": ["time pressure", "distractions"],
        "growth": "Achieves goal through persistence",
    },
    "JAMES": {
        "name": "JAMES",
        "age": "40s",
        "occupation": "Barista",
        "personality_traits": ["observant", "helpful", "friendly", "supportive"],
        "character_arc": "Supporting character providing assistance",
        "relationships": {"SARAH": "regular customer, friendly service"},
        "key_dialogue_traits": ["casual", "service-oriented", "considerate"],
        "motivation": "Provide good service",
        "obstacles": [],
        "growth": "Maintains consistent support role",
    },
}

# Dialogue analysis responses
DIALOGUE_ANALYSIS_RESPONSES = {
    "sarah_focused": {
        "character": "SARAH",
        "line": "Just one more scene and I'm done.",
        "analysis": {
            "emotion": "determined",
            "subtext": "pushing through final effort",
            "tone": "self-motivating",
            "reveals": "near completion of project",
        },
    },
    "james_helpful": {
        "character": "JAMES",
        "line": "Another refill?",
        "analysis": {
            "emotion": "considerate",
            "subtext": "noticing regular customer's needs",
            "tone": "friendly service",
            "reveals": "attentive to customers",
        },
    },
    "sarah_grateful": {
        "character": "SARAH",
        "line": "You're a lifesaver.",
        "analysis": {
            "emotion": "grateful",
            "subtext": "appreciates support during crunch time",
            "tone": "sincere appreciation",
            "reveals": "values help from others",
        },
    },
}

# Theme analysis responses
THEME_ANALYSIS_RESPONSES = {
    "overall_themes": [
        {
            "theme": "Creative Process",
            "description": "The journey of completing creative work",
            "scenes_referenced": ["coffee_shop", "apartment"],
            "strength": 0.9,
        },
        {
            "theme": "Support Systems",
            "description": "How others help us achieve our goals",
            "scenes_referenced": ["coffee_shop"],
            "strength": 0.7,
        },
        {
            "theme": "Dedication",
            "description": "Persistence in face of deadlines",
            "scenes_referenced": ["coffee_shop", "city_street", "apartment"],
            "strength": 0.85,
        },
        {
            "theme": "Work-Life Balance",
            "description": "Managing professional and personal elements",
            "scenes_referenced": ["apartment"],
            "strength": 0.6,
        },
    ]
}

# Embedding vectors (mock)
EMBEDDING_VECTORS = {
    "scene_coffee_shop": [0.12, 0.34, 0.56, 0.78, 0.90, 0.23, 0.45, 0.67],
    "scene_city_street": [0.23, 0.45, 0.67, 0.89, 0.01, 0.34, 0.56, 0.78],
    "scene_apartment": [0.34, 0.56, 0.78, 0.90, 0.12, 0.45, 0.67, 0.89],
    "character_sarah": [0.45, 0.67, 0.89, 0.01, 0.23, 0.56, 0.78, 0.90],
    "character_james": [0.56, 0.78, 0.90, 0.12, 0.34, 0.67, 0.89, 0.01],
    "theme_creativity": [0.67, 0.89, 0.01, 0.23, 0.45, 0.78, 0.90, 0.12],
    "theme_dedication": [0.78, 0.90, 0.12, 0.34, 0.56, 0.89, 0.01, 0.23],
}

# Agent analysis responses (for markdown agents)
AGENT_ANALYSIS_RESPONSES = {
    "scene_analyzer": {
        "agent": "scene_analyzer",
        "version": "1.0.0",
        "analysis": {
            "total_scenes": 3,
            "interior_scenes": 2,
            "exterior_scenes": 1,
            "day_scenes": 3,
            "night_scenes": 0,
            "location_changes": 2,
            "average_scene_length": 150,
        },
    },
    "character_tracker": {
        "agent": "character_tracker",
        "version": "1.0.0",
        "analysis": {
            "total_characters": 3,
            "speaking_characters": 2,
            "non_speaking_characters": 1,
            "protagonist": "SARAH",
            "character_interactions": [["SARAH", "JAMES"], ["SARAH", "WHISKERS"]],
        },
    },
    "dialogue_analyzer": {
        "agent": "dialogue_analyzer",
        "version": "1.0.0",
        "analysis": {
            "total_dialogue_lines": 6,
            "characters_with_dialogue": ["SARAH", "JAMES"],
            "average_line_length": 8,
            "dialogue_to_action_ratio": 0.4,
        },
    },
}

# Error responses for testing error handling
ERROR_RESPONSES = {
    "rate_limit": {
        "error": "rate_limit_exceeded",
        "message": "Rate limit exceeded. Please wait 60 seconds before retrying.",
        "retry_after": 60,
    },
    "token_limit": {
        "error": "context_length_exceeded",
        "message": "The input exceeds the maximum context length of 4096 tokens.",
        "max_tokens": 4096,
        "input_tokens": 5000,
    },
    "invalid_json": {
        "error": "invalid_response",
        "message": "Failed to parse LLM response as JSON",
        "raw_response": "This is not valid JSON { unclosed",
    },
    "timeout": {
        "error": "request_timeout",
        "message": "Request timed out after 30 seconds",
        "timeout": 30,
    },
}


def get_scene_analysis_response(scene_type: str = "coffee_shop") -> dict[str, Any]:
    """Get a mock scene analysis response.

    Args:
        scene_type: Type of scene (coffee_shop, city_street, apartment)

    Returns:
        Mock scene analysis response
    """
    return SCENE_ANALYSIS_RESPONSES.get(
        scene_type, SCENE_ANALYSIS_RESPONSES["coffee_shop"]
    )


def get_character_analysis_response(character: str = "SARAH") -> dict[str, Any]:
    """Get a mock character analysis response.

    Args:
        character: Character name (SARAH, JAMES)

    Returns:
        Mock character analysis response
    """
    return CHARACTER_ANALYSIS_RESPONSES.get(
        character, CHARACTER_ANALYSIS_RESPONSES["SARAH"]
    )


def get_dialogue_analysis_response(
    dialogue_key: str = "sarah_focused",
) -> dict[str, Any]:
    """Get a mock dialogue analysis response.

    Args:
        dialogue_key: Dialogue identifier

    Returns:
        Mock dialogue analysis response
    """
    return DIALOGUE_ANALYSIS_RESPONSES.get(
        dialogue_key, DIALOGUE_ANALYSIS_RESPONSES["sarah_focused"]
    )


def get_embedding_vector(content_type: str = "scene_coffee_shop") -> list[float]:
    """Get a mock embedding vector.

    Args:
        content_type: Type of content to embed

    Returns:
        Mock embedding vector
    """
    return EMBEDDING_VECTORS.get(content_type, EMBEDDING_VECTORS["scene_coffee_shop"])


def create_llm_completion_response(
    analysis_type: str = "scene", content_key: str = "coffee_shop", as_json: bool = True
) -> str:
    """Create a mock LLM completion response.

    Args:
        analysis_type: Type of analysis (scene, character, dialogue, theme)
        content_key: Specific content identifier
        as_json: Whether to return as JSON string

    Returns:
        Mock LLM completion response
    """
    response_map = {
        "scene": SCENE_ANALYSIS_RESPONSES,
        "character": CHARACTER_ANALYSIS_RESPONSES,
        "dialogue": DIALOGUE_ANALYSIS_RESPONSES,
        "theme": {"analysis": THEME_ANALYSIS_RESPONSES},
        "agent": AGENT_ANALYSIS_RESPONSES,
    }

    response_data = response_map.get(analysis_type, {})
    if analysis_type in ["scene", "character", "agent"]:
        response_data = response_data.get(content_key, {})

    if as_json:
        return json.dumps(response_data, indent=2)
    return str(response_data)


def create_error_response(error_type: str = "rate_limit") -> dict[str, Any]:
    """Create a mock error response.

    Args:
        error_type: Type of error (rate_limit, token_limit, invalid_json, timeout)

    Returns:
        Mock error response
    """
    return ERROR_RESPONSES.get(error_type, ERROR_RESPONSES["rate_limit"])
