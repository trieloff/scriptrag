#!/usr/bin/env python3
"""
Enhanced MagicMock file detection for tracing contamination to specific tests.

This script provides utilities to detect and trace MagicMock file artifacts
created during test runs, helping identify which specific test cases are
responsible for filesystem contamination.
"""

import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar


class MockFileDetector:
    """Detect and analyze MagicMock file artifacts in the filesystem."""

    # Patterns that indicate a file created by a MagicMock object
    MOCK_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r".*Mock.*name=.*"),  # Files with Mock and name= in path
        re.compile(r"<Mock.*"),  # Files starting with <Mock
        re.compile(r".*<Mock.*"),  # Files containing <Mock
        re.compile(r".*id='.*'.*"),  # Files with id='...' pattern
        re.compile(r".*MagicMock.*"),  # Files containing MagicMock
        re.compile(r".*spec=.*"),  # Files with spec= in name
        re.compile(r".*\bid=0x[0-9a-f]+\b.*"),  # Files with hex id pattern
    ]

    # Directories to exclude from scanning
    EXCLUDE_DIRS: ClassVar[set[str]] = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        ".tox",
        "node_modules",
        ".coverage",
        ".mypy_cache",
        ".ruff_cache",
    }

    def __init__(self, root_path: str = "."):
        """Initialize detector with root path to scan."""
        self.root_path = Path(root_path).resolve()

    def is_mock_file(self, path: Path) -> bool:
        """Check if a file path appears to be created by a MagicMock."""
        path_str = str(path)
        return any(pattern.match(path_str) for pattern in self.MOCK_PATTERNS)

    def scan_directory(self) -> Iterator[Path]:
        """Scan directory tree for mock file artifacts."""
        for root, dirs, files in os.walk(self.root_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

            root_path = Path(root)

            # Check directory names themselves
            for dir_name in dirs:
                dir_path = root_path / dir_name
                if self.is_mock_file(dir_path):
                    yield dir_path

            # Check file names
            for file_name in files:
                file_path = root_path / file_name
                if self.is_mock_file(file_path):
                    yield file_path

    def get_mock_files(self) -> set[Path]:
        """Get all mock files in the directory tree."""
        return set(self.scan_directory())

    def analyze_mock_file(self, path: Path) -> dict:
        """Analyze a mock file to extract information about its creation."""
        analysis = {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else None,
            "is_dir": path.is_dir() if path.exists() else None,
            "size": path.stat().st_size if path.exists() and path.is_file() else None,
            "patterns_matched": [],
        }

        path_str = str(path)
        for pattern in self.MOCK_PATTERNS:
            if pattern.match(path_str):
                analysis["patterns_matched"].append(pattern.pattern)

        # Try to extract mock details from the filename
        if "name=" in path_str:
            match = re.search(r"name='([^']*)'", path_str)
            if match:
                analysis["mock_name"] = match.group(1)

        if "id=" in path_str:
            match = re.search(r"id='([^']*)'", path_str)
            if match:
                analysis["mock_id"] = match.group(1)

        return analysis


class TestMockFileTracker:
    """Track mock files created during test execution."""

    def __init__(self, root_path: str = "."):
        """Initialize tracker."""
        self.detector = MockFileDetector(root_path)
        self.baseline_files: set[Path] = set()
        self.test_results: dict = {}

    def snapshot_baseline(self) -> None:
        """Take a snapshot of existing mock files before tests."""
        self.baseline_files = self.detector.get_mock_files()
        if self.baseline_files:
            print(
                f"⚠️  Found {len(self.baseline_files)} existing mock files before tests"
            )
            for file in sorted(self.baseline_files):
                print(f"   - {file}")

    def check_after_test(self, test_name: str) -> tuple[bool, set[Path]]:
        """
        Check for new mock files after a specific test.

        Returns:
            Tuple of (has_new_files, set_of_new_files)
        """
        current_files = self.detector.get_mock_files()
        new_files = current_files - self.baseline_files

        if new_files:
            self.test_results[test_name] = {
                "new_files": new_files,
                "analysis": [self.detector.analyze_mock_file(f) for f in new_files],
            }
            return True, new_files

        return False, set()

    def report_results(self) -> None:
        """Print a detailed report of test results."""
        if not self.test_results:
            print("✅ No mock files created during tests")
            return

        print("\n" + "=" * 80)
        print("❌ MOCK FILE CONTAMINATION DETECTED")
        print("=" * 80)

        for test_name, data in self.test_results.items():
            print(f"\n🔍 Test: {test_name}")
            print(f"   Created {len(data['new_files'])} mock file(s):")

            for analysis in data["analysis"]:
                print(f"\n   📁 {analysis['path']}")
                file_type = (
                    "File"
                    if analysis["is_file"]
                    else "Directory"
                    if analysis["is_dir"]
                    else "Unknown"
                )
                print(f"      Type: {file_type}")
                if analysis.get("size") is not None:
                    print(f"      Size: {analysis['size']} bytes")
                if analysis.get("mock_name"):
                    print(f"      Mock Name: {analysis['mock_name']}")
                if analysis.get("mock_id"):
                    print(f"      Mock ID: {analysis['mock_id']}")
                print(f"      Patterns: {', '.join(analysis['patterns_matched'])}")

    def cleanup_mock_files(self) -> None:
        """Remove all detected mock files."""
        all_mock_files = self.detector.get_mock_files()
        if not all_mock_files:
            return

        print(f"\n🧹 Cleaning up {len(all_mock_files)} mock file(s)...")
        for file in all_mock_files:
            try:
                if file.is_dir():
                    file.rmdir()
                else:
                    file.unlink()
                print(f"   ✓ Removed: {file}")
            except Exception as e:
                print(f"   ✗ Failed to remove {file}: {e}")


def main():
    """Command-line interface for mock file detection."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect and analyze MagicMock file artifacts"
    )
    parser.add_argument(
        "--path", default=".", help="Root path to scan (default: current directory)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove detected mock files after reporting",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Only show summary, not individual files"
    )

    args = parser.parse_args()

    detector = MockFileDetector(args.path)
    mock_files = detector.get_mock_files()

    if not mock_files:
        print("✅ No mock files detected")
        return 0

    print(f"❌ Found {len(mock_files)} mock file(s):")

    if not args.quiet:
        for file in sorted(mock_files):
            analysis = detector.analyze_mock_file(file)
            print(f"\n📁 {file}")
            if analysis.get("mock_name"):
                print(f"   Mock Name: {analysis['mock_name']}")
            if analysis.get("mock_id"):
                print(f"   Mock ID: {analysis['mock_id']}")

    if args.clean:
        print("\n🧹 Cleaning up mock files...")
        for file in mock_files:
            try:
                if file.is_dir():
                    file.rmdir()
                else:
                    file.unlink()
                print(f"   ✓ Removed: {file}")
            except Exception as e:
                print(f"   ✗ Failed to remove {file}: {e}")

    return 1 if mock_files else 0


if __name__ == "__main__":
    sys.exit(main())
