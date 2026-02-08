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

from dam.core.database import get_connection, get_models_stats, get_model_by_id
from dam.config import get_config

logger = logging.getLogger(__name__)
models_bp = Blueprint('models', __name__)


@models_bp.route('/models')
def api_models():
    """List 3D models with optional filters."""
    folder = request.args.get('folder')
    collection = request.args.get('collection')
    format_filter = request.args.get('format')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
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
        
        query += " ORDER BY collection, filename LIMIT ? OFFSET ?"
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
    """Search 3D models (legacy endpoint)."""
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 50))
    
    if not query:
        return jsonify([])
    
    from dam.core.database import search_models
    return jsonify(search_models(query, limit=limit))


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
                from dam.indexer.thumbnails import render_3d_thumbnail
                
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
    from dam.services.volume_monitor import check_volume_for_path
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
    """Get thumbnail cache statistics."""
    config = get_config()
    thumbnail_dir = Path(config.THUMBNAIL_DIR) / "3d"
    
    with get_connection() as conn:
        # Count total models
        total = conn.execute("SELECT COUNT(*) as cnt FROM models").fetchone()['cnt']
        
        # Count cached thumbnails
        if thumbnail_dir.exists():
            cached = len(list(thumbnail_dir.glob("*.png")))
        else:
            cached = 0
    
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
    from dam.indexer.thumbnails import render_3d_thumbnail
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
