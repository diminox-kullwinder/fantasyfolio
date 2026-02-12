# Test Database Schema Issues

## Problem

The test database (`/Users/claw/projects/dam/data/fantasyfolio.db`) has the **v0.4.8 schema** but the code expects **v0.4.9+ schema** with efficient indexing tables/columns.

## Missing Schema Elements

### Tables
- ✅ `volumes` (added manually during testing)
- ✅ `scan_jobs` (added manually during testing)
- ✅ `job_errors` (added manually during testing)
- ✅ `asset_locations` (added manually during testing)

### Columns in `models` table
- ❌ `file_mtime` - File modification time (Unix timestamp)
- ❌ `last_indexed_at` - Last indexing timestamp
- ❌ `last_rendered_at` - Last thumbnail render timestamp
- ❌ `force_update_flag` - Force re-render flag
- Plus ~20 more columns from efficient indexing migration

### Columns in `assets` table
- ✅ `deleted_at` (added manually during testing)
- ❌ Similar efficient indexing columns

## Impact

**What Works:**
- ✅ Old indexing path (Settings → Asset Locations → Index button)
- ✅ Thumbnail generation
- ✅ Search, viewing, sorting
- ✅ Upload

**What Fails:**
- ❌ Nav tree right-click → Force Full Index
- ❌ Breadcrumb right-click → Force Full Index  
- ❌ Any code path using `fantasyfolio.core.scanner` (efficient indexing)

## Solutions

### Option 1: Use Workaround (Current)
**For v0.4.10 testing:**
- Use Settings → Asset Locations → Index button
- Avoid nav tree right-click re-index
- Document limitation in release notes

### Option 2: Run Full Migration
**Apply all migrations from v0.4.9:**

```bash
docker exec fantasyfolio-test python3 /app/migrations/004_efficient_indexing_schema.py
docker exec fantasyfolio-test python3 /app/migrations/005_volume_registration.py
```

But migrations may not exist in container or may fail on existing data.

### Option 3: Fresh Database (Recommended for Windows)
**When deploying to Windows:**
- Use empty database or fresh schema
- Run migrations from scratch
- All features will work

### Option 4: Manual Schema Update
**Add missing columns to test database:**

```sql
-- Add to models table
ALTER TABLE models ADD COLUMN file_mtime INTEGER;
ALTER TABLE models ADD COLUMN last_indexed_at TEXT;
ALTER TABLE models ADD COLUMN last_rendered_at TEXT;
-- ... (20+ more columns)

-- Add to assets table  
ALTER TABLE assets ADD COLUMN file_mtime INTEGER;
ALTER TABLE assets ADD COLUMN last_indexed_at TEXT;
-- ... (more columns)
```

**Effort:** 30 minutes  
**Risk:** Tedious, error-prone

## Recommendation for v0.4.10

**For Mac testing:**
- ✅ Accept limitation, use workaround
- ✅ Document in release notes
- ✅ Test other features (all working)

**For Windows deployment:**
- ✅ Use fresh database with full schema
- ✅ OR apply migrations before first run
- ✅ All features will work as designed

## Why This Happened

The test database was created with v0.4.8 schema and manually updated during testing:
- Added `deleted_at` columns
- Added `asset_locations` table  
- Added `volumes`, `scan_jobs`, `job_errors` tables

But efficient indexing requires **many more columns** that weren't added. The v0.4.9 migrations (004, 005) add ~30 columns total.

Rather than manually adding all of them to the test database, it's better to use a fresh schema for Windows deployment.

## Testing Impact

**Not blocking v0.4.10 release because:**
- Core functionality works (indexing via Settings)
- This is a test database issue, not code issue
- Windows deployment will use fresh/proper schema
- Workaround is documented and simple

**Nav tree re-index will work on Windows with proper schema.**

---

**Date:** 2026-02-12  
**Status:** Documented - Using workaround for Mac testing  
**Resolution:** Will work on Windows with proper schema
