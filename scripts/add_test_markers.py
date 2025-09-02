#!/usr/bin/env python3
"""Add test markers to categorize tests for performance optimization."""

import argparse
import shutil
import sys
from pathlib import Path


def detect_test_type(
    file_path: Path,
    _test_name: str,
    test_content: str,
) -> set[str]:
    """Detect the type of test based on file path and content."""
    markers = set()

    # Check file path for test type
    path_str = str(file_path)
    if "/unit/" in path_str:
        markers.add("unit")
    elif "/integration/" in path_str:
        markers.add("integration")
    elif "/e2e/" in path_str:
        markers.add("e2e")

    # Check test content for specific features
    content_lower = test_content.lower()

    # Database tests
    if any(x in content_lower for x in ["database", "db_ops", "sqlite", "engine"]):
        markers.add("database")
        if "integration" not in markers:
            markers.add("unit")  # Default to unit if not already categorized

    # LLM tests
    if any(
        x in content_lower
        for x in ["llm", "completion", "embedding", "claude", "github_models"]
    ):
        markers.add("llm")
        markers.add("requires_llm")

    # Parser tests
    if any(x in content_lower for x in ["fountain", "parse", "parser"]):
        markers.add("parser")

    # API tests
    if any(x in content_lower for x in ["api", "endpoint", "fastapi", "httpx"]):
        markers.add("api")

    # CLI tests
    if any(x in content_lower for x in ["cli", "typer", "runner", "invoke"]):
        markers.add("cli")

    # MCP tests
    if "mcp" in content_lower:
        markers.add("mcp")

    # Scene management tests
    if any(x in content_lower for x in ["scene", "scene_database", "scene_index"]):
        markers.add("scene")

    # GraphRAG tests
    if any(x in content_lower for x in ["graph", "graphrag", "networkx"]):
        markers.add("graphrag")

    # Search tests
    if any(x in content_lower for x in ["search", "query", "similarity"]):
        markers.add("search")

    # Slow tests (heuristics)
    if any(
        x in content_lower
        for x in [
            "sleep",
            "delay",
            "timeout",
            "retry",
            "benchmark",
            "stress",
            "large",
            "many",
            "bulk",
            "batch",
            "concurrent",
            "parallel",
        ]
    ):
        markers.add("slow")

    # Tests with actual network calls
    if any(x in content_lower for x in ["httpx", "requests", "urllib", "aiohttp"]):
        markers.add("integration")
        markers.add("slow")

    # If no category detected, default to unit
    if not markers.intersection({"unit", "integration", "e2e"}):
        markers.add("unit")

    return markers


def add_markers_to_file(
    file_path: Path, backup: bool = False, dry_run: bool = False
) -> bool:
    """Add pytest markers to a test file.

    Args:
        file_path: Path to the test file
        backup: If True, create a backup of the file before modifying
        dry_run: If True, don't actually modify the file, just report what would be done

    Returns:
        True if the file was modified (or would be modified in dry-run mode)
    """
    content = file_path.read_text()
    lines = content.splitlines()
    modified = False
    new_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a test function or class
        if line.strip().startswith("def test_") or line.strip().startswith(
            "class Test"
        ):
            # Check if there are already markers
            has_markers = False
            j = i - 1
            while j >= 0 and lines[j].strip().startswith("@"):
                if "@pytest.mark" in lines[j]:
                    has_markers = True
                    break
                j -= 1

            if not has_markers:
                # Extract test content (next 20 lines or until next test)
                test_content = "\n".join(lines[i : min(i + 20, len(lines))])
                test_name = (
                    line.strip().split("(")[0].replace("def ", "").replace("class ", "")
                )

                # Detect markers
                markers = detect_test_type(file_path, test_name, test_content)

                # Add markers
                indent = len(line) - len(line.lstrip())
                for marker in sorted(markers):
                    new_lines.append(" " * indent + f"@pytest.mark.{marker}")
                    modified = True

        new_lines.append(line)
        i += 1

    if modified:
        if dry_run:
            print(f"[DRY RUN] Would modify {file_path}")
        else:
            if backup:
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)
                print(f"  Backup created: {backup_path}")
            file_path.write_text("\n".join(new_lines))
        return True

    return False


def main() -> int:
    """Main function to process all test files.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Add pytest markers to test files for performance optimization"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup files before modifying (*.bak)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore files from backups (*.bak files)",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="tests",
        help="Path to test directory or file (default: tests)",
    )

    args = parser.parse_args()

    # Handle restore mode
    if args.restore:
        return restore_from_backups(Path(args.path))

    test_path = Path(args.path)

    if not test_path.exists():
        print(f"Error: Path '{test_path}' does not exist")
        return 1

    # Determine test files to process
    if test_path.is_file():
        test_files = [test_path]
    else:
        # Find all test files
        test_files = list(test_path.rglob("test_*.py")) + list(
            test_path.rglob("*_test.py")
        )

    print(f"Found {len(test_files)} test files")

    if args.dry_run:
        print("=== DRY RUN MODE - No files will be modified ===")

    modified_count = 0
    for test_file in test_files:
        if add_markers_to_file(test_file, backup=args.backup, dry_run=args.dry_run):
            if not args.dry_run:
                print(f"✓ Added markers to {test_file}")
            modified_count += 1

    action = "Would modify" if args.dry_run else "Modified"
    print(f"\n{action} {modified_count} files")

    if args.backup and modified_count > 0 and not args.dry_run:
        print("\nBackup files created with .bak extension")
        print("To restore: python scripts/add_test_markers.py --restore")
    print("\nMarkers added:")
    print("- unit: Unit tests (fast, isolated)")
    print("- integration: Integration tests")
    print("- slow: Slow running tests")
    print("- database: Database tests")
    print("- llm: LLM tests")
    print("- requires_llm: Tests requiring LLM")
    print("- parser: Parser tests")
    print("- api: API tests")
    print("- cli: CLI tests")
    print("- mcp: MCP tests")
    print("- scene: Scene management tests")
    print("- graphrag: GraphRAG tests")
    print("- search: Search tests")

    return 0


def restore_from_backups(path: Path) -> int:
    """Restore files from their backups.

    Args:
        path: Directory or file path to restore

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if path.is_file():
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_files = [backup_path] if backup_path.exists() else []
    else:
        backup_files = list(path.rglob("*.py.bak"))

    if not backup_files:
        print("No backup files found")
        return 1

    print(f"Found {len(backup_files)} backup files")
    restored_count = 0

    for backup_file in backup_files:
        original_file = backup_file.with_suffix("")  # Remove .bak
        try:
            shutil.copy2(backup_file, original_file)
            backup_file.unlink()  # Remove backup after successful restore
            print(f"✓ Restored {original_file}")
            restored_count += 1
        except Exception as e:
            print(f"✗ Failed to restore {original_file}: {e}")

    print(f"\nRestored {restored_count} files")
    return 0 if restored_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
