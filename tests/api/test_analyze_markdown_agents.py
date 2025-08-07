"""Tests for markdown agent loading in analyze API."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.analyze import AnalyzeCommand


@pytest.fixture
def sample_agent_markdown() -> str:
    """Return sample markdown content for an agent."""
    return """---
name: test-agent
property: test_prop
description: A test agent
version: 1.0.0
requires_llm: false
---

# Test Agent

## Output Schema

```json
{
    "type": "object",
    "properties": {
        "result": {"type": "string"}
    }
}
```
"""


class TestAnalyzeCommandMarkdownAgents:
    """Test markdown agent loading in AnalyzeCommand."""

    @pytest.fixture
    def analyze_cmd(self) -> AnalyzeCommand:
        """Create an AnalyzeCommand instance."""
        return AnalyzeCommand()

    def test_load_analyzer_markdown_agent_success(
        self, analyze_cmd: AnalyzeCommand, sample_agent_markdown: str
    ) -> None:
        """Test successful loading of a markdown agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir) / "agents"
            agents_dir.mkdir()
            (agents_dir / "test-agent.md").write_text(sample_agent_markdown)

            with patch("scriptrag.agents.AgentLoader") as mock_loader_class:
                mock_loader = MagicMock()
                mock_analyzer = MagicMock()
                mock_analyzer.name = "test-agent"
                mock_loader.load_agent.return_value = mock_analyzer
                mock_loader_class.return_value = mock_loader

                # Load the markdown agent
                analyze_cmd.load_analyzer("test-agent")

                # Verify the loader was called
                mock_loader_class.assert_called_once()
                mock_loader.load_agent.assert_called_once_with("test-agent")

                # Verify the analyzer was added
                assert mock_analyzer in analyze_cmd.analyzers

    def test_load_analyzer_markdown_agent_import_error(
        self, analyze_cmd: AnalyzeCommand
    ) -> None:
        """Test handling when AgentLoader cannot be imported."""
        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch(
                "scriptrag.agents.AgentLoader",
                side_effect=ImportError("No module named 'scriptrag.agents'"),
            ),
            pytest.raises(ValueError, match="Unknown analyzer: nonexistent"),
        ):
            analyze_cmd.load_analyzer("nonexistent")

    def test_load_analyzer_markdown_agent_value_error(
        self, analyze_cmd: AnalyzeCommand
    ) -> None:
        """Test handling when markdown agent loading fails."""
        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch("scriptrag.agents.AgentLoader") as mock_loader_class,
        ):
            mock_loader = MagicMock()
            mock_loader.load_agent.side_effect = ValueError("Agent not found")
            mock_loader_class.return_value = mock_loader

            with pytest.raises(ValueError, match="Unknown analyzer: missing"):
                analyze_cmd.load_analyzer("missing")

    def test_load_analyzer_builtin_takes_precedence(
        self, analyze_cmd: AnalyzeCommand
    ) -> None:
        """Test that built-in analyzers take precedence over markdown agents."""
        # Create a mock built-in analyzer
        mock_builtin = MagicMock()
        mock_builtin.name = "builtin-test"

        with (
            patch(
                "scriptrag.analyzers.builtin.BUILTIN_ANALYZERS",
                {"builtin-test": lambda: mock_builtin},
            ),
            patch("scriptrag.agents.AgentLoader") as mock_loader_class,
        ):
            # Load the analyzer
            analyze_cmd.load_analyzer("builtin-test")

            # AgentLoader should not be called if built-in exists
            mock_loader_class.assert_not_called()

            # Verify the built-in analyzer was added
            assert mock_builtin in analyze_cmd.analyzers

    def test_load_analyzer_already_loaded(self, analyze_cmd: AnalyzeCommand) -> None:
        """Test that loading an already loaded analyzer is skipped."""
        # Add an analyzer with a specific name
        mock_analyzer = MagicMock()
        mock_analyzer.name = "already-loaded"
        analyze_cmd.analyzers.append(mock_analyzer)

        with patch("scriptrag.agents.AgentLoader") as mock_loader_class:
            # Try to load the same analyzer again
            analyze_cmd.load_analyzer("already-loaded")

            # AgentLoader should not be called
            mock_loader_class.assert_not_called()

            # Should still have only one analyzer
            assert len(analyze_cmd.analyzers) == 1

    def test_load_analyzer_fallback_order(self, analyze_cmd: AnalyzeCommand) -> None:
        """Test the fallback order: built-in -> markdown -> error."""
        # Test case 1: Built-in analyzer found
        with patch(
            "scriptrag.analyzers.builtin.BUILTIN_ANALYZERS",
            {"test1": lambda: MagicMock(name="test1")},
        ):
            analyze_cmd.load_analyzer("test1")
            assert len(analyze_cmd.analyzers) == 1

        # Clear analyzers
        analyze_cmd.analyzers = []

        # Test case 2: Built-in not found, markdown agent found
        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch("scriptrag.agents.AgentLoader") as mock_loader_class,
        ):
            mock_loader = MagicMock()
            mock_analyzer = MagicMock(name="test2")
            mock_loader.load_agent.return_value = mock_analyzer
            mock_loader_class.return_value = mock_loader

            analyze_cmd.load_analyzer("test2")
            assert mock_analyzer in analyze_cmd.analyzers

        # Clear analyzers
        analyze_cmd.analyzers = []

        # Test case 3: Neither found
        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch("scriptrag.agents.AgentLoader") as mock_loader_class,
        ):
            mock_loader = MagicMock()
            mock_loader.load_agent.side_effect = ValueError("Not found")
            mock_loader_class.return_value = mock_loader

            with pytest.raises(ValueError, match="Unknown analyzer: test3"):
                analyze_cmd.load_analyzer("test3")
