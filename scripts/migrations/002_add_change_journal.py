#!/usr/bin/env python3
"""
Migration 002: Add change journal table.

Tracks all modifications to assets and models for audit/rollback.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get('DAM_DATABASE_PATH', '/Users/claw/projects/dam/data/dam_uat.db')


def run_migration(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Add change_journal table."""
    results = {
        'migration': '002_add_change_journal',
        'timestamp': datetime.now().isoformat(),
        'db_path': DB_PATH,
        'dry_run': dry_run,
        'changes': []
    }
    
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_journal'")
    exists = cursor.fetchone()
    
    if exists:
        results['changes'].append('change_journal table already exists - skipping')
        results['status'] = 'skipped'
        return results
    
    if dry_run:
        results['changes'].append('[DRY RUN] Would create change_journal table')
        results['status'] = 'dry_run'
        return results
    
    # Create change_journal table
    cursor.execute("""
        CREATE TABLE change_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            
            -- What changed
            entity_type TEXT NOT NULL,      -- 'asset' or 'model'
            entity_id INTEGER NOT NULL,
            
            -- Change details
            action TEXT NOT NULL,           -- 'create', 'update', 'delete', 'restore'
            field_name TEXT,                -- Which field changed (for updates)
            old_value TEXT,                 -- Previous value (JSON for complex)
            new_value TEXT,                 -- New value
            
            -- Context
            source TEXT,                    -- 'indexer', 'api', 'manual', 'cleanup'
            user_info TEXT,                 -- Optional user context
            
            -- Indexes for efficient queries
            FOREIGN KEY (entity_id) REFERENCES assets(id) ON DELETE SET NULL
        )
    """)
    results['changes'].append('Created change_journal table')
    
    # Create indexes
    cursor.execute("CREATE INDEX idx_journal_timestamp ON change_journal(timestamp)")
    cursor.execute("CREATE INDEX idx_journal_entity ON change_journal(entity_type, entity_id)")
    cursor.execute("CREATE INDEX idx_journal_action ON change_journal(action)")
    results['changes'].append('Created indexes on change_journal')
    
    conn.commit()
    results['status'] = 'completed'
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add change journal table')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--db', help='Database path')
    args = parser.parse_args()
    
    global DB_PATH
    if args.db:
        DB_PATH = args.db
    
    print(f"Migration: 002_add_change_journal")
    print(f"Database: {DB_PATH}")
    print("-" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    results = run_migration(conn, dry_run=args.dry_run)
    conn.close()
    
    print(f"Status: {results['status']}")
    for change in results['changes']:
        print(f"  • {change}")


if __name__ == "__main__":
    main()
