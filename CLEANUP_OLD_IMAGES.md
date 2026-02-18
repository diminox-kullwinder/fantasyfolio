# Cleanup Old FantasyFolio Images

**Purpose:** Remove old/outdated Docker images to save space and avoid confusion

---

## 🧹 Cleanup Commands

### Step 1: Remove Old Containers
```bash
# Stop any running containers
docker ps -a | grep fantasyfolio

# Remove stopped containers
docker rm fantasyfolio-test
```

### Step 2: Remove Old Images (Keep Latest 2 Versions)

**Safe to remove (old versions):**
```bash
# v0.4.10 and older
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:v0.4.10
docker rmi fantasyfolio:v0.4.10-test
docker rmi fantasyfolio:v0.4.10
docker rmi fantasyfolio:test
docker rmi fantasyfolio:0.4.5-test

# Very old versions
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.4
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.2
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.1
```

**Keep these (current versions):**
```bash
# Current release
ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13  # KEEP
ghcr.io/diminox-kullwinder/fantasyfolio:latest  # KEEP (same as 0.4.13)

# Previous release (for rollback if needed)
ghcr.io/diminox-kullwinder/fantasyfolio:0.4.12  # KEEP (optional)
```

### Step 3: One-Line Cleanup (Automated)
```bash
# Remove all old FantasyFolio images except latest 2 versions
docker images | grep fantasyfolio | grep -v "0.4.13\|0.4.12\|latest" | awk '{print $1":"$2}' | xargs -r docker rmi
```

---

## 📊 Before/After Disk Space

### Before Cleanup
```bash
docker images | grep fantasyfolio
# Shows ~12 images = ~33GB total
```

### After Cleanup
```bash
docker images | grep fantasyfolio
# Should show only 3 images = ~8GB total
# - 0.4.13 (2.74GB)
# - latest (same as 0.4.13, 0 bytes - just a tag)
# - 0.4.12 (2.74GB) - optional for rollback
```

**Space saved:** ~25GB

---

## 🔒 Safety Notes

**Before removing any images:**
1. Ensure no containers are using them: `docker ps -a`
2. Backup any important data (though images don't contain user data)
3. Keep at least 2 versions for rollback capability

**Images that are safe to remove:**
- Any version before v0.4.11 (breaking schema changes)
- Test/experimental builds
- Duplicate tags pointing to same image

**Images to keep:**
- `0.4.13` - Current production release
- `latest` - Auto-updates tag (points to 0.4.13)
- `0.4.12` - Optional previous version for emergency rollback

---

## 🗑️ Complete Cleanup Script

```bash
#!/bin/bash
# cleanup-fantasyfolio-images.sh

echo "🧹 Cleaning up old FantasyFolio Docker images..."
echo ""

# Stop and remove old containers
echo "Step 1: Removing old containers..."
docker rm -f fantasyfolio-test 2>/dev/null || true

# Remove old images (keep 0.4.13, 0.4.12, latest)
echo "Step 2: Removing old images..."
docker rmi fantasyfolio:v0.4.10-test 2>/dev/null || true
docker rmi fantasyfolio:v0.4.10 2>/dev/null || true
docker rmi fantasyfolio:test 2>/dev/null || true
docker rmi fantasyfolio:0.4.5-test 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:v0.4.10 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.11 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.4 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.2 2>/dev/null || true
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.1 2>/dev/null || true

# Remove dangling images
echo "Step 3: Removing dangling images..."
docker image prune -f

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Remaining images:"
docker images | grep fantasyfolio

echo ""
echo "Disk space reclaimed:"
docker system df
```

---

## 🚀 Quick Cleanup (Mac)

Run this now on your Mac:

```bash
cd /Users/claw/projects/dam

# Remove old container
docker rm fantasyfolio-test

# Remove old images (keep 0.4.13, 0.4.12, latest)
docker rmi fantasyfolio:v0.4.10-test
docker rmi fantasyfolio:v0.4.10
docker rmi fantasyfolio:test
docker rmi fantasyfolio:0.4.5-test
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:v0.4.10
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.11
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.4
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.2
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.1

# Remove any dangling images
docker image prune -f

# Check results
docker images | grep fantasyfolio
```

**Expected result:** Only 2-3 images remaining (0.4.13, 0.4.12, latest)

---

## 📝 Windows Cleanup

Same commands work on Windows PowerShell:

```powershell
# Remove old images
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:v0.4.10
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.11
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.4

# Clean up dangling images
docker image prune -f

# Verify
docker images | Select-String fantasyfolio
```

---

## ⚠️ Important Notes

### Don't Remove
- **0.4.13** - Current release with all features
- **latest** - Points to 0.4.13 (it's just a tag, not a separate image)
- **0.4.12** - Optional backup for rollback

### Safe to Remove
- **0.4.11 and older** - Schema breaking changes, can't use with 0.4.12+ databases
- **Test builds** - Development/testing versions
- **Untagged images** - Orphaned layers

### If You Accidentally Remove Everything
```bash
# Just pull again from GitHub
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:latest
```

Images are safely stored on GitHub Container Registry!

---

## 🔄 Regular Maintenance

**Recommended schedule:**
- After each major release: Remove versions older than N-2
- Monthly: Run `docker image prune -a` to clean up unused images
- Before major upgrades: Keep previous version for rollback

**Current policy (Feb 2026):**
- Keep: 0.4.13 (current), 0.4.12 (previous)
- Remove: 0.4.11 and older

---

**Space efficiency matters when you're building frequently!**
