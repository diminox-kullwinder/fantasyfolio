"""
Indexer API Blueprint.

Handles triggering and monitoring indexing operations.
"""

import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

from dam.config import get_config

logger = logging.getLogger(__name__)
indexer_bp = Blueprint('indexer', __name__)


@indexer_bp.route('/index', methods=['POST'])
def api_trigger_index():
    """
    Trigger indexing for a content type (non-blocking).
    
    Request body:
    - type: Content type (pdf, 3d, smb)
    - path: Path to index
    - background: Run in background (default: true)
    
    Returns:
    - status: "started" if indexing began, "suspended" if volume unavailable
    - message: Human-readable status message
    """
    from dam.services.volume_monitor import check_volumes_for_index, check_volume_available
    
    config = get_config()
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    content_type = data.get('type')
    path = data.get('path')
    background = data.get('background', True)
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    # === VOLUME AVAILABILITY CHECK ===
    # Map content type to volume check type
    volume_check_type = {
        'pdf': 'pdfs',
        '3d': 'models',
        'smb': 'models'  # SMB typically used for 3D models
    }.get(content_type, 'all')
    
    # Check volume availability BEFORE validating paths
    volume_check = check_volumes_for_index(volume_check_type)
    
    if not volume_check['can_proceed']:
        # Volume unavailable - return suspended status (200 OK, not error)
        logger.info(f"Indexing suspended: {volume_check['message']}")
        return jsonify({
            'status': 'suspended',
            'message': volume_check['message'],
            'unavailable_volumes': volume_check['unavailable_volumes'],
            'volume_status': volume_check['volume_status']
        }), 200  # 200 OK - this is expected behavior, not an error
    
    # Volume available - proceed with path validation
    paths = path.split(',') if ',' in path else [path]
    for p in paths:
        p_stripped = p.strip()
        if not os.path.isdir(p_stripped):
            # Path doesn't exist - check if it's a volume issue
            vol_status = check_volume_available(p_stripped)
            if not vol_status['available']:
                return jsonify({
                    'status': 'suspended',
                    'message': f"Volume unavailable: {vol_status['reason']}",
                    'path': p_stripped
                }), 200
            else:
                return jsonify({'error': f'Path not found: {p}'}), 400
    
    # === AUTO-SNAPSHOT BEFORE INDEXING ===
    # Create a snapshot before potentially modifying the database
    try:
        from dam.core.database import get_setting
        auto_snapshot = get_setting('auto_snapshot_before_index')
        if auto_snapshot != 'false':  # Default to enabled
            from dam.services.snapshot import create_snapshot, list_snapshots
            
            # Only create if no snapshot in last hour (avoid spam)
            snapshots = list_snapshots()
            recent_snapshot = False
            if snapshots:
                from datetime import datetime, timedelta
                latest = datetime.fromisoformat(snapshots[0]['timestamp'])
                if datetime.now() - latest < timedelta(hours=1):
                    recent_snapshot = True
            
            if not recent_snapshot:
                logger.info("Creating auto-snapshot before indexing")
                snapshot_result = create_snapshot(note=f"Auto: before {content_type} index")
                if snapshot_result['status'] == 'completed':
                    logger.info(f"Auto-snapshot created: {snapshot_result['filename']}")
    except Exception as e:
        # Don't fail indexing if snapshot fails
        logger.warning(f"Auto-snapshot failed (continuing with index): {e}")
    
    # Determine indexer script
    scripts_dir = Path(__file__).parent.parent / "indexer"
    
    if content_type == 'pdf':
        indexer_module = "dam.indexer.pdf"
    elif content_type in ('3d', 'smb'):
        indexer_module = "dam.indexer.models3d"
    else:
        return jsonify({'error': f'Unknown content type: {content_type}'}), 400
    
    # Set up logging
    log_file = config.LOG_DIR / f"index_{content_type}.log"
    log_file.parent.mkdir(exist_ok=True)
    
    try:
        if background:
            # Run in background - return immediately
            with open(log_file, 'a') as log:
                log.write(f"\n\n=== Indexing started at {datetime.now()} ===\n")
                log.write(f"Type: {content_type}, Paths: {paths}\n\n")
                log.flush()
                
                for p in paths:
                    p = p.strip()
                    subprocess.Popen(
                        ['python', '-u', '-m', indexer_module, p],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                        cwd=str(config.BASE_DIR)
                    )
            
            return jsonify({
                'status': 'started',
                'success': True,
                'message': f'Indexing started in background for {len(paths)} path(s)',
                'log_file': str(log_file),
                'paths': paths
            })
        else:
            # Run synchronously (blocking)
            result = subprocess.run(
                ['python', '-m', indexer_module, path],
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(config.BASE_DIR)
            )
            
            if result.returncode == 0:
                return jsonify({'status': 'completed', 'success': True, 'message': f'Indexing complete for {path}'})
            else:
                return jsonify({'error': result.stderr or 'Indexing failed'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Indexing timed out (>1 hour)'}), 500
    except Exception as e:
        logger.exception(f"Indexing failed: {e}")
        return jsonify({'error': str(e)}), 500


@indexer_bp.route('/index/status')
def api_index_status():
    """Get indexing status and recent activity."""
    config = get_config()
    
    status = {
        'running': False,
        'recent_logs': []
    }
    
    # Check if indexer processes are running
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'dam.indexer'],
            capture_output=True,
            text=True
        )
        status['running'] = result.returncode == 0
    except Exception:
        pass
    
    # Get recent log entries
    for log_type in ['pdf', '3d', 'smb']:
        log_file = config.LOG_DIR / f"index_{log_type}.log"
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-20:]  # Last 20 lines
                    status['recent_logs'].extend([
                        {'type': log_type, 'line': line.strip()}
                        for line in lines if line.strip()
                    ])
            except Exception:
                pass
    
    return jsonify(status)


@indexer_bp.route('/index/clear', methods=['POST'])
def api_clear_index():
    """Clear index for a content type (destructive!)."""
    data = request.get_json(silent=True)
    content_type = data.get('type') if data else None
    
    if content_type not in ('pdf', '3d', 'all'):
        return jsonify({'error': 'Invalid content type'}), 400
    
    from dam.core.database import get_connection
    
    with get_connection() as conn:
        if content_type in ('pdf', 'all'):
            conn.execute("DELETE FROM asset_pages")
            conn.execute("DELETE FROM asset_bookmarks")
            conn.execute("DELETE FROM assets")
            logger.warning("Cleared PDF assets index")
        
        if content_type in ('3d', 'all'):
            conn.execute("DELETE FROM models")
            logger.warning("Cleared 3D models index")
        
        conn.commit()
    
    return jsonify({'success': True, 'message': f'Index cleared for type: {content_type}'})
