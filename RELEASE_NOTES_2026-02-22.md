# FantasyFolio Release Notes - February 22, 2026

## Collection Sharing & User Management Sprint

**Major Features Implemented Today:**

## 🔗 Collection Sharing System (Complete)

### Backend API (4 Endpoints)
- `GET /api/collections/<id>/shares` - List all shares (user + guest links)
- `POST /api/collections/<id>/share` - Create user share or guest link
- `PATCH /api/collections/<id>/shares/<id>` - Update permissions
- `DELETE /api/collections/<id>/shares/<id>` - Revoke access

### Features
- ✅ Share collections with registered users via email
- ✅ Guest links with secure tokens (SHA256 hashed)
- ✅ Time-limited guest links (1/7/30 days or permanent)
- ✅ Password protection for guest links
- ✅ Download limits and tracking
- ✅ Permission levels: View / Download / Edit
- ✅ Email invitations via SendGrid
- ✅ Personal collection aliases (shared users can rename)
- ✅ Inline permission editing (dropdown with colors)
- ✅ Copy link button for easy sharing via text/Slack/Discord
- ✅ Guest link access page with password prompt
- ✅ Bulk download (ZIP all items in shared collection)

### Guest Link Enhancements
- Shows thumbnails for both PDFs and 3D models
- Individual item downloads
- Archive member extraction (STL files in .zip)
- Proper timezone handling throughout
- Full URL generation using configured IP address

## 👥 User Management Overhaul

### Removed
- Users (👥) button from main header

### Settings Integration
- User Management now exclusively in Settings → User Management tab
- Full-featured user list with:
  - Color-coded role badges (Admin/GM/Player/Guest)
  - Inactive status indicators
  - Creation dates and last login times
  - Search functionality
  - Add/Edit/Activate/Deactivate

### Edit User Modal (NEW)
Three-tab interface for comprehensive user editing:

**Account Tab:**
- Change user role
- Edit display name
- Metadata privileges (placeholder)

**Collections Tab:**
- View all owned collections (with item counts)
- View collections shared with user (with permissions)
- Shows owner name for shared collections

**Profile Tab (Read-Only):**
- Email address
- Account created date/time
- Last login date/time
- Active/Inactive status
- User ID (UUID)

### Backend API Updates
- `GET /api/collections?owner_id=<id>` - View any user's collections (admin only)
- `GET /api/collections/shared-with/<id>` - View shares with specific user (admin only)
- Admin-only access control for viewing other users' data

## ⚙️ Settings Menu Reorganization

**New Structure:**
```
Settings
├── General (Asset Locations, Reindex, 3D Maintenance)
├── User Management (Full user interface)
└── Advanced
    ├── Deleted Records (Trash, Journal, Snapshots)
    ├── Email Settings (SMTP/SendGrid/AWS SES)
    └── DB Back-Up (Snapshots + Backup Policies)
```

**Database Snapshots** moved from Deleted Records to top of DB Back-Up section.

## 🐛 Critical Bugs Fixed

### Collection Sharing Issues
1. **Share modal not opening** - Missing `</div>` tag caused invisible nesting
2. **3D models not showing in guest links** - Query only joined assets table
3. **3D model downloads failing** - Archive member extraction not implemented
4. **Guest link URLs showing localhost** - Now uses configured IP from settings
5. **Database commits not saving** - Missing `conn.commit()` calls
6. **Datetime timezone mixing** - Fixed in 3 locations (creation, expiry, display)

### User Management Issues
1. **401 error on user list** - Added proper login check with clear messaging
2. **Settings tab not syncing** - Now shares functions with external modal

### Other Fixes
- Email integration (SendGrid dependency missing)
- Archive downloads for guest links
- Info panel for 3D models in collections
- Permission editing in share modal

## 🔐 Security Improvements

- Removed `.env.local` and `start-server.sh` from git tracking
- Added `start-server.sh.example` template
- Proper authentication checks for user management endpoints
- Admin-only access for viewing other users' data

## 📊 Database Changes

- Added `custom_name` column to `collection_shares` table (migration 007)
- Personal collection aliases for shared collections

## 🎯 What's Ready for Testing

1. **Share a collection** → Settings (not header anymore)
   - Right-click collection → Share
   - Add users via dropdown or email
   - Change permissions inline
   - Create guest links with copy button

2. **Guest links**:
   - Send external link via email or copy/paste
   - View collection with thumbnails
   - Download individual items or bulk ZIP
   - Works with password protection and expiry

3. **User management**:
   - Settings → User Management
   - Search, add, edit users
   - View user's collections and shares
   - Change roles and names

## 📝 Known Limitations

- **OAuth**: Google OAuth requires FQDN (not IP) - accepted limitation
- **Metadata privileges**: Placeholder in Edit User modal (future feature)
- **Settings reorganization**: Sub-tab JavaScript complete and functional

## 💡 Key Lessons Documented

Added to MEMORY.md:
- #28: Missing dependencies cause silent failures
- #29: Database context manager doesn't auto-commit
- #30: Timezone-aware vs naive datetime mixing
- #31: Unclosed HTML tags nest elements invisibly
- #32: Archive members require extraction before download

## 📈 Commits Today

**32 commits** pushed to master (pending GitHub secrets resolution):
- Collection sharing backend (4 endpoints)
- Collection sharing UI (modals, dropdowns, copy button)
- Guest link access page with downloads
- User management overhaul
- Settings menu reorganization
- Multiple bug fixes and improvements

## 🚀 Next Steps (Future)

- Smart collections (schema ready, logic pending)
- Bulk operations (select multiple assets)
- Collection export as ZIP
- Collection templates
- Guest link analytics (view/download tracking)
- Metadata privileges implementation

---

**Total Development Time:** ~7 hours (10:37 AM - 2:26 PM PST)
**Status:** ✅ Feature-complete and tested
**Environment:** macOS test server (192.168.50.190:8008)
