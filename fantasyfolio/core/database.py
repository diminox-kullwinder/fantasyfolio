"""
Database access layer for FantasyFolio.

Provides connection management, initialization, and core query functions.
Uses SQLite with WAL mode for better concurrency.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from contextlib import contextmanager

from fantasyfolio.config import get_config

logger = logging.getLogger(__name__)

# Schema path
SCHEMA_PATH = Path(__file__).parent.parent.parent / "data" / "schema.sql"


class Database:
    """Database manager class."""
    
    def __init__(self, db_path: Optional[Path] = None):
        config = get_config()
        self.db_path = db_path or config.DATABASE_PATH
        self.timeout = config.DATABASE_TIMEOUT
    
    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self, schema_path: Optional[Path] = None):
        """Initialize the database with schema."""
        schema_path = schema_path or SCHEMA_PATH
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if database already exists
        db_exists = self.db_path.exists()
        if db_exists:
            db_size = self.db_path.stat().st_size
            logger.info(f"Using existing database: {self.db_path} ({db_size / (1024*1024):.1f} MB)")
            
            # Safety check: if database is suspiciously small, warn loudly
            if db_size < 100_000_000:  # Less than 100MB
                logger.warning(f"⚠️  Database is only {db_size / (1024*1024):.1f}MB. "
                             f"Expected ~1.2GB for LIVE database. "
                             f"Check DAM_DATABASE_PATH in .env.local")
        else:
            with open(schema_path, 'r') as f:
                schema = f.read()
            
            with self.connection() as conn:
                conn.executescript(schema)
                conn.commit()
        
        logger.info(f"Database ready at {self.db_path}")
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor
    
    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and fetch one row as dict."""
        with self.connection() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None
    
    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and fetch all rows as list of dicts."""
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def init_db():
    """Initialize the database."""
    get_db().init_db()


@contextmanager
def get_connection():
    """Convenience function for getting a database connection."""
    with get_db().connection() as conn:
        yield conn


# ==================== Asset Operations ====================

def get_stats(include_deleted: bool = False) -> Dict[str, Any]:
    """Get overall database statistics.
    
    Args:
        include_deleted: If True, include soft-deleted records in counts
    """
    db = get_db()
    deleted_filter = "" if include_deleted else "WHERE deleted_at IS NULL"
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM assets {deleted_filter}").fetchone()[0]
        total_size = conn.execute(f"SELECT SUM(file_size) FROM assets {deleted_filter}").fetchone()[0] or 0
        publishers = conn.execute(f"SELECT COUNT(DISTINCT publisher) FROM assets {deleted_filter}").fetchone()[0]
        
        # Count deleted (for trash indicator)
        deleted_count = conn.execute("SELECT COUNT(*) FROM assets WHERE deleted_at IS NOT NULL").fetchone()[0]
        
        return {
            "total_assets": total,
            "total_size_bytes": total_size,
            "unique_publishers": publishers,
            "deleted_count": deleted_count
        }


def search_assets(query: str, limit: int = 50, offset: int = 0, include_deleted: bool = False) -> List[Dict[str, Any]]:
    """Search assets using full-text search with prefix matching.
    
    Args:
        query: Search query
        limit: Maximum results
        offset: Pagination offset
        include_deleted: If True, include soft-deleted records
    """
    db = get_db()
    # Add wildcard for prefix matching (e.g., "drag" matches "dragon")
    # Split into terms and add * to each for prefix matching
    terms = query.strip().split()
    fts_query = ' '.join(f'{term}*' for term in terms if term)
    
    deleted_filter = "" if include_deleted else "AND a.deleted_at IS NULL"
    
    with db.connection() as conn:
        rows = conn.execute(f"""
            SELECT a.*, highlight(assets_fts, 0, '<mark>', '</mark>') as highlight
            FROM assets a
            JOIN assets_fts ON a.id = assets_fts.rowid
            WHERE assets_fts MATCH ?
            {deleted_filter}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, (fts_query, limit, offset)).fetchall()
        return [dict(row) for row in rows]


def get_asset_by_id(asset_id: int) -> Optional[Dict[str, Any]]:
    """Get a single asset by ID."""
    return get_db().fetchone("SELECT * FROM assets WHERE id = ?", (asset_id,))


def list_assets(folder: Optional[str] = None, limit: int = 100, offset: int = 0, include_deleted: bool = False, sort: str = 'filename', order: str = 'asc') -> List[Dict[str, Any]]:
    """List assets with optional folder filter and sorting.
    
    Args:
        folder: Filter by folder path prefix
        limit: Maximum results
        offset: Pagination offset
        include_deleted: If True, include soft-deleted records
        sort: Column to sort by
        order: Sort order (asc or desc)
    """
    # Validate sort column to prevent SQL injection
    valid_sorts = {'filename', 'title', 'file_size', 'page_count', 'publisher', 'created_at', 'modified_at'}
    if sort not in valid_sorts:
        sort = 'filename'
    
    # Validate order
    order_sql = 'DESC' if order.lower() == 'desc' else 'ASC'
    
    db = get_db()
    deleted_filter = "deleted_at IS NULL" if not include_deleted else "1=1"
    with db.connection() as conn:
        if folder:
            rows = conn.execute(
                f"SELECT * FROM assets WHERE folder_path LIKE ? AND {deleted_filter} ORDER BY {sort} {order_sql} LIMIT ? OFFSET ?",
                (folder + '%', limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM assets WHERE {deleted_filter} ORDER BY {sort} {order_sql} LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]


def get_folder_tree(include_deleted: bool = False) -> List[Dict[str, Any]]:
    """Get folder structure for navigation.
    
    Args:
        include_deleted: If True, include soft-deleted records in counts
    """
    db = get_db()
    deleted_filter = "AND deleted_at IS NULL" if not include_deleted else ""
    with db.connection() as conn:
        rows = conn.execute(f"""
            SELECT folder_path, COUNT(*) as count
            FROM assets
            WHERE folder_path IS NOT NULL AND folder_path != ''
            {deleted_filter}
            GROUP BY folder_path
            ORDER BY folder_path
        """).fetchall()
        return [dict(row) for row in rows]


def insert_asset(asset: Dict[str, Any]) -> int:
    """Insert a new asset, return its ID."""
    db = get_db()
    with db.connection() as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO assets (
                file_path, filename, title, author, publisher,
                page_count, file_size, file_hash, created_at, modified_at,
                pdf_creator, pdf_producer, pdf_creation_date, pdf_mod_date,
                folder_path, game_system, category, tags,
                thumbnail_path, has_thumbnail
            ) VALUES (
                :file_path, :filename, :title, :author, :publisher,
                :page_count, :file_size, :file_hash, :created_at, :modified_at,
                :pdf_creator, :pdf_producer, :pdf_creation_date, :pdf_mod_date,
                :folder_path, :game_system, :category, :tags,
                :thumbnail_path, :has_thumbnail
            )
        """, asset)
        conn.commit()
        return cursor.lastrowid


# ==================== 3D Model Operations ====================

def get_models_stats(include_deleted: bool = False) -> Dict[str, Any]:
    """Get 3D model statistics.
    
    Args:
        include_deleted: If True, include soft-deleted records in counts
    """
    db = get_db()
    deleted_filter = "WHERE deleted_at IS NULL" if not include_deleted else ""
    deleted_filter_and = "AND deleted_at IS NULL" if not include_deleted else ""
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM models {deleted_filter}").fetchone()[0]
        by_format = conn.execute(
            f"SELECT format, COUNT(*) as count FROM models {deleted_filter} GROUP BY format"
        ).fetchall()
        collections = conn.execute(
            f"SELECT COUNT(DISTINCT collection) FROM models {deleted_filter}"
        ).fetchone()[0]
        total_size = conn.execute(
            f"SELECT SUM(file_size) FROM models {deleted_filter}"
        ).fetchone()[0] or 0
        
        # Count deleted (for trash indicator)
        deleted_count = conn.execute("SELECT COUNT(*) FROM models WHERE deleted_at IS NOT NULL").fetchone()[0]
        
        return {
            'total_models': total,
            'by_format': {row['format']: row['count'] for row in by_format},
            'collections': collections,
            'total_size_mb': round(total_size / (1024*1024), 2),
            'deleted_count': deleted_count
        }


def search_models(query: str, limit: int = 50, include_deleted: bool = False) -> List[Dict[str, Any]]:
    """Search 3D models using full-text search with prefix matching.
    
    Args:
        query: Search query
        limit: Maximum results
        include_deleted: If True, include soft-deleted records
    """
    db = get_db()
    # Add wildcard for prefix matching (e.g., "robo" matches "robot")
    terms = query.strip().split()
    fts_query = ' '.join(f'{term}*' for term in terms if term)
    
    deleted_filter = "AND m.deleted_at IS NULL" if not include_deleted else ""
    
    with db.connection() as conn:
        rows = conn.execute(f"""
            SELECT m.* FROM models m
            JOIN models_fts ON m.id = models_fts.rowid
            WHERE models_fts MATCH ?
            {deleted_filter}
            LIMIT ?
        """, (fts_query, limit)).fetchall()
        return [dict(row) for row in rows]


def get_model_by_id(model_id: int) -> Optional[Dict[str, Any]]:
    """Get a single 3D model by ID."""
    return get_db().fetchone("SELECT * FROM models WHERE id = ?", (model_id,))


def insert_model(model: Dict[str, Any]) -> int:
    """Insert a new 3D model, return its ID."""
    db = get_db()
    with db.connection() as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO models (
                file_path, filename, title, format, file_size, file_hash,
                archive_path, archive_member, folder_path, collection, creator,
                vertex_count, face_count, has_supports, preview_image,
                has_thumbnail, created_at, modified_at
            ) VALUES (
                :file_path, :filename, :title, :format, :file_size, :file_hash,
                :archive_path, :archive_member, :folder_path, :collection, :creator,
                :vertex_count, :face_count, :has_supports, :preview_image,
                :has_thumbnail, :created_at, :modified_at
            )
        """, model)
        conn.commit()
        return cursor.lastrowid


# ==================== Settings Operations ====================

def get_setting(key: str) -> Optional[str]:
    """Get a setting value."""
    row = get_db().fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return row['value'] if row else None


def set_setting(key: str, value: str):
    """Set a setting value."""
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value)
        )
        conn.commit()


def get_all_settings() -> Dict[str, str]:
    """Get all settings as a dictionary."""
    rows = get_db().fetchall("SELECT key, value FROM settings")
    return {row['key']: row['value'] for row in rows}


def set_multiple_settings(settings: Dict[str, str]):
    """Set multiple settings at once."""
    db = get_db()
    with db.connection() as conn:
        for key, value in settings.items():
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, str(value))
            )
        conn.commit()


# ==================== Page/Text Operations ====================

def insert_page_text(asset_id: int, page_num: int, text: str):
    """Insert text content for a page."""
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO asset_pages (asset_id, page_num, text_content) VALUES (?, ?, ?)",
            (asset_id, page_num, text)
        )
        conn.commit()


def get_pages_for_asset(asset_id: int) -> List[Dict[str, Any]]:
    """Get all pages for an asset."""
    return get_db().fetchall(
        "SELECT page_num, text_content FROM asset_pages WHERE asset_id = ? ORDER BY page_num",
        (asset_id,)
    )


def search_pages(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search page content."""
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT p.asset_id, p.page_num, a.filename, a.title,
                   snippet(pages_fts, 0, '<mark>', '</mark>', '...', 32) as snippet
            FROM asset_pages p
            JOIN pages_fts ON p.id = pages_fts.rowid
            JOIN assets a ON p.asset_id = a.id
            WHERE pages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
        return [dict(row) for row in rows]


def get_text_extraction_stats(include_deleted: bool = False) -> Dict[str, Any]:
    """Get statistics about text extraction.
    
    Args:
        include_deleted: If True, include soft-deleted records in counts
    """
    db = get_db()
    deleted_filter = "WHERE deleted_at IS NULL" if not include_deleted else ""
    deleted_filter_and = "AND a.deleted_at IS NULL" if not include_deleted else ""
    with db.connection() as conn:
        total_assets = conn.execute(f"SELECT COUNT(*) FROM assets {deleted_filter}").fetchone()[0]
        with_text = conn.execute(f"""
            SELECT COUNT(DISTINCT p.asset_id) 
            FROM asset_pages p
            JOIN assets a ON p.asset_id = a.id
            WHERE p.text_content IS NOT NULL AND p.text_content != ''
            {deleted_filter_and}
        """).fetchone()[0]
        total_pages = conn.execute(f"""
            SELECT COUNT(*) 
            FROM asset_pages p
            JOIN assets a ON p.asset_id = a.id
            WHERE 1=1 {deleted_filter_and}
        """).fetchone()[0]
        
        return {
            'total_assets': total_assets,
            'assets_with_text': with_text,
            'assets_without_text': total_assets - with_text,
            'total_pages_indexed': total_pages
        }


# ==================== Bookmark Operations ====================

def insert_bookmarks(asset_id: int, bookmarks: List[tuple]):
    """Insert bookmarks for an asset. Each bookmark is (level, title, page_num)."""
    db = get_db()
    with db.connection() as conn:
        for level, title, page_num in bookmarks:
            conn.execute(
                "INSERT OR IGNORE INTO asset_bookmarks (asset_id, level, title, page_num) VALUES (?, ?, ?, ?)",
                (asset_id, level, title, page_num)
            )
        conn.commit()


def get_bookmarks(asset_id: int) -> List[Dict[str, Any]]:
    """Get bookmarks for an asset."""
    return get_db().fetchall(
        "SELECT level, title, page_num FROM asset_bookmarks WHERE asset_id = ? ORDER BY id",
        (asset_id,)
    )


def has_bookmarks(asset_id: int) -> bool:
    """Check if asset has bookmarks."""
    result = get_db().fetchone(
        "SELECT 1 FROM asset_bookmarks WHERE asset_id = ? LIMIT 1",
        (asset_id,)
    )
    return result is not None


# ==================== Incremental Indexing Support ====================

def get_asset_by_path(file_path: str) -> Optional[Dict[str, Any]]:
    """Get an asset by its file path."""
    return get_db().fetchone("SELECT * FROM assets WHERE file_path = ?", (file_path,))


def needs_reindex(file_path: str, modified_at: str) -> bool:
    """Check if a file needs to be re-indexed based on modification time."""
    existing = get_asset_by_path(file_path)
    if not existing:
        return True
    return existing.get('modified_at') != modified_at


def delete_missing_assets(existing_paths: set, soft_delete: bool = True) -> int:
    """Soft-delete (or hard-delete) assets whose files no longer exist.
    
    Args:
        existing_paths: Set of file paths that still exist
        soft_delete: If True (default), set deleted_at instead of hard delete
    
    Returns:
        Count of deleted/soft-deleted records
    """
    db = get_db()
    deleted = 0
    from datetime import datetime
    now = datetime.now().isoformat()
    
    with db.connection() as conn:
        # Only check non-deleted assets
        rows = conn.execute("SELECT id, file_path FROM assets WHERE deleted_at IS NULL").fetchall()
        for row in rows:
            if row['file_path'] not in existing_paths:
                if soft_delete:
                    conn.execute("UPDATE assets SET deleted_at = ? WHERE id = ?", (now, row['id']))
                else:
                    conn.execute("DELETE FROM assets WHERE id = ?", (row['id'],))
                deleted += 1
        conn.commit()
    return deleted


def soft_delete_asset(asset_id: int, source: str = 'api') -> bool:
    """Soft-delete an asset by setting deleted_at timestamp.
    
    Args:
        asset_id: ID of asset to delete
        source: Origin of deletion ('api', 'indexer', 'cleanup')
    
    Returns:
        True if asset was found and deleted, False otherwise
    """
    db = get_db()
    from datetime import datetime
    now = datetime.now().isoformat()
    
    with db.connection() as conn:
        cursor = conn.execute(
            "UPDATE assets SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, asset_id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            # Log to change journal
            try:
                from fantasyfolio.services.change_journal import log_asset_change
                log_asset_change(asset_id, 'trash', source=source)
            except Exception:
                pass  # Don't fail if journal logging fails
            return True
        return False


def restore_asset(asset_id: int, source: str = 'api') -> bool:
    """Restore a soft-deleted asset by clearing deleted_at.
    
    Returns:
        True if asset was found and restored, False otherwise
    """
    db = get_db()
    with db.connection() as conn:
        cursor = conn.execute(
            "UPDATE assets SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            (asset_id,)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            # Log to change journal
            try:
                from fantasyfolio.services.change_journal import log_asset_change
                log_asset_change(asset_id, 'restore', source=source)
            except Exception:
                pass
            return True
        return False


def get_deleted_assets(limit: int = 100) -> List[Dict[str, Any]]:
    """Get list of soft-deleted assets (Trash contents).
    
    Returns:
        List of deleted assets ordered by deletion time (newest first)
    """
    return get_db().fetchall("""
        SELECT * FROM assets 
        WHERE deleted_at IS NOT NULL 
        ORDER BY deleted_at DESC 
        LIMIT ?
    """, (limit,))


def permanently_delete_asset(asset_id: int) -> bool:
    """Permanently delete an asset (hard delete from database).
    
    Returns:
        True if asset was found and deleted, False otherwise
    """
    db = get_db()
    with db.connection() as conn:
        # Delete related records first
        conn.execute("DELETE FROM asset_pages WHERE asset_id = ?", (asset_id,))
        conn.execute("DELETE FROM asset_bookmarks WHERE asset_id = ?", (asset_id,))
        # Delete the asset
        cursor = conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.commit()
        return cursor.rowcount > 0


def empty_trash(older_than_days: Optional[int] = None) -> int:
    """Permanently delete all soft-deleted assets (or those older than N days).
    
    Args:
        older_than_days: If provided, only delete items deleted more than N days ago
    
    Returns:
        Count of permanently deleted records
    """
    db = get_db()
    with db.connection() as conn:
        if older_than_days is not None:
            # Delete items older than N days
            cursor = conn.execute("""
                DELETE FROM assets 
                WHERE deleted_at IS NOT NULL 
                AND deleted_at < datetime('now', ? || ' days')
            """, (f'-{older_than_days}',))
        else:
            # Delete all soft-deleted items
            cursor = conn.execute("DELETE FROM assets WHERE deleted_at IS NOT NULL")
        conn.commit()
        return cursor.rowcount


# Similar functions for models

def soft_delete_model(model_id: int, source: str = 'api') -> bool:
    """Soft-delete a model by setting deleted_at timestamp."""
    db = get_db()
    from datetime import datetime
    now = datetime.now().isoformat()
    
    with db.connection() as conn:
        cursor = conn.execute(
            "UPDATE models SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, model_id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            try:
                from fantasyfolio.services.change_journal import log_model_change
                log_model_change(model_id, 'trash', source=source)
            except Exception:
                pass
            return True
        return False


def restore_model(model_id: int, source: str = 'api') -> bool:
    """Restore a soft-deleted model by clearing deleted_at."""
    db = get_db()
    with db.connection() as conn:
        cursor = conn.execute(
            "UPDATE models SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            (model_id,)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            try:
                from fantasyfolio.services.change_journal import log_model_change
                log_model_change(model_id, 'restore', source=source)
            except Exception:
                pass
            return True
        return False


def get_deleted_models(limit: int = 100) -> List[Dict[str, Any]]:
    """Get list of soft-deleted models (Trash contents)."""
    return get_db().fetchall("""
        SELECT * FROM models 
        WHERE deleted_at IS NOT NULL 
        ORDER BY deleted_at DESC 
        LIMIT ?
    """, (limit,))


def get_assets_without_text(limit: int = 100) -> List[Dict[str, Any]]:
    """Get assets that don't have extracted text yet."""
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT a.* FROM assets a
            LEFT JOIN asset_pages p ON a.id = p.asset_id
            WHERE p.id IS NULL
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


# ==================== Publishers and Game Systems ====================

def get_publishers(include_deleted: bool = False) -> List[Dict[str, Any]]:
    """Get list of publishers with counts.
    
    Args:
        include_deleted: If True, include soft-deleted records in counts
    """
    deleted_filter = "AND deleted_at IS NULL" if not include_deleted else ""
    return get_db().fetchall(f"""
        SELECT publisher, COUNT(*) as count
        FROM assets
        WHERE publisher IS NOT NULL AND publisher != ''
        {deleted_filter}
        GROUP BY publisher
        ORDER BY count DESC
    """)
