# FantasyFolio Roadmap

## Version Strategy

**Pre-v1.0:** Development phase - breaking changes allowed, focus on features and stability  
**v1.0:** Production-ready with migration system - no more "delete DB on upgrade"  
**Post-v1.0:** Semver versioning with backward compatibility

---

## v0.4.12 - Critical Bugfixes
**Target:** 2026-02-20  
**Focus:** Fix rendering issues discovered in v0.4.11

### Critical Fixes
- [ ] **GLB support in all code paths** - Add GLB/GLTF to 3 missing locations (lines 225, 403, 491)
- [ ] **On-demand preview DB updates** - Update thumb_storage/thumb_path columns during browsing
- [ ] **Deduplication detection** - Fix hash-based duplicate detection not working

### Nice to Have
- [ ] Unified rendering logic - Consolidate 3 code paths into single function
- [ ] Better error logging for failed renders

---

## v0.5.0 - Format Support & UX
**Target:** 2026-03-01  
**Focus:** New formats, better search, improved UI

### New Formats
- [ ] **SVG support** - 2D vector graphics rendering and thumbnails
  - Renderer: ImageMagick or Inkscape
  - Thumbnail generation
  - Preview display
  - New format category or integrate with existing?

### Search & Discovery
- [ ] **Advanced query builder** (from BACKLOG.md)
  - Per-line field selection
  - Context-aware operators
  - Dynamic AND/OR logic
  - Save/load queries

### UX Improvements
- [ ] Drag-and-drop file uploads
- [ ] Bulk operations (tag, move, delete)
- [ ] Recently viewed/accessed

---

## v0.6.0 - Performance & Scale
**Target:** 2026-03-15  
**Focus:** Handle large collections efficiently

### Performance
- [ ] **Lazy loading** - Virtual scrolling for 10K+ items
- [ ] **Thumbnail caching strategy** - Smart cache eviction
- [ ] **Database indexing** - Optimize slow queries
- [ ] **Background indexing queue** - Non-blocking, resumable

### Scale
- [ ] Handle 100K+ models
- [ ] Multi-volume support (NAS, cloud storage)
- [ ] Volume monitoring & auto-remount

---

## v0.7.0 - Collaboration Features
**Target:** 2026-04-01  
**Focus:** Sharing and multi-user basics

### Sharing
- [ ] **Public share links** - Share individual models/collections
- [ ] **Temporary access tokens** - Expiring links
- [ ] **Download tracking** - Who downloaded what

### Collections
- [ ] User-specific collections
- [ ] Shared collections
- [ ] Collection permissions

---

## v0.8.0 - Workflow & Integration
**Target:** 2026-04-15  
**Focus:** Print workflow and external integrations

### Print Workflow
- [ ] **Print queue** - Track what needs printing
- [ ] **Print history** - Success/failures, settings used
- [ ] **Material tracking** - Filament/resin inventory
- [ ] **Slicing integration** - Auto-slice with presets

### Integrations
- [ ] **Cloud sync** - Google Drive, Dropbox, OneDrive
- [ ] **Slicer plugins** - PrusaSlicer, Cura
- [ ] **API for external tools** - REST API documentation
- [ ] **Webhook notifications** - Index complete, new uploads

---

## v0.9.0 - Polish & Documentation
**Target:** 2026-05-01  
**Focus:** Production readiness prep

### Quality
- [ ] **Comprehensive testing** - Unit + integration tests
- [ ] **Error recovery** - Graceful degradation, retry logic
- [ ] **Backup/restore** - One-click backup, disaster recovery
- [ ] **Health monitoring** - Disk space, indexing status, errors

### Documentation
- [ ] **User guide** - Getting started, features, FAQ
- [ ] **Admin guide** - Installation, configuration, troubleshooting
- [ ] **API documentation** - REST endpoints, webhooks
- [ ] **Video tutorials** - Setup, common workflows

---

## v1.0 - Production Release
**Target:** 2026-06-01  
**Focus:** Production-ready with migration system

### Critical v1.0 Requirements
- [x] ~~Schema versioning~~ → **MUST HAVE**
- [x] ~~Automatic migrations~~ → **MUST HAVE**
- [x] ~~No breaking changes without migration path~~ → **MUST HAVE**
- [ ] Security audit
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

---

## v1.1+ - Authentication & Security
**Target:** TBD (Post-v1.0)  
**Focus:** Multi-user, permissions, security

### Authentication Layer
- [ ] **User accounts** - Local authentication
- [ ] **Password security** - Hashing, salting, password reset
- [ ] **Session management** - Secure tokens, timeouts
- [ ] **Remember me** - Persistent sessions

### Authorization
- [ ] **Role-based access** - Admin, Editor, Viewer
- [ ] **Per-resource permissions** - Who can view/edit what
- [ ] **Audit logging** - Who did what when

### Security Hardening
- [ ] **HTTPS enforcement** - No plaintext
- [ ] **CSRF protection** - Token-based
- [ ] **XSS prevention** - Content sanitization
- [ ] **SQL injection prevention** - Parameterized queries (already done)
- [ ] **Rate limiting** - Prevent abuse
- [ ] **Security headers** - CSP, HSTS, etc.

### External Auth (Future)
- [ ] OAuth2 / OpenID Connect
- [ ] LDAP / Active Directory
- [ ] SSO integration

---

## v2.0+ - Multi-User & Enterprise
**Target:** TBD  
**Focus:** Team collaboration, enterprise features

### Multi-User
- [ ] **User profiles** - Avatar, preferences, settings
- [ ] **Teams/Groups** - Organizational structure
- [ ] **Workspace isolation** - Separate libraries per team
- [ ] **Activity feeds** - What's new, recent changes

### Enterprise Features
- [ ] **Advanced permissions** - Fine-grained ACLs
- [ ] **Compliance** - Audit trails, retention policies
- [ ] **High availability** - Load balancing, failover
- [ ] **Centralized admin** - Multi-instance management

### Collaboration
- [ ] **Comments & annotations** - On models/collections
- [ ] **Version control** - Track model revisions
- [ ] **Approval workflows** - Review before publish
- [ ] **Real-time updates** - WebSocket notifications

---

## Feature Priorities

### Must Have (v1.0)
1. Migration system
2. Schema versioning
3. Stable API
4. Full documentation

### Should Have (v1.x)
1. Authentication/Authorization
2. Multi-user basics
3. Security hardening
4. Performance at scale

### Nice to Have (v2.0+)
1. Enterprise features
2. Advanced collaboration
3. External integrations
4. Cloud deployment

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

### Why no auth until v1.1+?
- Self-hosted = trusted environment
- Focus on core features first
- Auth adds complexity (testing, maintenance)
- Can add later without breaking existing deployments

---

**Last Updated:** 2026-02-17  
**Maintained By:** Hal + Matthew
