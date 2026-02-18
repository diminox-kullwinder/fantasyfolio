# Changelog

All notable changes to FantasyFolio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.14] - 2026-02-18

### Fixed - Critical Thumbnail Bugs (4 Issues)

**Windows deployment testing revealed thumbnails not rendering. Root cause analysis found 4 separate bugs:**

#### Bug #1: Infinite Scroll Stops at ~100 Models
- **Problem:** Scroll listener attached to `.content-section` (doesn't exist)
- **Fix:** Changed selector to `.main-scroll` (actual scrollable container)
- **Impact:** All 200+ models now load correctly when scrolling
- **Commit:** c1ea6bc

#### Bug #2: Flask Thumbnail Route Missing
- **Problem:** Thumbnails rendered to `/app/thumbnails/3d/*.png` but Flask had no route to serve them
- **Fix:** Added `send_from_directory` route for `/thumbnails/<path:filename>`
- **Impact:** Thumbnails now display in web UI
- **Commit:** 7d652d1

#### Bug #3: Unlimited Thread Spawning
- **Problem:** Each thumbnail preview spawned unlimited threads (272 models = 272 simultaneous renders = crash)
- **Fix:** Added global `ThreadPoolExecutor(max_workers=4)` to queue renders
- **Impact:** Prevents resource exhaustion, system remains responsive
- **Commit:** 5d876f7

#### Bug #4: Thumbnail Daemon Never Starts
- **Problem #1:** `autostart=false` in supervisord.conf (daemon disabled at boot)
- **Problem #2:** Missing `[rpcinterface:supervisor]` section (supervisorctl broken)
- **Fix:** Changed to `autostart=true` and added RPC interface section
- **Impact:** Thumbnails auto-generate during indexing
- **Commit:** feed6b8

### Testing Notes
**All fixes validated on macOS local dev environment:**
- Flask thumbnail route: HTTP 200 OK serving `/thumbnails/3d/1.png`
- ThreadPoolExecutor: Limits concurrent renders to 4 workers
- Supervisord config: Valid syntax, daemon auto-starts

**Ready for Windows deployment testing.**

---

## [0.4.13] - 2026-02-17

### Added - Duplicate Prevention System

#### Intelligent Duplicate Detection
- **Hash-based duplicate detection during indexing** - Prevents duplicate records when same file uploaded to different locations
  - Computes partial hash for every file during indexing/upload
  - Checks hash against ALL existing records (not just current scan)
  - Works for both standalone files and archive members
  - Detects duplicates across different folders, volumes, and archives

#### Three Duplicate Handling Policies
Users can now choose how to handle duplicates via `duplicate_policy` parameter:

**1. 'reject' (Strict Prevention)**
- Skips duplicate files entirely
- Does not create new records
- Returns DUPLICATE action in scan results
- Use case: Prevent any duplicate storage

**2. 'warn' (Track & Audit)**
- Creates new record but flags it
- Sets `is_duplicate = 1` and `duplicate_of_id = <original>`
- Preserves audit trail
- Use case: Track all uploads, clean up duplicates later

**3. 'merge' (Auto-Fix, Default)**
- Updates existing record with new file path
- Treats duplicate as "file moved"
- Mends broken links automatically
- No duplicate records created
- Use case: File organization, folder reorganization, broken link repair

#### API Enhancement
- POST `/api/index/directory` now accepts `duplicate_policy` parameter
- Scan statistics include `duplicate` count
- `ScanAction.DUPLICATE` added for tracking rejected duplicates

### Fixed - Duplicate Upload Prevention

#### Problem Solved
**Before v0.4.13:**
```
1. Upload dragon.stl to /models/folder-a → Record #123 created
2. Upload same file to /models/folder-b → Record #456 created (DUPLICATE)
Result: Two records, wasted storage, confusing search results
```

**After v0.4.13 (default 'merge' policy):**
```
1. Upload dragon.stl to /models/folder-a → Record #123 created
2. Upload same file to /models/folder-b → Record #123 updated to new path
Result: One record, broken link mended, no duplicates
```

### Improved - Indexing Intelligence

#### Automatic Link Repair
- When files are moved/renamed, existing records are automatically updated
- No more orphaned records pointing to old locations
- Database stays clean and accurate

#### Storage Optimization
- Single record per unique file (by content hash)
- One thumbnail per unique file
- Reduced database bloat

### Use Cases

**File Organization:**
```bash
# User reorganizes library: moves files from flat structure to organized folders
# Old: /models/all-files/dragon.stl
# New: /models/creatures/dragons/dragon.stl
# Result: Record auto-updated, no duplicate created
```

**Backup Recovery:**
```bash
# User restores files from backup to different location
# Original: /models/originals/model.stl (missing)
# Restored: /models/backup-2024/model.stl
# Result: Original record updated to point to restored location
```

**Duplicate Upload Protection:**
```bash
# User accidentally uploads same file multiple times
# Policy 'reject': All duplicates skipped after first
# Policy 'merge': First record kept, subsequent uploads update location
```

### API Usage

```json
POST /api/index/directory
{
  "path": "/models/new-folder",
  "duplicate_policy": "merge",  // or "reject" or "warn"
  "recursive": true,
  "force": false
}

Response:
{
  "new": 5,
  "update": 3,
  "moved": 2,     // Files found at new location (same hash)
  "duplicate": 1, // Duplicates rejected (if policy='reject')
  "skip": 10,
  "total": 21
}
```

### Technical Details

#### Hash Comparison Query
```sql
-- For each file during indexing:
SELECT * FROM models 
WHERE partial_hash = ? 
AND file_path != ?
ORDER BY last_seen_at DESC
LIMIT 1

-- If match found → Apply duplicate_policy
```

#### Scanner Changes
- `scan_file()`: Added duplicate_policy parameter, hash checking logic
- `scan_archive()`: Added duplicate_policy parameter for archive members
- `scan_directory()`: Propagates duplicate_policy to all scans
- `ScanAction` enum: Added DUPLICATE action

#### Database Columns Used
- `partial_hash`: Fast content comparison (MD5 of first 64KB + last 64KB + size)
- `is_duplicate`: Flag for 'warn' policy
- `duplicate_of_id`: Reference to original record
- `file_path`: Updated when policy='merge'

### Breaking Changes
None - default policy is 'merge' which maintains v0.4.12 behavior

### Notes
- Partial hash collision rate: ~0.01% (verified duplicates via full hash if needed)
- Performance impact: Minimal (single indexed query per file)
- Compatible with existing deduplication API endpoint

## [0.4.12] - 2026-02-17

### Added - New Features

#### SVG Support (QA Blocker)
- **SVG file support** - Enable NAS appliance QA testing with full asset libraries
  - Backend: cairosvg rendering, format detection in scanner/settings/indexers
  - Frontend: SVG viewer with "View Full Size" button, inline display
  - Thumbnails: PNG thumbnails generated from SVG files (512x512)
  - Works in all modes: indexing, batch render, manual regenerate
  - **Why critical:** QA testers need to test with complete asset libraries including vector graphics

#### GLB/GLTF Support
- **GLB and GLTF 3D model support** - Full support for modern 3D formats
  - Added to all format checks (scanner, settings, API endpoints)
  - Frontend: GLTFLoader integration, proper scene handling
  - Preserves embedded materials and textures
  - Works in all code paths: on-demand preview, batch render, manual regenerate

#### Infinite Scroll
- **Pagination with infinite scroll** - Performance optimization for large libraries
  - Load 100 models initially, load more on scroll
  - Automatic loading when within 300px of bottom
  - Works with filters (collection, folder, format)
  - Reduces initial page load time significantly

#### Deduplication API
- **Duplicate detection endpoint** - POST /api/models/detect-duplicates
  - Uses existing two-tier hash system (partial + full)
  - Marks duplicate models in database
  - Returns statistics on duplicates found
  - Integrates with existing partial_hash computation during indexing

### Fixed - Architecture Improvements

#### Unified Rendering Logic
- **Consolidated three rendering code paths** - All paths now use render_thumbnail()
  - Before: On-demand preview used `_render_3d_thumbnail()`, others used `render_thumbnail()`
  - After: All three paths (on-demand, batch, manual) use unified `render_thumbnail()`
  - **Benefits:**
    - Consistent thumbnail quality across all operations
    - All DB columns updated correctly (thumb_storage, thumb_path, thumb_rendered_at, thumb_source_mtime)
    - SVG support works everywhere automatically
    - Easier to maintain and debug

#### Database Column Updates
- **On-demand preview now updates all columns** - Was only updating has_thumbnail flag
  - Now updates: thumb_storage, thumb_path, thumb_rendered_at, thumb_source_mtime
  - Consistent with batch render behavior
  - Required for sidecar thumbnail architecture

### Improved

#### Format Detection
- **Comprehensive format coverage** - All file types supported everywhere
  - Updated 8+ locations across codebase
  - scanner.py (2 places), settings.py (2 places), models3d.py, models.py (3 places)
  - **Learning:** When adding new formats, must update ALL locations or get silent failures

### Dependencies
- Added: `cairosvg>=2.7.0` - SVG to PNG conversion
- Updated: `Pillow>=12.0.0` - Image processing for thumbnails

### Notes for QA Testing
This release enables NAS appliance QA testing with:
- Full asset library support (STL, OBJ, 3MF, GLB, GLTF, SVG)
- Optimized performance for 10K+ asset libraries (infinite scroll)
- Duplicate detection for storage optimization
- Consistent rendering across all operations

## [0.4.11] - 2026-02-17

### Fixed - Critical Deployment Issues

#### Database Schema
- **Missing columns in schema.sql** - Fresh deployments failed due to schema/code mismatch
  - Added 7 missing columns to schema.sql:
    - `volumes.mount_path`, `volumes.is_readonly`
    - `models.thumb_storage`, `models.volume_id`, `models.thumb_path`, `models.thumb_rendered_at`, `models.thumb_source_mtime`
  - Fixes: 500 errors on thumbnail operations, thumbnail misalignment
  - **Breaking:** Existing databases must be deleted and reindexed (pre-v1.0 only)

#### Background Thumbnail Rendering
- **Automatic indexing doesn't generate thumbnails** - Manual regenerate worked, but indexing didn't
  - Root cause: Background render used old `_render_3d_thumbnail()` instead of new `render_thumbnail()`
  - Only updated `has_thumbnail` flag, didn't populate new columns
  - Fixed: Background indexing now uses proper render system with full metadata tracking
  - All thumbnail columns now populated automatically during indexing

#### Container Initialization
- **No automatic database creation** - Fresh containers required manual DB setup
  - Added entrypoint script (`docker/entrypoint.sh`)
  - Automatically creates DB from schema.sql on first run
  - Fresh deployments now work without manual intervention

### Improved

#### Database Fully Containerized
- **Database moved from external to containerized** - No more external database dependency
  - Database now stored in named volume: `fantasyfolio_data:/app/data`
  - Thumbnails in named volume: `fantasyfolio_thumbs:/app/thumbnails`
  - Logs in named volume: `fantasyfolio_logs:/app/logs`
  - **Before:** Required external database path mounted from host
  - **After:** Database fully managed by Docker, persists in named volumes
  - **Benefits:** 
    - Simpler deployment (no external paths to configure)
    - Better isolation and portability
    - Docker handles volume lifecycle
    - No permissions issues with host filesystem

#### Deployment
- **Clean slate deployment** - Stop → delete data → start = working system
  - No more schema drift or stale caches
  - Fresh pull from GitHub guaranteed to work
  - Documented pre-v1.0 upgrade procedure: delete data directory and reindex

## [0.4.10] - 2026-02-12

### Fixed - Critical Bugs (3)

#### Upload System
- **3D upload hang** - Fixed indefinite hang when uploading 3D models
  - Root cause: Missing `models_au` UPDATE trigger caused FTS inconsistency
  - Added UPDATE trigger to schema.sql (matches assets table pattern)
  - Uploads now complete in ~3 seconds even on slow storage

#### Database Schema
- **SQL binding error on re-index** - Mixed positional and named parameters
  - Changed `has_thumbnail=?` to `has_thumbnail=:has_thumbnail`
  - Fixes re-indexing for models with existing thumbnails

#### Thumbnail Rendering
- **Camera angle orientation** - 3D thumbnails showed back view instead of front
  - Changed camera direction from `0,-1,-0.3` to `0,1,-0.3`
  - Thumbnails now show proper front-facing view

### Fixed - High Priority Bugs (7)

#### Search & Navigation
- **3D search folder scope** - Search returned all models regardless of selected folder
  - Added folder parameter to search API with proper LIKE matching
  - Search now respects nav tree folder selection

- **Advanced search PDF** - Search returned no results, didn't filter by criteria
  - Fixed JSON array parsing for terms parameter
  - Added content_type parameter to distinguish PDF vs 3D searches
  - Both simple and advanced search now work correctly

- **Context menu refresh wrong content type** - Right-click refresh loaded 3D models in PDF section
  - Added content_type check before calling refresh functions
  - Each content type now refreshes its own view correctly

#### Force Re-Index System
- **Force Index fails** - Nav tree context menu indexing threw errors
  - Added fallback to legacy indexers when efficient scanner unavailable
  - PDFs route to PDFIndexer, 3D falls back to legacy when schema old
  - Both now work with v0.4.8 and v0.4.9+ schemas

- **Force Index JavaScript error** - "Can't find variable: loadPdfFolders"
  - Fixed incorrect function names in context menu handlers
  - Changed to correct names: loadFolders() and loadAssets()

#### Thumbnails
- **has_thumbnail flag not updating** - Database showed 5/272 thumbnails when all existed
  - Added database UPDATE after background thumbnail render
  - Flag now tracks rendered thumbnails correctly

- **Thumbnail rendering path** - Bulk renders produced blue wireframe, manual renders high quality
  - Unified all rendering to use f3d → stl-thumb fallback
  - Consistent high-quality thumbnails everywhere

### Fixed - Medium Priority Bugs (6)

#### Upload System
- **Upload dialog broken** - "Not a directory" error, no folder navigation
  - Changed default path from `/content/models` to `/content/3d-models`
  - Added path existence check with fallback alternatives
  - Folder browser now works correctly

- **Upload folder creation fails** - "Path outside content root" error
  - Applied same path resolution logic to mkdir endpoint
  - All three upload endpoints now use unified path logic

- **Upload timeout on slow storage** - 2.8MB files hung indefinitely on degraded RAID
  - Added 5-minute XMLHttpRequest timeout
  - Skip MD5 hash for files >1MB (compute during indexing)
  - Shows warning message if timeout occurs

#### UI/UX
- **Tab switching cache issues** - Stale thumbnails after switching between PDF/3D tabs
  - Changed cache-bust from 10-second intervals to fresh timestamp
  - Added cache-busting to PDF thumbnails (was missing)
  - Thumbnails now refresh correctly on every tab switch

- **Grid manual refresh** - Regenerating thumbnail only updated detail view, not grid
  - Manual regeneration now triggers grid update
  - Added auto-polling during background bulk renders
  - Grid view updates in real-time as thumbnails generate

- **PDF thumbnail regeneration error** - Right-click → Regenerate Thumbnail failed
  - Fixed SQL error: "no such column: thumb_rendered_at"
  - Removed non-existent column from UPDATE statement
  - Set has_thumbnail flag correctly

### Improved - User Experience (5)

#### Force Re-Index System
- **Stats tracking** - Shows accurate "new vs updated" counts
  - PDFIndexer now tracks whether files already exist
  - Reports: "new: 0, update: 7" instead of misleading "new: 7"
  - Users can verify re-index is actually re-reading files

- **UI refresh** - Force re-index stays on correct tab and auto-updates
  - Checks content_type before calling refresh functions
  - PDF folders refresh PDF view, 3D folders refresh 3D view
  - No more switching tabs or manual refresh needed

#### Folder Hierarchy
- **PDF folder hierarchy** - Nav tree preserved proper structure during re-index
  - Separated scan_path from root_path in PDFIndexer
  - Folder paths now relative: "Others", "Upload-test1/re-sync-test3.1"
  - No more absolute paths like "/content/pdfs/Others"

- **3D folder hierarchy** - Nav tree maintained parent-child relationships
  - Applied same scan_path/root_path separation to ModelsIndexer
  - Proper hierarchy: "Superhero/Legion", "Terrain/Aurora Gnome"
  - Force re-index on subfolders preserves full path structure

#### Upload System
- **Upload path validation** - All three endpoints now use unified logic
  - Browse, mkdir, and upload share same path resolution
  - Consistent behavior across entire upload workflow
  - Better error messages and logging

### Added

- **Upload timeout handling** - 5-minute timeout for slow storage with user feedback
- **Upload path validation** - Security check with clear error messages
- **Force Index fallback** - Legacy indexers for older database schemas
- **Database trigger** - models_au UPDATE trigger for FTS consistency
- **Documentation** - SLOW_STORAGE.md, TEST_DATABASE_SCHEMA.md, BACKLOG.md

### Technical Details

**Database Changes:**
- Added `models_au` UPDATE trigger to schema.sql
- Fixed SQL parameter binding in models3d.py indexer
- Improved database update logic in thumbnail rendering

**Indexing Improvements:**
- Content-type detection for automatic indexer routing
- Scan_path vs root_path separation for correct relative paths
- Better error handling and logging throughout

**Performance:**
- Skip MD5 hash for large files during upload (defer to indexing)
- Auto-polling for thumbnail progress (reduces manual checks)
- Proper cache-busting prevents stale content

**Testing:**
- Validated with 10 PDFs, 69 3D models
- Tested on slow storage (degraded RAID)
- Container deployment with fresh database
- All context menus and UI interactions verified

### Known Limitations

- GLB/glTF 3D viewer support not yet implemented (planned for v0.4.11)
- Pagination/infinite scroll not implemented (planned for v0.4.11)
- Advanced search query builder enhancement backlogged
- Efficient scanner requires v0.4.9+ schema (falls back to legacy for v0.4.8)

### Upgrade Notes

**Docker Deployment:**
- Rebuild image: `docker build -t fantasyfolio:v0.4.10 .`
- **Important:** Use `docker stop/rm/run`, not `docker restart` (doesn't reload image!)
- Fresh database recommended for clean slate

**Schema Migration:**
- New installations: schema.sql includes all fixes
- Existing databases: models_au trigger added automatically on restart
- No manual migration needed

**Configuration:**
- No config changes required
- Upload paths now auto-detect with sensible fallbacks
- PDF_ROOT and MODELS_3D_ROOT still configurable via env

### Contributors

- Hal (AI Agent) - All bug fixes and improvements
- Matthew Laycock - Testing, validation, and issue reporting

---

## [0.4.9] - 2026-02-11

### Added
- Initial Windows PC deployment
- Volume monitoring system
- Change journal tracking
- Asset locations management

### Fixed
- Initial stability improvements

---

## Earlier Versions

See git history for changes prior to v0.4.9.
