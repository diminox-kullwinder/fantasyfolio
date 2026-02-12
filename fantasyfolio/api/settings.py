"""
Settings API Blueprint.

Handles application settings, configuration, backups, and uploads.
"""

import os
import logging
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

from fantasyfolio.core.database import get_setting, set_setting, get_all_settings, get_connection

logger = logging.getLogger(__name__)
settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET'])
def api_get_settings():
    """Get all settings."""
    return jsonify(get_all_settings())


@settings_bp.route('/settings', methods=['POST'])
def api_set_settings():
    """Set multiple settings at once."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    with get_connection() as conn:
        for key, value in data.items():
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, str(value))
            )
        conn.commit()
    
    return jsonify({'success': True})


@settings_bp.route('/settings/<key>', methods=['GET'])
def api_get_setting(key: str):
    """Get a single setting."""
    value = get_setting(key)
    if value is None:
        return jsonify({'error': 'Setting not found'}), 404
    return jsonify({key: value})


@settings_bp.route('/settings/<key>', methods=['PUT'])
def api_set_setting(key: str):
    """Set a single setting."""
    data = request.get_json(silent=True)
    if not data or 'value' not in data:
        return jsonify({'error': 'Value required'}), 400
    
    set_setting(key, str(data['value']))
    return jsonify({'success': True})


@settings_bp.route('/browse-directory')
def api_browse_directory():
    """
    Browse server directories for path selection.
    Used by the settings UI for selecting content roots.
    """
    import sys
    from pathlib import Path
    
    requested_path = request.args.get('path', '')
    
    if not requested_path:
        # Choose sensible default based on platform
        if sys.platform == 'darwin':
            path = '/Volumes'
        elif sys.platform == 'linux':
            # Linux/Container: prefer /content (our mount convention), else /mnt, else /
            if Path('/content').exists():
                path = '/content'
            elif Path('/mnt').exists() and any(Path('/mnt').iterdir()):
                path = '/mnt'
            else:
                path = '/'
        else:
            path = '/'
    else:
        path = requested_path
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Not a directory'}), 400
    
    try:
        entries = []
        for entry in os.scandir(path):
            if entry.is_dir() and not entry.name.startswith('.'):
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'type': 'directory'
                })
        
        entries.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'path': path,
            'parent': os.path.dirname(path) if path != '/' else None,
            'entries': entries
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        logger.error(f"Directory browse error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== BACKUP ENDPOINTS ====================

@settings_bp.route('/backup', methods=['POST'])
def api_create_backup():
    """Create a backup of the database."""
    from fantasyfolio.config import get_config
    
    config = get_config()
    db_path = config.DATABASE_FILE
    backup_dir = config.DATA_DIR / 'backups'
    backup_dir.mkdir(exist_ok=True)
    
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 404
    
    # Create timestamped backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"dam_backup_{timestamp}.db"
    backup_path = backup_dir / backup_name
    
    try:
        shutil.copy2(db_path, backup_path)
        
        # Get backup size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        
        # Clean up old backups (keep last 5)
        backups = sorted(backup_dir.glob("dam_backup_*.db"), reverse=True)
        for old_backup in backups[5:]:
            old_backup.unlink()
        
        return jsonify({
            'success': True,
            'backup_file': backup_name,
            'size_mb': round(size_mb, 2),
            'message': f'Backup created: {backup_name}'
        })
    except Exception as e:
        logger.error(f"Backup creation error: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/backups', methods=['GET'])
def api_list_backups():
    """List available database backups."""
    from fantasyfolio.config import get_config
    
    config = get_config()
    backup_dir = config.DATA_DIR / 'backups'
    
    if not backup_dir.exists():
        return jsonify({'backups': []})
    
    backups = []
    for f in sorted(backup_dir.glob("dam_backup_*.db"), reverse=True):
        backups.append({
            'filename': f.name,
            'size_mb': round(f.stat().st_size / (1024 * 1024), 2),
            'created': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })
    
    return jsonify({'backups': backups})


@settings_bp.route('/backup/restore', methods=['POST'])
def api_restore_backup():
    """Restore database from a backup."""
    from fantasyfolio.config import get_config
    
    config = get_config()
    data = request.get_json(silent=True) or {}
    backup_name = data.get('filename')
    
    if not backup_name:
        return jsonify({'error': 'Backup filename required'}), 400
    
    backup_dir = config.DATA_DIR / 'backups'
    backup_path = backup_dir / backup_name
    db_path = config.DATABASE_FILE
    
    if not backup_path.exists():
        return jsonify({'error': 'Backup not found'}), 404
    
    # Safety check - ensure it's a valid backup file
    if not backup_name.startswith('dam_backup_') or not backup_name.endswith('.db'):
        return jsonify({'error': 'Invalid backup filename'}), 400
    
    try:
        # Create a backup of current db before restoring
        if db_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pre_restore = backup_dir / f"dam_pre_restore_{timestamp}.db"
            shutil.copy2(db_path, pre_restore)
        
        # Restore the backup
        shutil.copy2(backup_path, db_path)
        
        return jsonify({
            'success': True,
            'message': f'Database restored from {backup_name}. Refresh the page.'
        })
    except Exception as e:
        logger.error(f"Backup restore error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== UPLOAD ENDPOINTS ====================

@settings_bp.route('/upload/browse', methods=['GET'])
def api_upload_browse():
    """Browse directories for upload destination."""
    content_type = request.args.get('type', 'pdf')  # 'pdf' or '3d'
    path = request.args.get('path')
    
    # Get the root path for this content type
    settings = get_all_settings()
    if content_type == '3d':
        root = settings.get('3d_root') or '/content/3d-models'
    else:
        root = settings.get('pdf_root') or '/content/pdfs'
    
    # Fallback if path doesn't exist - try common alternatives
    if not os.path.exists(root):
        if content_type == '3d':
            alternatives = ['/content/3d-models', '/content/models', '/app/uploads/3d']
        else:
            alternatives = ['/content/pdfs', '/app/uploads/pdf']
        
        for alt in alternatives:
            if os.path.exists(alt):
                root = alt
                break
    
    # If no path specified, start at the root
    if not path:
        path = root
    
    # Security: ensure path is within the root
    try:
        resolved_path = os.path.realpath(path)
        resolved_root = os.path.realpath(root)
        if not resolved_path.startswith(resolved_root) and resolved_path != resolved_root:
            if path != root:
                return jsonify({'error': 'Path outside content root'}), 403
    except Exception:
        pass
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Not a directory'}), 400
    
    try:
        entries = []
        for entry in os.scandir(path):
            if entry.is_dir() and not entry.name.startswith('.'):
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'type': 'directory'
                })
        
        entries.sort(key=lambda x: x['name'].lower())
        
        # Get parent path (but don't go above root)
        parent_path = str(Path(path).parent)
        if not parent_path.startswith(root) and parent_path != root:
            parent_path = None
        elif path == root:
            parent_path = None
        
        return jsonify({
            'current': path,
            'root': root,
            'parent': parent_path,
            'entries': entries,
            'can_upload': True
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        logger.error(f"Upload browse error: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/upload/mkdir', methods=['POST'])
def api_upload_mkdir():
    """Create a new directory for uploads."""
    data = request.get_json(silent=True) or {}
    parent_path = data.get('parent')
    folder_name = data.get('name')
    content_type = data.get('type', 'pdf')
    
    if not parent_path or not folder_name:
        return jsonify({'error': 'Parent path and folder name required'}), 400
    
    # Sanitize folder name
    folder_name = folder_name.strip().replace('/', '_').replace('\\', '_')
    if not folder_name or folder_name.startswith('.'):
        return jsonify({'error': 'Invalid folder name'}), 400
    
    # Get root for security check (same logic as browse endpoint)
    settings = get_all_settings()
    if content_type == '3d':
        root = settings.get('3d_root') or '/content/3d-models'
    else:
        root = settings.get('pdf_root') or '/content/pdfs'
    
    # Fallback if path doesn't exist - try common alternatives
    if not os.path.exists(root):
        if content_type == '3d':
            alternatives = ['/content/3d-models', '/content/models', '/app/uploads/3d']
        else:
            alternatives = ['/content/pdfs', '/app/uploads/pdf']
        
        for alt in alternatives:
            if os.path.exists(alt):
                root = alt
                break
    
    # Security: ensure parent is within root
    try:
        resolved_parent = os.path.realpath(parent_path)
        resolved_root = os.path.realpath(root)
        if not resolved_parent.startswith(resolved_root):
            return jsonify({'error': 'Path outside content root'}), 403
    except Exception as e:
        logger.error(f"Path resolution error: {e}, parent={parent_path}, root={root}")
        return jsonify({'error': 'Invalid path'}), 400
    
    new_path = os.path.join(parent_path, folder_name)
    
    if os.path.exists(new_path):
        return jsonify({'error': 'Folder already exists'}), 400
    
    try:
        os.makedirs(new_path, exist_ok=True)
        return jsonify({
            'success': True,
            'path': new_path,
            'message': f'Created folder: {folder_name}'
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        logger.error(f"Mkdir error: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/upload', methods=['POST'])
def api_upload_files():
    """Handle file uploads and index immediately."""
    import zipfile
    from pathlib import Path
    from datetime import datetime
    from fantasyfolio.core.database import insert_asset, insert_model
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    destination = request.form.get('destination')
    content_type = request.form.get('type', 'pdf')
    
    if not destination:
        return jsonify({'error': 'Destination directory required'}), 400
    
    if not os.path.isdir(destination):
        return jsonify({'error': 'Destination directory does not exist'}), 400
    
    # Get root for folder_path calculation (same logic as browse/mkdir)
    settings = get_all_settings()
    if content_type == '3d':
        root = settings.get('3d_root') or '/content/3d-models'
    else:
        root = settings.get('pdf_root') or '/content/pdfs'
    
    # Fallback if path doesn't exist - try common alternatives
    if not os.path.exists(root):
        if content_type == '3d':
            alternatives = ['/content/3d-models', '/content/models', '/app/uploads/3d']
        else:
            alternatives = ['/content/pdfs', '/app/uploads/pdf']
        
        for alt in alternatives:
            if os.path.exists(alt):
                root = alt
                break
    
    # Security: ensure destination is within root
    try:
        resolved_dest = os.path.realpath(destination)
        resolved_root = os.path.realpath(root)
        if not resolved_dest.startswith(resolved_root):
            return jsonify({'error': 'Destination outside content root'}), 403
    except Exception as e:
        logger.error(f"Upload path validation error: {e}, dest={destination}, root={root}")
        return jsonify({'error': 'Invalid destination'}), 400
    
    # Validate file types
    if content_type == '3d':
        allowed_extensions = {'.stl', '.obj', '.3mf', '.zip', '.rar', '.7z'}
    else:
        allowed_extensions = {'.pdf'}
    
    uploaded = []
    errors = []
    
    for file in files:
        if not file.filename:
            continue
        
        # Check extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            errors.append(f'{file.filename}: Invalid file type')
            continue
        
        # Sanitize filename
        safe_filename = file.filename.replace('/', '_').replace('\\', '_')
        file_path = os.path.join(destination, safe_filename)
        
        # Handle duplicates
        if os.path.exists(file_path):
            base, ext_part = os.path.splitext(safe_filename)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(destination, f'{base}_{counter}{ext_part}')
                counter += 1
        
        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            
            # Calculate folder_path relative to root
            rel_path = os.path.relpath(os.path.dirname(file_path), root)
            if rel_path == '.':
                folder_path = ''
            else:
                folder_path = rel_path
            
            # Compute file hash (skip for large files on slow storage - compute during indexing instead)
            # For files > 1MB, use a placeholder hash to speed up upload response
            if file_size > 1024 * 1024:  # 1MB threshold
                file_hash = f"pending_{os.path.basename(file_path)}_{file_size}"
                logger.info(f"Skipping hash for large file {safe_filename} ({file_size} bytes), will compute during indexing")
            else:
                hasher = hashlib.md5()
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        hasher.update(chunk)
                file_hash = hasher.hexdigest()
            
            # Special handling for ZIP files in 3D context - extract and index contents
            if content_type == '3d' and ext == '.zip':
                try:
                    zip_path = Path(file_path)
                    models_found = _scan_and_index_zip(zip_path, root, file_path)
                    
                    if models_found > 0:
                        uploaded.append({
                            'filename': os.path.basename(file_path),
                            'path': file_path,
                            'size': file_size,
                            'folder_path': folder_path,
                            'models_extracted': models_found
                        })
                        logger.info(f"ZIP upload: extracted {models_found} models from {safe_filename}")
                        continue  # Skip inserting the ZIP itself as a model
                    else:
                        logger.warning(f"ZIP upload: no models found in {safe_filename}")
                        # Fall through to insert ZIP as placeholder if desired
                except Exception as e:
                    logger.error(f"ZIP extraction error for {file_path}: {e}")
                    errors.append(f'{file.filename}: Error extracting ZIP - {str(e)}')
                    continue
            
            # Insert into database immediately
            if content_type == 'pdf':
                # Try to extract basic PDF metadata
                page_count = None
                title = None
                author = None
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(file_path)
                    page_count = doc.page_count
                    meta = doc.metadata
                    title = meta.get('title') or None
                    author = meta.get('author') or None
                    doc.close()
                except Exception:
                    pass
                
                # Insert PDF asset (provide all required fields)
                asset = {
                    'file_path': file_path,
                    'filename': os.path.basename(file_path),
                    'title': title or os.path.splitext(os.path.basename(file_path))[0],
                    'author': author,
                    'publisher': folder_path.split('/')[0] if folder_path else None,
                    'page_count': page_count,
                    'file_size': file_size,
                    'file_hash': file_hash,
                    'folder_path': folder_path,
                    'game_system': None,
                    'category': None,
                    'tags': None,
                    'thumbnail_path': None,
                    'has_thumbnail': 0,
                    'pdf_creator': None,
                    'pdf_producer': None,
                    'pdf_creation_date': None,
                    'pdf_mod_date': None,
                    'created_at': datetime.now().isoformat(),
                    'modified_at': datetime.now().isoformat()
                }
                insert_asset(asset)
                    
            else:
                # Insert 3D model (provide all required fields)
                model = {
                    'file_path': file_path,
                    'filename': os.path.basename(file_path),
                    'title': os.path.splitext(os.path.basename(file_path))[0].replace('_', ' '),
                    'format': ext[1:] if ext else 'unknown',
                    'file_size': file_size,
                    'file_hash': file_hash,
                    'folder_path': folder_path,
                    'collection': folder_path.split('/')[0] if folder_path else 'uploads',
                    'creator': 'uploaded',
                    'archive_path': None,  # Only set for files extracted from archives
                    'archive_member': None,  # Only set for files extracted from archives
                    'vertex_count': None,
                    'face_count': None,
                    'has_supports': 0,
                    'preview_image': None,
                    'has_thumbnail': 0,
                    'created_at': datetime.now().isoformat(),
                    'modified_at': datetime.now().isoformat()
                }
                insert_model(model)
            
            uploaded.append({
                'filename': os.path.basename(file_path),
                'path': file_path,
                'size': file_size,
                'folder_path': folder_path
            })
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f'{file.filename}: {str(e)}')
    
    return jsonify({
        'success': len(uploaded) > 0,
        'uploaded': uploaded,
        'errors': errors,
        'message': f'Uploaded {len(uploaded)} file(s)' + (f', {len(errors)} error(s)' if errors else '')
    })


# ==================== ZIP EXTRACTION HELPER ====================

def _scan_and_index_zip(zip_path: Path, root: str, archive_file_path: str) -> int:
    """
    Scan a ZIP archive for 3D model files and insert them into the database.
    Returns the number of models indexed.
    """
    import zipfile
    from fantasyfolio.core.database import insert_model
    
    MODEL_EXTENSIONS = {'.stl', '.3mf', '.obj'}
    PREVIEW_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    SKIP_PATTERNS = [r'__MACOSX', r'\.DS_Store', r'Thumbs\.db', r'^\.']
    
    models_indexed = 0
    
    try:
        # Calculate folder_path for this archive
        try:
            folder_path = str(zip_path.parent.relative_to(root))
            if folder_path == '.':
                folder_path = ''
        except ValueError:
            folder_path = ''
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # First pass: find preview images for mapping
            previews = {}
            for name in zf.namelist():
                # Skip entries matching skip patterns
                skip = False
                for pattern in SKIP_PATTERNS:
                    if pattern.lower() in name.lower():
                        skip = True
                        break
                if skip:
                    continue
                
                ext = os.path.splitext(name)[1].lower()
                if ext in PREVIEW_EXTENSIONS:
                    base = os.path.splitext(os.path.basename(name))[0].lower()
                    previews[base] = name
            
            # Second pass: find and index 3D model files
            for name in zf.namelist():
                # Skip entries matching skip patterns
                skip = False
                for pattern in SKIP_PATTERNS:
                    if pattern.lower() in name.lower():
                        skip = True
                        break
                if skip:
                    continue
                
                ext = os.path.splitext(name)[1].lower()
                if ext not in MODEL_EXTENSIONS:
                    continue
                
                info = zf.getinfo(name)
                filename = os.path.basename(name)
                
                # Try to find a preview image for this model
                preview = None
                base = os.path.splitext(filename)[0].lower()
                if base in previews:
                    preview = previews[base]
                
                # Clean title: remove file extension and replace underscores
                title = os.path.splitext(filename)[0].replace('_', ' ')
                
                # Extract collection name from ZIP filename
                collection = os.path.splitext(zip_path.name)[0]
                
                # Create unique file_path for database
                file_path = f"{archive_file_path}:{name}"
                
                # Build model record
                model = {
                    'file_path': file_path,
                    'filename': filename,
                    'title': title,
                    'format': ext[1:],  # Remove the dot
                    'file_size': info.file_size,
                    'file_hash': None,  # Could compute from ZIP member but skipping for now
                    'archive_path': str(archive_file_path),
                    'archive_member': name,
                    'folder_path': folder_path,
                    'collection': collection,
                    'creator': 'uploaded',
                    'vertex_count': None,
                    'face_count': None,
                    'has_supports': 1 if 'support' in name.lower() else 0,
                    'preview_image': preview,
                    'has_thumbnail': 1 if preview else 0,
                    'created_at': datetime(*info.date_time).isoformat(),
                    'modified_at': datetime(*info.date_time).isoformat()
                }
                
                try:
                    insert_model(model)
                    models_indexed += 1
                    logger.debug(f"Indexed model from ZIP: {filename} (archive: {collection})")
                except Exception as e:
                    logger.error(f"Error indexing model {filename} from ZIP: {e}")
    
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {zip_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error scanning ZIP file {zip_path}: {e}")
        raise
    
    return models_indexed
