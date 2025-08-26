# CLI Command Structure Consolidation

## Overview

This document describes the refactoring of the ScriptRAG CLI to achieve better separation of concerns, moving business logic to the API layer and keeping the CLI focused on argument parsing and output formatting.

## Problem Statement

The original CLI commands (scene.py: 548 lines, query.py: 402 lines) contained mixed responsibilities:

- Business logic embedded in CLI commands
- Inconsistent error handling
- Duplicated formatting code
- Tightly coupled validation logic

## Solution Architecture

### 1. Layer Separation

```text
┌─────────────────────────────────────────────┐
│                CLI Layer                     │
│  - Argument parsing (Typer)                  │
│  - Output selection (--json, --csv, etc.)    │
│  - User interaction (prompts, confirmations) │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│            Validation Layer                  │
│  - Input validation                          │
│  - Type checking                             │
│  - Business rule validation                  │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│              API Layer                       │
│  - Business logic                            │
│  - Database operations                       │
│  - External service integration              │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│           Formatting Layer                   │
│  - Output formatting                         │
│  - Multiple format support                   │
│  - Consistent presentation                   │
└─────────────────────────────────────────────┘
```

### 2. Module Structure

```text
src/scriptrag/cli/
├── commands/              # CLI commands (thin layer)
│   ├── scene_refactored.py
│   └── query_refactored.py
├── formatters/            # Output formatting
│   ├── base.py           # Base formatter classes
│   ├── scene_formatter.py
│   ├── query_formatter.py
│   ├── table_formatter.py
│   └── json_formatter.py
├── validators/            # Input validation
│   ├── base.py           # Base validator classes
│   ├── scene_validator.py
│   ├── project_validator.py
│   └── file_validator.py
└── utils/                # CLI utilities
    ├── cli_handler.py    # Unified error handling
    └── command_composer.py # Command composition
```

## Key Components

### 1. Formatters (`cli/formatters/`)

**Purpose**: Handle all output formatting, supporting multiple formats.

```python
class SceneFormatter(OutputFormatter):
    def format(self, data: Any, format_type: OutputFormat) -> str:
        # Format based on type: JSON, Table, Text, CSV, Markdown
        pass
```

**Benefits**:

- Consistent output across commands
- Easy to add new output formats
- Reusable formatting logic
- Testable in isolation

### 2. Validators (`cli/validators/`)

**Purpose**: Validate and transform user input before passing to API.

```python
class SceneValidator(Validator):
    def validate(self, value: dict) -> SceneIdentifier:
        # Validate scene components
        # Return validated model
        pass
```

**Benefits**:

- Early validation with clear error messages
- Reusable validation rules
- Type safety at CLI boundary
- Consistent validation across commands

### 3. CLI Handler (`cli/utils/cli_handler.py`)

**Purpose**: Standardized error handling and success responses.

```python
class CLIHandler:
    def handle_error(self, error: Exception, json_output: bool):
        # Consistent error formatting
        pass

    def handle_success(self, message: str, data: Any):
        # Consistent success formatting
        pass
```

**Benefits**:

- Unified error handling
- Consistent user feedback
- Support for JSON error responses
- Proper exit codes

### 4. Command Composer (`cli/utils/command_composer.py`)

**Purpose**: Compose complex multi-step operations.

```python
composer = CommandComposer()
composer.add_step("read", read_scene)
composer.add_step("validate", validate_content)
composer.add_step("update", update_scene, retry_count=2)
results = composer.execute()
```

**Benefits**:

- Complex workflows from simple steps
- Retry logic for resilient operations
- Transaction-like behavior with rollback
- Clear step-by-step execution

## Refactoring Example: Scene Command

### Before (Mixed Concerns)

```python
@scene_app.command()
def read_scene(project: str, scene: int, ...):
    # Validation mixed with business logic
    if not project:
        console.print("[red]Error: Project required[/red]")
        raise typer.Exit(1)

    # Business logic in CLI
    api = SceneManagementAPI()
    result = asyncio.run(api.read_scene(...))

    # Formatting logic embedded
    if json_output:
        console.print_json({...})
    else:
        console.print(Panel(...))
```

### After (Separated Concerns)

```python
@scene_app.command()
@async_cli_command
async def read_scene(project: str, scene: int, ...):
    # Initialize handlers
    handler = CLIHandler()
    formatter = SceneFormatter()
    validator = SceneValidator()

    # Validate input
    scene_id = validator.validate({...})

    # Call API (business logic)
    api = SceneManagementAPI()
    result = await api.read_scene(scene_id)

    # Format output
    formatter.print(result, output_format)
```

## Benefits Achieved

### 1. **Maintainability**

- Clear separation of concerns
- Each module has a single responsibility
- Easy to locate and fix issues

### 2. **Testability**

- Components can be tested in isolation
- Mock boundaries are clear
- Validators and formatters are pure functions

### 3. **Reusability**

- Formatters shared across commands
- Validators reused for similar inputs
- Common patterns extracted to utilities

### 4. **Consistency**

- Uniform error handling
- Consistent output formatting
- Standardized validation messages

### 5. **Extensibility**

- Easy to add new output formats
- Simple to add new validators
- New commands follow established patterns

## Usage Examples

### 1. Adding a New Output Format

```python
# Add to OutputFormat enum
class OutputFormat(Enum):
    YAML = "yaml"

# Implement in formatter
def format(self, data, format_type):
    if format_type == OutputFormat.YAML:
        return yaml.dump(data)
```

### 2. Creating a Composite Validator

```python
validator = CompositeValidator([
    ProjectValidator(),
    EpisodeIdentifierValidator(),
    SceneContentValidator()
])
result = validator.validate(input_data)
```

### 3. Building Complex Workflows

```python
composer = TransactionalComposer()
composer.add_step_with_rollback(
    "create", create_scene, rollback_create
)
composer.add_step_with_rollback(
    "index", update_index, rollback_index
)
results = composer.execute_with_rollback()
```

## Migration Guide

To migrate existing CLI commands:

1. **Extract Validation**
   - Move input validation to validators
   - Create specific validator classes
   - Use validators at command entry

2. **Move Business Logic**
   - Ensure all business logic is in API layer
   - CLI should only orchestrate API calls
   - No database access in CLI

3. **Implement Formatters**
   - Create formatters for each data type
   - Support multiple output formats
   - Remove embedded formatting logic

4. **Standardize Error Handling**
   - Use CLIHandler for all errors
   - Provide JSON error responses
   - Set appropriate exit codes

5. **Test Thoroughly**
   - Test validators independently
   - Test formatters with sample data
   - Test command composition
   - Ensure backward compatibility

## Conclusion

The refactored CLI structure provides a clean, maintainable, and extensible foundation for the ScriptRAG command-line interface. By separating concerns into distinct layers, we've achieved better code organization, improved testability, and consistent user experience across all commands.
