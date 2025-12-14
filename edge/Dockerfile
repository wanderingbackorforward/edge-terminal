# Multi-stage Dockerfile for Shield Tunneling Edge Platform
# Optimized for production deployment on edge devices

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY edge/requirements.txt .

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Allow host UID/GID to be injected at build time so bind-mounted configs remain readable
ARG EDGE_UID=1000
ARG EDGE_GID=1000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    LOG_LEVEL=INFO \
    DB_PATH=/app/data/edge.db

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user matching host UID/GID (permissions for bind mounts)
RUN groupadd -g ${EDGE_GID} tunnel && \
    useradd -r -u ${EDGE_UID} -g tunnel tunnel

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY edge/ /app/edge/

# Copy migrations from project root
COPY database/migrations/edge/ /app/database/migrations/edge/

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R ${EDGE_UID}:${EDGE_GID} /app

# Copy entrypoint script
COPY edge/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default entrypoint/command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "edge.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
