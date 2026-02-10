# FantasyFolio Rebrand & Containerization Plan

## Executive Summary

**Goal**: Transform DAM → FantasyFolio, then containerize for deployment on 64-core Windows PC.

**Scope**:
- Phase 1: Code/naming rebrand only (no GUI changes)
- Phase 2: Docker containerization with local rendering

---

## Phase 1: Rebrand to FantasyFolio

### 1.1 Rename Python Package Directory

**What**: Rename `dam/` folder to `fantasyfolio/`

```bash
# Files to move
dam/                    → fantasyfolio/
├── __init__.py
├── __main__.py
├── app.py
├── cli.py
├── config.py
├── api/
├── core/
├── indexer/
├── services/
└── utils/
```

**Effort**: 5 min

---

### 1.2 Update All Python Imports (164 occurrences)

**What**: Find/replace all `from dam` and `import dam` statements

**Files affected**:
| Location | Count (approx) |
|----------|----------------|
| `fantasyfolio/*.py` | 40 |
| `fantasyfolio/api/*.py` | 35 |
| `fantasyfolio/core/*.py` | 25 |
| `fantasyfolio/indexer/*.py` | 20 |
| `fantasyfolio/services/*.py` | 30 |
| `tests/*.py` | 10 |
| `scripts/*.py` | 4 |

**Pattern**:
```python
# Before
from dam.config import Config
from dam.core.database import get_db

# After
from fantasyfolio.config import Config
from fantasyfolio.core.database import get_db
```

**Effort**: 20 min (mostly automated find/replace)

---

### 1.3 Update Configuration

**Files**:

#### `fantasyfolio/config.py`
```python
# Before
APP_NAME = "Digital Asset Manager"
SECRET_KEY = os.environ.get("DAM_SECRET_KEY", ...)
DATABASE_PATH = Path(os.environ.get("DAM_DATABASE_PATH", ...))

# After
APP_NAME = "FantasyFolio"
SECRET_KEY = os.environ.get("FANTASYFOLIO_SECRET_KEY", os.environ.get("DAM_SECRET_KEY", ...))
DATABASE_PATH = Path(os.environ.get("FANTASYFOLIO_DATABASE_PATH", os.environ.get("DAM_DATABASE_PATH", ...)))
```

#### `.env.local`, `.env.uat`, `config/.env.example`
```bash
# Support both old and new env vars (backward compat)
FANTASYFOLIO_DATABASE_PATH=/path/to/db
FANTASYFOLIO_ENV=development
FANTASYFOLIO_PORT=8008
```

**Effort**: 15 min

---

### 1.4 Update CLI Entry Points

**Files**: `fantasyfolio/cli.py`, `fantasyfolio/__main__.py`

```python
# Before
@click.group()
def dam():
    """DAM - Digital Asset Manager CLI"""

# After
@click.group()
def fantasyfolio():
    """FantasyFolio - 3D Print Asset Manager"""
```

**Also update**:
- `wsgi.py` - Flask app import
- `start-server.sh` - startup script
- `start-uat.sh` - UAT startup

**Effort**: 10 min

---

### 1.5 Update Documentation

**Files to update**:
| File | Changes |
|------|---------|
| `README.md` | Title, description, all "DAM" references |
| `CHANGELOG.md` | Keep history, add rebrand note |
| `SETUP_GUIDE.md` | Installation instructions |
| `DOCKER_DEPLOYMENT_GUIDE.md` | Container names, env vars |
| `docs/*.md` | Any DAM references |
| `LICENSE` | Project name (if mentioned) |

**Effort**: 20 min

---

### 1.6 Update Templates & Frontend

**Files**: `templates/index.html`

```html
<!-- Before -->
<title>Digital Asset Manager</title>
<h1>DAM</h1>

<!-- After -->
<title>FantasyFolio</title>
<h1>FantasyFolio</h1>
```

**CSS classes** (can keep for now, rename in GUI phase):
- `.ssh-dam-key-row` → keep or rename
- `.dam-key-status` → keep or rename

**Effort**: 10 min

---

### 1.7 Update Docker Files

**Files**: `Dockerfile`, `docker-compose.yml`

```dockerfile
# Before
COPY dam/ dam/
ENV DAM_ENV=production
CMD ["python", "-m", "dam.cli", "run"]

# After
COPY fantasyfolio/ fantasyfolio/
ENV FANTASYFOLIO_ENV=production
CMD ["python", "-m", "fantasyfolio.cli", "run"]
```

```yaml
# docker-compose.yml
services:
  fantasyfolio:  # was: dam
    container_name: fantasyfolio
    environment:
      - FANTASYFOLIO_ENV=production
```

**Effort**: 10 min

---

### 1.8 Update Tests

**Files**: `tests/*.py`

```python
# Update imports
from fantasyfolio.core.database import get_db
```

**Effort**: 5 min

---

### 1.9 GitHub Repository Migration

**Strategy**: New repo for FantasyFolio, deprecate old DAM repo

#### Step 1: Create New Repository
```bash
# Create new repo on GitHub
gh repo create diminox-kullwinder/fantasyfolio --public --description "FantasyFolio - 3D Print & RPG Asset Manager"

# Or via GitHub web UI
```

#### Step 2: Push Rebranded Code
```bash
cd /Users/claw/projects/dam  # (now fantasyfolio)

# Add new remote
git remote add fantasyfolio https://github.com/diminox-kullwinder/fantasyfolio.git

# Push all branches and tags
git push fantasyfolio master --tags
git push fantasyfolio --all

# Update origin to point to new repo
git remote set-url origin https://github.com/diminox-kullwinder/fantasyfolio.git
git remote remove fantasyfolio
```

#### Step 3: Deprecate Old DAM Repo

**Update DAM README.md**:
```markdown
# ⚠️ DEPRECATED - See FantasyFolio

This project has been renamed and moved to **[FantasyFolio](https://github.com/diminox-kullwinder/fantasyfolio)**.

DAM (Digital Asset Manager) was the proof-of-concept version. All future development continues under the FantasyFolio name.

## Migration

If you have an existing DAM installation:
1. Clone the new repo: `git clone https://github.com/diminox-kullwinder/fantasyfolio.git`
2. Your existing database is compatible — just update the `FANTASYFOLIO_DATABASE_PATH` env var
3. See [Migration Guide](https://github.com/diminox-kullwinder/fantasyfolio/docs/MIGRATION.md)

---

*This repository is archived and will receive no further updates.*
```

#### Step 4: Archive DAM Repo
```bash
# Via GitHub CLI
gh repo archive diminox-kullwinder/dam --yes

# Or via GitHub web: Settings → Archive this repository
```

**Effort**: 15 min

---

### 1.10 Validation & Testing (Phase 1)

**What**: Verify rebrand is complete and functional before GitHub migration

#### Automated Tests
```bash
# Run test suite
cd /Users/claw/projects/fantasyfolio
source .venv/bin/activate
pytest tests/ -v
```

#### Manual Validation Checklist

| Check | Command / Action | Expected |
|-------|------------------|----------|
| CLI starts | `python -m fantasyfolio.cli run` | Server on :8008 |
| Web UI loads | Browser → `https://localhost:8008` | Page renders |
| Title correct | Inspect `<title>` tag | "FantasyFolio" |
| Header correct | Visual check | "FantasyFolio" in header |
| API works | `curl https://localhost:8008/api/system/health -k` | `{"status": "ok"}` |
| 3D browse works | Navigate to 3D Models | Folder tree loads |
| PDF browse works | Navigate to PDFs | Folder tree loads |
| Search works | Search for known term | Results return |
| Settings page | Open Settings modal | No errors |

#### Code Grep Validation
```bash
# Check for leftover "DAM" references in user-visible strings
grep -ri "digital asset manager" fantasyfolio/ templates/ --include="*.py" --include="*.html"
# Should return 0 results

# Check imports are clean
grep -r "from dam\." fantasyfolio/ tests/ scripts/
# Should return 0 results
```

#### Env Var Backward Compatibility
```bash
# Test old env vars still work
DAM_DATABASE_PATH=/tmp/test.db python -m fantasyfolio.cli run
# Should start (backward compat)

# Test new env vars work
FANTASYFOLIO_DATABASE_PATH=/tmp/test.db python -m fantasyfolio.cli run
# Should start
```

**Effort**: 20 min

---

### Phase 1 Summary

| Task | Files | Effort |
|------|-------|--------|
| 1.1 Rename package dir | 1 dir | 5 min |
| 1.2 Update imports | ~25 files | 20 min |
| 1.3 Update config | 4 files | 15 min |
| 1.4 Update CLI entry | 4 files | 10 min |
| 1.5 Update docs | 6 files | 20 min |
| 1.6 Update templates | 1 file | 10 min |
| 1.7 Update Docker | 2 files | 10 min |
| 1.8 Update tests | 3 files | 5 min |
| 1.9 GitHub migration | — | 15 min |
| **1.10 Validation & Testing** | — | **20 min** |
| **Total** | ~46 files | **~130 min** |

---

## Phase 2: Containerization

### 2.1 Dockerfile Updates

**Current state**: Basic Dockerfile exists but missing `stl-thumb` for 3D rendering.

**New Dockerfile**:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PDF rendering
    libmupdf-dev \
    fonts-dejavu-core \
    # 3D thumbnail rendering (stl-thumb)
    cargo \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install stl-thumb (Rust-based STL renderer)
RUN cargo install stl-thumb \
    && cp /root/.cargo/bin/stl-thumb /usr/local/bin/

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY fantasyfolio/ fantasyfolio/
COPY templates/ templates/
COPY static/ static/
COPY wsgi.py .

# Create directories
RUN mkdir -p data logs thumbnails/pdf thumbnails/3d

# Environment
ENV FANTASYFOLIO_ENV=production
ENV FANTASYFOLIO_HOST=0.0.0.0
ENV FANTASYFOLIO_PORT=8888
ENV PYTHONUNBUFFERED=1

EXPOSE 8888
CMD ["python", "-m", "fantasyfolio.cli", "run"]
```

**Effort**: 30 min (includes testing stl-thumb build)

---

### 2.2 Docker Compose for Windows

**Target**: Alienware Aurora R12 (Windows 11)
- CPU: AMD Ryzen 9 5900 (12 cores / 24 threads)
- RAM: 16 GB
- GPU: NVIDIA RTX 3080 (not used for rendering — stl-thumb is CPU-only)
- Storage: 1TB NVMe (boot) + 16TB+ SATA (assets)

**Container**: Linux (via Docker Desktop + WSL2)

```yaml
version: '3.8'

services:
  fantasyfolio:
    build: .
    container_name: fantasyfolio
    restart: unless-stopped
    ports:
      - "8888:8888"
    environment:
      - FANTASYFOLIO_ENV=production
      - FANTASYFOLIO_SECRET_KEY=${SECRET_KEY:-change-me}
      - FANTASYFOLIO_LOG_LEVEL=INFO
    volumes:
      # Database (persistent, on NVMe for speed)
      - fantasyfolio_data:/app/data
      
      # Thumbnails (persistent, can be regenerated)
      - fantasyfolio_thumbs:/app/thumbnails
      
      # Logs
      - fantasyfolio_logs:/app/logs
      
      # 3D Models - LOCAL on Windows SATA
      - D:\3D-Models:/content/models:ro
      
      # PDFs - LOCAL on Windows SATA (same volume)
      - D:\PDFs:/content/pdfs:ro
    
    deploy:
      resources:
        limits:
          cpus: '10'   # Leave 2 cores for OS + daemon
          memory: 8G
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/api/system/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Thumbnail daemon as separate service
  thumbnail-daemon:
    build: .
    container_name: fantasyfolio-thumbs
    restart: unless-stopped
    command: ["python", "scripts/thumbnail_daemon.py"]
    environment:
      - FANTASYFOLIO_ENV=production
      - FANTASYFOLIO_DATABASE_PATH=/app/data/fantasyfolio.db
      - CONTENT_ROOT=/content/models
      - THUMBNAIL_DIR=/app/thumbnails/3d
      - FAST_WORKERS=18    # 12 cores × 1.5 for I/O overlap
      - SLOW_WORKERS=4     # Dedicated for large files
      - SIZE_THRESHOLD_MB=30
      - FAST_TIMEOUT=120
      - SLOW_TIMEOUT=600
    volumes:
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
      - D:\3D-Models:/content/models:ro
    deploy:
      resources:
        limits:
          cpus: '10'
          memory: 6G
    depends_on:
      - fantasyfolio

volumes:
  fantasyfolio_data:
    driver: local
  fantasyfolio_thumbs:
    driver: local
  fantasyfolio_logs:
    driver: local
```

**Note**: Paths like `D:\3D-Models` work in Docker Desktop for Windows — it handles the WSL2 translation automatically.

**Effort**: 20 min

---

### 2.3 Thumbnail Daemon Container Entry Point

**What**: Ensure daemon runs properly in container with configurable paths

**Updates to `scripts/thumbnail_daemon.py`**:
```python
# Support container paths (defaults for local dev, overridden in container)
CONTENT_ROOT = os.environ.get("CONTENT_ROOT", "/content/models")
THUMBNAIL_DIR = os.environ.get("THUMBNAIL_DIR", "/app/thumbnails/3d")
PDF_ROOT = os.environ.get("PDF_ROOT", "/content/pdfs")
PDF_THUMBNAIL_DIR = os.environ.get("PDF_THUMBNAIL_DIR", "/app/thumbnails/pdf")

# Worker counts from env (tuned for Ryzen 9 5900 12c/24t)
FAST_WORKERS = int(os.environ.get("FAST_WORKERS", 18))
SLOW_WORKERS = int(os.environ.get("SLOW_WORKERS", 4))
SIZE_THRESHOLD_MB = int(os.environ.get("SIZE_THRESHOLD_MB", 30))
```

**Effort**: 15 min

---

### 2.4 Database Migration for Container

**What**: Ensure SQLite DB works with volume mounts

**Considerations**:
- SQLite file must be on named volume (not bind mount) for performance
- WAL mode works fine in containers
- Backup strategy: copy file from volume

**Migration script** (`scripts/migrate_to_container.py`):
```python
# Export current DB schema + data for container import
# Handle path remapping (Mac paths → container paths)
```

**Effort**: 30 min

---

### 2.5 Windows-Specific Considerations

| Issue | Solution |
|-------|----------|
| Line endings | `.gitattributes` with `* text=auto` |
| Path separators | Use `pathlib.Path` everywhere (already done) |
| Volume mounts | Use Windows paths in compose: `D:\3D-Models` |
| Docker Desktop | Ensure WSL2 backend for Linux containers |
| File permissions | Named volumes avoid permission issues |

**Effort**: 10 min (documentation)

---

### 2.6 Deployment Workflow & Documentation

**Workflow**: Mac (dev) → GitHub → Windows (prod)

```
┌─────────────────────────────────────────────────────────────────┐
│  DEVELOPMENT (Mac mini)                                         │
│  ├─ Hal: Code changes, Dockerfile, docker-compose.yml           │
│  ├─ Hal: Test build locally (docker build)                      │
│  ├─ Hal: Push to GitHub                                         │
│  └─ No direct Windows access                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ git push
┌─────────────────────────────────────────────────────────────────┐
│  GITHUB (diminox-kullwinder/fantasyfolio)                       │
│  └─ Source of truth for deployment                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ git pull
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION (Alienware Windows 11)                              │
│  ├─ Matthew: git pull                                           │
│  ├─ Matthew: docker compose build (builds Linux container)      │
│  ├─ Matthew: docker compose up -d                               │
│  ├─ Matthew: Shares SSH port for Hal remote access              │
│  └─ Hal: SSH into container for debugging/updates               │
└─────────────────────────────────────────────────────────────────┘
```

**Who Does What**:

| Task | Who | How |
|------|-----|-----|
| **Initial Setup** | Matthew | Clone repo, configure .env, first `docker compose up` |
| **Share SSH access** | Matthew | One-time: give Hal the LAN IP |
| **Code changes** | Hal | Push to GitHub from Mac |
| **Deploy code updates** | Hal | SSH in → `git pull` → `supervisorctl restart` |
| **Database migrations** | Hal | SSH in → `python -m fantasyfolio.cli migrate` |
| **Debugging** | Hal | SSH in → logs, DB queries, hot-fixes |
| **Dockerfile changes** | Hal → Matthew | Hal pushes, Matthew rebuilds container |
| **requirements.txt changes** | Hal → Matthew | Hal pushes, Matthew rebuilds container |
| **System issues** | Matthew | Docker Desktop, Windows, network |

**Matthew's Ongoing Role**: Minimal — just rebuild when Dockerfile/requirements change, handle Windows/Docker issues.

**Hal's Autonomy**: Full control over app code, deployments, migrations, and debugging via SSH.

---

### 2.6.1 SSH Access for Remote Debugging

**Add to Dockerfile**:
```dockerfile
# Install SSH server for remote debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd
RUN echo 'root:fantasyfolio' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# SSH port
EXPOSE 22
```

**Add to docker-compose.yml**:
```yaml
services:
  fantasyfolio:
    ports:
      - "8888:8888"
      - "2222:22"  # SSH access
    command: >
      sh -c "/usr/sbin/sshd && python -m fantasyfolio.cli run"
```

**Matthew's Setup** (one-time):
1. Get Windows machine's LAN IP (e.g., `192.168.1.100`)
2. Optionally: Set up port forwarding or Tailscale for remote access
3. Share IP + port with Hal

**Hal's Access**:
```bash
# SSH into container
ssh -p 2222 root@<windows-ip>
# Password: fantasyfolio (change in production)

# Once in, can:
# - View logs: tail -f /app/logs/*.log
# - Check DB: sqlite3 /app/data/fantasyfolio.db
# - Pull updates: cd /app && git pull
# - Restart app: supervisorctl restart fantasyfolio
# - Run migrations: python -m fantasyfolio.cli migrate
# - Check daemon: supervisorctl status thumbnail-daemon
```

**Security Note**: For LAN-only use, password auth is fine. For internet exposure, use SSH keys instead.

---

### 2.6.2 Self-Service Updates via SSH

**Key Change**: Mount code as volume + include git in container

This allows Hal to pull updates directly without Matthew needing to rebuild:

```yaml
# docker-compose.yml
services:
  fantasyfolio:
    volumes:
      # Mount code directory (persistent, updatable via git)
      - ./fantasyfolio:/app/fantasyfolio
      - ./scripts:/app/scripts
      - ./templates:/app/templates
      - ./static:/app/static
      
      # Data volumes (as before)
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
```

**Add to Dockerfile**:
```dockerfile
# Install git + supervisor for process management
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*
```

**Update Workflow**:
```
┌──────────────────────────────────────────────────────────────────┐
│  HAL (via SSH into container)                                    │
│                                                                  │
│  # Pull latest code                                              │
│  cd /app && git pull origin master                               │
│                                                                  │
│  # Restart services to pick up changes                           │
│  supervisorctl restart fantasyfolio                              │
│  supervisorctl restart thumbnail-daemon                          │
│                                                                  │
│  # Run migrations if needed                                      │
│  python -m fantasyfolio.cli migrate                              │
│                                                                  │
│  # Verify                                                        │
│  curl http://localhost:8888/api/system/health                    │
└──────────────────────────────────────────────────────────────────┘
```

**When Rebuild IS Needed**:
- Dockerfile changes (new system packages)
- requirements.txt changes (new Python packages)
- docker-compose.yml changes (new volumes, ports)

For these, Matthew runs:
```powershell
docker compose down
docker compose build
docker compose up -d
```

**Hal Can Handle Autonomously**:
- Python code changes (pull + restart)
- Template/static changes (pull + restart)
- Database migrations (pull + run migrate)
- Config changes (edit .env + restart)
- Debugging (logs, DB queries, hot-fixes)

---

### 2.6.2 Deployment Documentation

**New file**: `docs/WINDOWS_DEPLOYMENT.md`

Contents:
1. Prerequisites
   - Docker Desktop for Windows (WSL2 backend)
   - Git for Windows
   - ~20GB free disk for images
2. Initial Setup
   ```powershell
   git clone https://github.com/diminox-kullwinder/fantasyfolio.git
   cd fantasyfolio
   copy .env.example .env
   # Edit .env with your paths (D:\3D-Models, D:\PDFs)
   ```
3. Build & Run
   ```powershell
   docker compose build
   docker compose up -d
   ```
4. Verify
   - Web UI: http://localhost:8888
   - Check containers: `docker compose ps`
5. Database Migration (if importing from Mac)
   - Copy `dam.db` to Windows
   - Run path migration script
   - See `docs/DB_MIGRATION.md`
6. SSH Access for Remote Support
   - Container exposes port 2222
   - Share your LAN IP with Hal for debugging
7. Updates
   ```powershell
   git pull
   docker compose build
   docker compose up -d
   ```

**Effort**: 30 min

---

### 2.7 GitHub Container Registry & CI/CD

**What**: Publish pre-built images so users can pull and run without building

#### 2.7.1 Manual Push (Initial)

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u diminox-kullwinder --password-stdin

# Build with registry tag
docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:0.4.0 .
docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:latest .

# Push to registry
docker push ghcr.io/diminox-kullwinder/fantasyfolio:0.4.0
docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

#### 2.7.2 GitHub Actions Auto-Build (Recommended)

**File**: `.github/workflows/docker-publish.yml`

```yaml
name: Build and Push Docker Image

on:
  push:
    tags:
      - 'v*'  # Trigger on version tags

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

#### 2.7.3 Update docker-compose.yml for Users

```yaml
version: '3.8'

services:
  fantasyfolio:
    # Pull pre-built image instead of building locally
    image: ghcr.io/diminox-kullwinder/fantasyfolio:latest
    # build: .  # <-- commented out, not needed
    container_name: fantasyfolio
    restart: unless-stopped
    ports:
      - "8888:8888"
      - "2222:22"
    # ... rest of config
```

**Effort**: 30 min

---

### 2.8 Health Checks & Monitoring

**What**: Ensure container health is visible

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8888/api/system/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Add to `/api/system/health`**:
- Thumbnail daemon status
- Pending render count
- Database connection

**Effort**: 15 min

---

### 2.8 Validation & Testing (Phase 2)

**What**: Verify containerized deployment works end-to-end on Windows

#### Build Validation (Mac - pre-flight)
```bash
# Test Docker build completes
cd /Users/claw/projects/fantasyfolio
docker build -t fantasyfolio:test .

# Verify stl-thumb installed
docker run --rm fantasyfolio:test which stl-thumb
# Should return: /usr/local/bin/stl-thumb

# Test container starts
docker run --rm -p 8888:8888 fantasyfolio:test
# Should show Flask startup logs
```

#### Windows Deployment Validation

| Step | Command / Action | Expected |
|------|------------------|----------|
| Clone repo | `git clone https://github.com/diminox-kullwinder/fantasyfolio.git` | Success |
| Configure paths | Edit `.env` with `D:\3D-Models`, `D:\PDFs` | File saved |
| Build images | `docker compose build` | Both images built |
| Start services | `docker compose up -d` | 2 containers running |
| Check health | `docker compose ps` | Both "healthy" |
| Web UI | Browser → `http://localhost:8888` | FantasyFolio loads |
| Volume mounts | Check 3D folder tree | Shows local folders |
| PDF mounts | Check PDF folder tree | Shows local folders |

#### Thumbnail Daemon Validation

| Check | Command | Expected |
|-------|---------|----------|
| Daemon running | `docker logs fantasyfolio-thumbs` | Processing logs |
| Workers active | Look for "Fast lane" / "Slow lane" | 18 fast, 4 slow |
| Renders happening | `docker exec fantasyfolio-thumbs ls /app/thumbnails/3d \| wc -l` | Count increasing |
| DB updating | Check `has_thumbnail` count in DB | Count increasing |

#### Performance Validation

```bash
# Baseline: Record thumbnail count
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  "SELECT COUNT(*) FROM models WHERE has_thumbnail = 1"

# Wait 5 minutes

# Check progress
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  "SELECT COUNT(*) FROM models WHERE has_thumbnail = 1"

# Calculate: (new - old) / 5 = renders per minute
# Expected: 50-100+ per minute (local disk)
```

#### Database Migration Validation

| Check | How | Expected |
|-------|-----|----------|
| Model count matches | Compare Mac vs container | Same count |
| PDF count matches | Compare Mac vs container | Same count |
| Paths remapped | Query `file_path` column | Container paths (`/content/...`) |
| Thumbnails work | Browse UI, check images | Thumbnails display |

#### Persistence Validation

```bash
# Stop and restart
docker compose down
docker compose up -d

# Verify data persisted
# - Database still has all records
# - Thumbnails still exist
# - No re-indexing needed
```

**Effort**: 30 min

---

### Phase 2 Summary

| Task | Effort |
|------|--------|
| 2.1 Dockerfile with stl-thumb | 30 min |
| 2.2 Docker Compose for Windows | 20 min |
| 2.3 Daemon container support | 15 min |
| 2.4 Database migration | 30 min |
| 2.5 Windows considerations | 10 min |
| 2.6 Deployment workflow + SSH | 30 min |
| 2.7 GitHub Container Registry + CI/CD | 30 min |
| 2.8 Health checks | 15 min |
| **2.9 Validation & Testing** | **30 min** |
| **Total** | **~210 min (~3.5 hrs)** |

---

## Combined Timeline

| Phase | Tasks | Effort | Cumulative |
|-------|-------|--------|------------|
| Phase 1: Rebrand | 10 tasks | ~130 min | ~2.25 hrs |
| Phase 2: Containerize | 9 tasks | ~210 min | ~5.75 hrs |
| **Total** | 19 tasks | **~5.75 hours** | — |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Import breakage | Run tests after each major change |
| stl-thumb build fails | Pre-built binary fallback, or multi-stage build |
| Windows path issues | Test on actual Windows box early |
| Database corruption | Always snapshot before migration |
| Performance regression | Benchmark before/after with same dataset |

---

## Success Criteria

### Phase 1 Complete When:
- [ ] `python -m fantasyfolio.cli run` starts server
- [ ] All tests pass
- [ ] UI shows "FantasyFolio" title
- [ ] No "DAM" references in user-visible text
- [ ] New repo live at `github.com/diminox-kullwinder/fantasyfolio`
- [ ] Old DAM repo archived with deprecation notice

### Phase 2 Complete When:
- [ ] `docker compose up` starts both services on Windows
- [ ] Web UI accessible at localhost:8888
- [ ] Thumbnail daemon processes 3D models from local SATA
- [ ] PDF indexing works from local SATA
- [ ] Renders complete 10-50x faster than SMB (local disk)
- [ ] Database persists across container restarts
- [ ] Can migrate existing Mac database to container

---

*Created: 2026-02-09*
*Author: Hal*
