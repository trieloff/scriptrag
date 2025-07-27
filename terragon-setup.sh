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

# Function to check elapsed time
check_timeout() {
    local current=$(date +%s)
    local elapsed=$((current - SCRIPT_START))
    if [ $elapsed -gt 150 ]; then  # 2.5 minutes (leaving 30s buffer)
        log_error "Setup approaching 3-minute timeout limit. Aborting to prevent failure."
        exit 1
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

check_timeout

# Install jq if not present (needed for git API operations)
log_info "Checking for jq..."
if ! command -v jq &> /dev/null; then
    log_info "Installing jq..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y jq || {
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
            log_info "Found uv at $HOME/.local/bin/uv, using explicit path"
            UV_CMD="$HOME/.local/bin/uv"
        else
            log_error "Cannot find uv executable after installation"
            exit 1
        fi
    fi
fi

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

check_timeout

# Activate virtual environment
log_info "Activating virtual environment..."
source .venv/bin/activate || {
    log_error "Failed to activate virtual environment"
    exit 1
}

# Upgrade pip, setuptools, and wheel
log_info "Upgrading pip, setuptools, and wheel..."
${UV_CMD} pip install --upgrade pip setuptools wheel || {
    log_warning "Failed to upgrade pip/setuptools/wheel, continuing..."
}

check_timeout

# Install project dependencies
log_info "Installing project dependencies..."
if [ -f "pyproject.toml" ]; then
    # Install in editable mode with all extras for development
    ${UV_CMD} pip install -e ".[dev,test,docs]" || {
        log_warning "Failed to install with all extras, trying base installation..."
        ${UV_CMD} pip install -e "." || {
            log_error "Failed to install project dependencies"
            exit 1
        }
    }
    log_success "Project dependencies installed"
else
    log_error "pyproject.toml not found"
    exit 1
fi

check_timeout

# Set up environment variables if .env doesn't exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
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
fi

check_timeout

# Install pre-commit hooks (but don't run them to save time)
if command -v pre-commit &> /dev/null && [ -f ".pre-commit-config.yaml" ]; then
    log_info "Installing pre-commit hooks..."
    pre-commit install --install-hooks || {
        log_warning "Failed to install pre-commit hooks, continuing..."
    }
fi

check_timeout

# Initialize database if needed
if [ -f "src/scriptrag/database/init.py" ]; then
    log_info "Initializing database..."
    python -m scriptrag.database.init || {
        log_warning "Database initialization failed, may already exist"
    }
fi

# Create a setup completion marker
echo "Setup completed at: $(date)" > .terragon-setup-complete

# Final timeout check
check_timeout

# Calculate total time
SCRIPT_END=$(date +%s)
TOTAL_TIME=$((SCRIPT_END - SCRIPT_START))

log_success "✅ ScriptRAG Terragon setup completed successfully!"
log_info "Total setup time: ${TOTAL_TIME} seconds"
log_info ""
log_info "Environment ready. You can now run:"
log_info "  - 'python -m scriptrag' to run the CLI"
log_info "  - 'python -m scriptrag.mcp_server' to run the MCP server"
log_info "  - 'make test' to run tests"
log_info "  - 'make help' to see all available commands"

# Return success
exit 0
