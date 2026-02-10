# FantasyFolio - 3D Print & RPG Asset Manager
# Multi-stage build with stl-thumb, SSH, and supervisor

# =============================================================================
# Stage 1: Build stl-thumb from source (Rust)
# =============================================================================
FROM rust:1.75-slim as stl-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN cargo install stl-thumb --version 0.5.0

# =============================================================================
# Stage 2: Build Python dependencies
# =============================================================================
FROM python:3.12-slim as py-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================================================
# Stage 3: Production image
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PDF rendering
    libmupdf-dev \
    fonts-dejavu-core \
    # SSH server for remote debugging
    openssh-server \
    # Git for pulling updates
    git \
    # Process management
    supervisor \
    # Utilities
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy stl-thumb from builder
COPY --from=stl-builder /usr/local/cargo/bin/stl-thumb /usr/local/bin/stl-thumb

# Copy Python packages from builder
COPY --from=py-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Configure SSH
RUN mkdir -p /var/run/sshd \
    && echo 'root:fantasyfolio' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Copy application code (can be overridden by volume mount for dev)
COPY fantasyfolio/ /app/fantasyfolio/
COPY scripts/ /app/scripts/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY wsgi.py /app/

# Create directories
RUN mkdir -p /app/data /app/logs /app/thumbnails/pdf /app/thumbnails/3d

# Supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Environment
ENV FANTASYFOLIO_ENV=production
ENV FANTASYFOLIO_HOST=0.0.0.0
ENV FANTASYFOLIO_PORT=8888
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8888/api/system/health || exit 1

# Expose ports
EXPOSE 8888 22

# Start supervisor (manages Flask app + SSH)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
