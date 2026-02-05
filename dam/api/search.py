"""
Search API Blueprint.

Handles full-text search across assets and 3D models.
"""

import logging
from flask import Blueprint, jsonify, request

from dam.core.database import get_connection, search_assets, search_models

logger = logging.getLogger(__name__)
search_bp = Blueprint('search', __name__)


@search_bp.route('/search')
def api_search():
    """
    Unified search across all asset types.
    
    Query params:
    - q: Search query
    - type: Asset type filter (pdf, 3d, all)
    - limit: Max results (default 50)
    - offset: Pagination offset
    """
    query = request.args.get('q', '').strip()
    asset_type = request.args.get('type', 'all')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    results = {
        'query': query,
        'assets': [],
        'models': [],
        'total': 0
    }
    
    if asset_type in ('pdf', 'all'):
        results['assets'] = search_assets(query, limit=limit, offset=offset)
    
    if asset_type in ('3d', 'all'):
        results['models'] = search_models(query, limit=limit)
    
    results['total'] = len(results['assets']) + len(results['models'])
    
    return jsonify(results)


@search_bp.route('/search/assets')
def api_search_assets():
    """Search PDF assets with advanced filtering."""
    query = request.args.get('q', '').strip()
    folder = request.args.get('folder')
    publisher = request.args.get('publisher')
    game_system = request.args.get('game_system')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    with get_connection() as conn:
        if query:
            # Full-text search with filters
            sql = """
                SELECT a.*, snippet(assets_fts, 0, '<mark>', '</mark>', '...', 32) as snippet
                FROM assets a
                JOIN assets_fts ON a.id = assets_fts.rowid
                WHERE assets_fts MATCH ?
            """
            params = [query]
        else:
            sql = "SELECT * FROM assets WHERE 1=1"
            params = []
        
        if folder:
            sql += " AND folder_path LIKE ?"
            params.append(folder + '%')
        if publisher:
            sql += " AND publisher = ?"
            params.append(publisher)
        if game_system:
            sql += " AND game_system = ?"
            params.append(game_system)
        
        sql += " ORDER BY filename LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(row) for row in rows])


@search_bp.route('/search/models')
def api_search_models():
    """Search 3D models with advanced filtering."""
    query = request.args.get('q', '').strip()
    folder = request.args.get('folder')
    collection = request.args.get('collection')
    creator = request.args.get('creator')
    format_filter = request.args.get('format')
    limit = int(request.args.get('limit', 50))
    
    with get_connection() as conn:
        if query:
            sql = """
                SELECT m.* FROM models m
                JOIN models_fts ON m.id = models_fts.rowid
                WHERE models_fts MATCH ?
            """
            params = [query]
        else:
            sql = "SELECT * FROM models WHERE 1=1"
            params = []
        
        if folder:
            sql += " AND folder_path LIKE ?"
            params.append(folder + '%')
        if collection:
            sql += " AND collection = ?"
            params.append(collection)
        if creator:
            sql += " AND creator = ?"
            params.append(creator)
        if format_filter:
            sql += " AND format = ?"
            params.append(format_filter)
        
        sql += " ORDER BY collection, filename LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(row) for row in rows])


@search_bp.route('/search/pages')
def api_search_pages():
    """
    Search within PDF page contents.
    Returns matching pages with context snippets.
    """
    query = request.args.get('q', '').strip()
    asset_id = request.args.get('asset_id')
    limit = int(request.args.get('limit', 50))
    
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    with get_connection() as conn:
        sql = """
            SELECT 
                p.id,
                p.asset_id,
                p.page_num,
                a.filename,
                a.title,
                snippet(pages_fts, 0, '<mark>', '</mark>', '...', 32) as snippet
            FROM asset_pages p
            JOIN pages_fts ON p.id = pages_fts.rowid
            JOIN assets a ON p.asset_id = a.id
            WHERE pages_fts MATCH ?
        """
        params = [query]
        
        if asset_id:
            sql += " AND p.asset_id = ?"
            params.append(asset_id)
        
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(row) for row in rows])
