# FantasyFolio v0.4.9 → v0.4.14 Validation Checklist

**Purpose:** Complete validation before Windows deployment  
**Platform:** Mac local testing (representative of Docker/Windows environment)  
**Test Database:** `/Users/claw/projects/dam/data/fantasyfolio.db`  
**Test Assets:** `/Volumes/d-mini/ff-testing/`

---

## Release Summary

| Version | Date | Key Features |
|---------|------|--------------|
| v0.4.9 | 2026-02-11 | Volume management, asset locations |
| v0.4.10 | 2026-02-12 | 10 critical bug fixes (upload, search, thumbnails) |
| v0.4.11 | 2026-02-17 | Schema fixes, container deployment |
| v0.4.12 | 2026-02-17 | SVG/GLB/GLTF support, infinite scroll, deduplication |
| v0.4.13 | 2026-02-17 | Duplicate prevention system (3 policies) |
| v0.4.14 | 2026-02-18 | 4 critical thumbnail bugs fixed |

---

## v0.4.14 - Critical Thumbnail Fixes (4 Bugs)

### ✅ Bug #1: Infinite Scroll
- **Issue:** Grid stops loading at ~100 models
- **Test:**
  ```
  1. Navigate to 3D Models with 200+ models
  2. Scroll down past first 100 models
  3. Verify more models load automatically
  ```
- **Expected:** All models load as you scroll
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Bug #2: Flask Thumbnail Route
- **Issue:** Thumbnails render but don't display (404 errors)
- **Test:**
  ```bash
  curl -I https://192.168.50.190:8008/thumbnails/3d/1.png
  ```
- **Expected:** HTTP 200 OK
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Bug #3: Thread Exhaustion
- **Issue:** Unlimited threads spawn (272 models = 272 threads = crash)
- **Test:**
  ```
  1. Index folder with 200+ models
  2. Monitor system resources (Activity Monitor)
  3. Verify max 4 concurrent render processes
  ```
- **Expected:** ThreadPoolExecutor limits to 4 workers
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Bug #4: Daemon Autostart
- **Issue:** Thumbnail daemon doesn't start automatically
- **Test:**
  ```
  1. Restart server
  2. Check if daemon is running: ps aux | grep thumbnail_daemon
  3. Verify thumbnails render during indexing
  ```
- **Expected:** Daemon auto-starts, thumbnails generate
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## v0.4.13 - Duplicate Prevention

### ✅ Duplicate Detection During Index
- **Test:**
  ```
  1. Upload same file to two different folders
  2. Run indexer on both folders
  3. Check database for duplicates:
     SELECT filename, file_path, is_duplicate, duplicate_of_id 
     FROM models WHERE filename = 'test-model.stl'
  ```
- **Expected (default 'merge'):** Only one record, points to newest location
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Three Duplicate Policies
- **Test 'reject':**
  ```json
  POST /api/index/directory
  {"path": "/test", "duplicate_policy": "reject"}
  ```
  - Expected: Scan stats show `duplicate: N`, no new records created

- **Test 'warn':**
  ```json
  {"path": "/test", "duplicate_policy": "warn"}
  ```
  - Expected: New records created with `is_duplicate=1`, `duplicate_of_id` set

- **Test 'merge' (default):**
  ```json
  {"path": "/test", "duplicate_policy": "merge"}
  ```
  - Expected: Existing record updated to new path, no duplicates
  
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## v0.4.12 - New Format Support

### ✅ SVG Support
- **Test:**
  ```
  1. Upload SVG file to /content/3d-models/test/
  2. Verify SVG appears in grid with thumbnail
  3. Click to view - should show "View Full Size" button
  4. Right-click → Regenerate Thumbnail
  ```
- **Expected:** SVG displays, thumbnails render, inline viewer works
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ GLB Support
- **Test:**
  ```
  1. Upload GLB file (AuroraGnome.glb)
  2. Verify thumbnail renders
  3. Click to preview - should show 3D viewer
  ```
- **Expected:** GLB renders and displays correctly
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ GLTF Validation (NEW in current session)
- **Test incomplete GLTF:**
  ```
  1. Upload standalone .gltf file without companion files
  2. Run indexer
  3. Check scan results for validation error
  ```
- **Expected:** Error message: "Missing companion files: scene.bin, textures/..."
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

- **Test complete GLTF:**
  ```
  1. Upload .gltf with all companion files in same directory
  2. Run indexer
  3. Verify file indexes successfully
  ```
- **Expected:** No validation errors, file indexes
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Infinite Scroll
- **Test:**
  ```
  1. Navigate to folder with 500+ models
  2. Initial load should show 100 models
  3. Scroll to bottom - verify next 100 load automatically
  4. Apply filter (collection/folder) - verify scroll still works
  ```
- **Expected:** Pagination works, loads more on scroll
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Deduplication API
- **Test:**
  ```bash
  curl -X POST https://192.168.50.190:8008/api/models/detect-duplicates
  ```
- **Expected:** Returns stats on duplicates found, marks in database
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## v0.4.11 - Schema & Container Fixes

### ✅ Database Schema Complete
- **Test:**
  ```bash
  # Delete test DB and recreate from schema.sql
  cd /Users/claw/projects/dam
  rm data/fantasyfolio.db
  sqlite3 data/fantasyfolio.db < data/schema.sql
  
  # Verify all columns exist
  sqlite3 data/fantasyfolio.db ".schema models" | grep -E "thumb_storage|thumb_path|volume_id"
  ```
- **Expected:** All 40 columns present, no errors
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Automatic Thumbnail Generation
- **Test:**
  ```
  1. Index new folder with 20+ models
  2. Wait 30 seconds
  3. Check database:
     SELECT COUNT(*) FROM models WHERE thumb_storage IS NOT NULL;
  ```
- **Expected:** Thumbnails auto-generate during indexing
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## v0.4.10 - Bug Fixes (17 Total)

### ✅ Upload System (4 fixes)
1. **3D upload hang** - Test 3MB STL upload completes in <5 seconds
2. **Upload dialog broken** - Folder browser opens and navigates correctly
3. **Folder creation fails** - New folders created via UI without errors
4. **Upload timeout** - Large files (50MB+) timeout gracefully with warning

- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Search & Navigation (5 fixes)
1. **3D search folder scope** - Search respects selected folder
2. **Advanced search PDF** - Multi-criteria PDF search works
3. **Context menu refresh** - Right-click refresh loads correct content type
4. **Force Index nav tree** - Context menu "Force Index" works without errors
5. **Force Index JavaScript** - No console errors during force index

- **Test:** 
  ```
  1. Select folder in nav tree
  2. Search for model - should only return results from that folder
  3. Right-click folder → Refresh - should reload that folder
  4. Right-click folder → Force Index - should re-index
  ```
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Thumbnails (3 fixes)
1. **has_thumbnail flag** - Database flag updates after render
2. **Rendering quality** - All renders use f3d → stl-thumb fallback
3. **Camera angle** - Thumbnails show front view, not back

- **Test:**
  ```
  1. Regenerate thumbnail on any model
  2. Verify high-quality render (not wireframe)
  3. Verify model faces forward
  4. Check DB: has_thumbnail should be 1
  ```
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ UI/UX (3 fixes)
1. **Tab switching cache** - Thumbnails refresh on tab switch
2. **Grid manual refresh** - Regenerating thumbnail updates grid view
3. **PDF thumbnail regeneration** - Right-click → Regenerate works on PDFs

- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## v0.4.9 - Foundation

### ✅ Volume Management
- **Test:**
  ```
  1. Open Settings → Asset Locations
  2. Verify volumes list displays
  3. Add new volume - verify it saves
  ```
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

### ✅ Asset Locations
- **Test:**
  ```
  1. Settings → Asset Locations
  2. Add location with path
  3. Verify location appears in list
  4. Index location - verify assets found
  ```
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## New Formats (Added This Session)

### ✅ DAE, FBX, 3DS, PLY, X3D Support
- **Test:**
  ```
  1. Upload sample files of each format (Matthew uploading now)
  2. Verify files appear in grid
  3. Verify thumbnails render
  4. Click to preview
  ```
- **Expected:** All formats supported in indexing, search, thumbnails
- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## Critical Path Test (End-to-End)

### ✅ Full Workflow Test
1. **Fresh Install:**
   - Delete database: `rm data/fantasyfolio.db`
   - Restart server
   - Verify database auto-creates from schema.sql

2. **Asset Locations:**
   - Add volume: `/Volumes/d-mini/ff-testing/`
   - Set as read-only: `is_readonly=1`

3. **Indexing:**
   - Index 3D folder (200+ models)
   - Verify no `.dam` directories created (read-only protection)
   - Verify models appear in nav tree
   - Verify thumbnails auto-generate

4. **Search:**
   - Search for "dragon" - verify results
   - Filter by folder - verify scope works
   - Filter by format - verify correct formats

5. **Viewing:**
   - Click model - verify preview loads
   - Right-click → Regenerate Thumbnail - verify works
   - Switch between 3D/PDF tabs - verify no cache issues

6. **Duplicate Prevention:**
   - Copy model to different folder
   - Re-index both folders
   - Verify only one record (merge policy)

7. **New Formats:**
   - Upload DAE, FBX, PLY files
   - Verify all index and render

- **Status:** ⬜ Not tested | ✅ Pass | ❌ Fail

---

## Test Environment

**Server:** https://192.168.50.190:8008  
**Process:** PID 41928  
**Database:** `/Users/claw/projects/dam/data/fantasyfolio.db`  
**Test Assets:** `/Volumes/d-mini/ff-testing/`  
**Version in Code:** v0.4.14 (fantasyfolio/config.py)  

---

## Notes

- **Schema Drift Prevention:** RELEASE_PROCESS.md now mandatory for all releases
- **Windows Deployment:** Once Mac validation passes, deploy to Windows PC
- **Git Tags:** v0.4.11-v0.4.14 tags created and pushed to GitHub
- **Docker Images:** Ready to build once validation complete

---

## Sign-Off

**Tester:** __________  
**Date:** __________  
**Overall Status:** ⬜ Pass | ⬜ Fail  
**Notes:**
