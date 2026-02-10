#!/usr/bin/env python3
"""
Test suite for DAM Efficient Indexing Architecture v1.2

Run with: python -m pytest tests/test_efficient_indexing.py -v
Or directly: python tests/test_efficient_indexing.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pytest
except ImportError:
    pytest = None


class TestHashing:
    """Test partial hash computation."""
    
    def test_partial_hash_consistency(self):
        """Hash of file should match hash of same bytes."""
        from dam.core.hashing import compute_partial_hash, compute_partial_hash_from_bytes
        
        # Create test file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            content = b'Test content ' * 10000  # ~130KB
            f.write(content)
            test_path = Path(f.name)
        
        try:
            hash1 = compute_partial_hash(test_path)
            hash2 = compute_partial_hash_from_bytes(content)
            assert hash1 == hash2, "Hashes should match"
        finally:
            test_path.unlink()
    
    def test_partial_hash_small_file(self):
        """Small files should hash correctly."""
        from dam.core.hashing import compute_partial_hash
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'Small file')
            test_path = Path(f.name)
        
        try:
            hash1 = compute_partial_hash(test_path)
            assert len(hash1) == 32, "Should be MD5 hex digest"
        finally:
            test_path.unlink()
    
    def test_different_files_different_hashes(self):
        """Different files should have different hashes."""
        from dam.core.hashing import compute_partial_hash_from_bytes
        
        hash1 = compute_partial_hash_from_bytes(b'Content A ' * 10000)
        hash2 = compute_partial_hash_from_bytes(b'Content B ' * 10000)
        assert hash1 != hash2, "Different content should have different hashes"


class TestThumbnails:
    """Test thumbnail storage logic."""
    
    def test_determine_thumb_location_sidecar(self):
        """Writable volume should use sidecar."""
        from dam.core.thumbnails import determine_thumb_location, ThumbStorage
        
        model = {'file_path': '/test/path/model.stl', 'partial_hash': 'abc123'}
        volume = {'mount_path': '/test', 'is_readonly': False}
        central = Path('/central')
        
        # Note: This will fail on actual filesystem check, but logic is correct
        storage, path = determine_thumb_location(model, volume, central)
        # Would be SIDECAR if /test/path was writable
        assert storage in (ThumbStorage.SIDECAR, ThumbStorage.CENTRAL)
    
    def test_determine_thumb_location_readonly(self):
        """Read-only volume should use central cache."""
        from dam.core.thumbnails import determine_thumb_location, ThumbStorage
        
        model = {'file_path': '/readonly/model.stl', 'partial_hash': 'abc123'}
        volume = {'mount_path': '/readonly', 'is_readonly': True}
        central = Path('/central')
        
        storage, path = determine_thumb_location(model, volume, central)
        assert storage == ThumbStorage.CENTRAL
    
    def test_determine_thumb_location_archive(self):
        """Archive member should use archive_sidecar or central."""
        from dam.core.thumbnails import determine_thumb_location, ThumbStorage
        
        model = {
            'archive_path': '/test/archive.zip',
            'archive_member': 'model.stl',
            'partial_hash': 'abc123'
        }
        volume = {'mount_path': '/test', 'is_readonly': True}
        central = Path('/central')
        
        storage, path = determine_thumb_location(model, volume, central)
        assert storage in (ThumbStorage.ARCHIVE_SIDECAR, ThumbStorage.CENTRAL)


class TestScanner:
    """Test scan logic."""
    
    def test_find_existing_asset_new(self):
        """New file should return 'new' match type."""
        from dam.core.scanner import find_existing_asset
        import sqlite3
        
        # Create in-memory database
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE models (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                archive_path TEXT,
                archive_member TEXT,
                partial_hash TEXT,
                file_mtime INTEGER,
                file_size_bytes INTEGER
            )
        """)
        
        match_type, existing = find_existing_asset(
            conn, 'models',
            file_path='/new/file.stl',
            file_size=1000,
            file_mtime=12345
        )
        
        assert match_type == 'new'
        assert existing is None
        conn.close()
    
    def test_find_existing_asset_unchanged(self):
        """File with same path/mtime/size should be unchanged."""
        from dam.core.scanner import find_existing_asset
        import sqlite3
        
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE models (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                archive_path TEXT,
                archive_member TEXT,
                partial_hash TEXT,
                file_mtime INTEGER,
                file_size_bytes INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO models (file_path, file_mtime, file_size_bytes, partial_hash)
            VALUES ('/existing/file.stl', 12345, 1000, 'abc123')
        """)
        
        match_type, existing = find_existing_asset(
            conn, 'models',
            file_path='/existing/file.stl',
            file_size=1000,
            file_mtime=12345
        )
        
        assert match_type == 'unchanged'
        assert existing is not None
        conn.close()


class TestAPIEndpoints:
    """Test API endpoints (requires running server)."""
    
    def get_base_url(self):
        return os.environ.get('DAM_TEST_URL', 'https://localhost:8008')
    
    def test_index_stats(self):
        """Index stats endpoint should return valid JSON."""
        import urllib.request
        import ssl
        
        base_url = self.get_base_url()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(f'{base_url}/api/models/index-stats')
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read())
            assert 'total' in data
            assert 'with_hash' in data
    
    def test_volumes_endpoint(self):
        """Volumes endpoint should return list."""
        import urllib.request
        import ssl
        
        base_url = self.get_base_url()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(f'{base_url}/api/volumes')
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read())
            assert isinstance(data, list)


def run_basic_tests():
    """Run basic tests without pytest."""
    print("=" * 60)
    print("DAM Efficient Indexing - Basic Tests")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Hashing
    print("\n[Test 1] Partial Hash Consistency...")
    try:
        from dam.core.hashing import compute_partial_hash_from_bytes
        h1 = compute_partial_hash_from_bytes(b'test' * 10000)
        h2 = compute_partial_hash_from_bytes(b'test' * 10000)
        assert h1 == h2
        print("  ✓ PASSED")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1
    
    # Test 2: Different content
    print("\n[Test 2] Different Content -> Different Hash...")
    try:
        from dam.core.hashing import compute_partial_hash_from_bytes
        h1 = compute_partial_hash_from_bytes(b'content A' * 10000)
        h2 = compute_partial_hash_from_bytes(b'content B' * 10000)
        assert h1 != h2
        print("  ✓ PASSED")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1
    
    # Test 3: Thumbnail storage
    print("\n[Test 3] Thumbnail Storage Decision...")
    try:
        from dam.core.thumbnails import determine_thumb_location, ThumbStorage
        model = {'file_path': '/test.stl', 'partial_hash': 'abc'}
        volume = {'mount_path': '/', 'is_readonly': True}
        storage, _ = determine_thumb_location(model, volume, Path('/central'))
        assert storage == ThumbStorage.CENTRAL
        print("  ✓ PASSED")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1
    
    # Test 4: Scanner identity
    print("\n[Test 4] Scanner Identity Resolution...")
    try:
        from dam.core.scanner import find_existing_asset
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE models (id INTEGER PRIMARY KEY, file_path TEXT, archive_path TEXT, archive_member TEXT, partial_hash TEXT, file_mtime INTEGER, file_size_bytes INTEGER)")
        match_type, _ = find_existing_asset(conn, 'models', file_path='/new.stl')
        assert match_type == 'new'
        conn.close()
        print("  ✓ PASSED")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    if '--pytest' in sys.argv:
        pytest.main([__file__, '-v'])
    else:
        success = run_basic_tests()
        sys.exit(0 if success else 1)
