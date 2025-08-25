# ScriptRAG Configuration Examples

This directory contains example configuration files for different environments and use cases.

## Configuration Files

### config-local.YAML

Basic configuration for getting started quickly with ScriptRAG. Minimal settings for local usage.

**Use case:** Quick start, personal projects, trying out ScriptRAG

```bash
scriptrag --config examples/config-local.yaml init
```

### config-dev.YAML

Development environment configuration with verbose logging, relaxed thresholds, and local LLM support.

**Use case:** Active development, debugging, testing new features

```bash
scriptrag --config examples/config-dev.yaml index --recursive
```

### config-prod.YAML

Production-ready configuration with optimized performance, structured logging, and API-based LLMs.

**Use case:** Production deployments, stable environments, team usage

```bash
scriptrag --config /etc/scriptrag/config.yaml search "character arc"
```

### config-ci.YAML

Continuous Integration configuration with in-memory database and minimal output.

**Use case:** Automated testing, CI/CD pipelines, unit tests

```bash
scriptrag --config examples/config-ci.yaml test
```

## Configuration Management Commands

ScriptRAG provides several commands to manage configurations:

### Generate a new configuration file

```bash
# Generate default config
scriptrag config init

# Generate with environment preset
scriptrag config init --env dev
scriptrag config init --env prod
scriptrag config init --env ci

# Generate in different formats
scriptrag config init --format json
scriptrag config init --format toml
```

### Validate configuration

```bash
# Validate and show current configuration
scriptrag config validate

# Validate specific config file
scriptrag config validate -c myconfig.yaml

# Show configuration as JSON
scriptrag config validate --format json
```

### Show configuration

```bash
# Show all settings
scriptrag config show

# Show specific section
scriptrag config show database
scriptrag config show llm
scriptrag config show search

# Show configuration sources
scriptrag config show --sources
```

### Understanding precedence

```bash
# Display configuration precedence rules
scriptrag config precedence
```

## Configuration Precedence

Settings are resolved in the following order (highest to lowest priority):

1. **CLI Arguments** - Command-line flags override everything

   ```bash
   scriptrag index --db-path /custom/path.db
   ```

2. **Config Files** - YAML, TOML, or JSON configuration files

   ```bash
   scriptrag --config myconfig.yaml index
   ```

3. **Environment Variables** - Variables prefixed with `SCRIPTRAG_`

   ```bash
   export SCRIPTRAG_DATABASE_PATH=/data/scripts.db
   scriptrag index
   ```

4. **.env File** - Environment file in current directory

   ```bash
   echo "SCRIPTRAG_LOG_LEVEL=DEBUG" > .env
   scriptrag search "dialogue"
   ```

5. **Default Values** - Built-in defaults from ScriptRAGSettings

## Environment Variables

All settings can be overridden using environment variables with the `SCRIPTRAG_` prefix:

```bash
# Database settings
export SCRIPTRAG_DATABASE_PATH=/var/lib/scriptrag/db.sqlite
export SCRIPTRAG_DATABASE_TIMEOUT=60

# Logging
export SCRIPTRAG_LOG_LEVEL=DEBUG
export SCRIPTRAG_LOG_FORMAT=json

# LLM settings
export SCRIPTRAG_LLM_PROVIDER=openai
export SCRIPTRAG_LLM_API_KEY=$OPENAI_API_KEY
```

## Tips

1. **Start simple**: Use `config-local.yaml` to get started quickly
2. **Development**: Use `config-dev.yaml` with debug logging during development
3. **Production**: Copy `config-prod.yaml` to `/etc/scriptrag/` and customize
4. **Testing**: Use `config-ci.yaml` for consistent test environments
5. **Validation**: Always validate your config with `scriptrag config validate`
6. **Precedence**: Use `scriptrag config show` to see effective configuration

## Creating Custom Configurations

To create a custom configuration:

1. Generate a template:

   ```bash
   scriptrag config init -o custom-config.yaml
   ```

2. Edit the file to customize settings

3. Validate your configuration:

   ```bash
   scriptrag config validate -c custom-config.yaml
   ```

4. Use your configuration:

   ```bash
   scriptrag --config custom-config.yaml <command>
   ```

Or set as default:

```bash
cp custom-config.yaml ~/.config/scriptrag/config.yaml
```
