"""
3D Models API Blueprint.

Handles all 3D model-related endpoints: listing, details,
thumbnails, preview rendering, and file serving.
"""

import io
import os
import zipfile
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file

from fantasyfolio.core.database import get_connection, get_models_stats, get_model_by_id
from fantasyfolio.config import get_config

logger = logging.getLogger(__name__)
models_bp = Blueprint('models', __name__)


@models_bp.route('/models')
def api_models():
    """List 3D models with optional filters and sorting."""
    folder = request.args.get('folder')
    collection = request.args.get('collection')
    format_filter = request.args.get('format')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    sort = request.args.get('sort', 'filename')
    order = request.args.get('order', 'asc')
    
    # Validate sort column to prevent SQL injection
    valid_sorts = {'filename', 'title', 'file_size', 'format', 'collection', 'created_at'}
    if sort not in valid_sorts:
        sort = 'filename'
    
    # Validate order
    order = 'DESC' if order.lower() == 'desc' else 'ASC'
    
    with get_connection() as conn:
        query = "SELECT * FROM models WHERE 1=1"
        params = []
        
        if folder:
            query += " AND folder_path LIKE ?"
            params.append(folder + '%')
        if collection:
            query += " AND collection = ?"
            params.append(collection)
        if format_filter:
            query += " AND format = ?"
            params.append(format_filter)
        
        query += f" ORDER BY {sort} {order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(row) for row in rows])


@models_bp.route('/models/stats')
def api_models_stats():
    """Get 3D model statistics."""
    return jsonify(get_models_stats())


@models_bp.route('/models/<int:model_id>')
def api_model(model_id: int):
    """Get a single 3D model by ID."""
    model = get_model_by_id(model_id)
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    return jsonify(model)


@models_bp.route('/models/folders')
def api_models_folders():
    """Get folder tree for 3D models."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT folder_path, COUNT(*) as count
            FROM models
            WHERE folder_path IS NOT NULL AND folder_path != ''
            GROUP BY folder_path
            ORDER BY folder_path
        """).fetchall()
        return jsonify([dict(row) for row in rows])


@models_bp.route('/models/collections')
def api_models_collections():
    """Get list of collections."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT collection, creator, COUNT(*) as count
            FROM models
            WHERE collection IS NOT NULL
            GROUP BY collection, creator
            ORDER BY collection
        """).fetchall()
        return jsonify([dict(row) for row in rows])


@models_bp.route('/models/folder-tree')
def api_models_folder_tree():
    """Get hierarchical folder tree for 3D model navigation."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT folder_path, COUNT(*) as count
            FROM models
            WHERE folder_path IS NOT NULL AND folder_path != ''
            GROUP BY folder_path
            ORDER BY folder_path
        """).fetchall()
        
        # Build tree structure and collect all paths (including parents)
        tree = {}
        all_paths = {}  # {path: count}
        parents_with_children = set()  # Track which paths have children
        
        for row in rows:
            path = row['folder_path']
            count = row['count']
            
            # Add this path
            all_paths[path] = count
            
            # Add all parent paths with aggregated counts
            parts = path.split('/')
            for i in range(1, len(parts)):
                parent_path = '/'.join(parts[:i])
                if parent_path not in all_paths:
                    all_paths[parent_path] = 0
                all_paths[parent_path] += count
                parents_with_children.add(parent_path)  # This parent has children
            
            # Build tree structure
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {'_count': 0, '_children': {}}
                current[part]['_count'] += count
                current = current[part]['_children']
        
        # Convert to flat array with rendering properties (O(n) not O(n²))
        flat = []
        for path in sorted(all_paths.keys()):
            depth = path.count('/')
            name = path.split('/')[-1]
            flat.append({
                'folder_path': path,
                'path': path,
                'count': all_paths[path],
                'depth': depth,
                'name': name,
                'hasChildren': path in parents_with_children
            })
        
        return jsonify({'tree': tree, 'flat': flat})


@models_bp.route('/models/search')
def api_models_search():
    """Search 3D models with optional folder scope."""
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 50))
    folder = request.args.get('folder')
    
    if not query:
        return jsonify([])
    
    from fantasyfolio.core.database import search_models
    return jsonify(search_models(query, limit=limit, folder=folder))


@models_bp.route('/models/<int:model_id>/preview')
def api_model_preview(model_id: int):
    """Get preview image for a 3D model."""
    config = get_config()
    model = get_model_by_id(model_id)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    # Check for cached thumbnail
    cached_thumb = config.THUMBNAIL_DIR / "3d" / f"{model_id}.png"
    if cached_thumb.exists():
        return send_file(cached_thumb, mimetype='image/png')
    
    # Try to get preview from archive (but skip if it's likely just a texture file)
    if model.get('archive_path') and model.get('preview_image'):
        try:
            preview_name = model['preview_image'].lower()
            # Skip texture files - they're not real previews
            is_texture = any(x in preview_name for x in ['material', 'texture', 'diffuse', 'albedo', 'normal', 'roughness'])
            
            if not is_texture:
                with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                    info = zf.getinfo(model['preview_image'])
                    # Skip if file is too large (>2MB is probably a texture, not a preview)
                    if info.file_size < 2 * 1024 * 1024:
                        img_data = zf.read(model['preview_image'])
                        ext = Path(model['preview_image']).suffix.lower()
                        mime = {
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.png': 'image/png',
                            '.webp': 'image/webp',
                        }.get(ext, 'image/jpeg')
                        return send_file(io.BytesIO(img_data), mimetype=mime)
                    else:
                        logger.debug(f"Preview too large ({info.file_size} bytes), will render 3D thumbnail")
        except Exception as e:
            logger.debug(f"Failed to get preview from archive: {e}")
    
    # Try standalone preview file
    if model.get('preview_image') and os.path.exists(model['preview_image']):
        return send_file(model['preview_image'])
    
    # Try to render 3D thumbnail in background (non-blocking)
    # Supports STL, OBJ, and 3MF formats
    model_format = model.get('format', '').lower()
    if model_format in ('stl', 'obj', '3mf'):
        import threading
        
        def render_in_background():
            try:
                from fantasyfolio.indexer.thumbnails import render_3d_thumbnail
                
                # Get model data
                if model.get('archive_path') and model.get('archive_member'):
                    with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                        model_data = zf.read(model['archive_member'])
                elif os.path.exists(model.get('file_path', '')):
                    with open(model['file_path'], 'rb') as f:
                        model_data = f.read()
                else:
                    logger.warning(f"Model file not found for {model_id}")
                    return
                
                render_3d_thumbnail(model_data, model_format, str(cached_thumb))
                
                # Update database flag
                with get_connection() as conn:
                    conn.execute("UPDATE models SET has_thumbnail = 1 WHERE id = ?", (model_id,))
                    conn.commit()
                
                logger.info(f"Background render complete for model {model_id} ({model_format})")
            except Exception as e:
                logger.error(f"Background thumbnail render error for model {model_id}: {e}")
        
        # Start background render, return placeholder immediately
        thread = threading.Thread(target=render_in_background, daemon=True)
        thread.start()
    
    # Return placeholder
    placeholder = config.STATIC_DIR / 'placeholder-3d.svg'
    if placeholder.exists():
        return send_file(placeholder, mimetype='image/svg+xml')
    
    return jsonify({'error': 'No preview available'}), 404


@models_bp.route('/models/<int:model_id>/stl')
def api_model_stl(model_id: int):
    """Serve STL file for 3D viewer (handles ZIP extraction). Legacy endpoint."""
    return api_model_file(model_id)


@models_bp.route('/models/<int:model_id>/file')
def api_model_file(model_id: int):
    """Serve model file for 3D viewer (handles ZIP extraction). Supports STL, OBJ, 3MF."""
    model = get_model_by_id(model_id)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    # Determine MIME type based on format
    format_mime = {
        'stl': 'application/octet-stream',
        'obj': 'text/plain',
        '3mf': 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml',
    }
    mime_type = format_mime.get(model.get('format', '').lower(), 'application/octet-stream')
    
    try:
        if model.get('archive_path') and model.get('archive_member'):
            # Extract from ZIP
            with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                file_data = zf.read(model['archive_member'])
            return send_file(
                io.BytesIO(file_data),
                mimetype=mime_type,
                download_name=model['filename']
            )
        elif model.get('file_path') and os.path.exists(model['file_path']):
            return send_file(model['file_path'], mimetype=mime_type)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"File serve error for model {model_id}: {e}")
        return jsonify({'error': 'Failed to serve file'}), 500


@models_bp.route('/models/<int:model_id>/download')
def api_model_download(model_id: int):
    """Download the original model file.
    
    Returns 503 with volume_unavailable error if the storage volume is offline.
    This helps UI distinguish between "file deleted" vs "volume unmounted".
    """
    model = get_model_by_id(model_id)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    # Determine the path to check for volume availability
    # For archived models, check the archive path; otherwise check file_path
    check_path = model.get('archive_path') or model['file_path']
    
    # Check volume availability before attempting download
    from fantasyfolio.services.volume_monitor import check_volume_for_path
    volume_status = check_volume_for_path(str(check_path))
    
    if not volume_status['available']:
        return jsonify({
            'error': 'volume_unavailable',
            'message': f"Storage volume is offline: {volume_status['reason']}",
            'volume': volume_status.get('volume_name'),
            'file_path': str(check_path)
        }), 503  # Service Unavailable
    
    try:
        if model.get('archive_path') and model.get('archive_member'):
            # Check if archive file exists
            if not os.path.exists(model['archive_path']):
                return jsonify({
                    'error': 'file_not_found',
                    'message': 'Archive file not found on disk (may have been moved or deleted)',
                    'file_path': model['archive_path']
                }), 404
            
            with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                data = zf.read(model['archive_member'])
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=model['filename']
            )
        elif os.path.exists(model['file_path']):
            return send_file(
                model['file_path'],
                as_attachment=True,
                download_name=model['filename']
            )
        else:
            return jsonify({
                'error': 'file_not_found',
                'message': 'File not found on disk (may have been moved or deleted)',
                'file_path': model['file_path']
            }), 404
    except zipfile.BadZipFile:
        return jsonify({
            'error': 'archive_corrupt',
            'message': 'Archive file is corrupted or invalid',
            'file_path': model.get('archive_path')
        }), 500
    except KeyError:
        return jsonify({
            'error': 'member_not_found',
            'message': f"File '{model.get('archive_member')}' not found in archive",
            'file_path': model.get('archive_path')
        }), 404
    except Exception as e:
        logger.error(f"Download error for model {model_id}: {e}")
        return jsonify({'error': 'Download failed', 'message': str(e)}), 500


@models_bp.route('/models/thumbnail-stats')
def api_thumbnail_stats():
    """Get thumbnail cache statistics for current models."""
    config = get_config()
    thumbnail_dir = Path(config.THUMBNAIL_DIR) / "3d"
    
    with get_connection() as conn:
        # Get all model IDs (for 3D formats)
        model_rows = conn.execute("""
            SELECT id FROM models 
            WHERE format IN ('stl', 'obj', '3mf')
        """).fetchall()
    
    total = len(model_rows)
    model_ids = set(row['id'] for row in model_rows)
    
    # Count which models have cached thumbnails
    cached = 0
    if thumbnail_dir.exists():
        for png in thumbnail_dir.glob("*.png"):
            try:
                model_id = int(png.stem)
                if model_id in model_ids:
                    cached += 1
            except ValueError:
                pass
    
    return jsonify({
        'total': total,
        'cached': cached,
        'missing': total - cached,
        'percent': round((cached / total * 100) if total > 0 else 0, 1)
    })


# Global render status tracking
_render_status = {
    'active': False,
    'total': 0,
    'completed': 0,
    'errors': 0,
    'current_model': None,
    'started_at': None,
    'last_update': None
}


@models_bp.route('/models/render-thumbnails/status')
def api_render_thumbnails_status():
    """Get current thumbnail rendering status."""
    return jsonify(_render_status)


@models_bp.route('/models/render-thumbnails', methods=['POST'])
def api_render_thumbnails():
    """Queue all missing 3D model thumbnails for rendering."""
    import threading
    from fantasyfolio.indexer.thumbnails import render_3d_thumbnail
    from datetime import datetime
    global _render_status
    
    config = get_config()
    thumbnail_dir = Path(config.THUMBNAIL_DIR) / "3d"
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    
    with get_connection() as conn:
        models = conn.execute("SELECT id, format, file_path, archive_path, archive_member FROM models ORDER BY id").fetchall()
    
    # Separate cached vs missing
    models_to_render = []
    cached_count = 0
    
    for model in models:
        cached_thumb = thumbnail_dir / f"{model['id']}.png"
        if cached_thumb.exists():
            cached_count += 1
        else:
            models_to_render.append(model)
    
    # Initialize render status
    _render_status['active'] = True
    _render_status['total'] = len(models_to_render)
    _render_status['completed'] = 0
    _render_status['errors'] = 0
    _render_status['current_model'] = None
    _render_status['started_at'] = datetime.now().isoformat()
    _render_status['last_update'] = datetime.now().isoformat()
    
    # Start background rendering
    def render_batch():
        global _render_status
        
        for i, model in enumerate(models_to_render):
            _render_status['current_model'] = model['id']
            _render_status['last_update'] = datetime.now().isoformat()
            
            try:
                model_format = (model['format'] or 'stl').lower()
                if model_format not in ('stl', 'obj', '3mf'):
                    _render_status['completed'] += 1
                    continue
                
                # Get model data
                model_data = None
                try:
                    if model['archive_path'] and model['archive_member']:
                        if os.path.exists(model['archive_path']):
                            with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                                model_data = zf.read(model['archive_member'])
                    elif model['file_path'] and os.path.exists(model['file_path']):
                        with open(model['file_path'], 'rb') as f:
                            model_data = f.read()
                except Exception as read_err:
                    logger.debug(f"Could not read model {model['id']}: {read_err}")
                    _render_status['errors'] += 1
                    _render_status['completed'] += 1
                    continue
                
                if not model_data:
                    _render_status['errors'] += 1
                    _render_status['completed'] += 1
                    continue
                
                # Render thumbnail
                render_3d_thumbnail(model_data, model_format, str(thumbnail_dir / f"{model['id']}.png"))
                
                # Update database flag
                with get_connection() as conn:
                    conn.execute("UPDATE models SET has_thumbnail = 1 WHERE id = ?", (model['id'],))
                    conn.commit()
                
                _render_status['completed'] += 1
                
                if (i + 1) % 100 == 0:
                    pct = round((_render_status['completed'] / _render_status['total']) * 100, 1)
                    logger.info(f"Thumbnail render: {_render_status['completed']}/{_render_status['total']} ({pct}%) - {_render_status['errors']} errors")
                    
            except Exception as e:
                logger.debug(f"Thumbnail render error for model {model['id']}: {e}")
                _render_status['errors'] += 1
                _render_status['completed'] += 1
        
        # Mark as complete
        _render_status['active'] = False
        _render_status['current_model'] = None
        _render_status['last_update'] = datetime.now().isoformat()
        logger.info(f"Background render complete: {_render_status['completed']} processed, {_render_status['errors']} errors")
    
    # Start in background thread
    thread = threading.Thread(target=render_batch, daemon=True)
    thread.start()
    
    return jsonify({
        'message': f'Rendering {len(models_to_render)} thumbnails in background',
        'models_queued': len(models_to_render),
        'already_cached': cached_count,
        'total_models': len(models)
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# EFFICIENT INDEXING API (Phase 4)
# ═══════════════════════════════════════════════════════════════════════════════

@models_bp.route('/models/<int:model_id>/reindex', methods=['POST'])
def api_reindex_model(model_id):
    """
    Re-index a single model.
    
    POST body:
        force: bool - If true, reprocess regardless of cache
        include_thumbnail: bool - If true, also regenerate thumbnail
    """
    from fantasyfolio.core.scanner import reindex_single_asset
    
    data = request.get_json() or {}
    force = data.get('force', False)
    include_thumbnail = data.get('include_thumbnail', True)
    
    with get_connection() as conn:
        result = reindex_single_asset(conn, model_id, force=force)
    
    # TODO: If include_thumbnail and result['status'] == 'indexed', queue thumbnail render
    
    return jsonify(result)


@models_bp.route('/models/missing')
def api_get_missing_models():
    """
    Get list of missing models.
    
    Query params:
        volume_id: Filter by volume
        missing_before: ISO date - only show missing since before this date
        limit: Max results (default 100)
    """
    volume_id = request.args.get('volume_id')
    missing_before = request.args.get('missing_before')
    limit = int(request.args.get('limit', 100))
    
    with get_connection() as conn:
        conditions = ["index_status = 'missing'"]
        params = []
        
        if volume_id:
            conditions.append("volume_id = ?")
            params.append(volume_id)
        
        if missing_before:
            conditions.append("missing_since < ?")
            params.append(missing_before)
        
        where_clause = ' AND '.join(conditions)
        
        # Get count
        total = conn.execute(
            f"SELECT COUNT(*) FROM models WHERE {where_clause}",
            params
        ).fetchone()[0]
        
        # Get models
        params.append(limit)
        rows = conn.execute(f"""
            SELECT id, filename, file_path, archive_path, archive_member,
                   missing_since, last_seen_at, volume_id
            FROM models 
            WHERE {where_clause}
            ORDER BY missing_since ASC
            LIMIT ?
        """, params).fetchall()
        
        return jsonify({
            'models': [dict(row) for row in rows],
            'total_count': total
        })


@models_bp.route('/models/purge-missing', methods=['POST'])
def api_purge_missing_models():
    """
    Permanently delete missing models from database.
    
    REQUIRES explicit confirmation.
    
    POST body:
        model_ids: List of specific IDs to purge, OR
        volume_id: Purge all missing on this volume, OR
        missing_before: ISO date - purge missing since before this date
        confirm: REQUIRED - must be true
    """
    data = request.get_json() or {}
    
    model_ids = data.get('model_ids')
    volume_id = data.get('volume_id')
    missing_before = data.get('missing_before')
    confirm = data.get('confirm', False)
    
    if not confirm:
        return jsonify({
            'error': 'Confirmation required',
            'message': 'Set confirm=true to permanently delete missing assets'
        }), 400
    
    with get_connection() as conn:
        conditions = ["index_status = 'missing'"]
        params = []
        
        if model_ids:
            placeholders = ','.join('?' * len(model_ids))
            conditions.append(f"id IN ({placeholders})")
            params.extend(model_ids)
        
        if volume_id:
            conditions.append("volume_id = ?")
            params.append(volume_id)
        
        if missing_before:
            conditions.append("missing_since < ?")
            params.append(missing_before)
        
        where_clause = ' AND '.join(conditions)
        
        # Count before delete
        count = conn.execute(
            f"SELECT COUNT(*) FROM models WHERE {where_clause}",
            params
        ).fetchone()[0]
        
        if count == 0:
            return jsonify({'purged': 0, 'message': 'No matching assets to purge'})
        
        # Delete
        conn.execute(f"DELETE FROM models WHERE {where_clause}", params)
        conn.commit()
        
        return jsonify({'purged': count})


@models_bp.route('/models/index-stats')
def api_index_stats():
    """Get indexing statistics."""
    with get_connection() as conn:
        stats = {}
        
        # Total counts
        stats['total'] = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        
        # By status
        rows = conn.execute("""
            SELECT index_status, COUNT(*) as count 
            FROM models 
            GROUP BY index_status
        """).fetchall()
        stats['by_status'] = {row['index_status'] or 'null': row['count'] for row in rows}
        
        # Hash coverage
        stats['with_hash'] = conn.execute(
            "SELECT COUNT(*) FROM models WHERE partial_hash IS NOT NULL"
        ).fetchone()[0]
        
        # Thumbnail stats
        stats['with_thumbnail'] = conn.execute(
            "SELECT COUNT(*) FROM models WHERE thumb_storage IS NOT NULL"
        ).fetchone()[0]
        
        # Missing count
        stats['missing_count'] = conn.execute(
            "SELECT COUNT(*) FROM models WHERE index_status = 'missing'"
        ).fetchone()[0]
        
        # Offline count
        stats['offline_count'] = conn.execute(
            "SELECT COUNT(*) FROM models WHERE index_status = 'offline'"
        ).fetchone()[0]
        
        return jsonify(stats)


@models_bp.route('/volumes')
def api_list_volumes():
    """List all registered volumes."""
    with get_connection() as conn:
        volumes = conn.execute("""
            SELECT v.*,
                   (SELECT COUNT(*) FROM models WHERE volume_id = v.id) as model_count,
                   (SELECT COUNT(*) FROM models WHERE volume_id = v.id AND index_status = 'missing') as missing_count,
                   (SELECT COUNT(*) FROM assets WHERE volume_id = v.id) as asset_count
            FROM volumes v
            ORDER BY v.label
        """).fetchall()
        
        return jsonify([dict(v) for v in volumes])


@models_bp.route('/volumes/<volume_id>/check', methods=['POST'])
def api_check_volume(volume_id):
    """Check if a volume is online and update status."""
    from pathlib import Path
    from datetime import datetime
    
    with get_connection() as conn:
        volume = conn.execute(
            "SELECT * FROM volumes WHERE id = ?",
            (volume_id,)
        ).fetchone()
        
        if not volume:
            return jsonify({'error': 'Volume not found'}), 404
        
        volume = dict(volume)
        mount_path = Path(volume['mount_path'])
        
        was_online = volume['status'] == 'online'
        is_online = mount_path.exists() and mount_path.is_dir()
        
        # Update status
        new_status = 'online' if is_online else 'offline'
        conn.execute("""
            UPDATE volumes SET 
                status = ?,
                last_seen_at = CASE WHEN ? THEN ? ELSE last_seen_at END
            WHERE id = ?
        """, (
            new_status,
            is_online,
            datetime.now().isoformat(),
            volume_id
        ))
        
        # If status changed, update assets
        if was_online and not is_online:
            # Volume went offline
            affected = conn.execute("""
                UPDATE models SET index_status = 'offline'
                WHERE volume_id = ? AND index_status = 'indexed'
            """, (volume_id,)).rowcount
        elif not was_online and is_online:
            # Volume came online - queue verification
            affected = conn.execute("""
                SELECT COUNT(*) FROM models 
                WHERE volume_id = ? AND index_status IN ('offline', 'missing')
            """, (volume_id,)).fetchone()[0]
        else:
            affected = 0
        
        conn.commit()
        
        return jsonify({
            'status': new_status,
            'was_online': was_online,
            'is_online': is_online,
            'assets_affected': affected
        })


@models_bp.route('/volumes/<volume_id>/verify', methods=['POST'])
def api_verify_volume(volume_id):
    """Verify all assets on a volume exist."""
    from fantasyfolio.core.scanner import verify_assets_on_volume
    
    with get_connection() as conn:
        # Check volume exists and is online
        volume = conn.execute(
            "SELECT * FROM volumes WHERE id = ?",
            (volume_id,)
        ).fetchone()
        
        if not volume:
            return jsonify({'error': 'Volume not found'}), 404
        
        if volume['status'] != 'online':
            return jsonify({'error': 'Volume is offline'}), 400
        
        stats = verify_assets_on_volume(conn, volume_id)
        
        return jsonify(stats)


@models_bp.route('/index/directory', methods=['POST'])
def api_index_directory():
    """
    Index a directory using the efficient scanner.
    
    POST body:
        path: Required - directory path to scan
        recursive: bool - include subdirectories (default true)
        force: bool - force re-index (default false)
    
    Returns scan statistics.
    """
    from pathlib import Path
    from fantasyfolio.core.scanner import scan_directory, ScanAction
    
    data = request.get_json() or {}
    path = data.get('path')
    recursive = data.get('recursive', True)
    force = data.get('force', False)
    
    if not path:
        return jsonify({'error': 'path is required'}), 400
    
    scan_path = Path(path).resolve()
    if not scan_path.exists():
        return jsonify({'error': f'Path does not exist: {path}'}), 404
    
    with get_connection() as conn:
        # Auto-detect volume
        volume = conn.execute("""
            SELECT * FROM volumes 
            WHERE ? LIKE mount_path || '%'
            ORDER BY length(mount_path) DESC
            LIMIT 1
        """, (str(scan_path),)).fetchone()
        
        if not volume:
            return jsonify({'error': 'No volume found for path'}), 400
        
        volume = dict(volume)
        
        stats = {
            'new': 0, 'update': 0, 'skip': 0,
            'moved': 0, 'missing': 0, 'error': 0
        }
        
        for result in scan_directory(conn, scan_path, volume, force=force, recursive=recursive):
            stats[result.action.value] += 1
            
            # Apply changes
            if result.action in (ScanAction.NEW, ScanAction.UPDATE, ScanAction.MOVED):
                model = result.model
                
                if result.action == ScanAction.NEW:
                    columns = ', '.join(model.keys())
                    placeholders = ', '.join(['?' for _ in model])
                    conn.execute(
                        f"INSERT INTO models ({columns}) VALUES ({placeholders})",
                        list(model.values())
                    )
                else:
                    model_id = model.pop('id', None)
                    if model_id:
                        sets = ', '.join([f"{k} = ?" for k in model.keys()])
                        conn.execute(
                            f"UPDATE models SET {sets} WHERE id = ?",
                            list(model.values()) + [model_id]
                        )
        
        conn.commit()
        
        stats['total'] = sum(stats.values())
        stats['volume_id'] = volume['id']
        stats['path'] = str(scan_path)
        
        return jsonify(stats)


@models_bp.route('/volumes/<volume_id>/index', methods=['POST'])
def api_index_volume(volume_id):
    """
    Index an entire volume.
    
    POST body:
        force: bool - force re-index (default false)
    """
    data = request.get_json() or {}
    force = data.get('force', False)
    
    with get_connection() as conn:
        volume = conn.execute(
            "SELECT * FROM volumes WHERE id = ?",
            (volume_id,)
        ).fetchone()
        
        if not volume:
            return jsonify({'error': 'Volume not found'}), 404
        
        volume = dict(volume)
        
        if volume['status'] != 'online':
            return jsonify({'error': 'Volume is offline'}), 400
    
    # Delegate to directory index
    return api_index_directory_internal(volume['mount_path'], force=force)


@models_bp.route('/models/<int:model_id>/regenerate-thumbnail', methods=['POST'])
def api_regenerate_thumbnail(model_id):
    """
    Regenerate thumbnail for a single model.
    
    POST body:
        force: bool - Force regenerate even if exists
    """
    from pathlib import Path
    from fantasyfolio.core.thumbnails import render_thumbnail
    
    data = request.get_json() or {}
    force = data.get('force', True)
    
    config = get_config()
    central_dir = Path(config.THUMBNAIL_DIR)
    
    with get_connection() as conn:
        model = conn.execute(
            "SELECT * FROM models WHERE id = ?",
            (model_id,)
        ).fetchone()
        
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        model = dict(model)
        # No volume relationship in this schema - pass empty volume
        volume = {'id': None, 'mount_path': None, 'is_readonly': True}
        
        result = render_thumbnail(model, volume, central_dir, force=force)
        
        if result:
            conn.execute(
                "UPDATE models SET has_thumbnail = 1 WHERE id = ?",
                (model_id,)
            )
            conn.commit()
            return jsonify({
                'status': 'rendered',
                **result
            })
        else:
            return jsonify({'status': 'failed', 'message': 'Could not render thumbnail'}), 500


@models_bp.route('/thumbnails/render/pending', methods=['POST'])
def api_render_pending_thumbnails():
    """
    Render thumbnails for models that don't have them.
    
    POST body:
        limit: int - Max to render (default 100)
    """
    from pathlib import Path
    from fantasyfolio.core.thumbnails import render_pending_thumbnails
    
    data = request.get_json() or {}
    limit = data.get('limit', 100)
    
    config = get_config()
    central_dir = Path(config.DATA_DIR) / 'thumbnails'
    
    with get_connection() as conn:
        stats = render_pending_thumbnails(conn, central_dir, limit=limit)
    
    return jsonify(stats)


@models_bp.route('/thumbnails/migrate', methods=['POST'])
def api_migrate_thumbnails():
    """
    Migrate central thumbnails to sidecar locations.
    
    POST body:
        limit: int - Max to migrate (default all)
    """
    from pathlib import Path
    from fantasyfolio.core.thumbnails import migrate_thumbnails_to_sidecars
    
    data = request.get_json() or {}
    limit = data.get('limit')
    
    config = get_config()
    central_dir = Path(config.DATA_DIR) / 'thumbnails'
    
    with get_connection() as conn:
        stats = migrate_thumbnails_to_sidecars(conn, central_dir, limit=limit)
    
    return jsonify(stats)


def api_index_directory_internal(path: str, force: bool = False):
    """Internal helper for indexing."""
    from pathlib import Path
    from fantasyfolio.core.scanner import scan_directory, ScanAction
    
    scan_path = Path(path).resolve()
    
    with get_connection() as conn:
        volume = conn.execute("""
            SELECT * FROM volumes 
            WHERE ? LIKE mount_path || '%'
            ORDER BY length(mount_path) DESC
            LIMIT 1
        """, (str(scan_path),)).fetchone()
        
        if not volume:
            return jsonify({'error': 'No volume found'}), 400
        
        volume = dict(volume)
        
        stats = {
            'new': 0, 'update': 0, 'skip': 0,
            'moved': 0, 'missing': 0, 'error': 0
        }
        
        for result in scan_directory(conn, scan_path, volume, force=force, recursive=True):
            stats[result.action.value] += 1
            
            if result.action in (ScanAction.NEW, ScanAction.UPDATE, ScanAction.MOVED):
                model = result.model
                
                if result.action == ScanAction.NEW:
                    columns = ', '.join(model.keys())
                    placeholders = ', '.join(['?' for _ in model])
                    conn.execute(
                        f"INSERT INTO models ({columns}) VALUES ({placeholders})",
                        list(model.values())
                    )
                else:
                    model_id = model.pop('id', None)
                    if model_id:
                        sets = ', '.join([f"{k} = ?" for k in model.keys()])
                        conn.execute(
                            f"UPDATE models SET {sets} WHERE id = ?",
                            list(model.values()) + [model_id]
                        )
        
        conn.commit()
        
        stats['total'] = sum(stats.values())
        return jsonify(stats)
