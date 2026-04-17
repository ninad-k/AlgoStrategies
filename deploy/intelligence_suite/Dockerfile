# ReySentinel — Multi-stage Docker Build
# ================================================
# Production-ready container for the trading engine and dashboards.

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY intelligence_suite/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

LABEL maintainer="AlgoStrategies Team"
LABEL description="ReySentinel — AI-Powered Trading Engine"

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY intelligence_suite/ /app/intelligence_suite/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/exports /app/data \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    CONFIG_PATH=/app/intelligence_suite/config.yaml \
    LOG_LEVEL=INFO

# Expose ports: main(8060), heatmap(8061), multi-account(8062)
EXPOSE 8060 8061 8062

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8060/api/health || exit 1

# Default entry point
CMD ["python", "-m", "intelligence_suite.app"]
