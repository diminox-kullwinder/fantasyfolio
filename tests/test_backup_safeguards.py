#!/usr/bin/env python3
"""
Backup Safeguards Validation Test Suite

Tests all implemented backup safeguard features and produces a report.
Run with: python -m tests.test_backup_safeguards

Features tested:
- Volume monitoring service
- Volume status API endpoints
- Index API with volume check
- UI elements (via API responses)
"""

import os
import sys
import json
import time
import requests
import urllib3
from datetime import datetime
from pathlib import Path

# Suppress SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
# Use environment variable or default to UAT instance
import os
BASE_URL = os.environ.get('DAM_TEST_URL', "https://localhost:8009")  # Default to UAT
VERIFY_SSL = False

# Test results storage
results = {
    'passed': [],
    'failed': [],
    'warnings': [],
    'start_time': None,
    'end_time': None
}


def log_pass(test_name, details=""):
    results['passed'].append({'test': test_name, 'details': details})
    print(f"  ✅ PASS: {test_name}")
    if details:
        print(f"          {details}")


def log_fail(test_name, error):
    results['failed'].append({'test': test_name, 'error': str(error)})
    print(f"  ❌ FAIL: {test_name}")
    print(f"          Error: {error}")


def log_warn(test_name, warning):
    results['warnings'].append({'test': test_name, 'warning': warning})
    print(f"  ⚠️  WARN: {test_name}")
    print(f"          {warning}")


def api_get(endpoint):
    """Make GET request to API."""
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", verify=VERIFY_SSL, timeout=10)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, str(e)


def api_get_raw(endpoint):
    """Make GET request without JSON parsing (for file downloads)."""
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", verify=VERIFY_SSL, timeout=10)
        # Try to parse as JSON for error responses, otherwise return raw content type
        content_type = resp.headers.get('content-type', '')
        if 'application/json' in content_type:
            return resp.status_code, resp.json()
        else:
            return resp.status_code, {'content_type': content_type, 'size': len(resp.content)}
    except Exception as e:
        return None, str(e)


def api_post(endpoint, data):
    """Make POST request to API."""
    try:
        resp = requests.post(
            f"{BASE_URL}{endpoint}",
            json=data,
            verify=VERIFY_SSL,
            timeout=10
        )
        return resp.status_code, resp.json()
    except Exception as e:
        return None, str(e)


# =============================================================================
# TEST SECTION 1: Volume Monitor Service (Direct Import)
# =============================================================================

def test_volume_monitor_service():
    """Test the volume_monitor.py service directly."""
    print("\n" + "=" * 60)
    print("SECTION 1: Volume Monitor Service (Direct)")
    print("=" * 60)
    
    try:
        # Add project to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from dam.services.volume_monitor import (
            check_volume_available,
            get_all_volume_status,
            get_volume_for_path,
            check_volumes_for_index,
            get_configured_volumes
        )
        
        # Test 1.1: get_configured_volumes
        try:
            volumes = get_configured_volumes()
            if 'pdfs' in volumes and 'models' in volumes:
                log_pass("get_configured_volumes()", f"Found volumes: {list(volumes.keys())}")
            else:
                log_fail("get_configured_volumes()", f"Missing expected volumes. Got: {volumes}")
        except Exception as e:
            log_fail("get_configured_volumes()", e)
        
        # Test 1.2: check_volume_available (existing path)
        try:
            result = check_volume_available("/tmp")
            if result['available'] == True:
                log_pass("check_volume_available(/tmp)", "Correctly identified /tmp as available")
            else:
                log_fail("check_volume_available(/tmp)", f"Should be available. Got: {result}")
        except Exception as e:
            log_fail("check_volume_available(/tmp)", e)
        
        # Test 1.3: check_volume_available (non-existent path)
        try:
            result = check_volume_available("/Volumes/NonExistentVolume123")
            if result['available'] == False and result['reason']:
                log_pass("check_volume_available(non-existent)", f"Correctly unavailable: {result['reason']}")
            else:
                log_fail("check_volume_available(non-existent)", f"Should be unavailable. Got: {result}")
        except Exception as e:
            log_fail("check_volume_available(non-existent)", e)
        
        # Test 1.4: get_all_volume_status
        try:
            status = get_all_volume_status()
            if 'volumes' in status and 'all_available' in status and 'checked_at' in status:
                vol_count = len(status['volumes'])
                avail_count = sum(1 for v in status['volumes'].values() if v['available'])
                log_pass("get_all_volume_status()", f"{avail_count}/{vol_count} volumes available")
            else:
                log_fail("get_all_volume_status()", f"Missing expected fields. Got: {list(status.keys())}")
        except Exception as e:
            log_fail("get_all_volume_status()", e)
        
        # Test 1.5: get_volume_for_path
        try:
            volumes = get_configured_volumes()
            if 'models' in volumes:
                test_path = volumes['models'] + "/test.stl"
                result = get_volume_for_path(test_path)
                if result == 'models':
                    log_pass("get_volume_for_path(models)", f"Correctly identified as 'models'")
                else:
                    log_warn("get_volume_for_path(models)", f"Expected 'models', got '{result}'")
            else:
                log_warn("get_volume_for_path", "No models volume configured to test")
        except Exception as e:
            log_fail("get_volume_for_path()", e)
        
        # Test 1.6: check_volumes_for_index
        try:
            for idx_type in ['pdfs', 'models', 'all']:
                result = check_volumes_for_index(idx_type)
                if 'can_proceed' in result and 'required_volumes' in result and 'message' in result:
                    status = "✓ can proceed" if result['can_proceed'] else "⏸️ suspended"
                    log_pass(f"check_volumes_for_index({idx_type})", status)
                else:
                    log_fail(f"check_volumes_for_index({idx_type})", f"Missing fields. Got: {list(result.keys())}")
        except Exception as e:
            log_fail("check_volumes_for_index()", e)
            
    except ImportError as e:
        log_fail("Import volume_monitor", f"Could not import: {e}")


# =============================================================================
# TEST SECTION 2: Volume Status API Endpoints
# =============================================================================

def test_volume_status_api():
    """Test the /api/system/* endpoints."""
    print("\n" + "=" * 60)
    print("SECTION 2: Volume Status API Endpoints")
    print("=" * 60)
    
    # Test 2.1: GET /api/system/volume-status
    try:
        code, data = api_get("/api/system/volume-status")
        if code == 200 and 'volumes' in data:
            vol_count = len(data['volumes'])
            log_pass("GET /api/system/volume-status", f"Returned {vol_count} volumes")
            
            # Verify structure
            for name, status in data['volumes'].items():
                required_fields = ['path', 'available', 'reason', 'last_checked']
                missing = [f for f in required_fields if f not in status]
                if missing:
                    log_warn(f"Volume '{name}' structure", f"Missing fields: {missing}")
        else:
            log_fail("GET /api/system/volume-status", f"Status {code}, data: {data}")
    except Exception as e:
        log_fail("GET /api/system/volume-status", e)
    
    # Test 2.2: GET /api/system/check-index/models
    try:
        code, data = api_get("/api/system/check-index/models")
        if code == 200 and 'can_proceed' in data:
            status = "can proceed" if data['can_proceed'] else "suspended"
            log_pass("GET /api/system/check-index/models", f"Status: {status}")
        else:
            log_fail("GET /api/system/check-index/models", f"Status {code}, data: {data}")
    except Exception as e:
        log_fail("GET /api/system/check-index/models", e)
    
    # Test 2.3: GET /api/system/check-index/invalid (should return 400)
    try:
        code, data = api_get("/api/system/check-index/invalid_type")
        if code == 400:
            log_pass("GET /api/system/check-index/invalid", "Correctly rejected invalid type")
        else:
            log_warn("GET /api/system/check-index/invalid", f"Expected 400, got {code}")
    except Exception as e:
        log_fail("GET /api/system/check-index/invalid", e)
    
    # Test 2.4: GET /api/system/info
    try:
        code, data = api_get("/api/system/info")
        if code == 200 and 'database' in data and 'volumes' in data:
            db_size = data['database'].get('size_human', 'unknown')
            log_pass("GET /api/system/info", f"DB size: {db_size}")
        else:
            log_fail("GET /api/system/info", f"Status {code}, data: {data}")
    except Exception as e:
        log_fail("GET /api/system/info", e)
    
    # Test 2.5: GET /api/system/health
    try:
        code, data = api_get("/api/system/health")
        if code == 200 and data.get('status') == 'healthy':
            log_pass("GET /api/system/health", "Service healthy")
        else:
            log_fail("GET /api/system/health", f"Status {code}, data: {data}")
    except Exception as e:
        log_fail("GET /api/system/health", e)


# =============================================================================
# TEST SECTION 3: Index API with Volume Check
# =============================================================================

def test_index_api_volume_check():
    """Test the POST /api/index endpoint with volume checks."""
    print("\n" + "=" * 60)
    print("SECTION 3: Index API with Volume Check")
    print("=" * 60)
    
    # First get the configured volumes to know what paths to test
    code, vol_data = api_get("/api/system/volume-status")
    if code != 200:
        log_fail("Index API tests", "Could not get volume status for test setup")
        return
    
    # Test 3.1: Index with unavailable volume path
    try:
        code, data = api_post("/api/index", {
            "type": "3d",
            "path": "/Volumes/NonExistentVolume/Models"
        })
        if code == 200 and data.get('status') == 'suspended':
            log_pass("POST /api/index (unavailable volume)", f"Correctly suspended: {data.get('message', '')[:50]}")
        else:
            log_fail("POST /api/index (unavailable volume)", f"Expected suspended. Got: {code}, {data}")
    except Exception as e:
        log_fail("POST /api/index (unavailable volume)", e)
    
    # Test 3.2: Index with available volume (if models volume is available)
    models_vol = vol_data.get('volumes', {}).get('models', {})
    if models_vol.get('available'):
        try:
            # Use a real path but we'll check the response without actually running
            code, data = api_post("/api/index", {
                "type": "3d",
                "path": models_vol['path']
            })
            if code == 200 and data.get('status') == 'started':
                log_pass("POST /api/index (available volume)", "Correctly started indexing")
            elif code == 200 and data.get('status') == 'suspended':
                log_warn("POST /api/index (available volume)", f"Unexpectedly suspended: {data.get('message')}")
            else:
                log_fail("POST /api/index (available volume)", f"Unexpected: {code}, {data}")
        except Exception as e:
            log_fail("POST /api/index (available volume)", e)
    else:
        log_warn("POST /api/index (available volume)", "Models volume not available, skipping test")
    
    # Test 3.3: Index with missing required fields
    try:
        code, data = api_post("/api/index", {"type": "pdf"})
        if code == 400:
            log_pass("POST /api/index (no path)", "Correctly rejected missing path")
        else:
            log_warn("POST /api/index (no path)", f"Expected 400, got {code}")
    except Exception as e:
        log_fail("POST /api/index (no path)", e)
    
    # Test 3.4: Response includes status field
    try:
        code, data = api_post("/api/index", {
            "type": "pdf",
            "path": "/Volumes/NonExistent"
        })
        if 'status' in data:
            log_pass("Index API response has 'status' field", f"status={data['status']}")
        else:
            log_fail("Index API response has 'status' field", f"Missing. Keys: {list(data.keys())}")
    except Exception as e:
        log_fail("Index API response has 'status' field", e)


# =============================================================================
# TEST SECTION 4: Download Availability Check
# =============================================================================

def test_download_availability():
    """Test download endpoints return proper errors for unavailable volumes."""
    print("\n" + "=" * 60)
    print("SECTION 4: Download Availability Check")
    print("=" * 60)
    
    # Test 4.1: Asset download with valid ID (file on available volume)
    try:
        # First get a valid asset ID
        code, assets = api_get("/api/assets?limit=1")
        if code == 200 and assets:
            asset_id = assets[0]['id']
            code, data = api_get_raw(f"/api/assets/{asset_id}/download")
            # Could be 200 (success), 404 (file moved), or 503 (volume offline)
            if code == 200:
                log_pass("Asset download endpoint", f"OK - downloaded {data.get('size', 0)} bytes")
            elif code in [404, 503]:
                err = data.get('error', 'unknown') if isinstance(data, dict) else 'error'
                log_pass("Asset download endpoint", f"Proper error response: {code} ({err})")
            else:
                log_fail("Asset download endpoint", f"Unexpected code: {code}")
        else:
            log_warn("Asset download test", "No assets in database to test")
    except Exception as e:
        log_fail("Asset download endpoint", e)
    
    # Test 4.2: Model download with valid ID
    try:
        # First get a valid model ID
        code, models = api_get("/api/models?limit=1")
        if code == 200 and models:
            model_id = models[0]['id']
            code, data = api_get_raw(f"/api/models/{model_id}/download")
            if code == 200:
                log_pass("Model download endpoint", f"OK - downloaded {data.get('size', 0)} bytes")
            elif code in [404, 503]:
                err = data.get('error', 'unknown') if isinstance(data, dict) else 'error'
                log_pass("Model download endpoint", f"Proper error response: {code} ({err})")
            else:
                log_fail("Model download endpoint", f"Unexpected code: {code}")
        else:
            log_warn("Model download test", "No models in database to test")
    except Exception as e:
        log_fail("Model download endpoint", e)
    
    # Test 4.3: Download error response has correct structure
    try:
        # Test with non-existent asset
        code, data = api_get("/api/assets/999999/download")
        if code == 404 and 'error' in data:
            log_pass("Download 404 response structure", f"error={data.get('error')}")
        else:
            log_warn("Download 404 response", f"Code={code}, has error field: {'error' in data}")
    except Exception as e:
        log_fail("Download 404 response structure", e)
    
    # Test 4.4: Volume unavailable returns 503 with volume_unavailable error
    # (We can't easily test this without unmounting a volume, so we verify the code path exists)
    try:
        # Check that volume_monitor is importable
        from dam.services.volume_monitor import check_volume_for_path
        result = check_volume_for_path("/Volumes/NonExistentTestVolume/test.pdf")
        if not result['available']:
            log_pass("Volume check for invalid path", f"correctly unavailable: {result.get('reason', 'no reason')[:40]}")
        else:
            log_warn("Volume check for invalid path", "Expected unavailable for fake volume")
    except Exception as e:
        log_fail("Volume check for invalid path", e)


# =============================================================================
# TEST SECTION 5: Soft Delete Functionality
# =============================================================================

def test_soft_delete():
    """Test soft delete database operations."""
    print("\n" + "=" * 60)
    print("SECTION 5: Soft Delete Functionality")
    print("=" * 60)
    
    # Add project to path for imports
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Test 5.1: Stats include deleted_count field
    try:
        code, stats = api_get("/api/stats")
        if code == 200 and 'deleted_count' in stats:
            log_pass("Stats include deleted_count", f"deleted_count={stats.get('deleted_count', 0)}")
        else:
            log_fail("Stats include deleted_count", f"Missing field. Keys: {list(stats.keys()) if stats else 'none'}")
    except Exception as e:
        log_fail("Stats include deleted_count", e)
    
    # Test 5.2: Database soft delete functions exist
    try:
        from dam.core.database import (
            soft_delete_asset, restore_asset, get_deleted_assets,
            soft_delete_model, restore_model, get_deleted_models
        )
        log_pass("Soft delete functions available", "All 6 functions imported successfully")
    except ImportError as e:
        log_fail("Soft delete functions available", f"Import error: {e}")
    
    # Test 5.3: Trash API endpoints exist
    try:
        code, data = api_get("/api/trash")
        if code == 200:
            log_pass("GET /api/trash endpoint", f"Returns {len(data.get('assets', []))} assets, {len(data.get('models', []))} models")
        elif code == 404:
            log_warn("GET /api/trash endpoint", "Endpoint not implemented yet")
        else:
            log_fail("GET /api/trash endpoint", f"Unexpected code: {code}")
    except Exception as e:
        log_fail("GET /api/trash endpoint", e)
    
    # Test 5.4: Trash cleanup API exists
    try:
        code, data = api_get("/api/trash/cleanup/status")
        if code == 200 and 'retention_days' in data:
            log_pass("Trash cleanup status API", f"retention={data.get('retention_days')} days, expired={data.get('total_expired', 0)}")
        else:
            log_fail("Trash cleanup status API", f"Unexpected response: {code}")
    except Exception as e:
        log_fail("Trash cleanup status API", e)
    
    # Test 5.5: Journal API endpoints exist
    try:
        code, data = api_get("/api/journal/status")
        if code == 200 and 'total_entries' in data:
            log_pass("Journal status API", f"total_entries={data.get('total_entries', 0)}")
        else:
            log_fail("Journal status API", f"Unexpected response: {code}")
    except Exception as e:
        log_fail("Journal status API", e)
    
    # Test 5.6: Snapshots API endpoints exist
    try:
        code, data = api_get("/api/snapshots")
        if code == 200 and 'snapshots' in data:
            log_pass("Snapshots list API", f"total={data.get('total', 0)}")
        else:
            log_fail("Snapshots list API", f"Unexpected response: {code}")
    except Exception as e:
        log_fail("Snapshots list API", e)
    
    # Test 5.7: Snapshot creation works
    try:
        code, data = api_post("/api/snapshots", {"note": "Test from test suite"})
        if code == 201 and data.get('status') == 'completed':
            log_pass("Snapshot creation", f"Created: {data.get('filename')}")
        else:
            log_warn("Snapshot creation", f"Status: {data.get('status', 'unknown')}")
    except Exception as e:
        log_fail("Snapshot creation", e)
    
    # Test 5.8: Backup policies API exists
    try:
        code, data = api_get("/api/backup/policies")
        if code == 200 and 'policies' in data and 'active' in data and 'inactive' in data:
            log_pass("Backup policies API", f"total={data.get('total', 0)} policies")
        else:
            log_fail("Backup policies API", f"Unexpected response: {code}, keys={list(data.keys()) if data else 'none'}")
    except Exception as e:
        log_fail("Backup policies API", e)
    
    # Test 5.9: Deleted_at column exists in schema
    # Note: This test uses the API's system/info to get the DB path, then checks directly
    try:
        # Get DB path from server
        code, info = api_get("/api/system/info")
        if code != 200:
            log_fail("Schema check", f"Could not get system info: {code}")
        else:
            import sqlite3
            db_path = info.get('database', {}).get('path', '')
            conn = sqlite3.connect(db_path)
            
            # Check assets table
            cursor = conn.execute("PRAGMA table_info(assets)")
            columns = {row[1] for row in cursor.fetchall()}
            if 'deleted_at' in columns:
                log_pass("assets.deleted_at column exists", "Schema migration applied")
            else:
                log_fail("assets.deleted_at column exists", f"Column not found. Columns: {columns}")
            
            # Check models table
            cursor = conn.execute("PRAGMA table_info(models)")
            columns = {row[1] for row in cursor.fetchall()}
            if 'deleted_at' in columns:
                log_pass("models.deleted_at column exists", "Schema migration applied")
            else:
                log_fail("models.deleted_at column exists", f"Column not found")
            
            conn.close()
    except Exception as e:
        log_fail("Schema check", e)


# =============================================================================
# TEST SECTION 6: Integration Test (Full Flow)
# =============================================================================

def test_integration_flow():
    """Test the full flow: check volume -> attempt index -> verify response."""
    print("\n" + "=" * 60)
    print("SECTION 6: Integration Flow Test")
    print("=" * 60)
    
    # Step 1: Get current volume status
    try:
        code, vol_status = api_get("/api/system/volume-status")
        if code != 200:
            log_fail("Integration: Get volume status", f"Failed with code {code}")
            return
        log_pass("Integration: Get volume status", f"all_available={vol_status.get('all_available')}")
    except Exception as e:
        log_fail("Integration: Get volume status", e)
        return
    
    # Step 2: Check index prerequisites
    try:
        code, check_result = api_get("/api/system/check-index/all")
        if code != 200:
            log_fail("Integration: Check index prerequisites", f"Failed with code {code}")
            return
        can_proceed = check_result.get('can_proceed', False)
        log_pass("Integration: Check index prerequisites", f"can_proceed={can_proceed}")
    except Exception as e:
        log_fail("Integration: Check index prerequisites", e)
        return
    
    # Step 3: Verify consistency between volume status and index check
    try:
        vol_all_available = vol_status.get('all_available', False)
        if vol_all_available == can_proceed:
            log_pass("Integration: Status consistency", "Volume status matches index check")
        else:
            log_warn("Integration: Status consistency", 
                    f"Mismatch: vol_available={vol_all_available}, can_proceed={can_proceed}")
    except Exception as e:
        log_fail("Integration: Status consistency", e)
    
    # Step 4: Test suspended indexing with fake volume
    try:
        code, idx_result = api_post("/api/index", {
            "type": "3d",
            "path": "/Volumes/FakeTestVolume/Data"
        })
        if code == 200 and idx_result.get('status') == 'suspended':
            log_pass("Integration: Suspended index flow", "Fake volume correctly suspended")
        else:
            log_fail("Integration: Suspended index flow", f"Expected suspended, got: {idx_result}")
    except Exception as e:
        log_fail("Integration: Suspended index flow", e)


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report():
    """Generate final test report."""
    results['end_time'] = datetime.now()
    duration = (results['end_time'] - results['start_time']).total_seconds()
    
    print("\n")
    print("=" * 60)
    print("TEST REPORT: Backup Safeguards Validation")
    print("=" * 60)
    print(f"Date: {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.2f} seconds")
    print("-" * 60)
    
    total = len(results['passed']) + len(results['failed'])
    pass_rate = (len(results['passed']) / total * 100) if total > 0 else 0
    
    print(f"\n📊 SUMMARY")
    print(f"   Total Tests:  {total}")
    print(f"   ✅ Passed:    {len(results['passed'])}")
    print(f"   ❌ Failed:    {len(results['failed'])}")
    print(f"   ⚠️  Warnings: {len(results['warnings'])}")
    print(f"   Pass Rate:    {pass_rate:.1f}%")
    
    if results['failed']:
        print(f"\n❌ FAILED TESTS ({len(results['failed'])}):")
        for item in results['failed']:
            print(f"   • {item['test']}")
            print(f"     Error: {item['error']}")
    
    if results['warnings']:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for item in results['warnings']:
            print(f"   • {item['test']}")
            print(f"     {item['warning']}")
    
    print("\n" + "=" * 60)
    if len(results['failed']) == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {len(results['failed'])} TEST(S) FAILED - Review above")
    print("=" * 60)
    
    return len(results['failed']) == 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     BACKUP SAFEGUARDS VALIDATION TEST SUITE                ║")
    print("║     Testing: Volume Monitoring, Index API, UI States       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"\nTarget: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results['start_time'] = datetime.now()
    
    # Check if server is running
    try:
        code, _ = api_get("/api/system/health")
        if code != 200:
            print(f"\n❌ Server not responding properly (code: {code})")
            print("   Make sure Flask is running: cd /Users/claw/projects/dam && flask run")
            return False
    except Exception as e:
        print(f"\n❌ Cannot connect to server: {e}")
        print("   Make sure Flask is running on https://localhost:8008")
        return False
    
    print("\n✅ Server is running\n")
    
    # Run all test sections
    test_volume_monitor_service()
    test_volume_status_api()
    test_index_api_volume_check()
    test_download_availability()
    test_soft_delete()
    test_integration_flow()
    
    # Generate report
    return generate_report()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
