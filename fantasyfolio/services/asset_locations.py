"""
Asset Locations Service

Manages multiple asset storage locations (local, mounted volumes, remote SFTP).
Replaces the old single pdfRoot/3dRoot settings with flexible multi-location support.
"""

import os
import uuid
import sqlite3
import subprocess
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fantasyfolio.core.database import get_db

logger = logging.getLogger(__name__)


def get_all_locations() -> List[Dict[str, Any]]:
    """Get all asset locations."""
    return list_locations()


def list_locations(asset_type: Optional[str] = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
    """
    List all asset locations.
    
    Args:
        asset_type: Filter by 'documents' or 'models'
        enabled_only: Only return enabled locations
    
    Returns:
        List of location dictionaries
    """
    db = get_db()
    
    query = "SELECT * FROM asset_locations WHERE 1=1"
    params = []
    
    if asset_type:
        query += " AND asset_type = ?"
        params.append(asset_type)
    
    if enabled_only:
        query += " AND enabled = 1"
    
    query += " ORDER BY is_primary DESC, name ASC"
    
    with db.connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    
    return [dict(row) for row in rows]


def get_location_by_id(location_id: str) -> Optional[Dict[str, Any]]:
    """Get a single location by ID."""
    return get_location(location_id)


def get_location(location_id: str) -> Optional[Dict[str, Any]]:
    """Get a single location by ID."""
    db = get_db()
    
    with db.connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM asset_locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
    
    return dict(row) if row else None


def add_location(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new asset location with validation.
    
    Returns dict with success/error and location data.
    """
    # Validate required fields
    required = ['name', 'asset_type', 'location_type', 'path']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return {'success': False, 'error': f"Missing required fields: {', '.join(missing)}"}
    
    # Validate asset_type
    if data['asset_type'] not in ('documents', 'models'):
        return {'success': False, 'error': "asset_type must be 'documents' or 'models'"}
    
    # Validate location_type
    if data['location_type'] not in ('local', 'local_mount', 'remote_sftp'):
        return {'success': False, 'error': "location_type must be 'local', 'local_mount', or 'remote_sftp'"}
    
    try:
        location = create_location(data)
        return {'success': True, 'location': location}
    except Exception as e:
        logger.error(f"Error creating location: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def create_location(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new asset location.
    
    Required fields: name, asset_type, location_type, path
    Optional fields: ssh_host, ssh_key_path, ssh_user, ssh_port, mount_check_path, enabled, is_primary
    """
    db = get_db()
    location_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    with db.connection() as conn:
        # If this is marked as primary, unset other primaries of same type
        if data.get('is_primary'):
            conn.execute(
                "UPDATE asset_locations SET is_primary = 0 WHERE asset_type = ?",
                (data['asset_type'],)
            )
        
        conn.execute("""
            INSERT INTO asset_locations (
                id, name, asset_type, location_type, path,
                ssh_host, ssh_key_path, ssh_user, ssh_port,
                mount_check_path, enabled, is_primary,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            location_id,
            data['name'],
            data['asset_type'],
            data['location_type'],
            data['path'],
            data.get('ssh_host'),
            data.get('ssh_key_path'),
            data.get('ssh_user'),
            data.get('ssh_port', 22),
            data.get('mount_check_path'),
            1 if data.get('enabled', True) else 0,
            1 if data.get('is_primary', False) else 0,
            now,
            now
        ))
        conn.commit()
    
    return get_location(location_id)


def update_location(location_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing location. Returns dict with success status."""
    db = get_db()
    
    with db.connection() as conn:
        # Check if exists
        cursor = conn.execute("SELECT id FROM asset_locations WHERE id = ?", (location_id,))
        if not cursor.fetchone():
            return {'success': False, 'error': 'Location not found'}
        
        # Build update query dynamically
        allowed_fields = [
            'name', 'asset_type', 'location_type', 'path',
            'ssh_host', 'ssh_key_path', 'ssh_user', 'ssh_port',
            'mount_check_path', 'enabled', 'is_primary'
        ]
        
        updates = []
        params = []
        
        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field in ('enabled', 'is_primary'):
                    value = 1 if value else 0
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            location = get_location(location_id)
            return {'success': True, 'location': location, 'message': 'No changes'}
        
        # If setting as primary, unset other primaries first
        if data.get('is_primary'):
            cursor = conn.execute("SELECT asset_type FROM asset_locations WHERE id = ?", (location_id,))
            row = cursor.fetchone()
            if row:
                asset_type = data.get('asset_type', row[0])
                conn.execute(
                    "UPDATE asset_locations SET is_primary = 0 WHERE asset_type = ? AND id != ?",
                    (asset_type, location_id)
                )
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(location_id)
        
        query = f"UPDATE asset_locations SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        conn.commit()
    
    location = get_location(location_id)
    return {'success': True, 'location': location}


def delete_location(location_id: str) -> Dict[str, Any]:
    """Delete a location. Returns dict with success status."""
    db = get_db()
    
    with db.connection() as conn:
        # Check if exists
        cursor = conn.execute("SELECT name FROM asset_locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        if not row:
            return {'success': False, 'error': 'Location not found'}
        
        name = row[0]
        conn.execute("DELETE FROM asset_locations WHERE id = ?", (location_id,))
        conn.commit()
    
    return {'success': True, 'message': f"Deleted location '{name}'"}


def update_location_status(location_id: str, status: str, message: Optional[str] = None):
    """Update the status of a location (online/offline/error)."""
    db = get_db()
    
    with db.connection() as conn:
        conn.execute("""
            UPDATE asset_locations 
            SET last_status = ?, last_status_message = ?, updated_at = ?
            WHERE id = ?
        """, (status, message, datetime.now().isoformat(), location_id))
        conn.commit()


def update_indexed_timestamp(location_id: str):
    """Update the last_indexed_at timestamp."""
    db = get_db()
    
    with db.connection() as conn:
        conn.execute("""
            UPDATE asset_locations 
            SET last_indexed_at = ?, updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), datetime.now().isoformat(), location_id))
        conn.commit()


def test_location(location: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test if a location is accessible.
    
    Returns:
        {'success': bool, 'message': str, 'online': bool}
    """
    result = check_location_status(location)
    return {
        'success': result['online'],
        'online': result['online'],
        'message': result['message']
    }


def remount_location(location: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to remount a network volume.
    
    For macOS SMB/AFP mounts, tries to remount using the mount path.
    
    Returns:
        {'success': bool, 'message': str}
    """
    import subprocess
    
    path = location['path']
    
    # Check if already mounted and accessible
    if os.path.isdir(path):
        try:
            contents = os.listdir(path)
            if contents:
                return {'success': True, 'message': 'Volume already mounted and accessible'}
        except PermissionError:
            pass  # Continue to remount attempt
    
    # Try to trigger macOS automount by accessing the path
    # This works for paths like /Volumes/ShareName that are configured in Finder
    try:
        # Touch the parent Volumes directory to trigger automount
        volumes_dir = os.path.dirname(path)
        if os.path.isdir(volumes_dir):
            os.listdir(volumes_dir)
        
        # Give it a moment to mount
        import time
        time.sleep(1)
        
        # Check if mount succeeded
        if os.path.isdir(path):
            contents = os.listdir(path)
            if contents:
                return {'success': True, 'message': 'Volume remounted successfully'}
            else:
                return {'success': False, 'message': 'Mount point exists but appears empty'}
        else:
            return {'success': False, 'message': 'Could not remount volume. Check network connection or mount manually via Finder.'}
    
    except Exception as e:
        return {'success': False, 'message': f'Remount error: {str(e)}'}


def check_location_status(location: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if a location is accessible.
    
    Returns:
        {'online': bool, 'message': str}
    """
    location_type = location['location_type']
    path = location['path']
    
    if location_type == 'local':
        # Simple path existence check
        if os.path.isdir(path):
            return {'online': True, 'message': 'Directory accessible'}
        else:
            return {'online': False, 'message': f'Directory not found: {path}'}
    
    elif location_type == 'local_mount':
        # Check if mounted
        if not os.path.isdir(path):
            return {'online': False, 'message': f'Mount point not found: {path}'}
        
        # Check mount marker if configured
        mount_check = location.get('mount_check_path')
        if mount_check:
            check_path = os.path.join(path, mount_check)
            if not os.path.exists(check_path):
                return {'online': False, 'message': f'Mount marker not found: {mount_check}'}
        
        # Check if actually mounted (not just empty dir)
        try:
            contents = os.listdir(path)
            if not contents:
                return {'online': False, 'message': 'Mount point appears empty (volume may be offline)'}
            return {'online': True, 'message': 'Volume mounted and accessible'}
        except PermissionError:
            return {'online': False, 'message': 'Permission denied accessing mount'}
        except OSError as e:
            return {'online': False, 'message': f'Error accessing mount: {e}'}
    
    elif location_type == 'remote_sftp':
        # Test SSH connection
        ssh_host = location.get('ssh_host')
        if not ssh_host:
            return {'online': False, 'message': 'No SSH host configured'}
        
        # Build SSH test command
        ssh_cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5']
        
        if location.get('ssh_key_path'):
            ssh_cmd.extend(['-i', location['ssh_key_path']])
        
        if location.get('ssh_port') and location['ssh_port'] != 22:
            ssh_cmd.extend(['-p', str(location['ssh_port'])])
        
        # Build host string
        host_str = ssh_host
        if location.get('ssh_user'):
            host_str = f"{location['ssh_user']}@{ssh_host}"
        
        ssh_cmd.append(host_str)
        ssh_cmd.extend(['test', '-d', path, '&&', 'echo', 'OK'])
        
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and 'OK' in result.stdout:
                return {'online': True, 'message': 'Remote path accessible via SSH'}
            else:
                return {'online': False, 'message': f'Remote path not accessible: {result.stderr.strip() or "Unknown error"}'}
        except subprocess.TimeoutExpired:
            return {'online': False, 'message': 'SSH connection timed out'}
        except Exception as e:
            return {'online': False, 'message': f'SSH error: {e}'}
    
    return {'online': False, 'message': f'Unknown location type: {location_type}'}


def get_primary_location(asset_type: str) -> Optional[Dict[str, Any]]:
    """Get the primary location for an asset type."""
    db = get_db()
    
    with db.connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM asset_locations 
            WHERE asset_type = ? AND is_primary = 1 AND enabled = 1
            LIMIT 1
        """, (asset_type,))
        row = cursor.fetchone()
    
    return dict(row) if row else None


def get_enabled_paths(asset_type: str) -> List[str]:
    """
    Get all enabled local/mounted paths for an asset type.
    Used by indexer to know what directories to scan.
    
    Note: Remote SFTP locations need special handling and are not returned here.
    """
    locations = list_locations(asset_type=asset_type, enabled_only=True)
    
    paths = []
    for loc in locations:
        if loc['location_type'] in ('local', 'local_mount'):
            paths.append(loc['path'])
    
    return paths
