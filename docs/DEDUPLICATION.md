# Deduplication System (v0.3.1)

**Status**: IMPLEMENTED  
**Approach**: Two-tier collision detection + full hash verification  
**Trigger**: **Automatic** — runs when `compute-hashes` completes (or manual via CLI)

---

## Overview

The deduplication system identifies duplicate files in your DAM using a **hybrid approach** that balances **speed** (partial hash) with **accuracy** (full hash verification).

## How It Works

### Phase 1: Partial Hash (Fast, Already Running)
- **Algorithm**: MD5(first 64KB + last 64KB + file_size)
- **Time**: ~1-5ms per file
- **Purpose**: Quick fingerprint for all assets
- **Result**: Identifies potential duplicates (collision candidates)
- **Accuracy**: ~99.9% (very few false positives)

### Phase 2: Collision Detection (Automatic)
Once partial hash finishes, query for duplicates:
```sql
SELECT partial_hash, COUNT(*) FROM models 
GROUP BY partial_hash 
HAVING COUNT(*) > 1
```

**Expected result**: ~50-100 collision pairs out of 34,074 files

### Phase 3: Full Hash Verification (On-Demand)
For each collision pair, compute **full MD5**:
- Only files with matching partial hashes
- Confirms whether files are actually identical
- Results:
  - ✓ **Match**: True duplicate (same content)
  - ✗ **Mismatch**: False alarm (same start/end/size, different middle)

### Phase 4: Database Update
Mark verified duplicates:
```
is_duplicate = 1
duplicate_of_id = [primary file ID]
full_hash = [MD5 of entire file]
```

Primary selection rule: **Keep the file with the lower ID** (appeared first during scan)

---

## Running Deduplication

### Automatic Trigger (Default Behavior)

**Deduplication runs automatically** when `compute-hashes` completes:

```bash
# This command handles everything:
python -m dam.cli compute-hashes --type models

# When partial hashing finishes, you'll see:
# 🔎 All models hashed — auto-running deduplication...
# 📊 Deduplication Results:
#   Collision pairs checked: 45
#   True duplicates found: 8
#   ...
```

No manual step required — it's a true fallback that triggers itself.

### Manual Trigger (Optional)

If you need to re-run deduplication separately:

```bash
# Detect duplicates in 3D models
python -m dam.cli detect-duplicates --type models

# Detect duplicates in PDFs
python -m dam.cli detect-duplicates --type assets

# Detect duplicates in both
python -m dam.cli detect-duplicates --type all
```

### Prerequisites
1. **Partial hash must complete first** (auto-checked)
2. **Use the correct database path** (.env.local must be set)

### Output Example

```
🔎 Detecting duplicates in models...

🔍 Step 1: Finding partial hash collisions...
  Found 45 collision pairs to verify

🔐 Step 2: Computing full hashes for collision verification...
  ✓ [1/45] Duplicate found:
    Keep: Terrain_Dungeon_v1.3mf (ID: 1234)
    Mark: Terrain_Dungeon_v1_copy.3mf (ID: 5678)
    Hash: a1b2c3d4e5f6... (125.3MB)
  ✓ [2/45] Duplicate found:
    ...
  ✓ Full hash verification complete
  Found 8 true duplicates

💾 Step 3: Updating database...
  ✓ Database updated

📊 Results for models:
  Partial hash collisions: 45
  True duplicates found: 8
  Full hashes computed: 90
  Database entries updated: 16
  Errors: 0
  Time elapsed: 23.4s
```

---

## Database Schema

Three new columns on `models` and `assets` tables:

| Column | Type | Purpose |
|--------|------|---------|
| `full_hash` | TEXT | Complete MD5 hash (only for verified duplicates + primaries) |
| `is_duplicate` | INTEGER | 1 = duplicate, 0 = original |
| `duplicate_of_id` | INTEGER | ID of primary file (NULL if not a duplicate) |

### Querying Duplicates

```sql
-- Find all duplicates
SELECT id, filename, duplicate_of_id 
FROM models 
WHERE is_duplicate = 1
ORDER BY duplicate_of_id;

-- Show duplicate pairs
SELECT 
  p.id as primary_id, p.filename as primary_name,
  d.id as dup_id, d.filename as dup_name,
  p.file_size, p.full_hash
FROM models p
LEFT JOIN models d ON d.duplicate_of_id = p.id
WHERE d.id IS NOT NULL
ORDER BY p.id;

-- Count duplicates saved space
SELECT 
  COUNT(*) as duplicate_count,
  ROUND(SUM(file_size) / (1024*1024*1024.0), 2) as space_wasted_gb
FROM models
WHERE is_duplicate = 1;
```

---

## Performance

| Operation | Files | Time |
|-----------|-------|------|
| Partial hash all models | 34,074 | ~30 min |
| Collision detection query | - | <1 sec |
| Full hash for collisions | ~90 | ~20-30 sec |
| Database update | ~16 | <1 sec |
| **Total time** | - | **~30 min + 30 sec** |

The bottleneck is partial hash (already running). Full hash verification is negligible.

---

## What Happens to Duplicates?

Current behavior: **Marked but not deleted**

Options for handling duplicates:
- **Option A** (Current): Keep marked, do nothing
- **Option B**: Manual delete from UI  (recommended)
- **Option C**: Auto-delete duplicates (risky, not recommended)
- **Option D**: Soft-delete with trash recovery (future feature)

Recommendation: **Keep marked, then manually delete** one file at a time if desired. This preserves audit trail and prevents accidents.

---

## Future Enhancements

1. **Deduplication API**: `/api/duplicates/list`, `/api/duplicates/merge`
2. **UI Display**: Show duplicate warnings in asset browser
3. **Auto-cleanup**: Option to soft-delete duplicates
4. **Storage report**: Show disk space saved by removing duplicates
5. **Multiple versions**: Track which is "best" version of duplicate set

---

## Troubleshooting

### "No collisions found"
- Partial hash job may not be complete
- Check: `SELECT COUNT(*) FROM models WHERE partial_hash IS NULL`
- If non-zero, wait for partial hash to finish

### "Error reading file"
- File may have moved or been deleted
- Check: `SELECT COUNT(*) FROM models WHERE file_path IS NULL OR NOT EXISTS(file_path)`
- Archive members may have been renamed/moved

### "Process timeout"
- Large files can take 30+ seconds
- Full hash timeout is 300 seconds, should be sufficient
- Check log for specific failures

---

## Implementation Details

**File**: `dam/core/deduplication.py`

Key functions:
- `find_partial_hash_collisions()` - Find candidates
- `get_file_content()` - Read files/archives
- `verify_collision()` - Compute full hashes
- `process_duplicates()` - Orchestrate full workflow

**CLI**: `dam/cli.py detect-duplicates` command

---

## Testing

To test with a small set:

```bash
# Create test duplicates in UAT database
cd /Users/claw/projects/dam

# Run deduplication
python -m dam.cli detect-duplicates --type models

# Verify results
sqlite3 data/dam.db \
  "SELECT COUNT(*) as duplicates FROM models WHERE is_duplicate = 1"
```

