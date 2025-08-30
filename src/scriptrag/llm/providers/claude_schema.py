"""JSON schema handling for Claude Code provider."""

from __future__ import annotations

import json
from typing import Any

from scriptrag.llm.providers.claude_types import (
    JSONSchema,
    JSONSchemaProperty,
    SchemaInfo,
)


class ClaudeSchemaHandler:
    """Handles JSON schema operations for Claude Code provider."""

    def extract_schema_info(self, response_format: dict[str, Any]) -> SchemaInfo | None:
        """Extract schema information from response_format.

        Args:
            response_format: The response format specification

        Returns:
            Schema info dict or None
        """
        if not response_format:
            return None

        # Handle different response_format structures
        if response_format.get("type") == "json_schema":
            # OpenAI-style with nested json_schema
            json_schema = response_format.get("json_schema", {})
            return {
                "name": json_schema.get("name", "response"),
                "schema": json_schema.get("schema", {}),
            }
        if response_format.get("type") == "json_object":
            # Simple JSON object without schema
            return {"name": "response", "schema": {}}
        if "schema" in response_format:
            # Direct schema format
            return {
                "name": response_format.get("name", "response"),
                "schema": response_format["schema"],
            }

        return None

    def add_json_instructions(self, prompt: str, schema_info: SchemaInfo) -> str:
        """Add JSON output instructions to the prompt.

        Args:
            prompt: Original prompt
            schema_info: Schema information dict

        Returns:
            Modified prompt with JSON instructions
        """
        schema = schema_info.get("schema", {})

        # Build JSON instruction
        json_instruction = (
            "\n\nIMPORTANT: You must respond with valid JSON only, no other text."
        )

        if schema and "properties" in schema:
            props = schema["properties"]
            required = schema.get("required", [])

            json_instruction += "\n\nThe JSON response must have these properties:"
            for prop, details in props.items():
                prop_type = details.get("type", "any")
                desc = details.get("description", "")
                is_required = prop in required

                json_instruction += f"\n- {prop} ({prop_type})"
                if is_required:
                    json_instruction += " [REQUIRED]"
                if desc:
                    json_instruction += f": {desc}"

            # Add example if possible
            example = self.generate_example_from_schema(schema)
            if example:
                json_instruction += (
                    f"\n\nExample JSON structure:\n```json\n"
                    f"{json.dumps(example, indent=2)}\n```"
                )

        return prompt + json_instruction

    def generate_example_from_schema(self, schema: JSONSchema) -> dict[str, Any] | None:
        """Generate an example JSON object from schema.

        Args:
            schema: JSON schema

        Returns:
            Example dict or None
        """
        if not schema or "properties" not in schema:
            return None

        example: dict[str, Any] = {}
        props = schema["properties"]

        for prop, details in props.items():
            prop_type = details.get("type", "string")

            if prop_type == "array":
                items = details.get("items", {})
                # Handle case where items is a list (tuple validation) or dict
                # (single type)
                if isinstance(items, list):
                    # Multiple item types (tuple validation) - use first type
                    if items and isinstance(items[0], dict):
                        items_type = items[0].get("type", "string")
                        items_schema = items[0]
                    else:
                        items_type = "string"
                        items_schema = {}
                else:
                    # Single item type
                    items_type = items.get("type", "string")
                    items_schema = items

                if items_type == "object":
                    # For complex objects, provide a single example
                    example[prop] = [self._generate_object_example(items_schema)]
                else:
                    example[prop] = []
            elif prop_type == "object":
                example[prop] = self._generate_object_example(details)
            elif prop_type == "number" or prop_type == "integer":
                example[prop] = 0
            elif prop_type == "boolean":
                example[prop] = False
            else:  # string or unknown
                example[prop] = ""

        return example

    def _generate_object_example(
        self, obj_schema: JSONSchema | JSONSchemaProperty
    ) -> dict[str, Any]:
        """Generate example for object type.

        Args:
            obj_schema: Object schema

        Returns:
            Example object
        """
        if "properties" in obj_schema:
            result: dict[str, Any] = {}
            for key, val in obj_schema["properties"].items():
                prop_type = val.get("type", "string")
                if prop_type == "string":
                    result[key] = ""
                elif prop_type in ["number", "integer"]:
                    result[key] = 0
                elif prop_type == "boolean":
                    result[key] = False
                elif prop_type == "array":
                    result[key] = []
                elif prop_type == "object":
                    # Recursively generate nested object structure
                    result[key] = self._generate_object_example(val)
            return result
        return {}
