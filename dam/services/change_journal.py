"""
Change Journal Service.

Tracks all modifications to assets and models for audit and potential rollback.
Every create, update, delete, and restore operation is logged.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from dam.core.database import get_db, get_connection

logger = logging.getLogger(__name__)


def log_change(
    entity_type: str,
    entity_id: int,
    action: str,
    field_name: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    source: str = 'api',
    user_info: Optional[str] = None
) -> int:
    """
    Log a change to the journal.
    
    Args:
        entity_type: 'asset' or 'model'
        entity_id: ID of the affected record
        action: 'create', 'update', 'delete', 'restore', 'trash'
        field_name: Specific field that changed (for updates)
        old_value: Previous value
        new_value: New value
        source: Origin of change ('indexer', 'api', 'manual', 'cleanup')
        user_info: Optional user context
    
    Returns:
        ID of the journal entry
    """
    db = get_db()
    
    # Serialize complex values to JSON
    if old_value is not None and not isinstance(old_value, str):
        old_value = json.dumps(old_value)
    if new_value is not None and not isinstance(new_value, str):
        new_value = json.dumps(new_value)
    
    with db.connection() as conn:
        cursor = conn.execute("""
            INSERT INTO change_journal (
                entity_type, entity_id, action, field_name,
                old_value, new_value, source, user_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity_type, entity_id, action, field_name,
            old_value, new_value, source, user_info
        ))
        conn.commit()
        
        logger.debug(f"Journal: {action} {entity_type}#{entity_id} ({source})")
        return cursor.lastrowid


def log_asset_change(
    asset_id: int,
    action: str,
    **kwargs
) -> int:
    """Convenience wrapper for asset changes."""
    return log_change('asset', asset_id, action, **kwargs)


def log_model_change(
    model_id: int,
    action: str,
    **kwargs
) -> int:
    """Convenience wrapper for model changes."""
    return log_change('model', model_id, action, **kwargs)


def get_journal_entries(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Query journal entries with optional filters.
    
    Args:
        entity_type: Filter by 'asset' or 'model'
        entity_id: Filter by specific entity
        action: Filter by action type
        since: Only entries after this timestamp
        limit: Maximum results
        offset: Pagination offset
    
    Returns:
        List of journal entries
    """
    db = get_db()
    
    query = "SELECT * FROM change_journal WHERE 1=1"
    params = []
    
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    
    if entity_id:
        query += " AND entity_id = ?"
        params.append(entity_id)
    
    if action:
        query += " AND action = ?"
        params.append(action)
    
    if since:
        query += " AND timestamp >= ?"
        params.append(since.isoformat())
    
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with db.connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_entity_history(entity_type: str, entity_id: int) -> List[Dict]:
    """
    Get complete history for a specific entity.
    
    Returns all journal entries for the entity, oldest first.
    """
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("""
            SELECT * FROM change_journal
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY timestamp ASC
        """, (entity_type, entity_id)).fetchall()
        return [dict(row) for row in rows]


def get_journal_stats() -> Dict:
    """
    Get journal statistics.
    
    Returns:
        Dict with counts by action, entity type, and time period
    """
    db = get_db()
    
    with db.connection() as conn:
        # Total entries
        total = conn.execute("SELECT COUNT(*) FROM change_journal").fetchone()[0]
        
        # By action
        by_action = conn.execute("""
            SELECT action, COUNT(*) as count
            FROM change_journal
            GROUP BY action
        """).fetchall()
        
        # By entity type
        by_type = conn.execute("""
            SELECT entity_type, COUNT(*) as count
            FROM change_journal
            GROUP BY entity_type
        """).fetchall()
        
        # Recent (last 24 hours)
        recent_count = conn.execute("""
            SELECT COUNT(*) FROM change_journal
            WHERE timestamp >= datetime('now', '-1 day')
        """).fetchone()[0]
        
        # Oldest and newest entries
        oldest = conn.execute(
            "SELECT MIN(timestamp) FROM change_journal"
        ).fetchone()[0]
        newest = conn.execute(
            "SELECT MAX(timestamp) FROM change_journal"
        ).fetchone()[0]
    
    return {
        'total_entries': total,
        'by_action': {row['action']: row['count'] for row in by_action},
        'by_entity_type': {row['entity_type']: row['count'] for row in by_type},
        'recent_24h': recent_count,
        'oldest_entry': oldest,
        'newest_entry': newest
    }


def cleanup_old_entries(days: int = 90) -> int:
    """
    Remove journal entries older than specified days.
    
    Args:
        days: Remove entries older than this many days
    
    Returns:
        Count of deleted entries
    """
    db = get_db()
    
    with db.connection() as conn:
        cursor = conn.execute("""
            DELETE FROM change_journal
            WHERE timestamp < datetime('now', ? || ' days')
        """, (f'-{days}',))
        conn.commit()
        
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} journal entries older than {days} days")
        return deleted


# CLI interface
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description='Change Journal CLI')
    parser.add_argument('--stats', action='store_true', help='Show journal statistics')
    parser.add_argument('--recent', type=int, help='Show N most recent entries')
    parser.add_argument('--entity', help='Filter by entity (asset/model)')
    parser.add_argument('--id', type=int, help='Filter by entity ID')
    parser.add_argument('--cleanup', type=int, help='Remove entries older than N days')
    args = parser.parse_args()
    
    if args.stats:
        stats = get_journal_stats()
        print("Change Journal Statistics")
        print("=" * 40)
        print(f"Total entries: {stats['total_entries']}")
        print(f"Last 24 hours: {stats['recent_24h']}")
        print(f"\nBy action:")
        for action, count in stats['by_action'].items():
            print(f"  {action}: {count}")
        print(f"\nBy type:")
        for etype, count in stats['by_entity_type'].items():
            print(f"  {etype}: {count}")
    
    elif args.recent:
        entries = get_journal_entries(
            entity_type=args.entity,
            entity_id=args.id,
            limit=args.recent
        )
        print(f"Recent {len(entries)} journal entries:")
        for entry in entries:
            print(f"  [{entry['timestamp'][:19]}] {entry['action']} {entry['entity_type']}#{entry['entity_id']}")
    
    elif args.cleanup:
        deleted = cleanup_old_entries(args.cleanup)
        print(f"Deleted {deleted} entries older than {args.cleanup} days")
    
    else:
        parser.print_help()
