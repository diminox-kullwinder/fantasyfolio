"""
Database Snapshot Service.

Creates point-in-time snapshots of the SQLite database using the backup API.
Supports listing, creating, restoring, and cleaning up snapshots.
"""

import os
import sqlite3
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dam.config import get_config

logger = logging.getLogger(__name__)


def get_snapshot_dir() -> Path:
    """Get the snapshot storage directory."""
    config = get_config()
    snapshot_dir = config.DATA_DIR / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir


def create_snapshot(note: Optional[str] = None) -> Dict:
    """
    Create a snapshot of the current database.
    
    Uses SQLite's backup API for a consistent snapshot even during writes.
    
    Args:
        note: Optional description for the snapshot
    
    Returns:
        Dict with snapshot details
    """
    config = get_config()
    db_path = config.DATABASE_PATH
    snapshot_dir = get_snapshot_dir()
    
    # Generate snapshot filename
    timestamp = datetime.now()
    filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.db"
    snapshot_path = snapshot_dir / filename
    
    result = {
        'timestamp': timestamp.isoformat(),
        'filename': filename,
        'path': str(snapshot_path),
        'source_db': str(db_path),
        'note': note,
        'status': 'pending'
    }
    
    try:
        # Use SQLite backup API for consistent snapshot
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(snapshot_path)
        
        source.backup(dest)
        
        source.close()
        dest.close()
        
        # Get snapshot size
        result['size_bytes'] = snapshot_path.stat().st_size
        result['size_human'] = _format_size(result['size_bytes'])
        result['status'] = 'completed'
        
        logger.info(f"Created snapshot: {filename} ({result['size_human']})")
        
        # Write metadata file
        _write_snapshot_metadata(snapshot_path, result)
        
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        logger.error(f"Snapshot creation failed: {e}", exc_info=True)
    
    return result


def _write_snapshot_metadata(snapshot_path: Path, metadata: Dict):
    """Write metadata JSON alongside snapshot file."""
    import json
    meta_path = snapshot_path.with_suffix('.json')
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def _read_snapshot_metadata(snapshot_path: Path) -> Optional[Dict]:
    """Read metadata JSON for a snapshot."""
    import json
    meta_path = snapshot_path.with_suffix('.json')
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def list_snapshots() -> List[Dict]:
    """
    List all available snapshots.
    
    Returns:
        List of snapshot info dicts, newest first
    """
    snapshot_dir = get_snapshot_dir()
    snapshots = []
    
    for path in sorted(snapshot_dir.glob("snapshot_*.db"), reverse=True):
        metadata = _read_snapshot_metadata(path)
        
        if metadata:
            snapshots.append(metadata)
        else:
            # Generate basic info from file
            stat = path.stat()
            snapshots.append({
                'filename': path.name,
                'path': str(path),
                'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'size_bytes': stat.st_size,
                'size_human': _format_size(stat.st_size),
                'status': 'completed'
            })
    
    return snapshots


def get_latest_snapshot() -> Optional[Dict]:
    """Get the most recent snapshot."""
    snapshots = list_snapshots()
    return snapshots[0] if snapshots else None


def delete_snapshot(filename: str) -> bool:
    """
    Delete a snapshot file.
    
    Args:
        filename: Snapshot filename (e.g., 'snapshot_20260207_143000.db')
    
    Returns:
        True if deleted, False if not found
    """
    snapshot_dir = get_snapshot_dir()
    snapshot_path = snapshot_dir / filename
    meta_path = snapshot_path.with_suffix('.json')
    
    if not snapshot_path.exists():
        return False
    
    try:
        snapshot_path.unlink()
        if meta_path.exists():
            meta_path.unlink()
        logger.info(f"Deleted snapshot: {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete snapshot {filename}: {e}")
        return False


def restore_snapshot(filename: str, backup_current: bool = True) -> Dict:
    """
    Restore the database from a snapshot.
    
    WARNING: This replaces the current database!
    
    Args:
        filename: Snapshot filename to restore
        backup_current: If True, backup current DB before restoring
    
    Returns:
        Dict with restore result
    """
    config = get_config()
    db_path = config.DATABASE_PATH
    snapshot_dir = get_snapshot_dir()
    snapshot_path = snapshot_dir / filename
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'source_snapshot': filename,
        'target_db': str(db_path),
        'status': 'pending'
    }
    
    if not snapshot_path.exists():
        result['status'] = 'failed'
        result['error'] = 'Snapshot not found'
        return result
    
    try:
        # Backup current database first
        if backup_current:
            backup_name = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = snapshot_dir / backup_name
            shutil.copy2(db_path, backup_path)
            result['backup_created'] = backup_name
            logger.info(f"Created pre-restore backup: {backup_name}")
        
        # Restore by copying snapshot over current database
        shutil.copy2(snapshot_path, db_path)
        
        result['status'] = 'completed'
        result['message'] = f"Database restored from {filename}"
        logger.info(f"Restored database from snapshot: {filename}")
        
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        logger.error(f"Restore failed: {e}", exc_info=True)
    
    return result


def cleanup_old_snapshots(keep_count: int = 10, keep_days: int = 30) -> Dict:
    """
    Remove old snapshots, keeping either the most recent N or those within X days.
    
    Args:
        keep_count: Minimum number of snapshots to keep
        keep_days: Keep all snapshots from the last N days
    
    Returns:
        Dict with cleanup results
    """
    snapshots = list_snapshots()
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'total_snapshots': len(snapshots),
        'deleted': [],
        'kept': 0
    }
    
    # Always keep the most recent `keep_count` snapshots
    kept_count = 0
    for snapshot in snapshots:
        snapshot_date = datetime.fromisoformat(snapshot['timestamp'])
        
        # Keep if within recent count OR within date range
        if kept_count < keep_count or snapshot_date > cutoff_date:
            kept_count += 1
            continue
        
        # Delete old snapshot
        if delete_snapshot(snapshot['filename']):
            result['deleted'].append(snapshot['filename'])
    
    result['kept'] = kept_count
    result['deleted_count'] = len(result['deleted'])
    
    if result['deleted']:
        logger.info(f"Cleaned up {result['deleted_count']} old snapshots")
    
    return result


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# CLI interface
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description='Database Snapshot CLI')
    parser.add_argument('--create', action='store_true', help='Create a new snapshot')
    parser.add_argument('--list', action='store_true', help='List all snapshots')
    parser.add_argument('--delete', help='Delete a snapshot by filename')
    parser.add_argument('--restore', help='Restore from a snapshot')
    parser.add_argument('--cleanup', action='store_true', help='Remove old snapshots')
    parser.add_argument('--note', help='Note for new snapshot')
    args = parser.parse_args()
    
    if args.create:
        result = create_snapshot(note=args.note)
        print(f"Snapshot: {result['status']}")
        if result['status'] == 'completed':
            print(f"  File: {result['filename']}")
            print(f"  Size: {result['size_human']}")
    
    elif args.list:
        snapshots = list_snapshots()
        print(f"Snapshots ({len(snapshots)}):")
        for s in snapshots:
            print(f"  {s['filename']} - {s.get('size_human', '?')} - {s['timestamp'][:19]}")
    
    elif args.delete:
        if delete_snapshot(args.delete):
            print(f"Deleted: {args.delete}")
        else:
            print(f"Not found: {args.delete}")
    
    elif args.restore:
        result = restore_snapshot(args.restore)
        print(f"Restore: {result['status']}")
        if result.get('error'):
            print(f"  Error: {result['error']}")
    
    elif args.cleanup:
        result = cleanup_old_snapshots()
        print(f"Cleanup: Deleted {result['deleted_count']} snapshots, kept {result['kept']}")
    
    else:
        parser.print_help()
