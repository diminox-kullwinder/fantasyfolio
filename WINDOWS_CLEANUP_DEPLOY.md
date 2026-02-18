# Windows Machine - Cleanup & Deploy v0.4.13

**Purpose:** Clean up old FantasyFolio deployment and install fresh v0.4.13

---

## 🧹 Step 1: Stop & Remove Old Containers

```powershell
# Stop running container
docker-compose down

# Or if not using docker-compose:
docker stop fantasyfolio
docker rm fantasyfolio

# List all FantasyFolio containers (should be empty after this)
docker ps -a | Select-String fantasyfolio
```

---

## 🗑️ Step 2: Remove Old Images

```powershell
# Remove old FantasyFolio images
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.11
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.10
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:latest

# Or force remove all FantasyFolio images
docker images | Select-String fantasyfolio | ForEach-Object { 
    $parts = $_ -split '\s+'; 
    docker rmi "$($parts[0]):$($parts[1])" 
}
```

---

## 🗄️ Step 3: Clean Up Old Data (OPTIONAL - READ CAREFULLY)

### ⚠️ WARNING: This deletes all indexed data and thumbnails!

**Only do this if:**
- Upgrading from v0.4.10 or older (breaking schema changes)
- Starting fresh for testing
- Database is corrupted

**DO NOT do this if:**
- Upgrading from v0.4.11 or v0.4.12 (data is compatible)
- You want to keep existing indexed data

```powershell
# Delete Docker volumes (THIS DELETES ALL DATA)
docker volume rm fantasyfolio_fantasyfolio_data
docker volume rm fantasyfolio_fantasyfolio_thumbs
docker volume rm fantasyfolio_fantasyfolio_logs

# Or if using different volume names:
docker volume rm fantasyfolio_data
docker volume rm fantasyfolio_thumbs
docker volume rm fantasyfolio_logs

# List remaining volumes to verify
docker volume ls | Select-String fantasyfolio
```

**Note:** Your original 3D model files are NEVER deleted - they're in your source directories (e.g., `D:\3D-Models`). Only the database and thumbnails are removed.

---

## 📥 Step 4: Pull Fresh v0.4.13 Image

```powershell
# Pull latest release
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13

# Verify download
docker images | Select-String fantasyfolio
```

**Expected output:**
```
ghcr.io/diminox-kullwinder/fantasyfolio   0.4.13    a03a19608e6d   2.74GB
```

---

## 🚀 Step 5: Deploy v0.4.13

### Option A: Using docker-compose.yml (Recommended)

**Update your `C:\FantasyFolio\docker-compose.yml`:**

```yaml
version: '3.8'

services:
  fantasyfolio:
    image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13  # <-- Update this line
    container_name: fantasyfolio
    restart: unless-stopped
    
    ports:
      - "8888:8888"
    
    environment:
      - FANTASYFOLIO_ENV=production
      - FANTASYFOLIO_DATABASE_PATH=/app/data/fantasyfolio.db
      - FANTASYFOLIO_SECRET_KEY=change-me-in-production
    
    volumes:
      # Database (auto-created by Docker)
      - fantasyfolio_data:/app/data
      - fantasyfolio_thumbs:/app/thumbnails
      - fantasyfolio_logs:/app/logs
      
      # Your 3D models (read-only)
      - O:/3DFiles/3DModels-TEMP:/content/models:ro
      # Or your main library:
      # - D:/3D-Library:/content/models:ro

volumes:
  fantasyfolio_data:
  fantasyfolio_thumbs:
  fantasyfolio_logs:
```

**Start container:**
```powershell
cd C:\FantasyFolio
docker-compose up -d
```

### Option B: Direct Docker Run

```powershell
docker run -d `
  --name fantasyfolio `
  --restart unless-stopped `
  -p 8888:8888 `
  -v fantasyfolio_data:/app/data `
  -v fantasyfolio_thumbs:/app/thumbnails `
  -v fantasyfolio_logs:/app/logs `
  -v O:/3DFiles/3DModels-TEMP:/content/models:ro `
  ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
```

---

## ✅ Step 6: Verify Deployment

```powershell
# Check container is running
docker ps

# Check health
curl http://localhost:8888/api/system/health

# Expected response:
# {"status":"healthy","service":"FantasyFolio API","platform":"linux"}

# View logs
docker logs fantasyfolio --tail 50
```

---

## 🔍 Step 7: Index Your Models

### Using Browser
1. Open http://localhost:8888
2. Go to Settings
3. Click "Scan 3D Models"

### Using API
```powershell
# Index models with duplicate prevention (default 'merge' policy)
curl -X POST http://localhost:8888/api/index/directory `
  -H "Content-Type: application/json" `
  -d '{
    "path": "/content/models",
    "recursive": true,
    "duplicate_policy": "merge"
  }'

# Check indexing progress
curl http://localhost:8888/api/models/index-stats
```

---

## 🧪 Test New Features

### Test 1: SVG Support
1. Place an SVG file in your models directory
2. Re-index
3. Verify SVG appears with thumbnail
4. Click "View Full Size" button

### Test 2: GLB/GLTF Support
1. Place a GLB or GLTF file in your models directory
2. Re-index
3. Click on file, then "3D Preview"
4. Verify model loads in 3D viewer

### Test 3: Duplicate Prevention
```powershell
# Index directory
curl -X POST http://localhost:8888/api/index/directory `
  -d '{"path": "/content/models/test-folder", "duplicate_policy": "reject"}'

# Copy files to different location
# Re-index
curl -X POST http://localhost:8888/api/index/directory `
  -d '{"path": "/content/models/test-folder-copy", "duplicate_policy": "reject"}'

# Check stats - should show duplicate count
```

### Test 4: Infinite Scroll
1. Index 200+ models
2. Open web UI
3. Scroll to bottom of grid
4. Verify next 100 models load automatically

---

## 🔄 Complete Cleanup Script (PowerShell)

**Save as `cleanup-and-deploy.ps1`:**

```powershell
#!/usr/bin/env pwsh
# FantasyFolio v0.4.13 - Complete Cleanup & Deploy Script for Windows

Write-Host "🧹 FantasyFolio v0.4.13 - Cleanup & Deploy" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop containers
Write-Host "Step 1: Stopping containers..." -ForegroundColor Yellow
docker-compose down 2>$null
docker stop fantasyfolio 2>$null
docker rm fantasyfolio 2>$null

# Step 2: Remove old images
Write-Host "Step 2: Removing old images..." -ForegroundColor Yellow
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.11 2>$null
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.10 2>$null
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:latest 2>$null

# Step 3: Clean up volumes (OPTIONAL - uncomment if needed)
# Write-Host "Step 3: Removing old volumes (DATA WILL BE DELETED)..." -ForegroundColor Red
# docker volume rm fantasyfolio_data 2>$null
# docker volume rm fantasyfolio_thumbs 2>$null
# docker volume rm fantasyfolio_logs 2>$null

# Step 4: Pull new image
Write-Host "Step 4: Pulling v0.4.13..." -ForegroundColor Yellow
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13

# Step 5: Start container
Write-Host "Step 5: Starting FantasyFolio v0.4.13..." -ForegroundColor Yellow
docker-compose up -d

# Step 6: Wait for startup
Write-Host "Step 6: Waiting for startup (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Step 7: Check health
Write-Host "Step 7: Checking health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8888/api/system/health"
    if ($health.status -eq "healthy") {
        Write-Host "✅ FantasyFolio v0.4.13 is running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Access at: http://localhost:8888" -ForegroundColor Cyan
    } else {
        Write-Host "⚠️  Health check returned: $($health.status)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Health check failed. Check logs with: docker logs fantasyfolio" -ForegroundColor Red
}

Write-Host ""
Write-Host "📊 Current status:" -ForegroundColor Cyan
docker ps | Select-String fantasyfolio

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host "Next: Index your models via Settings or API" -ForegroundColor Cyan
```

**Run it:**
```powershell
cd C:\FantasyFolio
.\cleanup-and-deploy.ps1
```

---

## 📊 Quick Status Check

```powershell
# Container status
docker ps -a | Select-String fantasyfolio

# Images
docker images | Select-String fantasyfolio

# Volumes
docker volume ls | Select-String fantasyfolio

# Logs
docker logs fantasyfolio --tail 20

# Disk usage
docker system df
```

---

## 🆘 Troubleshooting

### Container won't start
```powershell
# Check logs
docker logs fantasyfolio

# Remove and recreate
docker rm -f fantasyfolio
docker-compose up -d
```

### Port 8888 already in use
```powershell
# Find what's using port 8888
netstat -ano | findstr :8888

# Kill the process (if safe)
taskkill /PID <process_id> /F
```

### Database permission errors
```powershell
# This shouldn't happen with named volumes, but if it does:
docker-compose down
docker volume rm fantasyfolio_data
docker-compose up -d
# Database will be recreated
```

### Can't pull image (authentication)
```powershell
# The image is public, but if you get auth errors:
# Just pull without login - it's a public package
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
```

---

## 📋 Deployment Checklist

- [ ] Old containers stopped and removed
- [ ] Old images removed (0.4.11 and older)
- [ ] Old volumes removed (if doing fresh install)
- [ ] v0.4.13 image pulled
- [ ] docker-compose.yml updated with `:0.4.13`
- [ ] Container started
- [ ] Health check passes
- [ ] Can access http://localhost:8888
- [ ] Models directory mounted correctly
- [ ] Indexing works
- [ ] New features tested (SVG, GLB, duplicate prevention)

---

## 🎯 Summary

**What this does:**
1. Removes old FantasyFolio containers and images
2. Pulls fresh v0.4.13 from GitHub
3. Starts new container with clean state
4. Verifies deployment working

**Time required:** ~5-10 minutes (depending on download speed)

**Data loss:** Only if you delete volumes (easily re-indexed)

**Risk level:** Low (original model files never touched)

---

**Ready to deploy v0.4.13 on Windows!** 🚀
