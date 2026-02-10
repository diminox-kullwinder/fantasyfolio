# FantasyFolio - 3D Print & RPG Asset Manager
# Production-ready container with SSH access

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
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
    wget \
    # Build tools for stl-thumb
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Install stl-thumb via cargo (simpler than multi-stage)
RUN cargo install stl-thumb \
    && cp /root/.cargo/bin/stl-thumb /usr/local/bin/ \
    && rm -rf /root/.cargo /root/.rustup

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Configure SSH
RUN mkdir -p /var/run/sshd \
    && echo 'root:fantasyfolio' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Copy application code
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
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8888/api/system/health || exit 1

# Expose ports
EXPOSE 8888 22

# Start supervisor (manages Flask app + SSH)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
