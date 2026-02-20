# FantasyFolio v0.4.15 - Windows Deployment Preflight Cleanup

## Critical: Run This Before Testing v0.4.15

Based on troubleshooting from Feb 18-19, 2026.

---

## 1. Stop All Running Containers

```bash
# Stop FantasyFolio if running
docker stop fantasyfolio 2>/dev/null || true

# Check for any test containers
docker ps -a | grep -E "(fantasyfolio|ff-test)"

# Stop and remove all
docker stop $(docker ps -a -q --filter "name=fantasyfolio") 2>/dev/null || true
docker stop $(docker ps -a -q --filter "name=ff-test") 2>/dev/null || true
```

---

## 2. Remove Old Containers

```bash
# Remove FantasyFolio containers
docker rm fantasyfolio 2>/dev/null || true
docker rm ff-test 2>/dev/null || true

# Remove any orphaned containers
docker container prune -f
```

---

## 3. Clean Up Docker Volumes

### ⚠️ WARNING: This deletes ALL data (database, thumbnails, logs)

**Production volumes (if you want fresh start):**
```bash
docker volume rm fantasyfolio_data 2>/dev/null || true
docker volume rm fantasyfolio_thumbs 2>/dev/null || true
docker volume rm fantasyfolio_logs 2>/dev/null || true
```

**Test volumes (safe to delete):**
```bash
docker volume rm ff-test_ff_test_data 2>/dev/null || true
docker volume rm ff-test_ff_test_thumbs 2>/dev/null || true
docker volume rm ff-test_ff_test_logs 2>/dev/null || true
```

**List all volumes to verify:**
```bash
docker volume ls | grep -E "(fantasyfolio|ff-test)"
```

---

## 4. Remove Old Docker Images

**Keep only v0.4.15, remove everything else:**

```bash
# List current images
docker images | grep fantasyfolio

# Remove old versions (BEFORE v0.4.15)
docker rmi fantasyfolio:0.4.13 2>/dev/null || true
docker rmi fantasyfolio:0.4.14 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14 2>/dev/null || true

# Remove OLD v0.4.15 (built before schema fix)
# SHA: 540810702596 (built 19:24 Feb 18)
docker rmi 540810702596 2>/dev/null || true

# Remove test images
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15-amd64 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15-arm64 2>/dev/null || true

# Clean up dangling images
docker image prune -f
```

**Verify only correct v0.4.15 remains:**
```bash
docker images | grep fantasyfolio
# Should show:
# ghcr.io/diminox-kullwinder/fantasyfolio  0.4.15   f1b9dd17da6c  (Built Feb 19 09:09)
# ghcr.io/diminox-kullwinder/fantasyfolio  latest   f1b9dd17da6c  (Same SHA)
```

---

## 5. Database & Schema Files (Mac/Dev - NOT Windows)

**⚠️ These are on YOUR Mac, not Windows deployment:**

### Test Database Location
```bash
# This was our small test DB
ls -lh /Users/claw/projects/dam/data/dam.db
# Safe to delete if you want
```

### Old Schema Files (Safe to delete)
```bash
cd /Users/claw/projects/dam
rm -f schema_clean.sql schema_export.sql schema_new.sql
rm -f data/schema_clean.sql data/schema_final.sql
rm -f create_clean_schema.py create_proper_schema.py
rm -f .dockerignore.tmp
```

### Orphaned Thumbnails (Already cleaned on Feb 11)
```bash
# These were cleaned up during v0.3.1 work
# Just verify they're gone:
ls /Users/claw/projects/dam/thumbnails/3d/ | wc -l
# Should be 0 or very few
```

---

## 6. Windows-Specific Cleanup (Run on Windows PC)

**BEFORE deploying v0.4.15 on Windows:**

### A. Stop Old Container
```powershell
docker stop fantasyfolio
docker rm fantasyfolio
```

### B. Remove Old Volumes (Fresh Start)
```powershell
# WARNING: Deletes all data
docker volume rm fantasyfolio_data
docker volume rm fantasyfolio_thumbs
docker volume rm fantasyfolio_logs
```

### C. Remove Old Images
```powershell
# Remove ALL old FantasyFolio images
docker images | findstr fantasyfolio
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14
# Remove old 0.4.15 if present
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

### D. Clean Docker System
```powershell
docker system prune -f
```

### E. Pull Fresh v0.4.15
```powershell
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
```

**Verify correct image:**
```powershell
docker images | findstr fantasyfolio
# Should show SHA: f1b9dd17da6c (Built Feb 19, 2026)
```

---

## 7. Verify Clean State (Before Starting)

### Mac/Dev Machine
```bash
# No running containers
docker ps | grep fantasyfolio
# Should be empty

# No test volumes
docker volume ls | grep ff-test
# Should be empty

# Only v0.4.15 image present
docker images | grep fantasyfolio
# Should show ONLY f1b9dd17da6c
```

### Windows Machine
```powershell
# No running containers
docker ps

# No volumes (or only new ones)
docker volume ls

# Only v0.4.15 image
docker images | findstr fantasyfolio
# Should show f1b9dd17da6c
```

---

## 8. Known Issues From Previous Testing

### Issue 1: Schema Parse Errors (FIXED in v0.4.15)
**Symptom:** "object name reserved for internal use: assets_fts_data"
**Fix:** Commit 97e18f8 removed FTS internal tables
**Verify:** Fresh database should initialize without errors

### Issue 2: Orphaned Thumbnails (Cleaned Feb 11)
**Location:** `/projects/dam/thumbnails/3d/`
**Issue:** 29,964 orphaned PNGs (~1.4GB)
**Status:** Already purged

### Issue 3: Sidecar Thumbnails Not Serving (Fixed v0.4.14)
**Symptom:** Thumbnails rendered to sidecars but API returned 404
**Fix:** Commit 7d652d1 added thumb_path column check
**Verify:** After adding assets, thumbnails should display

### Issue 4: Database Path Confusion
**Mac Live:** `/Users/claw/.openclaw/workspace/dam/data/dam.db` (1.2GB)
**Mac Test:** `/Users/claw/projects/dam/data/dam.db` (small)
**Windows:** Controlled by docker-compose.yml volumes
**Solution:** Fresh volumes prevent confusion

---

## 9. Post-Cleanup Verification Script

**Run this to confirm clean state:**

```bash
#!/bin/bash
echo "=== FantasyFolio Preflight Check ==="
echo ""

echo "1. Running containers:"
docker ps | grep fantasyfolio || echo "  ✅ None"
echo ""

echo "2. Stopped containers:"
docker ps -a | grep fantasyfolio || echo "  ✅ None"
echo ""

echo "3. Docker volumes:"
docker volume ls | grep fantasyfolio || echo "  ✅ None"
echo ""

echo "4. Docker images:"
docker images | grep fantasyfolio
echo ""

echo "5. Test artifacts:"
ls /tmp/ff-test 2>/dev/null && echo "  ⚠️  Test directory exists" || echo "  ✅ No test directory"
echo ""

echo "6. Old schema files:"
ls -1 /Users/claw/projects/dam/schema*.sql 2>/dev/null | wc -l | awk '{if ($1 > 0) print "  ⚠️  "$1" old schema files"; else print "  ✅ No old schemas"}'
echo ""

echo "=== Check Complete ==="
```

---

## 10. Fresh Deployment Checklist

After cleanup, deploy with:

**On Windows:**
```powershell
# 1. Pull fresh image
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15

# 2. Update docker-compose.yml
#    Change: image: ghcr.io/.../fantasyfolio:0.4.15

# 3. Start fresh
docker-compose up -d

# 4. Watch logs
docker logs -f fantasyfolio

# 5. Verify startup
# Should see: "[INIT] Database initialized successfully"

# 6. Access UI
# Browser: http://localhost:8888
```

**Success criteria:**
- ✅ No schema parse errors in logs
- ✅ Database initializes on first run
- ✅ UI loads at http://localhost:8888
- ✅ Can add asset location
- ✅ Thumbnails auto-generate

---

## Summary

**Safe to delete:**
- Old Docker images (< v0.4.15)
- Test containers and volumes
- Old schema files on Mac
- Windows: All volumes for fresh start

**Keep:**
- v0.4.15 image (SHA: f1b9dd17da6c)
- docker-compose.yml
- Asset directories (D:\3D-Models, etc.)

**Critical:** Pull fresh v0.4.15 (built Feb 19 09:09) before testing.

---
*Last updated: 2026-02-19 12:38 PST*
