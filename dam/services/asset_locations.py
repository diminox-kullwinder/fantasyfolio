"""
Asset Locations Service.

Manages multiple asset root directories with support for local,
mounted, and remote (SSH/SFTP) locations.
"""

import os
import json
import logging
import uuid
import subprocess
from typing import Dict, List, Optional
from pathlib import Path

from dam.core.database import get_setting, set_setting

logger = logging.getLogger(__name__)

# Asset types
TYPE_DOCUMENTS = 'documents'
TYPE_MODELS = 'models'

# Location types
LOC_LOCAL = 'local'           # Local filesystem path
LOC_MOUNT = 'mount'           # Mounted volume (SMB/NFS)
LOC_SSH = 'ssh'               # Remote via SSH
LOC_SFTP = 'sftp'             # Remote via SFTP


def get_all_locations() -> List[Dict]:
    """
    Get all configured asset locations.
    
    Returns:
        List of location dicts
    """
    try:
        locations_json = get_setting('asset_locations')
        if locations_json:
            locations = json.loads(locations_json)
            return sorted(locations, key=lambda x: (x.get('asset_type', ''), x.get('name', '')))
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Return default/migrated locations if none configured
    return _get_legacy_locations()


def _get_legacy_locations() -> List[Dict]:
    """
    Migrate legacy pdf_root and 3d_root settings to new format.
    """
    locations = []
    
    # Check for legacy PDF root
    pdf_root = get_setting('pdf_root')
    if pdf_root:
        locations.append({
            'id': 'legacy-pdf',
            'name': 'Documents',
            'asset_type': TYPE_DOCUMENTS,
            'location_type': LOC_LOCAL,
            'path': pdf_root,
            'ssh_host': None,
            'ssh_key': None,
            'enabled': True
        })
    
    # Check for legacy 3D root
    model_root = get_setting('3d_root')
    if model_root:
        locations.append({
            'id': 'legacy-3d',
            'name': '3D Models',
            'asset_type': TYPE_MODELS,
            'location_type': LOC_LOCAL,
            'path': model_root,
            'ssh_host': None,
            'ssh_key': None,
            'enabled': True
        })
    
    return locations


def save_all_locations(locations: List[Dict]) -> bool:
    """Save all locations to settings."""
    try:
        set_setting('asset_locations', json.dumps(locations))
        
        # Also update legacy settings for backward compatibility
        _update_legacy_settings(locations)
        
        return True
    except Exception as e:
        logger.error(f"Failed to save locations: {e}")
        return False


def _update_legacy_settings(locations: List[Dict]):
    """
    Update legacy pdf_root and 3d_root settings for backward compatibility.
    Uses the first enabled location of each type.
    """
    pdf_root = None
    model_root = None
    
    for loc in locations:
        if not loc.get('enabled'):
            continue
        
        if loc.get('asset_type') == TYPE_DOCUMENTS and not pdf_root:
            pdf_root = _get_effective_path(loc)
        elif loc.get('asset_type') == TYPE_MODELS and not model_root:
            model_root = _get_effective_path(loc)
    
    if pdf_root:
        set_setting('pdf_root', pdf_root)
    if model_root:
        set_setting('3d_root', model_root)


def _get_effective_path(location: Dict) -> str:
    """Get the effective local path for a location (for indexing)."""
    loc_type = location.get('location_type', LOC_LOCAL)
    
    if loc_type in (LOC_LOCAL, LOC_MOUNT):
        return location.get('path', '')
    else:
        # Remote locations would need mounting or special handling
        # For now, return the path as-is
        return location.get('path', '')


def get_location_by_id(location_id: str) -> Optional[Dict]:
    """Get a single location by ID."""
    for loc in get_all_locations():
        if loc.get('id') == location_id:
            return loc
    return None


def add_location(location_data: Dict) -> Dict:
    """
    Add a new asset location.
    
    Args:
        location_data: Location configuration
    
    Returns:
        Dict with success status and created location
    """
    result = {'success': False}
    
    # Validate required fields
    if not location_data.get('name'):
        result['error'] = 'Name is required'
        return result
    
    if not location_data.get('path'):
        result['error'] = 'Path is required'
        return result
    
    if location_data.get('asset_type') not in (TYPE_DOCUMENTS, TYPE_MODELS):
        result['error'] = 'Invalid asset type'
        return result
    
    if location_data.get('location_type') not in (LOC_LOCAL, LOC_MOUNT, LOC_SSH, LOC_SFTP):
        result['error'] = 'Invalid location type'
        return result
    
    # Generate ID
    location_id = location_data.get('id') or str(uuid.uuid4())[:8]
    
    # Build location object
    location = {
        'id': location_id,
        'name': location_data['name'].strip(),
        'asset_type': location_data['asset_type'],
        'location_type': location_data['location_type'],
        'path': location_data['path'].strip(),
        'ssh_host': location_data.get('ssh_host', '').strip() or None,
        'ssh_key': location_data.get('ssh_key', '').strip() or None,
        'enabled': location_data.get('enabled', True)
    }
    
    # Add to locations list
    locations = get_all_locations()
    locations.append(location)
    
    if save_all_locations(locations):
        result['success'] = True
        result['location'] = location
        logger.info(f"Added asset location: {location['name']}")
    else:
        result['error'] = 'Failed to save location'
    
    return result


def update_location(location_id: str, updates: Dict) -> Dict:
    """
    Update an existing location.
    
    Args:
        location_id: ID of location to update
        updates: Fields to update
    
    Returns:
        Dict with success status
    """
    result = {'success': False}
    
    locations = get_all_locations()
    location_index = None
    location = None
    
    for i, loc in enumerate(locations):
        if loc.get('id') == location_id:
            location_index = i
            location = loc
            break
    
    if location is None:
        result['error'] = 'Location not found'
        return result
    
    # Apply updates
    for key, value in updates.items():
        if key != 'id':  # Don't allow ID changes
            location[key] = value
    
    locations[location_index] = location
    
    if save_all_locations(locations):
        result['success'] = True
        result['location'] = location
        logger.info(f"Updated asset location: {location['name']}")
    else:
        result['error'] = 'Failed to save location'
    
    return result


def delete_location(location_id: str) -> Dict:
    """Delete a location by ID."""
    result = {'success': False}
    
    locations = get_all_locations()
    new_locations = [loc for loc in locations if loc.get('id') != location_id]
    
    if len(new_locations) == len(locations):
        result['error'] = 'Location not found'
        return result
    
    if save_all_locations(new_locations):
        result['success'] = True
        logger.info(f"Deleted asset location: {location_id}")
    else:
        result['error'] = 'Failed to save'
    
    return result


def test_location(location: Dict) -> Dict:
    """
    Test if a location is accessible.
    
    Returns:
        Dict with success status and details
    """
    result = {
        'success': False,
        'location_id': location.get('id'),
        'name': location.get('name')
    }
    
    loc_type = location.get('location_type', LOC_LOCAL)
    path = location.get('path', '')
    
    if loc_type in (LOC_LOCAL, LOC_MOUNT):
        # Test local/mounted path
        if os.path.exists(path):
            if os.path.isdir(path):
                if os.access(path, os.R_OK):
                    result['success'] = True
                    result['message'] = 'Directory accessible'
                    
                    # Count files
                    try:
                        file_count = sum(1 for _ in Path(path).rglob('*') if _.is_file())
                        result['file_count'] = file_count
                    except:
                        pass
                else:
                    result['error'] = 'Directory not readable'
            else:
                result['error'] = 'Path is not a directory'
        else:
            result['error'] = 'Path does not exist'
    
    elif loc_type in (LOC_SSH, LOC_SFTP):
        # Test SSH/SFTP connection
        ssh_host = location.get('ssh_host')
        ssh_key = location.get('ssh_key')
        
        if not ssh_host:
            result['error'] = 'SSH host not configured'
            return result
        
        from dam.services.ssh_keys import test_connection
        conn_result = test_connection(ssh_host, ssh_key)
        
        if conn_result.get('success'):
            result['success'] = True
            result['message'] = 'Connection successful'
        else:
            result['error'] = conn_result.get('error', 'Connection failed')
    
    return result


def get_locations_by_type(asset_type: str) -> List[Dict]:
    """Get all enabled locations for a specific asset type."""
    return [
        loc for loc in get_all_locations()
        if loc.get('asset_type') == asset_type and loc.get('enabled')
    ]
