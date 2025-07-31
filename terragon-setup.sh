#!/bin/bash
# Terragon Setup Script for ScriptRAG
# This script sets up the development environment for ScriptRAG in Terragon sandboxes
# Must complete within 3 minutes to avoid timeout

set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Setup log file
LOG_DIR="/tmp"
LOG_FILE="$LOG_DIR/terragon-setup-$(date +%Y%m%d-%H%M%S).log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Terragon setup script" > "$LOG_FILE"

# Color codes for output (console only)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions - output to both console and file
log_message() {
    local level="$1"
    local message="$2"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    # Write to log file with timestamp and level
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Also output to console with colors
    case "$level" in
        INFO)
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} $message"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} $message" >&2
            ;;
    esac
}

log_info() {
    log_message "INFO" "$1"
}

log_success() {
    log_message "SUCCESS" "$1"
}

log_warning() {
    log_message "WARNING" "$1"
}

log_error() {
    log_message "ERROR" "$1"
}

# Log command output
log_command() {
    local cmd="$1"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] [COMMAND] Running: $cmd" >> "$LOG_FILE"
    eval "$cmd" 2>&1 | tee -a "$LOG_FILE"
    local exit_code=${PIPESTATUS[0]}
    echo "[$timestamp] [COMMAND] Exit code: $exit_code" >> "$LOG_FILE"
    return $exit_code
}

# Track execution time
SCRIPT_START=$(date +%s)

# Log script environment
log_info "Log file: $LOG_FILE"
log_info "Current user: $(whoami)"
log_info "Current directory: $(pwd)"
log_info "PATH: $PATH"
log_info "Script parameters: $*"

# Track completed steps
declare -A COMPLETED_STEPS=(
    ["python_check"]=0
    ["jq_install"]=0
    ["gh_workflow_peek"]=0
    ["ai_aligned_git"]=0
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
    ["ai_aligned_git"]="Install ai-aligned-git for AI-safe git operations"
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
    for step in python_check jq_install gh_workflow_peek ai_aligned_git uv_install directories venv_create venv_activate pip_upgrade dependencies env_file pre_commit db_init; do
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
    log_info "GitHub CLI found at: $(which gh)"

    # First ensure column utility is installed (required by gh-workflow-peek)
    if ! command -v column &> /dev/null; then
        log_info "Installing column utility (required by gh-workflow-peek)..."
        if command -v apt-get &> /dev/null; then
            log_info "Using apt-get to install column utility..."
            sudo apt-get install -y bsdmainutils 2>&1 | tee -a "$LOG_FILE" || sudo apt-get install -y util-linux 2>&1 | tee -a "$LOG_FILE" || {
                log_warning "Failed to install column utility via apt-get"
            }
        elif command -v yum &> /dev/null; then
            log_info "Using yum to install column utility..."
            sudo yum install -y util-linux 2>&1 | tee -a "$LOG_FILE" || {
                log_warning "Failed to install column utility via yum"
            }
        elif command -v brew &> /dev/null; then
            log_info "Using brew to install column utility..."
            brew install util-linux 2>&1 | tee -a "$LOG_FILE" || {
                log_warning "Failed to install column utility via brew"
            }
        fi

        # Check if column is now available
        if command -v column &> /dev/null; then
            log_success "Column utility installed successfully at: $(which column)"
        else
            log_warning "Column utility still not found after installation attempt"
        fi
    else
        log_info "Column utility already available at: $(which column)"
    fi

    # Install gh-workflow-peek manually to avoid authentication requirement
    log_info "Installing gh-workflow-peek extension manually..."

    # GitHub CLI extensions are stored in ~/.local/share/gh/extensions/
    GH_EXT_DIR="$HOME/.local/share/gh/extensions"
    GH_WORKFLOW_PEEK_DIR="$GH_EXT_DIR/gh-workflow-peek"

    # Create extensions directory if it doesn't exist
    log_info "Creating GitHub CLI extensions directory: $GH_EXT_DIR"
    mkdir -p "$GH_EXT_DIR"

    # Check if gh-workflow-peek is already installed
    if [ -d "$GH_WORKFLOW_PEEK_DIR" ]; then
        log_info "gh-workflow-peek directory already exists at $GH_WORKFLOW_PEEK_DIR"

        # Check if it's a valid git repository
        if [ -d "$GH_WORKFLOW_PEEK_DIR/.git" ]; then
            log_info "Updating existing gh-workflow-peek installation..."
            cd "$GH_WORKFLOW_PEEK_DIR"
            git pull 2>&1 | tee -a "$LOG_FILE" || {
                log_warning "Failed to update gh-workflow-peek, using existing version"
            }
            cd - >/dev/null
        else
            log_warning "gh-workflow-peek directory exists but is not a git repository"
            log_info "Removing and re-installing..."
            rm -rf "$GH_WORKFLOW_PEEK_DIR"
        fi
    fi

    # Install if not present
    if [ ! -d "$GH_WORKFLOW_PEEK_DIR" ]; then
        log_info "Cloning gh-workflow-peek repository..."
        log_info "Running: git clone https://github.com/trieloff/gh-workflow-peek.git $GH_WORKFLOW_PEEK_DIR"
        git clone https://github.com/trieloff/gh-workflow-peek.git "$GH_WORKFLOW_PEEK_DIR" 2>&1 | tee -a "$LOG_FILE" || {
            exit_code=$?
            log_error "Failed to clone gh-workflow-peek, exit code: $exit_code"
            log_warning "Continuing with setup despite gh-workflow-peek installation failure..."
        }
    fi

    # Verify installation
    if [ -f "$GH_WORKFLOW_PEEK_DIR/gh-workflow-peek" ]; then
        log_success "gh-workflow-peek installed successfully at $GH_WORKFLOW_PEEK_DIR"
        log_info "Extension will be available after GitHub CLI authentication"
        log_info "To authenticate: gh auth login"
    else
        log_error "gh-workflow-peek executable not found after installation"
    fi
else
    log_warning "GitHub CLI (gh) not found at expected locations"
    log_info "Searched PATH: $PATH"
    log_warning "Skipping gh-workflow-peek installation"
fi

mark_completed "gh_workflow_peek"
check_timeout

# Install ai-aligned-git (git wrapper for AI safety)
log_info "Checking for ai-aligned-git..."
if [ ! -f "$HOME/.local/bin/git" ] || ! grep -q "Git wrapper - Automatically detect AI tools" "$HOME/.local/bin/git" 2>/dev/null; then
    log_info "Installing ai-aligned-git for AI-safe git operations..."
    # Download and run the install script
    curl -fsSL https://raw.githubusercontent.com/trieloff/ai-aligned-git/main/install.sh -o /tmp/install-ai-aligned-git.sh && \
    chmod +x /tmp/install-ai-aligned-git.sh && \
    bash /tmp/install-ai-aligned-git.sh -y || {
        log_warning "Failed to install ai-aligned-git, continuing..."
    }
    rm -f /tmp/install-ai-aligned-git.sh

    # Ensure ~/.local/bin is in PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    # Create symlink to make ai-aligned-git available system-wide
    if [ -f "$HOME/.local/bin/git" ]; then
        log_info "Creating symlink for ai-aligned-git..."
        sudo ln -sf "$HOME/.local/bin/git" /usr/local/bin/git || {
            log_warning "Failed to create symlink for ai-aligned-git"
        }
        # Verify the symlink worked
        if [ -L "/usr/local/bin/git" ]; then
            log_success "ai-aligned-git symlink created at /usr/local/bin/git"
        fi
    fi
else
    log_info "ai-aligned-git is already installed"

    # Check if symlink exists, create if not
    if [ ! -L "/usr/local/bin/git" ] && [ -f "$HOME/.local/bin/git" ]; then
        log_info "Creating symlink for existing ai-aligned-git installation..."
        sudo ln -sf "$HOME/.local/bin/git" /usr/local/bin/git || {
            log_warning "Failed to create symlink for ai-aligned-git"
        }
        if [ -L "/usr/local/bin/git" ]; then
            log_success "ai-aligned-git symlink created at /usr/local/bin/git"
        fi
    fi
fi

mark_completed "ai_aligned_git"
check_timeout

# Install uv if not present (it should be pre-installed in Terragon)
UV_CMD="uv"
log_info "Checking for uv package manager..."
log_info "Current PATH: $PATH"

if ! command -v uv &> /dev/null; then
    log_info "uv not found in PATH, attempting installation..."
    log_info "Running: curl -LsSf https://astral.sh/uv/install.sh | sh"
    curl -LsSf https://astral.sh/uv/install.sh 2>&1 | tee -a "$LOG_FILE" | sh 2>&1 | tee -a "$LOG_FILE" || {
        exit_code=$?
        log_error "Failed to install uv, exit code: $exit_code"
        exit 1
    }
    export PATH="$HOME/.local/bin:$PATH"
    log_info "Updated PATH: $PATH"

    # Source the uv environment script if it exists
    if [ -f "$HOME/.local/bin/env" ]; then
        log_info "Sourcing uv environment script at $HOME/.local/bin/env..."
        source "$HOME/.local/bin/env"
    else
        log_info "No uv environment script found at $HOME/.local/bin/env"
    fi

    # Verify uv is now available
    if ! command -v uv &> /dev/null; then
        log_info "uv not found in PATH after installation, checking explicit location..."
        log_info "Checking for uv at: $HOME/.local/bin/uv"

        if [ -x "$HOME/.local/bin/uv" ]; then
            log_info "Found uv executable at $HOME/.local/bin/uv"
            log_info "File details: $(ls -la $HOME/.local/bin/uv)"

            # Create symlink to make uv available system-wide
            log_info "Creating symlink to make uv available in PATH..."
            log_info "Running: sudo ln -sf $HOME/.local/bin/uv /usr/local/bin/uv"
            sudo ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv 2>&1 | tee -a "$LOG_FILE" || {
                exit_code=$?
                log_warning "Failed to create symlink, exit code: $exit_code"
                log_warning "Will use explicit path: $HOME/.local/bin/uv"
                UV_CMD="$HOME/.local/bin/uv"
            }

            # Check if symlink worked
            if command -v uv &> /dev/null; then
                log_success "uv is now available in PATH at: $(which uv)"
                log_info "uv version: $(uv --version 2>&1)"
            else
                log_info "uv still not in PATH, using explicit path"
                UV_CMD="$HOME/.local/bin/uv"
                log_info "Testing uv at explicit path: $($UV_CMD --version 2>&1)"
            fi
        else
            log_error "Cannot find uv executable at $HOME/.local/bin/uv after installation"
            log_info "Contents of $HOME/.local/bin:"
            ls -la "$HOME/.local/bin/" 2>&1 | tee -a "$LOG_FILE" || log_warning "Cannot list $HOME/.local/bin"
            exit 1
        fi
    else
        log_success "uv successfully installed and available at: $(which uv)"
        log_info "uv version: $(uv --version 2>&1)"
    fi
else
    log_info "uv is already available at: $(which uv)"
    log_info "uv version: $(uv --version 2>&1)"

    # Check if uv is in user's local bin but not symlinked to system-wide location
    if [ -x "$HOME/.local/bin/uv" ] && [ ! -L "/usr/local/bin/uv" ]; then
        log_info "Found uv at $HOME/.local/bin/uv but no system-wide symlink exists"
        log_info "Creating symlink for existing uv installation..."
        log_info "Running: sudo ln -sf $HOME/.local/bin/uv /usr/local/bin/uv"
        sudo ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv 2>&1 | tee -a "$LOG_FILE" || {
            exit_code=$?
            log_warning "Failed to create symlink for uv, exit code: $exit_code"
        }
        if [ -L "/usr/local/bin/uv" ]; then
            log_success "uv symlink created at /usr/local/bin/uv"
            log_info "Symlink details: $(ls -la /usr/local/bin/uv)"
        fi
    elif [ -L "/usr/local/bin/uv" ]; then
        log_info "System-wide uv symlink already exists at /usr/local/bin/uv"
        log_info "Symlink details: $(ls -la /usr/local/bin/uv)"
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
for step in python_check jq_install gh_workflow_peek ai_aligned_git uv_install directories venv_create venv_activate pip_upgrade dependencies env_file pre_commit db_init; do
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

# Log final summary
log_info ""
log_info "=================================================="
log_info "Setup log saved to: $LOG_FILE"
log_info "To view the log: cat $LOG_FILE"
log_info "=================================================="
log_info "  - 'make test' to run tests"
log_info "  - 'make help' to see all available commands"

# Return success
exit 0
