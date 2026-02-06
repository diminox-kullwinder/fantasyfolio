# DAM Setup Guide - Local Development

## Database Isolation

This project maintains **two separate databases** running simultaneously:

### 1. Local Flask Instance (Port 8008)
- **Database:** `/Users/claw/.openclaw/workspace/dam/data/dam.db` (LIVE, ~1.2GB, thousands of assets)
- **Purpose:** Production data - your actual working library
- **Config:** `.env.local` (auto-loaded by startup script)

### 2. Docker Instance (Port 8888)
- **Database:** `./data/dam.db` (FRESH, test/validation only)
- **Purpose:** Validate fresh GitHub installations work correctly
- **Config:** Docker Compose volumes (isolated container)

---

## Starting the Servers

### Automatic (on reboot)
The local Flask server starts automatically via crontab:
```bash
@reboot /Users/claw/projects/dam/start-server.sh
```

### Manual Start
```bash
# Local Flask (uses live 1.2GB database)
cd /Users/claw/projects/dam
source .venv/bin/activate
python -m flask run --port 8008

# Docker (uses fresh test database)
docker-compose up -d
```

---

## Preventing Database Mix-up

### Safety Mechanisms in Place:

1. **`.env.local` Configuration**
   - Explicitly specifies which database the local Flask instance uses
   - Prevents accidental pointing to wrong path
   - Loaded automatically by `start-server.sh`

2. **Startup Validation**
   - Database initialization logs file size
   - Warns if database < 100MB (expected ~1.2GB for LIVE)
   - Watch server logs for: `⚠️  Database is only 50.2MB...`

3. **Docker Isolation**
   - Docker container has its own data volume
   - Cannot accidentally write to live database
   - Can be reset by deleting `./data/` folder

---

## Environment Variables

If you need to override settings, add to `.env.local`:

```bash
# LIVE database path (don't change unless you know what you're doing)
DAM_DATABASE_PATH=/Users/claw/.openclaw/workspace/dam/data/dam.db

# Development vs Production
DAM_ENV=development

# Port for Flask (local)
DAM_PORT=8008

# Logging
DAM_LOG_LEVEL=INFO
```

---

## Verification

### Check Local Database is Correct
```bash
# Should return ~1.2GB (LIVE database)
ls -lh /Users/claw/.openclaw/workspace/dam/data/dam.db

# Should return small size (test database)
ls -lh /Users/claw/projects/dam/data/dam.db
```

### Check Ports Are Correct
```bash
# Local Flask on 8008 serving LIVE data
curl http://localhost:8008 | grep -i "RPG Library"

# Docker on 8888 serving fresh test data
curl http://localhost:8888 | grep -i "RPG Library"
```

---

## Troubleshooting

### Both ports showing same (small) database
- Local Flask is pointing to wrong database
- Fix: Check `.env.local` in `/Users/claw/projects/dam/`
- Restart: `/Users/claw/projects/dam/start-server.sh`

### Docker port 8888 not responding
```bash
# Check if container is running
docker ps | grep dam

# Check logs
docker logs dam

# Restart
docker-compose restart dam
```

### Database size warnings at startup
- Watch for: `⚠️  Database is only 50.2MB. Expected ~1.2GB`
- This means the local instance is pointing to the wrong database
- Check `DAM_DATABASE_PATH` in `.env.local`

---

## Remember

- **8008 = LIVE data (1.2GB, production)**
- **8888 = TEST data (small, fresh from GitHub)**

If in doubt, check file sizes:
```bash
ls -lh /Users/claw/.openclaw/workspace/dam/data/dam.db  # Should be ~1.2GB
ls -lh /Users/claw/projects/dam/data/dam.db             # Should be small
```
