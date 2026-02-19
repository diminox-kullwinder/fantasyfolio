"""
Efficient scanning logic for FantasyFolio assets.

Implements the scan algorithms from the Efficient Indexing Architecture v1.2:
- Standard mode: Skip unchanged files (mtime/size match)
- Forced mode: Reprocess everything
- Missing detection: Mark files as missing, never auto-delete
"""

import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Generator, Optional, Literal, Dict, Any
from enum import Enum

from fantasyfolio.core.hashing import compute_partial_hash, compute_partial_hash_from_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# GLTF VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_gltf_dependencies(file_path: Path) -> tuple[bool, str]:
    """
    Check if a text GLTF file has all required companion files.
    
    Text GLTF (.gltf) files reference external resources:
    - Binary buffers (.bin files)
    - Textures (PNG/JPG files)
    
    Binary GLB files are self-contained and always valid.
    
    Returns:
        (is_valid, error_message)
    """
    if file_path.suffix.lower() == '.glb':
        return (True, "")  # GLB is always self-contained
    
    if file_path.suffix.lower() != '.gltf':
        return (True, "")  # Not a GLTF file
    
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            gltf_data = json.load(f)
        
        parent_dir = file_path.parent
        missing_files = []
        
        # Check buffers
        if 'buffers' in gltf_data:
            for buf in gltf_data['buffers']:
                if 'uri' in buf and not buf['uri'].startswith('data:'):
                    # External file reference
                    ref_path = parent_dir / buf['uri']
                    if not ref_path.exists():
                        missing_files.append(buf['uri'])
        
        # Check images/textures
        if 'images' in gltf_data:
            for img in gltf_data['images']:
                if 'uri' in img and not img['uri'].startswith('data:'):
                    ref_path = parent_dir / img['uri']
                    if not ref_path.exists():
                        missing_files.append(img['uri'])
        
        if missing_files:
            return (False, f"Missing companion files: {', '.join(missing_files[:3])}")
        
        return (True, "")
    
    except Exception as e:
        return (False, f"GLTF validation error: {str(e)}")


class ScanAction(Enum):
    SKIP = 'skip'
    NEW = 'new'
    UPDATE = 'update'
    MOVED = 'moved'
    MISSING = 'missing'
    ERROR = 'error'
    DUPLICATE = 'duplicate'  # Same hash as existing file at different path


@dataclass
class ScanResult:
    """Result of scanning a single asset."""
    action: ScanAction
    model: Dict[str, Any]
    reason: str


# ═══════════════════════════════════════════════════════════════════════════════
# IDENTITY RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

def find_existing_asset(
    conn: sqlite3.Connection,
    table: str,
    file_path: str = None,
    archive_path: str = None,
    archive_member: str = None,
    partial_hash: str = None,
    file_size: int = None,
    file_mtime: int = None
) -> tuple[str, Optional[dict]]:
    """
    Find existing asset by identity.
    
    Returns: (match_type, existing_record)
    
    match_type values:
    - 'unchanged': Same path, same mtime/size — skip processing
    - 'touched':   Same path, mtime changed but content same (hash match)
    - 'modified':  Same path, content changed (hash mismatch)
    - 'moved':     Same content (hash), different path
    - 'new':       No match found
    """
    conn.row_factory = sqlite3.Row
    
    # Check 1: Exact path match
    if archive_path and archive_member:
        existing = conn.execute(f"""
            SELECT * FROM {table} 
            WHERE archive_path = ? AND archive_member = ?
        """, (archive_path, archive_member)).fetchone()
    elif file_path:
        existing = conn.execute(f"""
            SELECT * FROM {table} WHERE file_path = ?
        """, (file_path,)).fetchone()
    else:
        existing = None
    
    if existing:
        existing = dict(existing)
        
        # Check if unchanged (mtime + size match)
        if (existing.get('file_mtime') == file_mtime and 
            existing.get('file_size_bytes') == file_size):
            return ('unchanged', existing)
        
        # Path exists but may have changed - check hash if available
        if partial_hash and existing.get('partial_hash') == partial_hash:
            return ('touched', existing)  # mtime changed, content same
        elif partial_hash and existing.get('partial_hash'):
            return ('modified', existing)  # Content changed
        else:
            # No hash to compare, assume modified if mtime changed
            return ('modified', existing)
    
    # Check 2: Content match by hash (file may have moved)
    if partial_hash:
        moved = conn.execute(f"""
            SELECT * FROM {table} WHERE partial_hash = ?
        """, (partial_hash,)).fetchone()
        
        if moved:
            return ('moved', dict(moved))
    
    return ('new', None)


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE FILE SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

def scan_file(
    conn: sqlite3.Connection,
    file_path: Path,
    volume: dict,
    force: bool = False,
    duplicate_policy: Literal['reject', 'warn', 'merge'] = 'merge'
) -> ScanResult:
    """
    Scan a single standalone file.
    
    Args:
        conn: Database connection
        file_path: Path to file
        volume: Volume record dict
        force: If True, reprocess regardless of cache
        duplicate_policy: How to handle duplicate files (same hash, different path)
            - 'reject': Skip duplicate, don't create new record
            - 'warn': Create record but flag as duplicate
            - 'merge': Update existing record to point to new location (default)
    
    Returns:
        ScanResult with action and model data
    """
    now = datetime.now().isoformat()
    
    # Get file stats
    try:
        stat = file_path.stat()
    except FileNotFoundError:
        return ScanResult(
            ScanAction.MISSING,
            {'file_path': str(file_path)},
            'file not found'
        )
    except PermissionError as e:
        return ScanResult(
            ScanAction.ERROR,
            {'file_path': str(file_path)},
            f'permission denied: {e}'
        )
    
    file_size = stat.st_size
    file_mtime = int(stat.st_mtime)
    
    # Find existing record by path (without hash first for speed)
    match_type, existing = find_existing_asset(
        conn, 'models',
        file_path=str(file_path),
        file_size=file_size,
        file_mtime=file_mtime
    )
    
    # Handle unchanged case (fast path)
    if match_type == 'unchanged' and not force:
        return ScanResult(
            ScanAction.SKIP,
            {
                **existing,
                'last_seen_at': now,
                'index_status': 'indexed',
                'missing_since': None,
            },
            'unchanged (mtime match)'
        )
    
    # Need hash for further checks
    partial_hash = compute_partial_hash(file_path)
    
    # Check for duplicate (same hash at different path) - ALWAYS CHECK
    hash_match = conn.execute("""
        SELECT * FROM models 
        WHERE partial_hash = ? AND file_path != ?
        ORDER BY last_seen_at DESC
        LIMIT 1
    """, (partial_hash, str(file_path))).fetchone()
    
    if hash_match and not existing:
        # Same content, different path - handle based on policy
        hash_match = dict(hash_match)
        
        if duplicate_policy == 'reject':
            # Don't create duplicate - skip this file
            return ScanResult(
                ScanAction.DUPLICATE,
                hash_match,
                f"duplicate of {hash_match.get('file_path')} (rejected by policy)"
            )
        
        elif duplicate_policy == 'warn':
            # Create new record but flag as duplicate
            return ScanResult(
                ScanAction.NEW,
                {
                    'file_path': str(file_path),
                    'filename': file_path.name,
                    'relative_path': str(file_path.relative_to(volume['mount_path'])),
                    'volume_id': volume['id'],
                    'format': file_path.suffix[1:].lower(),
                    'file_size_bytes': file_size,
                    'file_mtime': file_mtime,
                    'partial_hash': partial_hash,
                    'index_status': 'indexed',
                    'last_indexed_at': now,
                    'last_seen_at': now,
                    'is_duplicate': 1,
                    'duplicate_of_id': hash_match['id'],
                },
                f"duplicate of {hash_match.get('file_path')} (flagged)"
            )
        
        elif duplicate_policy == 'merge':
            # Compute folder_path for new location
            folder_path = str(file_path.parent.relative_to(volume['mount_path']))
            if folder_path == '.':
                folder_path = ''
            
            # Treat as moved file - update existing record
            return ScanResult(
                ScanAction.MOVED,
                {
                    **hash_match,
                    'file_path': str(file_path),
                    'relative_path': str(file_path.relative_to(volume['mount_path'])),
                    'folder_path': folder_path,
                    'file_mtime': file_mtime,
                    'file_size_bytes': file_size,
                    'index_status': 'indexed',
                    'missing_since': None,
                    'last_verified_at': now,
                    'last_seen_at': now,
                },
                f"merged with {hash_match.get('file_path')} (same content)"
            )
    
    # Re-check with hash (existing file at this path)
    if existing and not force:
        if existing.get('partial_hash') == partial_hash:
            # mtime changed but content same
            return ScanResult(
                ScanAction.UPDATE,
                {
                    **existing,
                    'file_mtime': file_mtime,
                    'last_verified_at': now,
                    'last_seen_at': now,
                    'index_status': 'indexed',
                    'missing_since': None,
                },
                'touched (content unchanged)'
            )
    
    # Check for moved file (same hash, different path) - Legacy path
    if not existing and not hash_match:
        _, moved = find_existing_asset(
            conn, 'models',
            partial_hash=partial_hash
        )
        
        if moved:
            return ScanResult(
                ScanAction.MOVED,
                {
                    **moved,
                    'file_path': str(file_path),
                    'relative_path': str(file_path.relative_to(volume['mount_path'])),
                    'file_mtime': file_mtime,
                    'file_size_bytes': file_size,
                    'index_status': 'indexed',
                    'missing_since': None,
                    'last_verified_at': now,
                    'last_seen_at': now,
                },
                f"moved from {moved.get('file_path', 'unknown')}"
            )
    
    # Modified or forced re-index
    if existing:
        # Compute folder_path (may have changed if file moved or not set yet)
        folder_path = str(file_path.parent.relative_to(volume['mount_path']))
        if folder_path == '.':
            folder_path = ''
        
        return ScanResult(
            ScanAction.UPDATE,
            {
                **existing,
                'folder_path': folder_path,
                'file_mtime': file_mtime,
                'file_size_bytes': file_size,
                'partial_hash': partial_hash,
                'last_indexed_at': now,
                'last_seen_at': now,
                'index_status': 'indexed',
                'missing_since': None,
                'force_rerender': 1,  # Thumbnail needs update
            },
            'modified' if not force else 'forced re-index'
        )
    
    # Validate GLTF dependencies before marking as new
    file_format = file_path.suffix[1:].lower()
    if file_format == 'gltf':
        is_valid, error_msg = validate_gltf_dependencies(file_path)
        if not is_valid:
            return ScanResult(
                ScanAction.ERROR,
                {
                    'file_path': str(file_path),
                    'filename': file_path.name,
                    'format': file_format,
                },
                f'GLTF validation failed: {error_msg}'
            )
    
    # Compute folder_path (parent directory relative to volume mount)
    folder_path = str(file_path.parent.relative_to(volume['mount_path']))
    if folder_path == '.':
        folder_path = ''  # Empty string for files at volume root
    
    # New file
    return ScanResult(
        ScanAction.NEW,
        {
            'file_path': str(file_path),
            'filename': file_path.name,
            'relative_path': str(file_path.relative_to(volume['mount_path'])),
            'folder_path': folder_path,
            'volume_id': volume['id'],
            'format': file_format,
            'file_size_bytes': file_size,
            'file_mtime': file_mtime,
            'partial_hash': partial_hash,
            'index_status': 'indexed',
            'last_indexed_at': now,
            'last_seen_at': now,
        },
        'new file'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ARCHIVE SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

def scan_archive(
    conn: sqlite3.Connection,
    archive_path: Path,
    volume: dict,
    force: bool = False,
    duplicate_policy: Literal['reject', 'warn', 'merge'] = 'merge'
) -> Generator[ScanResult, None, None]:
    """
    Scan models inside a ZIP archive.
    
    Args:
        duplicate_policy: How to handle duplicate files (same hash, different archive member)
    
    Yields ScanResult for each model found.
    """
    MODEL_EXTENSIONS = {'.stl', '.obj', '.3mf', '.glb', '.gltf', '.svg', '.dae', '.3ds', '.ply', '.x3d'}
    
    try:
        archive_mtime = int(archive_path.stat().st_mtime)
    except (FileNotFoundError, PermissionError) as e:
        yield ScanResult(
            ScanAction.ERROR,
            {'archive_path': str(archive_path)},
            str(e)
        )
        return
    
    # Determine archive type
    archive_ext = archive_path.suffix.lower()
    
    try:
        if archive_ext == '.rar':
            # Handle RAR archives
            import rarfile
            rarfile.UNRAR_TOOL = "unar"  # Use unar instead of unrar
            
            with rarfile.RarFile(archive_path, 'r') as rf:
                for member in rf.namelist():
                    # Skip directories
                    if member.endswith('/'):
                        continue
                    
                    # Skip non-model files
                    ext = Path(member).suffix.lower()
                    if ext not in MODEL_EXTENSIONS:
                        continue
                    
                    # Skip macOS metadata
                    if '__MACOSX' in member or Path(member).name.startswith('.'):
                        continue
                    
                    yield scan_archive_member(
                        conn, archive_path, member, archive_mtime, volume, rf, force
                    )
        else:
            # Handle ZIP archives
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for member in zf.namelist():
                    # Skip directories
                    if member.endswith('/'):
                        continue
                    
                    # Skip non-model files
                    ext = Path(member).suffix.lower()
                    if ext not in MODEL_EXTENSIONS:
                        continue
                    
                    # Skip macOS metadata
                    if '__MACOSX' in member or Path(member).name.startswith('.'):
                        continue
                    
                    yield scan_archive_member(
                        conn, archive_path, member, archive_mtime, volume, zf, force
                    )
                
    except (zipfile.BadZipFile, Exception) as e:
        yield ScanResult(
            ScanAction.ERROR,
            {'archive_path': str(archive_path)},
            f'bad archive: {e}'
        )


def scan_archive_member(
    conn: sqlite3.Connection,
    archive_path: Path,
    member: str,
    archive_mtime: int,
    volume: dict,
    zf,  # zipfile.ZipFile or rarfile.RarFile
    force: bool
) -> ScanResult:
    """Scan a single member inside an archive (ZIP or RAR)."""
    now = datetime.now().isoformat()
    
    # Check for existing record (without hash first)
    match_type, existing = find_existing_asset(
        conn, 'models',
        archive_path=str(archive_path),
        archive_member=member,
        file_mtime=archive_mtime
    )
    
    # Fast path: unchanged
    if match_type == 'unchanged' and not force:
        return ScanResult(
            ScanAction.SKIP,
            {
                **existing,
                'last_seen_at': now,
                'index_status': 'indexed',
                'missing_since': None,
            },
            'archive unchanged'
        )
    
    # Read member data for hashing
    try:
        data = zf.read(member)
        file_size = len(data)
        partial_hash = compute_partial_hash_from_bytes(data)
    except Exception as e:
        return ScanResult(
            ScanAction.ERROR,
            {
                'archive_path': str(archive_path),
                'archive_member': member,
            },
            str(e)
        )
    
    # Check for duplicate (same hash, different archive member) - ALWAYS CHECK
    hash_match = conn.execute("""
        SELECT * FROM models 
        WHERE partial_hash = ? 
        AND NOT (archive_path = ? AND archive_member = ?)
        ORDER BY last_seen_at DESC
        LIMIT 1
    """, (partial_hash, str(archive_path), member)).fetchone()
    
    if hash_match and not existing:
        # Same content, different location - handle based on policy
        hash_match = dict(hash_match)
        
        if duplicate_policy == 'reject':
            return ScanResult(
                ScanAction.DUPLICATE,
                hash_match,
                f"duplicate of {hash_match.get('archive_path', hash_match.get('file_path'))} (rejected)"
            )
        
        elif duplicate_policy == 'warn':
            return ScanResult(
                ScanAction.NEW,
                {
                    'archive_path': str(archive_path),
                    'archive_member': member,
                    'filename': Path(member).name,
                    'volume_id': volume['id'],
                    'format': Path(member).suffix[1:].lower(),
                    'file_size_bytes': file_size,
                    'file_mtime': archive_mtime,
                    'partial_hash': partial_hash,
                    'index_status': 'indexed',
                    'last_indexed_at': now,
                    'last_seen_at': now,
                    'is_duplicate': 1,
                    'duplicate_of_id': hash_match['id'],
                },
                f"duplicate (flagged)"
            )
        
        elif duplicate_policy == 'merge':
            return ScanResult(
                ScanAction.MOVED,
                {
                    **hash_match,
                    'archive_path': str(archive_path),
                    'archive_member': member,
                    'file_mtime': archive_mtime,
                    'file_size_bytes': file_size,
                    'last_verified_at': now,
                    'last_seen_at': now,
                    'index_status': 'indexed',
                    'missing_since': None,
                },
                f"merged (same content)"
            )
    
    # Re-check with hash
    if existing and not force:
        if existing.get('partial_hash') == partial_hash:
            return ScanResult(
                ScanAction.SKIP,
                {
                    **existing,
                    'last_seen_at': now,
                },
                'content unchanged'
            )
    
    # Check for moved (same hash elsewhere)
    if not existing:
        _, moved = find_existing_asset(
            conn, 'models',
            partial_hash=partial_hash
        )
        
        if moved:
            return ScanResult(
                ScanAction.MOVED,
                {
                    **moved,
                    'archive_path': str(archive_path),
                    'archive_member': member,
                    'file_mtime': archive_mtime,
                    'file_size_bytes': file_size,
                    'last_verified_at': now,
                    'last_seen_at': now,
                    'index_status': 'indexed',
                    'missing_since': None,
                },
                f"moved from {moved.get('archive_path', moved.get('file_path'))}"
            )
    
    # Modified or new
    if existing:
        return ScanResult(
            ScanAction.UPDATE,
            {
                **existing,
                'file_size_bytes': file_size,
                'file_mtime': archive_mtime,
                'partial_hash': partial_hash,
                'last_indexed_at': now,
                'last_seen_at': now,
                'index_status': 'indexed',
                'missing_since': None,
                'force_rerender': 1,
            },
            'modified' if not force else 'forced re-index'
        )
    
    # Compute folder_path (archive parent directory relative to volume mount)
    folder_path = str(archive_path.parent.relative_to(volume['mount_path']))
    if folder_path == '.':
        folder_path = ''
    
    # New member
    return ScanResult(
        ScanAction.NEW,
        {
            'archive_path': str(archive_path),
            'archive_member': member,
            'filename': Path(member).name,
            'relative_path': str(archive_path.relative_to(volume['mount_path'])),
            'folder_path': folder_path,
            'volume_id': volume['id'],
            'format': Path(member).suffix[1:].lower(),
            'file_size_bytes': file_size,
            'file_mtime': archive_mtime,
            'partial_hash': partial_hash,
            'index_status': 'indexed',
            'last_indexed_at': now,
            'last_seen_at': now,
        },
        'new archive member'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECTORY SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

def scan_directory(
    conn: sqlite3.Connection,
    path: Path,
    volume: dict,
    force: bool = False,
    recursive: bool = True,
    duplicate_policy: Literal['reject', 'warn', 'merge'] = 'merge'
) -> Generator[ScanResult, None, None]:
    """
    Scan directory for assets.
    
    Args:
        duplicate_policy: How to handle duplicate files (same hash, different path)
            - 'reject': Skip duplicates
            - 'warn': Create records but flag as duplicates
            - 'merge': Update existing records (default)
    
    Yields ScanResult for each file/archive member found.
    """
    MODEL_EXTENSIONS = {'.stl', '.obj', '.3mf', '.glb', '.gltf', '.svg', '.dae', '.3ds', '.ply', '.x3d'}
    ARCHIVE_EXTENSIONS = {'.zip', '.rar'}
    
    pattern = '**/*' if recursive else '*'
    
    for file_path in path.glob(pattern):
        if file_path.is_dir():
            continue
        
        # Skip hidden files
        if file_path.name.startswith('.'):
            continue
        
        ext = file_path.suffix.lower()
        
        if ext in ARCHIVE_EXTENSIONS:
            # Scan inside archive
            yield from scan_archive(conn, file_path, volume, force, duplicate_policy)
        elif ext in MODEL_EXTENSIONS:
            # Standalone file
            yield scan_file(conn, file_path, volume, force, duplicate_policy)


# ═══════════════════════════════════════════════════════════════════════════════
# MISSING ASSET HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

def handle_missing_asset(
    conn: sqlite3.Connection,
    model: dict,
    volume: dict
) -> str:
    """
    Handle case where file is not found.
    
    NEVER deletes — only updates status.
    
    Returns: New status ('offline', 'missing', or 'indexed' if found by hash)
    """
    now = datetime.now().isoformat()
    
    # Check 1: Is the volume actually online?
    if volume.get('status') != 'online':
        # Volume is offline — don't mark asset as missing
        conn.execute("""
            UPDATE models SET 
                index_status = 'offline',
                last_verified_at = ?
            WHERE id = ?
        """, (now, model['id']))
        return 'offline'
    
    # Check 2: Try to find by hash (maybe file was moved)
    if model.get('partial_hash'):
        # This would require a full volume scan - expensive
        # For now, just mark as missing and let user relocate
        pass
    
    # Check 3: File is genuinely missing
    conn.execute("""
        UPDATE models SET 
            index_status = 'missing',
            missing_since = COALESCE(missing_since, ?),
            last_verified_at = ?
        WHERE id = ?
    """, (now, now, model['id']))
    
    return 'missing'


def verify_assets_on_volume(
    conn: sqlite3.Connection,
    volume_id: str,
    callback=None
) -> dict:
    """
    Verify all assets on a volume exist.
    Called when volume comes back online.
    
    Returns:
        Dict with counts: verified, still_missing, found, moved
    """
    stats = {
        'verified': 0,
        'still_missing': 0,
        'found': 0,
    }
    
    # Get volume info
    volume = conn.execute(
        "SELECT * FROM volumes WHERE id = ?",
        (volume_id,)
    ).fetchone()
    
    if not volume:
        return {'error': 'Volume not found'}
    
    volume = dict(volume)
    
    # Get all offline/missing assets on this volume
    assets = conn.execute("""
        SELECT * FROM models 
        WHERE volume_id = ? AND index_status IN ('offline', 'missing')
    """, (volume_id,)).fetchall()
    
    total = len(assets)
    
    for i, asset in enumerate(assets):
        asset = dict(asset)
        
        if callback:
            callback(i, total, asset.get('filename', ''))
        
        # Check if file exists
        if asset.get('archive_path'):
            file_path = Path(asset['archive_path'])
        else:
            file_path = Path(asset['file_path'])
        
        if file_path.exists():
            # File found
            conn.execute("""
                UPDATE models SET 
                    index_status = 'indexed',
                    missing_since = NULL,
                    last_seen_at = ?,
                    last_verified_at = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                asset['id']
            ))
            
            if asset['index_status'] in ('offline', 'missing'):
                stats['found'] += 1
            else:
                stats['verified'] += 1
        else:
            # Still missing
            handle_missing_asset(conn, asset, volume)
            stats['still_missing'] += 1
    
    conn.commit()
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE ASSET OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def reindex_single_asset(
    conn: sqlite3.Connection,
    model_id: int,
    force: bool = False
) -> dict:
    """
    Re-index a single asset by ID.
    
    Returns: Status dict with result
    """
    # Get model
    model = conn.execute(
        "SELECT * FROM models WHERE id = ?",
        (model_id,)
    ).fetchone()
    
    if not model:
        return {'status': 'error', 'message': 'Model not found'}
    
    model = dict(model)
    
    # Get volume
    volume = conn.execute(
        "SELECT * FROM volumes WHERE id = ?",
        (model.get('volume_id'),)
    ).fetchone()
    
    if not volume:
        return {'status': 'error', 'message': 'Volume not found'}
    
    volume = dict(volume)
    
    # Determine file location
    if model.get('archive_path'):
        file_path = Path(model['archive_path'])
        is_archive_member = True
    else:
        file_path = Path(model['file_path'])
        is_archive_member = False
    
    # Check file/archive exists
    if not file_path.exists():
        status = handle_missing_asset(conn, model, volume)
        conn.commit()
        return {'status': status, 'message': 'File not found'}
    
    # Perform scan
    if is_archive_member:
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                result = scan_archive_member(
                    conn, file_path, model['archive_member'],
                    int(file_path.stat().st_mtime),
                    volume, zf, force
                )
        except zipfile.BadZipFile as e:
            return {'status': 'error', 'message': str(e)}
    else:
        result = scan_file(conn, file_path, volume, force)
    
    # Apply result
    if result.action in (ScanAction.UPDATE, ScanAction.NEW, ScanAction.MOVED):
        # Update model with new data
        update_fields = []
        update_values = []
        
        for key, value in result.model.items():
            if key != 'id':
                update_fields.append(f"{key} = ?")
                update_values.append(value)
        
        update_values.append(model_id)
        
        conn.execute(f"""
            UPDATE models SET {', '.join(update_fields)}
            WHERE id = ?
        """, update_values)
        conn.commit()
        
        return {
            'status': 'indexed',
            'action': result.action.value,
            'reason': result.reason
        }
    
    elif result.action == ScanAction.SKIP:
        # Update last_seen even if skipped
        conn.execute("""
            UPDATE models SET last_seen_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), model_id))
        conn.commit()
        return {'status': 'skipped', 'reason': result.reason}
    
    else:
        return {'status': 'error', 'message': result.reason}
