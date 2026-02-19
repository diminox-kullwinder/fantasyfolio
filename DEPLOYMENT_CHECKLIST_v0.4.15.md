# FantasyFolio v0.4.15 - Final Deployment Checklist

**Release Date:** 2026-02-18  
**Docker Image:** `ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15`  
**Git Tag:** v0.4.15  
**Digest:** sha256:5408107025960a3523c2d80416c06201e557c7f595908328c2c14642ad031b19

---

## Pre-Deployment Verification ✅

### Code & Git
- [x] All code changes committed
- [x] Git tag v0.4.15 created and pushed
- [x] GitHub repository updated (master branch)
- [x] CHANGELOG.md updated with v0.4.15 changes
- [x] Release notes created (GIT_COMMIT_MESSAGE_v0.4.15.txt)

### Docker Build
- [x] Docker image built successfully (2.74GB)
- [x] Image tagged: 0.4.15 + latest
- [x] Pushed to ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
- [x] Pushed to ghcr.io/diminox-kullwinder/fantasyfolio:latest
- [x] Digest verified: sha256:5408107025960a3523c2d80416c06201e557c7f595908328c2c14642ad031b19

### Testing (Mac Local)
- [x] 10/10 critical tests passed
- [x] Volume-based navigation working (3D + PDF)
- [x] 86 models indexed across 3 volumes
- [x] 90.4% thumbnail coverage (66/73)
- [x] No 404 errors on thumbnail requests
- [x] Server stable under load
- [x] PDF page viewing working
- [x] New formats tested (PLY, GLTF)

### Documentation
- [x] DEPLOY_v0.4.15.md created (deployment guide)
- [x] VALIDATION_RESULTS_2026-02-18.md (test results)
- [x] FINAL_VALIDATION_v0.4.9-v0.4.14.md (test plan)
- [x] DEPLOYMENT_CHECKLIST_v0.4.15.md (this file)

---

## Windows PC Deployment Steps

### Step 1: Pre-Deployment Preparation
- [ ] **Backup current database** (if upgrading from v0.4.14)
  ```powershell
  # Stop containers
  docker-compose down
  
  # Backup database
  docker run --rm -v fantasyfolio_data:/data -v D:/backups:/backup \
    alpine tar czf /backup/fantasyfolio-backup-$(date +%Y%m%d).tar.gz /data
  ```

- [ ] **Check disk space** (image is 2.74GB)
  ```powershell
  docker system df
  ```

- [ ] **Verify network access to asset volumes**
  - D:/ drive accessible
  - E:/ drive accessible
  - Network shares mounted (if using SMB/NFS)

### Step 2: Pull New Image
```powershell
# Pull v0.4.15
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15

# Verify image
docker images | findstr fantasyfolio
```

**Expected output:**
```
ghcr.io/diminox-kullwinder/fantasyfolio   0.4.15    <image-id>   2.74GB
```

### Step 3: Update docker-compose.yml
```yaml
services:
  fantasyfolio:
    image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15  # ← Update this line
    container_name: fantasyfolio
    ports:
      - "8008:8008"
    volumes:
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
      - fantasyfolio_logs:/app/logs
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

### Step 4: Deploy
```powershell
# Stop old version
docker-compose down

# Start new version
docker-compose up -d

# Verify container started
docker ps | findstr fantasyfolio
```

**Expected output:**
```
<container-id>   ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15   Up X seconds   0.0.0.0:8008->8008/tcp
```

### Step 5: Check Logs
```powershell
# Watch startup logs
docker-compose logs -f fantasyfolio

# Look for:
# - "Running on https://0.0.0.0:8008"
# - No ERROR or FATAL messages
```

**Press Ctrl+C when startup complete**

### Step 6: Verify Database Schema
```powershell
# Check schema has all columns
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
  ".schema models" | findstr "folder_path volume_id thumb_storage"
```

**Expected output:**
```
  folder_path TEXT,
  volume_id TEXT REFERENCES volumes(id),
  thumb_storage TEXT,
```

### Step 7: Test Web Access
- [ ] Open browser: https://localhost:8008
- [ ] Accept self-signed certificate warning
- [ ] Verify homepage loads

### Step 8: Configure Asset Volumes

#### Via UI (Recommended)
1. Navigate to **Settings → Asset Locations**
2. Click **"Add Location"**
3. Configure each volume:

**3D Assets Example:**
```
Name: 3D Assets
Type: 3D Models
Path: /volumes/3d-assets
Read-only: ✓ (checked)
```

**Documents Example:**
```
Name: Documents
Type: PDFs
Path: /volumes/documents
Read-only: ✓ (checked)
```

4. Click **"Save"** for each location

#### Via API (Alternative)
```powershell
# 3D Assets
curl -X POST https://localhost:8008/api/asset-locations `
  -H "Content-Type: application/json" `
  -d '{
    "name": "3D Assets",
    "asset_type": "models",
    "location_type": "local",
    "path": "/volumes/3d-assets",
    "is_readonly": true
  }'

# Documents
curl -X POST https://localhost:8008/api/asset-locations `
  -H "Content-Type: application/json" `
  -d '{
    "name": "Documents",
    "asset_type": "documents",
    "location_type": "local",
    "path": "/volumes/documents",
    "is_readonly": true
  }'
```

### Step 9: Index Assets

#### Via UI
1. Go to **Settings → Asset Locations**
2. Click **"Index Now"** for each location
3. Monitor progress in UI
4. Wait for indexing to complete

#### Via API
```powershell
# Index 3D Assets
curl -X POST https://localhost:8008/api/index/directory `
  -H "Content-Type: application/json" `
  -d '{
    "path": "/volumes/3d-assets",
    "recursive": true,
    "force": false,
    "duplicate_policy": "merge"
  }'

# Index Documents
curl -X POST https://localhost:8008/api/index/directory `
  -H "Content-Type: application/json" `
  -d '{
    "path": "/volumes/documents",
    "recursive": true,
    "force": false
  }'
```

### Step 10: Verify Navigation

- [ ] **Check nav tree structure:**
  ```
  📁 3D Assets          ← Volume label from Settings
    └─ Fantasy/
    └─ Superhero/
    └─ Terrain/
  📁 Documents          ← Volume label from Settings
    └─ Manuals/
    └─ Projects/
  ```

- [ ] **Test volume root click:** Should show all models in that volume
- [ ] **Test folder click:** Should show models in that folder
- [ ] **Switch between 3D/PDF tabs:** Navigation should work in both

### Step 11: Verify Thumbnails

- [ ] **Check daemon status:**
  ```powershell
  docker exec fantasyfolio supervisorctl status thumbnail_daemon
  ```
  **Expected:** `RUNNING`

- [ ] **Wait for thumbnails to generate** (30-60 seconds)

- [ ] **Verify thumbnail coverage:**
  ```powershell
  docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
    "SELECT COUNT(*) as total, COUNT(thumb_storage) as with_thumbs FROM models"
  ```
  **Expected:** Most models have thumbnails

- [ ] **Check for 404 errors in browser console** (F12)
  - Should be no 404s for `/thumbnails/` paths

### Step 12: Test Core Features

- [ ] **Search:** Enter query, verify results
- [ ] **Filters:** Filter by format (STL, OBJ, etc.)
- [ ] **Sorting:** Sort by filename, size, date
- [ ] **Preview:** Click model, verify preview opens
- [ ] **Download:** Download a model
- [ ] **PDF viewing:** Click PDF, navigate pages
- [ ] **Infinite scroll:** Scroll down, more items load

### Step 13: Performance Check

```powershell
# Check container stats
docker stats fantasyfolio --no-stream

# Check disk usage
docker system df -v | findstr fantasyfolio
```

**Expected:**
- CPU: <10% idle, <50% during indexing
- Memory: <2GB
- Disk: ~3GB (image) + data volumes

---

## Post-Deployment Verification ✅

### Database Health
- [ ] Model count matches expected
  ```powershell
  docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
    "SELECT COUNT(*) FROM models WHERE format != 'unsupported'"
  ```

- [ ] All volumes have model counts
  ```powershell
  docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db \
    "SELECT v.label, COUNT(m.id) as models FROM volumes v LEFT JOIN models m ON m.volume_id = v.id GROUP BY v.id"
  ```

- [ ] Folder tree loads without errors
  ```powershell
  curl -k https://localhost:8008/api/models/folder-tree | jq '.flat | length'
  ```

### Feature Verification
- [ ] Volume-based navigation working
- [ ] Folder navigation working
- [ ] Thumbnails rendering and displaying
- [ ] Search returning results
- [ ] PDF page preview working
- [ ] New formats supported (DAE, 3DS, PLY, X3D)
- [ ] GLTF validation preventing incomplete files
- [ ] No FBX files indexed (format removed)

### Known Issues Check
- [ ] FTS search may need reindex (expected)
- [ ] Some thumbnails may be missing (~10%, expected for invalid files)
- [ ] GLTF files from before validation may be incomplete (grandfathered)

---

## Rollback Procedure (If Needed)

If issues occur, rollback to v0.4.14:

```powershell
# Stop current version
docker-compose down

# Update docker-compose.yml
# Change: image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14

# Start previous version
docker-compose up -d

# Restore backup if needed
docker run --rm -v fantasyfolio_data:/data -v D:/backups:/backup \
  alpine tar xzf /backup/fantasyfolio-backup-<date>.tar.gz -C /
```

**Note:** v0.4.15 has no breaking database changes, so rollback is safe.

---

## Troubleshooting

### Nav Tree Not Showing Volume Labels
**Solution:**
1. Clear browser cache (Ctrl+Shift+Del)
2. Hard reload (Ctrl+F5)
3. Check API: `curl https://localhost:8008/api/models/folder-tree`

### Thumbnails Not Generating
**Solution:**
```powershell
# Restart daemon
docker exec fantasyfolio supervisorctl restart thumbnail_daemon

# Check logs
docker exec fantasyfolio tail -f /app/logs/thumbnail_daemon.log
```

### Models Missing from Nav Tree
**Solution:**
```powershell
# Force re-index to populate folder_path
curl -X POST https://localhost:8008/api/index/directory \
  -H "Content-Type: application/json" \
  -d '{"path": "/volumes/3d-assets", "force": true}'
```

### Container Won't Start
**Solution:**
```powershell
# Check logs
docker-compose logs fantasyfolio

# Common fixes:
# - Verify port 8008 not in use
# - Check volume mounts exist
# - Verify SECRET_KEY is set
```

---

## Success Criteria ✅

**Deployment is successful when:**
- [x] Container running (docker ps shows UP status)
- [ ] Web UI accessible (https://localhost:8008)
- [ ] Nav tree shows volume-based structure
- [ ] Models indexed and visible in nav tree
- [ ] Thumbnails rendering (>80% coverage)
- [ ] No errors in browser console
- [ ] Search and filters working
- [ ] PDF viewing working
- [ ] Server stable (no crashes for 24h)

---

## Sign-Off

**Deployed By:** _________________  
**Date:** _________________  
**Time:** _________________  

**Deployment Status:** ⬜ Success | ⬜ Partial | ⬜ Rollback

**Issues Encountered:**
- 

**Notes:**
- 

**Next Steps:**
- Monitor for 24 hours
- Update Windows deployment documentation if needed
- Plan next feature release

---

## Support

**Documentation:** https://docs.openclaw.ai  
**Issues:** https://github.com/diminox-kullwinder/fantasyfolio/issues  
**Discord:** https://discord.com/invite/clawd  

**Emergency Rollback:** See "Rollback Procedure" section above
