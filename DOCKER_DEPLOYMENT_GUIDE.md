# DAM Docker Deployment - Complete Guide

This guide provides complete instructions for deploying the Digital Asset Manager (DAM) using Docker, based on real-world testing.

## Prerequisites

- Docker Engine 20.10+ or Docker Desktop
- Docker Compose v2.0+
- 4GB+ RAM recommended
- 10GB+ disk space for content libraries

### Verify Docker Setup

```bash
# Check Docker version
docker --version
docker-compose --version

# Verify Docker daemon is running
docker ps

# If you get permission denied on macOS/Linux:
# macOS: Start Docker Desktop from Applications
# Linux: sudo usermod -aG docker $USER && newgrp docker
```

## Pre-Deployment Checklist

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/diminox-kullwinder/dam.git
cd dam

# Verify files
ls -la Dockerfile docker-compose.yml config/.env.example
```

**Troubleshooting GitHub Access:**
- **HTTPS Clone:** Requires GitHub Personal Access Token
  ```bash
  git clone https://github.com/diminox-kullwinder/dam.git
  # When prompted for password, use: ghp_xxxxxxxxxxxx
  ```
- **SSH Clone:** Requires SSH key configured
  ```bash
  ssh-keygen -t ed25519 -C "your-email@example.com"
  cat ~/.ssh/id_ed25519.pub  # Add to GitHub SSH keys
  git clone git@github.com:diminox-kullwinder/dam.git
  ```

### 2. Configure Environment Variables

```bash
# Copy example configuration
cp config/.env.example .env

# Edit with your settings (required for production)
nano .env  # or vi .env
```

**Critical Variables:**

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `DAM_ENV` | Yes | Environment mode | `production` |
| `DAM_SECRET_KEY` | Yes (prod) | Flask session key | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DAM_PORT` | No | Server port | `8888` |
| `PDF_LIBRARY` | No | PDF mount path | `/Volumes/Documents/PDFs` |
| `MODELS_LIBRARY` | No | 3D models mount | `/Volumes/Documents/3D-Models` |

### 3. Prepare Content Directories

```bash
# Verify your content libraries exist
ls -la /path/to/pdfs
ls -la /path/to/3d-models

# Or create test directories
mkdir -p ~/Documents/dam-pdfs
mkdir -p ~/Documents/dam-models

# Set permissions (if needed)
chmod +rx ~/Documents/dam-pdfs
chmod +rx ~/Documents/dam-models
```

## Build Docker Image

```bash
# Build the image (this takes 2-3 minutes)
docker build -t dam .

# Verify build succeeded
docker images | grep dam
```

**Troubleshooting Build Issues:**

```bash
# If build fails due to network:
docker build --network host -t dam .

# If build fails due to pymu PDF:
# Check that libmupdf-dev is installed in Dockerfile

# Rebuild without cache:
docker build --no-cache -t dam .
```

## Run with Docker Compose

### Option A: Development (Recommended for Testing)

```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f dam

# Stop services
docker-compose down
```

### Option B: Production

```bash
# Set environment variables
export DAM_ENV=production
export DAM_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export PDF_LIBRARY=/path/to/pdfs
export MODELS_LIBRARY=/path/to/models

# Start with explicit env vars
docker-compose -f docker-compose.yml up -d

# Verify health
curl http://localhost:8888/health
```

### Option C: Manual Docker Run

```bash
# Without compose (useful for custom setups)
docker run -d \
  --name dam \
  -p 8888:8888 \
  -e DAM_ENV=production \
  -e DAM_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v /path/to/pdfs:/content/pdfs:ro \
  -v /path/to/models:/content/models:ro \
  dam
```

## Access the Application

### Initial Access

```bash
# Open in browser
http://localhost:8888

# Check if healthy
curl http://localhost:8888/health
```

### Configure Content Paths

1. Open http://localhost:8888
2. Click Settings (gear icon)
3. Enter PDF library path: `/content/pdfs`
4. Enter 3D models path: `/content/models`
5. Click Save

### Index Assets

1. Click "Index" button in Settings
2. Select content type (PDF or 3D Models)
3. Wait for indexing to complete (watch logs)
4. Browse your assets in the library

## Monitoring & Debugging

### View Logs

```bash
# Real-time logs
docker-compose logs -f dam

# Last 100 lines
docker-compose logs --tail=100 dam

# Specific time range
docker-compose logs --since 10m dam
```

### Common Issues

**Issue:** Port 8888 already in use
```bash
# Change port in docker-compose.yml or use different port
docker run -p 9999:8888 dam
# Access at http://localhost:9999
```

**Issue:** Volume mount permission denied
```bash
# Check mount permissions
docker-compose exec dam ls -la /content/pdfs

# Fix permissions on host
chmod +r /path/to/pdfs
chmod +rx /path/to/pdfs  # directories need execute
```

**Issue:** Database locked
```bash
# Restart service
docker-compose restart dam

# Or reinitialize
docker-compose exec dam python -m dam.cli init-db
```

**Issue:** Indexing hangs
```bash
# Check logs for errors
docker-compose logs dam | grep -i error

# Manually index specific directory
docker-compose exec dam python -m dam.cli index-pdfs /content/pdfs
```

### Container Inspection

```bash
# Enter container shell
docker-compose exec dam bash

# Check filesystem
df -h
ls -la /app/data

# Test database
python -m dam.cli stats

# Exit
exit
```

## Data Persistence

### Backup Data

```bash
# Stop container
docker-compose down

# Backup database and logs
tar -czf dam-backup-$(date +%Y%m%d).tar.gz data/ logs/

# Start container again
docker-compose up -d
```

### Restore from Backup

```bash
# Stop container
docker-compose down

# Restore backup
tar -xzf dam-backup-20260205.tar.gz

# Verify files
ls -la data/dam.db

# Start container
docker-compose up -d
```

## Production Deployment

### Best Practices

1. **Use environment variables** for secrets
2. **Set DAM_SECRET_KEY** to random 32-char string
3. **Use read-only mounts** for content (`/content/pdfs:ro`)
4. **Enable data persistence** via named volumes
5. **Use reverse proxy** (Nginx) for TLS/SSL
6. **Set resource limits**

### Example Production Setup

```yaml
version: '3.8'
services:
  dam:
    image: dam:latest
    container_name: dam-prod
    restart: unless-stopped
    ports:
      - "127.0.0.1:8888:8888"  # Localhost only, use proxy
    environment:
      DAM_ENV: production
      DAM_SECRET_KEY: ${DAM_SECRET_KEY}
      DAM_LOG_LEVEL: WARNING
    volumes:
      - dam-data:/app/data
      - dam-logs:/app/logs
      - ${PDF_LIBRARY}:/content/pdfs:ro
      - ${MODELS_LIBRARY}:/content/models:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

volumes:
  dam-data:
  dam-logs:
```

## Cleanup

```bash
# Stop containers
docker-compose down

# Remove images
docker rmi dam

# Remove volumes (WARNING: deletes data)
docker volume prune

# Remove all dangling data
docker system prune
```

## Support & Troubleshooting

### Check Container Status

```bash
docker-compose ps

# Status legend:
# - Up X minutes: Running normally
# - Exited: Container crashed, check logs
# - Restarting: Stuck in restart loop
```

### Verify Network

```bash
# Check if container can reach internet
docker-compose exec dam curl -I https://github.com

# Check DNS
docker-compose exec dam nslookup google.com
```

### Performance Issues

```bash
# Check container resource usage
docker stats

# Check disk space in container
docker-compose exec dam df -h

# Check database file size
docker-compose exec dam ls -lh /app/data/dam.db
```

## Next Steps

- Configure content paths via web UI
- Index your PDF and 3D model libraries
- Set up Nginx reverse proxy for production
- Configure backups
- Set up monitoring/alerting

---

**Questions?** Check the main README.md or create an issue on GitHub.
