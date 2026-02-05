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


def main():
    """Entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()
