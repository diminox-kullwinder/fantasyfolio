"""
PDF Assets API Blueprint.

Handles all PDF-related endpoints: listing, details, thumbnails,
page rendering, and bookmarks.
"""

import io
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file, current_app

from dam.core.database import (
    get_stats, list_assets, get_asset_by_id, get_folder_tree,
    get_connection
)
from dam.config import get_config

logger = logging.getLogger(__name__)
assets_bp = Blueprint('assets', __name__)


@assets_bp.route('/stats')
def api_stats():
    """Get overall database statistics."""
    return jsonify(get_stats())


@assets_bp.route('/assets')
def api_assets():
    """List assets with optional filters."""
    folder = request.args.get('folder')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    assets = list_assets(folder=folder, limit=limit, offset=offset)
    return jsonify(assets)


@assets_bp.route('/assets/<int:asset_id>')
def api_asset(asset_id: int):
    """Get a single asset by ID."""
    asset = get_asset_by_id(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    return jsonify(asset)


@assets_bp.route('/folders')
def api_folders():
    """Get folder tree for navigation."""
    return jsonify(get_folder_tree())


@assets_bp.route('/assets/<int:asset_id>/thumbnail')
def api_asset_thumbnail(asset_id: int):
    """Get thumbnail for an asset."""
    config = get_config()
    asset = get_asset_by_id(asset_id)
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    # Check for cached thumbnail
    thumb_path = config.THUMBNAIL_DIR / "pdf" / f"{asset_id}.png"
    if thumb_path.exists():
        return send_file(thumb_path, mimetype='image/png')
    
    # Generate thumbnail on-the-fly
    try:
        import pymupdf
        doc = pymupdf.open(asset['file_path'])
        page = doc[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5))
        
        # Save to cache
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(thumb_path))
        doc.close()
        
        return send_file(thumb_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Thumbnail generation failed for asset {asset_id}: {e}")
        return jsonify({'error': 'Thumbnail generation failed'}), 500


@assets_bp.route('/assets/<int:asset_id>/render/<int:page_num>')
def api_render_page(asset_id: int, page_num: int):
    """Render a specific page as an image."""
    asset = get_asset_by_id(asset_id)
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    zoom = float(request.args.get('zoom', 1.5))
    
    try:
        import pymupdf
        doc = pymupdf.open(asset['file_path'])
        
        if page_num < 1 or page_num > len(doc):
            doc.close()
            return jsonify({'error': 'Invalid page number'}), 400
        
        page = doc[page_num - 1]  # 0-indexed
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img_bytes = pix.tobytes("png")
        doc.close()
        
        return send_file(
            io.BytesIO(img_bytes),
            mimetype='image/png',
            download_name=f"{asset['filename']}_page{page_num}.png"
        )
    except Exception as e:
        logger.error(f"Page render failed for asset {asset_id}, page {page_num}: {e}")
        return jsonify({'error': 'Page render failed'}), 500


@assets_bp.route('/assets/<int:asset_id>/download')
def api_download_asset(asset_id: int):
    """Download the original asset file."""
    asset = get_asset_by_id(asset_id)
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    file_path = Path(asset['file_path'])
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=asset['filename']
    )


@assets_bp.route('/assets/<int:asset_id>/bookmarks')
def api_asset_bookmarks(asset_id: int):
    """Get bookmarks/TOC for an asset."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT level, title, page_num
            FROM asset_bookmarks
            WHERE asset_id = ?
            ORDER BY id
        """, (asset_id,)).fetchall()
        return jsonify([dict(row) for row in rows])


@assets_bp.route('/assets/<int:asset_id>/pages')
def api_asset_pages(asset_id: int):
    """Get text content for all pages of an asset."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT page_num, text_content
            FROM asset_pages
            WHERE asset_id = ?
            ORDER BY page_num
        """, (asset_id,)).fetchall()
        return jsonify([dict(row) for row in rows])


@assets_bp.route('/publishers')
def api_publishers():
    """Get list of unique publishers."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT publisher, COUNT(*) as count
            FROM assets
            WHERE publisher IS NOT NULL AND publisher != ''
            GROUP BY publisher
            ORDER BY count DESC
        """).fetchall()
        return jsonify([dict(row) for row in rows])


@assets_bp.route('/game-systems')
def api_game_systems():
    """Get list of unique game systems."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT game_system, COUNT(*) as count
            FROM assets
            WHERE game_system IS NOT NULL AND game_system != ''
            GROUP BY game_system
            ORDER BY count DESC
        """).fetchall()
        return jsonify([dict(row) for row in rows])
