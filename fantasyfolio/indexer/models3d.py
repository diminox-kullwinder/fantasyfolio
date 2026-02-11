"""
3D Models Indexer module.

Scans directories for 3D model files (STL, 3MF, OBJ, GLB, glTF) including
inside ZIP archives. Commonly used for Patreon miniature packs.
"""

import os
import re
import hashlib
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fantasyfolio.config import get_config
from fantasyfolio.core.database import get_connection, insert_model

logger = logging.getLogger(__name__)

# Supported 3D file extensions
MODEL_EXTENSIONS = {'.stl', '.3mf', '.obj', '.glb', '.gltf'}

# Preview image extensions
PREVIEW_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# Skip patterns
SKIP_PATTERNS = [r'__MACOSX', r'\.DS_Store', r'Thumbs\.db']


class ModelsIndexer:
    """3D model file indexer."""
    
    def __init__(self, root_path: Optional[str] = None):
        self.config = get_config()
        self.root_path = Path(root_path) if root_path else Path(self.config.MODELS_3D_ROOT)
        self.stats = {
            'archives_scanned': 0,
            'standalone_files': 0,
            'models_found': 0,
            'models_indexed': 0,
            'errors': 0
        }
    
    def run(self):
        """Run the 3D models indexer."""
        if not self.root_path.exists():
            logger.error(f"Root path does not exist: {self.root_path}")
            return self.stats
        
        logger.info(f"Starting 3D scan of: {self.root_path}")
        
        models = []
        
        # Walk directory
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            rel_dir = os.path.relpath(root, self.root_path)
            if rel_dir != '.':
                logger.debug(f"Scanning: {rel_dir}")
            
            for filename in files:
                file_path = Path(root) / filename
                
                if self._should_skip(str(file_path)):
                    continue
                
                ext = file_path.suffix.lower()
                
                # Process ZIP archives
                if ext == '.zip':
                    try:
                        zip_models = self._scan_zip(file_path)
                        models.extend(zip_models)
                        self.stats['archives_scanned'] += 1
                        logger.debug(f"Archive {filename}: {len(zip_models)} models")
                    except Exception as e:
                        logger.error(f"Error scanning {file_path}: {e}")
                        self.stats['errors'] += 1
                
                # Process standalone model files
                elif ext in MODEL_EXTENSIONS:
                    try:
                        model = self._process_standalone(file_path)
                        if model:
                            models.append(model)
                            self.stats['standalone_files'] += 1
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        self.stats['errors'] += 1
        
        self.stats['models_found'] = len(models)
        
        # Insert into database
        if models:
            logger.info(f"Saving {len(models)} models to database...")
            self._insert_models(models)
        
        logger.info(f"Scan complete: {self.stats}")
        return self.stats
    
    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped."""
        for pattern in SKIP_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False
    
    def _scan_zip(self, zip_path: Path) -> List[Dict[str, Any]]:
        """Scan a ZIP archive for 3D models."""
        models = []
        
        try:
            folder_path = str(zip_path.parent.relative_to(self.root_path))
        except ValueError:
            folder_path = str(zip_path.parent)
        
        collection = self._extract_collection_name(zip_path)
        creator = self._extract_creator(zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Find preview images
            previews = {}
            for name in zf.namelist():
                if self._should_skip(name):
                    continue
                ext = Path(name).suffix.lower()
                if ext in PREVIEW_EXTENSIONS:
                    # Map preview to potential model names
                    base = Path(name).stem.lower()
                    previews[base] = name
            
            # Find models
            for name in zf.namelist():
                if self._should_skip(name):
                    continue
                
                ext = Path(name).suffix.lower()
                if ext not in MODEL_EXTENSIONS:
                    continue
                
                info = zf.getinfo(name)
                filename = Path(name).name
                
                # Try to find preview
                preview = None
                base = Path(name).stem.lower()
                if base in previews:
                    preview = previews[base]
                
                # Handle bad ZIP dates (some have month=0)
                try:
                    dt = datetime(*info.date_time)
                    iso_date = dt.isoformat()
                except (ValueError, TypeError):
                    # Fall back to current time if ZIP date is corrupted
                    iso_date = datetime.now().isoformat()
                
                model = {
                    'file_path': f"{zip_path}:{name}",
                    'filename': filename,
                    'title': self._clean_title(Path(name).stem),
                    'format': ext[1:],  # Remove dot
                    'file_size': info.file_size,
                    'file_hash': None,
                    'archive_path': str(zip_path),
                    'archive_member': name,
                    'folder_path': folder_path,
                    'collection': collection,
                    'creator': creator,
                    'vertex_count': None,
                    'face_count': None,
                    'has_supports': 1 if 'support' in name.lower() else 0,
                    'preview_image': preview,
                    'has_thumbnail': 1 if preview else 0,
                    'created_at': iso_date,
                    'modified_at': iso_date
                }
                
                models.append(model)
        
        return models
    
    def _process_standalone(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Process a standalone 3D model file."""
        stat = file_path.stat()
        
        try:
            folder_path = str(file_path.parent.relative_to(self.root_path))
        except ValueError:
            folder_path = str(file_path.parent)
        
        return {
            'file_path': str(file_path),
            'filename': file_path.name,
            'title': self._clean_title(file_path.stem),
            'format': file_path.suffix[1:].lower(),
            'file_size': stat.st_size,
            'file_hash': self._get_file_hash(file_path),
            'archive_path': None,
            'archive_member': None,
            'folder_path': folder_path,
            'collection': self._extract_collection_name(file_path),
            'creator': self._extract_creator(file_path),
            'vertex_count': None,
            'face_count': None,
            'has_supports': 1 if 'support' in file_path.name.lower() else 0,
            'preview_image': None,
            'has_thumbnail': 0,
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    
    def _extract_collection_name(self, path: Path) -> Optional[str]:
        """Extract collection name from path."""
        parts = path.parts
        for part in reversed(parts[:-1]):
            if part.lower() not in {'3d', 'stl', 'models', 'files', 'supported', 'unsupported'}:
                if len(part) > 3:
                    return part
        return path.stem
    
    def _extract_creator(self, path: Path) -> Optional[str]:
        """Try to extract creator/author from path."""
        parts = path.parts
        # Often the creator is a parent folder
        if len(parts) > 3:
            return parts[-3] if parts[-3] not in {'3D', 'Models', 'STL'} else None
        return None
    
    def _clean_title(self, name: str) -> str:
        """Clean up model title from filename."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^[\d_\-]+', '', name)  # Leading numbers
        name = re.sub(r'_+', ' ', name)  # Underscores to spaces
        name = re.sub(r'\s+', ' ', name)  # Multiple spaces
        return name.strip() or name
    
    def _get_file_hash(self, path: Path) -> str:
        """Get MD5 hash of file."""
        with open(path, 'rb') as f:
            return hashlib.md5(f.read(8192)).hexdigest()
    
    def _insert_models(self, models: List[Dict[str, Any]]):
        """Insert models into database, preserving has_thumbnail if thumbnail exists."""
        from fantasyfolio.config import get_config
        config = get_config()
        thumb_dir = config.THUMBNAIL_DIR / "3d"
        
        with get_connection() as conn:
            for model in models:
                try:
                    # Check if model exists and get its ID
                    existing = conn.execute(
                        "SELECT id, has_thumbnail FROM models WHERE file_path = ?",
                        (model['file_path'],)
                    ).fetchone()
                    
                    if existing:
                        # Update existing - check if thumbnail file exists
                        thumb_file = thumb_dir / f"{existing['id']}.png"
                        has_thumb = 1 if thumb_file.exists() else existing['has_thumbnail']
                        
                        conn.execute("""
                            UPDATE models SET
                                filename=:filename, title=:title, format=:format, 
                                file_size=:file_size, file_hash=:file_hash,
                                archive_path=:archive_path, archive_member=:archive_member,
                                folder_path=:folder_path, collection=:collection, creator=:creator,
                                vertex_count=:vertex_count, face_count=:face_count,
                                has_supports=:has_supports, preview_image=:preview_image,
                                has_thumbnail=?, modified_at=:modified_at
                            WHERE file_path=:file_path
                        """, {**model, 'has_thumbnail': has_thumb})
                    else:
                        # Insert new
                        conn.execute("""
                            INSERT INTO models (
                                file_path, filename, title, format, file_size, file_hash,
                                archive_path, archive_member, folder_path, collection, creator,
                                vertex_count, face_count, has_supports, preview_image,
                                has_thumbnail, created_at, modified_at
                            ) VALUES (
                                :file_path, :filename, :title, :format, :file_size, :file_hash,
                                :archive_path, :archive_member, :folder_path, :collection, :creator,
                                :vertex_count, :face_count, :has_supports, :preview_image,
                                :has_thumbnail, :created_at, :modified_at
                            )
                        """, model)
                    self.stats['models_indexed'] += 1
                except Exception as e:
                    logger.error(f"Failed to insert model: {e}")
                    self.stats['errors'] += 1
            conn.commit()


def main():
    """CLI entry point."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    path = sys.argv[1] if len(sys.argv) > 1 else None
    indexer = ModelsIndexer(path)
    stats = indexer.run()
    print(f"Indexing complete: {stats}")


if __name__ == '__main__':
    main()
