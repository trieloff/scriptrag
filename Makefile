# ScriptRAG Development Makefile
# Requires: make, python3.11+
# UV will be installed automatically if missing

# Ensure we use bash for shell commands
SHELL := /bin/bash

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
format: install ## Format code with ruff and sqlfluff
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/
	uv run sqlfluff fix --dialect sqlite || echo "⚠️  SQLFluff fix failed (check SQL files manually)"
	@echo "✅ Code formatted"

.PHONY: lint
lint: install ## Run all linters (ruff, mypy, bandit, sqlfluff, etc.)
	@echo "🔍 Running Ruff..."
	uv run ruff check src/ tests/
	@echo "🔍 Running MyPy..."
	uv run mypy src/
	@echo "🔍 Running Bandit security checks..."
	uv run bandit -r src/ -c pyproject.toml
	@echo "🔍 Checking docstring coverage..."
	uv run interrogate -c pyproject.toml
	@echo "🔍 Checking for dead code..."
	uv run vulture --config pyproject.toml
	@echo "🔍 Running SQLFluff..."
	uv run sqlfluff lint --dialect sqlite || echo "⚠️  SQLFluff found issues (non-blocking)"
	@echo "✅ All linting checks passed"

.PHONY: type-check
type-check: install ## Run type checking with mypy
	uv run mypy src/ --show-error-codes --pretty

.PHONY: sql-lint
sql-lint: install ## Lint SQL files with SQLFluff
	uv run sqlfluff lint --dialect sqlite

.PHONY: sql-fix
sql-fix: install ## Fix SQL files with SQLFluff
	uv run sqlfluff fix --dialect sqlite

.PHONY: sql-format
sql-format: sql-fix ## Alias for sql-fix

.PHONY: security
security: install ## Run security checks (bandit, safety, pip-audit)
	uv run bandit -r src/ -c pyproject.toml -f json -o .bandit-report.json
	uv run safety check --json > .safety-report.json || true
	uv run pip-audit || true
	@echo "✅ Security scan complete (see .bandit-report.json and .safety-report.json)"

# Testing
.PHONY: test
test: install ## Run all tests in parallel with coverage
	@echo "🔍 Checking for mock files before tests..."
	@bash -c 'if find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null | head -1 | grep -q .; then \
		echo "❌ ERROR: Found mock files with invalid names!"; \
		echo "These files should never be created. They indicate a bug in test mocking."; \
		echo "Please fix the mock configuration to return proper values instead of Mock objects."; \
		echo ""; \
		echo "Files found:"; \
		find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null; \
		exit 1; \
	fi'
	@echo "🔍 Checking fixture files are clean..."
	@bash -c 'for f in tests/fixtures/fountain/test_data/{coffee_shop,simple_script,test_script,nested_script,parser_test}.fountain; do \
		if grep -q "SCRIPTRAG-META-START" "$$f" 2>/dev/null; then \
			echo "❌ ERROR: Fixture file $$f is contaminated with metadata!"; \
			echo "Run '\''git checkout $$f'\'' to restore it."; \
			exit 1; \
		fi; \
	done'
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		echo "🍎 Running tests on macOS with reduced parallelism to avoid hanging..."; \
		uv run pytest tests/ -v -n 2 --cov=scriptrag --cov-report= --junit-xml=junit.xml --timeout=300 --timeout-method=thread $(PYTEST_ARGS); \
	else \
		uv run pytest tests/ -v -n auto --cov=scriptrag --cov-report= --junit-xml=junit.xml --timeout=300 --timeout-method=thread $(PYTEST_ARGS); \
	fi
	uv run coverage combine || true  # May already be combined by pytest-xdist
	uv run coverage xml
	uv run coverage report --show-missing
	@echo "🔍 Checking for mock files after tests..."
	@bash -c 'if find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null | head -1 | grep -q .; then \
		echo "❌ ERROR: Tests created mock files with invalid names!"; \
		echo "These files indicate improper mock configuration in tests."; \
		echo "Mock objects should return proper string values, not Mock object representations."; \
		echo ""; \
		echo "Files created:"; \
		find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null; \
		echo ""; \
		echo "To fix: Ensure all mocked methods that return paths return actual string values."; \
		echo "Example: mock_settings.get_database_path.return_value = '\''/test/db.sqlite'\''"; \
		exit 1; \
	fi'

.PHONY: test-fast
test-unit: install ## Run only unit tests (fast)
	@echo "🧪 Running unit tests..."
	uv run pytest tests/ -v -m unit --timeout=30 $(PYTEST_ARGS)

test-integration: install ## Run only integration tests
	@echo "🔗 Running integration tests..."
	uv run pytest tests/ -v -m integration --timeout=60 $(PYTEST_ARGS)

test-llm: install ## Run LLM tests (requires SCRIPTRAG_TEST_LLMS=1)
	@echo "🤖 Running LLM tests..."
	@if [ -z "$$SCRIPTRAG_TEST_LLMS" ]; then \
		echo "⚠️  Warning: SCRIPTRAG_TEST_LLMS not set. LLM tests will be skipped."; \
		echo "Set SCRIPTRAG_TEST_LLMS=1 to enable LLM tests."; \
	fi
	uv run pytest tests/ -v -m requires_llm --timeout=120 $(PYTEST_ARGS)

test-no-llm: install ## Run all tests except LLM tests
	@echo "🧪 Running tests without LLM dependencies..."
	uv run pytest tests/ -v -m "not requires_llm" $(PYTEST_ARGS)

test-canary: install ## Run quick canary tests like CI (fast validation before push)
	@echo "🐤 Running canary tests for quick validation..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "⏭️  Excluding: integration, slow, and LLM tests"
	@echo "⚡ Settings: fail-fast (-x), 10 error limit, 15s per-test timeout"
	@echo "📊 Expected runtime: < 30 seconds"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@start=$$(date +%s); \
	uv run pytest -x -q --tb=short --maxfail=10 --disable-warnings --junit-xml=junit-canary.xml -o log_cli=false --capture=fd --timeout=15 --timeout-method=thread -m "not integration and not slow and not requires_llm" $(PYTEST_ARGS); \
	ret=$$?; \
	end=$$(date +%s); \
	runtime=$$((end-start)); \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	if [ $$ret -eq 0 ]; then \
		echo "✅ Canary tests passed in $${runtime}s"; \
		echo "🚀 Ready to push! Consider running 'make test' for full validation."; \
	else \
		echo "❌ Canary tests failed after $${runtime}s"; \
		echo "💡 Run 'make test' for detailed output or check junit-canary.xml"; \
	fi; \
	exit $$ret

test-fast: install ## Run tests without coverage (faster)
	@echo "🔍 Checking for mock files before tests..."
	@bash -c 'if find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null | head -1 | grep -q .; then \
		echo "❌ ERROR: Found mock files with invalid names!"; \
		echo "Run '\''make clean-mock-files'\'' to remove them."; \
		exit 1; \
	fi'
	@echo "🔍 Checking fixture files are clean..."
	@bash -c 'for f in tests/fixtures/fountain/test_data/{coffee_shop,simple_script,test_script,nested_script,parser_test}.fountain; do \
		if grep -q "SCRIPTRAG-META-START" "$$f" 2>/dev/null; then \
			echo "❌ ERROR: Fixture file $$f is contaminated with metadata!"; \
			echo "Run '\''git checkout $$f'\'' to restore it."; \
			exit 1; \
		fi; \
	done'
	uv run pytest tests/ -c pytest-minimal.ini -q --tb=short -n auto --maxfail=5 --durations=10
	@echo "🔍 Checking for mock files after tests..."
	@bash -c 'if find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null | head -1 | grep -q .; then \
		echo "❌ ERROR: Tests created mock files!"; \
		echo "Fix mock configuration in tests."; \
		exit 1; \
	fi'

.PHONY: test-watch
test-watch: install ## Run tests in watch mode
	uv run pytest-watch tests/ -- -v

.PHONY: test-parallel
test-parallel: install ## Run tests with maximum parallelization (fastest)
	@echo "⚡ Running tests with maximum parallelization..."
	uv run pytest tests/ --no-cov -q --tb=short -n $(shell nproc || echo 4) --dist loadscope --durations=10

.PHONY: test-quick
test-quick: install ## Run only unit tests in parallel (very fast)
	@echo "🚀 Running quick unit tests..."
	uv run pytest tests/ --no-cov -q --tb=short -n auto -m "unit and not slow" --maxfail=1

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

.PHONY: test-coverage
test-coverage: test ## Run tests and print detailed coverage report
	@echo ""
	@echo "📊 Detailed Coverage Report"
	@echo "==========================="
	uv run coverage report --show-missing --skip-covered --skip-empty --sort=cover
	@echo ""
	@echo "📈 Coverage Summary:"
	uv run coverage report --format=total
	@echo ""
	@echo "📁 HTML report available in htmlcov/index.html"

.PHONY: docstring-coverage
docstring-coverage: install ## Check docstring coverage with detailed report
	@echo "📊 Docstring Coverage Report"
	@echo "============================"
	uv run interrogate src/ -v
	@echo ""
	@echo "Current minimum threshold: 80%"

.PHONY: docstring-badge
docstring-badge: install ## Generate docstring coverage badge
	@echo "🏷️ Generating docstring coverage badge..."
	uv run interrogate src/ --generate-badge .
	@echo "✅ Badge generated as interrogate_badge.svg"

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

.PHONY: clean-python
clean-python: ## Clean Python cache files (.pyc, __pycache__)
	@echo "🧹 Cleaning Python cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage.*" -delete
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Python cache cleaned"

.PHONY: clean-mock-files
clean-mock-files: ## Clean up mock files created by tests
	@echo "🧹 Cleaning up mock files..."
	@bash -c 'find . \( -name "*Mock*name=*" -o -name "<Mock*" -o -name "*<Mock*" -o -name "*id='\''*'\''*" \) -not -path "*/.git/*" -not -path "*/__pycache__/*" 2>/dev/null -print0 | xargs -0 -r rm -f'
	@echo "✅ Mock files cleaned"

.PHONY: detect-mock-files
detect-mock-files: ## Detect which tests create mock file artifacts
	@echo "🔍 Running enhanced mock file detection..."
	@python tests/detect_mock_files.py
	@echo ""
	@echo "To trace which specific tests create mock files, run:"
	@echo "  make test-trace-mocks"

.PHONY: test-trace-mocks
test-trace-mocks: ## Run tests with mock file tracking to identify problematic tests
	@echo "🔍 Running tests with mock file detection enabled..."
	@echo ""
	@echo "This will identify which specific tests create mock file artifacts."
	@echo ""
	@bash tests/run_with_mock_detection.sh

.PHONY: clean-all
clean-all: clean clean-python clean-mock-files ## Clean all artifacts including caches and venv
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf site/
	rm -rf .bandit-report.json
	rm -rf .safety-report.json
	rm -rf junit.xml
	rm -rf prof/
	find . -type f -name "*~" -delete
	find . -type f -name ".DS_Store" -delete
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
	uv run interrogate src/ --fail-under 80 --quiet

.PHONY: check-canary
check-canary: check-fast test-canary ## Run fast checks + canary tests (recommended before push)

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
