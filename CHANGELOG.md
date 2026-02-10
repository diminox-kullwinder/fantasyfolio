# Changelog

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
  - Database: `is_duplicate`, `duplicate_of_id`, `full_hash` columns on models/assets
  - Only computes full hash for collision candidates (~50-100 files), not all 34,074
  - Marks duplicates in database; keeps original based on lower ID
  - Documentation: `docs/DEDUPLICATION.md`
  - Expected runtime: ~30 seconds after partial hash completes

### Fixed
- **Thumbnail Daemon Performance Regression** (204x speedup)
  - Root cause: Severely undersized parallelism limits
  - Worker pool increased: 2 → 32 concurrent renders
  - Batch processing: 10 → 200 items per cycle
  - Job polling interval: 30s → 2s faster job pickup
  - Render timeout: 120s → 300s (fixes timeouts on complex 3MF models)
  - Bug: Daemon not loading `.env.local` config (now uses dotenv)
  - **Performance impact**: 0.23 renders/sec → 50-60 renders/sec (previously saw 76/sec)
  - **Speed improvement**: 204x-330x faster than broken state
  - All 34,074 live models now render in ~10 minutes (was 150+ hours at old speed)

### Changed
- `scripts/thumbnail_daemon.py` completely rewritten for tiered processing (v2)
  - Now loads `.env.local` for proper database path resolution
  - Dual-lane architecture with parallel thread pools
  - Size-based queue partitioning at 30MB threshold
  - Updates `has_thumbnail` flag in database after successful render
- Tuned subprocess rendering approach for high-concurrency workloads

### Documentation
- `docs/INDEXING_STRATEGY.md` — **NEW** Comprehensive indexing architecture guide
- `docs/DEDUPLICATION.md` — **NEW** Two-tier deduplication system
- `docs/THUMBNAIL_PERFORMANCE_FIX.md` — **NEW** Performance analysis and fixes

### Testing
- Validated on live database (34,074 models)
- Fast lane: 22,031 files queued, ~45 renders/sec
- Slow lane: 7,866 files queued, dedicated processing
- Deduplication: CLI tested, auto-trigger verified
- System stable under 28+4 concurrent worker load

---

## [0.3.0] - 2026-02-07

### Added
- **Asset Locations Management**
  - Add/edit/delete asset locations from Settings UI
  - Support for Local, Network Mount (SMB), and SFTP location types
  - SFTP option auto-hidden on macOS/Windows (requires sshfs)
  - Test Connection button for validating paths
  - Remount button for network-mounted volumes
  - Migration script `003_add_asset_locations.py`

- **SSH Key Workflow Improvements**
  - "Use Existing" dropdown shows available keys
  - "Create New Key" with clear naming
  - "Advanced: SSH Config" moved to bottom with documentation link
  - New endpoint `/api/ssh/key/public` for fetching public keys

- **Settings UI Overhaul**
  - Index buttons moved to dedicated "🔄 Reindex Library" section
  - Renamed Index to "Scan" with explanatory text
  - Asset Locations list with action buttons (Test, Index, Edit menu)
  - Edit menu: Change Path, Disable, Delete with confirmation
  - Removed redundant Volume Status section

### Changed
- Platform-aware UI: SFTP hidden on non-Linux hosts
- Consolidated pdf_root/3d_root/smb_paths into asset_locations table

### Database Migrations
- `003_add_asset_locations.py` - Creates asset_locations table

---

## [0.2.0] - 2026-02-07

### Added
- **Backup & Recovery System** - Multi-layer data protection
  - Volume monitoring: Prevents operations when storage offline
  - Soft deletes with Trash: 30-day recovery window for deleted items
  - Change journal: Audit trail of all modifications
  - SQLite snapshots: Point-in-time local database backups
  - Backup policies: Automated backups with Restic deduplication

- **Restic Integration** for deduplicated backups
  - Local and remote (SFTP) repository support
  - Block-level deduplication (80-90% space savings)
  - One-click restore from any snapshot
  - Auto-initialize repos on first backup
  - Configurable retention policies

- **Settings UI Enhancements**
  - Resizable settings modal (percentage-based)
  - Server-side directory browser with folder creation
  - Full backup scheduling: frequency, time, start date, retention
  - SSH key generation and management
  - Password confirmation for Restic repositories
  - Test Connection for remote backups

- **New API Endpoints**
  - `/api/trash` - Soft delete management
  - `/api/journal/*` - Change journal queries
  - `/api/snapshots/*` - Snapshot management
  - `/api/backup/policies/*` - Backup policy CRUD
  - `/api/restic/*` - Restic operations
  - `/api/ssh/*` - SSH key management
  - `/api/browse-directories` - Server-side file browser
  - `/api/system/volume-status` - Volume availability checks

- **Documentation**
  - `docs/BACKUPS.md` - Comprehensive backup system guide

### Changed
- Index buttons show ⏸️ SUSPENDED when volumes unavailable (still clickable)
- Downloads return 503 with error modal when volume offline
- Settings restructured into General + Advanced tabs

### Database Migrations
- `001_add_soft_delete.py` - Adds deleted_at column to assets/models
- `002_add_change_journal.py` - Creates change_journal table
