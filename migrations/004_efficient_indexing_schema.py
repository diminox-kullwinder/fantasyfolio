#!/usr/bin/env python3
"""
Migration 004: Efficient Indexing & Thumbnail Architecture

Adds:
- volumes table for tracking mounted volumes
- scan_jobs table for job queue
- job_errors table for error tracking
- New columns on models table for identity, status, thumbnails
- New columns on assets table (same pattern)
- Indexes for efficient queries

Part of the DAM Efficient Indexing & Thumbnail Architecture v1.2
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row['name'] for row in cursor.fetchall()]
    return column in columns


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate(db_path: str, dry_run: bool = False) -> dict:
    """
    Run the migration.
    
    Args:
        db_path: Path to SQLite database
        dry_run: If True, only report what would be done
    
    Returns:
        Dict with migration results
    """
    results = {
        'tables_created': [],
        'columns_added': [],
        'indexes_created': [],
        'errors': [],
        'skipped': []
    }
    
    conn = get_connection(db_path)
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # 1. CREATE VOLUMES TABLE
        # ═══════════════════════════════════════════════════════════════════
        if not table_exists(conn, 'volumes'):
            sql = """
            CREATE TABLE volumes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                mount_path TEXT NOT NULL,
                volume_uuid TEXT,
                
                -- Status
                status TEXT DEFAULT 'online',
                last_seen_at TEXT,
                last_indexed_at TEXT,
                
                -- Settings
                is_readonly INTEGER DEFAULT 0,
                index_priority INTEGER DEFAULT 0,
                
                -- Timestamps
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
            if not dry_run:
                conn.execute(sql)
                conn.execute("CREATE INDEX idx_volumes_status ON volumes(status)")
                conn.execute("CREATE INDEX idx_volumes_mount ON volumes(mount_path)")
            results['tables_created'].append('volumes')
        else:
            results['skipped'].append('volumes table already exists')
        
        # ═══════════════════════════════════════════════════════════════════
        # 2. CREATE SCAN_JOBS TABLE
        # ═══════════════════════════════════════════════════════════════════
        if not table_exists(conn, 'scan_jobs'):
            sql = """
            CREATE TABLE scan_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                target_path TEXT,
                
                -- Settings
                force_mode INTEGER DEFAULT 0,
                recursive INTEGER DEFAULT 1,
                include_thumbnails INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 5,
                
                -- Status
                status TEXT DEFAULT 'pending',
                phase TEXT,
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER,
                current_item TEXT,
                
                -- Timing
                created_at TEXT DEFAULT (datetime('now')),
                scheduled_for TEXT,
                started_at TEXT,
                completed_at TEXT,
                
                -- Results
                items_processed INTEGER DEFAULT 0,
                items_skipped INTEGER DEFAULT 0,
                items_failed INTEGER DEFAULT 0,
                items_missing INTEGER DEFAULT 0,
                error_message TEXT,
                
                -- Metadata
                created_by TEXT
            )
            """
            if not dry_run:
                conn.execute(sql)
                conn.execute("CREATE INDEX idx_jobs_status ON scan_jobs(status, priority)")
                conn.execute("CREATE INDEX idx_jobs_type ON scan_jobs(job_type, status)")
            results['tables_created'].append('scan_jobs')
        else:
            results['skipped'].append('scan_jobs table already exists')
        
        # ═══════════════════════════════════════════════════════════════════
        # 3. CREATE JOB_ERRORS TABLE
        # ═══════════════════════════════════════════════════════════════════
        if not table_exists(conn, 'job_errors'):
            sql = """
            CREATE TABLE job_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES scan_jobs(id) ON DELETE CASCADE,
                asset_type TEXT,
                asset_id INTEGER,
                file_path TEXT,
                error_type TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
            if not dry_run:
                conn.execute(sql)
                conn.execute("CREATE INDEX idx_job_errors_job ON job_errors(job_id)")
            results['tables_created'].append('job_errors')
        else:
            results['skipped'].append('job_errors table already exists')
        
        # ═══════════════════════════════════════════════════════════════════
        # 4. ADD COLUMNS TO MODELS TABLE
        # ═══════════════════════════════════════════════════════════════════
        models_columns = [
            # Identity & Verification
            ("volume_id", "TEXT REFERENCES volumes(id)"),
            ("relative_path", "TEXT"),
            ("file_size_bytes", "INTEGER"),
            ("file_mtime", "INTEGER"),
            ("partial_hash", "TEXT"),
            ("full_hash", "TEXT"),
            
            # Index Status & Tracking
            ("index_status", "TEXT DEFAULT 'indexed'"),
            ("last_indexed_at", "TEXT"),
            ("last_verified_at", "TEXT"),
            ("last_seen_at", "TEXT"),
            ("missing_since", "TEXT"),
            
            # Thumbnail Metadata
            ("thumb_storage", "TEXT"),
            ("thumb_path", "TEXT"),
            ("thumb_rendered_at", "TEXT"),
            ("thumb_source_mtime", "INTEGER"),
            
            # Force Flags
            ("force_reindex", "INTEGER DEFAULT 0"),
            ("force_rerender", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in models_columns:
            if not column_exists(conn, 'models', col_name):
                if not dry_run:
                    conn.execute(f"ALTER TABLE models ADD COLUMN {col_name} {col_def}")
                results['columns_added'].append(f"models.{col_name}")
            else:
                results['skipped'].append(f"models.{col_name} already exists")
        
        # Add indexes for models
        models_indexes = [
            ("idx_models_volume", "models(volume_id)"),
            ("idx_models_status", "models(index_status)"),
            ("idx_models_partial_hash", "models(partial_hash)"),
            ("idx_models_full_hash", "models(full_hash)"),
            ("idx_models_force", "models(force_reindex, force_rerender)"),
        ]
        
        for idx_name, idx_def in models_indexes:
            # Check if index exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (idx_name,)
            )
            if not cursor.fetchone():
                if not dry_run:
                    conn.execute(f"CREATE INDEX {idx_name} ON {idx_def}")
                results['indexes_created'].append(idx_name)
            else:
                results['skipped'].append(f"index {idx_name} already exists")
        
        # ═══════════════════════════════════════════════════════════════════
        # 5. ADD COLUMNS TO ASSETS TABLE
        # ═══════════════════════════════════════════════════════════════════
        assets_columns = [
            # Identity & Verification
            ("volume_id", "TEXT REFERENCES volumes(id)"),
            ("relative_path", "TEXT"),
            ("file_size_bytes", "INTEGER"),
            ("file_mtime", "INTEGER"),
            ("partial_hash", "TEXT"),
            ("full_hash", "TEXT"),
            
            # Index Status & Tracking
            ("index_status", "TEXT DEFAULT 'indexed'"),
            ("last_indexed_at", "TEXT"),
            ("last_verified_at", "TEXT"),
            ("last_seen_at", "TEXT"),
            ("missing_since", "TEXT"),
            
            # Thumbnail Metadata
            ("thumb_storage", "TEXT"),
            ("thumb_rendered_at", "TEXT"),
            ("thumb_source_mtime", "INTEGER"),
            
            # Force Flags
            ("force_reindex", "INTEGER DEFAULT 0"),
            ("force_rerender", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in assets_columns:
            if not column_exists(conn, 'assets', col_name):
                if not dry_run:
                    conn.execute(f"ALTER TABLE assets ADD COLUMN {col_name} {col_def}")
                results['columns_added'].append(f"assets.{col_name}")
            else:
                results['skipped'].append(f"assets.{col_name} already exists")
        
        # Add indexes for assets
        assets_indexes = [
            ("idx_assets_volume", "assets(volume_id)"),
            ("idx_assets_status", "assets(index_status)"),
            ("idx_assets_partial_hash", "assets(partial_hash)"),
            ("idx_assets_full_hash", "assets(full_hash)"),
            ("idx_assets_force", "assets(force_reindex, force_rerender)"),
        ]
        
        for idx_name, idx_def in assets_indexes:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (idx_name,)
            )
            if not cursor.fetchone():
                if not dry_run:
                    conn.execute(f"CREATE INDEX {idx_name} ON {idx_def}")
                results['indexes_created'].append(idx_name)
            else:
                results['skipped'].append(f"index {idx_name} already exists")
        
        # ═══════════════════════════════════════════════════════════════════
        # 6. COMMIT
        # ═══════════════════════════════════════════════════════════════════
        if not dry_run:
            conn.commit()
            print("✓ Migration committed successfully")
        else:
            print("DRY RUN - no changes made")
        
    except Exception as e:
        results['errors'].append(str(e))
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return results


def print_results(results: dict):
    """Print migration results."""
    print("\n" + "=" * 60)
    print("MIGRATION RESULTS")
    print("=" * 60)
    
    if results['tables_created']:
        print(f"\n✓ Tables created ({len(results['tables_created'])}):")
        for t in results['tables_created']:
            print(f"    - {t}")
    
    if results['columns_added']:
        print(f"\n✓ Columns added ({len(results['columns_added'])}):")
        for c in results['columns_added']:
            print(f"    - {c}")
    
    if results['indexes_created']:
        print(f"\n✓ Indexes created ({len(results['indexes_created'])}):")
        for i in results['indexes_created']:
            print(f"    - {i}")
    
    if results['skipped']:
        print(f"\n○ Skipped ({len(results['skipped'])}):")
        for s in results['skipped']:
            print(f"    - {s}")
    
    if results['errors']:
        print(f"\n✗ Errors ({len(results['errors'])}):")
        for e in results['errors']:
            print(f"    - {e}")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run migration 004')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    if not Path(args.db_path).exists():
        print(f"Error: Database not found: {args.db_path}")
        sys.exit(1)
    
    print(f"Running migration on: {args.db_path}")
    print(f"Dry run: {args.dry_run}")
    
    results = migrate(args.db_path, dry_run=args.dry_run)
    print_results(results)
