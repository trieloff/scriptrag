"""Configuration template generator for ScriptRAG."""

from __future__ import annotations

from pathlib import Path


def generate_config_template() -> str:
    """Generate a comprehensive YAML configuration template with comments.

    Returns:
        A string containing the YAML configuration template with helpful comments.
    """
    # Build the config dictionary with all available settings
    config = {
        "# ScriptRAG Configuration File": None,
        "# This file contains all available settings for ScriptRAG": None,
        "# Settings can be overridden by environment variables "
        "prefixed with SCRIPTRAG_": None,
        "# For example: SCRIPTRAG_DATABASE_PATH=/path/to/db.sqlite": None,
        "": None,
        "# Database Configuration": None,
        "database_path": "scriptrag.db",
        "# Path to the SQLite database file (default: ./scriptrag.db)": None,
        "database_timeout": 30.0,
        "# SQLite connection timeout in seconds (default: 30.0)": None,
        "database_foreign_keys": True,
        "# Enable foreign key constraints (default: true)": None,
        "database_journal_mode": "WAL",
        "# SQLite journal mode: DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF "
        "(default: WAL)": None,
        "database_synchronous": "NORMAL",
        "# SQLite synchronous mode: OFF, NORMAL, FULL, EXTRA (default: NORMAL)": None,
        "database_cache_size": -2000,
        "# SQLite cache size (negative = KB, positive = pages) (default: -2000)": None,
        "database_temp_store": "MEMORY",
        "# SQLite temp store location: DEFAULT, FILE, MEMORY (default: MEMORY)": None,
        "\n# Application Settings": None,
        "app_name": "scriptrag",
        "# Application name (default: scriptrag)": None,
        "metadata_scan_size": 10240,
        "# Bytes to read from end of file when scanning for metadata "
        "(0 = entire file) (default: 10240)": None,
        "debug": False,
        "# Enable debug mode (default: false)": None,
        "\n# Logging Configuration": None,
        "log_level": "WARNING",
        "# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: WARNING)": (
            None
        ),
        "log_format": "console",
        "# Log output format: console, json, structured (default: console)": None,
        "# log_file: /path/to/logfile.log": None,
        "# Optional log file path (default: none)": None,
        "log_file_rotation": "1 day",
        "# Log file rotation interval (default: 1 day)": None,
        "log_file_retention": "7 days",
        "# Log file retention period (default: 7 days)": None,
        "\n# Search Settings": None,
        "search_vector_threshold": 10,
        "# Word count threshold for automatic vector search (default: 10)": None,
        "search_vector_similarity_threshold": 0.3,
        "# Minimum similarity score for vector search results (0.0-1.0) "
        "(default: 0.3)": None,
        "search_vector_result_limit_factor": 0.5,
        "# Factor of query limit to use for vector results (0.1-1.0) "
        "(default: 0.5)": None,
        "search_vector_min_results": 5,
        "# Minimum number of vector results to fetch (default: 5)": None,
        "\n# LLM (Language Model) Configuration": None,
        "# Choose one of the following provider configurations:": None,
        "\n# Option 1: Local LLM (e.g., Ollama, LM Studio, llama.cpp)": None,
        "# llm_provider: openai": None,
        "# llm_endpoint: http://localhost:1234/v1": None,
        "# llm_model: llama2": None,
        "# llm_embedding_model: nomic-embed-text": None,
        "# llm_embedding_dimensions: 768": None,
        "\n# Option 2: GitHub Models (requires GitHub token)": None,
        "# llm_provider: github_models": None,
        "# llm_api_key: ${GITHUB_TOKEN}  # Use environment variable": None,
        "# llm_model: gpt-4o": None,
        "# llm_embedding_model: text-embedding-3-small": None,
        "# llm_embedding_dimensions: 1536": None,
        "\n# Option 3: OpenAI API": None,
        "# llm_provider: openai (OpenAI)": None,
        "# llm_endpoint: https://api.openai.com/v1": None,
        "# llm_api_key: ${OPENAI_API_KEY}  # Use environment variable": None,
        "# llm_model: gpt-4": None,
        "# llm_embedding_model: text-embedding-ada-002": None,
        "# llm_embedding_dimensions: 1536 (OpenAI)": None,
        "\n# Option 4: Claude via Claude Code (when available)": None,
        "# llm_provider: claude_code": None,
        "# No additional configuration needed - uses local Claude Code": None,
        "\n# Common LLM Settings": None,
        "llm_temperature": 0.7,
        "# Temperature for completions (0.0-2.0) (default: 0.7)": None,
        "# llm_max_tokens: 2048": None,
        "# Maximum tokens for completions (default: model-specific)": None,
        "llm_force_static_models": False,
        "# Force use of static model lists instead of dynamic discovery "
        "(default: false)": None,
        "llm_model_cache_ttl": 3600,
        "# TTL in seconds for cached model lists (0 to disable) (default: 3600)": None,
        "\n# Bible/Document Embeddings Settings": None,
        "bible_embeddings_path": "embeddings/bible",
        "# Path for storing document chunk embeddings in Git LFS "
        "(default: embeddings/bible)": None,
        "bible_max_file_size": 10485760,
        "# Maximum size for bible/document files in bytes (default: 10MB)": None,
    }

    # Build YAML string with proper formatting and comments
    lines = []
    for key, value in config.items():
        if key.startswith("#"):
            # It's a comment line
            lines.append(key)
        elif key == "":
            # Empty line for spacing
            lines.append("")
        elif key.startswith("\n#"):
            # Comment with preceding newline
            lines.append("")
            lines.append(key[1:])  # Remove the \n
        elif value is None:
            # Skip None values (they were just for comments)
            continue
        else:
            # Regular key-value pair
            if isinstance(value, str) and not value.startswith("${"):
                # Quote strings except environment variable references
                lines.append(f'{key}: "{value}"')
            elif isinstance(value, bool):
                lines.append(f"{key}: {str(value).lower()}")
            else:
                lines.append(f"{key}: {value}")

    return "\n".join(lines)


def write_config_template(output_path: Path, force: bool = False) -> Path:
    """Write the configuration template to a file.

    Args:
        output_path: Path where the config file should be written.
        force: If True, overwrite existing file.

    Returns:
        The path to the written configuration file.

    Raises:
        FileExistsError: If the file exists and force is False.
    """
    # Resolve the output path
    output_path = output_path.resolve()

    # Check if file exists
    if output_path.exists() and not force:
        raise FileExistsError(f"Configuration file already exists: {output_path}")

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate and write the template
    template = generate_config_template()
    output_path.write_text(template, encoding="utf-8")

    return output_path


def get_default_config_path() -> Path:
    """Get the default configuration file path.

    Returns:
        The default path for the ScriptRAG configuration file.

    The default location follows the XDG Base Directory Specification:
    - On Linux/macOS: ~/.config/scriptrag/config.yaml
    - Falls back to: ./scriptrag.yaml in the current directory
    """
    # Try XDG config directory first
    try:
        home_dir = Path.home().resolve()
        config_dir = home_dir / ".config" / "scriptrag"

        # Use config directory if it exists or we can create it
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.yaml"
    except (OSError, PermissionError, RuntimeError):
        # Fall back to current directory on any path resolution issues
        # RuntimeError can occur on some systems when resolving home directory
        try:
            return Path.cwd().resolve() / "scriptrag.yaml"
        except (OSError, RuntimeError):
            # Ultimate fallback - relative path in current directory
            return Path("scriptrag.yaml")
