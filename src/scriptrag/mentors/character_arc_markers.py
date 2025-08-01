"""Character Arc Transformation Markers and Development Stages.

This module contains transformation markers, agency phases, and development
stages used in character arc analysis.
"""

from __future__ import annotations

from scriptrag.mentors.base import AnalysisSeverity


class TransformationMarker:
    """Represents a key transformation moment in a character's journey."""

    def __init__(
        self,
        name: str,
        description: str,
        arc_types: list[str],
        severity_if_missing: AnalysisSeverity,
        indicators: list[str],
    ):
        """Initialize a transformation marker.

        Args:
            name: Marker name
            description: What this marker represents
            arc_types: Which arc types this applies to
            severity_if_missing: How severe if this marker is missing
            indicators: Keywords/patterns that indicate this marker
        """
        self.name = name
        self.description = description
        self.arc_types = arc_types
        self.severity_if_missing = severity_if_missing
        self.indicators = indicators


class CharacterAgencyPhase:
    """Represents a phase in character agency development."""

    def __init__(
        self,
        name: str,
        description: str,
        indicators: list[str],
        typical_percentage: float,
    ):
        """Initialize an agency phase.

        Args:
            name: Phase name
            description: Character behavior in this phase
            indicators: Keywords indicating this phase
            typical_percentage: Typical % of story in this phase
        """
        self.name = name
        self.description = description
        self.indicators = indicators
        self.typical_percentage = typical_percentage


class CharacterDevelopmentStage:
    """Represents a stage in character development."""

    def __init__(
        self,
        name: str,
        description: str,
        typical_position: float,
        indicators: list[str],
    ):
        """Initialize a character development stage.

        Args:
            name: Stage name
            description: What happens in this stage
            typical_position: Where in the story this typically occurs (0.0-1.0)
            indicators: Keywords that indicate this stage
        """
        self.name = name
        self.description = description
        self.typical_position = typical_position
        self.indicators = indicators


# Key transformation markers to track
TRANSFORMATION_MARKERS = [
    TransformationMarker(
        "The Lie/False Belief",
        "Character's initial false belief that drives their flawed behavior",
        ["Positive Change Arc", "Negative Change Arc"],
        AnalysisSeverity.ERROR,
        ["believes", "thinks", "assumes", "fear", "flaw", "mistaken", "wrong about"],
    ),
    TransformationMarker(
        "The Wound",
        "Past trauma or experience that created the false belief",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.WARNING,
        ["past", "trauma", "hurt", "loss", "abandoned", "betrayed", "failed"],
    ),
    TransformationMarker(
        "The Want",
        "External goal the character pursues (what they think will make them happy)",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.ERROR,
        ["wants", "desires", "pursues", "goal", "seeks", "after", "needs to"],
    ),
    TransformationMarker(
        "The Need",
        "Internal truth the character must embrace for fulfillment",
        ["Positive Change Arc"],
        AnalysisSeverity.ERROR,
        ["needs to learn", "must understand", "truth is", "realize", "accept"],
    ),
    TransformationMarker(
        "Catalyst Crisis",
        "Event that forces character out of their comfort zone",
        ["Positive Change Arc", "Negative Change Arc", "Corruption Arc"],
        AnalysisSeverity.ERROR,
        ["forced", "catalyst", "inciting", "disrupts", "changes everything", "must"],
    ),
    TransformationMarker(
        "Moment of Truth",
        "Character faces choice between old self and potential new self",
        ["Positive Change Arc", "Negative Change Arc"],
        AnalysisSeverity.ERROR,
        ["chooses", "decides", "moment of truth", "crossroads", "ultimatum"],
    ),
    TransformationMarker(
        "The Cost",
        "What the character must sacrifice for their transformation",
        ["Positive Change Arc", "Corruption Arc"],
        AnalysisSeverity.WARNING,
        ["sacrifice", "lose", "give up", "cost", "price", "let go"],
    ),
    TransformationMarker(
        "Core Truth",
        "The unchanging principle the character embodies",
        ["Flat Arc"],
        AnalysisSeverity.ERROR,
        ["believes in", "stands for", "principle", "truth", "values", "integrity"],
    ),
    TransformationMarker(
        "World's Lie",
        "The false belief the world around the character holds",
        ["Flat Arc"],
        AnalysisSeverity.WARNING,
        ["world believes", "everyone thinks", "corrupt", "forgotten", "lost"],
    ),
]


# Character agency progression phases
AGENCY_PHASES = [
    CharacterAgencyPhase(
        "Victim Stage",
        "Things happen TO the character - 'Why is this happening to me?'",
        ["happens to", "victim", "powerless", "why me", "unfair", "can't"],
        0.15,
    ),
    CharacterAgencyPhase(
        "Survivor Stage",
        "Character reacts to survive - 'I'll do whatever it takes to get through'",
        ["survives", "reacts", "defends", "escapes", "endures", "gets through"],
        0.25,
    ),
    CharacterAgencyPhase(
        "Navigator Stage",
        "Character makes active choices - 'I choose my path'",
        ["decides", "chooses", "plans", "pursues", "takes action", "determines"],
        0.35,
    ),
    CharacterAgencyPhase(
        "Creator Stage",
        "Character shapes their world - 'I create my reality'",
        ["creates", "transforms", "influences", "changes", "shapes", "builds"],
        0.25,
    ),
]


# Universal character development stages
DEVELOPMENT_STAGES = [
    CharacterDevelopmentStage(
        "Establishment",
        "Introduction showing character's initial state, flaws, and false beliefs",
        0.05,
        ["introduction", "first appearance", "establishes", "normal", "flaw"],
    ),
    CharacterDevelopmentStage(
        "Want Revealed",
        (
            "Character's external goal becomes clear - what they think "
            "will make them happy"
        ),
        0.15,
        ["wants", "desires", "goal", "pursues", "thinks needs"],
    ),
    CharacterDevelopmentStage(
        "First Test",
        "Initial challenge that reveals character's limitations and approach",
        0.25,
        ["challenged", "tested", "fails", "struggles", "confronts"],
    ),
    CharacterDevelopmentStage(
        "Deepening Conflict",
        "Internal conflict intensifies as want and need clash",
        0.40,
        ["conflict", "torn between", "doubts", "questions", "internal struggle"],
    ),
    CharacterDevelopmentStage(
        "Crisis Point",
        "Major setback forces character to question their approach",
        0.60,
        ["crisis", "lowest point", "devastated", "loses", "questioned"],
    ),
    CharacterDevelopmentStage(
        "Moment of Truth",
        "Character must choose between want and need",
        0.75,
        ["chooses", "decides", "realization", "epiphany", "moment of truth"],
    ),
    CharacterDevelopmentStage(
        "Transformation",
        "Character demonstrates their change through action",
        0.85,
        ["transformed", "changed", "different", "new person", "demonstrates"],
    ),
    CharacterDevelopmentStage(
        "New Equilibrium",
        "Character's new state is established, showing lasting change",
        0.95,
        ["new normal", "changed forever", "resolution", "peace", "fulfilled"],
    ),
]
