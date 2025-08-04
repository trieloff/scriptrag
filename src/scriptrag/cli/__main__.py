"""Main entry point for scriptrag CLI when run as a module."""

from scriptrag.cli.main import main

if __name__ == "__main__":  # pragma: no cover
    # This block only runs when executed directly as a script.
    # The main() function is tested separately via test_cli_main_block.py
    main()
