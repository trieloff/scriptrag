#!/usr/bin/env python3
"""Check that test fixture files haven't been modified."""

import sys
from pathlib import Path


def check_fountain_fixtures() -> bool:
    """Ensure fountain fixture files are clean (no metadata)."""
    fixtures_dir = Path("tests/fixtures/fountain/test_data")

    if not fixtures_dir.exists():
        print(f"Warning: Fixtures directory not found: {fixtures_dir}")
        return True

    # Files that are expected to have metadata (for testing purposes)
    expected_with_metadata = {
        "coffee_shop_with_metadata.fountain",
        "script_with_metadata.fountain",
        "props_test_script.fountain",  # May have metadata from props tests
    }

    errors = []
    for fountain_file in fixtures_dir.glob("*.fountain"):
        # Skip files that are expected to have metadata
        if fountain_file.name in expected_with_metadata:
            continue

        content = fountain_file.read_text(encoding="utf-8")
        if "SCRIPTRAG-META-START" in content:
            errors.append(f"Fixture file contaminated with metadata: {fountain_file}")

    if errors:
        print("ERROR: Test fixture files have been modified!")
        for error in errors:
            print(f"  - {error}")
        print("\nFixture files should NEVER be modified by tests.")
        print("Tests must work with temporary copies only.")
        return False

    print("✓ All fixture files are clean")
    return True


if __name__ == "__main__":
    if not check_fountain_fixtures():
        sys.exit(1)
