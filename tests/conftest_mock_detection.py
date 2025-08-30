"""
Pytest plugin for detecting MagicMock file contamination at the test level.

This plugin hooks into pytest to detect which specific tests are creating
MagicMock file artifacts in the filesystem. It can be enabled with:

    pytest --track-mock-files

Or set the environment variable:

    PYTEST_TRACK_MOCK_FILES=1 pytest

To fail tests that create mock files:

    pytest --track-mock-files --fail-on-mock-files
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item
from detect_mock_files import TestMockFileTracker


def pytest_addoption(parser: Parser) -> None:
    """Add command-line options for mock file tracking."""
    parser.addoption(
        "--track-mock-files",
        action="store_true",
        default=False,
        help="Track creation of MagicMock file artifacts during tests",
    )
    parser.addoption(
        "--fail-on-mock-files",
        action="store_true",
        default=False,
        help="Fail tests that create MagicMock file artifacts",
    )
    parser.addoption(
        "--mock-file-root",
        default=".",
        help="Root directory to scan for mock files (default: current directory)",
    )


def pytest_configure(config: Config) -> None:
    """Configure the mock file tracking plugin."""
    # Enable tracking if environment variable is set
    if os.environ.get("PYTEST_TRACK_MOCK_FILES", "").lower() in ("1", "true", "yes"):
        config.option.track_mock_files = True

    if config.option.track_mock_files:
        # Create and attach the tracker to the config
        root_path = config.option.mock_file_root
        config._mock_file_tracker = TestMockFileTracker(root_path)

        # Add custom markers
        config.addinivalue_line(
            "markers",
            "allow_mock_files: mark test as allowed to create mock file artifacts",
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Called at the start of the test session."""
    if hasattr(session.config, "_mock_file_tracker"):
        tracker: TestMockFileTracker = session.config._mock_file_tracker
        print("\n🔍 Mock File Detection: Taking baseline snapshot...")
        tracker.snapshot_baseline()


@pytest.fixture(autouse=True)
def _mock_file_detector(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """
    Fixture that automatically checks for mock files after each test.

    This fixture runs for every test when --track-mock-files is enabled.
    """
    config = request.config

    # Skip if tracking is not enabled
    if not config.option.track_mock_files:
        yield
        return

    # Skip if test is marked to allow mock files
    if request.node.get_closest_marker("allow_mock_files"):
        yield
        return

    tracker: TestMockFileTracker = config._mock_file_tracker
    test_name = request.node.nodeid

    # Take snapshot before test
    before_files = tracker.detector.get_mock_files()

    # Run the test
    yield

    # Check for new files after test
    after_files = tracker.detector.get_mock_files()
    new_files = after_files - before_files

    if new_files:
        # Record the contamination
        tracker.test_results[test_name] = {
            "new_files": new_files,
            "analysis": [tracker.detector.analyze_mock_file(f) for f in new_files],
        }

        # Build error message
        msg_lines = [
            f"Test created {len(new_files)} mock file artifact(s):",
        ]
        for file in sorted(new_files):
            msg_lines.append(f"  - {file}")

        msg_lines.extend(
            [
                "",
                "This usually happens when:",
                "  1. A MagicMock object is used as a file path",
                "  2. Mock.spec or Mock.spec_set is not properly configured",
                "  3. A mock's string representation is used in file operations",
                "",
                "To fix this:",
                "  1. Always use spec_set=True when creating mocks",
                "  2. Never use mock objects directly as file paths",
                "  3. Use proper string values for file operations",
                "",
                "To allow this test to create mock files, add:",
                "  @pytest.mark.allow_mock_files",
            ]
        )

        error_msg = "\n".join(msg_lines)

        # Fail the test if configured to do so
        if config.option.fail_on_mock_files:
            pytest.fail(error_msg)
        else:
            # Just warn about it
            pytest.warns(UserWarning, match=error_msg)


def pytest_terminal_summary(terminalreporter, exitstatus, config: Config) -> None:
    """Print summary of mock file detection at the end of test session."""
    if not config.option.track_mock_files:
        return

    tracker: TestMockFileTracker = config._mock_file_tracker

    if not tracker.test_results:
        terminalreporter.section("Mock File Detection")
        terminalreporter.write_line("✅ No mock files created during tests")
        return

    # Print detailed report
    terminalreporter.section("Mock File Detection - CONTAMINATION FOUND", sep="=")

    total_files = sum(len(data["new_files"]) for data in tracker.test_results.values())
    terminalreporter.write_line(
        f"❌ {len(tracker.test_results)} test(s) created {total_files} mock file(s):\n"
    )

    # Sort by test name for consistent output
    for test_name in sorted(tracker.test_results.keys()):
        data = tracker.test_results[test_name]
        terminalreporter.write_line(f"  📍 {test_name}")
        for file in sorted(data["new_files"]):
            # Show relative path if possible
            try:
                rel_path = file.relative_to(Path.cwd())
                terminalreporter.write_line(f"      - {rel_path}")
            except ValueError:
                terminalreporter.write_line(f"      - {file}")

    terminalreporter.write_line("")
    terminalreporter.write_line("To investigate specific tests, run:")
    terminalreporter.write_line(
        "  pytest --track-mock-files --fail-on-mock-files -k 'test_name'"
    )
    terminalreporter.write_line("")
    terminalreporter.write_line("To clean up mock files, run:")
    terminalreporter.write_line("  python tests/detect_mock_files.py --clean")


class MockFilePlugin:
    """Pytest plugin class for mock file detection."""

    def __init__(self, config: Config):
        self.config = config
        self.tracker = TestMockFileTracker(config.option.mock_file_root)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item: Item, nextitem: Item | None):
        """Hook that runs around each test item."""
        # Only track if enabled
        if not self.config.option.track_mock_files:
            yield
            return

        # Check if test should be skipped
        if item.get_closest_marker("allow_mock_files"):
            yield
            return

        # Take snapshot before test
        before_files = self.tracker.detector.get_mock_files()

        # Run the test
        outcome = yield

        # Check for new files after test
        after_files = self.tracker.detector.get_mock_files()
        new_files = after_files - before_files

        if new_files:
            test_name = item.nodeid
            self.tracker.test_results[test_name] = {
                "new_files": new_files,
                "analysis": [
                    self.tracker.detector.analyze_mock_file(f) for f in new_files
                ],
            }

            # Report immediately
            print(f"\n⚠️  Test '{test_name}' created {len(new_files)} mock file(s)")
            for file in sorted(new_files):
                print(f"     - {file}")


def pytest_plugin(config: Config) -> MockFilePlugin | None:
    """Create plugin instance if tracking is enabled."""
    if config.option.track_mock_files:
        return MockFilePlugin(config)
    return None
