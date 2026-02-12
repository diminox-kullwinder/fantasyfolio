# Changelog

All notable changes to FantasyFolio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
