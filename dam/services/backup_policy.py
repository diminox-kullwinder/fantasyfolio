"""
Backup Policy Service.

Manages flexible backup policies with validation, scheduling, and execution.
Supports multiple named policies with local or network destinations.
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dam.core.database import get_setting, set_setting

logger = logging.getLogger(__name__)


# Policy states
STATE_ACTIVE = 'active'
STATE_PAUSED = 'paused'
STATE_DISABLED = 'disabled'

# Destination types
DEST_LOCAL = 'local'
DEST_NETWORK = 'network'
DEST_RESTIC = 'restic'
DEST_RESTIC_REMOTE = 'restic-remote'

# Frequency options
FREQUENCIES = {
    'hourly': timedelta(hours=1),
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
    'monthly': timedelta(days=30),
    'yearly': timedelta(days=365),
}


def get_all_policies() -> List[Dict]:
    """
    Get all backup policies.
    
    Returns:
        List of policy dicts sorted by state (active first) then name
    """
    try:
        policies_json = get_setting('backup_policies_v2')
        if policies_json:
            policies = json.loads(policies_json)
            # Sort: active first, then paused, then disabled, then by name
            state_order = {STATE_ACTIVE: 0, STATE_PAUSED: 1, STATE_DISABLED: 2}
            return sorted(policies, key=lambda p: (state_order.get(p.get('state', STATE_DISABLED), 2), p.get('name', '')))
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def save_all_policies(policies: List[Dict]) -> bool:
    """Save all policies to settings."""
    try:
        set_setting('backup_policies_v2', json.dumps(policies))
        return True
    except Exception as e:
        logger.error(f"Failed to save policies: {e}")
        return False


def get_policy_by_id(policy_id: str) -> Optional[Dict]:
    """Get a single policy by ID."""
    policies = get_all_policies()
    for p in policies:
        if p.get('id') == policy_id:
            return p
    return None


def create_policy(policy_data: Dict) -> Dict:
    """
    Create a new backup policy.
    
    Args:
        policy_data: Policy configuration
    
    Returns:
        Dict with success status and created policy or error
    """
    result = {'success': False}
    
    # Validate required fields
    validation = validate_policy(policy_data)
    if not validation['valid']:
        result['error'] = validation['error']
        result['field'] = validation.get('field')
        return result
    
    # Generate ID if not provided
    policy_id = policy_data.get('id') or str(uuid.uuid4())[:8]
    
    # Build policy object
    policy = {
        'id': policy_id,
        'name': policy_data['name'].strip(),
        'destination_type': policy_data['destination_type'],
        'path': policy_data['path'].strip(),
        'frequency': policy_data['frequency'],
        'schedule_time': policy_data.get('schedule_time', '02:00'),
        'start_date': policy_data.get('start_date'),  # ISO date string or None
        'state': policy_data.get('state', STATE_DISABLED),
        'ssh_host': policy_data.get('ssh_host', '').strip(),
        'ssh_key_path': policy_data.get('ssh_key_path', '').strip(),
        'restic_password': policy_data.get('restic_password', ''),  # For Restic repos
        'keep_count': int(policy_data.get('keep_count') or policy_data.get('retention_count') or 10),
        'created_at': datetime.now().isoformat(),
        'last_backup': None,
        'last_backup_status': None,
        'next_scheduled': None
    }
    
    # Calculate next scheduled if active
    if policy['state'] == STATE_ACTIVE:
        policy['next_scheduled'] = _calculate_next_run(
            policy['frequency'], 
            policy.get('schedule_time'),
            policy.get('start_date')
        )
    
    # Add to policies list
    policies = get_all_policies()
    policies.append(policy)
    
    if save_all_policies(policies):
        result['success'] = True
        result['policy'] = policy
        logger.info(f"Created backup policy: {policy['name']}")
    else:
        result['error'] = 'Failed to save policy'
    
    return result


def update_policy(policy_id: str, updates: Dict) -> Dict:
    """
    Update an existing policy.
    
    Args:
        policy_id: ID of policy to update
        updates: Fields to update
    
    Returns:
        Dict with success status
    """
    result = {'success': False}
    
    policies = get_all_policies()
    policy_index = None
    
    for i, p in enumerate(policies):
        if p.get('id') == policy_id:
            policy_index = i
            break
    
    if policy_index is None:
        result['error'] = 'Policy not found'
        return result
    
    # Merge updates
    policy = policies[policy_index]
    
    # If changing to active, validate first
    if updates.get('state') == STATE_ACTIVE and policy.get('state') != STATE_ACTIVE:
        merged = {**policy, **updates}
        validation = validate_policy(merged, check_connectivity=True)
        if not validation['valid']:
            result['error'] = validation['error']
            result['field'] = validation.get('field')
            return result
    
    for key, value in updates.items():
        if key != 'id':  # Don't allow ID changes
            policy[key] = value
    
    policy['updated_at'] = datetime.now().isoformat()
    
    # Recalculate next scheduled
    if policy['state'] == STATE_ACTIVE:
        policy['next_scheduled'] = _calculate_next_run(
            policy['frequency'],
            policy.get('schedule_time'),
            policy.get('start_date'),
            policy.get('last_backup')
        )
    else:
        policy['next_scheduled'] = None
    
    policies[policy_index] = policy
    
    if save_all_policies(policies):
        result['success'] = True
        result['policy'] = policy
        logger.info(f"Updated backup policy: {policy['name']}")
    else:
        result['error'] = 'Failed to save policy'
    
    return result


def delete_policy(policy_id: str) -> Dict:
    """Delete a policy by ID."""
    result = {'success': False}
    
    policies = get_all_policies()
    original_count = len(policies)
    policies = [p for p in policies if p.get('id') != policy_id]
    
    if len(policies) == original_count:
        result['error'] = 'Policy not found'
        return result
    
    if save_all_policies(policies):
        result['success'] = True
        logger.info(f"Deleted backup policy: {policy_id}")
    else:
        result['error'] = 'Failed to save policies'
    
    return result


def validate_policy(policy_data: Dict, check_connectivity: bool = False) -> Dict:
    """
    Validate a policy configuration.
    
    Args:
        policy_data: Policy to validate
        check_connectivity: If True, also test network connectivity
    
    Returns:
        Dict with valid status and error if invalid
    """
    result = {'valid': True}
    
    # Required fields
    if not policy_data.get('name', '').strip():
        return {'valid': False, 'error': 'Policy name is required', 'field': 'name'}
    
    if not policy_data.get('path', '').strip():
        return {'valid': False, 'error': 'Destination path is required', 'field': 'path'}
    
    if not policy_data.get('frequency'):
        return {'valid': False, 'error': 'Frequency is required', 'field': 'frequency'}
    
    if policy_data['frequency'] not in FREQUENCIES:
        return {'valid': False, 'error': f"Invalid frequency: {policy_data['frequency']}", 'field': 'frequency'}
    
    dest_type = policy_data.get('destination_type', DEST_LOCAL)
    path = policy_data['path'].strip()
    
    if dest_type == DEST_LOCAL:
        # Validate local path exists and is writable
        if not os.path.isdir(path):
            return {'valid': False, 'error': f'Directory does not exist: {path}', 'field': 'path'}
        
        # Test write access
        test_file = Path(path) / '.dam_write_test'
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            return {'valid': False, 'error': f'Directory not writable: {e}', 'field': 'path'}
    
    elif dest_type == DEST_NETWORK:
        # Network destination requires SSH host
        ssh_host = policy_data.get('ssh_host', '').strip()
        if not ssh_host:
            return {'valid': False, 'error': 'SSH host is required for network backups', 'field': 'ssh_host'}
        
        # Validate SSH key exists if specified
        ssh_key = policy_data.get('ssh_key_path', '').strip()
        if ssh_key and not os.path.exists(os.path.expanduser(ssh_key)):
            return {'valid': False, 'error': f'SSH key not found: {ssh_key}', 'field': 'ssh_key_path'}
        
        # Test connectivity if requested
        if check_connectivity:
            from dam.services.rsync_wrapper import test_rsync_connection
            key_path = os.path.expanduser(ssh_key) if ssh_key else None
            conn_test = test_rsync_connection(ssh_host, path, key_path)
            if not conn_test['success']:
                return {'valid': False, 'error': f"Connection failed: {conn_test.get('error')}", 'field': 'ssh_host'}
    
    elif dest_type in (DEST_RESTIC, DEST_RESTIC_REMOTE):
        # Restic destination requires password
        restic_password = policy_data.get('restic_password', '').strip()
        if not restic_password:
            return {'valid': False, 'error': 'Restic repository password is required', 'field': 'restic_password'}
        
        # Validate remote format
        if dest_type == DEST_RESTIC_REMOTE and not path.startswith('sftp:'):
            return {'valid': False, 'error': 'Remote path must start with sftp: (e.g., sftp:user@host:/path)', 'field': 'path'}
        
        # Check if restic is installed
        from dam.services.restic_backup import check_restic_installed
        restic_check = check_restic_installed()
        if not restic_check.get('installed'):
            return {'valid': False, 'error': restic_check.get('error', 'Restic not installed'), 'field': 'path'}
    
    return result


def run_policy_backup(policy_id: str) -> Dict:
    """
    Execute a backup for a specific policy.
    
    Args:
        policy_id: ID of policy to run
    
    Returns:
        Dict with backup result
    """
    policy = get_policy_by_id(policy_id)
    if not policy:
        return {'success': False, 'error': 'Policy not found'}
    
    result = {
        'success': False,
        'policy_id': policy_id,
        'policy_name': policy['name'],
        'timestamp': datetime.now().isoformat()
    }
    
    # Get latest snapshot to backup
    from dam.services.snapshot import get_latest_snapshot
    snapshot = get_latest_snapshot()
    
    if not snapshot:
        result['error'] = 'No snapshots available to backup'
        return result
    
    source_path = snapshot['path']
    result['source'] = source_path
    
    try:
        if policy['destination_type'] in (DEST_RESTIC, DEST_RESTIC_REMOTE):
            # Restic deduplicated backup
            from dam.services.restic_backup import run_backup, prune_snapshots, init_repo
            
            repo_path = policy['path']
            password = policy.get('restic_password', '')
            
            if not password:
                result['error'] = 'Restic repository password not configured'
                return result
            
            # Auto-initialize repo if it doesn't exist
            init_result = init_repo(repo_path, password)
            if not init_result.get('success'):
                result['error'] = f"Failed to initialize repository: {init_result.get('error')}"
                return result
            
            backup_result = run_backup(
                repo_path,
                password,
                source_path,
                tags=[f"policy:{policy['name']}", 'dam-backup']
            )
            
            # Prune old snapshots according to retention
            if backup_result.get('success'):
                keep_count = policy.get('keep_count', 10)
                prune_snapshots(repo_path, password, keep_count)
        
        elif policy['destination_type'] == DEST_LOCAL:
            from dam.services.rsync_wrapper import rsync_local
            backup_result = rsync_local(
                source_path,
                policy['path'],
                filename_prefix=f"dam_{policy['name'].replace(' ', '_')}",
                delete_old=policy.get('keep_count', 10)
            )
        else:
            from dam.services.rsync_wrapper import rsync_ssh
            key_path = policy.get('ssh_key_path')
            if key_path:
                key_path = os.path.expanduser(key_path)
            
            backup_result = rsync_ssh(
                source_path,
                policy['ssh_host'],
                policy['path'],
                key_path=key_path,
                filename_prefix=f"dam_{policy['name'].replace(' ', '_')}"
            )
        
        if backup_result['success']:
            result['success'] = True
            result['destination'] = backup_result.get('destination')
            result['size_bytes'] = backup_result.get('size_bytes')
            
            # Update policy with last backup info
            update_policy(policy_id, {
                'last_backup': result['timestamp'],
                'last_backup_status': 'success'
            })
        else:
            result['error'] = backup_result.get('error', 'Backup failed')
            update_policy(policy_id, {
                'last_backup': result['timestamp'],
                'last_backup_status': 'failed'
            })
    
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Backup failed for policy {policy['name']}: {e}", exc_info=True)
    
    return result


def get_active_policies() -> List[Dict]:
    """Get policies with state='active'."""
    return [p for p in get_all_policies() if p.get('state') == STATE_ACTIVE]


def get_inactive_policies() -> List[Dict]:
    """Get policies with state='paused' or 'disabled'."""
    return [p for p in get_all_policies() if p.get('state') in (STATE_PAUSED, STATE_DISABLED)]


def get_policies_due() -> List[Dict]:
    """Get active policies that are due to run."""
    now = datetime.now()
    due = []
    
    for policy in get_active_policies():
        next_scheduled = policy.get('next_scheduled')
        if next_scheduled:
            try:
                next_dt = datetime.fromisoformat(next_scheduled)
                if next_dt <= now:
                    due.append(policy)
            except (ValueError, TypeError):
                pass
    
    return due


def _calculate_next_run(frequency: str, schedule_time: Optional[str] = None, start_date: Optional[str] = None, last_run: Optional[str] = None) -> str:
    """
    Calculate next scheduled run time.
    
    Args:
        frequency: daily, weekly, monthly, yearly
        schedule_time: Time of day in HH:MM format (default 02:00)
        start_date: Start date in YYYY-MM-DD format (optional)
        last_run: Last run timestamp (for calculating next from last)
    """
    delta = FREQUENCIES.get(frequency, timedelta(days=1))
    now = datetime.now()
    
    # Parse schedule time (default 02:00 AM)
    hour, minute = 2, 0
    if schedule_time:
        try:
            parts = schedule_time.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            pass
    
    # Determine base date
    if last_run:
        try:
            base = datetime.fromisoformat(last_run)
            next_run = base + delta
        except (ValueError, TypeError):
            next_run = now + delta
    elif start_date:
        try:
            # Start from the specified date
            start = datetime.strptime(start_date, '%Y-%m-%d')
            next_run = start.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except (ValueError, TypeError):
            next_run = now + delta
    else:
        # Start from now, next occurrence at scheduled time
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + delta
    
    # Apply scheduled time to the calculated date
    next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If next run is in the past, advance until it's in the future
    while next_run < now:
        next_run = next_run + delta
    
    return next_run.isoformat()


# CLI interface
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description='Backup Policy CLI')
    parser.add_argument('--list', action='store_true', help='List all policies')
    parser.add_argument('--run', help='Run backup for policy ID')
    args = parser.parse_args()
    
    if args.list:
        policies = get_all_policies()
        print(f"Backup Policies ({len(policies)}):")
        for p in policies:
            state = p.get('state', 'disabled')
            print(f"  [{state:8}] {p['name']} -> {p['path']} ({p['frequency']})")
    
    elif args.run:
        result = run_policy_backup(args.run)
        if result['success']:
            print(f"✓ Backup completed: {result.get('destination')}")
        else:
            print(f"✗ Backup failed: {result.get('error')}")
    
    else:
        parser.print_help()
