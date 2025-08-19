"""Comprehensive tests for JSON schema validation and extraction logic."""

import json

import pytest

from scriptrag.llm.providers.claude_schema import ClaudeSchemaHandler
from scriptrag.llm.providers.claude_types import JSONSchema, SchemaInfo


class TestClaudeSchemaHandler:
    """Test JSON schema extraction and validation for Claude provider."""

    @pytest.fixture
    def handler(self):
        """Create schema handler instance."""
        return ClaudeSchemaHandler()

    def test_extract_schema_info_openai_style(self, handler):
        """Test extracting schema from OpenAI-style response format."""
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "weather_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "temperature": {"type": "number"},
                        "humidity": {"type": "number"},
                        "conditions": {"type": "string"},
                    },
                    "required": ["temperature", "conditions"],
                },
            },
        }

        result = handler.extract_schema_info(response_format)

        assert result is not None
        assert result["name"] == "weather_response"
        assert "properties" in result["schema"]
        assert "temperature" in result["schema"]["properties"]
        assert "humidity" in result["schema"]["properties"]
        assert result["schema"]["required"] == ["temperature", "conditions"]

    def test_extract_schema_info_json_object_type(self, handler):
        """Test extracting schema for simple json_object type."""
        response_format = {"type": "json_object"}

        result = handler.extract_schema_info(response_format)

        assert result is not None
        assert result["name"] == "response"
        assert result["schema"] == {}

    def test_extract_schema_info_direct_schema(self, handler):
        """Test extracting schema from direct schema format."""
        response_format = {
            "name": "custom_response",
            "schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                    "score": {"type": "integer"},
                },
            },
        }

        result = handler.extract_schema_info(response_format)

        assert result is not None
        assert result["name"] == "custom_response"
        assert "properties" in result["schema"]
        assert "result" in result["schema"]["properties"]

    def test_extract_schema_info_none_input(self, handler):
        """Test extracting schema with None input."""
        result = handler.extract_schema_info(None)
        assert result is None

    def test_extract_schema_info_empty_dict(self, handler):
        """Test extracting schema with empty dict."""
        result = handler.extract_schema_info({})
        assert result is None

    def test_extract_schema_info_invalid_format(self, handler):
        """Test extracting schema with invalid format."""
        invalid_formats = [
            {"type": "unknown_type"},
            {"random": "data"},
            {"type": "json_schema"},  # Missing json_schema field
            {"json_schema": {}},  # Missing type field
        ]

        for invalid_format in invalid_formats:
            result = handler.extract_schema_info(invalid_format)
            # Should either return None or handle gracefully
            if result is not None:
                assert "name" in result
                assert "schema" in result

    def test_add_json_instructions_with_full_schema(self, handler):
        """Test adding JSON instructions with complete schema."""
        prompt = "Generate a weather report"
        schema_info: SchemaInfo = {
            "name": "weather",
            "schema": {
                "type": "object",
                "properties": {
                    "temperature": {
                        "type": "number",
                        "description": "Temperature in Celsius",
                    },
                    "humidity": {
                        "type": "integer",
                        "description": "Humidity percentage",
                    },
                    "conditions": {
                        "type": "string",
                        "description": "Weather conditions",
                    },
                    "wind_speed": {"type": "number"},
                },
                "required": ["temperature", "conditions"],
            },
        }

        result = handler.add_json_instructions(prompt, schema_info)

        # Check base instruction added
        assert "You must respond with valid JSON only" in result
        assert prompt in result

        # Check properties documented
        assert "temperature (number) [REQUIRED]: Temperature in Celsius" in result
        assert "humidity (integer): Humidity percentage" in result
        assert "conditions (string) [REQUIRED]: Weather conditions" in result
        assert "wind_speed (number)" in result

        # Check example included
        assert "Example JSON structure:" in result
        assert "```json" in result

    def test_add_json_instructions_without_schema(self, handler):
        """Test adding JSON instructions without schema properties."""
        prompt = "Generate JSON"
        schema_info: SchemaInfo = {"name": "response", "schema": {}}

        result = handler.add_json_instructions(prompt, schema_info)

        assert "You must respond with valid JSON only" in result
        assert prompt in result
        # Should not have property list or example
        assert "properties:" not in result.lower()
        assert "```json" not in result

    def test_add_json_instructions_with_nested_objects(self, handler):
        """Test adding JSON instructions with nested object schemas."""
        prompt = "Generate user data"
        schema_info: SchemaInfo = {
            "name": "user",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {
                        "type": "object",
                        "properties": {
                            "street": {"type": "string"},
                            "city": {"type": "string"},
                            "zip": {"type": "string"},
                        },
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name"],
            },
        }

        result = handler.add_json_instructions(prompt, schema_info)

        assert "name (string) [REQUIRED]" in result
        assert "address (object)" in result
        assert "tags (array)" in result
        assert "Example JSON structure:" in result

    def test_generate_example_from_schema_basic_types(self, handler):
        """Test generating example from schema with basic types."""
        schema: JSONSchema = {
            "type": "object",
            "properties": {
                "string_prop": {"type": "string"},
                "number_prop": {"type": "number"},
                "integer_prop": {"type": "integer"},
                "boolean_prop": {"type": "boolean"},
                "array_prop": {"type": "array", "items": {"type": "string"}},
            },
        }

        example = handler.generate_example_from_schema(schema)

        assert example is not None
        assert example["string_prop"] == ""
        assert example["number_prop"] == 0
        assert example["integer_prop"] == 0
        assert example["boolean_prop"] is False
        assert example["array_prop"] == []

    def test_generate_example_from_schema_nested_objects(self, handler):
        """Test generating example with nested objects."""
        schema: JSONSchema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "active": {"type": "boolean"},
                    },
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "created": {"type": "string"},
                        "version": {"type": "number"},
                    },
                },
            },
        }

        example = handler.generate_example_from_schema(schema)

        assert example is not None
        assert "user" in example
        assert example["user"]["id"] == 0
        assert example["user"]["name"] == ""
        assert example["user"]["active"] is False
        assert "metadata" in example
        assert example["metadata"]["created"] == ""
        assert example["metadata"]["version"] == 0

    def test_generate_example_from_schema_array_of_objects(self, handler):
        """Test generating example with array of objects."""
        schema: JSONSchema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
        }

        example = handler.generate_example_from_schema(schema)

        assert example is not None
        assert "items" in example
        assert isinstance(example["items"], list)
        assert len(example["items"]) == 1  # Single example item
        assert example["items"][0]["id"] == 0
        assert example["items"][0]["name"] == ""

    def test_generate_example_from_schema_empty_schema(self, handler):
        """Test generating example from empty schema."""
        result = handler.generate_example_from_schema({})
        assert result is None

        result = handler.generate_example_from_schema(None)
        assert result is None

    def test_generate_example_from_schema_unknown_types(self, handler):
        """Test generating example with unknown/invalid types."""
        schema: JSONSchema = {
            "type": "object",
            "properties": {
                "unknown_type": {"type": "unknown"},
                "missing_type": {},
                "null_type": {"type": None},
            },
        }

        example = handler.generate_example_from_schema(schema)

        assert example is not None
        # Should default to empty string for unknown types
        assert example["unknown_type"] == ""
        assert example["missing_type"] == ""
        assert example["null_type"] == ""

    def test_generate_object_example_complex_nesting(self, handler):
        """Test generating deeply nested object examples."""
        obj_schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "level3": {
                                    "type": "object",
                                    "properties": {
                                        "value": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

        result = handler._generate_object_example(obj_schema)

        assert "level1" in result
        assert "level2" in result["level1"]
        assert "level3" in result["level1"]["level2"]
        assert "value" in result["level1"]["level2"]["level3"]
        assert result["level1"]["level2"]["level3"]["value"] == ""

    def test_schema_validation_edge_cases(self, handler):
        """Test schema validation with edge cases."""
        edge_cases = [
            # Circular reference (simplified)
            {
                "type": "object",
                "properties": {
                    "self": {"type": "object"},  # Would need $ref for true circular
                },
            },
            # Mixed array types
            {
                "type": "object",
                "properties": {
                    "mixed": {
                        "type": "array",
                        "items": [
                            {"type": "string"},
                            {"type": "number"},
                        ],
                    },
                },
            },
            # Additional properties
            {
                "type": "object",
                "properties": {
                    "known": {"type": "string"},
                },
                "additionalProperties": {"type": "number"},
            },
            # Enum values
            {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "pending"],
                    },
                },
            },
        ]

        for schema in edge_cases:
            # Should handle without crashing
            example = handler.generate_example_from_schema(schema)
            assert example is not None or schema == {}

    def test_add_json_instructions_preserves_original_prompt(self, handler):
        """Test that original prompt is preserved when adding instructions."""
        original_prompt = (
            "This is my original prompt with\nmultiple lines\nand special chars: !@#$%"
        )
        schema_info: SchemaInfo = {
            "name": "test",
            "schema": {
                "type": "object",
                "properties": {"field": {"type": "string"}},
            },
        }

        result = handler.add_json_instructions(original_prompt, schema_info)

        assert original_prompt in result
        assert result.startswith(original_prompt)
        assert len(result) > len(original_prompt)

    def test_json_instruction_formatting(self, handler):
        """Test JSON instruction formatting and structure."""
        schema_info: SchemaInfo = {
            "name": "test",
            "schema": {
                "type": "object",
                "properties": {
                    "required_field": {
                        "type": "string",
                        "description": "A required field",
                    },
                    "optional_field": {
                        "type": "number",
                        "description": "An optional field",
                    },
                },
                "required": ["required_field"],
            },
        }

        result = handler.add_json_instructions("Test", schema_info)

        # Check formatting structure
        lines = result.split("\n")
        assert any("IMPORTANT:" in line for line in lines)
        assert any("REQUIRED" in line for line in lines)
        assert any("required_field" in line for line in lines)
        assert any("optional_field" in line for line in lines)

        # Verify JSON example is valid
        json_start = result.find("```json")
        json_end = result.find("```", json_start + 7)
        if json_start != -1 and json_end != -1:
            json_str = result[json_start + 7 : json_end].strip()
            try:
                parsed = json.loads(json_str)
                assert "required_field" in parsed
                assert "optional_field" in parsed
            except json.JSONDecodeError:
                pytest.fail("Generated JSON example is not valid")

    def test_schema_with_all_field_types(self, handler):
        """Test comprehensive schema with all supported field types."""
        complex_schema: SchemaInfo = {
            "name": "comprehensive",
            "schema": {
                "type": "object",
                "properties": {
                    "string_field": {"type": "string", "description": "Text field"},
                    "number_field": {"type": "number", "description": "Decimal"},
                    "integer_field": {"type": "integer", "description": "Whole number"},
                    "boolean_field": {"type": "boolean", "description": "True/False"},
                    "array_strings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of strings",
                    },
                    "array_numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of numbers",
                    },
                    "array_objects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "value": {"type": "string"},
                            },
                        },
                        "description": "List of objects",
                    },
                    "nested_object": {
                        "type": "object",
                        "properties": {
                            "nested_string": {"type": "string"},
                            "nested_array": {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                        },
                        "description": "Nested structure",
                    },
                },
                "required": [
                    "string_field",
                    "number_field",
                    "boolean_field",
                ],
            },
        }

        # Test instruction generation
        instructions = handler.add_json_instructions("Generate data", complex_schema)
        assert "string_field (string) [REQUIRED]: Text field" in instructions
        assert "number_field (number) [REQUIRED]: Decimal" in instructions
        assert "boolean_field (boolean) [REQUIRED]: True/False" in instructions
        assert "array_strings (array): List of strings" in instructions
        assert "nested_object (object): Nested structure" in instructions

        # Test example generation
        example = handler.generate_example_from_schema(complex_schema["schema"])
        assert example is not None
        assert isinstance(example["string_field"], str)
        assert isinstance(example["number_field"], int | float)
        assert isinstance(example["boolean_field"], bool)
        assert isinstance(example["array_strings"], list)
        assert isinstance(example["nested_object"], dict)
