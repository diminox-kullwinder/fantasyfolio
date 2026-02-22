"""
Migration 007: Add custom_name to collection_shares

Allows users to rename shared collections from their perspective
without affecting the original collection name.

Run with: python -m migrations.007_collection_share_aliases
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_SQL = """
-- Add custom_name column for personal collection aliases
ALTER TABLE collection_shares ADD COLUMN custom_name TEXT;
"""


def run_migration(db_path: Path) -> bool:
    """Add custom_name column to collection_shares table."""
    logger.info(f"Running collection alias migration on {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Check if column already exists
        cursor = conn.execute("PRAGMA table_info(collection_shares)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'custom_name' in columns:
            logger.info("⚠️  Column 'custom_name' already exists, skipping")
            conn.close()
            return True
        
        # Add the column
        conn.execute("ALTER TABLE collection_shares ADD COLUMN custom_name TEXT")
        conn.commit()
        
        logger.info("✅ Added custom_name column to collection_shares")
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
