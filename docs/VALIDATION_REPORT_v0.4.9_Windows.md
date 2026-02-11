# FantasyFolio v0.4.9 - Windows Validation Report

**Date:** 2026-02-11  
**Tester:** Matthew  
**Platform:** Windows PC (Alienware) with Docker Desktop + WSL2  
**Container:** `ghcr.io/diminox-kullwinder/fantasyfolio:latest` (v0.4.9)  
**Test Dataset:** 3,200 PDFs, 2,133 3D models (391 in initial test set)  

---

## Executive Summary

**Verdict:** ❌ **NOT PRODUCTION READY**

v0.4.9 deploys successfully and core features work (indexing, viewing, sorting), but has **16 critical/high/medium bugs** that significantly impact usability. Most UI convenience features are broken or call non-existent API endpoints.

**Recommendation:** Fix critical bugs before v0.4.10 release. Focus on search, database tracking, and camera angle.

---

## What Works ✅

### Core Functionality
- **Container deployment**: Pulls and starts without errors
- **PDF indexing**: 3,200 PDFs indexed successfully via Asset Volume button
- **3D model indexing**: 2,133 models indexed (1,742 successful, 391 SQL errors)
- **Thumbnail rendering**: 272 thumbnails generated successfully
- **Bulk thumbnail generation**: Settings → 3D Model Maintenance → Render Thumbnails works with progress tracking
- **Sorting**: Name, Size, Format all work correctly
- **Format filters**: STL, OBJ, 3MF, GLB filters work
- **3D viewer**: STL, OBJ, 3MF files display correctly in browser
- **Folder navigation**: Tree view and breadcrumbs functional
- **Individual thumbnail regeneration**: Right-click → Regenerate works (batches folder automatically)

---

## Critical Bugs 🚨

### 1. has_thumbnail Database Flag Not Updated
**Severity:** CRITICAL  
**Impact:** Stats show wrong counts, queries return incorrect results  
**Details:**
- 272 thumbnail files exist on disk
- Only 5 models flagged with `has_thumbnail=1` in database
- UI works (checks file directly), but backend queries fail
- Stats show "121/152 cached" when reality is "272/2133"

**Root Cause:** Thumbnail rendering code doesn't UPDATE models table after successful render  
**Kanban:** task-20260211125307818234

---

### 2. 3D Re-indexing Fails with SQL Binding Error
**Severity:** CRITICAL  
**Impact:** Cannot re-index existing models, 391 models consistently fail  
**Details:**
- Error: "Binding 15 has no name, but you supplied a dictionary"
- First index works (153 models), subsequent indexes fail
- 391 models fail every time (likely duplicates or specific attribute triggers bug)
- Results: `models_found: 391, models_indexed: 0, errors: 391`

**Root Cause:** SQL INSERT has positional/named parameter mismatch in indexer code  
**File:** `fantasyfolio/indexer/models3d.py`  
**Kanban:** task-20260211124733129266

---

### 3. Advanced Search Completely Broken
**Severity:** CRITICAL  
**Impact:** Users cannot search for assets  
**Details:**
- "This folder" scope always defaults to global
- Search switches from 3D tab to PDF tab unexpectedly
- Search criteria ignored - shows all assets instead of filtered results
- Folder scope not respected at any level

**Root Cause:** Search handler logic broken or endpoints return wrong data  
**File:** `templates/index.html` (search handler) or `fantasyfolio/api/search.py`  
**Kanban:** task-20260211135322898125

---

## High Priority Bugs 🔴

### 4. Camera Angle Shows Back View on Almost All Models
**Severity:** HIGH  
**Impact:** Poor UX - thumbnails show wrong angle  
**Details:**
- Current: `--camera-direction=0,-1,-0.3` (looking from negative Y)
- Result: Most models show back side instead of front
- Affects nearly all thumbnails

**Fix:** Change to `--camera-direction=0,1,-0.3` (positive Y direction)  
**File:** `fantasyfolio/core/thumbnails.py` line ~234  
**Kanban:** task-20260211121055408462

---

### 5. GLTFLoader Missing from 3D Viewer
**Severity:** HIGH  
**Impact:** GLB/glTF files cannot be viewed in browser  
**Details:**
- Three.js loads STLLoader and OBJLoader
- GLTFLoader not loaded
- Error: "GLB Loader failed to load"

**Fix:** Add `await loadScript('...GLTFLoader.js')` and handle GLTF scene loading  
**File:** `templates/index.html` (Three.js loader section)  
**Kanban:** task-20260211122814510367

---

### 6. No Pagination/Infinite Scroll - Large Folders Truncated
**Severity:** HIGH  
**Impact:** Cannot view all assets in large folders  
**Details:**
- Folders with 100+ assets show only subset
- No "Load More" button or pagination controls
- No way to access hidden assets

**Fix:** Implement infinite scroll or pagination  
**File:** `templates/index.html`  
**Kanban:** task-20260211125631769101

---

### 7. Nav Tree Force Full Index Calls Non-existent Endpoint
**Severity:** HIGH  
**Impact:** Feature advertised but doesn't exist  
**Details:**
- Right-click folder → Force Full Index calls `POST /api/index/directory`
- Endpoint returns `404 NOT FOUND`
- Backend never implemented

**Fix:** Implement endpoint or remove UI button  
**File:** `fantasyfolio/api/indexer.py` (add endpoint) or remove from UI  
**Kanban:** task-20260211131728293853

---

### 8. ZIP Asset Thumbnails Missing from Grid View
**Severity:** HIGH  
**Impact:** Assets from archives appear to have no thumbnail  
**Details:**
- Models extracted from ZIP show thumbnail in detail popup
- Grid/list view shows placeholder
- Thumbnail exists but path resolution fails

**Fix:** Fix thumbnail path logic for archive-extracted files  
**File:** `templates/index.html` or `fantasyfolio/api/models.py`  
**Kanban:** task-20260211132526885993

---

### 9. Multi-threaded PDF Indexing Needed
**Severity:** HIGH  
**Impact:** Poor performance - 3,200 PDFs took ~90 minutes  
**Details:**
- Single-threaded: ~21 PDFs/minute (1 every ~3 seconds)
- Expected with 4-8 workers: 4-8x faster

**Fix:** Add parallel worker support to PDF indexer  
**File:** `fantasyfolio/indexer/pdf.py`  
**Kanban:** task-20260211104101061260

---

## Medium Priority Bugs 🟡

### 10. change_journal Table Missing
**Severity:** MEDIUM  
**Impact:** Errors in logs, feature doesn't work  
**Details:**
- Code expects `change_journal` table
- Table missing from `schema.sql`
- Error: `sqlite3.OperationalError: no such table: change_journal`

**Fix:** Add table to schema or gracefully disable feature  
**Recommendation:** Disable for single-user use case  
**Kanban:** task-20260211094446849965

---

### 11. Supervisor Config Broken
**Severity:** MEDIUM  
**Impact:** Cannot use supervisorctl to manage processes  
**Details:**
- Missing `[rpcinterface:supervisor]` section
- Error: "did not recognize the supervisor namespace commands"

**Fix:** Add missing section to `/etc/supervisor/conf.d/supervisord.conf`  
**Kanban:** task-20260211121055385715

---

### 12. Thumbnail Daemon Not Autostarting
**Severity:** MEDIUM  
**Impact:** Thumbnails don't render in background on container start  
**Details:**
- `autostart=false` in supervisor config
- Must manually start daemon

**Fix:** Set `autostart=true`  
**File:** `/etc/supervisor/conf.d/supervisord.conf`  
**Kanban:** task-20260211121055408462

---

### 13. Grid View Doesn't Auto-refresh After Bulk Operations
**Severity:** MEDIUM  
**Impact:** User must manually refresh (F5) to see results  
**Details:**
- Bulk thumbnail regeneration completes in background
- Grid view doesn't update automatically
- Manual F5 refresh shows thumbnails

**Fix:** Poll for completion or trigger grid reload  
**File:** `templates/index.html`  
**Kanban:** task-20260211125858326004

---

### 14. Inconsistent Index Triggers in Settings UI
**Severity:** MEDIUM  
**Impact:** Confusing UX - some buttons work, others don't  
**Details:**
- **Working:** Asset Volume index button
- **Broken:** Reindex Library → Scan 3D models/PDFs
- **Broken:** Browse folder → Index
- **Broken:** Nav tree right-click → Force Full Index

**Fix:** All buttons should call same backend endpoint  
**File:** `templates/index.html`  
**Kanban:** task-20260211124617860754

---

### 15. Upload/Browse Dialog Broken
**Severity:** MEDIUM  
**Impact:** Manual upload feature unusable  
**Details:**
- `GET /api/upload/browse?type=3d` returns `400 BAD REQUEST`
- Error: "not a directory"
- Browse dialog shows perpetual "Loading..."

**Fix:** Fix path validation or permissions check  
**File:** `fantasyfolio/api/upload.py`  
**Kanban:** task-20260211131528416639

---

### 16. Folder-level Index from Browse Dialog Fails
**Severity:** MEDIUM  
**Impact:** Convenience feature doesn't work  
**Details:**
- Settings → Browse to folder → Index button does nothing
- Only works for Asset Volume root paths

**Fix:** Wire up browse → index properly  
**File:** `templates/index.html` or `fantasyfolio/api/indexer.py`  
**Kanban:** task-20260211130422358186

---

## Workaround for Current Version

**Indexing:**
1. Use Settings → Asset Locations → Index button next to volume path (ONLY working option)

**Thumbnails:**
1. Settings → 3D Model Maintenance → Render Thumbnails
2. Click "Show Status" to track progress
3. Manual refresh (F5) page to see results

**Viewing:**
1. Sorting and filters work normally
2. STL/OBJ viewer works
3. Avoid GLB files (viewer fails)

**Search:**
- Not functional - browse folders manually instead

---

## Test Environment Details

**System:**
- Windows 10/11 with Docker Desktop
- WSL2 backend
- Container: `ghcr.io/diminox-kullwinder/fantasyfolio:latest`
- Image built: 2026-02-10 19:40 PST
- Git commit: `a2cc8a3d0c83539daa5c7e532064c77da9f7922e`

**Volumes:**
- Data: `C:\FantasyFolio\data` → `/app/data`
- 3D Models: `O:\3DFiles\3D-Models` → `/content/3d-models:ro`
- PDFs: `O:\DROBO\D\Gaming\Gaming PDF's Consolidated 2\Gathered` → `/content/pdfs:ro`

**Performance Notes:**
- PDF indexing: ~21 files/minute (single-threaded)
- Thumbnail rendering: Fast when working (batch operations)
- UI responsive with 2,133 models + 3,200 PDFs

---

## Next Steps for v0.4.10

### Must Fix (Critical)
1. has_thumbnail database flag updates
2. SQL binding error on re-index
3. Advanced search functionality

### Should Fix (High)
4. Camera angle (simple one-line fix)
5. GLTFLoader for viewer
6. Pagination/infinite scroll
7. Remove broken UI features or implement backends

### Nice to Have (Medium)
8. Multi-threaded PDF indexing
9. Auto-refresh grid after operations
10. Consistent index triggers
11. Fix upload/browse dialog

### Consider Removing
- change_journal feature (incomplete, unused)
- Non-functional UI buttons until backends implemented

---

## Validation Checklist Results

| Feature | Status | Notes |
|---------|--------|-------|
| Container deployment | ✅ | Clean start |
| PDF indexing | ✅ | 3,200 indexed |
| 3D indexing | ⚠️ | 1,742 successful, 391 fail |
| Thumbnails | ⚠️ | Work but tracking broken |
| Sorting | ✅ | All options work |
| Format filters | ✅ | All formats work |
| Folder navigation | ✅ | Tree + breadcrumbs |
| PDF viewer | ✅ | Preview works |
| 3D viewer | ⚠️ | STL/OBJ yes, GLB no |
| Search | ❌ | Completely broken |
| Persistence | ✅ | Data survives restart |
| Settings UI | ⚠️ | Many broken buttons |

**Overall Score:** 8/12 features functional (67%)

---

## Conclusion

v0.4.9 demonstrates solid core functionality but needs significant polish before production deployment. The container architecture works well, and the fundamental features (indexing, viewing, sorting) are functional. However, numerous broken UI features and missing backend implementations make it frustrating to use.

**Primary Issues:**
1. Too many UI features that don't work (call non-existent endpoints)
2. Database tracking out of sync with actual files
3. Search completely broken
4. No pagination for large datasets

**Recommendation:** 
- Fix 3 critical bugs + 4 high-priority bugs
- Remove or disable non-functional features
- Test on Windows before release
- Consider a v0.4.9.1 hotfix or skip to v0.4.10

**Positive Notes:**
- Container deploys cleanly
- Core indexing + viewing workflow is solid
- Performance is acceptable for single-user
- Thumbnails render successfully (tracking aside)

---

**Report prepared:** 2026-02-11  
**Tested by:** Matthew  
**Documented by:** Hal
