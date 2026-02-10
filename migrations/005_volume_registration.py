#!/usr/bin/env python3
"""
Migration 005: Volume Registration

Phase 2 of Efficient Indexing Architecture:
- Auto-detect volumes from asset_locations table
- Create volume records with UUIDs
- Compute relative_path for existing assets
- Link assets to volumes via volume_id
- Implement basic volume health check

Part of the DAM Efficient Indexing & Thumbnail Architecture v1.2
"""

import sqlite3
import sys
import os
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_os_volume_uuid(mount_path: str) -> Optional[str]:
    """
    Get the OS-level UUID for a mounted volume (macOS).
    Returns None if not available.
    """
    try:
        # On macOS, use diskutil to get volume UUID
        result = subprocess.run(
            ['diskutil', 'info', mount_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'Volume UUID:' in line:
                    return line.split(':')[1].strip()
        
        return None
    except Exception:
        return None


def is_volume_online(mount_path: str) -> bool:
    """Check if a volume/path is accessible."""
    path = Path(mount_path)
    return path.exists() and path.is_dir()


def is_path_writable(path: str) -> bool:
    """Check if a path is writable."""
    try:
        test_file = Path(path) / '.dam_write_test'
        test_file.touch()
        test_file.unlink()
        return True
    except (PermissionError, OSError):
        return False


def compute_relative_path(file_path: str, mount_path: str) -> Optional[str]:
    """
    Compute relative path from mount point.
    Returns None if file_path is not under mount_path.
    """
    try:
        file_p = Path(file_path)
        mount_p = Path(mount_path)
        
        # Check if file is under mount path
        rel = file_p.relative_to(mount_p)
        return str(rel)
    except ValueError:
        return None


def migrate(db_path: str, dry_run: bool = False) -> dict:
    """
    Run the migration.
    
    Args:
        db_path: Path to SQLite database
        dry_run: If True, only report what would be done
    
    Returns:
        Dict with migration results
    """
    results = {
        'volumes_created': [],
        'models_linked': 0,
        'models_unlinked': 0,
        'assets_linked': 0,
        'assets_unlinked': 0,
        'errors': [],
        'warnings': []
    }
    
    conn = get_connection(db_path)
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # 1. GET ASSET LOCATIONS
        # ═══════════════════════════════════════════════════════════════════
        locations = conn.execute("""
            SELECT id, name, asset_type, path, enabled 
            FROM asset_locations
            WHERE enabled = 1
        """).fetchall()
        
        print(f"\nFound {len(locations)} enabled asset locations")
        
        # ═══════════════════════════════════════════════════════════════════
        # 2. CREATE VOLUME RECORDS
        # ═══════════════════════════════════════════════════════════════════
        volume_map = {}  # location_id -> volume_id
        path_to_volume = {}  # mount_path -> volume_id
        
        for loc in locations:
            loc = dict(loc)
            mount_path = loc['path']
            
            # Check if volume already exists for this path
            existing = conn.execute(
                "SELECT id FROM volumes WHERE mount_path = ?",
                (mount_path,)
            ).fetchone()
            
            if existing:
                volume_id = existing['id']
                print(f"  Volume already exists for {mount_path}: {volume_id}")
                results['warnings'].append(f"Volume already exists: {mount_path}")
            else:
                # Create new volume
                volume_id = f"vol-{uuid.uuid4().hex[:12]}"
                is_online = is_volume_online(mount_path)
                is_readonly = not is_path_writable(mount_path) if is_online else True
                volume_uuid = get_os_volume_uuid(mount_path) if is_online else None
                
                volume = {
                    'id': volume_id,
                    'label': loc['name'],
                    'mount_path': mount_path,
                    'volume_uuid': volume_uuid,
                    'status': 'online' if is_online else 'offline',
                    'is_readonly': 1 if is_readonly else 0,
                    'last_seen_at': datetime.now().isoformat() if is_online else None,
                }
                
                print(f"\n  Creating volume: {volume_id}")
                print(f"    Label: {volume['label']}")
                print(f"    Path: {mount_path}")
                print(f"    Status: {volume['status']}")
                print(f"    Read-only: {bool(volume['is_readonly'])}")
                print(f"    UUID: {volume['volume_uuid']}")
                
                if not dry_run:
                    conn.execute("""
                        INSERT INTO volumes (id, label, mount_path, volume_uuid, 
                                             status, is_readonly, last_seen_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        volume['id'], volume['label'], volume['mount_path'],
                        volume['volume_uuid'], volume['status'], 
                        volume['is_readonly'], volume['last_seen_at']
                    ))
                
                results['volumes_created'].append({
                    'id': volume_id,
                    'label': volume['label'],
                    'path': mount_path,
                    'status': volume['status']
                })
            
            volume_map[loc['id']] = volume_id
            path_to_volume[mount_path] = volume_id
        
        # ═══════════════════════════════════════════════════════════════════
        # 3. LINK MODELS TO VOLUMES
        # ═══════════════════════════════════════════════════════════════════
        print("\n\nLinking models to volumes...")
        
        # Get all models without volume_id
        models = conn.execute("""
            SELECT id, file_path, archive_path FROM models 
            WHERE volume_id IS NULL
        """).fetchall()
        
        print(f"  Found {len(models)} models to process")
        
        linked_count = 0
        unlinked_count = 0
        
        for model in models:
            model = dict(model)
            
            # Determine the root path (archive_path or file_path)
            root_path = model['archive_path'] or model['file_path']
            if not root_path:
                unlinked_count += 1
                continue
            
            # Find matching volume
            matched_volume = None
            matched_mount = None
            
            for mount_path, vol_id in path_to_volume.items():
                if root_path.startswith(mount_path):
                    # Use longest matching mount path
                    if matched_mount is None or len(mount_path) > len(matched_mount):
                        matched_volume = vol_id
                        matched_mount = mount_path
            
            if matched_volume:
                relative = compute_relative_path(root_path, matched_mount)
                
                if not dry_run:
                    conn.execute("""
                        UPDATE models SET 
                            volume_id = ?,
                            relative_path = ?,
                            last_seen_at = ?
                        WHERE id = ?
                    """, (
                        matched_volume,
                        relative,
                        datetime.now().isoformat(),
                        model['id']
                    ))
                
                linked_count += 1
            else:
                unlinked_count += 1
                if unlinked_count <= 5:
                    results['warnings'].append(f"No volume for model: {root_path[:80]}")
        
        results['models_linked'] = linked_count
        results['models_unlinked'] = unlinked_count
        print(f"  Linked: {linked_count}, Unlinked: {unlinked_count}")
        
        # ═══════════════════════════════════════════════════════════════════
        # 4. LINK ASSETS (PDFs) TO VOLUMES
        # ═══════════════════════════════════════════════════════════════════
        print("\nLinking assets (PDFs) to volumes...")
        
        assets = conn.execute("""
            SELECT id, file_path FROM assets 
            WHERE volume_id IS NULL
        """).fetchall()
        
        print(f"  Found {len(assets)} assets to process")
        
        linked_count = 0
        unlinked_count = 0
        
        for asset in assets:
            asset = dict(asset)
            file_path = asset['file_path']
            
            if not file_path:
                unlinked_count += 1
                continue
            
            # Find matching volume
            matched_volume = None
            matched_mount = None
            
            for mount_path, vol_id in path_to_volume.items():
                if file_path.startswith(mount_path):
                    if matched_mount is None or len(mount_path) > len(matched_mount):
                        matched_volume = vol_id
                        matched_mount = mount_path
            
            if matched_volume:
                relative = compute_relative_path(file_path, matched_mount)
                
                if not dry_run:
                    conn.execute("""
                        UPDATE assets SET 
                            volume_id = ?,
                            relative_path = ?,
                            last_seen_at = ?
                        WHERE id = ?
                    """, (
                        matched_volume,
                        relative,
                        datetime.now().isoformat(),
                        asset['id']
                    ))
                
                linked_count += 1
            else:
                unlinked_count += 1
                if unlinked_count <= 5:
                    results['warnings'].append(f"No volume for asset: {file_path[:80]}")
        
        results['assets_linked'] = linked_count
        results['assets_unlinked'] = unlinked_count
        print(f"  Linked: {linked_count}, Unlinked: {unlinked_count}")
        
        # ═══════════════════════════════════════════════════════════════════
        # 5. COMMIT
        # ═══════════════════════════════════════════════════════════════════
        if not dry_run:
            conn.commit()
            print("\n✓ Migration committed successfully")
        else:
            print("\nDRY RUN - no changes made")
        
    except Exception as e:
        results['errors'].append(str(e))
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return results


def print_results(results: dict):
    """Print migration results."""
    print("\n" + "=" * 60)
    print("MIGRATION RESULTS")
    print("=" * 60)
    
    if results['volumes_created']:
        print(f"\n✓ Volumes created ({len(results['volumes_created'])}):")
        for v in results['volumes_created']:
            status_icon = "🟢" if v['status'] == 'online' else "🔴"
            print(f"    {status_icon} {v['id']}: {v['label']}")
            print(f"       {v['path']}")
    
    print(f"\n✓ Models linked: {results['models_linked']}")
    if results['models_unlinked']:
        print(f"  ⚠ Models without volume: {results['models_unlinked']}")
    
    print(f"\n✓ Assets linked: {results['assets_linked']}")
    if results['assets_unlinked']:
        print(f"  ⚠ Assets without volume: {results['assets_unlinked']}")
    
    if results['warnings']:
        print(f"\n⚠ Warnings ({len(results['warnings'])}):")
        for w in results['warnings'][:10]:
            print(f"    - {w}")
        if len(results['warnings']) > 10:
            print(f"    ... and {len(results['warnings']) - 10} more")
    
    if results['errors']:
        print(f"\n✗ Errors ({len(results['errors'])}):")
        for e in results['errors']:
            print(f"    - {e}")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run migration 005 - Volume Registration')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    if not Path(args.db_path).exists():
        print(f"Error: Database not found: {args.db_path}")
        sys.exit(1)
    
    print(f"Running migration on: {args.db_path}")
    print(f"Dry run: {args.dry_run}")
    
    results = migrate(args.db_path, dry_run=args.dry_run)
    print_results(results)
