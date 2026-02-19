"""
PDF Indexer module.

Scans directories for PDF files and indexes them with metadata,
text extraction, bookmarks, and thumbnail generation.
"""

import os
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fantasyfolio.config import get_config
from fantasyfolio.core.database import get_connection, insert_asset
from fantasyfolio.services.asset_locations import get_location_for_path

logger = logging.getLogger(__name__)


class PDFIndexer:
    """PDF file indexer."""
    
    def __init__(self, root_path: Optional[str] = None, scan_path: Optional[str] = None):
        self.config = get_config()
        self.root_path = Path(root_path) if root_path else Path(self.config.PDF_ROOT)
        self.scan_path = Path(scan_path) if scan_path else self.root_path
        self.stats = {
            'scanned': 0,
            'indexed': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def run(self, extract_text: bool = True, generate_thumbnails: bool = True):
        """Run the PDF indexer."""
        if not self.scan_path.exists():
            logger.error(f"Scan path does not exist: {self.scan_path}")
            return self.stats
        
        logger.info(f"Starting PDF scan of: {self.scan_path} (root: {self.root_path})")
        
        for pdf_path in self.scan_path.rglob("*.pdf"):
            try:
                self._process_pdf(pdf_path, extract_text, generate_thumbnails)
                self.stats['scanned'] += 1
            except Exception as e:
                logger.error(f"Error processing {pdf_path}: {e}")
                self.stats['errors'] += 1
        
        logger.info(f"PDF scan complete: {self.stats}")
        return self.stats
    
    def _process_pdf(self, pdf_path: Path, extract_text: bool, generate_thumbnails: bool):
        """Process a single PDF file."""
        import pymupdf
        from fantasyfolio.core.database import get_asset_by_path
        
        # Check if already indexed
        existing = get_asset_by_path(str(pdf_path))
        is_update = existing is not None
        
        # Get file info
        stat = pdf_path.stat()
        file_hash = self._get_file_hash(pdf_path)
        
        # Calculate relative folder path
        try:
            folder_path = str(pdf_path.parent.relative_to(self.root_path))
            if folder_path == '.':
                folder_path = ''  # Empty string for files at root level
            logger.debug(f"Folder path for {pdf_path.name}: '{folder_path}' (root: {self.root_path})")
        except ValueError as e:
            folder_path = str(pdf_path.parent)
            logger.warning(f"Failed to calculate relative path for {pdf_path}: {e}, using absolute: {folder_path}")
        
        # Open and extract metadata
        doc = pymupdf.open(str(pdf_path))
        metadata = doc.metadata or {}
        
        # Look up which asset location this file belongs to (for volume_id)
        location = get_location_for_path(str(pdf_path), asset_type='documents')
        volume_id = location['id'] if location else None
        
        asset = {
            'file_path': str(pdf_path),
            'filename': pdf_path.name,
            'title': metadata.get('title') or pdf_path.stem,
            'author': metadata.get('author'),
            'publisher': self._extract_publisher(pdf_path, metadata),
            'page_count': len(doc),
            'file_size': stat.st_size,
            'file_hash': file_hash,
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'pdf_creator': metadata.get('creator'),
            'pdf_producer': metadata.get('producer'),
            'pdf_creation_date': metadata.get('creationDate'),
            'pdf_mod_date': metadata.get('modDate'),
            'folder_path': folder_path,
            'game_system': self._detect_game_system(pdf_path),
            'category': None,
            'tags': None,
            'thumbnail_path': None,
            'has_thumbnail': 0,
            'volume_id': volume_id
        }
        
        # Insert asset
        asset_id = insert_asset(asset)
        
        # Extract text if requested
        if extract_text:
            self._extract_text(doc, asset_id)
        
        # Extract bookmarks
        self._extract_bookmarks(doc, asset_id)
        
        # Generate thumbnail if requested
        if generate_thumbnails:
            self._generate_thumbnail(doc, asset_id)
        
        doc.close()
        
        # Track stats
        if is_update:
            self.stats['updated'] += 1
            logger.debug(f"Updated: {pdf_path.name}")
        else:
            self.stats['indexed'] += 1
            logger.debug(f"Indexed: {pdf_path.name}")
    
    def _get_file_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Calculate MD5 hash of first chunk of file."""
        with open(path, 'rb') as f:
            data = f.read(chunk_size)
        return hashlib.md5(data).hexdigest()
    
    def _extract_publisher(self, path: Path, metadata: Dict) -> Optional[str]:
        """Try to extract publisher from metadata or path."""
        if metadata.get('author'):
            return metadata['author']
        
        # Try to get from folder structure
        parts = path.parts
        if len(parts) > 2:
            return parts[-2]  # Parent folder name
        
        return None
    
    def _detect_game_system(self, path: Path) -> Optional[str]:
        """Detect game system from path or filename."""
        text = str(path).lower()
        
        systems = {
            'd&d': ['dnd', 'd&d', 'dungeons', 'dragons', '5e', '5th edition'],
            'pathfinder': ['pathfinder', 'pf2e', 'pf1e'],
            'call of cthulhu': ['cthulhu', 'coc'],
            'warhammer': ['warhammer', '40k', 'age of sigmar'],
            'shadowrun': ['shadowrun'],
            'traveller': ['traveller'],
            'savage worlds': ['savage worlds'],
        }
        
        for system, keywords in systems.items():
            if any(kw in text for kw in keywords):
                return system
        
        return None
    
    def _extract_text(self, doc, asset_id: int):
        """Extract text from all pages."""
        with get_connection() as conn:
            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                if text.strip():
                    conn.execute(
                        "INSERT OR REPLACE INTO asset_pages (asset_id, page_num, text_content) VALUES (?, ?, ?)",
                        (asset_id, page_num, text)
                    )
            conn.commit()
    
    def _extract_bookmarks(self, doc, asset_id: int):
        """Extract bookmarks/TOC."""
        toc = doc.get_toc()
        if not toc:
            return
        
        with get_connection() as conn:
            for level, title, page in toc:
                conn.execute(
                    "INSERT OR IGNORE INTO asset_bookmarks (asset_id, level, title, page_num) VALUES (?, ?, ?, ?)",
                    (asset_id, level, title, page)
                )
            conn.commit()
    
    def _generate_thumbnail(self, doc, asset_id: int):
        """Generate thumbnail for first page."""
        import pymupdf
        
        thumb_path = self.config.THUMBNAIL_DIR / "pdf" / f"{asset_id}.png"
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        
        page = doc[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5))
        pix.save(str(thumb_path))
        
        with get_connection() as conn:
            conn.execute(
                "UPDATE assets SET thumbnail_path = ?, has_thumbnail = 1 WHERE id = ?",
                (str(thumb_path), asset_id)
            )
            conn.commit()


def main():
    """CLI entry point."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    path = sys.argv[1] if len(sys.argv) > 1 else None
    indexer = PDFIndexer(path)
    stats = indexer.run()
    print(f"Indexing complete: {stats}")


if __name__ == '__main__':
    main()
