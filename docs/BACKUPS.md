# DAM Backup System

DAM provides a multi-layer data protection system to safeguard your digital assets database.

## Overview

The backup system has five layers of protection:

| Layer | Feature | Purpose |
|-------|---------|---------|
| 0 | Volume Monitoring | Prevent operations when storage offline |
| 1 | Soft Deletes (Trash) | 30-day recovery window for deleted items |
| 2 | Change Journal | Audit trail of all modifications |
| 3 | SQLite Snapshots | Point-in-time local database copies |
| 4 | Backup Policies | Automated offsite/deduplicated backups |

## Backup Destination Types

### Local (Copy)
Simple file copy to a local directory. Creates timestamped copies of the database snapshot.

- **Pros**: Simple, fast, no dependencies
- **Cons**: No deduplication, uses full space per copy
- **Use for**: Quick local backups, external drives

### Restic (Deduplicated) ⭐ Recommended
Uses [Restic](https://restic.net) for block-level deduplicated backups. Only changed data blocks are stored.

- **Pros**: 
  - Massive space savings (typically 80-90% reduction)
  - Built-in encryption
  - Works locally or over SFTP
  - Cross-platform (macOS, Linux, Windows)
- **Cons**: Requires Restic installation
- **Use for**: Primary backup strategy, NAS backups, cloud storage

### Network (SSH/rsync)
Copies snapshots to a remote server via SSH using rsync.

- **Pros**: Works with any SSH server
- **Cons**: No deduplication, full copies each time
- **Use for**: Simple remote backup when Restic not available

## Installing Restic

```bash
# macOS
brew install restic

# Linux (Debian/Ubuntu)
sudo apt install restic

# Linux (Fedora)
sudo dnf install restic

# Windows
choco install restic
# or download from https://github.com/restic/restic/releases
```

Verify installation:
```bash
restic version
```

## Setting Up a Restic Backup Policy

### 1. Create the Repository

Choose a location for your backup repository:

```bash
# Local directory
restic init --repo /Volumes/Backup/dam-backups

# NAS via SFTP (remote)
restic init --repo sftp:user@nas.local:/volume1/backups/dam

# When prompted, enter a strong password and SAVE IT SECURELY
```

**Remote Repository Formats:**
- `sftp:user@hostname:/path` — SFTP over SSH (most common)
- `sftp:user@hostname:port/path` — SFTP with custom port
- Uses your default SSH key (`~/.ssh/id_rsa`)

### 2. Create a Backup Policy in DAM

1. Open DAM → Settings (⚙️) → Advanced tab
2. Scroll to **Backup Policies** section
3. Click **➕ Add Policy**
4. Configure:
   - **Name**: e.g., "Daily NAS Backup"
   - **Type**: Restic (dedup)
   - **Path**: Your repository path (e.g., `/Volumes/Backup/dam-backups`)
   - **Password**: The password you set during `restic init`
   - **Frequency**: Daily, Weekly, Monthly, or Yearly
   - **Time**: When to run (default 2:00 AM)
   - **Keep**: Number of snapshots to retain (e.g., 7)
   - **State**: Set to "Active" to enable

### 3. Understanding Deduplication

Restic stores data in 64KB chunks. When you backup:

| Backup | Database Size | Data Stored | Cumulative Total |
|--------|--------------|-------------|------------------|
| 1st | 1.2 GB | 1.2 GB | 1.2 GB |
| 2nd (5% changed) | 1.2 GB | ~60 MB | ~1.26 GB |
| 3rd (5% changed) | 1.2 GB | ~60 MB | ~1.32 GB |
| ... | | | |
| 7th | 1.2 GB | ~60 MB | ~1.56 GB |

**7 "copies" in ~1.56 GB instead of 8.4 GB!**

## One-Click Restore

### From Local Snapshot

1. Settings → Advanced → **Database Snapshots**
2. Click **📋 View All**
3. Find the snapshot you want
4. Click **🔄 Restore**
5. Confirm the restore

A safety backup is automatically created before restoring.

### From Restic Repository

1. Settings → Advanced → **Restore from Restic**
2. Enter your repository path
3. Enter your repository password
4. Click **🔍 Load Snapshots**
5. Find the snapshot you want
6. Click **🔄 Restore**
7. Confirm the restore

The restore process:
1. Creates a safety backup of current database
2. Downloads the snapshot from Restic
3. Extracts the database file
4. Replaces the current database
5. Shows success message

## Backup Schedule Recommendations

| Scenario | Frequency | Retention | Notes |
|----------|-----------|-----------|-------|
| Active editing | Daily | 14 days | Frequent changes |
| Moderate use | Daily | 7 days | Normal usage |
| Archive/Reference | Weekly | 4 weeks | Rarely changed |
| Critical data | Daily + Weekly | 7 daily + 4 weekly | Belt and suspenders |

## Command-Line Operations

### Manual Backup
```bash
# From DAM directory
.venv/bin/python -m dam.services.restic_backup backup \
  --repo /path/to/repo \
  --source data/snapshots/latest.db
```

### List Snapshots
```bash
restic -r /path/to/repo snapshots
```

### Check Repository Health
```bash
restic -r /path/to/repo check
```

### Restore Specific File
```bash
restic -r /path/to/repo restore latest --target /tmp/restore/
```

## Troubleshooting

### "Restic not installed"
Install Restic using the commands in the Installation section above.

### "Repository not initialized"
Run `restic init --repo /your/path` first, or let DAM auto-initialize when creating the policy.

### "Wrong password"
Restic repositories are encrypted. You must use the exact password set during `restic init`. There is no password recovery.

### "No snapshots available"
Backups copy from DAM snapshots, not the live database. Create a snapshot first:
- Settings → Advanced → Database Snapshots → **📸 Create Snapshot**

### Backup fails with timeout
Large databases or slow networks may need more time. Check:
- Network connectivity to remote repositories
- Available disk space
- Repository health: `restic -r /path check`

## Security Notes

1. **Repository Password**: Restic encrypts all data. Store your password securely (password manager recommended).

2. **SSH Keys**: For remote Restic repositories over SFTP, use SSH keys instead of passwords.

3. **Backup the Password**: If you lose the repository password, the backups are unrecoverable.

4. **Test Restores**: Periodically test that you can restore from your backups.

## API Reference

### Check Restic Status
```
GET /api/restic/status
```

### Initialize Repository
```
POST /api/restic/init
Body: { "repo_path": "...", "password": "..." }
```

### Run Backup
```
POST /api/restic/backup
Body: { "repo_path": "...", "password": "...", "tags": ["..."] }
```

### List Snapshots
```
GET /api/restic/snapshots?repo_path=...&password=...
```

### Restore Database
```
POST /api/restic/restore
Body: { "repo_path": "...", "password": "...", "snapshot_id": "..." }
```

### Prune Old Snapshots
```
POST /api/restic/prune
Body: { "repo_path": "...", "password": "...", "keep_last": 7 }
```
