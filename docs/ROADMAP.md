# FantasyFolio Roadmap

## Version Strategy

**Pre-v1.0:** Development phase - breaking changes allowed, focus on features and stability  
**v1.0:** Production-ready with migration system - no more "delete DB on upgrade"  
**Post-v1.0:** Semver versioning with backward compatibility

---

## Current Status (v0.4.11)

**✅ Complete:**
- Schema.sql with all required columns
- Automatic DB initialization on first run
- Batch render endpoint uses new thumbnail system
- Docker containerization with named volumes (DB fully containerized)
- Rebrand (DAM → FantasyFolio)

**❌ Incomplete:**
- GLB support in all code paths
- SVG support (blocker for NAS QA testing)
- Infinite scroll / pagination
- Deduplication integration into indexing
- On-demand preview DB column updates

---

## v0.4.12 - Critical Bugfixes + SVG Support
**Target:** 2026-02-24  
**Focus:** Fix rendering issues + enable NAS QA testing

### QA Blockers (Required for NAS Testing)
- [ ] **SVG support** - Add SVG thumbnail generation, format detection, and viewer
  - Rendering: Add SVG to thumbnail pipeline (ImageMagick/Inkscape)
  - Detection: Add `.svg` to supported formats list
  - Viewer: Display SVG in preview modal
  - **Why critical:** QA testers need to test with full asset libraries on NAS Docker deployments

### Critical Fixes (from v0.4.11 issues)
- [ ] **GLB support in all code paths** - Add GLB/GLTF to 3 missing locations (lines 225, 403, 491)
- [ ] **On-demand preview DB updates** - Update thumb_storage/thumb_path columns during browsing
- [ ] **Integrate deduplication** - Hook into indexing workflow (code exists, not integrated)
- [ ] **Unified rendering logic** - Consolidate 3 code paths into single function

### Planned Features (from original roadmap)
- [ ] **Infinite scroll** (90 min) - Load assets progressively, not all at once
  - Option A: Simple pagination (easier)
  - Option B: Infinite scroll (preferred)
  - Backend: Add LIMIT/OFFSET to queries
  - Frontend: Track scroll position, load next batch
- [ ] **GLB/GLTF 3D viewer** (15 min) - Load GLTFLoader in viewer

### Nice to Have
- [ ] Better error logging for failed renders
- [ ] Thumbnail generation progress indicator

**Estimated Effort:** 1-2 weeks

---

## v0.5.0 - SSO Authentication & Week 1 Foundation
**Target:** 2026-03-15  
**Focus:** Google/Apple login + core organization features

### SSO/OAuth Implementation (Plan Ready - See DAM_SSO_IMPLEMENTATION_PLAN.md)
**Effort:** 2-3 weeks  
**Status:** Complete implementation plan exists

- [ ] **Google OAuth login** - Sign in with Google
- [ ] **Apple OAuth login** - Sign in with Apple
- [ ] **User management** - User, Role, UserIdentity tables
- [ ] **Permission system** - Viewer, Editor, Admin roles
- [ ] **Protected endpoints** - @require_role decorators
- [ ] **Login UI** - Login page with OAuth buttons

**Tech Stack:**
- Flask + Authlib + Flask-Login
- SQLite with User/Role/Identity tables
- OAuth 2.0 via Authlib

**Prerequisites:**
- Google Cloud Console setup (OAuth client ID/secret)
- Apple Developer Account setup (Service ID, .p8 key)
- HTTPS (self-signed certs OK for dev)

### Week 1 Foundation Features (from Feature Priority Matrix - P0)
- [ ] **Bulk Tag Operations** (1 day) - Tag multiple models at once
- [ ] **Folder Hierarchy Sidebar** (2 days) - Tree navigation
- [ ] **Drag-n-Drop Upload** (2 days) - Upload via drag-drop
- [ ] **Inline Tag Editor** (1 day) - Edit tags without modal

**Result:** Users can organize and import models efficiently + secure multi-user access

**Estimated Effort:** 3-4 weeks total

---

## v0.6.0 - Week 2 Organization Features
**Target:** 2026-04-01  
**Focus:** Advanced organization and auto-organization

### Week 2 Features (from Feature Priority Matrix - P1)
- [ ] **Collection Nesting** (3 days) - Multi-level collections, parent/child relationships
- [ ] **Path Templating** (4 days) - Auto-organize by metadata pattern
  - Example: `{creator}/{collection}/{filename}`
  - Automatic folder structure based on rules
- [ ] **Bulk Move Operation** (1 day) - Move multiple models at once
- [ ] **Basic Version Tracking** (3 days) - Track model revisions

### Search & Discovery
- [ ] **Advanced query builder** (from BACKLOG.md)
  - Per-line field selection
  - Context-aware operators  
  - Dynamic AND/OR logic
  - Save/load queries

**Result:** Auto-organization based on metadata, multi-part collections

**Estimated Effort:** 2 weeks

---

## v0.7.0 - Performance & Scale (Week 3-4 Features)
**Target:** 2026-04-15  
**Focus:** Handle large collections efficiently

### Week 3-4 Features (from Feature Priority Matrix - P2)
- [ ] **Async Job Queue (Celery)** (2 weeks) - Background processing for:
  - Thumbnail generation
  - Large file uploads
  - Batch operations
  - Index operations
- [ ] **In-Browser Thumbnail Capture** (1 week) - Generate thumbnails client-side
- [ ] **Storage Abstraction (S3)** (1 week) - Support cloud storage backends
- [ ] **Virtual scrolling** - Render only visible items for 10K+ collections

### Performance
- [ ] **Database indexing** - Optimize slow queries
- [ ] **Thumbnail caching strategy** - Smart cache eviction
- [ ] **Background indexing queue** - Non-blocking, resumable

### Scale
- [ ] Handle 100K+ models
- [ ] Multi-volume support (NAS, cloud storage)
- [ ] Volume monitoring & auto-remount

**Result:** Can scale to 10K+ models, async processing, S3 support

**Estimated Effort:** 3 weeks

---

## v0.8.0 - Advanced Features (Week 5-6)
**Target:** 2026-05-01  
**Focus:** Power users and advanced organization

### Week 5-6 Features (from Feature Priority Matrix - P2/P3)
- [ ] **Advanced Search DSL** (2 weeks) - Complex queries with boolean logic
- [ ] **Full Version Control System** (3 weeks) - Track model changes over time
- [ ] **Smart Metadata Extraction** (2-3 weeks) - ML-based auto-tagging

### Collaboration
- [ ] **Public share links** - Share individual models/collections
- [ ] **Temporary access tokens** - Expiring links
- [ ] **Download tracking** - Who downloaded what
- [ ] User-specific collections
- [ ] Shared collections with permissions

**Result:** Teams can collaborate with permissions, advanced search

**Estimated Effort:** 4-5 weeks

---

## v0.9.0 - Workflow & Integration
**Target:** 2026-05-15  
**Focus:** Print workflow and external integrations

### Print Workflow
- [ ] **Print queue** - Track what needs printing
- [ ] **Print history** - Success/failures, settings used
- [ ] **Material tracking** - Filament/resin inventory
- [ ] **Slicing integration** - Auto-slice with presets

### Integrations
- [ ] **Cloud sync** - Google Drive, Dropbox, OneDrive
- [ ] **Slicer plugins** - PrusaSlicer, Cura, Bambu Studio
- [ ] **API for external tools** - REST API documentation
- [ ] **Webhook notifications** - Index complete, new uploads

**Estimated Effort:** 3-4 weeks

---

## v0.10.0 - Polish & Documentation
**Target:** 2026-06-01  
**Focus:** Production readiness prep

### Quality
- [ ] **Comprehensive testing** - Unit + integration tests (>90% coverage)
- [ ] **Error recovery** - Graceful degradation, retry logic
- [ ] **Backup/restore** - One-click backup, disaster recovery
- [ ] **Health monitoring** - Disk space, indexing status, errors

### Documentation
- [ ] **User guide** - Getting started, features, FAQ
- [ ] **Admin guide** - Installation, configuration, troubleshooting
- [ ] **API documentation** - REST endpoints, webhooks
- [ ] **Video tutorials** - Setup, common workflows

**Estimated Effort:** 2 weeks

---

## v1.0 - Production Release
**Target:** 2026-06-15  
**Focus:** Production-ready with migration system

### Critical v1.0 Requirements
- [ ] **Schema versioning** → **MUST HAVE**
- [ ] **Automatic migrations** → **MUST HAVE**
- [ ] **No breaking changes without migration path** → **MUST HAVE**
- [ ] Security audit (SSO implemented in v0.5.0)
- [ ] Performance testing (100K+ models)
- [ ] Backup/restore validation
- [ ] Full documentation

### Migration System Design
```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

Entrypoint checks version and runs pending migrations:
```bash
if [ current_version < target_version ]; then
    run migrations/001_add_columns.sql
    run migrations/002_add_tables.sql
    update schema_version
fi
```

### What v1.0 Means
- ✅ SSO/OAuth authentication (done in v0.5.0)
- ✅ Role-based permissions (done in v0.5.0)
- ✅ All Week 1-6 features complete
- ✅ Migration system prevents data loss
- ✅ Production-tested at scale
- ✅ Comprehensive documentation
- ✅ No more "delete DB on upgrade"

**After v1.0: Semantic versioning, backward compatibility guaranteed**

---

## v1.1+ - Advanced Security & Compliance
**Target:** TBD (Post-v1.0)  
**Focus:** Enterprise security and compliance

### Security Hardening
- [ ] **HTTPS enforcement** - No plaintext
- [ ] **CSRF protection** - Token-based (if not already done)
- [ ] **XSS prevention** - Content sanitization
- [ ] **Rate limiting** - Prevent abuse/DDoS
- [ ] **Security headers** - CSP, HSTS, X-Frame-Options
- [ ] **Audit logging** - Who did what when
- [ ] **2FA/MFA** - Two-factor authentication

### External Auth Providers
- [ ] **LDAP / Active Directory** integration
- [ ] **SAML 2.0** - Enterprise SSO
- [ ] **Additional OAuth providers** - GitHub, Microsoft, etc.

### Compliance
- [ ] **GDPR tools** - Data export, right to deletion
- [ ] **Audit trails** - Immutable logs
- [ ] **Data retention policies** - Auto-cleanup rules

---

## v2.0+ - Enterprise & Federation
**Target:** TBD  
**Focus:** Team collaboration, enterprise features

### Multi-User Enhancements
- [ ] **User profiles** - Avatar, preferences, settings
- [ ] **Teams/Groups** - Organizational structure
- [ ] **Workspace isolation** - Separate libraries per team
- [ ] **Activity feeds** - What's new, recent changes

### Enterprise Features
- [ ] **Advanced permissions** - Fine-grained ACLs
- [ ] **High availability** - Load balancing, failover
- [ ] **Centralized admin** - Multi-instance management
- [ ] **Usage analytics** - User activity, popular models

### Collaboration
- [ ] **Comments & annotations** - On models/collections
- [ ] **Approval workflows** - Review before publish
- [ ] **Real-time updates** - WebSocket notifications
- [ ] **ActivityPub Federation** (4 weeks) - Share across instances (low priority)

---

## Feature Priorities

### Must Have (Pre-v1.0)
**v0.4.12:**
1. Fix GLB rendering bugs
2. Infinite scroll
3. Integrate deduplication

**v0.5.0:**
1. Google/Apple SSO authentication
2. Role-based permissions (Viewer/Editor/Admin)
3. Week 1 foundation features (bulk ops, drag-drop, folder UI)

**v0.6.0:**
1. Collection nesting
2. Path templating (auto-organization)
3. Advanced search

**v1.0:**
1. Migration system (no more delete-DB-on-upgrade)
2. Schema versioning
3. Stable API
4. Full documentation

### Should Have (v1.x)
1. Additional auth providers (LDAP, SAML)
2. 2FA/MFA
3. Advanced security (rate limiting, audit logs)
4. Compliance tools (GDPR, data retention)

### Nice to Have (v2.0+)
1. Enterprise features (HA, multi-instance)
2. Advanced collaboration (comments, real-time)
3. Federation (ActivityPub)
4. Cloud deployment options

---

## Non-Goals

What FantasyFolio is **NOT**:
- Not a slicing tool (integrates with slicers)
- Not a CAD editor (views/organizes files)
- Not a cloud service (self-hosted)
- Not a marketplace (manages your library)

---

## Decision Log

### Why SQLite?
- Simple deployment (single file)
- Good enough for 100K+ models
- FTS5 for search
- Upgrade to PostgreSQL only if needed

### Why Flask?
- Simple, mature, well-documented
- Easy to deploy
- Fast development
- Good enough for single-user/small teams

### Why SSO in v0.5.0 instead of later?
- **Plan ready:** Complete implementation plan exists (DAM_SSO_IMPLEMENTATION_PLAN.md)
- **User request:** Multi-user access is high priority
- **Foundation complete:** v0.4.11 has stable schema, entrypoint, deployment
- **Timing:** 2-3 weeks effort fits between UX features and scaling work
- **Risk:** Low - isolated feature, can be disabled if needed
- **Benefit:** Enables secure sharing, enables Week 2-6 collaboration features

### Why not later?
- Delaying to v1.1+ would block collaboration features (v0.6-v0.8)
- SSO is prerequisite for permissions, sharing, team features
- Better to build on secure foundation early than retrofit later

---

**Last Updated:** 2026-02-17  
**Maintained By:** Hal + Matthew
