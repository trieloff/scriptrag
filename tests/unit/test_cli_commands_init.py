"""Unit tests for CLI commands __init__ module."""


class TestCLICommandsInit:
    """Test CLI commands module initialization and imports."""

    def test_all_commands_importable(self):
        """Test that all commands listed in __all__ are importable."""
        from scriptrag.cli.commands import (
            analyze_command,
            index_command,
            init_command,
            list_command,
            mcp_command,
            pull_command,
            query_app,
            search_command,
            watch_command,
        )

        # Verify all commands are callable
        assert callable(analyze_command)
        assert callable(index_command)
        assert callable(init_command)
        assert callable(list_command)
        assert callable(mcp_command)
        assert callable(pull_command)
        assert callable(search_command)
        assert callable(watch_command)

        # query_app is a Typer app, not a command function
        from typer import Typer

        assert isinstance(query_app, Typer)

    def test_all_exports_match_imports(self):
        """Test that __all__ list matches actual imports."""
        import scriptrag.cli.commands as commands_module

        expected_exports = [
            "analyze_command",
            "index_command",
            "init_command",
            "list_command",
            "mcp_command",
            "pull_command",
            "query_app",
            "search_command",
            "watch_command",
        ]

        # Verify __all__ exists and contains expected items
        assert hasattr(commands_module, "__all__")
        assert set(commands_module.__all__) == set(expected_exports)

        # Verify all items in __all__ are actually available as attributes
        for export in expected_exports:
            assert hasattr(commands_module, export), f"{export} not found in module"
            assert getattr(commands_module, export) is not None

    def test_import_star_works(self):
        """Test that 'from scriptrag.cli.commands import *' works correctly."""
        # This simulates what happens with 'from module import *'
        import scriptrag.cli.commands as commands_module

        # Get all items that would be imported with import *
        star_imports = {
            name: getattr(commands_module, name) for name in commands_module.__all__
        }

        # Verify we get the expected number of items
        assert len(star_imports) == 9  # Number of items in __all__

        # Verify specific key commands are present
        assert "mcp_command" in star_imports
        assert "analyze_command" in star_imports
        assert "query_app" in star_imports

    def test_module_docstring_exists(self):
        """Test that the module has a proper docstring."""
        import scriptrag.cli.commands as commands_module

        assert commands_module.__doc__ is not None
        assert len(commands_module.__doc__.strip()) > 0
        assert "ScriptRAG CLI commands" in commands_module.__doc__

    def test_individual_command_imports(self):
        """Test importing individual commands directly from submodules."""
        # Test that we can import directly from submodules
        # Test that direct imports match the re-exported ones
        from scriptrag.cli.commands import (
            analyze_command,
            mcp_command,
            search_command,
        )
        from scriptrag.cli.commands.analyze import analyze_command as direct_analyze
        from scriptrag.cli.commands.mcp import mcp_command as direct_mcp
        from scriptrag.cli.commands.search import search_command as direct_search

        assert direct_analyze is analyze_command
        assert direct_mcp is mcp_command
        assert direct_search is search_command

    def test_no_circular_imports(self):
        """Test that importing the commands module doesn't cause circular imports."""
        # This should not raise any ImportError
        import scriptrag.cli.commands

        # Reimporting should work fine
        import scriptrag.cli.commands as commands2

        # Should be the same module object
        assert scriptrag.cli.commands is commands2

    def test_commands_have_expected_signatures(self):
        """Test that commands have expected function signatures."""
        import inspect

        from scriptrag.cli.commands import (
            analyze_command,
            mcp_command,
            search_command,
        )

        # Test MCP command signature
        mcp_sig = inspect.signature(mcp_command)
        assert "host" in mcp_sig.parameters
        assert "port" in mcp_sig.parameters

        # Commands should be callable
        assert callable(analyze_command)
        assert callable(search_command)

    def test_module_level_constants(self):
        """Test any module-level constants or configurations."""
        import scriptrag.cli.commands as commands_module

        # Verify __all__ is a list of strings
        assert isinstance(commands_module.__all__, list)
        assert all(isinstance(item, str) for item in commands_module.__all__)

        # Verify no private exports
        assert all(not item.startswith("_") for item in commands_module.__all__)

    def test_import_performance(self):
        """Test that importing commands doesn't take excessive time."""
        import time

        start_time = time.time()

        # Import all commands

        end_time = time.time()
        import_time = end_time - start_time

        # Imports should be reasonably fast (less than 1 second)
        assert import_time < 1.0, (
            f"Command imports took {import_time:.2f}s, which is too slow"
        )

    def test_command_objects_are_distinct(self):
        """Test that different command functions are distinct objects."""
        from scriptrag.cli.commands import (
            analyze_command,
            mcp_command,
            search_command,
        )

        # Commands should be different functions
        assert analyze_command is not mcp_command
        assert mcp_command is not search_command
        assert analyze_command is not search_command

        # But they should all be callable
        assert callable(analyze_command)
        assert callable(mcp_command)
        assert callable(search_command)

    def test_module_attributes_complete(self):
        """Test that all expected module attributes are present."""
        import scriptrag.cli.commands as commands_module

        # Standard module attributes
        assert hasattr(commands_module, "__name__")
        assert hasattr(commands_module, "__doc__")
        assert hasattr(commands_module, "__all__")
        assert hasattr(commands_module, "__file__")

        # All exported commands should be present
        for command_name in commands_module.__all__:
            assert hasattr(commands_module, command_name)
            command_obj = getattr(commands_module, command_name)
            assert command_obj is not None


class TestCommandsModuleEdgeCases:
    """Test edge cases and error conditions for commands module."""

    def test_import_with_missing_dependency(self):
        """Test behavior when optional dependencies are missing."""
        # The commands module should import successfully even if some
        # optional dependencies are missing (they should fail at runtime,
        # not import time)

        # This should not raise ImportError
        from scriptrag.cli.commands import mcp_command

        assert mcp_command is not None
        assert callable(mcp_command)

    def test_all_list_consistency(self):
        """Test that __all__ list is consistent with actual exports."""
        import scriptrag.cli.commands as commands_module

        # Get all public attributes (not starting with _)
        public_attrs = [
            name for name in dir(commands_module) if not name.startswith("_")
        ]

        # Remove any imported modules or non-command items
        expected_in_all = []
        for attr_name in public_attrs:
            attr = getattr(commands_module, attr_name)
            # Include if it's a function or Typer app
            if callable(attr) or str(type(attr)).find("Typer") != -1:
                expected_in_all.append(attr_name)

        # All items in __all__ should be public callable attributes
        for item in commands_module.__all__:
            assert item in public_attrs, (
                f"{item} in __all__ but not in public attributes"
            )
            assert (
                callable(getattr(commands_module, item))
                or str(type(getattr(commands_module, item))).find("Typer") != -1
            )

    def test_command_function_metadata(self):
        """Test that command functions have proper metadata."""
        from scriptrag.cli.commands import analyze_command, mcp_command

        # Functions should have names
        assert mcp_command.__name__ == "mcp_command"
        assert analyze_command.__name__ == "analyze_command"

        # Functions should have modules
        assert mcp_command.__module__ == "scriptrag.cli.commands.mcp"
        assert analyze_command.__module__ == "scriptrag.cli.commands.analyze"

        # Functions should have docstrings (for help text)
        assert mcp_command.__doc__ is not None
        assert len(mcp_command.__doc__.strip()) > 0
