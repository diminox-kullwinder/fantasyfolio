"""
Deduplication system for FantasyFolio assets.

Two-tier approach:
1. Partial hash collisions → candidates for full hash
2. Full hash verification → true duplicates
3. Mark as duplicates in database
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

from fantasyfolio.core.hashing import compute_full_hash, compute_full_hash_from_bytes
import zipfile


@dataclass
class DuplicateCandidate:
    """Two files with matching partial hash."""
    file1_id: int
    file2_id: int
    file1_name: str
    file2_name: str
    partial_hash: str
    file1_path: str
    file2_path: str


@dataclass
class DuplicateVerified:
    """Two files confirmed as identical (same full hash)."""
    primary_id: int  # Keep this one
    duplicate_id: int  # Mark as duplicate
    primary_name: str
    duplicate_name: str
    partial_hash: str
    full_hash: str
    file_size: int


def find_partial_hash_collisions(
    db_path: str,
    table: str = 'models'
) -> List[DuplicateCandidate]:
    """
    Find all partial hash collisions (candidates for full hash verification).
    
    Args:
        db_path: Path to database
        table: 'models' or 'assets'
    
    Returns:
        List of DuplicateCandidate objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    candidates = []
    
    # Find partial hashes with multiple files
    collisions = conn.execute(f"""
        SELECT partial_hash, COUNT(*) as count
        FROM {table}
        WHERE partial_hash IS NOT NULL
        GROUP BY partial_hash
        HAVING COUNT(*) > 1
        ORDER BY count DESC, file_size DESC
    """).fetchall()
    
    print(f"Found {len(collisions)} partial hash collisions")
    
    for collision in collisions:
        partial_hash = collision['partial_hash']
        count = collision['count']
        
        # Get all files with this partial hash
        files = conn.execute(f"""
            SELECT id, filename, file_path, archive_path, archive_member, file_size
            FROM {table}
            WHERE partial_hash = ?
            ORDER BY file_size DESC, id ASC
        """, (partial_hash,)).fetchall()
        
        # Create pairs for full hash verification
        for i in range(len(files) - 1):
            for j in range(i + 1, len(files)):
                file1 = files[i]
                file2 = files[j]
                
                path1 = file1['archive_path'] if file1['archive_path'] else file1['file_path']
                path2 = file2['archive_path'] if file2['archive_path'] else file2['file_path']
                
                candidates.append(DuplicateCandidate(
                    file1_id=file1['id'],
                    file2_id=file2['id'],
                    file1_name=file1['filename'],
                    file2_name=file2['filename'],
                    partial_hash=partial_hash,
                    file1_path=str(path1),
                    file2_path=str(path2)
                ))
    
    conn.close()
    return candidates


def get_file_content(db_path: str, model_id: int, table: str = 'models') -> Optional[bytes]:
    """
    Get file content from disk or archive.
    
    Args:
        db_path: Path to database
        model_id: Model ID
        table: Table name
    
    Returns:
        File content as bytes, or None if file not found
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    model = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?",
        (model_id,)
    ).fetchone()
    conn.close()
    
    if not model:
        return None
    
    try:
        # Try archive member first
        if model['archive_path'] and model['archive_member']:
            archive_path = Path(model['archive_path'])
            if archive_path.exists():
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zf:
                        return zf.read(model['archive_member'])
                except Exception as e:
                    print(f"  ✗ Failed to read {model_id} from archive: {e}")
                    return None
        
        # Try direct file
        if model['file_path']:
            file_path = Path(model['file_path'])
            if file_path.exists():
                return file_path.read_bytes()
        
        return None
    
    except Exception as e:
        print(f"  ✗ Error reading file {model_id}: {e}")
        return None


def verify_collision(
    db_path: str,
    candidate: DuplicateCandidate,
    table: str = 'models'
) -> Optional[DuplicateVerified]:
    """
    Verify if two files with matching partial hash have same full hash.
    
    Args:
        db_path: Path to database
        candidate: DuplicateCandidate to verify
        table: Table name
    
    Returns:
        DuplicateVerified if files match, None if different
    """
    # Get content for both files
    content1 = get_file_content(db_path, candidate.file1_id, table)
    content2 = get_file_content(db_path, candidate.file2_id, table)
    
    if not content1 or not content2:
        # Can't verify if we can't read files
        return None
    
    # Compute full hashes
    full_hash1 = compute_full_hash_from_bytes(content1)
    full_hash2 = compute_full_hash_from_bytes(content2)
    
    # If hashes match, it's a true duplicate
    if full_hash1 == full_hash2:
        # Primary is the one that appeared first (lower ID)
        primary_id = min(candidate.file1_id, candidate.file2_id)
        duplicate_id = max(candidate.file1_id, candidate.file2_id)
        
        primary_name = candidate.file1_name if candidate.file1_id == primary_id else candidate.file2_name
        duplicate_name = candidate.file2_name if candidate.file1_id == primary_id else candidate.file1_name
        
        return DuplicateVerified(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            primary_name=primary_name,
            duplicate_name=duplicate_name,
            partial_hash=candidate.partial_hash,
            full_hash=full_hash1,
            file_size=len(content1)
        )
    
    return None


def process_duplicates(
    db_path: str,
    table: str = 'models',
    callback=None
) -> Dict:
    """
    Find and verify all duplicates.
    
    Process:
    1. Find partial hash collisions
    2. Compute full hashes for collisions
    3. Mark verified duplicates in database
    4. Update full_hash column for all checked files
    
    Args:
        db_path: Path to database
        table: Table name ('models' or 'assets')
        callback: Optional function(checked, total, duplicate) for progress
    
    Returns:
        Results dict with statistics
    """
    results = {
        'candidates_found': 0,
        'candidates_verified': 0,
        'duplicates_found': 0,
        'full_hashes_computed': 0,
        'full_hashes_updated': 0,
        'errors': 0,
        'elapsed_seconds': 0,
        'duplicates': []
    }
    
    start_time = time.time()
    
    # Step 1: Find candidates
    print("\n🔍 Step 1: Finding partial hash collisions...")
    candidates = find_partial_hash_collisions(db_path, table)
    results['candidates_found'] = len(candidates)
    print(f"  Found {len(candidates)} collision pairs to verify\n")
    
    if len(candidates) == 0:
        results['elapsed_seconds'] = time.time() - start_time
        print("  ✓ No collisions found - no duplicates detected")
        return results
    
    # Step 2: Verify collisions
    print(f"🔐 Step 2: Computing full hashes for collision verification...")
    verified_duplicates = []
    
    for i, candidate in enumerate(candidates):
        if callback:
            callback(i, len(candidates), None)
        
        try:
            verified = verify_collision(db_path, candidate, table)
            results['full_hashes_computed'] += 2  # Both files hashed
            
            if verified:
                verified_duplicates.append(verified)
                results['duplicates_found'] += 1
                print(f"  ✓ [{i+1}/{len(candidates)}] Duplicate found:")
                print(f"    Keep: {verified.primary_name} (ID: {verified.primary_id})")
                print(f"    Mark: {verified.duplicate_name} (ID: {verified.duplicate_id})")
                print(f"    Hash: {verified.full_hash[:16]}... ({verified.file_size / (1024*1024):.1f}MB)")
        
        except Exception as e:
            results['errors'] += 1
            print(f"  ✗ Error verifying candidate {i+1}: {e}")
    
    print(f"\n  ✓ Full hash verification complete")
    print(f"  Found {results['duplicates_found']} true duplicates\n")
    
    # Step 3: Update database with results
    if verified_duplicates:
        print(f"💾 Step 3: Updating database...")
        conn = sqlite3.connect(db_path)
        
        for duplicate in verified_duplicates:
            try:
                conn.execute(f"""
                    UPDATE {table}
                    SET full_hash = ?,
                        is_duplicate = 1,
                        duplicate_of_id = ?
                    WHERE id = ?
                """, (
                    duplicate.full_hash,
                    duplicate.primary_id,
                    duplicate.duplicate_id
                ))
                
                # Also update primary with full_hash
                conn.execute(f"""
                    UPDATE {table}
                    SET full_hash = ?
                    WHERE id = ? AND full_hash IS NULL
                """, (
                    duplicate.full_hash,
                    duplicate.primary_id
                ))
                
                results['full_hashes_updated'] += 2
            
            except Exception as e:
                results['errors'] += 1
                print(f"  ✗ Error updating {duplicate.duplicate_id}: {e}")
        
        conn.commit()
        conn.close()
        print(f"  ✓ Database updated\n")
    
    results['elapsed_seconds'] = time.time() - start_time
    results['duplicates'] = [
        {
            'primary_id': d.primary_id,
            'duplicate_id': d.duplicate_id,
            'primary_name': d.primary_name,
            'duplicate_name': d.duplicate_name,
            'full_hash': d.full_hash,
            'file_size_mb': d.file_size / (1024*1024)
        }
        for d in verified_duplicates
    ]
    
    return results
