#!/usr/bin/env python3
"""
Migration 001: Add soft delete support.

Adds deleted_at column to assets and models tables for soft delete functionality.
Records with deleted_at != NULL are considered "in trash" and hidden from normal queries.
"""

import sqlite3
import os
from datetime import datetime

# Get database path from environment or use default
DB_PATH = os.environ.get('DAM_DB_PATH', '/Users/claw/projects/dam/data/dam_uat.db')


def run_migration(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """
    Add deleted_at column to assets and models tables.
    
    Returns:
        dict with migration results
    """
    results = {
        'migration': '001_add_soft_delete',
        'timestamp': datetime.now().isoformat(),
        'db_path': DB_PATH,
        'dry_run': dry_run,
        'changes': []
    }
    
    cursor = conn.cursor()
    
    # Check current schema for assets
    cursor.execute("PRAGMA table_info(assets)")
    asset_columns = {row[1] for row in cursor.fetchall()}
    
    # Check current schema for models  
    cursor.execute("PRAGMA table_info(models)")
    model_columns = {row[1] for row in cursor.fetchall()}
    
    # Add deleted_at to assets if not present
    if 'deleted_at' not in asset_columns:
        if not dry_run:
            cursor.execute("ALTER TABLE assets ADD COLUMN deleted_at TEXT DEFAULT NULL")
            results['changes'].append('Added deleted_at column to assets table')
        else:
            results['changes'].append('[DRY RUN] Would add deleted_at column to assets table')
    else:
        results['changes'].append('assets.deleted_at already exists - skipping')
    
    # Add deleted_at to models if not present
    if 'deleted_at' not in model_columns:
        if not dry_run:
            cursor.execute("ALTER TABLE models ADD COLUMN deleted_at TEXT DEFAULT NULL")
            results['changes'].append('Added deleted_at column to models table')
        else:
            results['changes'].append('[DRY RUN] Would add deleted_at column to models table')
    else:
        results['changes'].append('models.deleted_at already exists - skipping')
    
    # Create index for efficient filtering of non-deleted records
    if not dry_run:
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_deleted ON assets(deleted_at)")
            results['changes'].append('Created index idx_assets_deleted')
        except sqlite3.OperationalError:
            results['changes'].append('Index idx_assets_deleted already exists')
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_deleted ON models(deleted_at)")
            results['changes'].append('Created index idx_models_deleted')
        except sqlite3.OperationalError:
            results['changes'].append('Index idx_models_deleted already exists')
    
    if not dry_run:
        conn.commit()
        results['status'] = 'completed'
    else:
        results['status'] = 'dry_run'
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add soft delete columns')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--db', help='Database path (overrides DAM_DB_PATH env)')
    args = parser.parse_args()
    
    global DB_PATH
    if args.db:
        DB_PATH = args.db
    
    print(f"Migration: 001_add_soft_delete")
    print(f"Database: {DB_PATH}")
    print(f"Dry run: {args.dry_run}")
    print("-" * 50)
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return 1
    
    conn = sqlite3.connect(DB_PATH)
    results = run_migration(conn, dry_run=args.dry_run)
    conn.close()
    
    print(f"\nStatus: {results['status']}")
    print("\nChanges:")
    for change in results['changes']:
        print(f"  • {change}")
    
    return 0


if __name__ == "__main__":
    exit(main())
