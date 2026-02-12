# Next Steps - Post v0.4.10 Release

## Immediate Actions (v0.4.10 Release)

### 1. GitHub Release ✅ IN PROGRESS
- [x] Aggregate all fixes
- [x] Update CHANGELOG.md
- [x] Create RELEASE_NOTES_v0.4.10.md
- [ ] Push commits to GitHub
- [ ] Create GitHub release tag v0.4.10
- [ ] Attach release notes to GitHub release

### 2. Docker Image
- [ ] Build production image: `docker build -t fantasyfolio:v0.4.10 .`
- [ ] Tag as latest: `docker tag fantasyfolio:v0.4.10 fantasyfolio:latest`
- [ ] Push to registry (if applicable)
- [ ] Test pull and deploy on clean system

### 3. Windows PC Deployment
- [ ] Pull latest code on Windows PC
- [ ] Rebuild container with v0.4.10 tag
- [ ] Fresh database initialization
- [ ] Full production validation with real data
- [ ] Performance testing (1000+ assets)

### 4. Documentation
- [x] Update CHANGELOG.md
- [x] Create RELEASE_NOTES_v0.4.10.md
- [x] Create NEXT_STEPS.md (this file)
- [x] Update BACKLOG.md with deferred features
- [ ] Update README.md with v0.4.10 info
- [ ] Update deployment guides if needed

---

## v0.4.11 Planning

### High Priority Features

#### 1. GLB/glTF 3D Viewer Support
**Effort:** ~15 minutes  
**Priority:** High (user requested today)

**Current State:**
- GLB files index correctly (format=glb)
- Upload accepts .glb/.gltf files
- Format filter includes GLB/glTF options
- ❌ 3D viewer missing GLTFLoader

**Implementation:**
1. Load GLTFLoader from CDN in `open3dViewer()`
   ```javascript
   await loadScript('https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/js/loaders/GLTFLoader.js');
   ```

2. Add GLTFLoader case to `init3dViewer()`:
   ```javascript
   else if (format === 'glb' || format === 'gltf') {
     loader = new THREE.GLTFLoader();
     // GLTFLoader returns { scene, animations, cameras }
     // Extract scene and add to Three.js scene
   }
   ```

3. Test with AuroraGnome.glb (model #51)

#### 2. Pagination/Infinite Scroll
**Effort:** ~90 minutes  
**Priority:** Medium (performance improvement)

**Problem:**
- Currently loads all assets at once
- Large collections (1000+ models) slow initial page load
- No way to navigate large result sets

**Solution Options:**

**Option A: Simple Pagination**
- Add page controls: Previous/Next + page numbers
- Load 100 assets per page
- Backend: Add `LIMIT` and `OFFSET` to queries
- Frontend: Track current page, show controls
- Pros: Simple, predictable
- Cons: Can't quickly jump to end

**Option B: Infinite Scroll**
- Load initial 100 assets
- Monitor scroll position
- Load next batch when scrolling near bottom
- Backend: Same LIMIT/OFFSET approach
- Pros: Smooth UX, feels native
- Cons: Can't quickly jump to specific item

**Option C: Virtual Scrolling**
- Render only visible items
- Recycle DOM elements as user scrolls
- Works with thousands of items
- Pros: Best performance
- Cons: More complex implementation

**Recommendation:** Start with Option A (pagination) for simplicity. Can upgrade to infinite scroll in v0.4.12 if needed.

**Implementation:**
1. Backend: Add pagination to `/api/models` and `/api/assets`
2. Frontend: Add page state tracking
3. UI: Page controls in bottom toolbar
4. Preserve page when switching tabs/folders

#### 3. Test ZIP STL 3D Preview
**Effort:** ~5 minutes  
**Priority:** Medium (validation)

**Status:** Uncertain - needs testing

**Action:**
- Test 3D preview on model #4 (ToA_Dwarf_Druid_Supported.stl, 19.9MB from ZIP)
- Test 3D preview on model #6 (ToA_Fallen_Paladin_Weapon_Supported.stl, 3.9MB from ZIP)
- Verify backend extraction works in production
- Check browser console for errors
- Document results

### Medium Priority Features

#### 4. Advanced Search Query Builder
**Effort:** 4-6 hours  
**Priority:** Medium (nice-to-have)

See `docs/BACKLOG.md` for detailed specification.

**Summary:**
- Per-line field selection (Name, Format, Date, Size, etc.)
- Context-aware operators (is, contains, before, after, etc.)
- Boolean logic between lines (AND/OR)
- Save/load common queries
- Visual query preview

**Decision:** Backlog for v0.4.12+. Current advanced search works adequately.

#### 5. Two-Stage Upload for Slow Storage
**Effort:** 2-3 hours  
**Priority:** Low (workaround exists)

See `docs/SLOW_STORAGE.md` for architecture.

**Current State:**
- 5-minute timeout prevents indefinite hang
- Large files show warning if timeout occurs
- File may still complete in background

**Improvement:**
- Stage 1: Fast upload to staging directory
- Stage 2: Background copy to final location
- Return immediately after stage 1
- Show progress indicator for stage 2
- Update database when complete

**Decision:** Current timeout solution adequate. Defer to v0.4.12+ if users request.

---

## Long-Term Roadmap

### v0.4.12 (Future)
- Infinite scroll implementation
- Advanced search query builder
- Performance optimizations
- Thumbnail caching improvements

### v0.5.0 (Major)
- Multi-user support
- Authentication system
- User preferences
- Collection sharing

### v1.0.0 (Stable)
- Feature-complete
- Production-hardened
- Comprehensive testing
- Full documentation

---

## Deployment Checklist

**Before Each Release:**
1. [ ] All tests pass
2. [ ] No critical bugs
3. [ ] CHANGELOG updated
4. [ ] Release notes written
5. [ ] Documentation current
6. [ ] Docker image builds
7. [ ] Fresh database tested
8. [ ] Upgrade path verified
9. [ ] Backup instructions clear
10. [ ] Git tag created

**After Each Release:**
1. [ ] GitHub release published
2. [ ] Docker image pushed
3. [ ] Production deployment complete
4. [ ] Smoke tests pass
5. [ ] Monitor for issues
6. [ ] User communication sent
7. [ ] Update next steps document

---

## Questions to Resolve

1. **Docker Registry:** Push to Docker Hub? Private registry? Or just local builds?
2. **Versioning:** Continue 0.4.x or jump to 0.5.0 for next feature release?
3. **Testing Strategy:** Manual testing sufficient? Add automated tests?
4. **Release Cadence:** How often to release? Weekly? Monthly? As-needed?
5. **Communication:** How to notify users of updates? Email? In-app? README?

---

## Notes

**Lessons Learned from v0.4.10:**
- `docker restart` doesn't reload images - always use `stop/rm/run`
- Test with fresh database catches schema issues early
- Force re-index critical for folder hierarchy - must preserve relative paths
- Slow storage requires special handling (timeouts, skip hash, warnings)
- Container deployments need schema.sql in multiple locations

**Best Practices Going Forward:**
- Test container deployment before declaring "done"
- Verify database schema changes in both new and existing databases
- Test with realistic data volumes (1000+ items)
- Document known limitations in release notes
- Keep BACKLOG.md updated with deferred features

---

**Last Updated:** 2026-02-12 15:30 PST  
**Status:** v0.4.10 release in progress  
**Next Milestone:** v0.4.11 with GLB viewer support
