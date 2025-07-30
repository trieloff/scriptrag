#!/bin/bash
# Terragon Setup Script for ScriptRAG
# This script sets up the development environment for ScriptRAG in Terragon sandboxes
# Must complete within 3 minutes to avoid timeout

set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Track execution time
SCRIPT_START=$(date +%s)

# Track completed steps
declare -A COMPLETED_STEPS=(
    ["python_check"]=0
    ["jq_install"]=0
    ["gh_workflow_peek"]=0
    ["uv_install"]=0
    ["directories"]=0
    ["venv_create"]=0
    ["venv_activate"]=0
    ["pip_upgrade"]=0
    ["dependencies"]=0
    ["env_file"]=0
    ["pre_commit"]=0
    ["db_init"]=0
)

# List of all steps with descriptions
declare -A STEP_DESCRIPTIONS=(
    ["python_check"]="Check Python version (3.11+)"
    ["jq_install"]="Install jq for git operations"
    ["gh_workflow_peek"]="Install gh-workflow-peek for CI analysis"
    ["uv_install"]="Install uv package manager"
    ["directories"]="Create required directories"
    ["venv_create"]="Create Python virtual environment"
    ["venv_activate"]="Activate virtual environment"
    ["pip_upgrade"]="Upgrade pip, setuptools, wheel"
    ["dependencies"]="Install project dependencies"
    ["env_file"]="Set up .env configuration"
    ["pre_commit"]="Install pre-commit hooks"
    ["db_init"]="Initialize database"
)

# Function to mark step as completed
mark_completed() {
    COMPLETED_STEPS["$1"]=1
}

# Function to show remaining steps
show_remaining_steps() {
    log_warning "Setup approaching 3-minute timeout limit."
    log_info ""
    log_info "✅ Completed steps:"
    for step in "${!COMPLETED_STEPS[@]}"; do
        if [ "${COMPLETED_STEPS[$step]}" -eq 1 ]; then
            echo "   - ${STEP_DESCRIPTIONS[$step]}"
        fi
    done

    log_info ""
    log_warning "⏳ Remaining steps to complete manually:"
    local has_remaining=0
    for step in python_check jq_install gh_workflow_peek uv_install directories venv_create venv_activate pip_upgrade dependencies env_file pre_commit db_init; do
        if [ "${COMPLETED_STEPS[$step]}" -eq 0 ]; then
            echo "   - ${STEP_DESCRIPTIONS[$step]}"
            has_remaining=1
        fi
    done

    if [ $has_remaining -eq 0 ]; then
        log_success "All steps completed!"
    else
        log_info ""
        log_info "To complete setup manually, run these commands:"
        log_info ""

        # Provide specific commands for remaining steps
        if [ "${COMPLETED_STEPS[venv_create]}" -eq 0 ]; then
            echo "   uv venv --python python3.11"
        fi
        if [ "${COMPLETED_STEPS[venv_activate]}" -eq 0 ]; then
            echo "   source .venv/bin/activate"
        fi
        if [ "${COMPLETED_STEPS[pip_upgrade]}" -eq 0 ]; then
            echo "   # No need to upgrade pip with uv sync"
        fi
        if [ "${COMPLETED_STEPS[dependencies]}" -eq 0 ]; then
            echo "   uv sync --all-extras"
        fi
        if [ "${COMPLETED_STEPS[env_file]}" -eq 0 ] && [ -f ".env.example" ]; then
            echo "   cp .env.example .env"
        fi
        if [ "${COMPLETED_STEPS[pre_commit]}" -eq 0 ] && [ -f ".pre-commit-config.yaml" ]; then
            echo "   pre-commit install --install-hooks"
        fi
        if [ "${COMPLETED_STEPS[db_init]}" -eq 0 ] && [ -f "src/scriptrag/database/init.py" ]; then
            echo "   python -m scriptrag.database.init"
        fi
    fi
}

# Function to check elapsed time
check_timeout() {
    local current=$(date +%s)
    local elapsed=$((current - SCRIPT_START))
    if [ $elapsed -gt 150 ]; then  # 2.5 minutes (leaving 30s buffer)
        show_remaining_steps
        exit 0  # Exit successfully with helpful output
    fi
}

# Create a lockfile to prevent concurrent runs
LOCKFILE="/tmp/terragon-setup.lock"
if [ -f "$LOCKFILE" ]; then
    log_warning "Another setup process is running or previously failed. Removing stale lock."
    rm -f "$LOCKFILE"
fi
touch "$LOCKFILE"

# Cleanup function
cleanup() {
    rm -f "$LOCKFILE"
}
trap cleanup EXIT

# Start setup
log_info "Starting ScriptRAG Terragon environment setup..."
log_info "Script must complete within 3 minutes"

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_info "Found Python $PYTHON_VERSION"

# Check if we meet minimum Python requirement (3.11+)
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    log_error "Python 3.11 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

mark_completed "python_check"
check_timeout

# Install jq if not present (needed for git API operations)
log_info "Checking for jq..."
if ! command -v jq &> /dev/null; then
    log_info "Installing jq..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y jq || {
            log_warning "Failed to install jq via apt-get, continuing..."
        }
    elif command -v yum &> /dev/null; then
        sudo yum install -y jq || {
            log_warning "Failed to install jq via yum, continuing..."
        }
    elif command -v brew &> /dev/null; then
        brew install jq || {
            log_warning "Failed to install jq via brew, continuing..."
        }
    else
        log_warning "No supported package manager found for jq installation"
    fi
else
    log_info "jq is already installed"
fi

mark_completed "jq_install"
check_timeout

# Install gh-workflow-peek GitHub CLI extension
log_info "Checking for gh-workflow-peek extension..."
if command -v gh &> /dev/null; then
    # Check if gh-workflow-peek is already installed
    if ! gh extension list | grep -q "trieloff/gh-workflow-peek"; then
        log_info "Installing gh-workflow-peek for CI/CD analysis..."
        gh extension install trieloff/gh-workflow-peek || {
            log_warning "Failed to install gh-workflow-peek, continuing..."
        }
    else
        log_info "gh-workflow-peek is already installed"
    fi
else
    log_warning "GitHub CLI (gh) not found, skipping gh-workflow-peek installation"
fi

mark_completed "gh_workflow_peek"
check_timeout

# Install uv if not present (it should be pre-installed in Terragon)
UV_CMD="uv"
if ! command -v uv &> /dev/null; then
    log_info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || {
        log_error "Failed to install uv"
        exit 1
    }
    export PATH="$HOME/.local/bin:$PATH"

    # Source the uv environment script if it exists
    if [ -f "$HOME/.local/bin/env" ]; then
        log_info "Sourcing uv environment script..."
        source "$HOME/.local/bin/env"
    fi

    # Verify uv is now available
    if ! command -v uv &> /dev/null; then
        log_info "uv not found in PATH after installation, checking explicit location..."
        if [ -x "$HOME/.local/bin/uv" ]; then
            log_info "Found uv at $HOME/.local/bin/uv"
            # Create symlink to make uv available system-wide
            log_info "Creating symlink to make uv available in PATH..."
            sudo ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv || {
                log_warning "Failed to create symlink, using explicit path"
                UV_CMD="$HOME/.local/bin/uv"
            }
            # Check if symlink worked
            if command -v uv &> /dev/null; then
                log_success "uv is now available in PATH"
            else
                UV_CMD="$HOME/.local/bin/uv"
            fi
        else
            log_error "Cannot find uv executable after installation"
            exit 1
        fi
    fi
fi

mark_completed "uv_install"
check_timeout

# Navigate to project directory
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)
log_info "Project root: $PROJECT_ROOT"

# Create necessary directories
log_info "Creating required directories..."
mkdir -p logs
mkdir -p data
mkdir -p cache
mkdir -p exports
mkdir -p temp
mkdir -p notebooks

mark_completed "directories"

# Set up Python virtual environment
log_info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    ${UV_CMD} venv --python python3.11 || {
        log_error "Failed to create virtual environment"
        exit 1
    }
    log_success "Virtual environment created"
else
    log_info "Virtual environment already exists"
fi

mark_completed "venv_create"
check_timeout

# Activate virtual environment
log_info "Activating virtual environment..."
source .venv/bin/activate || {
    log_error "Failed to activate virtual environment"
    exit 1
}

mark_completed "venv_activate"

# No need to upgrade pip/setuptools/wheel with uv sync
log_info "Using uv sync for dependency management..."

mark_completed "pip_upgrade"
check_timeout

# Install project dependencies
log_info "Installing project dependencies..."
if [ -f "pyproject.toml" ]; then
    # Install all extras for development
    ${UV_CMD} sync --all-extras || {
        log_warning "Failed to install with all extras, trying base installation..."
        ${UV_CMD} sync || {
            log_error "Failed to install project dependencies"
            exit 1
        }
    }
    log_success "Project dependencies installed"
else
    log_error "pyproject.toml not found"
    exit 1
fi

mark_completed "dependencies"
check_timeout

# Set up environment variables if .env doesn't exist
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    log_info "Creating .env file from .env.example..."
    cp .env.example .env

    # Replace with Terragon environment variables if available
    if [ -n "${DATABASE_URL:-}" ]; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
    fi
    if [ -n "${OPENAI_API_KEY:-}" ]; then
        sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$OPENAI_API_KEY|" .env
    fi
    if [ -n "${LLM_API_URL:-}" ]; then
        sed -i "s|^LLM_API_URL=.*|LLM_API_URL=$LLM_API_URL|" .env
    fi
    log_success ".env file created"
  else
    log_warning "No .env.example file found, skipping .env creation"
  fi
else
    log_info ".env file already exists"
fi

mark_completed "env_file"
check_timeout

# Install pre-commit hooks (but don't run them to save time)
if [ -f ".pre-commit-config.yaml" ]; then
  if command -v pre-commit &> /dev/null; then
    log_info "Installing pre-commit hooks..."
    pre-commit install --install-hooks || {
        log_warning "Failed to install pre-commit hooks, continuing..."
    }
  else
    log_warning "pre-commit not available, skipping hook installation"
  fi
else
    log_info "No .pre-commit-config.yaml found, skipping pre-commit setup"
fi

mark_completed "pre_commit"
check_timeout

# Initialize database if needed
if [ -f "src/scriptrag/database/init.py" ]; then
    log_info "Initializing database..."
    python -m scriptrag.database.init || {
        log_warning "Database initialization failed, may already exist"
    }
fi

mark_completed "db_init"

# Create a setup completion marker
echo "Setup completed at: $(date)" > .terragon-setup-complete

# Final timeout check
check_timeout

# Calculate total time
SCRIPT_END=$(date +%s)
TOTAL_TIME=$((SCRIPT_END - SCRIPT_START))

log_success "✅ ScriptRAG Terragon setup completed successfully!"
log_info "Total setup time: ${TOTAL_TIME} seconds"

# Show completion summary
log_info ""
log_info "📋 Setup Summary:"
for step in python_check jq_install gh_workflow_peek uv_install directories venv_create venv_activate pip_upgrade dependencies env_file pre_commit db_init; do
    if [ "${COMPLETED_STEPS[$step]}" -eq 1 ]; then
        echo "   ✅ ${STEP_DESCRIPTIONS[$step]}"
    else
        echo "   ❌ ${STEP_DESCRIPTIONS[$step]} (skipped or failed)"
    fi
done

log_info ""
log_info "Environment ready. You can now run:"
log_info "  - 'python -m scriptrag' to run the CLI"
log_info "  - 'python -m scriptrag.mcp_server' to run the MCP server"
log_info "  - 'make test' to run tests"
log_info "  - 'make help' to see all available commands"

# Return success
exit 0
