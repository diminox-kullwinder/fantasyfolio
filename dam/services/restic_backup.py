"""
Restic Backup Service.

Provides deduplicated backups using Restic with support for
local and SFTP repositories. Includes one-click restore.
"""

import os
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def check_restic_installed() -> Dict:
    """Check if restic is installed and return version info."""
    try:
        result = subprocess.run(
            ['restic', 'version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return {
                'installed': True,
                'version': result.stdout.strip()
            }
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"Error checking restic: {e}")
    
    return {
        'installed': False,
        'error': 'Restic not found. Install with: brew install restic (macOS), apt install restic (Linux), or choco install restic (Windows)'
    }


def init_repo(repo_path: str, password: str) -> Dict:
    """
    Initialize a new Restic repository.
    
    Args:
        repo_path: Local path or sftp:user@host:/path
        password: Repository encryption password
    
    Returns:
        Dict with success status
    """
    result = {'success': False}
    
    if not password:
        result['error'] = 'Repository password is required'
        return result
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        proc = subprocess.run(
            ['restic', 'init', '--repo', repo_path],
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        
        if proc.returncode == 0:
            result['success'] = True
            result['message'] = 'Repository initialized'
            logger.info(f"Initialized restic repo: {repo_path}")
        else:
            # Check if already initialized
            if 'already initialized' in proc.stderr.lower() or 'config file already exists' in proc.stderr.lower():
                result['success'] = True
                result['message'] = 'Repository already initialized'
            else:
                result['error'] = proc.stderr.strip() or 'Failed to initialize repository'
                
    except subprocess.TimeoutExpired:
        result['error'] = 'Repository initialization timed out'
    except Exception as e:
        result['error'] = f'Error initializing repository: {str(e)}'
        logger.error(f"Restic init error: {e}", exc_info=True)
    
    return result


def run_backup(repo_path: str, password: str, source_path: str, tags: List[str] = None) -> Dict:
    """
    Run a backup to the Restic repository.
    
    Args:
        repo_path: Repository path
        password: Repository password
        source_path: Path to file/directory to backup
        tags: Optional list of tags to apply
    
    Returns:
        Dict with success status and snapshot info
    """
    result = {'success': False}
    
    if not os.path.exists(source_path):
        result['error'] = f'Source path does not exist: {source_path}'
        return result
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        cmd = ['restic', 'backup', '--repo', repo_path, '--json', source_path]
        
        if tags:
            for tag in tags:
                cmd.extend(['--tag', tag])
        
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout for large DBs
            env=env
        )
        
        if proc.returncode == 0:
            result['success'] = True
            result['message'] = 'Backup completed'
            
            # Parse JSON output for snapshot info
            for line in proc.stdout.strip().split('\n'):
                try:
                    data = json.loads(line)
                    if data.get('message_type') == 'summary':
                        result['snapshot_id'] = data.get('snapshot_id')
                        result['files_new'] = data.get('files_new', 0)
                        result['files_changed'] = data.get('files_changed', 0)
                        result['data_added'] = data.get('data_added', 0)
                        result['total_bytes'] = data.get('total_bytes_processed', 0)
                except json.JSONDecodeError:
                    pass
            
            logger.info(f"Restic backup completed: {result.get('snapshot_id', 'unknown')}")
        else:
            result['error'] = proc.stderr.strip() or 'Backup failed'
            logger.error(f"Restic backup failed: {proc.stderr}")
            
    except subprocess.TimeoutExpired:
        result['error'] = 'Backup timed out'
    except Exception as e:
        result['error'] = f'Backup error: {str(e)}'
        logger.error(f"Restic backup error: {e}", exc_info=True)
    
    return result


def list_snapshots(repo_path: str, password: str) -> Dict:
    """
    List all snapshots in the repository.
    
    Returns:
        Dict with list of snapshots
    """
    result = {'success': False, 'snapshots': []}
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        proc = subprocess.run(
            ['restic', 'snapshots', '--repo', repo_path, '--json'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if proc.returncode == 0:
            snapshots = json.loads(proc.stdout) if proc.stdout.strip() else []
            
            # Format snapshots for UI
            formatted = []
            for snap in snapshots:
                formatted.append({
                    'id': snap.get('id', '')[:8],  # Short ID
                    'full_id': snap.get('id', ''),
                    'time': snap.get('time', ''),
                    'hostname': snap.get('hostname', ''),
                    'tags': snap.get('tags', []),
                    'paths': snap.get('paths', [])
                })
            
            # Sort by time, newest first
            formatted.sort(key=lambda x: x['time'], reverse=True)
            
            result['success'] = True
            result['snapshots'] = formatted
        else:
            result['error'] = proc.stderr.strip() or 'Failed to list snapshots'
            
    except json.JSONDecodeError as e:
        result['error'] = f'Invalid response from restic: {e}'
    except subprocess.TimeoutExpired:
        result['error'] = 'List snapshots timed out'
    except Exception as e:
        result['error'] = f'Error listing snapshots: {str(e)}'
        logger.error(f"Restic list error: {e}", exc_info=True)
    
    return result


def restore_snapshot(repo_path: str, password: str, snapshot_id: str, target_path: str) -> Dict:
    """
    Restore a snapshot to the target path.
    
    Args:
        repo_path: Repository path
        password: Repository password
        snapshot_id: Snapshot ID to restore (short or full)
        target_path: Directory to restore into
    
    Returns:
        Dict with success status and restored path
    """
    result = {'success': False}
    
    # Ensure target directory exists
    os.makedirs(target_path, exist_ok=True)
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        proc = subprocess.run(
            ['restic', 'restore', snapshot_id, '--repo', repo_path, '--target', target_path],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        
        if proc.returncode == 0:
            result['success'] = True
            result['target_path'] = target_path
            result['message'] = f'Restored snapshot {snapshot_id[:8]} to {target_path}'
            logger.info(f"Restic restore completed: {snapshot_id[:8]} -> {target_path}")
        else:
            result['error'] = proc.stderr.strip() or 'Restore failed'
            logger.error(f"Restic restore failed: {proc.stderr}")
            
    except subprocess.TimeoutExpired:
        result['error'] = 'Restore timed out'
    except Exception as e:
        result['error'] = f'Restore error: {str(e)}'
        logger.error(f"Restic restore error: {e}", exc_info=True)
    
    return result


def prune_snapshots(repo_path: str, password: str, keep_last: int = 7) -> Dict:
    """
    Remove old snapshots, keeping only the specified number.
    
    Args:
        repo_path: Repository path
        password: Repository password
        keep_last: Number of snapshots to keep
    
    Returns:
        Dict with success status
    """
    result = {'success': False}
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        # First, mark old snapshots for removal
        proc = subprocess.run(
            ['restic', 'forget', '--repo', repo_path, '--keep-last', str(keep_last), '--prune'],
            capture_output=True,
            text=True,
            timeout=600,  # Pruning can take a while
            env=env
        )
        
        if proc.returncode == 0:
            result['success'] = True
            result['message'] = f'Pruned repository, keeping last {keep_last} snapshots'
            logger.info(f"Restic prune completed for {repo_path}")
        else:
            result['error'] = proc.stderr.strip() or 'Prune failed'
            
    except subprocess.TimeoutExpired:
        result['error'] = 'Prune timed out'
    except Exception as e:
        result['error'] = f'Prune error: {str(e)}'
        logger.error(f"Restic prune error: {e}", exc_info=True)
    
    return result


def get_repo_stats(repo_path: str, password: str) -> Dict:
    """
    Get repository statistics (size, dedup ratio, etc).
    
    Returns:
        Dict with repo stats
    """
    result = {'success': False}
    
    try:
        env = os.environ.copy()
        env['RESTIC_PASSWORD'] = password
        
        proc = subprocess.run(
            ['restic', 'stats', '--repo', repo_path, '--json'],
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        
        if proc.returncode == 0:
            stats = json.loads(proc.stdout) if proc.stdout.strip() else {}
            result['success'] = True
            result['total_size'] = stats.get('total_size', 0)
            result['total_file_count'] = stats.get('total_file_count', 0)
            
            # Human readable size
            size_bytes = result['total_size']
            if size_bytes > 1024**3:
                result['total_size_human'] = f"{size_bytes / 1024**3:.2f} GB"
            elif size_bytes > 1024**2:
                result['total_size_human'] = f"{size_bytes / 1024**2:.2f} MB"
            else:
                result['total_size_human'] = f"{size_bytes / 1024:.2f} KB"
        else:
            result['error'] = proc.stderr.strip() or 'Failed to get stats'
            
    except json.JSONDecodeError:
        result['error'] = 'Invalid stats response'
    except subprocess.TimeoutExpired:
        result['error'] = 'Stats request timed out'
    except Exception as e:
        result['error'] = f'Stats error: {str(e)}'
    
    return result


def restore_database(repo_path: str, password: str, snapshot_id: str, db_path: str) -> Dict:
    """
    One-click database restore from Restic snapshot.
    
    1. Creates safety backup of current database
    2. Restores snapshot to temp location
    3. Finds the database file in restored data
    4. Replaces current database
    
    Args:
        repo_path: Restic repository path
        password: Repository password
        snapshot_id: Snapshot to restore
        db_path: Path to current database to replace
    
    Returns:
        Dict with success status and backup path
    """
    result = {'success': False}
    
    from dam.services.snapshot import create_snapshot
    import shutil
    import tempfile
    
    # Step 1: Safety backup of current database
    logger.info("Creating safety backup before restore...")
    safety_backup = create_snapshot(reason='pre_restore_safety')
    if not safety_backup.get('success'):
        result['error'] = f"Failed to create safety backup: {safety_backup.get('error')}"
        return result
    
    result['safety_backup'] = safety_backup.get('path')
    
    # Step 2: Restore to temp location
    temp_dir = tempfile.mkdtemp(prefix='dam_restore_')
    logger.info(f"Restoring snapshot {snapshot_id[:8]} to {temp_dir}...")
    
    restore_result = restore_snapshot(repo_path, password, snapshot_id, temp_dir)
    if not restore_result.get('success'):
        result['error'] = f"Restore failed: {restore_result.get('error')}"
        return result
    
    # Step 3: Find the database file in restored data
    # Restic preserves directory structure, so look for .db files
    restored_db = None
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            if f.endswith('.db'):
                restored_db = os.path.join(root, f)
                break
        if restored_db:
            break
    
    if not restored_db:
        result['error'] = 'No database file found in restored snapshot'
        shutil.rmtree(temp_dir, ignore_errors=True)
        return result
    
    # Step 4: Replace current database
    logger.info(f"Replacing database with restored version...")
    try:
        # Backup current db one more time (in case snapshot failed)
        if os.path.exists(db_path):
            backup_path = db_path + '.pre_restore'
            shutil.copy2(db_path, backup_path)
            result['replaced_backup'] = backup_path
        
        # Copy restored db to target location
        shutil.copy2(restored_db, db_path)
        
        result['success'] = True
        result['message'] = f'Database restored from snapshot {snapshot_id[:8]}'
        result['restored_from'] = restored_db
        logger.info(f"Database restore completed: {snapshot_id[:8]}")
        
    except Exception as e:
        result['error'] = f'Failed to replace database: {str(e)}'
        logger.error(f"Database replace error: {e}", exc_info=True)
    finally:
        # Cleanup temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return result
