# Windows Deployment Guide

Deploy FantasyFolio on Windows using Docker Desktop.

## Prerequisites

1. **Docker Desktop for Windows**
   - Download: https://www.docker.com/products/docker-desktop/
   - Ensure WSL2 backend is enabled (Settings → General → Use WSL 2)
   - Allocate sufficient resources (Settings → Resources → 8GB+ RAM, 4+ CPUs)

2. **Git for Windows**
   - Download: https://git-scm.com/download/win

3. **Storage**
   - ~5GB for Docker image
   - Space for thumbnails (estimate: 100MB per 10,000 models)

## Quick Start

### 1. Clone the Repository

```powershell
git clone https://github.com/diminox-kullwinder/fantasyfolio.git
cd fantasyfolio
```

### 2. Configure Environment

```powershell
# Copy example config
copy .env.example .env

# Edit with your paths
notepad .env
```

Edit `.env` with your asset paths:
```bash
MODELS_PATH=D:/3D-Models
PDF_PATH=D:/PDFs
SECRET_KEY=your-random-secret-key-here
FAST_WORKERS=18
SLOW_WORKERS=4
```

### 3. Start FantasyFolio

```powershell
# Pull the pre-built image and start
docker compose up -d
```

### 4. Access the Web UI

Open http://localhost:8888 in your browser.

## Configuration

### Asset Paths

| Variable | Description | Example |
|----------|-------------|---------|
| `MODELS_PATH` | 3D models directory | `D:/3D-Models` |
| `PDF_PATH` | PDF documents directory | `D:/PDFs` |

**Note**: Use forward slashes (`/`) or double backslashes (`\\`) in paths.

### Thumbnail Daemon

Tune for your CPU:

| CPU | FAST_WORKERS | SLOW_WORKERS |
|-----|--------------|--------------|
| Ryzen 9 5900 (12c) | 18 | 4 |
| Intel i7 (8c) | 12 | 3 |
| Intel i5 (6c) | 8 | 2 |
| Low-end (4c) | 4 | 1 |

### SSH Access for Remote Support

The container exposes SSH on port 2222:

```bash
# From remote machine (Hal's access)
ssh -p 2222 root@YOUR_WINDOWS_IP
# Password: fantasyfolio
```

**To find your Windows IP**:
```powershell
ipconfig
# Look for IPv4 Address under your network adapter
```

## Managing the Container

### View Logs

```powershell
# All logs
docker compose logs -f

# Just the app
docker compose logs -f fantasyfolio
```

### Restart Services

```powershell
docker compose restart
```

### Stop

```powershell
docker compose down
```

### Update to Latest Version

```powershell
git pull
docker compose pull
docker compose up -d
```

## Database Migration

If migrating from a Mac/Linux installation:

1. Copy your existing `dam.db` to a location on Windows
2. Update `.env`:
   ```bash
   FANTASYFOLIO_DATABASE_PATH=/path/to/dam.db
   ```
3. File paths in the database reference the original paths. You may need to:
   - Re-index if paths changed
   - Or update the `file_path` column in the database

## Troubleshooting

### Container won't start

```powershell
# Check logs
docker compose logs

# Verify Docker is running
docker info
```

### Can't access web UI

1. Check container is running: `docker compose ps`
2. Check port isn't blocked by firewall
3. Try http://127.0.0.1:8888 instead of localhost

### Thumbnails not rendering

1. Verify MODELS_PATH is correct
2. Check daemon logs: `docker compose logs fantasyfolio | grep thumbnail`
3. Ensure stl-thumb is working: 
   ```powershell
   docker compose exec fantasyfolio stl-thumb --version
   ```

### Permission denied on volumes

Docker Desktop should handle permissions automatically. If issues persist:
1. Right-click Docker Desktop → Settings → Resources → File Sharing
2. Add your asset directories to the list

## Performance Tips

1. **Use local storage**: Local SSD is 10-50x faster than network shares
2. **Tune workers**: Match FAST_WORKERS to your CPU core count × 1.5
3. **Allocate RAM**: Give Docker Desktop at least 8GB for large libraries
4. **SSD for thumbnails**: Store the thumbnail volume on SSD if possible
