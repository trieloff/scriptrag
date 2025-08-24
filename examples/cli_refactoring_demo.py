"""Demonstration of the refactored CLI structure improvements."""

from scriptrag.api.scene_management import SceneManagementAPI
from scriptrag.cli.formatters.scene_formatter import SceneFormatter
from scriptrag.cli.formatters.table_formatter import TableFormatter
from scriptrag.cli.utils.cli_handler import CLIHandler
from scriptrag.cli.utils.command_composer import CommandComposer, TransactionalComposer
from scriptrag.cli.validators.project_validator import ProjectValidator
from scriptrag.cli.validators.scene_validator import SceneContentValidator


def demonstrate_separation_of_concerns() -> None:
    """Show how business logic, formatting, and validation are separated."""
    print("=== Separation of Concerns Demo ===\n")

    # 1. Validation Layer - Input validation separate from business logic
    print("1. Validation Layer:")
    validator = ProjectValidator()
    try:
        valid_project = validator.validate("my_screenplay")
        print(f"  ✓ Valid project name: {valid_project}")
    except Exception as e:
        print(f"  ✗ Validation failed: {e}")

    # 2. Business Logic Layer - Pure API calls without CLI concerns
    print("\n2. Business Logic Layer (API):")
    SceneManagementAPI()  # Example instantiation
    print("  - API handles all business operations")
    print("  - No CLI formatting or user interaction")
    print("  - Returns structured data models")

    # 3. Formatting Layer - Consistent output formatting
    print("\n3. Formatting Layer:")
    SceneFormatter()  # Example instantiation
    print("  - Formatters handle all output rendering")
    print("  - Support multiple formats (JSON, Table, Text)")
    print("  - Reusable across commands")

    # 4. Error Handling Layer - Unified error handling
    print("\n4. Error Handling Layer:")
    CLIHandler()  # Example instantiation
    print("  - Centralized error handling")
    print("  - Consistent error messages")
    print("  - Support for JSON error responses")


def demonstrate_command_composition() -> None:
    """Show how complex operations can be composed from simple steps."""
    print("\n=== Command Composition Demo ===\n")

    # Example: Complex scene editing workflow
    composer = CommandComposer()

    # Compose a multi-step workflow
    print("Composing a scene editing workflow:")

    # Mock functions for demonstration
    def read_scene() -> dict[str, str]:
        print("  → Reading scene from database")
        return {"content": "INT. OFFICE - DAY\nContent here..."}

    def validate_content(scene_data: dict[str, str]) -> str:
        print("  → Validating scene content")
        validator = SceneContentValidator()
        return validator.validate(scene_data["content"])

    def update_scene(content: str) -> dict[str, str | bool]:  # noqa: ARG001
        print("  → Updating scene in database")
        return {"success": True, "scene_id": "scene_42"}

    def send_notification(result: dict[str, str | bool]) -> bool:  # noqa: ARG001
        print("  → Sending update notification")
        return True

    # Build the composition
    composer.add_step("read", read_scene, on_error="abort")
    composer.add_step("validate", validate_content, on_error="abort")
    composer.add_step("update", update_scene, on_error="retry", retry_count=2)
    composer.add_step("notify", send_notification, on_error="continue")

    print("\nExecuting workflow:")
    composer.execute()

    print(f"\nWorkflow completed: {composer.all_successful()}")
    print(f"Successful steps: {len(composer.get_successful_results())}")


def demonstrate_transactional_operations() -> None:
    """Show how transactional operations with rollback work."""
    print("\n=== Transactional Operations Demo ===\n")

    composer = TransactionalComposer()

    # Mock functions with rollback
    def create_scene() -> dict[str, int]:
        print("  → Creating new scene")
        return {"scene_id": 42}

    def rollback_create(data: dict[str, int]) -> None:
        print(f"  ← Rolling back scene creation: {data['scene_id']}")

    def update_index() -> dict[str, bool]:
        print("  → Updating scene index")
        return {"index_updated": True}

    def rollback_index(data: dict[str, bool]) -> None:  # noqa: ARG001
        print("  ← Rolling back index update")

    # Add steps with rollback functions
    composer.add_step_with_rollback("create", create_scene, rollback_create)
    composer.add_step_with_rollback("index", update_index, rollback_index)

    print("Executing transactional workflow:")
    composer.execute_with_rollback()


def demonstrate_formatter_flexibility() -> None:
    """Show how formatters provide flexible output options."""
    print("\n=== Formatter Flexibility Demo ===\n")

    # Sample data
    data = [
        {"scene": 1, "location": "OFFICE", "time": "DAY"},
        {"scene": 2, "location": "STREET", "time": "NIGHT"},
        {"scene": 3, "location": "APARTMENT", "time": "MORNING"},
    ]

    formatter = TableFormatter()

    print("Same data, multiple formats:\n")

    # Table format
    print("1. Table Format:")
    print(formatter.format(data))

    # CSV format
    print("\n2. CSV Format:")
    from scriptrag.cli.formatters.base import OutputFormat

    print(formatter.format(data, OutputFormat.CSV))

    # Markdown format
    print("\n3. Markdown Format:")
    print(formatter.format(data, OutputFormat.MARKDOWN))


def main() -> None:
    """Run all demonstrations."""
    print("ScriptRAG CLI Refactoring Demonstration")
    print("=" * 50)

    demonstrate_separation_of_concerns()
    demonstrate_command_composition()
    demonstrate_transactional_operations()
    demonstrate_formatter_flexibility()

    print("\n" + "=" * 50)
    print("Key Improvements:")
    print("1. ✓ Business logic moved to API layer")
    print("2. ✓ CLI focused on argument parsing and output")
    print("3. ✓ Dedicated formatters for output formatting")
    print("4. ✓ Dedicated validators for input validation")
    print("5. ✓ Command composition for complex operations")
    print("6. ✓ Standardized error handling and user feedback")


if __name__ == "__main__":
    main()
