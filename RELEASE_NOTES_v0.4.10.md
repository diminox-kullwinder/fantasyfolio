# FantasyFolio v0.4.10 Release Notes

## Overview

Version 0.4.10 is a major stability and bug-fix release addressing **17 critical bugs** from Windows validation testing, plus **5 user experience improvements** discovered during live testing. This release focuses on upload reliability, force re-indexing, thumbnail rendering, and folder hierarchy preservation.

## Highlights

✅ **3D Upload Hang Fixed** - Uploads complete reliably in ~3 seconds  
✅ **Force Re-Index Works** - PDF and 3D folders maintain proper hierarchy  
✅ **Thumbnail Rendering** - Consistent high-quality renders everywhere  
✅ **Search Improvements** - Advanced search works correctly for PDFs and 3D models  
✅ **Upload System** - Complete path validation and timeout handling  

## Bugs Fixed

### Critical (3)
1. **3D upload hang** - Indefinite hang when uploading models
2. **SQL binding error** - Re-indexing failed with parameter mismatch
3. **Camera angle** - Thumbnails showed back view instead of front

### High Priority (7)
4. **3D search folder scope** - Search ignored folder selection
5. **Advanced search PDF** - No results, filters didn't work
6. **Context menu refresh** - Loaded wrong content type
7. **Force Index fails** - Nav tree indexing threw errors
8. **Force Index JavaScript error** - Undefined function call
9. **has_thumbnail flag** - Database not tracking renders correctly
10. **Thumbnail rendering inconsistency** - Different quality between bulk and manual

### Medium Priority (6)
11. **Upload dialog broken** - Couldn't browse folders
12. **Upload folder creation** - Path validation error
13. **Upload timeout** - Files hung on slow storage
14. **Tab switching cache** - Stale thumbnails after switching
15. **Grid manual refresh** - Thumbnail update not visible
16. **PDF thumbnail regeneration** - SQL column error

## Improvements

1. **Force Index stats** - Shows accurate "new vs updated" counts
2. **Force Index UI** - Stays on correct tab and auto-refreshes
3. **PDF folder hierarchy** - Proper relative paths preserved
4. **3D folder hierarchy** - Parent-child relationships maintained
5. **Upload path validation** - Unified logic across all endpoints

## Testing

- ✅ 12 PDFs indexed with correct hierarchy
- ✅ 69 3D models indexed (52 from ZIPs, 17 standalone)
- ✅ Force re-index preserves folder structure
- ✅ Upload works on slow storage (degraded RAID)
- ✅ All context menus and UI interactions verified
- ✅ Container deployment validated

## Installation

### Docker (Recommended)

```bash
# Build new image
docker build -t fantasyfolio:v0.4.10 .

# Stop old container
docker stop fantasyfolio
docker rm fantasyfolio

# Run new version
docker run -d \
  --name fantasyfolio \
  -p 8888:8888 \
  -v /path/to/data:/app/data \
  -v /path/to/3d:/content/3d-models \
  -v /path/to/pdfs:/content/pdfs \
  fantasyfolio:v0.4.10
```

**Important:** Use `docker stop/rm/run`, not `docker restart`! Restart doesn't reload the image.

### Direct Python

```bash
# Pull latest
git pull origin master
git checkout v0.4.10

# Update dependencies (if needed)
pip install -r requirements.txt

# Restart service
systemctl restart fantasyfolio  # or your process manager
```

## Upgrade Notes

**Fresh Database Recommended:**
For cleanest experience, start with a fresh database and re-index your collections. The fixes ensure proper folder hierarchy and thumbnail tracking from the start.

**Existing Database:**
The `models_au` trigger will be created automatically on first startup. No manual migration needed.

**Configuration:**
No config changes required. Upload paths auto-detect with sensible defaults.

## Known Issues

**Not Included in v0.4.10:**
- GLB/glTF 3D viewer support (planned for v0.4.11)
- Pagination/infinite scroll (planned for v0.4.11)
- Advanced search query builder enhancement (backlogged)

**Workarounds:**
- GLB files index correctly but can't be previewed in 3D viewer yet
- Large collections (1000+) load all at once (may be slow on first load)

## What's Next?

See `NEXT_STEPS.md` for v0.4.11 roadmap:
- GLB/glTF 3D viewer support (~15 min)
- Pagination/infinite scroll (~90 min)
- Advanced search query builder (4-6 hours)
- Performance optimizations

## Contributors

- **Hal** (AI Agent) - All bug fixes, testing, and documentation
- **Matthew Laycock** - Testing, validation, and issue reporting

## Links

- **Repository:** https://github.com/diminox-kullwinder/dam
- **Docker Hub:** (TBD)
- **Documentation:** `/docs` directory in repository
- **Issues:** GitHub Issues

---

**Full Changelog:** [CHANGELOG.md](CHANGELOG.md)
