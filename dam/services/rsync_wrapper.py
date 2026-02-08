"""
Rsync Wrapper Service.

Provides a simplified interface for rsync operations with progress tracking
and error handling for backup operations.
"""

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


def check_rsync_available() -> bool:
    """Check if rsync is installed and accessible."""
    try:
        result = subprocess.run(['rsync', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def rsync_local(
    source: str,
    dest_dir: str,
    filename_prefix: str = "backup",
    delete_old: int = 0,
    progress_callback: Optional[Callable] = None
) -> Dict:
    """
    Copy file to local destination using rsync.
    
    Args:
        source: Source file path
        dest_dir: Destination directory
        filename_prefix: Prefix for backup filename
        delete_old: Number of old backups to keep (0 = keep all)
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with success status and details
    """
    result = {
        'success': False,
        'source': source,
        'destination': None,
        'timestamp': datetime.now().isoformat()
    }
    
    if not os.path.exists(source):
        result['error'] = f'Source not found: {source}'
        return result
    
    dest_path = Path(dest_dir)
    if not dest_path.exists():
        try:
            dest_path.mkdir(parents=True)
        except Exception as e:
            result['error'] = f'Cannot create destination: {e}'
            return result
    
    # Generate destination filename with timestamp
    source_name = Path(source).name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_file = dest_path / f"{filename_prefix}_{timestamp}_{source_name}"
    
    try:
        cmd = [
            'rsync',
            '-av',
            '--progress',
            source,
            str(dest_file)
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if proc.returncode == 0:
            result['success'] = True
            result['destination'] = str(dest_file)
            result['size_bytes'] = dest_file.stat().st_size if dest_file.exists() else 0
            
            # Cleanup old backups if requested
            if delete_old > 0:
                _cleanup_old_files(dest_path, filename_prefix, delete_old)
        else:
            result['error'] = proc.stderr or 'rsync failed'
    
    except subprocess.TimeoutExpired:
        result['error'] = 'rsync timed out (>1 hour)'
    except Exception as e:
        result['error'] = str(e)
    
    return result


def rsync_ssh(
    source: str,
    host: str,
    remote_path: str,
    key_path: Optional[str] = None,
    filename_prefix: str = "backup",
    port: int = 22,
    timeout: int = 300
) -> Dict:
    """
    Copy file to remote host via rsync over SSH.
    
    Args:
        source: Source file path
        host: SSH host (user@hostname)
        remote_path: Remote directory path
        key_path: Path to SSH key (optional)
        filename_prefix: Prefix for backup filename
        port: SSH port
        timeout: Timeout in seconds
    
    Returns:
        Dict with success status and details
    """
    result = {
        'success': False,
        'source': source,
        'host': host,
        'timestamp': datetime.now().isoformat()
    }
    
    if not os.path.exists(source):
        result['error'] = f'Source not found: {source}'
        return result
    
    # Generate remote filename with timestamp
    source_name = Path(source).name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    remote_file = f"{remote_path}/{filename_prefix}_{timestamp}_{source_name}"
    
    # Build rsync command
    ssh_cmd = f'ssh -p {port}'
    if key_path and os.path.exists(key_path):
        ssh_cmd += f' -i {key_path}'
    ssh_cmd += ' -o BatchMode=yes -o ConnectTimeout=10'
    
    cmd = [
        'rsync',
        '-avz',
        '--progress',
        '-e', ssh_cmd,
        source,
        f'{host}:{remote_file}'
    ]
    
    try:
        logger.info(f"Starting rsync to {host}:{remote_path}")
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if proc.returncode == 0:
            result['success'] = True
            result['destination'] = f'{host}:{remote_file}'
            
            # Parse transfer stats from output
            stats = _parse_rsync_stats(proc.stdout)
            result.update(stats)
            
            logger.info(f"rsync completed: {result['destination']}")
        else:
            result['error'] = proc.stderr or 'rsync failed'
            logger.error(f"rsync failed: {result['error']}")
    
    except subprocess.TimeoutExpired:
        result['error'] = f'rsync timed out (>{timeout}s)'
        logger.error(result['error'])
    except FileNotFoundError:
        result['error'] = 'rsync not installed'
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"rsync error: {e}")
    
    return result


def _parse_rsync_stats(output: str) -> Dict:
    """Parse rsync output for transfer statistics."""
    stats = {}
    
    # Try to find "sent X bytes" and "received Y bytes"
    sent_match = re.search(r'sent (\d[\d,]*) bytes', output)
    recv_match = re.search(r'received (\d[\d,]*) bytes', output)
    speed_match = re.search(r'(\d[\d,.]*) bytes/sec', output)
    
    if sent_match:
        stats['bytes_sent'] = int(sent_match.group(1).replace(',', ''))
    if recv_match:
        stats['bytes_received'] = int(recv_match.group(1).replace(',', ''))
    if speed_match:
        stats['speed_bytes_sec'] = float(speed_match.group(1).replace(',', ''))
    
    return stats


def _cleanup_old_files(directory: Path, prefix: str, keep_count: int):
    """Remove old backup files, keeping only the most recent N."""
    pattern = f"{prefix}_*.db"
    files = sorted(
        directory.glob(pattern),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    for old_file in files[keep_count:]:
        try:
            old_file.unlink()
            logger.debug(f"Removed old backup: {old_file.name}")
        except Exception as e:
            logger.warning(f"Failed to remove {old_file}: {e}")


def test_rsync_connection(host: str, remote_path: str, key_path: Optional[str] = None) -> Dict:
    """
    Test rsync connectivity to remote host.
    
    Args:
        host: SSH host (user@hostname)
        remote_path: Remote directory to test
        key_path: Path to SSH key
    
    Returns:
        Dict with success status
    """
    result = {
        'success': False,
        'host': host,
        'path': remote_path
    }
    
    # Build SSH command
    ssh_cmd = 'ssh -o BatchMode=yes -o ConnectTimeout=10'
    if key_path and os.path.exists(key_path):
        ssh_cmd += f' -i {key_path}'
    
    cmd = [
        'rsync',
        '--dry-run',
        '-av',
        '-e', ssh_cmd,
        '/dev/null',  # Empty source
        f'{host}:{remote_path}/'
    ]
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        # rsync --dry-run with /dev/null should succeed if connection works
        # Some error codes are acceptable (e.g., 23 = partial transfer)
        if proc.returncode in (0, 23):
            result['success'] = True
            result['message'] = 'Connection successful'
        else:
            result['error'] = proc.stderr or f'rsync failed with code {proc.returncode}'
    
    except subprocess.TimeoutExpired:
        result['error'] = 'Connection timed out'
    except FileNotFoundError:
        result['error'] = 'rsync not installed'
    except Exception as e:
        result['error'] = str(e)
    
    return result


# CLI interface
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description='Rsync Wrapper CLI')
    parser.add_argument('--check', action='store_true', help='Check if rsync is available')
    parser.add_argument('--test', nargs=2, metavar=('HOST', 'PATH'), help='Test connection')
    parser.add_argument('--local', nargs=2, metavar=('SOURCE', 'DEST'), help='Local backup')
    parser.add_argument('--ssh', nargs=3, metavar=('SOURCE', 'HOST', 'PATH'), help='SSH backup')
    parser.add_argument('--key', help='SSH key path')
    args = parser.parse_args()
    
    if args.check:
        if check_rsync_available():
            print("✓ rsync is available")
        else:
            print("✗ rsync not found")
    
    elif args.test:
        result = test_rsync_connection(args.test[0], args.test[1], args.key)
        if result['success']:
            print(f"✓ Connection to {args.test[0]} successful")
        else:
            print(f"✗ Connection failed: {result.get('error')}")
    
    elif args.local:
        result = rsync_local(args.local[0], args.local[1])
        if result['success']:
            print(f"✓ Backup created: {result['destination']}")
        else:
            print(f"✗ Backup failed: {result.get('error')}")
    
    elif args.ssh:
        result = rsync_ssh(args.ssh[0], args.ssh[1], args.ssh[2], key_path=args.key)
        if result['success']:
            print(f"✓ Backup created: {result['destination']}")
        else:
            print(f"✗ Backup failed: {result.get('error')}")
    
    else:
        parser.print_help()
