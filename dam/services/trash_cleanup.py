"""
Trash Auto-Cleanup Service.

Automatically removes items from trash that are older than the configured retention period.
Can be run as a cron job or background task.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from dam.core.database import get_db, get_connection

logger = logging.getLogger(__name__)

# Default retention: 30 days
DEFAULT_RETENTION_DAYS = 30


def get_trash_retention_days() -> int:
    """
    Get the configured trash retention period in days.
    
    Checks settings table for 'trash_retention_days', falls back to default.
    """
    from dam.core.database import get_setting
    
    try:
        value = get_setting('trash_retention_days')
        if value:
            return int(value)
    except (ValueError, TypeError):
        pass
    
    return DEFAULT_RETENTION_DAYS


def get_expired_trash_items(retention_days: Optional[int] = None) -> Dict:
    """
    Get items that have been in trash longer than the retention period.
    
    Args:
        retention_days: Override default retention period
    
    Returns:
        Dict with 'assets' and 'models' lists
    """
    if retention_days is None:
        retention_days = get_trash_retention_days()
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_iso = cutoff_date.isoformat()
    
    db = get_db()
    with db.connection() as conn:
        # Get expired assets
        assets = conn.execute("""
            SELECT id, filename, title, deleted_at, file_size
            FROM assets
            WHERE deleted_at IS NOT NULL AND deleted_at < ?
        """, (cutoff_iso,)).fetchall()
        
        # Get expired models
        models = conn.execute("""
            SELECT id, filename, title, deleted_at, file_size
            FROM models
            WHERE deleted_at IS NOT NULL AND deleted_at < ?
        """, (cutoff_iso,)).fetchall()
    
    return {
        'assets': [dict(row) for row in assets],
        'models': [dict(row) for row in models],
        'cutoff_date': cutoff_iso,
        'retention_days': retention_days
    }


def cleanup_expired_trash(retention_days: Optional[int] = None, dry_run: bool = False) -> Dict:
    """
    Remove items from trash that exceed the retention period.
    
    Args:
        retention_days: Override default retention period
        dry_run: If True, don't actually delete, just report what would be deleted
    
    Returns:
        Dict with cleanup results
    """
    if retention_days is None:
        retention_days = get_trash_retention_days()
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_iso = cutoff_date.isoformat()
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'retention_days': retention_days,
        'cutoff_date': cutoff_iso,
        'dry_run': dry_run,
        'assets_deleted': 0,
        'models_deleted': 0,
        'total_size_freed': 0,
        'errors': []
    }
    
    db = get_db()
    
    try:
        with db.connection() as conn:
            # Get items to be deleted (for logging and size calculation)
            expired = get_expired_trash_items(retention_days)
            
            # Calculate total size
            for asset in expired['assets']:
                result['total_size_freed'] += asset.get('file_size', 0) or 0
            for model in expired['models']:
                result['total_size_freed'] += model.get('file_size', 0) or 0
            
            if dry_run:
                result['assets_deleted'] = len(expired['assets'])
                result['models_deleted'] = len(expired['models'])
                result['message'] = f"Would delete {result['assets_deleted']} assets and {result['models_deleted']} models"
                logger.info(f"[DRY RUN] Trash cleanup: {result['message']}")
                return result
            
            # Delete expired assets (and related records)
            for asset in expired['assets']:
                try:
                    conn.execute("DELETE FROM asset_pages WHERE asset_id = ?", (asset['id'],))
                    conn.execute("DELETE FROM asset_bookmarks WHERE asset_id = ?", (asset['id'],))
                    conn.execute("DELETE FROM assets WHERE id = ?", (asset['id'],))
                    result['assets_deleted'] += 1
                except Exception as e:
                    result['errors'].append(f"Asset {asset['id']}: {str(e)}")
                    logger.error(f"Error deleting asset {asset['id']}: {e}")
            
            # Delete expired models
            for model in expired['models']:
                try:
                    conn.execute("DELETE FROM models WHERE id = ?", (model['id'],))
                    result['models_deleted'] += 1
                except Exception as e:
                    result['errors'].append(f"Model {model['id']}: {str(e)}")
                    logger.error(f"Error deleting model {model['id']}: {e}")
            
            conn.commit()
            
            result['message'] = f"Deleted {result['assets_deleted']} assets and {result['models_deleted']} models"
            logger.info(f"Trash cleanup completed: {result['message']}")
    
    except Exception as e:
        result['errors'].append(f"Cleanup failed: {str(e)}")
        logger.error(f"Trash cleanup failed: {e}", exc_info=True)
    
    return result


def run_cleanup_job():
    """
    Entry point for cron/scheduled cleanup.
    
    Logs results and returns exit code.
    """
    logger.info("Starting scheduled trash cleanup")
    result = cleanup_expired_trash()
    
    if result['errors']:
        logger.warning(f"Cleanup completed with {len(result['errors'])} errors")
        return 1
    
    return 0


# CLI interface
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Trash auto-cleanup service')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without deleting')
    parser.add_argument('--days', type=int, help='Override retention period (days)')
    parser.add_argument('--status', action='store_true', help='Show current trash status')
    args = parser.parse_args()
    
    # Set up logging for CLI
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    if args.status:
        expired = get_expired_trash_items(args.days)
        retention = args.days or get_trash_retention_days()
        print(f"Trash Cleanup Status")
        print(f"=" * 40)
        print(f"Retention period: {retention} days")
        print(f"Cutoff date: {expired['cutoff_date'][:10]}")
        print(f"Expired assets: {len(expired['assets'])}")
        print(f"Expired models: {len(expired['models'])}")
        
        total_size = sum(a.get('file_size', 0) or 0 for a in expired['assets'])
        total_size += sum(m.get('file_size', 0) or 0 for m in expired['models'])
        print(f"Total size to free: {total_size / (1024*1024):.2f} MB")
    else:
        result = cleanup_expired_trash(retention_days=args.days, dry_run=args.dry_run)
        
        print(f"Trash Cleanup {'(DRY RUN)' if args.dry_run else 'Results'}")
        print(f"=" * 40)
        print(f"Retention: {result['retention_days']} days")
        print(f"Assets deleted: {result['assets_deleted']}")
        print(f"Models deleted: {result['models_deleted']}")
        print(f"Space freed: {result['total_size_freed'] / (1024*1024):.2f} MB")
        
        if result['errors']:
            print(f"\nErrors ({len(result['errors'])}):")
            for err in result['errors']:
                print(f"  • {err}")
            sys.exit(1)
        
        sys.exit(0)
