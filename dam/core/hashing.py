"""
Partial hash computation for asset identity.

Uses first 64KB + last 64KB + file size to create a fast content fingerprint.
~99.9% reliable for identifying unique files. Fast enough for real-time scanning.
"""

import hashlib
from pathlib import Path
from typing import Optional
import zipfile
import io

CHUNK_SIZE = 64 * 1024  # 64KB


def compute_partial_hash(file_path: Path) -> str:
    """
    Compute partial hash for a standalone file.
    
    Algorithm: MD5(first_64KB + last_64KB + str(size))
    
    Args:
        file_path: Path to file
    
    Returns:
        Hex digest string
    """
    size = file_path.stat().st_size
    hasher = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        # First chunk
        hasher.update(f.read(CHUNK_SIZE))
        
        # Last chunk (if file large enough)
        if size > CHUNK_SIZE * 2:
            f.seek(-CHUNK_SIZE, 2)  # Seek from end
            hasher.update(f.read(CHUNK_SIZE))
        elif size > CHUNK_SIZE:
            # File is between 64KB and 128KB, read the rest
            hasher.update(f.read())
    
    # Include size to differentiate same-start-end files
    hasher.update(str(size).encode())
    
    return hasher.hexdigest()


def compute_partial_hash_from_bytes(data: bytes) -> str:
    """
    Compute partial hash from bytes (for archive members).
    
    Args:
        data: File content as bytes
    
    Returns:
        Hex digest string
    """
    size = len(data)
    hasher = hashlib.md5()
    
    # First chunk
    hasher.update(data[:CHUNK_SIZE])
    
    # Last chunk
    if size > CHUNK_SIZE * 2:
        hasher.update(data[-CHUNK_SIZE:])
    elif size > CHUNK_SIZE:
        hasher.update(data[CHUNK_SIZE:])
    
    # Include size
    hasher.update(str(size).encode())
    
    return hasher.hexdigest()


def compute_partial_hash_from_archive(
    archive_path: Path,
    member_name: str
) -> Optional[str]:
    """
    Compute partial hash for a file inside a ZIP archive.
    
    Args:
        archive_path: Path to ZIP file
        member_name: Name of member within archive
    
    Returns:
        Hex digest string, or None if member not found
    """
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            data = zf.read(member_name)
            return compute_partial_hash_from_bytes(data)
    except (KeyError, zipfile.BadZipFile):
        return None


def compute_full_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Compute full MD5 hash of a file.
    Use sparingly - slow for large files.
    
    Args:
        file_path: Path to file
        chunk_size: Read chunk size
    
    Returns:
        Hex digest string
    """
    hasher = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def compute_full_hash_from_bytes(data: bytes) -> str:
    """
    Compute full MD5 hash from bytes.
    
    Args:
        data: File content as bytes
    
    Returns:
        Hex digest string
    """
    return hashlib.md5(data).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# BATCH HASHING (for existing assets)
# ═══════════════════════════════════════════════════════════════════════════

def batch_compute_hashes(
    db_path: str,
    table: str = 'models',
    batch_size: int = 100,
    limit: int = None,
    callback=None
) -> dict:
    """
    Compute partial hashes for assets missing them.
    
    Args:
        db_path: Path to database
        table: 'models' or 'assets'
        batch_size: Number of assets per batch
        limit: Maximum total to process (None = all)
        callback: Optional function(processed, total, current_file) for progress
    
    Returns:
        Dict with results: {processed, skipped, errors, elapsed_seconds}
    """
    import sqlite3
    import time
    from datetime import datetime
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    results = {
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': [],
        'elapsed_seconds': 0
    }
    
    start_time = time.time()
    
    try:
        # Count total needing hashes
        total = conn.execute(f"""
            SELECT COUNT(*) FROM {table} 
            WHERE partial_hash IS NULL AND volume_id IS NOT NULL
        """).fetchone()[0]
        
        if limit:
            total = min(total, limit)
        
        print(f"Found {total} {table} needing hash computation")
        
        offset = 0
        while True:
            # Get batch - different columns for models vs assets
            if table == 'models':
                query = f"""
                    SELECT id, file_path, archive_path, archive_member, volume_id
                    FROM {table}
                    WHERE partial_hash IS NULL AND volume_id IS NOT NULL
                    LIMIT ? OFFSET ?
                """
            else:
                # assets table doesn't have archive columns
                query = f"""
                    SELECT id, file_path, volume_id
                    FROM {table}
                    WHERE partial_hash IS NULL AND volume_id IS NOT NULL
                    LIMIT ? OFFSET ?
                """
            
            if limit and offset + batch_size > limit:
                batch_size = limit - offset
            
            rows = conn.execute(query, (batch_size, offset)).fetchall()
            
            if not rows:
                break
            
            for row in rows:
                row = dict(row)
                
                if callback:
                    callback(results['processed'], total, row.get('file_path', row.get('archive_path', '')))
                
                try:
                    # Compute hash based on type
                    is_archive_member = (
                        table == 'models' and 
                        row.get('archive_path') and 
                        row.get('archive_member')
                    )
                    
                    if is_archive_member:
                        # Archive member (3D models in ZIPs)
                        archive = Path(row['archive_path'])
                        if not archive.exists():
                            results['skipped'] += 1
                            continue
                        
                        partial = compute_partial_hash_from_archive(
                            archive, row['archive_member']
                        )
                    else:
                        # Standalone file (PDFs or standalone 3D models)
                        file_path = Path(row['file_path'])
                        if not file_path.exists():
                            results['skipped'] += 1
                            continue
                        
                        partial = compute_partial_hash(file_path)
                    
                    if partial:
                        # Get file size and mtime
                        if is_archive_member:
                            archive = Path(row['archive_path'])
                            stat = archive.stat()
                            file_mtime = int(stat.st_mtime)
                            
                            # Get member size from archive
                            with zipfile.ZipFile(archive, 'r') as zf:
                                info = zf.getinfo(row['archive_member'])
                                file_size = info.file_size
                        else:
                            file_path = Path(row['file_path'])
                            stat = file_path.stat()
                            file_size = stat.st_size
                            file_mtime = int(stat.st_mtime)
                        
                        # Update database
                        conn.execute(f"""
                            UPDATE {table} SET 
                                partial_hash = ?,
                                file_size_bytes = ?,
                                file_mtime = ?,
                                last_verified_at = ?
                            WHERE id = ?
                        """, (
                            partial,
                            file_size,
                            file_mtime,
                            datetime.now().isoformat(),
                            row['id']
                        ))
                        
                        results['processed'] += 1
                    else:
                        results['skipped'] += 1
                
                except Exception as e:
                    results['errors'] += 1
                    if len(results['error_details']) < 10:
                        results['error_details'].append({
                            'id': row['id'],
                            'path': row.get('file_path') or row.get('archive_path'),
                            'error': str(e)
                        })
            
            # Commit batch
            conn.commit()
            
            offset += len(rows)
            
            if limit and offset >= limit:
                break
        
    finally:
        conn.close()
        results['elapsed_seconds'] = round(time.time() - start_time, 2)
    
    return results


if __name__ == '__main__':
    # Test with sample files
    import tempfile
    
    # Create test file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b'Hello World!' * 10000)  # ~120KB
        test_path = Path(f.name)
    
    try:
        hash1 = compute_partial_hash(test_path)
        print(f"Partial hash: {hash1}")
        
        # Read as bytes and compare
        with open(test_path, 'rb') as f:
            data = f.read()
        hash2 = compute_partial_hash_from_bytes(data)
        print(f"From bytes:   {hash2}")
        
        assert hash1 == hash2, "Hashes should match!"
        print("✓ Hash consistency verified")
        
    finally:
        test_path.unlink()
