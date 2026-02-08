#!/usr/bin/env python3
"""
Create UAT database with a subset of production data.
Copies schema and ~500 assets + ~500 models from production.
"""

import sqlite3
import os
import shutil
from pathlib import Path

# Paths
PROD_DB = "/Users/claw/.openclaw/workspace/dam/data/dam.db"
UAT_DB = "/Users/claw/projects/dam/data/dam_uat.db"

def create_uat_database():
    """Create UAT database with production schema and subset of data."""
    
    # Remove existing UAT database if it exists
    if os.path.exists(UAT_DB):
        os.remove(UAT_DB)
        print(f"Removed existing UAT database")
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(UAT_DB), exist_ok=True)
    
    # Connect to production database (read-only)
    prod_conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    prod_conn.row_factory = sqlite3.Row
    
    # Create new UAT database
    uat_conn = sqlite3.connect(UAT_DB)
    
    print(f"Connected to production: {PROD_DB}")
    print(f"Creating UAT database: {UAT_DB}")
    
    # Get schema from production
    schema_rows = prod_conn.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"
    ).fetchall()
    
    # Create schema in UAT
    for row in schema_rows:
        sql = row[0]
        if sql:
            try:
                uat_conn.execute(sql)
            except sqlite3.OperationalError as e:
                # Skip if already exists
                if "already exists" not in str(e):
                    print(f"Schema warning: {e}")
    
    uat_conn.commit()
    print("Schema copied successfully")
    
    # Copy subset of assets (500 records, varied content)
    print("\nCopying assets...")
    assets = prod_conn.execute("""
        SELECT * FROM assets 
        ORDER BY RANDOM() 
        LIMIT 500
    """).fetchall()
    
    if assets:
        columns = [desc[0] for desc in prod_conn.execute("SELECT * FROM assets LIMIT 1").description]
        placeholders = ",".join(["?" for _ in columns])
        col_names = ",".join(columns)
        
        uat_conn.executemany(
            f"INSERT INTO assets ({col_names}) VALUES ({placeholders})",
            [tuple(row) for row in assets]
        )
        print(f"  Copied {len(assets)} assets")
    
    # Copy subset of models (500 records)
    print("Copying models...")
    models = prod_conn.execute("""
        SELECT * FROM models 
        ORDER BY RANDOM() 
        LIMIT 500
    """).fetchall()
    
    if models:
        columns = [desc[0] for desc in prod_conn.execute("SELECT * FROM models LIMIT 1").description]
        placeholders = ",".join(["?" for _ in columns])
        col_names = ",".join(columns)
        
        uat_conn.executemany(
            f"INSERT INTO models ({col_names}) VALUES ({placeholders})",
            [tuple(row) for row in models]
        )
        print(f"  Copied {len(models)} models")
    
    # Copy any other relevant tables (folders, tags, etc.)
    tables_to_copy = ['folders', 'tags', 'asset_tags', 'model_tags', 'settings']
    
    for table in tables_to_copy:
        try:
            # Check if table exists
            exists = prod_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            
            if not exists:
                continue
                
            rows = prod_conn.execute(f"SELECT * FROM {table} LIMIT 1000").fetchall()
            if rows:
                columns = [desc[0] for desc in prod_conn.execute(f"SELECT * FROM {table} LIMIT 1").description]
                placeholders = ",".join(["?" for _ in columns])
                col_names = ",".join(columns)
                
                uat_conn.executemany(
                    f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})",
                    [tuple(row) for row in rows]
                )
                print(f"  Copied {len(rows)} rows from {table}")
        except Exception as e:
            print(f"  Skipped {table}: {e}")
    
    uat_conn.commit()
    
    # Rebuild FTS indexes if they exist
    print("\nRebuilding FTS indexes...")
    for fts_table in ['assets_fts', 'models_fts']:
        try:
            uat_conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
            print(f"  Rebuilt {fts_table}")
        except Exception as e:
            print(f"  Skipped {fts_table}: {e}")
    
    uat_conn.commit()
    
    # Report final counts
    print("\n=== UAT Database Summary ===")
    asset_count = uat_conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    model_count = uat_conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    print(f"Assets: {asset_count}")
    print(f"Models: {model_count}")
    
    # File size
    uat_conn.close()
    prod_conn.close()
    
    size_kb = os.path.getsize(UAT_DB) / 1024
    print(f"Database size: {size_kb:.1f} KB")
    print(f"\nUAT database created: {UAT_DB}")

if __name__ == "__main__":
    create_uat_database()
