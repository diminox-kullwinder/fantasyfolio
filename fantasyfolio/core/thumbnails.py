"""
Thumbnail storage and management for FantasyFolio.

Implements sidecar thumbnail storage strategy from Architecture v1.2:
- Sidecar files next to standalone assets (.{filename}.thumb.png)
- Archive-adjacent dirs for ZIP members (.{archive}.dam/thumbs/)
- Central cache fallback for read-only volumes
"""

import os
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum


class ThumbStorage(Enum):
    SIDECAR = 'sidecar'
    ARCHIVE_SIDECAR = 'archive_sidecar'
    CENTRAL = 'central'


# ═══════════════════════════════════════════════════════════════════════════════
# PATH DETERMINATION
# ═══════════════════════════════════════════════════════════════════════════════

def determine_thumb_location(
    model: dict,
    volume: dict,
    central_dir: Path
) -> Tuple[ThumbStorage, Path]:
    """
    Determine where to store thumbnail for an asset.
    
    Priority:
    1. Sidecar (travels with asset) if writable
    2. Archive sidecar (travels with archive) if writable
    3. Central cache (fallback for read-only)
    
    Returns: (storage_type, absolute_path)
    """
    is_readonly = volume.get('is_readonly', False) if volume else True
    
    if model.get('archive_path'):
        # Archive member
        archive_path = Path(model['archive_path'])
        parent_dir = archive_path.parent
        
        if is_readonly or not _is_writable(parent_dir):
            return _central_path(model, central_dir)
        
        # Archive-adjacent metadata directory
        meta_dir = parent_dir / f".{archive_path.name}.dam" / "thumbs"
        thumb_name = _thumb_name_for_member(
            model.get('archive_member', ''),
            model.get('partial_hash', '') or model.get('id', '')
        )
        return (ThumbStorage.ARCHIVE_SIDECAR, meta_dir / thumb_name)
    
    else:
        # Standalone file
        file_path = Path(model['file_path'])
        parent_dir = file_path.parent
        
        if is_readonly or not _is_writable(parent_dir):
            return _central_path(model, central_dir)
        
        # Sidecar next to file
        thumb_name = f".{file_path.name}.thumb.png"
        return (ThumbStorage.SIDECAR, parent_dir / thumb_name)


def _central_path(model: dict, central_dir: Path) -> Tuple[ThumbStorage, Path]:
    """Fallback to central thumbnail cache."""
    # Use partial_hash or id for filename (content-addressable)
    hash_id = model.get('partial_hash') or str(model.get('id', 'unknown'))
    
    # Determine asset type subfolder
    fmt = (model.get('format') or '').lower()
    if fmt in ('stl', 'obj', '3mf', 'glb', 'gltf'):
        asset_type = '3d'
    elif fmt == 'pdf':
        asset_type = 'pdf'
    else:
        asset_type = 'other'
    
    return (ThumbStorage.CENTRAL, central_dir / asset_type / f"{hash_id}.png")


def _thumb_name_for_member(member_path: str, identifier: str) -> str:
    """Generate readable thumbnail filename for archive member."""
    import re
    
    filename = Path(member_path).stem
    safe_name = re.sub(r'[^\w\-]', '_', filename)[:40]
    short_id = str(identifier)[:8] if identifier else 'noid'
    
    return f"{safe_name}_{short_id}.thumb.png"


def _is_writable(path: Path) -> bool:
    """Check if directory is writable."""
    try:
        if not path.exists():
            return False
        test_file = path / '.dam_write_test'
        test_file.touch()
        test_file.unlink()
        return True
    except (PermissionError, OSError):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL RESOLUTION (READING)
# ═══════════════════════════════════════════════════════════════════════════════

def find_thumbnail(model: dict, volume: dict, central_dir: Path) -> Optional[Path]:
    """
    Find existing thumbnail, checking all possible locations.
    
    Check order:
    1. Recorded path (if we already know where it is)
    2. Sidecar location (preferred)
    3. Central cache (fallback)
    
    Returns: Absolute path if found, None otherwise
    """
    # 1. Check recorded path first
    if model.get('thumb_path') and model.get('thumb_storage'):
        recorded = _resolve_thumb_path(model, volume, central_dir)
        if recorded and recorded.exists():
            return recorded
    
    # 2. Check sidecar location
    if model.get('archive_path'):
        storage, sidecar = determine_thumb_location(model, volume, central_dir)
        if storage == ThumbStorage.ARCHIVE_SIDECAR and sidecar.exists():
            return sidecar
    elif model.get('file_path'):
        storage, sidecar = determine_thumb_location(model, volume, central_dir)
        if storage == ThumbStorage.SIDECAR and sidecar.exists():
            return sidecar
    
    # 3. Check central cache
    _, central = _central_path(model, central_dir)
    if central.exists():
        return central
    
    # 4. Check old-style central cache (by ID)
    old_central = central_dir / '3d' / f"{model.get('id', 0)}.png"
    if old_central.exists():
        return old_central
    
    return None


def _resolve_thumb_path(model: dict, volume: dict, central_dir: Path) -> Optional[Path]:
    """Resolve recorded thumb_path to absolute path."""
    thumb_path = model.get('thumb_path')
    if not thumb_path:
        return None
    
    storage = model.get('thumb_storage')
    
    if storage == ThumbStorage.CENTRAL.value:
        return central_dir / thumb_path
    elif storage in (ThumbStorage.SIDECAR.value, ThumbStorage.ARCHIVE_SIDECAR.value):
        # Relative to volume mount
        if volume and volume.get('mount_path'):
            return Path(volume['mount_path']) / thumb_path
        return Path(thumb_path)
    else:
        return Path(thumb_path)


# ═══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL RENDERING
# ═══════════════════════════════════════════════════════════════════════════════

def render_thumbnail(
    model: dict,
    volume: dict,
    central_dir: Path,
    size: int = 512,
    force: bool = False
) -> Optional[dict]:
    """
    Render thumbnail for a model.
    
    Returns: Dict with storage info, or None on failure
        {
            'thumb_storage': 'sidecar' | 'archive_sidecar' | 'central',
            'thumb_path': str,
            'thumb_rendered_at': str,
            'thumb_source_mtime': int
        }
    """
    # Check if already rendered (unless forced)
    if not force:
        existing = find_thumbnail(model, volume, central_dir)
        if existing:
            return None  # Already exists
    
    # Determine output location
    storage, output_path = determine_thumb_location(model, volume, central_dir)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get source data
    source_mtime = None
    
    if model.get('archive_path') and model.get('archive_member'):
        # Archive member - extract to temp file
        archive_path = Path(model['archive_path'])
        if not archive_path.exists():
            return None
        
        source_mtime = int(archive_path.stat().st_mtime)
        
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                data = zf.read(model['archive_member'])
            
            # Write to temp file for rendering
            with tempfile.NamedTemporaryFile(
                suffix=f".{model.get('format', 'stl')}",
                delete=False
            ) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            
            success = _render_3d_thumbnail(tmp_path, str(output_path), size)
            os.unlink(tmp_path)
            
        except Exception:
            return None
    
    else:
        # Standalone file
        file_path = Path(model['file_path'])
        if not file_path.exists():
            return None
        
        source_mtime = int(file_path.stat().st_mtime)
        success = _render_3d_thumbnail(str(file_path), str(output_path), size)
    
    if success and output_path.exists():
        # Compute relative path for storage
        if storage == ThumbStorage.CENTRAL:
            rel_path = str(output_path.relative_to(central_dir))
        elif volume and volume.get('mount_path'):
            try:
                rel_path = str(output_path.relative_to(volume['mount_path']))
            except ValueError:
                rel_path = str(output_path)
        else:
            rel_path = str(output_path)
        
        return {
            'thumb_storage': storage.value,
            'thumb_path': rel_path,
            'thumb_rendered_at': datetime.now().isoformat(),
            'thumb_source_mtime': source_mtime
        }
    
    return None


def _render_with_f3d(input_path: str, output_path: str, size: int = 1024) -> bool:
    """Render using f3d CLI - works in containers with Xvfb.
    
    f3d supports: STL, OBJ, 3MF, GLTF, PLY, FBX, and many more via assimp.
    
    Settings:
    - --up +Z: STL/OBJ files typically use Z-up
    - Resolution: square thumbnail at specified size
    - Uses xvfb-run for headless rendering in containers
    """
    import shutil
    import os
    
    if not shutil.which('f3d'):
        return False
    
    base_cmd = [
        'f3d',
        '--output', output_path,
        '--resolution', f'{size},{size}',
        '--up', '+Z',
        '--camera-direction=0,1,-0.3',  # Front view, slight downward angle (good for miniatures)
        input_path
    ]
    
    # Use xvfb-run if available (for headless rendering in containers)
    use_xvfb = shutil.which('xvfb-run') is not None
    
    if use_xvfb:
        cmd = ['xvfb-run', '-a'] + base_cmd
    else:
        cmd = base_cmd
    
    try:
        # Set DISPLAY if not set (for non-xvfb-run cases)
        env = os.environ.copy()
        if 'DISPLAY' not in env:
            env['DISPLAY'] = ':0'
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            env=env
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _render_with_stl_thumb(input_path: str, output_path: str, size: int = 1024) -> bool:
    """Fallback: render using stl-thumb CLI (may not work in containers).
    
    Enhanced quality settings:
    - 1024px size for crisp thumbnails
    - Silver/grey material colors for realistic 3D print look
    - Dark grey background for better contrast
    """
    import shutil
    
    if not shutil.which('stl-thumb'):
        return False
    
    # Use xvfb-run if available (for headless OpenGL rendering in containers)
    use_xvfb = shutil.which('xvfb-run') is not None
    
    # Material colors (ambient, diffuse, specular) - silver/grey for 3D print look
    material_ambient = 'c0c0c0'
    material_diffuse = 'd8d8d8'
    material_specular = 'ffffff'
    
    # Background: dark grey, matches UI dark theme
    background = '2a2a2aff'
    
    base_cmd = [
        'stl-thumb', input_path, output_path,
        '-s', str(size),
        '-m', material_ambient, material_diffuse, material_specular,
        '-b', background
    ]
    
    if use_xvfb:
        cmd = ['xvfb-run', '-a'] + base_cmd
    else:
        cmd = base_cmd
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _render_3d_thumbnail(input_path: str, output_path: str, size: int = 1024) -> bool:
    """Render 3D model thumbnail using best available renderer.
    
    Tries f3d first (container-friendly), falls back to stl-thumb.
    """
    # Try f3d first - works in containers
    if _render_with_f3d(input_path, output_path, size):
        return True
    
    # Fallback to stl-thumb (works on Mac/desktop)
    return _render_with_stl_thumb(input_path, output_path, size)


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def migrate_thumbnails_to_sidecars(
    conn: sqlite3.Connection,
    central_dir: Path,
    limit: int = None,
    callback = None
) -> dict:
    """
    Migrate existing central thumbnails to sidecar locations.
    
    Returns: Stats dict
    """
    stats = {
        'migrated': 0,
        'skipped': 0,
        'failed': 0,
        'already_sidecar': 0
    }
    
    # Get models with central thumbnails
    query = """
        SELECT m.*, v.mount_path, v.is_readonly
        FROM models m
        LEFT JOIN volumes v ON m.volume_id = v.id
        WHERE m.thumb_storage = 'central' OR m.thumb_storage IS NULL
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = conn.execute(query).fetchall()
    total = len(rows)
    
    for i, row in enumerate(rows):
        model = dict(row)
        
        if callback:
            callback(i, total, model.get('filename', ''))
        
        # Build volume dict
        volume = {
            'mount_path': model.get('mount_path'),
            'is_readonly': model.get('is_readonly', 1)
        }
        
        # Check if read-only (can't migrate)
        if volume.get('is_readonly'):
            stats['skipped'] += 1
            continue
        
        # Find existing central thumbnail
        old_thumb = find_thumbnail(model, volume, central_dir)
        if not old_thumb or not old_thumb.exists():
            stats['skipped'] += 1
            continue
        
        # Determine new sidecar location
        storage, new_path = determine_thumb_location(model, volume, central_dir)
        
        if storage == ThumbStorage.CENTRAL:
            # Still central (read-only volume)
            stats['skipped'] += 1
            continue
        
        if new_path.exists():
            stats['already_sidecar'] += 1
            continue
        
        try:
            # Create directory and copy
            new_path.parent.mkdir(parents=True, exist_ok=True)
            
            import shutil
            shutil.copy2(old_thumb, new_path)
            
            # Update database
            rel_path = str(new_path.relative_to(Path(volume['mount_path'])))
            conn.execute("""
                UPDATE models SET
                    thumb_storage = ?,
                    thumb_path = ?
                WHERE id = ?
            """, (storage.value, rel_path, model['id']))
            
            stats['migrated'] += 1
            
            # Commit every 100
            if stats['migrated'] % 100 == 0:
                conn.commit()
        
        except Exception:
            stats['failed'] += 1
    
    conn.commit()
    return stats


def render_pending_thumbnails(
    conn: sqlite3.Connection,
    central_dir: Path,
    limit: int = 100,
    callback = None
) -> dict:
    """
    Render thumbnails for models that don't have them.
    """
    stats = {
        'rendered': 0,
        'skipped': 0,
        'failed': 0
    }
    
    # Get models without thumbnails
    rows = conn.execute("""
        SELECT m.*, v.mount_path, v.is_readonly
        FROM models m
        LEFT JOIN volumes v ON m.volume_id = v.id
        WHERE m.thumb_storage IS NULL
        AND m.format IN ('stl', 'obj', '3mf', 'glb', 'gltf')
        LIMIT ?
    """, (limit,)).fetchall()
    
    total = len(rows)
    
    for i, row in enumerate(rows):
        model = dict(row)
        
        if callback:
            callback(i, total, model.get('filename', ''))
        
        volume = {
            'id': model.get('volume_id'),
            'mount_path': model.get('mount_path'),
            'is_readonly': model.get('is_readonly', 1)
        }
        
        result = render_thumbnail(model, volume, central_dir, force=True)
        
        if result:
            conn.execute("""
                UPDATE models SET
                    thumb_storage = ?,
                    thumb_path = ?,
                    thumb_rendered_at = ?,
                    thumb_source_mtime = ?
                WHERE id = ?
            """, (
                result['thumb_storage'],
                result['thumb_path'],
                result['thumb_rendered_at'],
                result['thumb_source_mtime'],
                model['id']
            ))
            stats['rendered'] += 1
        else:
            stats['failed'] += 1
        
        # Commit every 10
        if (i + 1) % 10 == 0:
            conn.commit()
    
    conn.commit()
    return stats
