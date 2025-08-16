#!/usr/bin/env python3
"""Add test markers to categorize tests for performance optimization."""

from pathlib import Path


def detect_test_type(
    file_path: Path,
    test_name: str,  # noqa: ARG001
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


def add_markers_to_file(file_path: Path) -> bool:
    """Add pytest markers to a test file."""
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
        file_path.write_text("\n".join(new_lines))
        return True

    return False


def main():
    """Main function to process all test files."""
    test_dir = Path("tests")

    # Find all test files
    test_files = list(test_dir.rglob("test_*.py")) + list(test_dir.rglob("*_test.py"))

    print(f"Found {len(test_files)} test files")

    modified_count = 0
    for test_file in test_files:
        if add_markers_to_file(test_file):
            print(f"✓ Added markers to {test_file}")
            modified_count += 1

    print(f"\nModified {modified_count} files")
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


if __name__ == "__main__":
    main()
