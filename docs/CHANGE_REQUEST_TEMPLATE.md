# FantasyFolio Change Request Template

Use this template when requesting code changes, features, or fixes. Copy and fill out relevant sections.

---

## 📋 CHANGE REQUEST

### Request ID
`CR-YYYY-MM-DD-###` (e.g., CR-2026-02-20-001)

### Request Type
- [ ] New Feature
- [ ] Bug Fix
- [ ] Schema Change
- [ ] UI Change
- [ ] API Change
- [ ] Configuration Change
- [ ] Documentation Only
- [ ] Container/Deployment

### Priority
- [ ] Critical (blocking, needs immediate fix)
- [ ] High (important, this sprint)
- [ ] Medium (should do soon)
- [ ] Low (nice to have)

---

## 📝 DESCRIPTION

### Summary
_One-line description of the change_

### Detailed Description
_Full explanation of what needs to be done_

### Acceptance Criteria
_How do we know it's complete? Be specific._
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Related Issues/Context
_Links to GitHub issues, previous discussions, related CRs_

---

## 🗃️ DATABASE CHANGES

### Schema Changes Required?
- [ ] Yes
- [ ] No

### If Yes:

#### New Tables
```sql
-- Paste CREATE TABLE statements
```

#### Altered Tables
```sql
-- Paste ALTER TABLE statements
```

#### New Indexes
```sql
-- Paste CREATE INDEX statements
```

#### Migration Required for Existing Data?
- [ ] Yes - describe migration steps
- [ ] No - new tables only

#### Files to Update
- [ ] `data/schema.sql` (always for new installs)
- [ ] `fantasyfolio/migrations/XXX_description.py` (for existing DBs)
- [ ] `fantasyfolio/core/database.py` (if helper functions change)

### Migration Instructions for Existing Deployments
```
1. Step one
2. Step two
```

---

## 🔌 API CHANGES

### New Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/example | Description |
| POST | /api/example | Description |

### Modified Endpoints
| Endpoint | Change Description |
|----------|-------------------|
| /api/example | Added field X to response |

### Removed Endpoints
| Endpoint | Replacement |
|----------|-------------|
| /api/old | Use /api/new instead |

### Request/Response Examples
```json
// Request
{
  "field": "value"
}

// Response
{
  "result": "value"
}
```

---

## 🎨 UI CHANGES

### Affected Pages/Components
- [ ] Dashboard
- [ ] Settings
- [ ] Asset Browser (3D)
- [ ] Asset Browser (PDF)
- [ ] Collection View
- [ ] Navigation
- [ ] Other: _________

### UI Mockup/Screenshot
_Attach image or ASCII mockup_

### New UI Elements
_Describe new buttons, forms, dialogs, etc._

---

## 📁 FILES TO MODIFY

### Backend (Python)
- [ ] `fantasyfolio/api/_________.py`
- [ ] `fantasyfolio/services/_________.py`
- [ ] `fantasyfolio/core/_________.py`
- [ ] `fantasyfolio/indexer/_________.py`
- [ ] Other: _________

### Frontend (Templates/JS)
- [ ] `templates/index.html`
- [ ] `templates/_________.html`
- [ ] `static/js/_________.js`
- [ ] `static/css/_________.css`

### Configuration
- [ ] `docker/supervisord.conf`
- [ ] `docker/entrypoint.sh`
- [ ] `Dockerfile`
- [ ] `requirements.txt`
- [ ] `.env.example`

### Documentation
- [ ] `README.md`
- [ ] `docs/_________.md`
- [ ] `CHANGELOG.md`

---

## ✅ PRE-IMPLEMENTATION CHECKLIST

Before coding begins, confirm:

- [ ] Requirements are clear and complete
- [ ] Database schema changes documented
- [ ] API contracts defined
- [ ] No conflicting work in progress
- [ ] Test data/environment available

---

## 🧪 TESTING REQUIREMENTS

### Test Environment
- [ ] Mac local (specify port: _____)
- [ ] Docker on Mac (specify port: _____)
- [ ] Docker on Windows (specify port: _____)

### Test Data Needed
_Describe any specific test files, volumes, or data required_

### Test Cases
| # | Test Case | Expected Result | Pass/Fail |
|---|-----------|-----------------|-----------|
| 1 | Description | Expected outcome | |
| 2 | Description | Expected outcome | |
| 3 | Description | Expected outcome | |

### Regression Tests
_What existing functionality should be verified still works?_
- [ ] Existing test 1
- [ ] Existing test 2

---

## 🚀 DEPLOYMENT CHECKLIST

### Version Bump
- [ ] Update `fantasyfolio/__init__.py` version to: `_._._`

### Git Operations
- [ ] All changes committed with descriptive messages
- [ ] Pushed to `master` branch
- [ ] Tag created (if release): `v_._._`

### Container Build
- [ ] Build command: `docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X .`
- [ ] Push to registry: `docker push ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X`
- [ ] Update `latest` tag: `docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest`

### Deployment Commands (Windows)
```powershell
# Stop existing container
docker rm -f fantasyfolio

# Remove old image
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:OLD_VERSION

# Pull new image
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:NEW_VERSION

# Start container (update volumes as needed)
docker run -d --name fantasyfolio -p 8888:8888 -v C:\fantasyfolio\data:/app/data [VOLUME_MOUNTS] ghcr.io/diminox-kullwinder/fantasyfolio:NEW_VERSION

# Verify startup
docker logs fantasyfolio
```

### Database Migration (if needed)
```powershell
# Run migration command
docker exec fantasyfolio python -m fantasyfolio.migrations.XXX_description
```

---

## 🔍 POST-DEPLOYMENT VERIFICATION

### Smoke Tests
- [ ] Container starts without errors
- [ ] All 3 services running (fantasyfolio, sshd, thumbnail-daemon)
- [ ] Web UI accessible at http://localhost:8888
- [ ] Can add asset location
- [ ] Can trigger index
- [ ] Thumbnails render

### Feature-Specific Tests
- [ ] Test case 1 from Testing Requirements
- [ ] Test case 2 from Testing Requirements
- [ ] Test case 3 from Testing Requirements

### Performance Check
- [ ] Page load time acceptable
- [ ] Index operation completes
- [ ] No memory leaks observed

---

## 📊 SIGN-OFF

### Development Complete
- [ ] Code complete
- [ ] Self-tested by Hal
- Date: ___________

### Ready for User Testing
- [ ] All checklist items above complete
- [ ] Deployment instructions provided
- Date: ___________

### User Acceptance
- [ ] Matthew has tested and approved
- [ ] Issues found: ___________
- Date: ___________

### Production Release
- [ ] Final version deployed
- [ ] CHANGELOG updated
- [ ] MEMORY.md updated
- Date: ___________

---

## 📎 ATTACHMENTS

_Add any relevant files, screenshots, logs, etc._

---

## 💬 NOTES / DISCUSSION

_Running notes during implementation_

---

# Quick Reference: Common Gotchas

## Schema Changes
1. **ALWAYS update `data/schema.sql`** - this is used for fresh installs
2. **Create migration script** for existing databases
3. **Test both paths**: fresh install AND migration from previous version

## Container Builds
1. Version bump BEFORE building
2. Test the built image locally before pushing
3. Always push both versioned tag AND `latest`

## API Changes
1. Use `request.get_json(silent=True)` for optional JSON bodies
2. Return proper HTTP status codes
3. Update any API documentation

## Testing
1. Test on FRESH database (delete data, pull image, start)
2. Test on EXISTING database (migration path)
3. Test on Windows if any path handling involved

## Common Windows Commands
```powershell
# Check container logs
docker logs fantasyfolio --tail 50

# Execute command in container
docker exec fantasyfolio [command]

# Check database
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db "SELECT..."

# Restart container
docker restart fantasyfolio
```

---

# 🏁 QUICK RELEASE CHECKLIST

**Use this after testing is complete and you're ready to publish a release.**

Copy and paste this section when wrapping up:

```
## Release: v_._._

### Pre-Release
- [ ] All bugs fixed and verified
- [ ] Version bumped in `fantasyfolio/__init__.py`
- [ ] CHANGELOG.md updated
- [ ] All code committed and pushed to master

### Schema Check
- [ ] `data/schema.sql` matches current code expectations
- [ ] Migration script created (if needed for existing DBs)

### Build & Push
- [ ] Container built: `docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X -t ghcr.io/diminox-kullwinder/fantasyfolio:latest .`
- [ ] Pushed version tag: `docker push ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X`
- [ ] Pushed latest tag: `docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest`

### Fresh Pull Test (Mac)
- [ ] Removed local images: `docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X`
- [ ] Pulled fresh: `docker pull ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X`
- [ ] Started with clean data directory
- [ ] Container starts, all 3 services running
- [ ] Basic smoke test passed (add location, index, view assets)

### Windows Deployment Commands Ready
```powershell
docker rm -f fantasyfolio
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:OLD
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X
docker run -d --name fantasyfolio -p 8888:8888 -v C:\fantasyfolio\data:/app/data [VOLUMES] ghcr.io/diminox-kullwinder/fantasyfolio:X.X.X
docker logs fantasyfolio
```

### Documentation
- [ ] Release notes written
- [ ] Any new features documented
- [ ] Memory files updated (MEMORY.md, memory/YYYY-MM-DD.md)

### Ready for Windows Test
- [ ] All above complete
- [ ] Matthew notified with version number and commands
```
