"""
SSH Key Management Service.

Handles SSH key generation and management for remote backups.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default key location
DEFAULT_KEY_DIR = Path.home() / ".ssh"
DAM_KEY_NAME = "dam_backup_key"


def get_dam_key_path() -> Path:
    """Get path to DAM's SSH key."""
    return DEFAULT_KEY_DIR / DAM_KEY_NAME


def check_key_exists() -> Dict:
    """
    Check if DAM SSH key exists.
    
    Returns:
        Dict with exists, path, and public_key info
    """
    key_path = get_dam_key_path()
    pub_path = Path(str(key_path) + ".pub")
    
    result = {
        'exists': key_path.exists(),
        'key_path': str(key_path),
        'pub_path': str(pub_path),
        'public_key': None
    }
    
    if pub_path.exists():
        try:
            result['public_key'] = pub_path.read_text().strip()
        except Exception:
            pass
    
    return result


def generate_key(comment: str = "DAM Backup Key") -> Dict:
    """
    Generate a new SSH key pair for DAM backups.
    
    Args:
        comment: Comment to embed in key
    
    Returns:
        Dict with success status and key info
    """
    key_path = get_dam_key_path()
    
    result = {
        'success': False,
        'key_path': str(key_path),
        'pub_path': str(key_path) + ".pub"
    }
    
    # Check if key already exists
    if key_path.exists():
        result['error'] = 'Key already exists'
        result['exists'] = True
        return result
    
    # Ensure .ssh directory exists with correct permissions
    DEFAULT_KEY_DIR.mkdir(mode=0o700, exist_ok=True)
    
    try:
        # Generate ed25519 key (more secure than RSA)
        cmd = [
            'ssh-keygen',
            '-t', 'ed25519',
            '-f', str(key_path),
            '-N', '',  # No passphrase
            '-C', comment
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            result['success'] = True
            
            # Read public key
            pub_path = Path(result['pub_path'])
            if pub_path.exists():
                result['public_key'] = pub_path.read_text().strip()
            
            logger.info(f"Generated SSH key: {key_path}")
        else:
            result['error'] = proc.stderr or 'Key generation failed'
            logger.error(f"SSH key generation failed: {proc.stderr}")
    
    except FileNotFoundError:
        result['error'] = 'ssh-keygen not found'
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"SSH key generation error: {e}")
    
    return result


def delete_key() -> Dict:
    """
    Delete the DAM SSH key pair.
    
    Returns:
        Dict with success status
    """
    key_path = get_dam_key_path()
    pub_path = Path(str(key_path) + ".pub")
    
    result = {'success': False}
    
    try:
        deleted = []
        if key_path.exists():
            key_path.unlink()
            deleted.append('private key')
        if pub_path.exists():
            pub_path.unlink()
            deleted.append('public key')
        
        if deleted:
            result['success'] = True
            result['deleted'] = deleted
            logger.info(f"Deleted SSH key: {key_path}")
        else:
            result['error'] = 'Key not found'
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"SSH key deletion error: {e}")
    
    return result


def test_connection(host: str, key_path: Optional[str] = None) -> Dict:
    """
    Test SSH connection to a host.
    
    Args:
        host: SSH host (user@hostname or SSH config alias)
        key_path: Path to SSH key (optional - uses SSH config if not specified)
    
    Returns:
        Dict with success status and details
    """
    result = {
        'success': False,
        'host': host
    }
    
    # Build SSH command
    cmd = [
        'ssh',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=10',
        '-o', 'StrictHostKeyChecking=accept-new',
    ]
    
    # Only add -i if key_path is explicitly provided and exists
    if key_path:
        key_path = os.path.expanduser(key_path)
        if os.path.exists(key_path):
            cmd.extend(['-i', key_path])
        else:
            # Key specified but doesn't exist - warn but continue (might use SSH config)
            logger.warning(f"Specified key not found: {key_path}, falling back to SSH config")
    
    cmd.extend([host, 'echo "Connection successful"'])
    
    try:
        logger.info(f"Testing SSH connection: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if proc.returncode == 0:
            result['success'] = True
            result['message'] = 'Connection successful'
        else:
            error_msg = proc.stderr.strip() if proc.stderr else 'Connection failed'
            # Clean up common SSH error messages
            if 'Permission denied' in error_msg:
                result['error'] = 'Permission denied - check that your public key is in authorized_keys on the remote server'
            elif 'Host key verification failed' in error_msg:
                result['error'] = 'Host key verification failed - try connecting manually first'
            elif 'Connection refused' in error_msg:
                result['error'] = 'Connection refused - check host and port'
            elif 'No route to host' in error_msg or 'Network is unreachable' in error_msg:
                result['error'] = 'Cannot reach host - check network connectivity'
            else:
                result['error'] = error_msg
    
    except subprocess.TimeoutExpired:
        result['error'] = 'Connection timed out after 10 seconds'
    except Exception as e:
        result['error'] = str(e)
    
    return result


def list_system_keys() -> List[Dict]:
    """
    List SSH keys in ~/.ssh directory.
    
    Returns:
        List of key info dicts
    """
    keys = []
    
    if not DEFAULT_KEY_DIR.exists():
        return keys
    
    for path in DEFAULT_KEY_DIR.iterdir():
        # Skip public keys and known_hosts, config, etc
        if path.suffix == '.pub' or path.name in ('known_hosts', 'config', 'authorized_keys'):
            continue
        
        # Check if it's a private key (has matching .pub)
        pub_path = Path(str(path) + '.pub')
        if pub_path.exists():
            try:
                pub_key = pub_path.read_text().strip()
                # Parse key type and comment
                parts = pub_key.split()
                key_type = parts[0] if parts else 'unknown'
                comment = parts[2] if len(parts) > 2 else ''
                
                keys.append({
                    'name': path.name,
                    'path': str(path),
                    'type': key_type,
                    'comment': comment,
                    'is_dam_key': path.name == DAM_KEY_NAME
                })
            except Exception:
                pass
    
    return sorted(keys, key=lambda k: (not k['is_dam_key'], k['name']))


# CLI interface
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description='SSH Key Management')
    parser.add_argument('--check', action='store_true', help='Check if DAM key exists')
    parser.add_argument('--generate', action='store_true', help='Generate DAM key')
    parser.add_argument('--delete', action='store_true', help='Delete DAM key')
    parser.add_argument('--list', action='store_true', help='List all SSH keys')
    parser.add_argument('--test', help='Test connection to host')
    args = parser.parse_args()
    
    if args.check:
        result = check_key_exists()
        print(f"Key exists: {result['exists']}")
        if result['public_key']:
            print(f"Public key:\n{result['public_key']}")
    
    elif args.generate:
        result = generate_key()
        if result['success']:
            print("Key generated successfully!")
            print(f"Path: {result['key_path']}")
            print(f"\nPublic key (add to remote host's authorized_keys):")
            print(result['public_key'])
        else:
            print(f"Failed: {result.get('error')}")
    
    elif args.delete:
        result = delete_key()
        if result['success']:
            print(f"Deleted: {', '.join(result['deleted'])}")
        else:
            print(f"Failed: {result.get('error')}")
    
    elif args.list:
        keys = list_system_keys()
        print(f"SSH Keys ({len(keys)}):")
        for k in keys:
            dam = " [DAM]" if k['is_dam_key'] else ""
            print(f"  {k['name']}{dam} - {k['type']} - {k['comment']}")
    
    elif args.test:
        result = test_connection(args.test)
        if result['success']:
            print(f"✓ Connection to {args.test} successful")
        else:
            print(f"✗ Connection failed: {result.get('error')}")
    
    else:
        parser.print_help()
