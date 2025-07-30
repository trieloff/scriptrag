# ScriptRAG Development Makefile
# Requires: make, python3.11+
# UV will be installed automatically if missing

.PHONY: help
help: ## Show this help message
	@echo "ScriptRAG Development Commands"
	@echo "=============================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# UV bootstrap
.PHONY: check-uv
check-uv:
	@command -v uv >/dev/null 2>&1 || (echo "UV not found. Installing..." && $(MAKE) install-uv)

.PHONY: install-uv
install-uv: ## Install UV package manager
	@echo "Installing UV package manager..."
	@if command -v curl >/dev/null 2>&1; then \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	elif command -v wget >/dev/null 2>&1; then \
		wget -qO- https://astral.sh/uv/install.sh | sh; \
	else \
		echo "Error: Neither curl nor wget found. Please install UV manually from https://github.com/astral-sh/uv"; \
		exit 1; \
	fi
	@echo "✅ UV installed. You may need to restart your shell or add UV to your PATH."

# Environment setup
.PHONY: install
install: check-uv ## Install the project in development mode with all dependencies
	uv sync --all-extras
	@echo "✅ Installation complete. Activate venv with: source .venv/bin/activate"

.PHONY: setup-dev
setup-dev: check-uv ## Complete developer environment setup (venv, deps, hooks, tools)
	@echo "🚀 Setting up complete developer environment..."
	@echo "1️⃣ Creating virtual environment..."
	uv venv
	@echo "2️⃣ Installing all dependencies..."
	uv sync --all-extras
	@echo "3️⃣ Installing pre-commit hooks..."
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "4️⃣ Running initial pre-commit checks..."
	uv run pre-commit run --all-files || echo "⚠️  Some pre-commit checks failed. Run 'make format' to fix."
	@echo "5️⃣ Checking for Node.js dependencies..."
	@if command -v npm >/dev/null 2>&1; then \
		echo "Installing markdownlint-cli..."; \
		npm install -g markdownlint-cli; \
	else \
		echo "⚠️  npm not found. Install Node.js for markdown linting support."; \
	fi
	@echo "6️⃣ Installing GitHub CLI extensions..."
	@if command -v gh >/dev/null 2>&1; then \
		if ! gh extension list | grep -q "trieloff/gh-workflow-peek"; then \
			echo "Installing gh-workflow-peek for CI/CD analysis..."; \
			gh extension install trieloff/gh-workflow-peek || echo "⚠️  Failed to install gh-workflow-peek"; \
		else \
			echo "gh-workflow-peek is already installed"; \
		fi; \
	else \
		echo "⚠️  GitHub CLI (gh) not found. Install it for CI/CD analysis support."; \
	fi
	@echo "✅ Developer environment setup complete!"
	@echo ""
	@echo "📝 Next steps:"
	@echo "   - Activate virtual environment: source .venv/bin/activate"
	@echo "   - Run tests: make test"
	@echo "   - Check code quality: make check"
	@echo "   - See all commands: make help"

.PHONY: install-pre-commit
install-pre-commit: ## Install pre-commit hooks
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Pre-commit hooks installed"

.PHONY: update
update: install ## Update all dependencies to latest versions
	uv sync --all-extras --upgrade
	uv run pre-commit autoupdate
	@echo "✅ Dependencies updated"

# Code quality
.PHONY: format
format: install ## Format code with ruff
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/
	@echo "✅ Code formatted"

.PHONY: lint
lint: install ## Run all linters (ruff, mypy, bandit, etc.)
	@echo "🔍 Running Ruff..."
	uv run ruff check src/ tests/
	@echo "🔍 Running MyPy..."
	uv run mypy src/
	@echo "🔍 Running Bandit security checks..."
	uv run bandit -r src/ -c pyproject.toml
	@echo "🔍 Checking docstring coverage..."
	uv run interrogate -c pyproject.toml
	@echo "🔍 Checking for dead code..."
	uv run vulture src/ --min-confidence 80
	@echo "✅ All linting checks passed"

.PHONY: type-check
type-check: install ## Run type checking with mypy
	uv run mypy src/ --show-error-codes --pretty

.PHONY: security
security: install ## Run security checks (bandit, safety, pip-audit)
	uv run bandit -r src/ -c pyproject.toml -f json -o .bandit-report.json
	uv run safety check --json > .safety-report.json || true
	uv run pip-audit || true
	@echo "✅ Security scan complete (see .bandit-report.json and .safety-report.json)"

# Testing
.PHONY: test
test: install ## Run all tests in parallel with coverage
	uv run pytest tests/ -v -n auto --cov=scriptrag --cov-report= --junit-xml=junit.xml $(PYTEST_ARGS)
	uv run coverage combine || true  # May already be combined by pytest-xdist
	uv run coverage xml
	uv run coverage report --show-missing

.PHONY: test-fast
test-fast: install ## Run tests without coverage (faster)
	uv run pytest tests/ -v -n auto

.PHONY: test-watch
test-watch: install ## Run tests in watch mode
	uv run pytest-watch tests/ -- -v

.PHONY: test-profile
test-profile: install ## Run tests with profiling
	uv run pytest tests/ -v --profile --profile-svg

.PHONY: coverage
coverage: install ## Generate coverage report
	uv run coverage run -m pytest tests/
	uv run coverage report
	uv run coverage html
	@echo "✅ Coverage report generated in htmlcov/"

.PHONY: coverage-combine
coverage-combine: install ## Combine coverage data from parallel test runs
	uv run coverage combine
	uv run coverage report
	uv run coverage html
	@echo "✅ Combined coverage report generated in htmlcov/"

# Documentation
.PHONY: docs
docs: install ## Build documentation
	uv run mkdocs build
	@echo "✅ Documentation built in site/"

.PHONY: docs-serve
docs-serve: install ## Serve documentation locally
	uv run mkdocs serve --dev-addr localhost:8000

.PHONY: docs-deploy
docs-deploy: install ## Deploy documentation to GitHub Pages
	uv run mkdocs gh-deploy --force

# Development tasks
.PHONY: run
run: install ## Run the CLI application
	uv run python -m scriptrag

.PHONY: run-mcp
run-mcp: install ## Run the MCP server
	uv run python -m scriptrag.mcp_server

.PHONY: run-api
run-api: install ## Run the REST API server
	uv run python -m scriptrag server api

.PHONY: run-api-dev
run-api-dev: install ## Run the REST API server in development mode with auto-reload
	uv run python -m scriptrag server api --reload

.PHONY: shell
shell: install ## Start IPython shell with project context
	uv run ipython -i -c "from scriptrag import *; print('ScriptRAG modules loaded')"

.PHONY: notebook
notebook: install ## Start Jupyter notebook server
	uv run jupyter notebook --notebook-dir=notebooks/

# Database tasks
.PHONY: db-init
db-init: install ## Initialize the database
	uv run python -m scriptrag.database.init

.PHONY: db-migrate
db-migrate: install ## Run database migrations
	uv run python -m scriptrag.database.migrate

.PHONY: db-seed
db-seed: install ## Seed database with sample data
	uv run python -m scriptrag.database.seed

# Build and distribution
.PHONY: build
build: clean install ## Build distribution packages
	uv run python -m build
	@echo "✅ Distribution packages built in dist/"

.PHONY: check-dist
check-dist: install ## Check distribution packages
	uv run twine check dist/*
	@echo "✅ Distribution packages validated"

.PHONY: publish-test
publish-test: build ## Publish to TestPyPI
	uv run python -m twine upload --repository testpypi dist/*

.PHONY: publish
publish: build ## Publish to PyPI
	uv run python -m twine upload dist/*

# Cleaning
.PHONY: clean
clean: ## Clean build artifacts and caches
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf site/
	rm -rf .bandit-report.json
	rm -rf .safety-report.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	find . -type f -name ".DS_Store" -delete

.PHONY: clean-all
clean-all: clean ## Clean everything including venv
	rm -rf .venv/
	rm -rf uv.lock

# Quality checks (combines multiple checks)
.PHONY: check
check: check-uv lint type-check security test ## Run all quality checks

.PHONY: check-fast
check-fast: install ## Run fast quality checks (no tests)
	uv run ruff check src/ tests/
	uv run mypy src/ --no-error-summary
	uv run ruff format --check src/ tests/

.PHONY: pre-commit
pre-commit: install ## Run pre-commit on all files
	uv run pre-commit run --all-files

# Project specific
.PHONY: parse-fountain
parse-fountain: install ## Parse a fountain file (usage: make parse-fountain FILE=script.fountain)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: Please specify a fountain file. Usage: make parse-fountain FILE=script.fountain"; \
		exit 1; \
	fi
	uv run python -m scriptrag parse "$(FILE)"

.PHONY: start-llm
start-llm: ## Instructions to start LMStudio
	@echo "📝 To use ScriptRAG, start LMStudio and:"
	@echo "1. Load a model (recommended: Mistral, Llama 2, or similar)"
	@echo "2. Start the server on http://localhost:1234"
	@echo "3. Verify the OpenAI-compatible endpoint at http://localhost:1234/v1"

# Git helpers
.PHONY: git-clean
git-clean: ## Clean git repository (remove untracked files)
	git clean -xdf -e .venv -e .env -e .env.local

# Dependencies management
.PHONY: deps-upgrade
deps-upgrade: install ## Upgrade all dependencies to latest versions
	uv sync --all-extras --upgrade

.PHONY: deps-tree
deps-tree: install ## Show dependency tree
	uv run pipdeptree

.PHONY: deps-check
deps-check: ## Check for dependency conflicts
	pip check

# Default target
.DEFAULT_GOAL := help
