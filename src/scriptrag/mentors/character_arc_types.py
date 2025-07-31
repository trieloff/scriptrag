"""Character Arc Types and Constants.

This module contains the definitions for various character arc types
used in screenplay analysis, including positive, negative, flat, and
corruption arcs.
"""

from __future__ import annotations


class CharacterArcType:
    """Represents a type of character arc."""

    def __init__(
        self,
        name: str,
        description: str,
        indicators: list[str],
        journey_pattern: list[str],
        examples: list[str],
        thematic_focus: str,
    ):
        """Initialize a character arc type.

        Args:
            name: Arc type name
            description: Arc description
            indicators: Keywords/patterns that indicate this arc type
            journey_pattern: Expected stages in this arc
            examples: Famous examples of this arc type
            thematic_focus: What theme this arc typically explores
        """
        self.name = name
        self.description = description
        self.indicators = indicators
        self.journey_pattern = journey_pattern
        self.examples = examples
        self.thematic_focus = thematic_focus


# Comprehensive character arc types based on screenplay expertise
CHARACTER_ARC_TYPES = [
    CharacterArcType(
        "Positive Change Arc",
        (
            "Character overcomes their false belief (The Lie) to embrace truth. "
            "They transform from flawed to fulfilled through trials and revelation. "
            "Most common arc where protagonist grows and changes for the better."
        ),
        [
            "growth",
            "learns",
            "realizes",
            "overcomes",
            "transforms",
            "becomes",
            "discovers",
            "accepts",
            "embraces",
            "evolves",
            "heals",
            "forgives",
        ],
        [
            "The Lie They Believe (initial false belief)",
            "Comfort Zone (where they hide from growth)",
            "Catalyst Moment (forced out of hiding)",
            "First Act Resistance (clinging to the lie)",
            "Education Phase (learning but not changing inside)",
            "Midpoint Mirror (seeing who they could become)",
            "Dark Night Moment (everything fails, lie seems true)",
            "The Revelation (visceral understanding of truth)",
            "Climactic Choice (choosing new self over old)",
            "New Equilibrium (fundamentally changed)",
        ],
        ["Luke Skywalker", "Erin Brockovich", "Andy Dufresne", "Katniss Everdeen"],
        "Personal growth through adversity",
    ),
    CharacterArcType(
        "Negative Change Arc",
        (
            "Character had every opportunity to change but refused them all. "
            "Their fatal flaw and pride lead to systematic destruction of everything "
            "they claimed to value. The tragedy of stubborn blindness."
        ),
        [
            "corrupted",
            "falls",
            "descends",
            "loses",
            "deteriorates",
            "pride",
            "refuses",
            "justifies",
            "rationalizes",
            "betrays",
            "isolates",
            "destroys",
        ],
        [
            "The Pride Point (where they cannot bend)",
            "Initial Compromise ('just this once')",
            "The Rationalization (justifying the means)",
            "First Warning (consequences appear)",
            "Doubling Down (going deeper instead of pulling back)",
            "Rejected Redemptions (speeding past offramps)",
            "The Betrayal Cascade (betraying more important values)",
            "Point of No Return (the damning choice)",
            "Systematic Destruction (losing what they protected)",
            "The Isolation Endpoint (alone with their pride)",
        ],
        ["Walter White", "Michael Corleone", "Anakin Skywalker", "Macbeth"],
        "How pride and fear corrupt absolutely",
    ),
    CharacterArcType(
        "Flat Arc",
        (
            "Character doesn't change - they change everyone around them. "
            "They enter a world that has forgotten truth and through steadfast "
            "demonstration of their values, bend the world to accommodate their truth."
        ),
        [
            "steadfast",
            "unchanging",
            "principled",
            "inspires",
            "influences",
            "demonstrates",
            "consistent",
            "unwavering",
            "catalyst",
            "transforms others",
        ],
        [
            "Core Truth (what they know that world forgot)",
            "Truth vs World (entering corrupt environment)",
            "Pressure Points (attempts to change them)",
            "Standing Firm (maintaining principles under pressure)",
            "The Demonstration (showing truth through action)",
            "First Convert (someone sees their truth)",
            "The Conversion Wave (others adopt worldview)",
            "Testing Crucibles (extreme tests of truth)",
            "Influence Ripples (change spreading outward)",
            "World Reformed (environment bent to their truth)",
        ],
        ["Ellen Ripley", "Paddington Bear", "Captain America", "Atticus Finch"],
        "How integrity changes the world",
    ),
    CharacterArcType(
        "Corruption Arc",
        (
            "Good person becomes monster through incremental moral compromises. "
            "Starting with noble intentions, they're seduced by power/fear into "
            "becoming everything they once fought against."
        ),
        [
            "corrupts",
            "seduced",
            "tempted",
            "compromises",
            "justifies",
            "transforms negatively",
            "becomes monster",
            "loses soul",
            "darkness",
        ],
        [
            "Innocence Established (who they were)",
            "The Wound Inflicted (breaking their faith)",
            "Noble Intention (initial good purpose)",
            "The Dark Invitation (offered power through corruption)",
            "First Sin (framed as necessity)",
            "The Mentor Figure (guide into darkness)",
            "Justified Atrocity (terrible but 'necessary')",
            "The Slippery Slope (each act requires worse)",
            "Moral Event Horizon (act they can't return from)",
            "Final Transformation (becoming the monster)",
        ],
        ["Michael Corleone", "Harvey Dent", "Smeagol/Gollum", "Carrie White"],
        "How good intentions pave the road to hell",
    ),
]
