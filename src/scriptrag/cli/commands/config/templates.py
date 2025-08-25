"""Configuration template generation functions."""

from scriptrag.config.template import generate_config_template


def get_template_config(env: str | None) -> str:
    """Get configuration template for the specified environment.

    Args:
        env: Environment name (dev, prod, ci) or None for default

    Returns:
        Configuration template as a string
    """
    if env == "dev":
        return _generate_dev_config()
    if env == "prod":
        return _generate_prod_config()
    if env == "ci":
        return _generate_ci_config()
    # Use existing template generator for default
    return generate_config_template()


def _generate_dev_config() -> str:
    """Generate development environment configuration."""
    return """# ScriptRAG Development Configuration
# Optimized for local development and testing
#
# SECURITY WARNING: Never replace ${VAR_NAME} with actual API keys!
# Use environment variables or .env files for sensitive data

# Database - Use local SQLite with debugging enabled
database_path: "./dev/scriptrag.db"
database_timeout: 60.0
database_wal_mode: true
database_foreign_keys: true
database_journal_mode: "WAL"
database_synchronous: "NORMAL"
database_cache_size: -4000  # 4MB cache for development

# Application
app_name: "scriptrag-dev"
metadata_scan_size: 0  # Read entire file in dev
skip_boneyard_filter: true  # Skip filtering for testing
debug: true

# Logging - Verbose for development
log_level: "DEBUG"
log_format: "console"
log_file: "./dev/logs/scriptrag.log"
log_file_rotation: "1 hour"
log_file_retention: "1 day"

# Search - Relaxed thresholds for testing
search_vector_threshold: 5
search_vector_similarity_threshold: 0.2
search_vector_result_limit_factor: 0.7
search_vector_min_results: 10
search_thread_timeout: 600.0  # 10 minutes for debugging

# LLM - Local development with Ollama
llm_provider: "openai"
llm_endpoint: "http://localhost:11434/v1"
llm_model: "llama2"
llm_embedding_model: "nomic-embed-text"
llm_embedding_dimensions: 768
llm_temperature: 0.9
llm_max_tokens: 4096
llm_force_static_models: true  # Use static models in dev
llm_model_cache_ttl: 60  # Short cache for development

# Bible/Embeddings
bible_embeddings_path: "./dev/embeddings/bible"
bible_max_file_size: 52428800  # 50MB for testing large files
bible_llm_context_limit: 4000  # Larger context for testing
"""


def _generate_prod_config() -> str:
    """Generate production environment configuration."""
    return """# ScriptRAG Production Configuration
# Optimized for production deployment
#
# SECURITY WARNING: Never replace ${VAR_NAME} with actual API keys!
# Use environment variables or secrets management for sensitive data

# Database - Production settings with high performance
database_path: "/var/lib/scriptrag/scriptrag.db"
database_timeout: 30.0
database_wal_mode: true
database_foreign_keys: true
database_journal_mode: "WAL"
database_synchronous: "FULL"  # Data safety in production
database_cache_size: -64000  # 64MB cache
database_temp_store: "MEMORY"

# Application
app_name: "scriptrag"
metadata_scan_size: 10240
skip_boneyard_filter: false
debug: false

# Logging - Production logging
log_level: "WARNING"
log_format: "json"  # Structured logs for monitoring
log_file: "/var/log/scriptrag/scriptrag.log"
log_file_rotation: "1 day"
log_file_retention: "30 days"

# Search - Optimized for production
search_vector_threshold: 10
search_vector_similarity_threshold: 0.3
search_vector_result_limit_factor: 0.5
search_vector_min_results: 5
search_thread_timeout: 300.0

# LLM - Production API configuration
# IMPORTANT: Set SCRIPTRAG_LLM_API_KEY environment variable
llm_provider: "openai"
llm_endpoint: "https://api.openai.com/v1"
llm_api_key: "${OPENAI_API_KEY}"  # From environment variable
llm_model: "gpt-4"
llm_embedding_model: "text-embedding-3-small"
llm_embedding_dimensions: 1536
llm_temperature: 0.7
llm_max_tokens: 2048
llm_force_static_models: false
llm_model_cache_ttl: 3600

# Bible/Embeddings
bible_embeddings_path: "/var/lib/scriptrag/embeddings/bible"
bible_max_file_size: 10485760  # 10MB limit
bible_llm_context_limit: 2000
"""


def _generate_ci_config() -> str:
    """Generate CI/testing environment configuration."""
    return """# ScriptRAG CI/Testing Configuration
# Optimized for continuous integration and automated testing
#
# SECURITY WARNING: Use mock credentials or test keys only

# Database - In-memory for fast tests
database_path: ":memory:"
database_timeout: 10.0
database_wal_mode: false  # Not applicable for :memory:
database_foreign_keys: true
database_journal_mode: "MEMORY"
database_synchronous: "OFF"  # Speed over safety in CI
database_cache_size: -2000
database_temp_store: "MEMORY"

# Application
app_name: "scriptrag-test"
metadata_scan_size: 10240
skip_boneyard_filter: true  # Skip for test speed
debug: false

# Logging - Minimal for CI
log_level: "ERROR"
log_format: "console"
# No log file in CI
log_file_rotation: "1 hour"
log_file_retention: "1 hour"

# Search - Fast settings for CI
search_vector_threshold: 5
search_vector_similarity_threshold: 0.1
search_vector_result_limit_factor: 0.5
search_vector_min_results: 3
search_thread_timeout: 30.0  # Short timeout for CI

# LLM - Disabled for CI (use mocks)
# llm_provider: none
llm_temperature: 0.0
llm_force_static_models: true
llm_model_cache_ttl: 0  # No caching in CI

# Bible/Embeddings
bible_embeddings_path: "/tmp/embeddings/bible"
bible_max_file_size: 1048576  # 1MB for test files
bible_llm_context_limit: 1000
"""
