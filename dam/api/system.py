"""
System API Blueprint.

Handles system-level endpoints: volume status, health checks, system info.
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify

from dam.services.volume_monitor import (
    get_all_volume_status,
    check_volume_available,
    check_volumes_for_index
)

logger = logging.getLogger(__name__)
system_bp = Blueprint('system', __name__)


@system_bp.route('/system/volume-status')
def api_volume_status():
    """
    Get availability status of all configured volumes.
    
    Returns JSON:
    {
        "volumes": {
            "pdfs": {"path": "...", "available": true, "reason": null, "last_checked": "..."},
            "models": {"path": "...", "available": false, "reason": "Volume not mounted", ...}
        },
        "all_available": false,
        "unavailable": ["models"],
        "checked_at": "2026-02-07T12:00:00"
    }
    """
    try:
        status = get_all_volume_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error checking volume status: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to check volume status',
            'message': str(e)
        }), 500


@system_bp.route('/system/volume-status/<volume_name>')
def api_single_volume_status(volume_name: str):
    """
    Get availability status of a single volume.
    
    Args:
        volume_name: Name of the volume (e.g., 'pdfs', 'models')
    
    Returns JSON with volume status or 404 if volume not configured.
    """
    try:
        status = get_all_volume_status()
        
        if volume_name not in status['volumes']:
            return jsonify({
                'error': 'Volume not found',
                'message': f"Volume '{volume_name}' is not configured",
                'configured_volumes': list(status['volumes'].keys())
            }), 404
        
        return jsonify(status['volumes'][volume_name])
    except Exception as e:
        logger.error(f"Error checking volume {volume_name}: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to check volume status',
            'message': str(e)
        }), 500


@system_bp.route('/system/check-index/<index_type>')
def api_check_index_volumes(index_type: str):
    """
    Check if required volumes are available for an index operation.
    
    Args:
        index_type: Type of index ('pdfs', 'models', 'all')
    
    Returns JSON:
    {
        "can_proceed": true/false,
        "required_volumes": ["pdfs"],
        "unavailable_volumes": [],
        "volume_status": {...},
        "message": "All required volumes are available"
    }
    """
    if index_type not in ('pdfs', 'models', 'all'):
        return jsonify({
            'error': 'Invalid index type',
            'message': f"Index type must be 'pdfs', 'models', or 'all', got '{index_type}'",
            'valid_types': ['pdfs', 'models', 'all']
        }), 400
    
    try:
        result = check_volumes_for_index(index_type)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error checking volumes for index {index_type}: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to check volumes',
            'message': str(e)
        }), 500


@system_bp.route('/system/state')
def api_system_state():
    """
    Get comprehensive system state for recovery/monitoring.
    
    Returns all relevant status information in one call.
    """
    from dam.services.volume_monitor import get_all_volume_status
    from dam.services.snapshot import get_latest_snapshot, list_snapshots
    from dam.services.change_journal import get_journal_stats
    from dam.services.backup_policy import get_policy_status
    from dam.core.database import get_stats, get_models_stats
    
    try:
        # Volume status
        volumes = get_all_volume_status()
        
        # Database stats
        asset_stats = get_stats()
        model_stats = get_models_stats()
        
        # Snapshot info
        snapshots = list_snapshots()
        latest_snapshot = snapshots[0] if snapshots else None
        
        # Journal stats
        journal = get_journal_stats()
        
        # Backup status
        backups = get_policy_status()
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'volumes': {
                'all_available': volumes['all_available'],
                'unavailable': volumes['unavailable'],
                'details': volumes['volumes']
            },
            'database': {
                'assets': asset_stats['total_assets'],
                'models': model_stats['total_models'],
                'deleted_assets': asset_stats.get('deleted_count', 0),
                'deleted_models': model_stats.get('deleted_count', 0)
            },
            'snapshots': {
                'total': len(snapshots),
                'latest': latest_snapshot['timestamp'] if latest_snapshot else None,
                'latest_size': latest_snapshot.get('size_human') if latest_snapshot else None
            },
            'journal': {
                'total_entries': journal['total_entries'],
                'recent_24h': journal['recent_24h']
            },
            'backups': backups
        })
    except Exception as e:
        logger.error(f"Error getting system state: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get state', 'message': str(e)}), 500


@system_bp.route('/system/health')
def api_health():
    """
    Simple health check endpoint.
    
    Returns 200 if the application is running.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'DAM API'
    })


@system_bp.route('/system/info')
def api_system_info():
    """
    Get system information including volume status summary.
    
    Returns basic system info for dashboard display.
    """
    from dam.config import get_config
    import os
    
    config = get_config()
    volume_status = get_all_volume_status()
    
    # Get database size
    db_size = 0
    try:
        if config.DATABASE_PATH.exists():
            db_size = config.DATABASE_PATH.stat().st_size
    except Exception:
        pass
    
    return jsonify({
        'app_name': config.APP_NAME,
        'version': config.APP_VERSION,
        'database': {
            'path': str(config.DATABASE_PATH),
            'size_bytes': db_size,
            'size_human': _format_size(db_size)
        },
        'volumes': {
            'all_available': volume_status['all_available'],
            'unavailable': volume_status['unavailable'],
            'count': len(volume_status['volumes'])
        }
    })


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# =============================================================================
# TRASH API (Soft Delete Management)
# =============================================================================

@system_bp.route('/trash')
def api_trash_list():
    """
    Get contents of the Trash (soft-deleted items).
    
    Returns JSON:
    {
        "assets": [...],
        "models": [...],
        "total_assets": 5,
        "total_models": 2
    }
    """
    from dam.core.database import get_deleted_assets, get_deleted_models
    
    try:
        assets = get_deleted_assets(limit=200)
        models = get_deleted_models(limit=200)
        
        return jsonify({
            'assets': assets,
            'models': models,
            'total_assets': len(assets),
            'total_models': len(models)
        })
    except Exception as e:
        logger.error(f"Error fetching trash: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch trash', 'message': str(e)}), 500


@system_bp.route('/trash/asset/<int:asset_id>', methods=['DELETE'])
def api_trash_asset(asset_id: int):
    """
    Move an asset to trash (soft delete).
    
    Returns JSON with success status.
    """
    from dam.core.database import soft_delete_asset, get_asset_by_id
    
    try:
        # Check if asset exists
        asset = get_asset_by_id(asset_id)
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        if asset.get('deleted_at'):
            return jsonify({'error': 'Asset already in trash'}), 400
        
        success = soft_delete_asset(asset_id)
        if success:
            return jsonify({
                'success': True,
                'message': f"Asset '{asset.get('filename')}' moved to trash"
            })
        else:
            return jsonify({'error': 'Failed to delete asset'}), 500
    except Exception as e:
        logger.error(f"Error trashing asset {asset_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to trash asset', 'message': str(e)}), 500


@system_bp.route('/trash/asset/<int:asset_id>/restore', methods=['POST'])
def api_restore_asset(asset_id: int):
    """
    Restore an asset from trash.
    
    Returns JSON with success status.
    """
    from dam.core.database import restore_asset, get_asset_by_id
    
    try:
        asset = get_asset_by_id(asset_id)
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        if not asset.get('deleted_at'):
            return jsonify({'error': 'Asset is not in trash'}), 400
        
        success = restore_asset(asset_id)
        if success:
            return jsonify({
                'success': True,
                'message': f"Asset '{asset.get('filename')}' restored from trash"
            })
        else:
            return jsonify({'error': 'Failed to restore asset'}), 500
    except Exception as e:
        logger.error(f"Error restoring asset {asset_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to restore asset', 'message': str(e)}), 500


@system_bp.route('/trash/asset/<int:asset_id>/permanent', methods=['DELETE'])
def api_permanent_delete_asset(asset_id: int):
    """
    Permanently delete an asset (cannot be undone).
    
    Returns JSON with success status.
    """
    from dam.core.database import permanently_delete_asset, get_asset_by_id
    
    try:
        asset = get_asset_by_id(asset_id)
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        success = permanently_delete_asset(asset_id)
        if success:
            return jsonify({
                'success': True,
                'message': f"Asset permanently deleted"
            })
        else:
            return jsonify({'error': 'Failed to delete asset'}), 500
    except Exception as e:
        logger.error(f"Error permanently deleting asset {asset_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete asset', 'message': str(e)}), 500


@system_bp.route('/trash/model/<int:model_id>', methods=['DELETE'])
def api_trash_model(model_id: int):
    """Move a model to trash (soft delete)."""
    from dam.core.database import soft_delete_model, get_model_by_id
    
    try:
        model = get_model_by_id(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        if model.get('deleted_at'):
            return jsonify({'error': 'Model already in trash'}), 400
        
        success = soft_delete_model(model_id)
        if success:
            return jsonify({
                'success': True,
                'message': f"Model '{model.get('filename')}' moved to trash"
            })
        else:
            return jsonify({'error': 'Failed to delete model'}), 500
    except Exception as e:
        logger.error(f"Error trashing model {model_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to trash model', 'message': str(e)}), 500


@system_bp.route('/trash/model/<int:model_id>/restore', methods=['POST'])
def api_restore_model(model_id: int):
    """Restore a model from trash."""
    from dam.core.database import restore_model, get_model_by_id
    
    try:
        model = get_model_by_id(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        if not model.get('deleted_at'):
            return jsonify({'error': 'Model is not in trash'}), 400
        
        success = restore_model(model_id)
        if success:
            return jsonify({
                'success': True,
                'message': f"Model '{model.get('filename')}' restored from trash"
            })
        else:
            return jsonify({'error': 'Failed to restore model'}), 500
    except Exception as e:
        logger.error(f"Error restoring model {model_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to restore model', 'message': str(e)}), 500


@system_bp.route('/trash/empty', methods=['POST'])
def api_empty_trash():
    """
    Permanently empty the trash (delete all soft-deleted items).
    
    Query params:
        older_than_days: Only delete items older than N days (optional)
    
    Returns JSON with count of deleted items.
    """
    from flask import request
    from dam.core.database import empty_trash
    
    try:
        older_than = request.args.get('older_than_days', type=int)
        
        # Count before (for models we'd need a similar function)
        # For now just empty assets
        deleted_count = empty_trash(older_than_days=older_than)
        
        return jsonify({
            'success': True,
            'message': f"Permanently deleted {deleted_count} items from trash",
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"Error emptying trash: {e}", exc_info=True)
        return jsonify({'error': 'Failed to empty trash', 'message': str(e)}), 500


@system_bp.route('/trash/cleanup', methods=['POST'])
def api_trash_cleanup():
    """
    Run trash auto-cleanup (remove items older than retention period).
    
    Query params:
        days: Override retention period (optional)
        dry_run: If 'true', don't actually delete (optional)
    
    Returns JSON with cleanup results.
    """
    from flask import request
    from dam.services.trash_cleanup import cleanup_expired_trash, get_trash_retention_days
    
    try:
        retention_days = request.args.get('days', type=int)
        dry_run = request.args.get('dry_run', '').lower() == 'true'
        
        result = cleanup_expired_trash(retention_days=retention_days, dry_run=dry_run)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running trash cleanup: {e}", exc_info=True)
        return jsonify({'error': 'Cleanup failed', 'message': str(e)}), 500


# =============================================================================
# CHANGE JOURNAL API
# =============================================================================

@system_bp.route('/journal/status')
def api_journal_status():
    """Get journal statistics."""
    from dam.services.change_journal import get_journal_stats
    
    try:
        stats = get_journal_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting journal stats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get stats', 'message': str(e)}), 500


@system_bp.route('/journal')
def api_journal_list():
    """
    Get journal entries with optional filters.
    
    Query params:
        type: Filter by entity type ('asset' or 'model')
        id: Filter by entity ID
        action: Filter by action type
        limit: Maximum entries (default 100)
        offset: Pagination offset
    """
    from flask import request
    from dam.services.change_journal import get_journal_entries
    
    try:
        entity_type = request.args.get('type')
        entity_id = request.args.get('id', type=int)
        action = request.args.get('action')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        entries = get_journal_entries(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            limit=min(limit, 500),  # Cap at 500
            offset=offset
        )
        
        return jsonify({
            'entries': entries,
            'count': len(entries),
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"Error fetching journal: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch journal', 'message': str(e)}), 500


@system_bp.route('/journal/cleanup', methods=['POST'])
def api_journal_cleanup():
    """
    Clean up old journal entries.
    
    Query params:
        days: Remove entries older than N days (default: 90)
    """
    from flask import request
    from dam.services.change_journal import cleanup_old_entries
    
    try:
        days = request.args.get('days', 90, type=int)
        deleted = cleanup_old_entries(days)
        
        return jsonify({
            'success': True,
            'deleted_count': deleted,
            'retention_days': days
        })
    except Exception as e:
        logger.error(f"Error cleaning up journal: {e}", exc_info=True)
        return jsonify({'error': 'Cleanup failed', 'message': str(e)}), 500


@system_bp.route('/journal/entity/<entity_type>/<int:entity_id>')
def api_journal_entity_history(entity_type: str, entity_id: int):
    """Get complete history for a specific entity."""
    from dam.services.change_journal import get_entity_history
    
    if entity_type not in ('asset', 'model'):
        return jsonify({'error': 'Invalid entity type'}), 400
    
    try:
        history = get_entity_history(entity_type, entity_id)
        return jsonify({
            'entity_type': entity_type,
            'entity_id': entity_id,
            'history': history,
            'total_changes': len(history)
        })
    except Exception as e:
        logger.error(f"Error fetching entity history: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch history', 'message': str(e)}), 500


# =============================================================================
# SNAPSHOT API
# =============================================================================

@system_bp.route('/snapshots')
def api_snapshots_list():
    """List all database snapshots."""
    from dam.services.snapshot import list_snapshots
    
    try:
        snapshots = list_snapshots()
        return jsonify({
            'snapshots': snapshots,
            'total': len(snapshots)
        })
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list snapshots', 'message': str(e)}), 500


@system_bp.route('/snapshots', methods=['POST'])
def api_snapshots_create():
    """Create a new database snapshot."""
    from flask import request
    from dam.services.snapshot import create_snapshot
    
    try:
        data = request.get_json() or {}
        note = data.get('note')
        
        result = create_snapshot(note=note)
        
        if result['status'] == 'completed':
            return jsonify(result), 201
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create snapshot', 'message': str(e)}), 500


@system_bp.route('/snapshots/latest')
def api_snapshots_latest():
    """Get the most recent snapshot."""
    from dam.services.snapshot import get_latest_snapshot
    
    try:
        snapshot = get_latest_snapshot()
        if snapshot:
            return jsonify(snapshot)
        else:
            return jsonify({'error': 'No snapshots found'}), 404
    except Exception as e:
        logger.error(f"Error getting latest snapshot: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get snapshot', 'message': str(e)}), 500


@system_bp.route('/snapshots/<filename>', methods=['DELETE'])
def api_snapshots_delete(filename: str):
    """Delete a snapshot."""
    from dam.services.snapshot import delete_snapshot
    
    try:
        if delete_snapshot(filename):
            return jsonify({'success': True, 'message': f'Deleted {filename}'})
        else:
            return jsonify({'error': 'Snapshot not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting snapshot: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete snapshot', 'message': str(e)}), 500


@system_bp.route('/snapshots/<filename>/restore', methods=['POST'])
def api_snapshots_restore(filename: str):
    """
    Restore database from a snapshot.
    
    WARNING: This replaces the current database!
    """
    from dam.services.snapshot import restore_snapshot
    
    try:
        result = restore_snapshot(filename)
        
        if result['status'] == 'completed':
            return jsonify(result)
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error restoring snapshot: {e}", exc_info=True)
        return jsonify({'error': 'Restore failed', 'message': str(e)}), 500


@system_bp.route('/snapshots/cleanup', methods=['POST'])
def api_snapshots_cleanup():
    """Remove old snapshots."""
    from flask import request
    from dam.services.snapshot import cleanup_old_snapshots
    
    try:
        data = request.get_json() or {}
        keep_count = data.get('keep_count', 10)
        keep_days = data.get('keep_days', 30)
        
        result = cleanup_old_snapshots(keep_count=keep_count, keep_days=keep_days)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error cleaning up snapshots: {e}", exc_info=True)
        return jsonify({'error': 'Cleanup failed', 'message': str(e)}), 500


# =============================================================================
# BACKUP POLICY API
# =============================================================================

@system_bp.route('/backup/policies')
def api_backup_policies():
    """Get all backup policies."""
    from dam.services.backup_policy import get_all_policies, get_active_policies, get_inactive_policies
    
    try:
        all_policies = get_all_policies()
        active = [p for p in all_policies if p.get('state') == 'active']
        inactive = [p for p in all_policies if p.get('state') in ('paused', 'disabled')]
        
        return jsonify({
            'policies': all_policies,
            'active': active,
            'inactive': inactive,
            'total': len(all_policies)
        })
    except Exception as e:
        logger.error(f"Error getting backup policies: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get policies', 'message': str(e)}), 500


@system_bp.route('/backup/policies', methods=['POST'])
def api_backup_policy_create():
    """Create a new backup policy."""
    from flask import request
    from dam.services.backup_policy import create_policy
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = create_policy(data)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error creating backup policy: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create policy', 'message': str(e)}), 500


@system_bp.route('/backup/policies/<policy_id>', methods=['GET'])
def api_backup_policy_get(policy_id: str):
    """Get a single policy by ID."""
    from dam.services.backup_policy import get_policy_by_id
    
    try:
        policy = get_policy_by_id(policy_id)
        if policy:
            return jsonify(policy)
        else:
            return jsonify({'error': 'Policy not found'}), 404
    except Exception as e:
        logger.error(f"Error getting policy: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get policy', 'message': str(e)}), 500


@system_bp.route('/backup/policies/<policy_id>', methods=['PUT'])
def api_backup_policy_update(policy_id: str):
    """Update an existing backup policy."""
    from flask import request
    from dam.services.backup_policy import update_policy
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = update_policy(policy_id, data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error updating backup policy: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update policy', 'message': str(e)}), 500


@system_bp.route('/backup/policies/<policy_id>', methods=['DELETE'])
def api_backup_policy_delete(policy_id: str):
    """Delete a backup policy."""
    from dam.services.backup_policy import delete_policy
    
    try:
        result = delete_policy(policy_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error deleting policy: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete policy', 'message': str(e)}), 500


@system_bp.route('/backup/policies/<policy_id>/run', methods=['POST'])
def api_backup_policy_run(policy_id: str):
    """Run backup for a specific policy."""
    from dam.services.backup_policy import run_policy_backup
    
    try:
        result = run_policy_backup(policy_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error running backup: {e}", exc_info=True)
        return jsonify({'error': 'Backup failed', 'message': str(e)}), 500


@system_bp.route('/backup/policies/validate', methods=['POST'])
def api_backup_policy_validate():
    """Validate a policy configuration without saving."""
    from flask import request
    from dam.services.backup_policy import validate_policy
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check connectivity for network policies
        check_connectivity = data.get('destination_type') == 'network'
        result = validate_policy(data, check_connectivity=check_connectivity)
        
        if result['valid']:
            return jsonify({'valid': True, 'message': 'Policy configuration is valid'})
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error validating policy: {e}", exc_info=True)
        return jsonify({'error': 'Validation failed', 'message': str(e)}), 500


# =============================================================================
# ASSET LOCATIONS API
# =============================================================================

@system_bp.route('/asset-locations')
def api_asset_locations_list():
    """List all asset locations."""
    from dam.services.asset_locations import get_all_locations
    
    try:
        locations = get_all_locations()
        return jsonify({
            'locations': locations,
            'total': len(locations)
        })
    except Exception as e:
        logger.error(f"Error listing locations: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list locations', 'message': str(e)}), 500


@system_bp.route('/asset-locations', methods=['POST'])
def api_asset_locations_add():
    """Add a new asset location."""
    from flask import request
    from dam.services.asset_locations import add_location
    
    try:
        data = request.get_json() or {}
        result = add_location(data)
        
        if result.get('success'):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error adding location: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add location', 'message': str(e)}), 500


@system_bp.route('/asset-locations/<location_id>', methods=['PUT', 'PATCH'])
def api_asset_locations_update(location_id: str):
    """Update an asset location."""
    from flask import request
    from dam.services.asset_locations import update_location
    
    try:
        data = request.get_json() or {}
        result = update_location(location_id, data)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error updating location: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update location', 'message': str(e)}), 500


@system_bp.route('/asset-locations/<location_id>', methods=['DELETE'])
def api_asset_locations_delete(location_id: str):
    """Delete an asset location."""
    from dam.services.asset_locations import delete_location
    
    try:
        result = delete_location(location_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error deleting location: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete location', 'message': str(e)}), 500


@system_bp.route('/asset-locations/<location_id>/test', methods=['POST'])
def api_asset_locations_test(location_id: str):
    """Test if an asset location is accessible."""
    from dam.services.asset_locations import get_location_by_id, test_location
    
    try:
        location = get_location_by_id(location_id)
        if not location:
            return jsonify({'error': 'Location not found'}), 404
        
        result = test_location(location)
        return jsonify(result), 200 if result.get('success') else 400
    except Exception as e:
        logger.error(f"Error testing location: {e}", exc_info=True)
        return jsonify({'error': 'Test failed', 'message': str(e)}), 500


# =============================================================================
# SSH KEY API
# =============================================================================

@system_bp.route('/ssh/key')
def api_ssh_key_status():
    """Check if DAM SSH key exists."""
    from dam.services.ssh_keys import check_key_exists
    
    try:
        return jsonify(check_key_exists())
    except Exception as e:
        logger.error(f"Error checking SSH key: {e}", exc_info=True)
        return jsonify({'error': 'Failed to check key', 'message': str(e)}), 500


@system_bp.route('/ssh/key', methods=['POST'])
def api_ssh_key_generate():
    """Generate a new DAM SSH key."""
    from dam.services.ssh_keys import generate_key
    
    try:
        result = generate_key()
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error generating SSH key: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate key', 'message': str(e)}), 500


@system_bp.route('/ssh/key', methods=['DELETE'])
def api_ssh_key_delete():
    """Delete the DAM SSH key."""
    from dam.services.ssh_keys import delete_key
    
    try:
        result = delete_key()
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error deleting SSH key: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete key', 'message': str(e)}), 500


@system_bp.route('/ssh/test', methods=['POST'])
def api_ssh_test_connection():
    """Test SSH connection to a host."""
    from flask import request
    from dam.services.ssh_keys import test_connection
    
    try:
        data = request.get_json()
        host = data.get('host')
        key_path = data.get('key_path')
        
        if not host:
            return jsonify({'error': 'Host required'}), 400
        
        result = test_connection(host, key_path)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error testing SSH: {e}", exc_info=True)
        return jsonify({'error': 'Test failed', 'message': str(e)}), 500


@system_bp.route('/ssh/keys')
def api_ssh_keys_list():
    """List all SSH keys in ~/.ssh."""
    from dam.services.ssh_keys import list_system_keys
    
    try:
        keys = list_system_keys()
        return jsonify({'keys': keys, 'count': len(keys)})
    except Exception as e:
        logger.error(f"Error listing SSH keys: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list keys', 'message': str(e)}), 500


@system_bp.route('/trash/cleanup/status')
def api_trash_cleanup_status():
    """
    Get trash cleanup status (items that would be cleaned up).
    
    Query params:
        days: Override retention period (optional)
    
    Returns JSON with expired items count and details.
    """
    from flask import request
    from dam.services.trash_cleanup import get_expired_trash_items, get_trash_retention_days
    
    try:
        retention_days = request.args.get('days', type=int) or get_trash_retention_days()
        expired = get_expired_trash_items(retention_days)
        
        # Calculate total size
        total_size = sum(a.get('file_size', 0) or 0 for a in expired['assets'])
        total_size += sum(m.get('file_size', 0) or 0 for m in expired['models'])
        
        return jsonify({
            'retention_days': retention_days,
            'cutoff_date': expired['cutoff_date'],
            'expired_assets': len(expired['assets']),
            'expired_models': len(expired['models']),
            'total_expired': len(expired['assets']) + len(expired['models']),
            'total_size_bytes': total_size,
            'total_size_human': _format_size(total_size)
        })
    except Exception as e:
        logger.error(f"Error getting cleanup status: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get status', 'message': str(e)}), 500


@system_bp.route('/create-directory', methods=['POST'])
def api_create_directory():
    """
    Create a new directory on the server.
    
    JSON body:
        path: Parent directory path
        name: Name of new directory to create
    
    Returns JSON with the created directory path.
    """
    import os
    from pathlib import Path
    from flask import request
    
    try:
        data = request.get_json() or {}
        parent_path = data.get('path', '')
        folder_name = data.get('name', '').strip()
        
        if not parent_path:
            return jsonify({'error': 'Parent path is required'}), 400
        
        if not folder_name:
            return jsonify({'error': 'Folder name is required'}), 400
        
        # Security: disallow path traversal in folder name
        if '/' in folder_name or '\\' in folder_name or folder_name in ('.', '..'):
            return jsonify({'error': 'Invalid folder name'}), 400
        
        parent = Path(parent_path).resolve()
        
        if not parent.exists():
            return jsonify({'error': 'Parent directory does not exist'}), 404
        
        if not parent.is_dir():
            return jsonify({'error': 'Parent path is not a directory'}), 400
        
        new_dir = parent / folder_name
        
        if new_dir.exists():
            return jsonify({'error': 'Directory already exists'}), 409
        
        # Create the directory
        new_dir.mkdir(parents=False, exist_ok=False)
        
        return jsonify({
            'success': True,
            'path': str(new_dir),
            'name': folder_name
        })
        
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        logger.error(f"Error creating directory: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create directory', 'message': str(e)}), 500


@system_bp.route('/browse-directories')
def api_browse_directories():
    """
    Browse server-side directories for backup path selection.
    
    Query params:
        path: Directory to list (default: user's home directory)
    
    Returns JSON with directories in the specified path.
    """
    import os
    from pathlib import Path
    from flask import request
    
    try:
        # Get requested path, default to home directory
        requested_path = request.args.get('path', '')
        
        if not requested_path:
            # Start at home directory
            base_path = Path.home()
        else:
            base_path = Path(requested_path)
        
        # Resolve to absolute path
        base_path = base_path.resolve()
        
        # Security: ensure path exists and is a directory
        if not base_path.exists():
            return jsonify({
                'error': 'Path does not exist',
                'path': str(base_path)
            }), 404
        
        if not base_path.is_dir():
            return jsonify({
                'error': 'Path is not a directory',
                'path': str(base_path)
            }), 400
        
        # List directories only (not files)
        directories = []
        try:
            for entry in sorted(base_path.iterdir()):
                # Skip hidden files/dirs (starting with .)
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    # Check if we can read it
                    try:
                        readable = os.access(entry, os.R_OK)
                    except:
                        readable = False
                    
                    directories.append({
                        'name': entry.name,
                        'path': str(entry),
                        'readable': readable
                    })
        except PermissionError:
            return jsonify({
                'error': 'Permission denied',
                'path': str(base_path)
            }), 403
        
        # Get parent path (for navigation up)
        parent_path = str(base_path.parent) if base_path.parent != base_path else None
        
        return jsonify({
            'current_path': str(base_path),
            'parent_path': parent_path,
            'directories': directories,
            'count': len(directories)
        })
        
    except Exception as e:
        logger.error(f"Error browsing directories: {e}", exc_info=True)
        return jsonify({'error': 'Failed to browse', 'message': str(e)}), 500


# ==================== RESTIC BACKUP API ====================

@system_bp.route('/restic/status')
def api_restic_status():
    """Check if Restic is installed."""
    from dam.services.restic_backup import check_restic_installed
    return jsonify(check_restic_installed())


@system_bp.route('/restic/init', methods=['POST'])
def api_restic_init():
    """
    Initialize a Restic repository.
    
    JSON body:
        repo_path: Repository path (local or sftp:user@host:/path)
        password: Repository encryption password
    """
    from flask import request
    from dam.services.restic_backup import init_repo
    
    data = request.get_json() or {}
    repo_path = data.get('repo_path', '').strip()
    password = data.get('password', '')
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    result = init_repo(repo_path, password)
    return jsonify(result), 200 if result.get('success') else 400


@system_bp.route('/restic/backup', methods=['POST'])
def api_restic_backup():
    """
    Run a backup to Restic repository.
    
    JSON body:
        repo_path: Repository path
        password: Repository password
        source_path: Path to backup (defaults to latest snapshot)
        tags: Optional list of tags
    """
    from flask import request
    from dam.services.restic_backup import run_backup
    from dam.services.snapshot import get_latest_snapshot
    
    data = request.get_json() or {}
    repo_path = data.get('repo_path', '').strip()
    password = data.get('password', '')
    source_path = data.get('source_path', '').strip()
    tags = data.get('tags', ['dam-backup'])
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    # Default to latest snapshot if no source specified
    if not source_path:
        snapshot = get_latest_snapshot()
        if not snapshot:
            return jsonify({'error': 'No snapshots available. Create a snapshot first.'}), 400
        source_path = snapshot['path']
    
    result = run_backup(repo_path, password, source_path, tags)
    return jsonify(result), 200 if result.get('success') else 400


@system_bp.route('/restic/snapshots')
def api_restic_snapshots():
    """
    List snapshots in a Restic repository.
    
    Query params:
        repo_path: Repository path
        password: Repository password
    """
    from flask import request
    from dam.services.restic_backup import list_snapshots
    
    repo_path = request.args.get('repo_path', '').strip()
    password = request.args.get('password', '')
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    result = list_snapshots(repo_path, password)
    return jsonify(result), 200 if result.get('success') else 400


@system_bp.route('/restic/restore', methods=['POST'])
def api_restic_restore():
    """
    One-click restore database from Restic snapshot.
    
    JSON body:
        repo_path: Repository path
        password: Repository password
        snapshot_id: Snapshot ID to restore
    """
    from flask import request, current_app
    from dam.services.restic_backup import restore_database
    
    data = request.get_json() or {}
    repo_path = data.get('repo_path', '').strip()
    password = data.get('password', '')
    snapshot_id = data.get('snapshot_id', '').strip()
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    if not snapshot_id:
        return jsonify({'error': 'Snapshot ID is required'}), 400
    
    # Get current database path
    db_path = current_app.config.get('DATABASE_PATH')
    if not db_path:
        from dam.core.database import get_database_path
        db_path = get_database_path()
    
    result = restore_database(repo_path, password, snapshot_id, db_path)
    return jsonify(result), 200 if result.get('success') else 400


@system_bp.route('/restic/stats')
def api_restic_stats():
    """
    Get Restic repository statistics.
    
    Query params:
        repo_path: Repository path
        password: Repository password
    """
    from flask import request
    from dam.services.restic_backup import get_repo_stats
    
    repo_path = request.args.get('repo_path', '').strip()
    password = request.args.get('password', '')
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    result = get_repo_stats(repo_path, password)
    return jsonify(result), 200 if result.get('success') else 400


@system_bp.route('/restic/prune', methods=['POST'])
def api_restic_prune():
    """
    Prune old snapshots from repository.
    
    JSON body:
        repo_path: Repository path
        password: Repository password
        keep_last: Number of snapshots to keep (default 7)
    """
    from flask import request
    from dam.services.restic_backup import prune_snapshots
    
    data = request.get_json() or {}
    repo_path = data.get('repo_path', '').strip()
    password = data.get('password', '')
    keep_last = data.get('keep_last', 7)
    
    if not repo_path:
        return jsonify({'error': 'Repository path is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    result = prune_snapshots(repo_path, password, keep_last)
    return jsonify(result), 200 if result.get('success') else 400
