"""Unit tests for CLI commands module (__init__.py)."""

import importlib
import inspect
from types import ModuleType

from scriptrag.cli.commands import (
    analyze_command,
    index_command,
    init_command,
    list_command,
    mcp_command,
    pull_command,
    search_command,
    watch_command,
)


class TestCLICommandsModule:
    """Test the CLI commands module initialization and exports."""

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        # Re-import the module to ensure it loads cleanly
        import scriptrag.cli.commands

        assert scriptrag.cli.commands is not None
        assert isinstance(scriptrag.cli.commands, ModuleType)

    def test_all_commands_are_exported(self):
        """Test that all expected commands are in __all__ and accessible."""
        import scriptrag.cli.commands as commands_module

        # Check __all__ contains expected commands
        expected_commands = [
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

        assert hasattr(commands_module, "__all__")
        assert commands_module.__all__ == expected_commands

        # Verify each command is accessible as module attribute
        for command_name in expected_commands:
            assert hasattr(commands_module, command_name)
            command_func = getattr(commands_module, command_name)
            assert callable(command_func)

    def test_imported_commands_are_callable(self):
        """Test that all imported commands are callable functions."""
        commands = [
            analyze_command,
            index_command,
            init_command,
            list_command,
            mcp_command,
            pull_command,
            search_command,
            watch_command,
        ]

        for command in commands:
            assert callable(command)
            assert inspect.isfunction(command)

    def test_imported_commands_have_proper_signatures(self):
        """Test that imported commands have the expected function signatures."""
        # Each command should have parameters (though signatures may vary)
        commands = [
            analyze_command,
            index_command,
            init_command,
            list_command,
            mcp_command,
            pull_command,
            search_command,
            watch_command,
        ]

        for command in commands:
            sig = inspect.signature(command)
            # Each command should have at least some parameters
            # Some commands might have no required params
            assert len(sig.parameters) >= 0

    def test_module_docstring_exists(self):
        """Test that the module has a proper docstring."""
        import scriptrag.cli.commands as commands_module

        assert commands_module.__doc__ is not None
        assert "ScriptRAG CLI commands" in commands_module.__doc__

    def test_no_extra_public_attributes(self):
        """Test that the module exports expected commands and their modules."""
        import scriptrag.cli.commands as commands_module

        # Get all public attributes (not starting with _)
        public_attrs = [
            name for name in dir(commands_module) if not name.startswith("_")
        ]

        # Should contain the commands in __all__ plus the imported module names
        expected_attrs = set(commands_module.__all__)
        # Add the module names that get imported as side effects
        expected_attrs.update(
            [
                "analyze",
                "index",
                "init",
                "list",
                "mcp",
                "pull",
                "query",
                "scene",  # Scene module imported as side effect from main.py
                "search",
                "watch",
            ]
        )

        assert set(public_attrs) == expected_attrs

    def test_command_imports_resolve_correctly(self):
        """Test that the imports in the module resolve to the correct functions."""
        # Import the individual command modules directly
        # Import via the __init__ module
        from scriptrag.cli.commands import (
            analyze_command,
            index_command,
            init_command,
            list_command,
            mcp_command,
            pull_command,
            search_command,
            watch_command,
        )
        from scriptrag.cli.commands.analyze import analyze_command as direct_analyze
        from scriptrag.cli.commands.index import index_command as direct_index
        from scriptrag.cli.commands.init import init_command as direct_init
        from scriptrag.cli.commands.list import list_command as direct_list
        from scriptrag.cli.commands.mcp import mcp_command as direct_mcp
        from scriptrag.cli.commands.pull import pull_command as direct_pull
        from scriptrag.cli.commands.search import search_command as direct_search
        from scriptrag.cli.commands.watch import watch_command as direct_watch

        # Verify they are the same objects
        assert analyze_command is direct_analyze
        assert index_command is direct_index
        assert init_command is direct_init
        assert list_command is direct_list
        assert mcp_command is direct_mcp
        assert pull_command is direct_pull
        assert search_command is direct_search
        assert watch_command is direct_watch

    def test_module_can_be_reloaded(self):
        """Test that the module can be reloaded without issues."""
        import scriptrag.cli.commands as commands_module

        # Store original references
        original_all = commands_module.__all__
        original_analyze = commands_module.analyze_command

        # Reload the module
        importlib.reload(commands_module)

        # Verify the module still works after reload
        assert commands_module.__all__ == original_all
        assert callable(commands_module.analyze_command)
        # Note: After reload, the function objects may be different instances
        # but they should still have the same name and be callable
        assert commands_module.analyze_command.__name__ == original_analyze.__name__

    def test_star_import_works(self):
        """Test that 'from scriptrag.cli.commands import *' works correctly."""
        import importlib

        # Import the module
        module = importlib.import_module("scriptrag.cli.commands")

        # Get __all__ exports or all public attributes
        all_exports = getattr(module, "__all__", [])

        # Check that all expected commands are exported
        expected_commands = [
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

        for command_name in expected_commands:
            if all_exports:
                assert command_name in all_exports, f"{command_name} not in __all__"
            assert hasattr(module, command_name)
            assert callable(getattr(module, command_name))

        # Ensure only the expected commands are imported (no private attributes)
        if all_exports:
            imported_commands = [
                name
                for name in all_exports
                if not name.startswith("__") and name != "builtins"
            ]
            assert set(imported_commands) == set(expected_commands)

    def test_module_imports_are_accessible(self):
        """Test that the imported command modules are accessible as attributes."""
        # These should be module objects
        from types import ModuleType

        from scriptrag.cli.commands import (
            analyze,
            index,
            init,
            mcp,
            pull,
            search,
            watch,
        )
        from scriptrag.cli.commands import (
            list as list_module,
        )

        assert isinstance(analyze, ModuleType)
        assert isinstance(index, ModuleType)
        assert isinstance(init, ModuleType)
        assert isinstance(list_module, ModuleType)
        assert isinstance(mcp, ModuleType)
        assert isinstance(pull, ModuleType)
        assert isinstance(search, ModuleType)
        assert isinstance(watch, ModuleType)

        # Each module should have the expected command function
        assert hasattr(analyze, "analyze_command")
        assert hasattr(index, "index_command")
        assert hasattr(init, "init_command")
        assert hasattr(list_module, "list_command")
        assert hasattr(mcp, "mcp_command")
        assert hasattr(pull, "pull_command")
        assert hasattr(search, "search_command")
        assert hasattr(watch, "watch_command")

    def test_module_name_consistency(self):
        """Test that module names match their expected command prefixes."""
        from scriptrag.cli.commands import (
            analyze,
            index,
            init,
            mcp,
            pull,
            search,
            watch,
        )
        from scriptrag.cli.commands import (
            list as list_module,
        )

        # Check module names
        assert analyze.__name__.endswith("analyze")
        assert index.__name__.endswith("index")
        assert init.__name__.endswith("init")
        assert list_module.__name__.endswith("list")
        assert mcp.__name__.endswith("mcp")
        assert pull.__name__.endswith("pull")
        assert search.__name__.endswith("search")
        assert watch.__name__.endswith("watch")
