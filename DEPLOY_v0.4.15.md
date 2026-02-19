# FantasyFolio v0.4.15 Deployment Guide

**Release Date:** 2026-02-18  
**Git Tag:** v0.4.15  
**Docker Image:** `ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15`

---

## Pre-Deployment Checklist

- [x] All code changes committed to git
- [x] v0.4.15 tag created and pushed
- [x] CHANGELOG.md updated
- [x] Validation completed (10/10 tests passed)
- [x] Schema.sql synchronized with database
- [ ] Docker image built and pushed
- [ ] Windows deployment tested

---

## What's New in v0.4.15

### Major Features
1. **Volume-Based Navigation** - Folder tree organized by volume labels
2. **New Formats** - DAE, 3DS, PLY, X3D support added
3. **RAR Archives** - Extract models from RAR files
4. **GLTF Validation** - Prevents incomplete GLTF files
5. **folder_path Bug Fixed** - All models now appear in nav tree
6. **FBX Removed** - Unreliable format removed from support

### Breaking Changes
**None** - All changes are backward compatible

---

## Docker Build & Push

### Prerequisites
```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Or use Docker Desktop authentication
```

### Build Image
```bash
cd /Users/claw/projects/dam

# Build for current platform (Mac)
docker build -t fantasyfolio:0.4.15 .

# Build for multi-platform (Mac + Windows/Linux)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15 \
  -t ghcr.io/diminox-kullwinder/fantasyfolio:latest \
  --push .
```

### Tag and Push
```bash
# Tag with version
docker tag fantasyfolio:0.4.15 ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15

# Tag as latest
docker tag fantasyfolio:0.4.15 ghcr.io/diminox-kullwinder/fantasyfolio:latest

# Push both tags
docker push ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

### Verify Images
```bash
# Check images
docker images | grep fantasyfolio

# Inspect image
docker inspect ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15

# Test run (quick smoke test)
docker run --rm ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15 python -c "import fantasyfolio; print('OK')"
```

---

## Windows PC Deployment

### Method 1: Docker Compose (Recommended)

#### Step 1: Update docker-compose.yml
```yaml
services:
  fantasyfolio:
    image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15  # Update this line
    container_name: fantasyfolio
    ports:
      - "8008:8008"
    volumes:
      # Named volumes (data persists)
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
      - fantasyfolio_logs:/app/logs
      
      # Asset volumes (read-only recommended)
      - D:/3D-Assets:/volumes/3d-assets:ro
      - E:/Documents:/volumes/documents:ro
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped

volumes:
  fantasyfolio_data:
  fantasyfolio_thumbs:
  fantasyfolio_logs:
```

#### Step 2: Pull and Start
```powershell
# Pull latest image
docker-compose pull

# Stop old version
docker-compose down

# Start new version
docker-compose up -d

# Check logs
docker-compose logs -f fantasyfolio
```

#### Step 3: Verify Deployment
```powershell
# Check container status
docker ps | findstr fantasyfolio

# Check database schema (should have all columns)
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db ".schema models" | findstr "folder_path volume_id thumb_storage"

# Test API
curl -k https://localhost:8008/api/models/folder-tree
```

### Method 2: Direct Docker Run

```powershell
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15

docker run -d \
  --name fantasyfolio \
  -p 8008:8008 \
  -v fantasyfolio_data:/app/data \
  -v fantasyfolio_thumbs:/app/thumbnails \
  -v D:/3D-Assets:/volumes/3d-assets:ro \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
```

---

## Post-Deployment Configuration

### Step 1: Add Asset Volumes

1. Open https://localhost:8008
2. Navigate to Settings → Asset Locations
3. Click "Add Location"
4. Configure each volume:
   ```
   Name: 3D Assets
   Type: 3D Models
   Path: /volumes/3d-assets
   Read-only: ✓ (recommended)
   ```
5. Click "Save"

### Step 2: Index Assets

**Option A: Via UI**
1. Click "Index Now" button for each location
2. Monitor progress in UI
3. Thumbnails auto-generate in background

**Option B: Via API**
```bash
curl -X POST https://localhost:8008/api/index/directory \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/volumes/3d-assets",
    "recursive": true,
    "force": false,
    "duplicate_policy": "merge"
  }'
```

### Step 3: Verify Navigation

1. Open https://localhost:8008
2. Check nav tree shows:
   ```
   📁 3D Assets (volume label)
     └─ Fantasy/
     └─ Superhero/
     └─ Terrain/
   📁 Documents (volume label)
     └─ Projects/
     └─ Manuals/
   ```
3. Click volume root → should show all models in that volume
4. Click folder → should show models in that folder

### Step 4: Test Thumbnails

1. Click any folder with 3D models
2. Thumbnails should start generating automatically
3. Check thumbnail daemon: `docker exec fantasyfolio supervisorctl status thumbnail_daemon`
4. Expected: `thumbnail_daemon RUNNING pid X, uptime Y`

---

## Rollback Procedure

If issues occur, rollback to v0.4.14:

```powershell
# Stop current version
docker-compose down

# Update docker-compose.yml
# Change image to: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14

# Start previous version
docker-compose up -d
```

**Note:** No database changes were made in v0.4.15, so rollback is safe.

---

## Troubleshooting

### Nav Tree Not Showing Volume Labels

**Symptom:** Old flat folder structure instead of volume-grouped

**Solution:**
1. Clear browser cache
2. Hard reload: Ctrl+F5 (Windows) / Cmd+Shift+R (Mac)
3. Check API: `curl https://localhost:8008/api/models/folder-tree` should show `volume_label` fields

### Thumbnails Not Generating

**Check daemon status:**
```powershell
docker exec fantasyfolio supervisorctl status thumbnail_daemon
```

**Expected:** `RUNNING`

**If stopped:**
```powershell
docker exec fantasyfolio supervisorctl start thumbnail_daemon
```

### Missing Models in Nav Tree

**Symptom:** Some files indexed but don't appear in folders

**Solution:**
1. Check if `folder_path` is set:
   ```bash
   docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
     "SELECT COUNT(*) as missing FROM models WHERE folder_path IS NULL"
   ```
2. If missing, force re-index:
   ```bash
   curl -X POST https://localhost:8008/api/index/directory \
     -H "Content-Type: application/json" \
     -d '{"path": "/volumes/3d-assets", "force": true}'
   ```

### GLTF Files Not Appearing

**Expected:** Incomplete GLTF files (missing .bin or textures) are rejected

**Check validation:**
1. Look for `.gltf` files in asset folder
2. Check for companion files in same directory:
   - `scene.bin` or similar .bin files
   - `textures/` folder with PNG/JPG files
3. If missing, file is correctly rejected
4. **Solution:** Re-download complete GLTF package or use GLB format

### FBX Files Showing as "Unsupported"

**Expected:** FBX format removed in v0.4.15 due to unreliable rendering

**Solution:**
- Export FBX to OBJ: Universal, works everywhere
- Export FBX to GLB: Modern, self-contained
- Export FBX to DAE: Collada, industry standard

---

## Monitoring

### Check Container Logs
```powershell
# Real-time logs
docker-compose logs -f fantasyfolio

# Last 100 lines
docker-compose logs --tail=100 fantasyfolio

# Search for errors
docker-compose logs fantasyfolio | findstr ERROR
```

### Database Health
```powershell
# Count models
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  "SELECT COUNT(*) FROM models WHERE format != 'unsupported'"

# Check volumes
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  "SELECT id, label, COUNT(models.id) FROM volumes LEFT JOIN models ON models.volume_id = volumes.id GROUP BY volumes.id"

# Thumbnail coverage
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  "SELECT COUNT(*) as total, COUNT(thumb_storage) as with_thumbs, ROUND(COUNT(thumb_storage) * 100.0 / COUNT(*), 1) as percent FROM models WHERE format IN ('stl', 'obj', '3mf', 'ply', 'glb')"
```

### Performance Metrics
```powershell
# Container stats
docker stats fantasyfolio --no-stream

# Disk usage
docker system df -v | findstr fantasyfolio
```

---

## Support

**Documentation:** https://docs.openclaw.ai  
**Issues:** https://github.com/diminox-kullwinder/fantasyfolio/issues  
**Discord:** https://discord.com/invite/clawd

---

## Release Notes

**Full changelog:** See CHANGELOG.md in repository

**Key highlights:**
- ✅ Volume-based navigation
- ✅ 4 new 3D formats (DAE, 3DS, PLY, X3D)
- ✅ RAR archive extraction
- ✅ GLTF validation
- ✅ folder_path bug fixed
- ❌ FBX support removed

**Database:** No migration needed (all columns present since v0.4.11)

**Compatibility:** Backward compatible with v0.4.9+

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Status:** ⬜ Success | ⬜ Partial | ⬜ Rollback
