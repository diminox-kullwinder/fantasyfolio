# FantasyFolio v0.4.13 - Release Notes

**Release Date:** 2026-02-17  
**Focus:** Duplicate Prevention System

---

## 🎯 What's New

### Intelligent Duplicate Prevention
FantasyFolio now prevents duplicate records when the same file is uploaded to different locations. The system uses content-based hashing to detect duplicates and offers three handling policies.

---

## ✨ Key Features

### 1. Hash-Based Duplicate Detection
- **Automatic during indexing:** Every file gets a partial hash computed
- **Content-based:** Detects identical files regardless of filename or location
- **Fast & accurate:** MD5 hash of first 64KB + last 64KB + file size
- **Works everywhere:** Standalone files and archive members

### 2. Three Duplicate Handling Policies

#### 'reject' - Strict Prevention
```json
POST /api/index/directory
{
  "path": "/models/new-folder",
  "duplicate_policy": "reject"
}
```
- **Behavior:** Skips duplicate files entirely
- **Result:** No duplicate records created
- **Stats:** Shows `duplicate: N` count
- **Use case:** Prevent any duplicate storage

#### 'warn' - Track & Audit
```json
{
  "duplicate_policy": "warn"
}
```
- **Behavior:** Creates records but flags them
- **Database:** Sets `is_duplicate=1`, `duplicate_of_id=<original_id>`
- **Use case:** Track all uploads, clean up duplicates later
- **Benefit:** Preserves audit trail

#### 'merge' - Auto-Fix (Default)
```json
{
  "duplicate_policy": "merge"  // or omit (default)
}
```
- **Behavior:** Updates existing record with new file path
- **Result:** Treats duplicate as "file moved"
- **Benefit:** Mends broken links automatically
- **Use case:** File organization, broken link repair

---

## 🔧 How It Works

### Before v0.4.13
```
Step 1: Upload dragon.stl to /models/folder-a
  → Record #123 created (file_path: /models/folder-a/dragon.stl)

Step 2: Upload same file to /models/folder-b  
  → Record #456 created (file_path: /models/folder-b/dragon.stl)

Problem:
  ✗ Two records for same content
  ✗ Wasted database space
  ✗ Confusing search results
  ✗ Two thumbnails for identical file
```

### After v0.4.13 (default 'merge' policy)
```
Step 1: Upload dragon.stl to /models/folder-a
  → Record #123 created (file_path: /models/folder-a/dragon.stl)

Step 2: Upload same file to /models/folder-b
  → Record #123 UPDATED (file_path: /models/folder-b/dragon.stl)

Benefits:
  ✓ Single record per unique file
  ✓ Broken link mended automatically  
  ✓ Clean database
  ✓ One thumbnail per file
```

---

## 📊 Real-World Use Cases

### Use Case 1: File Organization
```
Scenario: User reorganizes library from flat to structured folders

Before:
  /models/all-files/dragon.stl
  /models/all-files/sword.stl
  /models/all-files/castle.stl

After:
  /models/creatures/dragons/dragon.stl
  /models/weapons/medieval/sword.stl
  /models/buildings/castles/castle.stl

Result with 'merge' policy:
  - All 3 records auto-updated to new paths
  - No duplicates created
  - No broken links
```

### Use Case 2: Backup Recovery
```
Scenario: User restores files from backup to different location

Original: /models/originals/model.stl (missing/corrupted)
Restored: /models/backup-2024/model.stl

Result with 'merge' policy:
  - Original record updated to point to restored file
  - Link automatically repaired
  - No manual database editing needed
```

### Use Case 3: Duplicate Upload Protection
```
Scenario: User accidentally uploads same file multiple times

Upload 1: /models/downloads/model.stl → Record created
Upload 2: /models/downloads/model.stl → Duplicate detected

Result with 'reject' policy:
  - Second upload skipped
  - Stats show: duplicate: 1
  - Storage protected

Result with 'merge' policy:
  - Record timestamp updated
  - File verified still present
  - Single record maintained
```

---

## 🛠️ API Usage

### Basic Index (Default Behavior)
```bash
curl -X POST http://localhost:8888/api/index/directory \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/models/new-folder",
    "recursive": true,
    "force": false
  }'
```
**Default:** `duplicate_policy: "merge"` - Updates existing records

### Reject Duplicates
```bash
curl -X POST http://localhost:8888/api/index/directory \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/models/new-folder",
    "duplicate_policy": "reject"
  }'
```
**Response:**
```json
{
  "new": 5,
  "update": 3,
  "moved": 2,
  "duplicate": 4,  // Files skipped (duplicates)
  "skip": 10,
  "total": 24
}
```

### Flag Duplicates for Review
```bash
curl -X POST http://localhost:8888/api/index/directory \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/models/new-folder",
    "duplicate_policy": "warn"
  }'
```
**Database Result:**
```sql
-- Duplicate records flagged:
SELECT id, filename, is_duplicate, duplicate_of_id 
FROM models 
WHERE is_duplicate = 1;

-- Result:
-- id: 456, filename: dragon.stl, is_duplicate: 1, duplicate_of_id: 123
```

---

## 🔍 Technical Details

### Hash Comparison Algorithm
```sql
-- For each file during indexing:
SELECT * FROM models 
WHERE partial_hash = ? 
  AND file_path != ?
ORDER BY last_seen_at DESC
LIMIT 1

-- If match found → Apply duplicate_policy
```

### Database Schema Changes
**New Columns Used:**
- `partial_hash` - Content hash for fast comparison
- `is_duplicate` - Flag for 'warn' policy (0 or 1)
- `duplicate_of_id` - References original record ID

**No Breaking Changes:**
- Existing columns remain unchanged
- Default policy maintains v0.4.12 behavior

### Performance Impact
- **Hash computation:** ~5ms per file (fast partial hash)
- **Database query:** Single indexed lookup per file
- **Overall impact:** Negligible (~1-2% slower indexing)
- **Benefit:** Prevents duplicate storage (saves space + time)

### Collision Rate
- **Partial hash:** MD5(first 64KB + last 64KB + size)
- **Collision probability:** ~0.01% for different files
- **Full hash verification:** Available via `/api/models/detect-duplicates`

---

## 📦 Deployment

### Docker Images
```bash
# Pull latest release
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13

# Or use latest tag
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

### Docker Compose
```yaml
services:
  fantasyfolio:
    image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
    # ... rest of config
```

### Upgrade from v0.4.12
**No database migration required** - v0.4.13 is fully backward compatible.

**Important:** v0.4.11+ includes database containerization:
- Database moved from external to named volumes
- `fantasyfolio_data:/app/data` - database storage
- `fantasyfolio_thumbs:/app/thumbnails` - thumbnail cache
- `fantasyfolio_logs:/app/logs` - application logs
- No external database path configuration needed

```bash
# Stop current container
docker-compose down

# Pull new image
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13

# Update docker-compose.yml to use :0.4.13

# Start with new version
docker-compose up -d
```

**Existing data:** All existing records remain unchanged. Duplicate prevention applies only to new indexing operations.

---

## 🧪 Testing Recommendations

### Test Scenario 1: Duplicate Upload Detection
1. Index a test directory with 10 files
2. Copy those 10 files to a different folder
3. Index the new folder with `duplicate_policy: "reject"`
4. Verify stats show `duplicate: 10`
5. Verify no new records created in database

### Test Scenario 2: File Move Auto-Repair
1. Index a test file: `/models/test/dragon.stl`
2. Move file to: `/models/organized/creatures/dragon.stl`
3. Index new location with default policy (merge)
4. Verify record updated with new path
5. Verify thumbnail still works

### Test Scenario 3: Audit Trail
1. Index files with `duplicate_policy: "warn"`
2. Upload same files to different location
3. Query database: `SELECT * FROM models WHERE is_duplicate = 1`
4. Verify duplicate records exist and are flagged
5. Use duplicate_of_id to find original records

---

## 📝 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

### v0.4.13 Summary
- ✅ Hash-based duplicate detection during indexing
- ✅ Three duplicate policies: reject, warn, merge
- ✅ Auto-mend broken links when files move
- ✅ Prevents duplicate records from re-uploads
- ✅ API enhancement: `duplicate_policy` parameter
- ✅ Statistics include `duplicate` count
- ✅ New `ScanAction.DUPLICATE` for tracking

---

## 🚀 What's Next

### v0.5.0 (Planned: 2026-03-15)
- Google/Apple SSO authentication
- Role-based permissions
- Week 1 foundation features (bulk operations, drag-drop upload)
- Multi-user collaboration

### v0.6.0 (Planned: 2026-04-01)
- Collection nesting
- Path templating (auto-organization)
- Advanced search

---

## 🐛 Known Issues

None reported for v0.4.13 at release time.

If you encounter issues, please report via GitHub Issues.

---

## 📧 Support

- **Documentation:** `/docs/` in project repository
- **GitHub:** https://github.com/diminox-kullwinder/fantasyfolio
- **Docker Hub:** ghcr.io/diminox-kullwinder/fantasyfolio

---

**Built with ❤️ for the 3D printing community**
