# Changelog

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
