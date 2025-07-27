# Multi-stage Dockerfile for ScriptRAG
# Optimized for small image size and fast builds using uv

# Base stage with Python and system dependencies
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    sqlite3 \
    libsqlite3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Development stage - includes all dev dependencies
FROM base as development

# Copy dependency files
COPY pyproject.toml ./
COPY src/scriptrag/__init__.py ./src/scriptrag/

# Install all dependencies including dev
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e ".[dev,test,docs]"

# Copy source code
COPY . .

# Activate virtual environment by default
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install pre-commit hooks
RUN pre-commit install || true

# Default command for development
CMD ["bash"]

# Builder stage - builds the application
FROM base as builder

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./
COPY src ./src

# Build the package
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install --no-deps . && \
    uv pip install -r <(uv pip compile pyproject.toml --no-deps)

# Production stage - minimal runtime image
FROM python:3.11-slim as production

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 scriptrag

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/src ./src
COPY --from=builder /app/pyproject.toml ./

# Copy default configuration
COPY config.yaml ./
COPY examples ./examples

# Set ownership
RUN chown -R scriptrag:scriptrag /app

# Switch to non-root user
USER scriptrag

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV SCRIPTRAG_ENV=production

# Expose ports for API and MCP server
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import scriptrag; print('healthy')" || exit 1

# Default command runs the API server
CMD ["python", "-m", "scriptrag", "server", "api", "--host", "0.0.0.0", "--port", "8000"]

# Test stage - for running tests in CI
FROM development as test

# Run all quality checks and tests
RUN make check

# MCP server stage - specialized for MCP server deployment
FROM production as mcp-server

# Override default command to run MCP server
CMD ["python", "-m", "scriptrag.mcp_server"]