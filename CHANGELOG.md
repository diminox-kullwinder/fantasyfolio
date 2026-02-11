# Changelog

## [0.4.9] - 2026-02-10

### Added
- **GLB/glTF Support**: Full support for GL Transmission Format models
  - Indexing: GLB and glTF files now detected and indexed
  - Thumbnails: f3d renders GLB/glTF with full texture support
  - Format filter: New GLB and glTF options in dropdown
  - Upload: GLB/glTF files accepted in upload modal

### Fixed
- **Thumbnail Persistence**: Thumbnails now stored in `/app/data/thumbnails/` (persisted volume) instead of `/app/thumbnails/` (lost on container restart)
- **Camera Angle**: f3d now renders from front view with slight downward angle (`--camera-direction=0,-1,-0.3`) - better for character miniatures
- **Sorting (Models)**: Sort dropdown now works for 3D models tab (was missing sort/order params)
- **Sorting (PDFs)**: Fixed PDF sorting - now properly passes sort/order to backend
- **API Sorting**: Both `/api/models` and `/api/assets` endpoints now support `sort` and `order` query parameters
  - Valid model sorts: filename, title, file_size, format, collection, created_at
  - Valid asset sorts: filename, title, file_size, page_count, publisher, created_at, modified_at

### Changed
- **Thumbnail Daemon Config**: Updated supervisor config paths (note: autostart still false by default)
- **Upload Hints**: Now shows GLB/glTF in accepted formats

### Technical Details
- Files modified: 11 (schema, 4 API modules, 2 core modules, 2 indexer modules, 1 service, 1 template)
- Thumbnail storage: `Config.THUMBNAIL_DIR` = `DATA_DIR / "thumbnails"`
- f3d camera: `--up +Z --camera-direction=0,-1,-0.3`

---

## [0.4.0] - 2026-02-09

### 🎉 Rebranded to FantasyFolio

This release marks the official rebrand from "DAM" (Digital Asset Manager) to **FantasyFolio**.

### Changed
- **Package renamed**: `dam/` → `fantasyfolio/`
- **All imports updated**: `from dam.` → `from fantasyfolio.`
- **App name**: "Digital Asset Manager" → "FantasyFolio"
- **Environment variables**: Now use `FANTASYFOLIO_*` prefix (e.g., `FANTASYFOLIO_DATABASE_PATH`)
  - **Backward compatible**: `DAM_*` variables still work as fallback
- **CLI**: `python -m fantasyfolio.cli run`
- **UI**: Title and header now show "FantasyFolio"
- **API health**: Returns `{"service": "FantasyFolio API", ...}`

### Added
- GitHub Container Registry support (`ghcr.io/diminox-kullwinder/fantasyfolio`)
- GitHub Actions CI/CD for automated Docker builds
- SSH access in container for remote debugging
- Supervisor process management in container
- Windows deployment documentation

### Migrating from DAM
1. Your existing database is fully compatible
2. Update your `.env` file to use `FANTASYFOLIO_*` variables (optional — `DAM_*` still works)
3. Update CLI commands: `python -m dam.cli` → `python -m fantasyfolio.cli`
4. Update imports if you have custom scripts: `from dam.` → `from fantasyfolio.`

---

## [0.3.1] - 2026-02-09

### Added
- **Tiered Thumbnail Processing** (Fast/Slow Lane Architecture)
  - Files partitioned by size: < 30MB (fast lane), > 30MB (slow lane)
  - Fast lane: 28 workers, 100 batch, 120s timeout → ~45 renders/sec
  - Slow lane: 4 workers, 10 batch, 600s timeout → dedicated for large files
  - Prevents large files from blocking small file processing
  - Parallel execution: both lanes run simultaneously
  - Documentation: `docs/INDEXING_STRATEGY.md`
  - **Performance impact**: 22K small files in ~8 minutes (was 24+ hours with blocking)

- **Deduplication System** (Two-tier collision detection, auto-triggered)
  - Partial hash collisions → full hash verification workflow
  - `dam/core/deduplication.py` with `find_partial_hash_collisions()`, `verify_collision()`, `process_duplicates()`
  - **Auto-trigger**: `compute-hashes` automatically runs deduplication when complete
  - Manual CLI also available: `python -m dam.cli detect-duplicates`
  - Documentation: `docs/DEDUPLICATION.md`

### Fixed
- **Thumbnail Daemon Database Path**: Fixed `.env.local` loading to use correct database
- **Orphan Cleanup**: Removed 29,964 orphaned PNG files (~1.4GB) from old database state
- Documentation: `docs/THUMBNAIL_PERFORMANCE_FIX.md`

---

## [0.3.0] - 2026-02-07

### Added
- Settings UI with Asset Locations management
- SFTP auto-hidden on macOS/Windows (requires macFUSE)
- SSH key workflow redesigned
- PR/Release workflow via GitHub API

---

## [0.2.0] - 2026-02-05

### Added
- 3D Model indexing with STL, OBJ, 3MF support
- ZIP archive scanning for nested models
- Thumbnail rendering with stl-thumb
- Collection/folder organization

---

## [0.1.0] - 2026-02-01

### Added
- Initial PDF asset management
- Full-text search with SQLite FTS5
- Folder navigation
- Basic thumbnail generation
