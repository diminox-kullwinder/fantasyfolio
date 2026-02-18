# MANDATORY Release Process

**CRITICAL:** This process MUST be followed for EVERY release to prevent schema drift, missing features, and broken deployments.

## Problem This Solves

**2026-02-18 Incident:**
- v0.4.11, v0.4.12, v0.4.13 code was committed
- schema.sql was NEVER updated (stayed at pre-v0.4.9)
- No git tags created
- Fresh deployments = ancient schema + modern code = BROKEN
- Missing: duplicate detection, volumes table, 15+ critical columns
- Result: Mac test failures, broken move operations, data loss risk

**Never Again.**

---

## Release Checklist (MANDATORY)

### 1. Schema Synchronization (CRITICAL)

**Before committing code changes:**

```bash
# Export current working schema from live/test database
sqlite3 /path/to/working.db ".schema --indent" | grep -v "sqlite_sequence\|sqlite_stat" > data/schema.sql

# Verify schema has new columns/tables
grep "new_column\|new_table" data/schema.sql

# Test fresh database creation
rm -f data/test_fresh.db
sqlite3 data/test_fresh.db < data/schema.sql

# Verify all tables created
sqlite3 data/test_fresh.db ".tables"
```

**Files to update:**
- ✅ `data/schema.sql` - Master schema (from live DB)
- ✅ `docker/init-db.sh` - Container initialization (if exists)
- ✅ Any migration scripts

### 2. Version Number Update (MANDATORY)

**Update version in ALL locations:**

```bash
# 1. fantasyfolio/config.py
APP_VERSION = "0.4.X"

# 2. docker-compose.yml (if using version tags)
image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.X

# 3. Dockerfile (if has version labels)
LABEL version="0.4.X"

# Verify version consistency
grep -r "0\.4\.[0-9]" fantasyfolio/config.py docker-compose.yml Dockerfile
```

### 3. Documentation Update (MANDATORY)

**Update these files:**

```bash
# 1. CHANGELOG.md - Add release notes AT TOP
## [0.4.X] - YYYY-MM-DD
### Added/Fixed/Changed
- Feature/fix description

# 2. README.md - Update version badges (if exists)

# 3. Docker deployment guide - Update pull commands
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.X
```

### 4. Clean Test Deployment (MANDATORY)

**Test fresh install BEFORE tagging:**

```bash
# Stop existing
docker-compose down -v  # -v removes volumes!

# Clean all data
rm -rf data/fantasyfolio.db data/thumbnails/*

# Fresh install from schema
sqlite3 data/fantasyfolio.db < data/schema.sql

# Verify schema
sqlite3 data/fantasyfolio.db ".schema models" | grep "partial_hash\|is_duplicate"

# Start fresh
docker-compose up -d

# Test critical features:
# - Index assets
# - Generate thumbnails
# - Search works
# - Move operation (if duplicate detection)
# - All API endpoints respond 200
```

### 5. Git Commit and Tag (MANDATORY)

```bash
# Stage all changes
git add -A

# Commit with comprehensive message
git commit -m "feat/fix(v0.4.X): Brief summary

Detailed changes:
- Feature 1
- Fix 2
- Update schema.sql with columns X, Y, Z
- Update version to 0.4.X

Breaking changes: (if any)
Migration notes: (if any)"

# Create annotated tag
git tag -a v0.4.X -m "v0.4.X: Brief summary"

# Push BOTH
git push origin master
git push origin --tags
```

### 6. Docker Image Build and Push (MANDATORY)

```bash
# Build with version tag
docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:0.4.X .
docker build -t ghcr.io/diminox-kullwinder/fantasyfolio:latest .

# Test image locally
docker run -p 8888:8888 ghcr.io/diminox-kullwinder/fantasyfolio:0.4.X

# Push to registry
docker push ghcr.io/diminox-kullwinder/fantasyfolio:0.4.X
docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

### 7. Purge Obsolete Artifacts (MANDATORY)

**Delete old files that no longer apply:**

```bash
# Old backup databases
rm -f data/*.backup_* data/*_old.db data/*.db.bak

# Old schema versions
rm -f data/schema.sql.old data/schema_v*.sql

# Obsolete code
rm -f path/to/deprecated_module.py

# Old documentation
rm -f docs/obsolete_guide.md

# Commit cleanup
git add -A
git commit -m "chore: Purge obsolete artifacts for v0.4.X"
git push origin master
```

---

## Pre-Release Verification Checklist

**Run through this BEFORE tagging:**

- [ ] Schema exported from working database (not hand-edited)
- [ ] schema.sql creates database successfully
- [ ] Fresh database has ALL new columns/tables
- [ ] Version number updated in config.py
- [ ] CHANGELOG.md updated with release notes
- [ ] Fresh deployment tested (clean DB + Docker)
- [ ] All critical features work on fresh install
- [ ] Git commit includes schema.sql changes
- [ ] Git tag created with descriptive message
- [ ] Code + tags pushed to GitHub
- [ ] Docker image built with version tag
- [ ] Docker image pushed to registry
- [ ] Old backup files deleted
- [ ] Obsolete code/docs removed

---

## What Gets Updated in EVERY Release

### Minimum Required Updates:
1. ✅ **data/schema.sql** - Always export from working DB
2. ✅ **fantasyfolio/config.py** - APP_VERSION
3. ✅ **CHANGELOG.md** - Add release notes
4. ✅ **Git tag** - Annotated tag with message
5. ✅ **Docker image** - Build + push with version tag

### Often Required Updates:
- Migration scripts (if schema changes)
- API documentation (if endpoints changed)
- Docker deployment guide (if setup changed)
- README.md (if major features added)

---

## Release Types

### Patch Release (0.4.X → 0.4.X+1)
**For:** Bug fixes, small improvements, no schema changes
**Must update:** Version, CHANGELOG, tag, Docker image
**Optional:** Schema (only if columns added/fixed)

### Minor Release (0.4.X → 0.5.0)
**For:** New features, schema changes, API additions
**Must update:** ALL items in checklist
**Required:** Migration guide, schema.sql, fresh deployment test

### Major Release (0.X → 1.0)
**For:** Breaking changes, major rewrites
**Must update:** ALL items + migration scripts
**Required:** Deprecation notices, upgrade guide, announcement

---

## Common Mistakes to Avoid

❌ **DO NOT:**
- Edit schema.sql by hand (always export from working DB)
- Commit code without updating schema.sql
- Create git tag before testing fresh deployment
- Push Docker image before verifying it works
- Leave old backup databases in repo
- Forget to update version number
- Skip CHANGELOG.md updates

✅ **DO:**
- Export schema from WORKING database
- Test fresh install before every release
- Create annotated git tags (not lightweight)
- Push code AND tags together
- Clean up obsolete files
- Update ALL version references
- Document breaking changes

---

## Emergency Schema Fix Procedure

**If schema.sql is out of date (like 2026-02-18 incident):**

```bash
# 1. Stop all services
docker-compose down

# 2. Export correct schema from working DB
sqlite3 /path/to/working.db ".schema --indent" | grep -v "sqlite_sequence" > data/schema.sql.new

# 3. Verify new schema
sqlite3 test.db < data/schema.sql.new
sqlite3 test.db ".tables"

# 4. Replace old schema
mv data/schema.sql data/schema.sql.BROKEN
mv data/schema.sql.new data/schema.sql

# 5. Commit emergency fix
git add data/schema.sql
git commit -m "fix: Emergency schema correction - restore missing columns"
git push origin master

# 6. Rebuild Docker image
docker build -t fantasyfolio:latest .
docker push ghcr.io/diminox-kullwinder/fantasyfolio:latest

# 7. Test fresh deployment
rm -rf data/fantasyfolio.db
sqlite3 data/fantasyfolio.db < data/schema.sql
# Verify all tables exist
```

---

## Automated Checks (Future TODO)

**Pre-commit hook ideas:**
- Verify schema.sql creates database successfully
- Check version consistency across files
- Ensure CHANGELOG.md updated
- Warn if schema.sql not modified but models.py is

**CI/CD pipeline ideas:**
- Fresh database creation test
- Schema column count verification
- API endpoint smoke tests
- Docker image build + test

---

## Questions Before Release

1. **Did I export schema.sql from a WORKING database?**
2. **Does a fresh database from schema.sql work?**
3. **Did I update the version number everywhere?**
4. **Did I test a clean deployment (empty DB)?**
5. **Did I create and push the git tag?**
6. **Did I build and push the Docker image?**
7. **Did I update CHANGELOG.md?**
8. **Did I delete old backup files?**

**If you answered NO to ANY question, DO NOT release yet.**

---

## Ownership

**Matthew (Human):**
- Final approval for releases
- Production deployment decision
- Breaking change authorization

**Hal (AI Agent):**
- Execute release checklist
- Export schema from working DB
- Update version numbers
- Create git tags
- Build Docker images
- Document changes

**Both Must Verify:**
- Fresh deployment works
- No schema drift
- All features functional
- Documentation accurate

---

**Last Updated:** 2026-02-18 (after schema crisis)  
**Next Review:** Before v0.5.0 release
