# ============================================================================
# Multi-Stage Dockerfile for DoclingServer
# Production-grade build optimized for size and security
# ============================================================================

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim as builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="DoclingServer"
LABEL description="Production-grade PDF document analysis microservice"
LABEL version="1.0.0"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=appuser:appuser api_server.py .
COPY --chown=appuser:appuser document_analyzer.py .

# Create data directories with proper permissions
RUN mkdir -p /app/data/input /app/data/output /app/data/temp /app/.docling && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment defaults (can be overridden via docker-compose or K8s)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=INFO \
    OUTPUT_DIR=/app/data/output \
    TEMP_DIR=/app/data/temp \
    DOCLING_CACHE_DIR=/app/.docling \
    MAX_FILE_SIZE_MB=100 \
    CORS_ORIGINS=* \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "api_server.py"]
