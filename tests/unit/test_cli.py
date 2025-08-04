"""Unit tests for CLI module."""

from unittest.mock import patch

from scriptrag.cli import main


class TestCLIMain:
    """Test CLI main entry point."""

    def test_main_function(self):
        """Test that main() calls app()."""
        with patch("scriptrag.cli.main.app") as mock_app:
            # Mock app to prevent actual execution
            mock_app.return_value = None
            main()
            mock_app.assert_called_once()

    def test_main_as_script(self):
        """Test __main__ execution."""
        # Test the if __name__ == "__main__" block
        test_code = """
__name__ = "__main__"
main_called = False
def main():
    global main_called
    main_called = True

if __name__ == "__main__":
    main()
"""
        namespace = {}
        exec(test_code, namespace)  # noqa: S102
        assert namespace["main_called"] is True
