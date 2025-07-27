# ScriptRAG Development Makefile
# Requires: make, python3.11+, uv

.PHONY: help
help: ## Show this help message
	@echo "ScriptRAG Development Commands"
	@echo "=============================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Environment setup
.PHONY: install
install: ## Install the project in development mode with all dependencies
	uv venv
	uv pip install -e ".[dev,test,docs]"
	@echo "✅ Installation complete. Activate venv with: source .venv/bin/activate"

.PHONY: setup-dev
setup-dev: ## Complete developer environment setup (venv, deps, hooks, tools)
	@echo "🚀 Setting up complete developer environment..."
	@echo "1️⃣ Creating virtual environment..."
	uv venv
	@echo "2️⃣ Installing all dependencies..."
	@bash -c 'source .venv/bin/activate && uv pip install -e ".[dev,test,docs]"'
	@echo "3️⃣ Installing pre-commit hooks..."
	@bash -c 'source .venv/bin/activate && pre-commit install'
	@bash -c 'source .venv/bin/activate && pre-commit install --hook-type commit-msg'
	@echo "4️⃣ Running initial pre-commit checks..."
	@bash -c 'source .venv/bin/activate && pre-commit run --all-files || echo "⚠️  Some pre-commit checks failed. Run '\''make format'\'' to fix."'
	@echo "5️⃣ Checking for Node.js dependencies..."
	@if command -v npm >/dev/null 2>&1; then \
		echo "Installing markdownlint-cli..."; \
		npm install -g markdownlint-cli; \
	else \
		echo "⚠️  npm not found. Install Node.js for markdown linting support."; \
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
update: ## Update all dependencies to latest versions
	uv pip install --upgrade -e ".[dev,test,docs]"
	pre-commit autoupdate
	@echo "✅ Dependencies updated"

# Code quality
.PHONY: format
format: ## Format code with black and ruff
	@bash -c 'source .venv/bin/activate && black src/ tests/'
	@bash -c 'source .venv/bin/activate && ruff check --fix src/ tests/'
	@bash -c 'source .venv/bin/activate && ruff format src/ tests/'
	@echo "✅ Code formatted"

.PHONY: lint
lint: ## Run all linters (ruff, mypy, bandit, etc.)
	@echo "🔍 Running Ruff..."
	@bash -c 'source .venv/bin/activate && ruff check src/ tests/'
	@echo "🔍 Running MyPy..."
	@bash -c 'source .venv/bin/activate && mypy src/'
	@echo "🔍 Running Bandit security checks..."
	@bash -c 'source .venv/bin/activate && bandit -r src/ -c pyproject.toml'
	@echo "🔍 Checking docstring coverage..."
	@bash -c 'source .venv/bin/activate && interrogate -c pyproject.toml'
	@echo "🔍 Checking for dead code..."
	@bash -c 'source .venv/bin/activate && vulture src/ --min-confidence 80'
	@echo "✅ All linting checks passed"

.PHONY: type-check
type-check: ## Run type checking with mypy
	@bash -c 'source .venv/bin/activate && mypy src/ --show-error-codes --pretty'

.PHONY: security
security: ## Run security checks (bandit, safety, pip-audit)
	@bash -c 'source .venv/bin/activate && bandit -r src/ -c pyproject.toml -f json -o .bandit-report.json'
	@bash -c 'source .venv/bin/activate && safety check --json --output .safety-report.json || true'
	@bash -c 'source .venv/bin/activate && pip-audit || true'
	@echo "✅ Security scan complete (see .bandit-report.json and .safety-report.json)"

# Testing
.PHONY: test
test: ## Run all tests with coverage
	@bash -c 'source .venv/bin/activate && pytest tests/ -v --cov=scriptrag --cov-report=term-missing --cov-report=html'

.PHONY: test-fast
test-fast: ## Run tests without coverage (faster)
	@bash -c 'source .venv/bin/activate && pytest tests/ -v'

.PHONY: test-property
test-property: ## Run property-based tests with Hypothesis
	@bash -c 'source .venv/bin/activate && pytest tests/test_property_based.py -v --hypothesis-show-statistics'

.PHONY: test-hypothesis-ci
test-hypothesis-ci: ## Run property-based tests in CI mode (deterministic)
	@bash -c 'source .venv/bin/activate && pytest tests/ -v --hypothesis-profile=ci'

.PHONY: test-hypothesis-debug
test-hypothesis-debug: ## Run property-based tests in debug mode (more examples)
	@bash -c 'source .venv/bin/activate && pytest tests/ -v --hypothesis-profile=debug'

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	pytest-watch tests/ -- -v

.PHONY: test-parallel
test-parallel: ## Run tests in parallel
	pytest tests/ -v -n auto

.PHONY: test-profile
test-profile: ## Run tests with profiling
	pytest tests/ -v --profile --profile-svg

.PHONY: profile-cpu
profile-cpu: ## Profile CPU usage with py-spy
	@echo "🔍 Profiling CPU usage..."
	py-spy record -o profile_cpu.svg -- python -m scriptrag parse examples/data/sample_screenplay.fountain
	@echo "✅ CPU profile saved to profile_cpu.svg"

.PHONY: profile-memory
profile-memory: ## Profile memory usage
	@echo "🔍 Profiling memory usage..."
	@bash -c 'source .venv/bin/activate && python -m memory_profiler -o profile_memory.txt examples/build_knowledge_graph.py'
	@echo "✅ Memory profile saved to profile_memory.txt"

.PHONY: profile-line
profile-line: ## Line-by-line profiling of a specific module
	@echo "🔍 Line profiling..."
	@echo "Usage: make profile-line MODULE=scriptrag.parser"
	@if [ -z "$(MODULE)" ]; then \
		echo "Error: Please specify a module. Example: make profile-line MODULE=scriptrag.parser"; \
		exit 1; \
	fi
	kernprof -l -v -m $(MODULE)

.PHONY: profile-scalene
profile-scalene: ## Profile with Scalene (CPU, GPU, memory)
	@echo "🔍 Profiling with Scalene..."
	scalene --html --outfile=profile_scalene.html -- python -m scriptrag parse examples/data/sample_screenplay.fountain
	@echo "✅ Scalene profile saved to profile_scalene.html"

.PHONY: benchmark
benchmark: ## Run performance benchmarks
	@bash -c 'source .venv/bin/activate && pytest tests/ -v --benchmark-only --benchmark-autosave'

.PHONY: benchmark-compare
benchmark-compare: ## Compare benchmark results
	@bash -c 'source .venv/bin/activate && pytest-benchmark compare'

.PHONY: mutate
mutate: ## Run mutation testing on the codebase
	@echo "🧬 Running mutation testing..."
	@bash -c 'source .venv/bin/activate && mutmut run --paths-to-mutate=src/scriptrag/ --runner="pytest -x -q"'

.PHONY: mutate-results
mutate-results: ## Show mutation testing results
	@bash -c 'source .venv/bin/activate && mutmut results'

.PHONY: mutate-html
mutate-html: ## Generate HTML report for mutation testing
	@bash -c 'source .venv/bin/activate && mutmut html'
	@echo "✅ Mutation testing report generated in html/"

.PHONY: mutate-apply
mutate-apply: ## Apply a specific mutation for inspection
	@if [ -z "$(ID)" ]; then \
		echo "Error: Please specify a mutation ID. Example: make mutate-apply ID=42"; \
		exit 1; \
	fi
	@bash -c 'source .venv/bin/activate && mutmut apply $(ID)'

.PHONY: coverage
coverage: ## Generate coverage report
	coverage run -m pytest tests/
	coverage report
	coverage html
	@echo "✅ Coverage report generated in htmlcov/"

# Documentation
.PHONY: docs
docs: ## Build documentation
	mkdocs build
	@echo "✅ Documentation built in site/"

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	mkdocs serve --dev-addr localhost:8000

.PHONY: docs-deploy
docs-deploy: ## Deploy documentation to GitHub Pages
	mkdocs gh-deploy --force

# Development tasks
.PHONY: run
run: ## Run the CLI application
	python -m scriptrag

.PHONY: run-mcp
run-mcp: ## Run the MCP server
	python -m scriptrag.mcp_server

.PHONY: run-api
run-api: ## Run the REST API server
	python -m scriptrag server api

.PHONY: run-api-dev
run-api-dev: ## Run the REST API server in development mode with auto-reload
	python -m scriptrag server api --reload

.PHONY: shell
shell: ## Start IPython shell with project context
	ipython -i -c "from scriptrag import *; print('ScriptRAG modules loaded')"

.PHONY: notebook
notebook: ## Start Jupyter notebook server
	jupyter notebook --notebook-dir=notebooks/

# Database tasks
.PHONY: db-init
db-init: ## Initialize the database
	python -m scriptrag.database.init

.PHONY: db-migrate
db-migrate: ## Run database migrations
	python -m scriptrag.database.migrate

.PHONY: db-seed
db-seed: ## Seed database with sample data
	python -m scriptrag.database.seed

# Build and distribution
.PHONY: build
build: clean ## Build distribution packages
	python -m build
	@echo "✅ Distribution packages built in dist/"

.PHONY: publish-test
publish-test: build ## Publish to TestPyPI
	python -m twine upload --repository testpypi dist/*

.PHONY: publish
publish: build ## Publish to PyPI
	python -m twine upload dist/*

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
check: lint type-check security test ## Run all quality checks

.PHONY: check-fast
check-fast: ## Run fast quality checks (no tests)
	@bash -c 'source .venv/bin/activate && ruff check src/ tests/'
	@bash -c 'source .venv/bin/activate && mypy src/ --no-error-summary'
	@bash -c 'source .venv/bin/activate && black --check src/ tests/'

.PHONY: pre-commit
pre-commit: ## Run pre-commit on all files
	@bash -c 'source .venv/bin/activate && pre-commit run --all-files'

# Project specific
.PHONY: parse-fountain
parse-fountain: ## Parse a fountain file (usage: make parse-fountain FILE=script.fountain)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: Please specify a fountain file. Usage: make parse-fountain FILE=script.fountain"; \
		exit 1; \
	fi
	python -m scriptrag parse "$(FILE)"

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
deps-upgrade: ## Upgrade all dependencies to latest versions
	uv pip install --upgrade $(shell uv pip freeze | cut -d= -f1)

.PHONY: deps-tree
deps-tree: ## Show dependency tree
	pipdeptree

.PHONY: deps-check
deps-check: ## Check for dependency conflicts
	pip check

# Docker commands
.PHONY: docker-build
docker-build: ## Build all Docker images
	docker-compose build

.PHONY: docker-build-prod
docker-build-prod: ## Build production Docker image
	docker build -t scriptrag:latest --target production .

.PHONY: docker-dev
docker-dev: ## Start development environment in Docker
	docker-compose up -d dev
	docker-compose exec dev bash

.PHONY: docker-test
docker-test: ## Run tests in Docker
	docker-compose run --rm test

.PHONY: docker-api
docker-api: ## Start API server in Docker
	docker-compose up -d api

.PHONY: docker-mcp
docker-mcp: ## Start MCP server in Docker
	docker-compose up -d mcp

.PHONY: docker-docs
docker-docs: ## Start documentation server in Docker
	docker-compose up -d docs
	@echo "📚 Documentation available at http://localhost:8080"

.PHONY: docker-down
docker-down: ## Stop all Docker containers
	docker-compose down

.PHONY: docker-clean
docker-clean: ## Clean Docker volumes and images
	docker-compose down -v
	docker rmi scriptrag:latest || true

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	docker-compose logs -f

.PHONY: docker-shell
docker-shell: ## Open shell in running container
	docker-compose exec dev bash

# Default target
.DEFAULT_GOAL := help
