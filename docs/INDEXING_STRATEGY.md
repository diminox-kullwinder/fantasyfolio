# Indexing Strategy & Architecture

**Version**: 0.3.1  
**Updated**: February 9, 2026  

---

## Overview

DAM uses a multi-phase indexing strategy optimized for large libraries (30K+ assets) stored on network volumes (SMB/NFS). The system balances **speed** (partial hashes, tiered rendering) with **accuracy** (full hash verification for duplicates).

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     INDEXING PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DISCOVERY        2. HASHING           3. THUMBNAILS         │
│  ─────────────       ─────────────        ─────────────         │
│  Scan volumes   →    Partial hash    →    Tiered rendering      │
│  Register files      (64KB chunks)        Fast lane (<30MB)     │
│  Track mtimes        Full hash            Slow lane (>30MB)     │
│                      (collisions only)                          │
│                                                                  │
│  4. DEDUPLICATION    5. VERIFICATION                            │
│  ─────────────       ─────────────                              │
│  Auto-triggered      Periodic checks                            │
│  Collision detect    Missing file detect                        │
│  Mark duplicates     Volume availability                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Asset Discovery

### Volume Registration
Assets are organized by **volumes** — mounted storage locations (local, SMB, NFS).

```sql
-- volumes table
CREATE TABLE volumes (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    mount_path TEXT NOT NULL,
    status TEXT DEFAULT 'online',
    last_indexed_at TEXT
);
```

### File Scanning
The scanner walks each volume, registering files with:
- `file_path` — Full path to file
- `file_size` — Size in bytes
- `file_mtime` — Last modification timestamp
- `volume_id` — Parent volume reference

**Skip logic**: Files are skipped if `mtime` and `size` unchanged since last scan.

---

## Phase 2: Content Hashing

### Two-Tier Hashing Strategy

| Hash Type | Algorithm | Speed | Purpose |
|-----------|-----------|-------|---------|
| **Partial** | MD5(first 64KB + last 64KB + size) | Fast (~1ms) | Initial fingerprint |
| **Full** | MD5(entire file) | Slow (50-200ms) | Collision verification |

### Partial Hash
Computed for **all assets** during indexing:
```python
def compute_partial_hash(file_path):
    hasher = hashlib.md5()
    hasher.update(first_64KB)
    hasher.update(last_64KB)
    hasher.update(str(file_size))
    return hasher.hexdigest()
```

**Accuracy**: ~99.9% unique identification. Two different files with same partial hash are extremely rare.

### Full Hash
Computed **only for collision candidates** (files with matching partial hash):
```python
# Only runs when:
# SELECT partial_hash, COUNT(*) FROM models 
# GROUP BY partial_hash HAVING COUNT(*) > 1
```

**Trigger**: Automatic when `compute-hashes` completes (see Deduplication).

### CLI Commands

```bash
# Compute partial hashes (auto-triggers dedup when done)
python -m dam.cli compute-hashes --type models

# Manual deduplication run
python -m dam.cli detect-duplicates --type models
```

---

## Phase 3: Thumbnail Rendering

### Tiered Processing Architecture

Large files over network storage can block the rendering queue. DAM uses **parallel processing lanes** to prevent this:

```
┌──────────────────────────────────────────────────────────────┐
│                   THUMBNAIL DAEMON v2                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│   FAST LANE                      SLOW LANE                   │
│   ─────────                      ─────────                   │
│   Files < 30MB                   Files > 30MB                │
│   28 workers                     4 workers                   │
│   Batch: 100                     Batch: 10                   │
│   Timeout: 120s                  Timeout: 600s               │
│   ~45 renders/sec                ~1 render/min               │
│                                                               │
│   ETA: ~8 minutes                ETA: ~2-3 hours             │
│   (for 22K files)                (for 8K files)              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Why Two Lanes?

| Problem | Solution |
|---------|----------|
| Large files (50-100MB) take 2-5 min over SMB | Dedicated slow lane |
| Small files blocked waiting for large ones | Fast lane runs independently |
| 32 workers all reading big files = SMB congestion | Fewer workers on large files |
| Progress appears stuck | Fast lane shows rapid progress |

### Configuration

In `scripts/thumbnail_daemon.py`:
```python
SIZE_THRESHOLD_MB = 30   # Cutoff between fast/slow
FAST_WORKERS = 28        # High parallelism for small files
SLOW_WORKERS = 4         # Low parallelism for large files
FAST_TIMEOUT = 120       # 2 min for small files
SLOW_TIMEOUT = 600       # 10 min for large files
```

### Render Tool

Uses `stl-thumb` for 3D model thumbnails:
```bash
stl-thumb -s 512 input.stl output.png
```

Supports: STL, OBJ, 3MF formats.

### Database Tracking

```sql
-- Updated after successful render
UPDATE models SET has_thumbnail = 1 WHERE id = ?
```

---

## Phase 4: Deduplication

### Automatic Trigger

When `compute-hashes` completes (all partial hashes computed), deduplication runs automatically:

1. **Find collisions**: Query for duplicate partial hashes
2. **Verify with full hash**: Compute MD5 of entire file for candidates
3. **Mark duplicates**: Update database with `is_duplicate = 1`

### Database Schema

```sql
-- Added to models/assets tables
is_duplicate INTEGER DEFAULT 0,
duplicate_of_id INTEGER,
full_hash TEXT
```

### Duplicate Selection Rule

When two files are confirmed duplicates:
- **Keep**: File with lower ID (appeared first during scan)
- **Mark**: File with higher ID flagged as duplicate

### Expected Results

For a library of 34,074 models:
- Partial hash collisions: ~50-100 pairs
- True duplicates: ~5-15 files
- Full hash runtime: ~30 seconds

See `docs/DEDUPLICATION.md` for full details.

---

## Phase 5: Verification

### Missing File Detection

Periodic scans check if indexed files still exist:
```python
# Mark missing files (don't auto-delete)
UPDATE models SET missing_since = datetime('now') 
WHERE file_path NOT IN (SELECT path FROM filesystem_scan)
```

### Volume Availability

Before operations, check if volumes are mounted:
```python
# volumes.status: 'online' | 'offline' | 'error'
if not Path(volume.mount_path).exists():
    volume.status = 'offline'
```

Operations gracefully fail when volumes are unavailable.

---

## Performance Benchmarks

### Before Optimization (v0.3.0)
| Operation | Speed | Time for 34K models |
|-----------|-------|---------------------|
| Thumbnails | 0.23/sec | **41+ hours** |
| Partial hash | ~100/sec | ~6 minutes |

### After Optimization (v0.3.1)
| Operation | Speed | Time for 34K models |
|-----------|-------|---------------------|
| Thumbnails (fast) | ~45/sec | **~8 minutes** |
| Thumbnails (slow) | ~1/min | **~2-3 hours** |
| Partial hash | ~100/sec | ~6 minutes |
| Full hash | ~10/sec | ~30 sec (collisions only) |

**Total indexing time**: ~3 hours (was 41+ hours)

---

## CLI Reference

### Indexing Commands

```bash
# Index 3D models from a directory
python -m dam.cli index-models /path/to/models

# Index PDFs
python -m dam.cli index-pdfs /path/to/pdfs

# Compute hashes (auto-runs dedup when done)
python -m dam.cli compute-hashes --type models

# Manual deduplication
python -m dam.cli detect-duplicates --type models

# Show statistics
python -m dam.cli stats
```

### Daemon Management

```bash
# Start thumbnail daemon (tiered processing)
cd /Users/claw/projects/dam
source .venv/bin/activate
nohup python scripts/thumbnail_daemon.py &

# Check daemon status
ps aux | grep thumbnail_daemon

# View logs
tail -f logs/thumbnail_daemon.log

# Stop daemon
pkill -f thumbnail_daemon.py
```

---

## Configuration

### Environment Variables

```bash
# .env.local
DAM_DATABASE_PATH=/path/to/dam.db
DAM_THUMBNAIL_DIR=/path/to/thumbnails
DAM_LOG_LEVEL=INFO
```

### Tuning for Your Hardware

| Setting | Low-end | Mid-range | High-end |
|---------|---------|-----------|----------|
| FAST_WORKERS | 8 | 16 | 28 |
| SLOW_WORKERS | 2 | 4 | 8 |
| SIZE_THRESHOLD_MB | 20 | 30 | 50 |

Reduce workers if SMB connection becomes unstable.

---

## Troubleshooting

### Thumbnails Not Appearing
1. Check daemon is running: `ps aux | grep thumbnail_daemon`
2. Check logs: `tail logs/thumbnail_daemon.log`
3. Verify database updates: `SELECT COUNT(*) FROM models WHERE has_thumbnail = 1`

### Slow Indexing
1. Check network: `ping <smb-server>`
2. Reduce workers (SMB congestion)
3. Consider local rsync first for bulk imports

### Deduplication Not Running
1. Check partial hash progress: `SELECT COUNT(*) FROM models WHERE partial_hash IS NULL`
2. Run manually: `python -m dam.cli detect-duplicates`

### High Memory Usage
1. Reduce batch sizes in daemon config
2. Reduce worker counts
3. Check for memory leaks in logs

---

## Related Documentation

- `docs/BACKUPS.md` — Backup and recovery system
- `docs/DEDUPLICATION.md` — Deduplication details
- `docs/THUMBNAIL_PERFORMANCE_FIX.md` — Performance analysis

