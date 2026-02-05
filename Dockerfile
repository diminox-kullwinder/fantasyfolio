# DAM - Digital Asset Manager
# Multi-stage build for smaller image

# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY dam/ dam/
COPY data/schema.sql data/
COPY static/ static/
COPY templates/ templates/

# Create directories
RUN mkdir -p data logs thumbnails/pdf thumbnails/3d

# Environment
ENV DAM_ENV=production
ENV DAM_HOST=0.0.0.0
ENV DAM_PORT=8888
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/health')" || exit 1

# Run
EXPOSE 8888
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8888", "dam.app:create_app()"]
