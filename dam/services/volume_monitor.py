"""
Volume Availability Monitor Service.

Checks if configured asset volumes (PDFs, 3D Models) are mounted and accessible.
Prevents indexing operations when storage is unavailable.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


# Default volume configuration (can be overridden by backup_config.yaml)
DEFAULT_VOLUMES = {
    'pdfs': '/Volumes/d-mini/DROBO/D/PDF/Gathered',
    'models': '/Volumes/3D-Files/3D-Models',
}


def get_configured_volumes() -> Dict[str, str]:
    """
    Get configured volume paths.
    
    Priority:
    1. backup_config.yaml (if exists)
    2. Environment variables (DAM_PDF_ROOT, DAM_3D_ROOT)
    3. Default volumes
    
    Returns:
        Dict mapping volume name to path
    """
    volumes = {}
    
    # Try to load from backup_config.yaml
    try:
        from dam.services.backup_config import load_backup_config
        config = load_backup_config()
        if config and 'protection' in config:
            vol_config = config.get('protection', {}).get('volume_check', {}).get('volumes', {})
            if vol_config:
                return vol_config
    except (ImportError, FileNotFoundError):
        pass  # backup_config not yet implemented or file doesn't exist
    
    # Fall back to environment variables
    pdf_root = os.environ.get('DAM_PDF_ROOT', '')
    models_root = os.environ.get('DAM_3D_ROOT', '')
    
    if pdf_root:
        volumes['pdfs'] = pdf_root
    else:
        volumes['pdfs'] = DEFAULT_VOLUMES['pdfs']
    
    if models_root:
        volumes['models'] = models_root
    else:
        volumes['models'] = DEFAULT_VOLUMES['models']
    
    return volumes


def check_volume_available(volume_path: str) -> Dict:
    """
    Check if a volume/path is mounted and accessible.
    
    Performs checks:
    1. Path exists (volume is mounted)
    2. Path is readable (can list directory)
    3. No permission issues
    
    Args:
        volume_path: Path to check (e.g., /Volumes/NAS/data)
    
    Returns:
        Dict with:
            - path: The checked path
            - available: True if accessible, False otherwise
            - reason: Explanation if unavailable (None if available)
            - last_checked: ISO timestamp of check
    """
    result = {
        'path': volume_path,
        'available': False,
        'reason': None,
        'last_checked': datetime.now().isoformat()
    }
    
    # Normalize path
    path = Path(volume_path)
    
    # Check 1: Does the path exist?
    if not path.exists():
        # Determine more specific reason
        if volume_path.startswith('/Volumes/'):
            volume_name = volume_path.split('/')[2] if len(volume_path.split('/')) > 2 else 'Unknown'
            result['reason'] = f"Volume '{volume_name}' is not mounted"
        else:
            result['reason'] = "Path does not exist"
        logger.warning(f"Volume check failed for {volume_path}: {result['reason']}")
        return result
    
    # Check 2: Is it a directory?
    if not path.is_dir():
        result['reason'] = "Path exists but is not a directory"
        logger.warning(f"Volume check failed for {volume_path}: {result['reason']}")
        return result
    
    # Check 3: Can we read it?
    try:
        # Try to list directory contents (basic read test)
        list(path.iterdir())
        result['available'] = True
        logger.debug(f"Volume check passed for {volume_path}")
    except PermissionError:
        result['reason'] = "Permission denied - cannot read directory"
        logger.warning(f"Volume check failed for {volume_path}: {result['reason']}")
    except OSError as e:
        # Catch various OS errors (network timeout, I/O error, etc.)
        result['reason'] = f"Access error: {e.strerror}"
        logger.warning(f"Volume check failed for {volume_path}: {result['reason']}")
    except Exception as e:
        result['reason'] = f"Unexpected error: {str(e)}"
        logger.error(f"Volume check failed for {volume_path}: {result['reason']}", exc_info=True)
    
    return result


def get_all_volume_status() -> Dict:
    """
    Check availability of all configured volumes.
    
    Returns:
        Dict with:
            - volumes: Dict mapping volume name to status
            - all_available: True if all volumes are available
            - unavailable: List of unavailable volume names
            - checked_at: ISO timestamp
    """
    volumes = get_configured_volumes()
    
    result = {
        'volumes': {},
        'all_available': True,
        'unavailable': [],
        'checked_at': datetime.now().isoformat()
    }
    
    for name, path in volumes.items():
        status = check_volume_available(path)
        result['volumes'][name] = status
        
        if not status['available']:
            result['all_available'] = False
            result['unavailable'].append(name)
    
    if result['unavailable']:
        logger.info(f"Volume status check: {len(result['unavailable'])} unavailable: {result['unavailable']}")
    else:
        logger.debug("Volume status check: All volumes available")
    
    return result


def get_volume_for_path(file_path: str) -> Optional[str]:
    """
    Determine which configured volume a file path belongs to.
    
    Args:
        file_path: Full path to a file
    
    Returns:
        Volume name (e.g., 'pdfs', 'models') or None if not in any configured volume
    """
    file_path = str(file_path)
    volumes = get_configured_volumes()
    
    for name, volume_path in volumes.items():
        # Normalize paths for comparison
        volume_path = str(Path(volume_path).resolve())
        
        # Check if file_path starts with volume_path
        if file_path.startswith(volume_path):
            return name
    
    # Check if it's under any /Volumes/ path (SMB mount)
    if file_path.startswith('/Volumes/'):
        parts = file_path.split('/')
        if len(parts) >= 3:
            # Return the volume mount point
            return parts[2]
    
    return None


def check_volume_for_path(file_path: str) -> Dict:
    """
    Check if the volume containing a file path is available.
    
    Args:
        file_path: Full path to a file
    
    Returns:
        Dict with:
            - file_path: The input file path
            - volume_name: Name of the volume (or None)
            - volume_path: Path to the volume root
            - available: True if volume is accessible
            - reason: Explanation if unavailable
    """
    volume_name = get_volume_for_path(file_path)
    
    result = {
        'file_path': file_path,
        'volume_name': volume_name,
        'volume_path': None,
        'available': False,
        'reason': None
    }
    
    if volume_name is None:
        # File is not in a configured volume - assume available (local path)
        result['available'] = True
        result['reason'] = "File not in monitored volume (assuming local)"
        return result
    
    # Get volume path
    volumes = get_configured_volumes()
    if volume_name in volumes:
        volume_path = volumes[volume_name]
    else:
        # Reconstruct volume path from file_path (for /Volumes/ paths)
        parts = file_path.split('/')
        volume_path = '/'.join(parts[:3])  # /Volumes/VolumeName
    
    result['volume_path'] = volume_path
    
    # Check volume availability
    status = check_volume_available(volume_path)
    result['available'] = status['available']
    result['reason'] = status['reason']
    
    return result


def get_required_volumes_for_index(index_type: str) -> List[str]:
    """
    Get list of volume names required for a specific index operation.
    
    Args:
        index_type: Type of index ('pdfs', 'models', 'all')
    
    Returns:
        List of volume names that must be available
    """
    if index_type == 'pdfs':
        return ['pdfs']
    elif index_type == 'models':
        return ['models']
    elif index_type == 'all':
        return ['pdfs', 'models']
    else:
        # Unknown type - require all volumes
        return list(get_configured_volumes().keys())


def check_volumes_for_index(index_type: str) -> Dict:
    """
    Check if all required volumes are available for an index operation.
    
    Args:
        index_type: Type of index ('pdfs', 'models', 'all')
    
    Returns:
        Dict with:
            - can_proceed: True if all required volumes are available
            - required_volumes: List of required volume names
            - unavailable_volumes: List of unavailable volume names
            - volume_status: Full status of each required volume
            - message: Human-readable status message
    """
    required = get_required_volumes_for_index(index_type)
    all_status = get_all_volume_status()
    
    result = {
        'can_proceed': True,
        'required_volumes': required,
        'unavailable_volumes': [],
        'volume_status': {},
        'message': ''
    }
    
    for vol_name in required:
        if vol_name in all_status['volumes']:
            status = all_status['volumes'][vol_name]
            result['volume_status'][vol_name] = status
            
            if not status['available']:
                result['can_proceed'] = False
                result['unavailable_volumes'].append(vol_name)
    
    # Generate message
    if result['can_proceed']:
        result['message'] = "All required volumes are available"
    else:
        unavailable_str = ', '.join(result['unavailable_volumes'])
        result['message'] = f"Volume(s) unavailable: {unavailable_str}. Indexing suspended."
    
    return result
