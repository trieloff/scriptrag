#!/usr/bin/env python3
"""Check Python file sizes for MCP tools compatibility."""

import argparse
import sys
from pathlib import Path

# Known violations that we're tracking but not enforcing yet
# These files need refactoring in separate PRs
KNOWN_VIOLATIONS = {
    "src/scriptrag/cli.py",
    "src/scriptrag/mcp_server.py",
    "src/scriptrag/mentors/character_arc.py",
    "src/scriptrag/database/operations.py",
    "src/scriptrag/database/migrations.py",
}


def count_lines(file_path: Path) -> int:
    """Count the number of lines in a file."""
    try:
        with file_path.open(encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0


def check_file_sizes(
    paths: list[str],
    soft_limit: int = 1000,
    hard_limit: int = 1500,
    test_limit: int = 2000,
) -> int:
    """Check file sizes and report violations.

    Args:
        paths: List of file paths to check
        soft_limit: Warning threshold for regular files
        hard_limit: Error threshold for regular files
        test_limit: Error threshold for test files

    Returns:
        Exit code (0 for success, 1 for violations)
    """
    warnings = []
    errors = []

    for path_str in paths:
        path = Path(path_str)
        if not path.exists() or path.suffix != ".py":
            continue

        lines = count_lines(path)
        is_test = "test" in path.parts or path.name.startswith("test_")

        if is_test:
            if lines > test_limit:
                errors.append(
                    f"{path}: {lines} lines exceeds test file limit of {test_limit}"
                )
        else:
            if lines > hard_limit:
                # Check if this is a known violation
                if str(path) in KNOWN_VIOLATIONS:
                    msg = f"{path}: {lines} lines exceeds hard limit of {hard_limit}"
                    warnings.append(f"{msg} (known violation)")
                else:
                    errors.append(
                        f"{path}: {lines} lines exceeds hard limit of {hard_limit}"
                    )
            elif lines > soft_limit:
                warnings.append(
                    f"{path}: {lines} lines exceeds soft limit of {soft_limit}"
                )

    # Print warnings
    for warning in warnings:
        print(f"WARNING: {warning}")

    # Print errors
    for error in errors:
        print(f"ERROR: {error}")

    # Suggest refactoring for files exceeding soft limit
    if warnings:
        print("\nConsider refactoring these files into smaller modules:")
        print("- Split by functionality or responsibility")
        print("- Extract common utilities to separate modules")
        print("- Use composition and delegation patterns")

    return 1 if errors else 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check Python file sizes for MCP compatibility"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python files to check",
    )
    parser.add_argument(
        "--soft-limit",
        type=int,
        default=1000,
        help="Soft limit for regular files (warning)",
    )
    parser.add_argument(
        "--hard-limit",
        type=int,
        default=1500,
        help="Hard limit for regular files (error)",
    )
    parser.add_argument(
        "--test-limit",
        type=int,
        default=2000,
        help="Hard limit for test files (error)",
    )

    args = parser.parse_args()

    exit_code = check_file_sizes(
        args.files,
        soft_limit=args.soft_limit,
        hard_limit=args.hard_limit,
        test_limit=args.test_limit,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
