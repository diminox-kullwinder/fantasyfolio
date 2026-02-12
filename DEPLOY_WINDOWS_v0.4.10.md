# Windows PC Deployment Guide - v0.4.10

**For:** Production deployment on Matthew's Windows PC  
**Version:** v0.4.10  
**Date:** 2026-02-12

---

## Prerequisites

- Docker Desktop installed and running
- Git for Windows installed
- Access to the repository: https://github.com/diminox-kullwinder/fantasyfolio

---

## Step 1: Pull Latest Code

```powershell
# Navigate to your FantasyFolio directory
cd C:\path\to\fantasyfolio

# Pull latest changes
git fetch origin
git pull origin master

# Verify you have v0.4.10
git log --oneline -5
# Should show: "docs: Add comprehensive release summary for v0.4.10" at top

# Checkout the release tag
git checkout v0.4.10
```

**Verify:**
```powershell
git describe --tags
# Should output: v0.4.10
```

---

## Step 2: Stop Old Container

```powershell
# Stop the running container
docker stop fantasyfolio

# Remove the old container
docker rm fantasyfolio

# Optional: Remove old image to save space
docker rmi fantasyfolio:v0.4.9
```

**Verify:**
```powershell
docker ps -a | findstr fantasyfolio
# Should show no results (container removed)
```

---

## Step 3: Build New Image

```powershell
# Build v0.4.10 image (this takes ~5-10 minutes)
docker build -t fantasyfolio:v0.4.10 -t fantasyfolio:latest .
```

**Expected output:**
```
Successfully built xxxxxxxxxx
Successfully tagged fantasyfolio:v0.4.10
Successfully tagged fantasyfolio:latest
```

**Verify:**
```powershell
docker images | findstr fantasyfolio
# Should show v0.4.10 and latest
```

---

## Step 4: Deploy Container

### Option A: Fresh Database (Recommended for Testing)

```powershell
# Backup existing database (if any)
copy "C:\path\to\data\fantasyfolio.db" "C:\path\to\data\fantasyfolio.db.backup_v0.4.9"

# Remove old database to start fresh
del "C:\path\to\data\fantasyfolio.db"

# Run container
docker run -d `
  --name fantasyfolio `
  -p 8888:8888 `
  -v "C:\path\to\data:/app/data" `
  -v "C:\path\to\3d-models:/content/3d-models" `
  -v "C:\path\to\pdfs:/content/pdfs" `
  fantasyfolio:v0.4.10
```

### Option B: Keep Existing Database

```powershell
# Run container with existing database
docker run -d `
  --name fantasyfolio `
  -p 8888:8888 `
  -v "C:\path\to\data:/app/data" `
  -v "C:\path\to\3d-models:/content/3d-models" `
  -v "C:\path\to\pdfs:/content/pdfs" `
  fantasyfolio:v0.4.10
```

**Note:** The `models_au` trigger will be created automatically if missing.

**Verify:**
```powershell
# Check container is running
docker ps | findstr fantasyfolio
# Should show CREATED few seconds ago

# Check health
timeout /t 10
curl http://localhost:8888/api/system/health
# Should return: {"status":"healthy",...}
```

---

## Step 5: Validation Tests

### Test 1: Upload (3D Model)
1. Open browser: http://localhost:8888
2. Click "3D Models" tab
3. Click upload icon (top-right)
4. Select a small STL file (<10MB)
5. Upload should complete in ~3-10 seconds
6. Verify file appears in grid

**Expected:** ✅ Upload completes without hanging

### Test 2: Upload (PDF)
1. Click "PDFs" tab
2. Click upload icon
3. Select a PDF file
4. Upload should complete quickly
5. Verify file appears in grid

**Expected:** ✅ Upload completes successfully

### Test 3: Force Re-Index (PDF)
1. Stay on "PDFs" tab
2. Right-click a folder in nav tree
3. Select "Force Full Index"
4. Toast should show: "Indexed: X new, Y updated"
5. Nav tree should refresh with correct hierarchy

**Expected:** ✅ No JavaScript errors, hierarchy preserved

### Test 4: Force Re-Index (3D)
1. Switch to "3D Models" tab
2. Right-click a folder in nav tree
3. Select "Force Full Index"
4. Toast should show results
5. Nav tree should refresh correctly

**Expected:** ✅ No errors, proper folder structure

### Test 5: Search
1. PDFs tab: Search for a term
2. Should return relevant results
3. 3D tab: Search for a model name
4. Should return matching models

**Expected:** ✅ Both searches work correctly

### Test 6: Thumbnails
1. Find a model without thumbnail
2. Right-click → "Regenerate Thumbnail"
3. Thumbnail should appear in ~2-5 seconds

**Expected:** ✅ Thumbnail generates successfully

---

## Step 6: Performance Testing

### Large Dataset Test
1. Navigate to a folder with 100+ items
2. Measure page load time
3. Scroll through grid
4. Test search in large folder

**Expected:** Page loads in 1-3 seconds, scrolling smooth

### Force Re-Index Test
1. Right-click folder with 50+ items
2. Force Full Index
3. Measure completion time

**Expected:** Completes in 5-15 seconds depending on file count

---

## Troubleshooting

### Container Won't Start
```powershell
# Check logs
docker logs fantasyfolio --tail 50

# Common issues:
# - Port 8888 already in use
# - Volume paths don't exist
# - Permission issues
```

### Database Errors
```powershell
# Check database size
dir "C:\path\to\data\fantasyfolio.db"

# If 0 bytes or corrupted:
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db < /app/data/schema.sql
```

### Upload Fails
```powershell
# Check if volumes are mounted correctly
docker exec fantasyfolio ls -la /content/3d-models
docker exec fantasyfolio ls -la /content/pdfs

# Should show your actual files
```

### Thumbnails Don't Generate
```powershell
# Check if f3d is installed
docker exec fantasyfolio which f3d
# Should output: /usr/bin/f3d

# Check logs for render errors
docker logs fantasyfolio --tail 100 | findstr "thumbnail"
```

---

## Rollback (If Needed)

```powershell
# Stop v0.4.10 container
docker stop fantasyfolio
docker rm fantasyfolio

# Restore backup database
copy "C:\path\to\data\fantasyfolio.db.backup_v0.4.9" "C:\path\to\data\fantasyfolio.db"

# Run previous version
docker run -d `
  --name fantasyfolio `
  -p 8888:8888 `
  -v "C:\path\to\data:/app/data" `
  -v "C:\path\to\3d-models:/content/3d-models" `
  -v "C:\path\to\pdfs:/content/pdfs" `
  fantasyfolio:v0.4.9
```

---

## Success Criteria

After deployment, you should have:

- ✅ Container running without errors
- ✅ Web UI accessible at http://localhost:8888
- ✅ Uploads working (both PDF and 3D)
- ✅ Force re-index preserves folder hierarchy
- ✅ Search returns correct results
- ✅ Thumbnails generate successfully
- ✅ No JavaScript errors in browser console
- ✅ Performance acceptable with production data

---

## Next Steps After Validation

1. **If all tests pass:**
   - Document any issues found
   - Plan v0.4.11 deployment (GLB viewer, etc.)
   - Consider automated testing

2. **If issues found:**
   - Document exact steps to reproduce
   - Check browser console for errors
   - Check Docker logs for backend errors
   - Report to development

3. **Future improvements:**
   - Review `NEXT_STEPS.md` for v0.4.11 features
   - Consider pagination if dataset is very large
   - Review `docs/BACKLOG.md` for requested features

---

## Support

**Documentation:**
- CHANGELOG.md - What changed
- RELEASE_NOTES_v0.4.10.md - User guide
- RELEASE_SUMMARY_v0.4.10.md - Technical details
- NEXT_STEPS.md - Roadmap

**Logs:**
- Container logs: `docker logs fantasyfolio`
- Application logs: `docker exec fantasyfolio cat /app/logs/fantasyfolio.log`

**Issues:**
- GitHub: https://github.com/diminox-kullwinder/fantasyfolio/issues
- Include: Version (v0.4.10), logs, steps to reproduce

---

**Deployment Guide Version:** 1.0  
**FantasyFolio Version:** v0.4.10  
**Last Updated:** 2026-02-12
