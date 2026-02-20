# FantasyFolio v0.4.15 - Bug Report

**Date:** 2026-02-19  
**Reported by:** Matthew (Windows deployment testing)  
**Analyzed:** Code extracted from SHA c308893afabd

---

## 🐛 Bug #1: Infinite Scroll Repeating Same Items

**Symptom:**
- Scrolling down loads more items, but shows the same models repeatedly
- Example: "Meshy AI Fathom" and "PRJ Tower1" appear multiple times in sequence
- Never reaches end of list

**Code Analysis:**

Frontend (`index.html` lines 4336-4351):
```javascript
mainScroll.addEventListener('scroll', () => {
  if (contentType !== '3d') return;
  
  if (scrollHeight - scrollTop - clientHeight < 300) {
    if (modelsHasMore && !modelsLoading) {
      console.log('Loading more models...', {offset: modelsOffset, hasMore: modelsHasMore});
      load3dModels(true); // append=true ✅ CORRECT
    }
  }
});
```

Load function (lines 4549-4605):
```javascript
async function load3dModels(append = false) {
  if (!append) {
    modelsOffset = 0;  // Reset only when NOT appending ✅
    modelsHasMore = true;
    allLoadedModels = [];
  }
  
  let url = `/api/models?limit=${modelsLimit}&offset=${modelsOffset}&sort=${currentSort}&order=${currentOrder}`;
  
  const res = await fetch(url);
  const models = await res.json();
  
  if (models.length < modelsLimit) {
    modelsHasMore = false;  // ✅ CORRECT
  }
  
  modelsOffset += models.length;  // ✅ CORRECT - should increment
  
  if (append) {
    allLoadedModels = allLoadedModels.concat(models);
  } else {
    allLoadedModels = models;
  }
  
  render3dModels(allLoadedModels, append);
}
```

Backend API (`api/models.py` lines 66-69):
```python
query += f" ORDER BY {sort} {order} LIMIT ? OFFSET ?"
params.extend([limit, offset])
rows = conn.execute(query, params).fetchall()
```
✅ Backend pagination looks correct too.

**Root Cause Analysis:**

The code logic appears CORRECT on both frontend and backend. Possible causes:

1. **Browser caching** - API responses being cached, returning same data
2. **Race condition** - Multiple scroll events firing before `modelsLoading` flag is set
3. **render3dModels() bug** - Rendering function might be duplicating items
4. **State not persisting** - `modelsOffset` getting reset somewhere else

**Recommended Fix:**

Add debugging to Windows instance:
```javascript
// Add before fetch
console.log('API call:', url, 'offset=', modelsOffset, 'allLoaded=', allLoadedModels.length);

// Add after fetch
console.log('Received:', models.length, 'new offset=', modelsOffset);
```

Check browser Network tab for actual API calls - verify offset is incrementing.

---

## 🐛 Bug #2: Navigation Tree Not Populating

**Symptom:**
- Folder tree sidebar remains empty
- Cannot browse by folder hierarchy

**Code Analysis:**

Tree load function (lines 4435-4448):
```javascript
async function load3dFolders() {
  const res = await fetch('/api/models/folder-tree');
  const data = await res.json();
  const flat = data.flat || [];
  
  modelFolderTreeData = flat.sort((a, b) => a.path.localeCompare(b.path));
  
  flat.forEach(item => {
    folderQueryInfo.set(item.path, {
      query_param: item.query_param || 'folder',
      query_value: item.query_value || item.folder_path || item.path
    });
  });
  
  render3dFolderTree();
}
```

Backend API (needs to find `/api/models/folder-tree` endpoint):
- Check `api/models.py` for this route
- Verify it's returning proper volume-based tree structure

**Recommended Fix:**

1. Check browser console for API errors
2. Verify `/api/models/folder-tree` returns data
3. Check if `render3dFolderTree()` has a rendering bug

---

## 🐛 Bug #3: Directory Picker "Up" Button Broken

**Symptom:**
- When adding new asset location via Settings
- Can navigate down into folders
- "Up" button doesn't work to go back up tree

**Location:**
- Settings UI file browser component
- Likely in `api/settings.py` or browse dialog in `index.html`

**Recommended Fix:**
- Find directory browser component
- Check "up" button click handler
- Verify path manipulation logic

---

## 🐛 Bug #4: PDF Indexing Incomplete

**Symptom:**
- Only 1 PDF indexed per volume initially
- "Scan Documents" adds more but still incomplete (6/12 files)
- Indexer stops early

**Expected:**
- All PDFs in directory should be indexed

**Code Analysis:**

Backend indexer location:
- `/app/fantasyfolio/indexer/` (need to check PDF scanner)
- Likely `indexer/pdfs.py` or similar

**Possible Causes:**
1. Shallow scan (only top-level files, not recursive)
2. Error during scan that's silently caught
3. Timeout during indexing
4. File permission issues

**Recommended Fix:**

Check PDF indexer logs:
```powershell
docker logs fantasyfolio 2>&1 | Select-String -Pattern "pdf|index|scan|error"
```

Check scan job status:
```powershell
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db "SELECT * FROM scan_jobs ORDER BY id DESC LIMIT 5;"
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db "SELECT * FROM job_errors ORDER BY id DESC LIMIT 10;"
```

---

## Testing Environment

**Windows Deployment:**
- Container: `c308893afabd` (v0.4.15)
- Database: 420 models, 2 asset locations
- Thumbnails: 415/420 rendered (98.8%)
- API accessible at http://localhost:8888

**Code Extracted:**
- Files at `/Users/claw/.openclaw/workspace/ff-debug-code/`
- Template at `/Users/claw/.openclaw/workspace/ff-debug-index.html`

---

## Next Steps

1. **Immediate:** Add console logging to Windows browser (F12)
2. **Check:** Browser Network tab for actual API calls/responses
3. **Debug:** Run queries on Windows DB to verify data integrity
4. **Fix:** Create patches for confirmed bugs
5. **Release:** v0.4.16 with fixes

---

## Notes

- Backend API pagination logic appears correct
- Frontend scroll/offset logic appears correct
- Bugs may be browser-side caching or race conditions
- Need Windows browser console output to confirm root cause
