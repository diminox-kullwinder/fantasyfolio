"""
Database access layer for DAM.

Provides connection management, initialization, and core query functions.
Uses SQLite with WAL mode for better concurrency.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from contextlib import contextmanager

from dam.config import get_config

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
        
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        with self.connection() as conn:
            conn.executescript(schema)
            conn.commit()
        
        logger.info(f"Database initialized at {self.db_path}")
    
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

def get_stats() -> Dict[str, Any]:
    """Get overall database statistics."""
    db = get_db()
    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        total_size = conn.execute("SELECT SUM(file_size) FROM assets").fetchone()[0] or 0
        publishers = conn.execute("SELECT COUNT(DISTINCT publisher) FROM assets").fetchone()[0]
        
        return {
            "total_assets": total,
            "total_size_bytes": total_size,
            "unique_publishers": publishers
        }


def search_assets(query: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Search assets using full-text search with prefix matching."""
    db = get_db()
    # Add wildcard for prefix matching (e.g., "drag" matches "dragon")
    # Split into terms and add * to each for prefix matching
    terms = query.strip().split()
    fts_query = ' '.join(f'{term}*' for term in terms if term)
    
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT a.*, highlight(assets_fts, 0, '<mark>', '</mark>') as highlight
            FROM assets a
            JOIN assets_fts ON a.id = assets_fts.rowid
            WHERE assets_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, (fts_query, limit, offset)).fetchall()
        return [dict(row) for row in rows]


def get_asset_by_id(asset_id: int) -> Optional[Dict[str, Any]]:
    """Get a single asset by ID."""
    return get_db().fetchone("SELECT * FROM assets WHERE id = ?", (asset_id,))


def list_assets(folder: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List assets with optional folder filter."""
    db = get_db()
    with db.connection() as conn:
        if folder:
            rows = conn.execute(
                "SELECT * FROM assets WHERE folder_path LIKE ? ORDER BY filename LIMIT ? OFFSET ?",
                (folder + '%', limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assets ORDER BY filename LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]


def get_folder_tree() -> List[Dict[str, Any]]:
    """Get folder structure for navigation."""
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT folder_path, COUNT(*) as count
            FROM assets
            WHERE folder_path IS NOT NULL AND folder_path != ''
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

def get_models_stats() -> Dict[str, Any]:
    """Get 3D model statistics."""
    db = get_db()
    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        by_format = conn.execute(
            "SELECT format, COUNT(*) as count FROM models GROUP BY format"
        ).fetchall()
        collections = conn.execute(
            "SELECT COUNT(DISTINCT collection) FROM models"
        ).fetchone()[0]
        total_size = conn.execute(
            "SELECT SUM(file_size) FROM models"
        ).fetchone()[0] or 0
        
        return {
            'total_models': total,
            'by_format': {row['format']: row['count'] for row in by_format},
            'collections': collections,
            'total_size_mb': round(total_size / (1024*1024), 2)
        }


def search_models(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search 3D models using full-text search with prefix matching."""
    db = get_db()
    # Add wildcard for prefix matching (e.g., "robo" matches "robot")
    terms = query.strip().split()
    fts_query = ' '.join(f'{term}*' for term in terms if term)
    
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT m.* FROM models m
            JOIN models_fts ON m.id = models_fts.rowid
            WHERE models_fts MATCH ?
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


def get_text_extraction_stats() -> Dict[str, Any]:
    """Get statistics about text extraction."""
    db = get_db()
    with db.connection() as conn:
        total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        with_text = conn.execute(
            "SELECT COUNT(DISTINCT asset_id) FROM asset_pages WHERE text_content IS NOT NULL AND text_content != ''"
        ).fetchone()[0]
        total_pages = conn.execute("SELECT COUNT(*) FROM asset_pages").fetchone()[0]
        
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


def delete_missing_assets(existing_paths: set) -> int:
    """Delete assets whose files no longer exist. Returns count of deleted."""
    db = get_db()
    deleted = 0
    with db.connection() as conn:
        rows = conn.execute("SELECT id, file_path FROM assets").fetchall()
        for row in rows:
            if row['file_path'] not in existing_paths:
                conn.execute("DELETE FROM assets WHERE id = ?", (row['id'],))
                deleted += 1
        conn.commit()
    return deleted


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

def get_publishers() -> List[Dict[str, Any]]:
    """Get list of publishers with counts."""
    return get_db().fetchall("""
        SELECT publisher, COUNT(*) as count
        FROM assets
        WHERE publisher IS NOT NULL AND publisher != ''
        GROUP BY publisher
        ORDER BY count DESC
    """)
