# Upload Staging Architecture

**Status:** Required for SSO/User Management Implementation  
**Priority:** Implement with v0.5.0+ SSO authentication  
**Decided:** 2026-02-18

## Problem

Current upload implementation writes directly to asset volumes:
- Requires `is_readonly=0` on main library
- Users can accidentally corrupt/overwrite library
- No admin oversight or approval workflow
- Breaks Docker read-only mount strategy (`:ro`)

## Solution: Separate Upload Volume

### Architecture

**Two Volume Types:**

1. **Library Volumes (Read-Only)**
   - Main asset collections
   - Mounted read-only (`:ro` in Docker)
   - `is_readonly=1` in database
   - Used for: browsing, viewing, downloading
   - Thumbnails go to central cache only

2. **Upload Volume (Read/Write)**
   - Dedicated staging area
   - Mounted read/write (`:rw` in Docker)
   - `is_readonly=0` in database
   - `volume_type='upload'` flag
   - Used for: user uploads, admin review

### Database Schema

Add to `volumes` table:
```sql
ALTER TABLE volumes ADD COLUMN volume_type TEXT DEFAULT 'library';
-- Possible values: 'library', 'upload', 'archive'

-- Or extend asset_locations
ALTER TABLE asset_locations ADD COLUMN allow_uploads INTEGER DEFAULT 0;
```

### Directory Structure

```
Docker Container:
  /content/models/        (ro) ← Main 3D library
  /content/pdfs/          (ro) ← Main PDF library
  /app/uploads/pending/   (rw) ← User uploads staging
  /app/uploads/approved/  (rw) ← Admin approved (awaiting index)
  /app/data/              (rw) ← Database, central thumbnail cache
```

### Upload Workflow (with SSO Auth)

**Phase 1: Upload (User)**
1. User selects files via web UI
2. Files upload to `/app/uploads/pending/{user_id}/{timestamp}/`
3. System extracts metadata (filename, size, format)
4. Status: `pending_approval`

**Phase 2: Review (Admin)**
5. Admin sees notification: "3 new uploads awaiting review"
6. Admin views uploads in UI (with preview/metadata)
7. Admin actions:
   - **Approve** → move to `/app/uploads/approved/` + queue indexing
   - **Reject** → delete from staging + notify user
   - **Edit** → rename/reorganize before approval

**Phase 3: Indexing (System)**
8. Approved files indexed into database
9. Thumbnails generated
10. Files remain in `/app/uploads/approved/` (becomes part of library)
11. OR: Move to main library if admin wants consolidation

### UI Changes Required

**Settings → Asset Locations:**
```
┌─ Add Asset Location ──────────────────────────┐
│ Name: [3D Models - Main Library           ]  │
│ Type: [Library (Read-Only) ▼]                │
│ Path: [/Volumes/NAS/3D-Models             ]  │
│                                               │
│ ☐ Allow uploads to this location             │
│   (requires write access)                     │
└───────────────────────────────────────────────┘

┌─ Add Asset Location ──────────────────────────┐
│ Name: [User Uploads - Staging            ]  │
│ Type: [Upload Staging ▼]                     │
│ Path: [/app/uploads                       ]  │
│                                               │
│ ✓ Allow uploads to this location             │
│   (admin approval required)                   │
└───────────────────────────────────────────────┘
```

**Upload Modal:**
```
┌─ Upload Assets ───────────────────────────────┐
│ Destination: [User Uploads - Staging ▼]      │
│              (awaiting admin approval)        │
│                                               │
│ [Choose Files] or drag & drop                 │
│                                               │
│ Status: 3 files uploaded, pending review      │
└───────────────────────────────────────────────┘
```

**Admin Panel (New):**
```
┌─ Pending Uploads (3) ─────────────────────────┐
│ User          | Files | Date       | Actions  │
│ john@org.com  | 5 PDF | 2026-02-18 | Review   │
│ jane@org.com  | 2 STL | 2026-02-17 | Review   │
│ bob@org.com   | 1 ZIP | 2026-02-16 | Review   │
└───────────────────────────────────────────────┘

┌─ Review Upload: john@org.com ─────────────────┐
│ File: adventure-module-5e.pdf                 │
│ Size: 45.2 MB                                 │
│ Type: PDF                                     │
│ Pages: 234                                    │
│                                               │
│ Preview: [thumbnail]                          │
│                                               │
│ Move to: [/content/pdfs/D&D/5e ▼]            │
│                                               │
│ [Approve & Index] [Reject] [Download]        │
└───────────────────────────────────────────────┘
```

### Notifications (SSO Integration)

**Admin Notification:**
- Email: "3 new uploads awaiting approval"
- In-app badge: "Pending Uploads (3)"
- Webhook/Discord: Optional integration

**User Notification:**
- On approval: "Your upload 'dragon-miniature.stl' has been approved"
- On rejection: "Your upload was rejected: reason"

### Permissions (SSO Roles)

```yaml
roles:
  viewer:
    - view library
    - download files
  
  uploader:
    - view library
    - download files
    - upload to staging
    - view own uploads
  
  curator:
    - all uploader permissions
    - approve/reject uploads
    - edit metadata
    - move files between locations
  
  admin:
    - all curator permissions
    - manage users
    - manage volumes
    - system settings
```

## Implementation Phases

### v0.4.14 (Current)
- ✅ Read-only volumes working
- ✅ Central thumbnail cache
- ✅ Upload disabled (or fails gracefully)

### v0.5.0 (Foundation)
- Add `volume_type` column
- Separate upload volume in Docker compose
- Upload writes to staging only
- Basic "pending uploads" list (no approval yet)

### v0.5.x (User Management)
- Google/Apple SSO authentication
- User roles (viewer/uploader/curator/admin)
- Admin approval UI
- Notifications (email/in-app)

### v0.6.0+ (Advanced)
- Bulk approval/rejection
- Metadata editing before approval
- Automatic categorization (AI-assisted)
- Duplicate detection before indexing

## Docker Compose Changes

```yaml
services:
  fantasyfolio:
    volumes:
      # Read-only library volumes
      - ${MODELS_PATH}:/content/models:ro
      - ${PDF_PATH}:/content/pdfs:ro
      
      # Read-write upload staging
      - fantasyfolio_uploads:/app/uploads
      
      # Persistent data
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails

volumes:
  fantasyfolio_uploads:
    driver: local
```

## Testing Checklist (v0.5.x)

- [ ] Upload to staging succeeds
- [ ] Upload to library volume fails gracefully
- [ ] Admin sees pending uploads
- [ ] Approve → file indexes successfully
- [ ] Reject → file deleted, user notified
- [ ] Permissions enforced (viewer can't upload)
- [ ] Duplicate detection works
- [ ] Thumbnails generate after approval
- [ ] Metadata extraction accurate

## Security Considerations

1. **File Type Validation**: Only allow PDF/STL/OBJ/ZIP/etc.
2. **Size Limits**: Prevent DoS via huge uploads
3. **Path Traversal**: Sanitize filenames (no `../` tricks)
4. **Malware Scanning**: Optional ClamAV integration
5. **Quota Management**: Per-user upload limits
6. **Audit Log**: Track who uploaded/approved/rejected what

## Migration Path

Existing deployments with direct upload:
1. Backup current upload configuration
2. Create new upload volume
3. Migrate pending uploads to staging
4. Update volume settings to read-only
5. Enable approval workflow

## Related Issues

- SSO Authentication (#TBD)
- Role-Based Access Control (#TBD)
- Admin Dashboard (#TBD)
- Notification System (#TBD)

---

**Decision Log:**
- 2026-02-18: Decided to separate library (ro) and upload (rw) volumes
- 2026-02-18: Defer admin approval to SSO implementation phase
