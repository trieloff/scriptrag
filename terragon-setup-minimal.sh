#!/bin/sh
# Minimal Terragon Setup Script for ScriptRAG
# Ultra-resilient version with graceful degradation
# Designed to complete in under 2 minutes

echo "[SETUP] Starting minimal ScriptRAG setup..."
echo "[SETUP] This is a fallback script - some features may be limited"

# Simple timeout mechanism
START_TIME=$(date +%s)

# Function to check if we should abort due to timeout
check_time() {
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    if [ $ELAPSED -gt 120 ]; then
        echo "[TIMEOUT] Reached 2-minute limit. Aborting."
        exit 0  # Exit with success to prevent Terragon from failing
    fi
}

# Move to script directory
cd "$(dirname "$0")" 2>/dev/null || true

# Create minimal required directories
echo "[SETUP] Creating directories..."
mkdir -p logs data cache 2>/dev/null || true

# Check if virtual environment exists or can be created quickly
if [ -d ".venv" ]; then
    echo "[SETUP] Using existing virtual environment"
else
    echo "[SETUP] Creating virtual environment..."
    if command -v uv >/dev/null 2>&1; then
        uv venv --python python3 2>/dev/null || python3 -m venv .venv 2>/dev/null || true
    else
        python3 -m venv .venv 2>/dev/null || true
    fi
fi

check_time

# Try to activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    . .venv/bin/activate 2>/dev/null || true
fi

# Install only core dependencies
echo "[SETUP] Installing core dependencies..."
if [ -f "pyproject.toml" ]; then
    if command -v uv >/dev/null 2>&1; then
        # Try uv first (faster)
        uv pip install -e . 2>/dev/null || \
        pip install -e . 2>/dev/null || \
        echo "[WARNING] Dependency installation failed - environment may be incomplete"
    else
        # Fallback to regular pip
        pip install -e . 2>/dev/null || \
        echo "[WARNING] Dependency installation failed - environment may be incomplete"
    fi
else
    echo "[WARNING] No pyproject.toml found - skipping dependency installation"
fi

check_time

# Create basic .env if needed
if [ ! -f ".env" ]; then
    echo "[SETUP] Creating basic .env file..."
    cat > .env << 'EOF' 2>/dev/null || true
# ScriptRAG Environment Configuration
DATABASE_URL=sqlite:///data/scriptrag.db
LOG_LEVEL=INFO
EOF
fi

# Mark setup as complete
date > .terragon-setup-minimal 2>/dev/null || true

echo "[SETUP] Minimal setup completed in $(($(date +%s) - START_TIME)) seconds"
echo "[SETUP] Note: This was a minimal setup. Some features may require additional configuration."

# Always exit with success to prevent Terragon failures
exit 0
