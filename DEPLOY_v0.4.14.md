# FantasyFolio v0.4.14 - Deployment Guide

**Date:** 2026-02-18  
**Status:** ✅ Ready for Windows Testing

---

## Summary

**All 4 thumbnail bugs fixed and tested locally on Mac:**

1. ✅ **Infinite scroll** - Fixed wrong container selector
2. ✅ **Flask thumbnail route** - Added `/thumbnails/` serving  
3. ✅ **Concurrency control** - ThreadPoolExecutor limits to 4 workers
4. ✅ **Daemon autostart** - Enabled in supervisord.conf

---

## Windows Deployment (Tomorrow Morning)

### Step 1: Pull Latest Image

```powershell
cd C:\FantasyFolio
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14
```

### Step 2: Update docker-compose.yml

Change this line:
```yaml
image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.13
```

To:
```yaml
image: ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14
```

### Step 3: Restart Container

```powershell
docker-compose down
docker-compose up -d
```

### Step 4: Verify Daemon is Running

Wait 10 seconds, then:

```powershell
docker exec fantasyfolio ps aux | Select-String "thumbnail_daemon"
```

You should see:
```
root  XXX  ... python /app/scripts/thumbnail_daemon.py
```

### Step 5: Test Thumbnails

1. Open browser: `http://localhost:8888`
2. Navigate to models
3. Thumbnails should appear automatically as you browse!

---

## What Changed?

### Before v0.4.14
- Thumbnails rendered to disk but Flask couldn't serve them (404)
- Daemon never started (`autostart=false`)
- Each model preview spawned unlimited threads → crash with 200+ models
- `supervisorctl` broken (missing RPC interface)

### After v0.4.14
- Flask serves thumbnails from `/app/thumbnails/` via new route
- Daemon auto-starts on boot
- ThreadPoolExecutor limits concurrent renders to 4 workers
- `supervisorctl` works (RPC interface added)

---

## Expected Behavior

**When you index models:**
- Thumbnail daemon automatically starts
- Renders thumbnails in background (4 at a time)
- Check progress: `docker logs fantasyfolio --tail 50`

**When you browse models:**
- Thumbnails load automatically
- If missing, queued for render (max 4 concurrent)
- Placeholder shown while rendering

**All 272 models:**
- Should render within 5-10 minutes
- System stays responsive (no more crashes!)
- Thumbnails appear as they complete

---

## Troubleshooting

### Thumbnails Still Don't Show

**Check daemon is running:**
```powershell
docker exec fantasyfolio ps aux | Select-String "thumbnail_daemon"
```

**Check thumbnail directory:**
```powershell
docker exec fantasyfolio ls /app/thumbnails/3d/ | Select-Object -First 10
```

**Check database:**
```powershell
docker exec fantasyfolio sqlite3 /app/data/fantasyfolio.db "SELECT COUNT(*) FROM models WHERE has_thumbnail = 1;"
```

**Test thumbnail route:**
```powershell
curl http://localhost:8888/thumbnails/3d/1.png -o test.png
```

If `test.png` downloads = route works!

### Daemon Not Running

**Manual start:**
```powershell
docker exec -d fantasyfolio python /app/scripts/thumbnail_daemon.py
```

**Check supervisord status:**
```powershell
docker exec fantasyfolio cat /app/logs/supervisord.log | Select-Object -Last 50
```

### Browser 404 on Thumbnails

**Check Flask route:**
```powershell
curl -I http://localhost:8888/thumbnails/3d/1.png
```

Should return `HTTP/1.1 200 OK`

---

## Git Commits (v0.4.14)

All fixes pushed to master branch:

- `c1ea6bc` - Fix infinite scroll (wrong container selector)
- `88c4a50` - Add thumbnail debugging
- `7d652d1` - Add Flask `/thumbnails/` route
- `5d876f7` - Add ThreadPoolExecutor concurrency control
- `feed6b8` - Enable daemon autostart + RPC interface
- `6a7a39d` - Update documentation

**View full changes:**
```bash
git log --oneline feed6b8..6a7a39d
```

---

## Next Steps After Testing

1. **If thumbnails work:** Deploy to NAS appliance for full library QA
2. **If issues remain:** Provide diagnostics:
   - `docker logs fantasyfolio > logs.txt`
   - Screenshot of browser console (F12)
   - Output of troubleshooting commands above

3. **Once stable:** Plan v0.5.0 development:
   - Google/Apple SSO authentication
   - Role-based permissions
   - Week 1 foundation features (bulk ops, drag-drop, folder UI)

---

## Technical Details

**Thumbnail Rendering Flow (v0.4.14):**

1. User browses → Frontend requests `/thumbnails/3d/123.png`
2. Flask route serves from `/app/thumbnails/3d/`
3. If file missing → Queue render via ThreadPoolExecutor (max 4 workers)
4. Daemon also runs in background, rendering pending models
5. Database tracks: `has_thumbnail`, `thumb_path`, `thumb_rendered_at`

**Key Files Changed:**
- `fantasyfolio/app.py` - Added `/thumbnails/` route
- `fantasyfolio/api/models.py` - Added ThreadPoolExecutor
- `docker/supervisord.conf` - Enabled autostart, added RPC interface

**Docker Image:**
- Tag: `ghcr.io/diminox-kullwinder/fantasyfolio:0.4.14`
- Also: `ghcr.io/diminox-kullwinder/fantasyfolio:latest`
- Size: ~2.7GB (unchanged from v0.4.13)

---

**Questions?** Check `BUGFIX_v0.4.14.md` for detailed root cause analysis.

**Ready to test!** 🔴
