"""
Migration 007: Add nested collections support

Adds parent_collection_id to user_collections table for hierarchical organization.

Run with: python -m migrations.007_nested_collections
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_SQL = """
-- Add parent_collection_id for nested collections
ALTER TABLE user_collections ADD COLUMN parent_collection_id TEXT REFERENCES user_collections(id) ON DELETE CASCADE;

-- Index for parent lookups
CREATE INDEX IF NOT EXISTS idx_collections_parent ON user_collections(parent_collection_id);
"""


def run_migration(db_path: Path) -> bool:
    """Run the nested collections migration."""
    logger.info(f"Running nested collections migration on {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Check if column already exists
        cursor = conn.execute("PRAGMA table_info(user_collections)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'parent_collection_id' in columns:
            logger.info("✅ parent_collection_id already exists, skipping")
            conn.close()
            return True
        
        # Execute migration
        conn.executescript(MIGRATION_SQL)
        conn.commit()
        
        logger.info("✅ Nested collections migration completed successfully")
        conn.close()
        return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # Default to test database
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/fantasyfolio.db")
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    success = run_migration(db_path)
    sys.exit(0 if success else 1)
