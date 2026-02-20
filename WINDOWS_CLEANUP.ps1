# FantasyFolio v0.4.15 - Windows Preflight Cleanup (PowerShell)
# Run in PowerShell (not bash)

Write-Host "=== FantasyFolio v0.4.15 Preflight Cleanup ===" -ForegroundColor Cyan
Write-Host ""

# 1. Stop and remove old container
Write-Host "1. Stopping old containers..." -ForegroundColor Yellow
docker stop fantasyfolio -ErrorAction SilentlyContinue
docker rm fantasyfolio -ErrorAction SilentlyContinue
Write-Host "   Done" -ForegroundColor Green
Write-Host ""

# 2. Remove old volumes (FRESH START)
Write-Host "2. Removing old volumes (THIS DELETES ALL DATA)..." -ForegroundColor Yellow
$confirm = Read-Host "   Are you sure? This deletes the database and thumbnails. (y/n)"
if ($confirm -eq 'y') {
    docker volume rm fantasyfolio_data -ErrorAction SilentlyContinue
    docker volume rm fantasyfolio_thumbs -ErrorAction SilentlyContinue
    docker volume rm fantasyfolio_logs -ErrorAction SilentlyContinue
    Write-Host "   Volumes removed" -ForegroundColor Green
} else {
    Write-Host "   Skipped volume removal" -ForegroundColor Yellow
}
Write-Host ""

# 3. Remove old images
Write-Host "3. Checking for old images..." -ForegroundColor Yellow
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}" | Select-String "fantasyfolio"
Write-Host ""

Write-Host "   Removing old versions..." -ForegroundColor Yellow
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13 -ErrorAction SilentlyContinue
docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14 -ErrorAction SilentlyContinue

# Remove old 0.4.15 if SHA doesn't match f1b9dd17da6c
$oldImages = docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Select-String "fantasyfolio:0.4.15" | ForEach-Object { $_.ToString().Split()[1] }
foreach ($imageId in $oldImages) {
    if ($imageId -notlike "f1b9dd17da6c*") {
        Write-Host "   Removing old 0.4.15 image: $imageId" -ForegroundColor Yellow
        docker rmi $imageId -ErrorAction SilentlyContinue
    }
}

docker rmi ghcr.io/diminox-kullwinder/fantasyfolio:latest -ErrorAction SilentlyContinue
Write-Host "   Done" -ForegroundColor Green
Write-Host ""

# 4. Clean Docker system
Write-Host "4. Cleaning Docker system..." -ForegroundColor Yellow
docker system prune -f
Write-Host "   Done" -ForegroundColor Green
Write-Host ""

# 5. Pull fresh v0.4.15
Write-Host "5. Pulling fresh v0.4.15 image..." -ForegroundColor Yellow
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
Write-Host "   Done" -ForegroundColor Green
Write-Host ""

# 6. Verify
Write-Host "6. Verification:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Current images:" -ForegroundColor Yellow
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}" | Select-String "fantasyfolio"
Write-Host ""

$correctImage = docker images --format "{{.ID}}" ghcr.io/diminox-kullwinder/fantasyfolio:0.4.15
if ($correctImage -like "f1b9dd17da6c*") {
    Write-Host "   ✅ Correct v0.4.15 image present (SHA: $correctImage)" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  WARNING: Image SHA doesn't match expected f1b9dd17da6c" -ForegroundColor Red
    Write-Host "   Found: $correctImage" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Cleanup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Update docker-compose.yml (set image to 0.4.15)"
Write-Host "2. Run: docker-compose up -d"
Write-Host "3. Check logs: docker logs -f fantasyfolio"
Write-Host ""
