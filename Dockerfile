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
    # OpenGL software rendering (Mesa) for stl-thumb
    libgl1 \
    libgl1-mesa-dri \
    libegl1 \
    libosmesa6-dev \
    xvfb \
    xauth \
    # X11 libraries for stl-thumb windowing
    libxcursor1 \
    libxrandr2 \
    libxi6 \
    libxinerama1 \
    # Backup tool
    restic \
    # SFTP filesystem mount (Linux only)
    sshfs \
    # 3D model thumbnail renderer (container-friendly, supports STL/OBJ/3MF/GLTF)
    f3d \
    && rm -rf /var/lib/apt/lists/*

# Install stl-thumb from pre-built .deb packages (platform-aware)
COPY docker/binaries/stl-thumb_0.5.0_*.deb /tmp/
RUN dpkg -i /tmp/stl-thumb_0.5.0_$(dpkg --print-architecture).deb \
    && rm -f /tmp/stl-thumb_0.5.0_*.deb

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

# Copy schema to safe location (outside /app/data which may be a volume mount)
COPY data/schema.sql /app/schema.sql

# Copy entrypoint and supervisor config
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /app/entrypoint.sh

# Environment
ENV FANTASYFOLIO_ENV=production
ENV FANTASYFOLIO_HOST=0.0.0.0
ENV FANTASYFOLIO_PORT=8888
ENV FANTASYFOLIO_SECRET_KEY=change-me-in-production
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8888/api/system/health || exit 1

# Expose ports
EXPOSE 8888 22

# Entrypoint handles schema.sql copy for volume mounts
ENTRYPOINT ["/app/entrypoint.sh"]

# Start supervisor (manages Flask app + SSH)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
