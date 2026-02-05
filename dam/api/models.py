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
    
    # Try to get preview from archive
    if model.get('archive_path') and model.get('preview_image'):
        try:
            with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                img_data = zf.read(model['preview_image'])
                ext = Path(model['preview_image']).suffix.lower()
                mime = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.webp': 'image/webp',
                }.get(ext, 'image/jpeg')
                return send_file(io.BytesIO(img_data), mimetype=mime)
        except Exception as e:
            logger.debug(f"Failed to get preview from archive: {e}")
    
    # Try standalone preview file
    if model.get('preview_image') and os.path.exists(model['preview_image']):
        return send_file(model['preview_image'])
    
    # Try to render STL thumbnail
    if model.get('format') == 'stl':
        try:
            from dam.indexer.thumbnails import render_stl_thumbnail
            
            # Get STL data
            if model.get('archive_path') and model.get('archive_member'):
                with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                    stl_data = zf.read(model['archive_member'])
            elif os.path.exists(model['file_path']):
                with open(model['file_path'], 'rb') as f:
                    stl_data = f.read()
            else:
                raise FileNotFoundError("Model file not found")
            
            png_data = render_stl_thumbnail(stl_data, str(cached_thumb))
            return send_file(io.BytesIO(png_data), mimetype='image/png')
        except Exception as e:
            logger.error(f"Thumbnail render error for model {model_id}: {e}")
    
    # Return placeholder
    placeholder = config.STATIC_DIR / 'placeholder-3d.svg'
    if placeholder.exists():
        return send_file(placeholder, mimetype='image/svg+xml')
    
    return jsonify({'error': 'No preview available'}), 404


@models_bp.route('/models/<int:model_id>/stl')
def api_model_stl(model_id: int):
    """Serve STL file for 3D viewer (handles ZIP extraction)."""
    model = get_model_by_id(model_id)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    try:
        if model.get('archive_path') and model.get('archive_member'):
            # Extract from ZIP
            with zipfile.ZipFile(model['archive_path'], 'r') as zf:
                stl_data = zf.read(model['archive_member'])
            return send_file(
                io.BytesIO(stl_data),
                mimetype='application/octet-stream',
                download_name=model['filename']
            )
        elif os.path.exists(model['file_path']):
            return send_file(model['file_path'])
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"STL serve error for model {model_id}: {e}")
        return jsonify({'error': 'Failed to serve file'}), 500


@models_bp.route('/models/<int:model_id>/download')
def api_model_download(model_id: int):
    """Download the original model file."""
    model = get_model_by_id(model_id)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    try:
        if model.get('archive_path') and model.get('archive_member'):
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
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error for model {model_id}: {e}")
        return jsonify({'error': 'Download failed'}), 500
