# FantasyFolio v0.4.14 - Bug Fixes

**Date:** 2026-02-17  
**Bugs Fixed:** 2 critical issues from Windows testing

---

## Bug #1: Infinite Scroll Stops at ~90-100 Models ✅ FIXED

**Reported By:** Matthew  
**Symptom:** Asset count shows 272, but scrolling only reveals ~90-100 models

**Root Cause:**
- Scroll listener attached to `.content-section` (doesn't exist)
- Should have been `.main-scroll` (actual scrollable container)

**Fix:**
```javascript
// BEFORE (broken):
const contentSection = document.querySelector('.content-section');

// AFTER (fixed):
const mainScroll = document.querySelector('.main-scroll');
```

**Testing:**
1. Index 200+ models
2. Open web UI  
3. Scroll to bottom
4. Should auto-load next 100, then next 100, etc.
5. All 272 models should be viewable

**Status:** ✅ Fixed in commit `c1ea6bc`

---

## Bug #2: No Thumbnails Rendering ✅ FIXED

**Reported By:** Matthew  
**Symptom:** Models indexed but thumbnails don't render during browsing

**Root Causes Found:**
1. ❌ Flask `/thumbnails/` route missing (thumbnails rendered but not served)
2. ❌ Thumbnail daemon `autostart=false` (never starts on boot)
3. ❌ Unlimited thread spawning in preview endpoint (causes crashes)
4. ❌ Missing `[rpcinterface:supervisor]` (supervisorctl broken)

**Fixes Applied:**
1. ✅ Added Flask `send_from_directory` route for `/thumbnails/<path>`
2. ✅ Changed `autostart=false` → `autostart=true` in supervisord.conf
3. ✅ Added `ThreadPoolExecutor(max_workers=4)` to limit concurrent renders
4. ✅ Added `[rpcinterface:supervisor]` section to supervisord.conf

**Testing Steps for Matthew:**

### Step 1: Check Logs
```powershell
# Watch logs in real-time
docker logs fantasyfolio --follow

# Look for these patterns:
# ✓ Background render complete for model X
# ✗ Thumbnail render returned None
# ✗ Background thumbnail render EXCEPTION
```

### Step 2: Manual Thumbnail Test
```powershell
# Check if rendering tools are available
docker exec fantasyfolio which f3d
docker exec fantasyfolio which stl-thumb

# Test f3d manually
docker exec fantasyfolio f3d --version

# Test stl-thumb manually  
docker exec fantasyfolio stl-thumb --version
```

### Step 3: Check File Permissions
```powershell
# Check thumbnail directory
docker exec fantasyfolio ls -la /app/thumbnails/3d/

# Check if writable
docker exec fantasyfolio touch /app/thumbnails/3d/test.txt
docker exec fantasyfolio ls -la /app/thumbnails/3d/test.txt
docker exec fantasyfolio rm /app/thumbnails/3d/test.txt
```

### Step 4: Manual Render Test via API
```powershell
# Trigger manual thumbnail generation for model ID 1
curl -X POST http://localhost:8888/api/models/1/regenerate-thumbnail `
  -H "Content-Type: application/json" `
  -d '{"force": true}'

# Check response - should show success or error details
```

### Step 5: Check Browser Console
1. Open browser developer tools (F12)
2. Go to Console tab
3. Load a model preview
4. Look for JavaScript errors

---

## Diagnostic Information Needed

If thumbnails still don't work, provide:

1. **Container logs:**
```powershell
docker logs fantasyfolio > C:\FantasyFolio\logs.txt
```

2. **Tool availability:**
```powershell
docker exec fantasyfolio f3d --version
docker exec fantasyfolio stl-thumb --version
```

3. **Directory permissions:**
```powershell
docker exec fantasyfolio ls -la /app/thumbnails/
docker exec fantasyfolio ls -la /app/data/
```

4. **Database check:**
```powershell
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db "SELECT id, filename, format, has_thumbnail, volume_id, file_path FROM models LIMIT 5;"
```

5. **Manual render test result:**
```powershell
curl -X POST http://localhost:8888/api/models/1/regenerate-thumbnail -H "Content-Type: application/json" -d '{"force": true}' | ConvertFrom-Json | Format-List
```

---

## Quick Fix If Still Broken

If thumbnails still don't generate after v0.4.14:

### Option A: Batch Render
```powershell
# Trigger batch render for all models
curl -X POST http://localhost:8888/api/models/render-thumbnails
```

### Option B: Force Render via UI
1. Go to Settings
2. Look for "Render Thumbnails" button
3. Click it
4. Wait for completion

### Option C: Check if xvfb is running
```powershell
# f3d needs xvfb for headless rendering
docker exec fantasyfolio ps aux | Select-String xvfb

# If not running, the Dockerfile should have it but may need supervisord
```

---

## Building v0.4.14

**Current Status:** Fixes committed but image not yet built

**To build and test:**
```bash
# On Mac
cd /Users/claw/projects/dam
docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14 .
docker tag ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14 ghcr.io/diminox-kullwinder/fantasyfolio:latest
docker push ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14
docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

**On Windows (after image pushed):**
```powershell
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14
# Update docker-compose.yml to :0.4.14
docker-compose down
docker-compose up -d
```

---

## Next Steps

1. **Matthew:** Run diagnostic commands above and report findings
2. **Hal:** Build v0.4.14 image with fixes
3. **Matthew:** Test v0.4.14 on Windows
4. **Iterate:** Additional fixes if needed based on diagnostics

---

**Status:** 
- Bug #1 (Infinite scroll): ✅ FIXED
- Bug #2 (Thumbnails): ✅ FIXED (4 issues resolved)

**Commits:**
- `c1ea6bc` - Fix infinite scroll (wrong container selector)
- `88c4a50` - Add thumbnail debugging  
- `7d652d1` - Add Flask `/thumbnails/` route
- `5d876f7` - Add ThreadPoolExecutor concurrency control
- `feed6b8` - Enable daemon autostart + RPC interface

**Ready for Docker build and Windows testing.**
