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


# ==================== Legacy Path Compatibility ====================
# These endpoints maintain compatibility with the original API paths
# that the frontend template expects

@assets_bp.route('/folder-tree')
def api_folder_tree():
    """Get hierarchical folder tree for PDF navigation."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT folder_path, COUNT(*) as count
            FROM assets
            WHERE folder_path IS NOT NULL AND folder_path != ''
            GROUP BY folder_path
            ORDER BY folder_path
        """).fetchall()
        
        # Build tree structure
        tree = {}
        for row in rows:
            path = row['folder_path']
            count = row['count']
            parts = path.split('/')
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {'_count': 0, '_children': {}}
                current[part]['_count'] += count
                current = current[part]['_children']
        
        return jsonify({'tree': tree, 'flat': [dict(row) for row in rows]})


@assets_bp.route('/thumbnail/<int:asset_id>')
def api_thumbnail_legacy(asset_id: int):
    """Legacy path for thumbnails."""
    return api_asset_thumbnail(asset_id)


@assets_bp.route('/render/<int:asset_id>/<int:page_num>')
def api_render_legacy(asset_id: int, page_num: int):
    """Legacy path for page rendering."""
    return api_render_page(asset_id, page_num)


@assets_bp.route('/download/<int:asset_id>')
def api_download_legacy(asset_id: int):
    """Legacy path for downloads."""
    return api_download_asset(asset_id)


@assets_bp.route('/pdf/<int:asset_id>')
def api_serve_pdf(asset_id: int):
    """Serve the raw PDF file for in-browser viewing."""
    asset = get_asset_by_id(asset_id)
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    file_path = Path(asset['file_path'])
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        file_path,
        mimetype='application/pdf',
        download_name=asset['filename']
    )


@assets_bp.route('/extract-pages/<int:asset_id>', methods=['POST'])
def api_extract_pages(asset_id: int):
    """Extract a range of pages from a PDF as a new file."""
    asset = get_asset_by_id(asset_id)
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    start_page = data.get('start', 1)
    end_page = data.get('end')
    
    try:
        import pymupdf
        doc = pymupdf.open(asset['file_path'])
        
        if end_page is None:
            end_page = len(doc)
        
        # Validate range
        if start_page < 1 or end_page > len(doc) or start_page > end_page:
            doc.close()
            return jsonify({'error': 'Invalid page range'}), 400
        
        # Create new PDF with selected pages
        new_doc = pymupdf.open()
        new_doc.insert_pdf(doc, from_page=start_page-1, to_page=end_page-1)
        
        # Save to bytes
        pdf_bytes = new_doc.tobytes()
        new_doc.close()
        doc.close()
        
        filename = f"{Path(asset['filename']).stem}_pages_{start_page}-{end_page}.pdf"
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Page extraction failed: {e}")
        return jsonify({'error': str(e)}), 500
