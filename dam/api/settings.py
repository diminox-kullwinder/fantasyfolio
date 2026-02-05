"""
Settings API Blueprint.

Handles application settings and configuration.
"""

import os
import logging
from flask import Blueprint, jsonify, request

from dam.core.database import get_setting, set_setting, get_all_settings, get_connection

logger = logging.getLogger(__name__)
settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET'])
def api_get_settings():
    """Get all settings."""
    return jsonify(get_all_settings())


@settings_bp.route('/settings', methods=['POST'])
def api_set_settings():
    """Set multiple settings at once."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    with get_connection() as conn:
        for key, value in data.items():
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, str(value))
            )
        conn.commit()
    
    return jsonify({'success': True})


@settings_bp.route('/settings/<key>', methods=['GET'])
def api_get_setting(key: str):
    """Get a single setting."""
    value = get_setting(key)
    if value is None:
        return jsonify({'error': 'Setting not found'}), 404
    return jsonify({key: value})


@settings_bp.route('/settings/<key>', methods=['PUT'])
def api_set_setting(key: str):
    """Set a single setting."""
    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({'error': 'Value required'}), 400
    
    set_setting(key, str(data['value']))
    return jsonify({'success': True})


@settings_bp.route('/browse-directory')
def api_browse_directory():
    """
    Browse server directories for path selection.
    Used by the settings UI for selecting content roots.
    """
    path = request.args.get('path', '/Volumes')
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Not a directory'}), 400
    
    try:
        entries = []
        for entry in os.scandir(path):
            if entry.is_dir() and not entry.name.startswith('.'):
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'type': 'directory'
                })
        
        entries.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'path': path,
            'parent': os.path.dirname(path) if path != '/' else None,
            'entries': entries
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        logger.error(f"Directory browse error: {e}")
        return jsonify({'error': str(e)}), 500
