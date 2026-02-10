"""Core modules for FantasyFolio."""

from fantasyfolio.core.database import (
    # Database management
    get_db, init_db, get_connection,
    
    # Asset operations
    get_stats, search_assets, get_asset_by_id, list_assets,
    get_folder_tree, insert_asset, get_asset_by_path,
    needs_reindex, delete_missing_assets, get_assets_without_text,
    
    # Page/text operations
    insert_page_text, get_pages_for_asset, search_pages,
    get_text_extraction_stats,
    
    # Bookmark operations
    insert_bookmarks, get_bookmarks, has_bookmarks,
    
    # 3D model operations
    get_models_stats, search_models, get_model_by_id, insert_model,
    
    # Settings
    get_setting, set_setting, get_all_settings, set_multiple_settings,
    
    # Metadata
    get_publishers
)

__all__ = [
    'get_db', 'init_db', 'get_connection',
    'get_stats', 'search_assets', 'get_asset_by_id', 'list_assets',
    'get_folder_tree', 'insert_asset', 'get_asset_by_path',
    'needs_reindex', 'delete_missing_assets', 'get_assets_without_text',
    'insert_page_text', 'get_pages_for_asset', 'search_pages',
    'get_text_extraction_stats',
    'insert_bookmarks', 'get_bookmarks', 'has_bookmarks',
    'get_models_stats', 'search_models', 'get_model_by_id', 'insert_model',
    'get_setting', 'set_setting', 'get_all_settings', 'set_multiple_settings',
    'get_publishers'
]
