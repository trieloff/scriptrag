"""Mock props analyzer for testing that doesn't require LLM."""

from typing import Any


class MockPropsAnalyzer:
    """Mock analyzer that returns predefined props for testing."""

    name = "props_inventory"

    @property
    def requires_llm(self) -> bool:
        return False

    async def initialize(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Return mock props analysis based on scene heading."""

        heading = scene.get("heading", "")

        # Define mock props for each scene
        if "DETECTIVE'S OFFICE" in heading:
            return {
                "props": [
                    {
                        "name": "Revolver",
                        "category": "weapons",
                        "significance": "hero",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Badge",
                        "category": "personal_items",
                        "significance": "character_defining",
                        "action_required": False,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Whiskey Bottle",
                        "category": "food_beverage",
                        "significance": "character_defining",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Glass",
                        "category": "food_beverage",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Phone",
                        "category": "technology",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action", "dialogue"],
                    },
                    {
                        "name": "Cigarette",
                        "category": "personal_items",
                        "significance": "character_defining",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Lighter",
                        "category": "personal_items",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Briefcase",
                        "category": "personal_items",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Money",
                        "category": "money_valuables",
                        "significance": "plot_device",
                        "action_required": False,
                        "quantity": 1,
                        "mentions": ["dialogue", "action"],
                    },
                    {
                        "name": "Envelope",
                        "category": "documents",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "USB Drive",
                        "category": "technology",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["dialogue"],
                    },
                    {
                        "name": "Plane Ticket",
                        "category": "documents",
                        "significance": "plot_device",
                        "action_required": False,
                        "quantity": 1,
                        "mentions": ["dialogue"],
                    },
                    {
                        "name": "Hat",
                        "category": "clothing_accessories",
                        "significance": "character_defining",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Trench Coat",
                        "category": "clothing_accessories",
                        "significance": "character_defining",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Watch",
                        "category": "clothing_accessories",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Car Keys",
                        "category": "personal_items",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action", "dialogue"],
                    },
                ],
                "summary": {
                    "total_props": 16,
                    "hero_props": 1,
                    "requires_action": 14,
                    "categories": [
                        "weapons",
                        "personal_items",
                        "food_beverage",
                        "technology",
                        "documents",
                        "money_valuables",
                        "clothing_accessories",
                    ],
                },
            }
        if "PARKING LOT" in heading:
            return {
                "props": [
                    {
                        "name": "Mustang",
                        "category": "vehicles",
                        "significance": "hero",
                        "action_required": False,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Shotgun",
                        "category": "weapons",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "First Aid Kit",
                        "category": "medical",
                        "significance": "background",
                        "action_required": False,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Briefcase",
                        "category": "personal_items",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                ],
                "summary": {
                    "total_props": 4,
                    "hero_props": 1,
                    "requires_action": 2,
                    "categories": ["vehicles", "weapons", "medical", "personal_items"],
                },
            }
        if "MUSTANG" in heading:
            return {
                "props": [
                    {
                        "name": "Cellphone",
                        "category": "technology",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Diamonds",
                        "category": "money_valuables",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 5,
                        "mentions": ["action", "dialogue"],
                    },
                    {
                        "name": "Pouch",
                        "category": "personal_items",
                        "significance": "practical",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                    {
                        "name": "Laptop",
                        "category": "technology",
                        "significance": "plot_device",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["dialogue", "action"],
                    },
                    {
                        "name": "Shotgun",
                        "category": "weapons",
                        "significance": "hero",
                        "action_required": True,
                        "quantity": 1,
                        "mentions": ["action"],
                    },
                ],
                "summary": {
                    "total_props": 5,
                    "hero_props": 1,
                    "requires_action": 5,
                    "categories": [
                        "technology",
                        "money_valuables",
                        "personal_items",
                        "weapons",
                    ],
                },
            }
        # Default empty response
        return {
            "props": [],
            "summary": {
                "total_props": 0,
                "hero_props": 0,
                "requires_action": 0,
                "categories": [],
            },
        }
