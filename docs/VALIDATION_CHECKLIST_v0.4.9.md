# FantasyFolio v0.4.9 Validation Checklist

## Pre-requisites
- [ ] Docker Desktop running on Windows PC
- [ ] Network access to 3D model share
- [ ] Network access to PDF share

## Installation Steps

```powershell
# 1. Pull latest image
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:latest

# 2. Stop existing container (if running)
docker stop fantasyfolio
docker rm fantasyfolio

# 3. Start new container
docker run -d --name fantasyfolio \
  -p 8888:8888 \
  -v "D:\FantasyFolio\data:/app/data" \
  -v "\\NAS\3D-Models:/content/3d-models:ro" \
  -v "\\NAS\PDFs:/content/pdfs:ro" \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/diminox-kullwinder/fantasyfolio:latest

# 4. Check logs
docker logs fantasyfolio
```

---

## Validation Tests

### 1. Basic Startup
- [ ] Container starts without errors
- [ ] Web UI accessible at http://localhost:8888
- [ ] No console errors in browser dev tools

### 2. PDF Tab
- [ ] PDFs load in grid view
- [ ] PDFs load in list view
- [ ] **Sorting works**: Test "Size (Large first)" - largest PDFs should appear first
- [ ] **Sorting works**: Test "Name (A-Z)" - alphabetical order
- [ ] Folder navigation works
- [ ] PDF preview/viewer works
- [ ] Search works

### 3. 3D Models Tab
- [ ] Models load in grid view
- [ ] Models load in list view
- [ ] **Sorting works**: Test "Size (Large first)" - largest models first
- [ ] **Sorting works**: Test "Name (A-Z)" - alphabetical order
- [ ] Folder navigation works
- [ ] **Format filter**: Test filtering by STL only
- [ ] **Format filter**: Test filtering by GLB only (new!)
- [ ] Model detail view works
- [ ] 3D viewer loads model

### 4. Thumbnail Rendering (NEW FEATURES)
- [ ] **STL thumbnails**: Render correctly with front view
- [ ] **OBJ thumbnails**: Show model from front (not bottom of base)
- [ ] **3MF thumbnails**: Render correctly
- [ ] **GLB thumbnails**: Render correctly (NEW!)
- [ ] **glTF thumbnails**: Render correctly (NEW!)
- [ ] Thumbnails persist after container restart
- [ ] Right-click → "Regenerate Thumbnail" works

### 5. Indexing
- [ ] Settings → Add Location works
- [ ] Index 3D models triggers successfully
- [ ] Index PDFs triggers successfully
- [ ] GLB/glTF files are indexed (NEW!)
- [ ] Thumbnail stats show correct counts

### 6. Thumbnail Stats Panel
- [ ] Shows "X / Y cached (Z%)"
- [ ] "Render Missing" button works
- [ ] Progress updates during rendering

### 7. Persistence Test
```powershell
# Restart container
docker restart fantasyfolio

# After restart, verify:
```
- [ ] Database still has all indexed assets
- [ ] Thumbnails still display (not re-rendering)
- [ ] Settings preserved

---

## Known Limitations (Document, Don't Fix)

1. **OBJ with textures from ZIP**: Renders geometry only (textures not extracted)
2. **0-byte files**: Will render as blank thumbnails
3. **Sort options**: "Pages" sort has no effect on 3D models (falls back to filename)

---

## If Issues Found

1. Note the specific test that failed
2. Capture browser console errors (F12 → Console)
3. Capture container logs: `docker logs fantasyfolio`
4. Screenshot if visual issue

---

## Sign-off

- [ ] All critical tests pass
- [ ] Tested by: _______________
- [ ] Date: _______________
- [ ] Notes: 
