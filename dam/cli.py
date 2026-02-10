"""
DAM Command Line Interface.

Provides CLI commands for running the server, indexing content,
and managing the database.
"""

import os
import sys
import click
import logging

from dam.config import get_config, Config


@click.group()
@click.option('--env', default=None, help='Environment (development/staging/production)')
@click.pass_context
def cli(ctx, env):
    """Digital Asset Manager CLI."""
    if env:
        os.environ['DAM_ENV'] = env
    ctx.ensure_object(dict)
    ctx.obj['config'] = get_config(env)


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize the database."""
    from dam.core.database import init_db as do_init
    config = ctx.obj['config']
    config.init_dirs()
    do_init()
    click.echo(f"Database initialized at {config.DATABASE_PATH}")


@cli.command()
@click.option('--host', default=None, help='Host to bind to')
@click.option('--port', default=None, type=int, help='Port to bind to')
@click.option('--debug/--no-debug', default=None, help='Enable debug mode')
@click.pass_context
def run(ctx, host, port, debug):
    """Run the web server."""
    from dam.app import create_app
    
    config = ctx.obj['config']
    
    app = create_app(config)
    app.run(
        host=host or config.HOST,
        port=port or config.PORT,
        debug=debug if debug is not None else config.DEBUG
    )


@cli.command()
@click.argument('path', required=False)
@click.option('--no-text', is_flag=True, help='Skip text extraction')
@click.option('--no-thumbnails', is_flag=True, help='Skip thumbnail generation')
@click.pass_context
def index_pdfs(ctx, path, no_text, no_thumbnails):
    """Index PDF files from a directory."""
    from dam.indexer.pdf import PDFIndexer
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    indexer = PDFIndexer(path)
    stats = indexer.run(
        extract_text=not no_text,
        generate_thumbnails=not no_thumbnails
    )
    click.echo(f"Indexing complete: {stats}")


@cli.command()
@click.argument('path', required=False)
@click.pass_context
def index_models(ctx, path):
    """Index 3D model files from a directory."""
    from dam.indexer.models3d import ModelsIndexer
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    indexer = ModelsIndexer(path)
    stats = indexer.run()
    click.echo(f"Indexing complete: {stats}")


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    from dam.core.database import get_stats, get_models_stats, init_db
    
    init_db()
    
    pdf_stats = get_stats()
    model_stats = get_models_stats()
    
    click.echo("\n📚 PDF Assets:")
    click.echo(f"   Total: {pdf_stats.get('total_assets', 0)}")
    click.echo(f"   Size: {pdf_stats.get('total_size_bytes', 0) / (1024*1024*1024):.2f} GB")
    click.echo(f"   Publishers: {pdf_stats.get('unique_publishers', 0)}")
    
    click.echo("\n🎲 3D Models:")
    click.echo(f"   Total: {model_stats.get('total_models', 0)}")
    click.echo(f"   Size: {model_stats.get('total_size_mb', 0) / 1024:.2f} GB")
    click.echo(f"   Collections: {model_stats.get('collections', 0)}")
    click.echo(f"   Formats: {model_stats.get('by_format', {})}")


@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['models', 'assets', 'all']), default='all')
@click.option('--limit', default=None, type=int, help='Max assets to process')
@click.option('--batch-size', default=100, type=int, help='Batch size for commits')
@click.pass_context
def compute_hashes(ctx, content_type, limit, batch_size):
    """Compute partial hashes for assets missing them."""
    from dam.core.hashing import batch_compute_hashes
    from dam.core.database import init_db
    
    config = ctx.obj['config']
    init_db()
    
    db_path = str(config.DATABASE_PATH)
    
    def progress_callback(processed, total, current):
        if processed % 100 == 0:
            pct = (processed / total * 100) if total > 0 else 0
            click.echo(f"\r  {processed}/{total} ({pct:.1f}%) - {current[:60]}", nl=False)
    
    tables = []
    if content_type in ('models', 'all'):
        tables.append('models')
    if content_type in ('assets', 'all'):
        tables.append('assets')
    
    for table in tables:
        click.echo(f"\n🔐 Computing hashes for {table}...")
        results = batch_compute_hashes(
            db_path=db_path,
            table=table,
            batch_size=batch_size,
            limit=limit,
            callback=progress_callback
        )
        
        click.echo(f"\n  ✓ Processed: {results['processed']}")
        click.echo(f"  ○ Skipped: {results['skipped']}")
        click.echo(f"  ✗ Errors: {results['errors']}")
        click.echo(f"  ⏱ Time: {results['elapsed_seconds']}s")
        
        if results['error_details']:
            click.echo("  Errors:")
            for err in results['error_details'][:5]:
                click.echo(f"    - {err['path']}: {err['error']}")
        
        # Auto-trigger deduplication when hashing completes
        import sqlite3
        conn = sqlite3.connect(db_path)
        remaining = conn.execute(f"""
            SELECT COUNT(*) FROM {table} 
            WHERE partial_hash IS NULL AND volume_id IS NOT NULL
        """).fetchone()[0]
        conn.close()
        
        if remaining == 0:
            click.echo(f"\n🔎 All {table} hashed — auto-running deduplication...")
            from dam.core.deduplication import process_duplicates
            
            dedup_results = process_duplicates(db_path=db_path, table=table)
            
            click.echo(f"\n📊 Deduplication Results:")
            click.echo(f"  Collision pairs checked: {dedup_results['candidates_found']}")
            click.echo(f"  True duplicates found: {dedup_results['duplicates_found']}")
            click.echo(f"  Full hashes computed: {dedup_results['full_hashes_computed']}")
            click.echo(f"  Time: {dedup_results['elapsed_seconds']:.1f}s")
            
            if dedup_results['duplicates']:
                click.echo(f"\n📋 Duplicates Detected:")
                for dup in dedup_results['duplicates']:
                    click.echo(f"  • {dup['duplicate_name']} → duplicate of {dup['primary_name']}")
        else:
            click.echo(f"\n  ℹ {remaining} files still need hashing — deduplication will run when complete")


@cli.command()
@click.argument('path', required=True)
@click.option('--force', is_flag=True, help='Force re-index (ignore cache)')
@click.option('--no-recursive', is_flag=True, help='Do not recurse into subdirectories')
@click.option('--volume-id', default=None, help='Volume ID (auto-detected if not provided)')
@click.pass_context
def scan_directory(ctx, path, force, no_recursive, volume_id):
    """Scan a directory using the efficient indexer."""
    from pathlib import Path
    from dam.core.database import get_connection, init_db
    from dam.core.scanner import scan_directory as do_scan, ScanAction
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    init_db()
    config = ctx.obj['config']
    
    scan_path = Path(path).resolve()
    if not scan_path.exists():
        click.echo(f"Error: Path does not exist: {scan_path}")
        return
    
    with get_connection() as conn:
        # Get or detect volume
        if volume_id:
            volume = conn.execute(
                "SELECT * FROM volumes WHERE id = ?", (volume_id,)
            ).fetchone()
        else:
            # Auto-detect from path
            volume = conn.execute("""
                SELECT * FROM volumes 
                WHERE ? LIKE mount_path || '%'
                ORDER BY length(mount_path) DESC
                LIMIT 1
            """, (str(scan_path),)).fetchone()
        
        if not volume:
            click.echo(f"Error: No volume found for path: {scan_path}")
            click.echo("Register a volume first or specify --volume-id")
            return
        
        volume = dict(volume)
        click.echo(f"Scanning: {scan_path}")
        click.echo(f"Volume: {volume['label']} ({volume['id']})")
        click.echo(f"Mode: {'Forced' if force else 'Standard'}")
        click.echo("")
        
        stats = {
            'new': 0, 'update': 0, 'skip': 0, 
            'moved': 0, 'missing': 0, 'error': 0
        }
        
        count = 0
        for result in do_scan(conn, scan_path, volume, force=force, recursive=not no_recursive):
            stats[result.action.value] += 1
            count += 1
            
            # Apply changes for new/update/moved
            if result.action in (ScanAction.NEW, ScanAction.UPDATE, ScanAction.MOVED):
                model = result.model
                
                if result.action == ScanAction.NEW:
                    # Insert new record
                    columns = ', '.join(model.keys())
                    placeholders = ', '.join(['?' for _ in model])
                    conn.execute(
                        f"INSERT INTO models ({columns}) VALUES ({placeholders})",
                        list(model.values())
                    )
                else:
                    # Update existing record
                    model_id = model.pop('id', None)
                    if model_id:
                        sets = ', '.join([f"{k} = ?" for k in model.keys()])
                        conn.execute(
                            f"UPDATE models SET {sets} WHERE id = ?",
                            list(model.values()) + [model_id]
                        )
            
            # Progress update
            if count % 100 == 0:
                click.echo(f"  Processed {count}... (new: {stats['new']}, skip: {stats['skip']})")
                conn.commit()
        
        conn.commit()
        
        click.echo("")
        click.echo("=" * 50)
        click.echo("SCAN COMPLETE")
        click.echo("=" * 50)
        click.echo(f"  New:     {stats['new']}")
        click.echo(f"  Updated: {stats['update']}")
        click.echo(f"  Skipped: {stats['skip']}")
        click.echo(f"  Moved:   {stats['moved']}")
        click.echo(f"  Missing: {stats['missing']}")
        click.echo(f"  Errors:  {stats['error']}")
        click.echo(f"  Total:   {count}")


@cli.command()
@click.option('--limit', default=100, type=int, help='Max thumbnails to render')
@click.option('--force', is_flag=True, help='Re-render existing thumbnails')
@click.pass_context
def render_thumbnails(ctx, limit, force):
    """Render pending thumbnails using sidecar storage."""
    from pathlib import Path
    from dam.core.database import get_connection, init_db
    from dam.core.thumbnails import render_pending_thumbnails
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    init_db()
    config = ctx.obj['config']
    central_dir = Path(config.DATA_DIR) / 'thumbnails'
    
    def progress(current, total, filename):
        if current % 10 == 0:
            pct = (current / total * 100) if total > 0 else 0
            click.echo(f"  {current}/{total} ({pct:.1f}%) - {filename[:50]}")
    
    click.echo(f"Rendering up to {limit} thumbnails...")
    click.echo(f"Central cache: {central_dir}")
    
    with get_connection() as conn:
        stats = render_pending_thumbnails(conn, central_dir, limit=limit, callback=progress)
    
    click.echo("")
    click.echo("=" * 50)
    click.echo(f"  Rendered: {stats['rendered']}")
    click.echo(f"  Failed:   {stats['failed']}")
    click.echo(f"  Skipped:  {stats['skipped']}")


@cli.command()
@click.option('--limit', default=None, type=int, help='Max to migrate')
@click.pass_context
def migrate_thumbnails(ctx, limit):
    """Migrate central thumbnails to sidecar locations."""
    from pathlib import Path
    from dam.core.database import get_connection, init_db
    from dam.core.thumbnails import migrate_thumbnails_to_sidecars
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    init_db()
    config = ctx.obj['config']
    central_dir = Path(config.DATA_DIR) / 'thumbnails'
    
    def progress(current, total, filename):
        if current % 100 == 0:
            pct = (current / total * 100) if total > 0 else 0
            click.echo(f"  {current}/{total} ({pct:.1f}%)")
    
    click.echo("Migrating central thumbnails to sidecars...")
    click.echo(f"Central dir: {central_dir}")
    
    with get_connection() as conn:
        stats = migrate_thumbnails_to_sidecars(conn, central_dir, limit=limit, callback=progress)
    
    click.echo("")
    click.echo("=" * 50)
    click.echo(f"  Migrated:        {stats['migrated']}")
    click.echo(f"  Already sidecar: {stats['already_sidecar']}")
    click.echo(f"  Skipped:         {stats['skipped']}")
    click.echo(f"  Failed:          {stats['failed']}")


@cli.command()
@click.argument('volume_id', required=True)
@click.option('--force', is_flag=True, help='Force re-index all assets')
@click.pass_context
def scan_volume(ctx, volume_id, force):
    """Scan an entire volume using the efficient indexer."""
    from pathlib import Path
    from dam.core.database import get_connection, init_db
    
    init_db()
    
    with get_connection() as conn:
        volume = conn.execute(
            "SELECT * FROM volumes WHERE id = ?", (volume_id,)
        ).fetchone()
        
        if not volume:
            click.echo(f"Error: Volume not found: {volume_id}")
            return
        
        volume = dict(volume)
        
        if volume['status'] != 'online':
            click.echo(f"Error: Volume is offline: {volume['mount_path']}")
            return
        
        click.echo(f"Will scan entire volume: {volume['label']}")
        click.echo(f"Path: {volume['mount_path']}")
        
    # Call scan_directory with the volume's mount path
    ctx.invoke(scan_directory, path=volume['mount_path'], force=force, no_recursive=False, volume_id=volume_id)


@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['pdf', '3d', 'all']), default='all')
@click.option('--yes', is_flag=True, help='Skip confirmation')
@click.pass_context
def clear(ctx, content_type, yes):
    """Clear the index (destructive!)."""
    if not yes:
        click.confirm(f"This will delete all {content_type} index data. Continue?", abort=True)
    
    from dam.core.database import get_connection
    
    with get_connection() as conn:
        if content_type in ('pdf', 'all'):
            conn.execute("DELETE FROM asset_pages")
            conn.execute("DELETE FROM asset_bookmarks")
            conn.execute("DELETE FROM assets")
            click.echo("Cleared PDF assets")
        
        if content_type in ('3d', 'all'):
            conn.execute("DELETE FROM models")
            click.echo("Cleared 3D models")
        
        conn.commit()


@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['models', 'assets', 'all']), default='models')
@click.pass_context
def detect_duplicates(ctx, content_type):
    """Detect and verify duplicate files using full hash.
    
    Process:
    1. Find partial hash collisions (fast)
    2. Compute full hashes for collisions (slow, only for candidates)
    3. Mark verified duplicates in database
    """
    from dam.core.deduplication import process_duplicates
    from dam.core.database import init_db
    
    config = ctx.obj['config']
    init_db()
    
    db_path = str(config.DATABASE_PATH)
    
    tables = []
    if content_type in ('models', 'all'):
        tables.append('models')
    if content_type in ('assets', 'all'):
        tables.append('assets')
    
    for table in tables:
        click.echo(f"\n🔎 Detecting duplicates in {table}...\n")
        
        results = process_duplicates(
            db_path=db_path,
            table=table,
            callback=None
        )
        
        click.echo(f"\n📊 Results for {table}:")
        click.echo(f"  Partial hash collisions: {results['candidates_found']}")
        click.echo(f"  Collisions verified: {results['candidates_verified']}")
        click.echo(f"  True duplicates found: {results['duplicates_found']}")
        click.echo(f"  Full hashes computed: {results['full_hashes_computed']}")
        click.echo(f"  Database entries updated: {results['full_hashes_updated']}")
        click.echo(f"  Errors: {results['errors']}")
        click.echo(f"  Time elapsed: {results['elapsed_seconds']:.1f}s")
        
        if results['duplicates']:
            click.echo(f"\n📋 Duplicate List:")
            for dup in results['duplicates']:
                click.echo(f"  • {dup['primary_name']} (ID: {dup['primary_id']}) [KEEP]")
                click.echo(f"    ↔ {dup['duplicate_name']} (ID: {dup['duplicate_id']}) [MARK]")
                click.echo(f"    Size: {dup['file_size_mb']:.1f}MB, Hash: {dup['full_hash'][:16]}...")
                click.echo()


def main():
    """Entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()
