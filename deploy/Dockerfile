FROM python:3.11-slim

# Metadata
LABEL maintainer="0xEkho"
LABEL description="ALE OmniSwitch MCP Server - Network automation via Model Context Protocol"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -r -u 10001 -m -s /bin/bash appuser

WORKDIR /app

# Copy ALL application files first (for pip install -e .)
COPY pyproject.toml requirements.txt README.md LICENSE /app/
COPY aos_server /app/aos_server
COPY config.example.yaml /app/config.example.yaml

# Install Python dependencies (editable mode needs source files present)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create directories for runtime data
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment defaults
ENV AOS_CONFIG_FILE=/app/config.yaml \
    AOS_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz').read()"

EXPOSE 8080

# Run the MCP server with uvicorn directly
CMD ["python", "-m", "uvicorn", "aos_server.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
