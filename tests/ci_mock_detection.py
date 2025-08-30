#!/usr/bin/env python3
"""
CI-friendly mock detection script.

This script is designed to be used in CI environments to detect
and report mock file contamination with proper exit codes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from detect_mock_files import MockFileDetector, TestMockFileTracker


def run_tests_with_tracking(test_args: list[str] | None = None) -> dict[str, Any]:
    """
    Run pytest with mock file tracking and return results.

    Args:
        test_args: Additional arguments to pass to pytest

    Returns:
        Dictionary with test results and mock file information
    """
    tracker = TestMockFileTracker()
    results = {
        "baseline_files": [],
        "tests_with_mock_files": {},
        "total_mock_files": 0,
        "test_exit_code": 0,
    }

    # Take baseline snapshot
    tracker.snapshot_baseline()
    results["baseline_files"] = [str(f) for f in tracker.baseline_files]

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    if test_args:
        cmd.extend(test_args)

    # Set environment variable to enable tracking
    env = os.environ.copy()
    env["PYTEST_TRACK_MOCK_FILES"] = "1"

    # Run tests
    print("🧪 Running tests with mock file tracking...")
    print(f"Command: {' '.join(cmd)}")
    print()

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)  # noqa: S603

    results["test_exit_code"] = proc.returncode

    # Check for new mock files after all tests
    detector = MockFileDetector()
    final_files = detector.get_mock_files()
    new_files = final_files - set(tracker.baseline_files)

    if new_files:
        results["tests_with_mock_files"]["unknown"] = [str(f) for f in new_files]
        results["total_mock_files"] = len(new_files)

    return results


def generate_github_annotation(results: dict[str, Any]) -> None:
    """Generate GitHub Actions annotations for mock file issues."""
    if not results["tests_with_mock_files"]:
        return

    for test_name, files in results["tests_with_mock_files"].items():
        for file_path in files:
            print(f"::error file={file_path}::Mock file created by test: {test_name}")


def generate_junit_report(
    results: dict[str, Any], output_file: str = "mock-detection-report.xml"
) -> None:
    """Generate JUnit XML report for CI systems."""
    from xml.etree import ElementTree as ET

    testsuites = ET.Element("testsuites")
    testsuite = ET.SubElement(
        testsuites,
        "testsuite",
        name="Mock File Detection",
        tests="1",
        failures=str(1 if results["total_mock_files"] > 0 else 0),
    )

    testcase = ET.SubElement(
        testsuite,
        "testcase",
        classname="MockFileDetection",
        name="check_for_mock_files",
    )

    if results["total_mock_files"] > 0:
        failure = ET.SubElement(
            testcase,
            "failure",
            message=f"Found {results['total_mock_files']} mock file(s)",
        )
        failure.text = json.dumps(results["tests_with_mock_files"], indent=2)

    tree = ET.ElementTree(testsuites)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"📄 JUnit report written to {output_file}")


def main():
    """Main entry point for CI mock detection."""
    import argparse

    parser = argparse.ArgumentParser(description="CI mock file detection")
    parser.add_argument(
        "--junit", help="Generate JUnit XML report", metavar="FILE", default=None
    )
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help="Generate GitHub Actions annotations",
    )
    parser.add_argument(
        "--fail-on-baseline",
        action="store_true",
        help="Fail if baseline contains mock files",
    )
    parser.add_argument(
        "--test-args", nargs=argparse.REMAINDER, help="Arguments to pass to pytest"
    )

    args = parser.parse_args()

    # Quick check for existing mock files
    detector = MockFileDetector()
    existing_files = detector.get_mock_files()

    if existing_files:
        print(f"⚠️  Found {len(existing_files)} existing mock file(s) before tests:")
        for file in sorted(existing_files):
            try:
                rel_path = file.relative_to(Path.cwd())
                print(f"   - {rel_path}")
            except ValueError:
                print(f"   - {file}")

        if args.fail_on_baseline:
            print("\n❌ Failing due to existing mock files (--fail-on-baseline)")
            return 1
        print("\n⚠️  Continuing with existing mock files...")

    # Run tests with tracking
    results = run_tests_with_tracking(args.test_args)

    # Generate reports if requested
    if args.github_annotations:
        generate_github_annotation(results)

    if args.junit:
        generate_junit_report(results, args.junit)

    # Print summary
    print("\n" + "=" * 80)
    print("Mock File Detection Summary")
    print("=" * 80)

    if results["baseline_files"]:
        baseline_count = len(results["baseline_files"])
        print(f"⚠️  Baseline: {baseline_count} mock file(s) existed before tests")

    if results["tests_with_mock_files"]:
        total_count = results["total_mock_files"]
        print(f"❌ New mock files: {total_count} file(s) created during tests")
        for test_name, files in results["tests_with_mock_files"].items():
            print(f"\n  Test: {test_name}")
            for file_path in files:
                print(f"    - {file_path}")
    else:
        print("✅ No new mock files created during tests")

    print(f"\nTest exit code: {results['test_exit_code']}")

    # Exit with appropriate code
    if results["total_mock_files"] > 0:
        return 2  # Mock files found
    if results["test_exit_code"] != 0:
        return results["test_exit_code"]  # Test failures
    return 0  # All good


if __name__ == "__main__":
    sys.exit(main())
