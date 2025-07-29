# Installation

## Requirements

- Python 3.11 or higher
- SQLite 3.38 or higher (for vector support)
- uv package manager

## Install uv

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install from Source

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
uv sync
```

## Development Installation

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
uv sync --dev
```

## Verify Installation

```bash
uv run scriptrag --version
```
