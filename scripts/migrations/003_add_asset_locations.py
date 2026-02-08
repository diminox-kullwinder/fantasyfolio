#!/usr/bin/env python3
"""
Migration 003: Add asset_locations table.

Replaces hardcoded settingPdfRoot/setting3dRoot with flexible multi-location system.
Supports local directories, mounted volumes, and remote SFTP connections.
"""

import sqlite3
import os
import json
import uuid
from datetime import datetime

DB_PATH = os.environ.get('DAM_DATABASE_PATH', '/Users/claw/projects/dam/data/dam_uat.db')


def run_migration(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Add asset_locations table and migrate existing settings."""
    results = {
        'migration': '003_add_asset_locations',
        'timestamp': datetime.now().isoformat(),
        'db_path': DB_PATH,
        'dry_run': dry_run,
        'changes': []
    }
    
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_locations'")
    exists = cursor.fetchone()
    
    if exists:
        results['changes'].append('asset_locations table already exists - skipping')
        results['status'] = 'skipped'
        return results
    
    if dry_run:
        results['changes'].append('[DRY RUN] Would create asset_locations table')
        results['changes'].append('[DRY RUN] Would migrate existing settings')
        results['status'] = 'dry_run'
        return results
    
    # Create asset_locations table
    cursor.execute("""
        CREATE TABLE asset_locations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            
            -- Type of assets: 'documents' or 'models'
            asset_type TEXT NOT NULL CHECK(asset_type IN ('documents', 'models')),
            
            -- Location type: local, local_mount (SMB/NFS), remote_sftp
            location_type TEXT NOT NULL CHECK(location_type IN ('local', 'local_mount', 'remote_sftp')),
            
            -- Path configuration
            path TEXT NOT NULL,                 -- Local path or remote path
            
            -- Remote connection (for remote_sftp)
            ssh_host TEXT,                      -- SSH host or config alias
            ssh_key_path TEXT,                  -- Path to SSH private key (optional if using config)
            ssh_user TEXT,                      -- SSH username (optional if in host or config)
            ssh_port INTEGER DEFAULT 22,        -- SSH port
            
            -- Mount info (for local_mount)
            mount_check_path TEXT,              -- Path to check if mounted (e.g., .mounted marker)
            
            -- Status
            enabled INTEGER NOT NULL DEFAULT 1,
            is_primary INTEGER NOT NULL DEFAULT 0,  -- Primary location for new uploads
            
            -- Metadata
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_indexed_at TEXT,
            last_status TEXT,                   -- 'online', 'offline', 'error'
            last_status_message TEXT
        )
    """)
    results['changes'].append('Created asset_locations table')
    
    # Create indexes
    cursor.execute("CREATE INDEX idx_locations_type ON asset_locations(asset_type)")
    cursor.execute("CREATE INDEX idx_locations_enabled ON asset_locations(enabled)")
    results['changes'].append('Created indexes on asset_locations')
    
    # Migrate existing settings to asset_locations
    migrated = migrate_existing_settings(cursor, results)
    
    conn.commit()
    results['status'] = 'completed'
    results['migrated_locations'] = migrated
    
    return results


def migrate_existing_settings(cursor: sqlite3.Connection, results: dict) -> int:
    """Migrate settingPdfRoot and setting3dRoot to asset_locations."""
    migrated = 0
    
    # Get existing settings
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('pdfRoot', '3dRoot')")
    settings = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Migrate PDF root
    pdf_root = settings.get('pdfRoot')
    if pdf_root and pdf_root.strip():
        location_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO asset_locations (id, name, asset_type, location_type, path, is_primary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (location_id, 'Documents (migrated)', 'documents', 'local', pdf_root, 1))
        results['changes'].append(f'Migrated pdfRoot: {pdf_root}')
        migrated += 1
    
    # Migrate 3D root
    model_root = settings.get('3dRoot')
    if model_root and model_root.strip():
        location_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO asset_locations (id, name, asset_type, location_type, path, is_primary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (location_id, '3D Models (migrated)', 'models', 'local', model_root, 1))
        results['changes'].append(f'Migrated 3dRoot: {model_root}')
        migrated += 1
    
    # Migrate additional SMB mount points if present
    cursor.execute("SELECT value FROM settings WHERE key = 'smbMountPoints'")
    row = cursor.fetchone()
    if row and row[0]:
        mount_points = [p.strip() for p in row[0].split('\n') if p.strip()]
        for i, mp in enumerate(mount_points):
            location_id = str(uuid.uuid4())
            # Guess type from path
            asset_type = 'models' if '3d' in mp.lower() or 'model' in mp.lower() else 'documents'
            cursor.execute("""
                INSERT INTO asset_locations (id, name, asset_type, location_type, path, is_primary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (location_id, f'SMB Mount {i+1} (migrated)', asset_type, 'local_mount', mp, 0))
            results['changes'].append(f'Migrated SMB mount: {mp}')
            migrated += 1
    
    return migrated


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add asset_locations table')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--db', help='Database path')
    args = parser.parse_args()
    
    global DB_PATH
    if args.db:
        DB_PATH = args.db
    
    print(f"Migration: 003_add_asset_locations")
    print(f"Database: {DB_PATH}")
    print("-" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    results = run_migration(conn, dry_run=args.dry_run)
    conn.close()
    
    print(f"Status: {results['status']}")
    for change in results['changes']:
        print(f"  • {change}")
    if 'migrated_locations' in results:
        print(f"  Migrated {results['migrated_locations']} location(s)")


if __name__ == "__main__":
    main()
