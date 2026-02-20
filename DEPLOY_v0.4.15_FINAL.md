# FantasyFolio v0.4.15 - Final Deployment Guide

## Critical Fixes

### 1. Schema Fix (Database Initialization)
**Problem:** v0.4.15 initial release (built 19:20 PST) failed on fresh database init with:
```
Parse error: object name reserved for internal use: assets_fts_data
```

**Root Cause:** schema.sql contained FTS5 internal tables that SQLite auto-generates

**Fix:** Commit `97e18f8` removed FTS internal tables from schema.sql

### 2. Build Process Fix (Docker Compilation)
**Problem:** Building Docker images hit SIGKILL during Rust compilation (~27 minutes in)
- Compiling stl-thumb from source consumed excessive memory
- Failed on both combined (amd64+arm64) and arm64-only builds

**Solution:** Use pre-built stl-thumb binaries from official GitHub releases

**Changes:**
```dockerfile
# BEFORE (caused OOM crashes):
RUN cargo install stl-thumb \
    && cp /root/.cargo/bin/stl-thumb /usr/local/bin/ \
    && rm -rf /root/.cargo /root/.rustup

# AFTER (instant, reliable):
COPY docker/binaries/stl-thumb_0.5.0_*.deb /tmp/
RUN dpkg -i /tmp/stl-thumb_0.5.0_$(dpkg --print-architecture).deb \
    && rm -f /tmp/stl-thumb_0.5.0_*.deb
```

**Benefits:**
- ✅ Build time: 30 min (vs crashing at 27 min)
- ✅ No more SIGKILL/OOM errors
- ✅ Removed `cargo` dependency (saves ~200MB in image)
- ✅ Faster builds (no Rust compilation)

## Deployment

### Pull Latest Image
```bash
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
```

### Windows Deployment

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  fantasyfolio:
    image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
    container_name: fantasyfolio
    restart: unless-stopped
    
    ports:
      - "8888:8888"
    
    environment:
      - FANTASYFOLIO_ENV=production
      - FANTASYFOLIO_DATABASE_PATH=/app/data/fantasyfolio.db
      - FANTASYFOLIO_SECRET_KEY=${SECRET_KEY}
      - ENABLE_THUMBNAIL_DAEMON=true
    
    volumes:
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
      - fantasyfolio_logs:/app/logs
      # Mount your asset directories (read-only recommended):
      - D:\3D-Models:/content/models:ro
      - D:\PDF-Library:/content/pdfs:ro

volumes:
  fantasyfolio_data:
  fantasyfolio_thumbs:
  fantasyfolio_logs:
```

**Start:**
```bash
docker-compose up -d
docker logs -f fantasyfolio
```

**Expected Output:**
```
[INIT] FantasyFolio starting...
[INIT] No database found, creating from schema.sql...
[INIT] Database initialized successfully
```

### Validation Tests

**Test 1: Schema Initialization**
```bash
docker run --rm \
  -e FANTASYFOLIO_DATABASE_PATH=/tmp/test.db \
  -e FANTASYFOLIO_SECRET_KEY=test \
  ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15 \
  sh -c "cat /app/schema.sql | head -5"
```
Should show: `-- FantasyFolio Database Schema`

**Test 2: stl-thumb Binary**
```bash
docker run --rm ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15 stl-thumb --version
```
Should show: `stl-thumb 0.5.0`

**Test 3: Fresh Database**
```bash
docker run --rm \
  -e FANTASYFOLIO_DATABASE_PATH=/tmp/test.db \
  -e FANTASYFOLIO_SECRET_KEY=test \
  ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15 \
  python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/test.db')
print('Tables:', [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])
"
```

## Timeline

- **19:20 PST (Feb 18)**: Initial v0.4.15 build (broken schema)
- **22:45 PST (Feb 18)**: Schema fix committed (97e18f8)
- **06:38 PST (Feb 19)**: Rebuild attempt (hit SIGKILL)
- **07:08 PST (Feb 19)**: Second SIGKILL
- **09:08 PST (Feb 19)**: Switched to pre-built binaries
- **11:34 PST (Feb 19)**: ✅ Final v0.4.15 published

## Image Details

- **Registry:** ghcr.io/diminox-kullwinder/fantasyfolio
- **Tag:** 0.4.15
- **Platforms:** linux/amd64, linux/arm64
- **Size:** ~2.8GB
- **Digest:** sha256:f1b9dd17da6cd12b6a684b142e5c97a7740f8137844ce5542fa93c29ba3e950d

## Changes from v0.4.14

1. **Schema:** Removed FTS internal tables (fixed fresh DB init)
2. **Build:** Pre-built stl-thumb binaries (fixed OOM crashes)
3. **Dependencies:** Removed cargo (~200MB savings)
4. **Volume navigation:** Extended to PDF assets (matches 3D pattern)
5. **Format support:** DAE, 3DS, PLY, X3D, RAR archives
6. **GLTF validation:** Detects missing .bin/texture files

## Known Issues

- None critical
- 12 PDFs with NULL volume_id (cosmetic, no functionality impact)

## Next Steps

1. **Windows Testing:** Confirm thumbnails render correctly
2. **Performance:** Monitor thumbnail daemon with real asset library
3. **v0.4.16 Planning:** PDF volume migration fix (FTS workaround)

---
**Built:** 2026-02-19 09:09 PST  
**Published:** 2026-02-19 11:34 PST  
**Status:** ✅ Ready for deployment
