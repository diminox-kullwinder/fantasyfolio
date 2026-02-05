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
    """Search assets using full-text search."""
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT a.*, highlight(assets_fts, 0, '<mark>', '</mark>') as highlight
            FROM assets a
            JOIN assets_fts ON a.id = assets_fts.rowid
            WHERE assets_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, (query, limit, offset)).fetchall()
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
    """Search 3D models using full-text search."""
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT m.* FROM models m
            JOIN models_fts ON m.id = models_fts.rowid
            WHERE models_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
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
