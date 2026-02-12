# Handling Slow Storage / Degraded RAID

## Issue
Upload progress hangs on degraded RAID array with slow write performance.

## Root Cause
The upload endpoint performs several **synchronous blocking operations**:
1. `file.save(file_path)` - writes to slow RAID
2. Re-reads entire file to compute MD5 hash
3. For ZIP files: extraction and indexing
4. Database operations

On slow storage, a 2.8MB file can take minutes to process.

## Current Fix (v0.4.10)
Added 5-minute timeout to frontend XMLHttpRequest:
- Shows warning message after timeout
- UI remains responsive
- Backend continues processing in background

## Recommended Solutions

### 1. **Two-Stage Upload** (Quick Win - 2 hours)
Upload to fast staging directory first, then move/process:

```python
# Stage 1: Fast upload to /tmp or local SSD
staging_path = '/tmp/uploads'
file.save(staging_path)  # Fast write

# Return immediately with upload_id
return jsonify({'status': 'staged', 'upload_id': upload_id})

# Stage 2: Background job moves to final destination
# - Copy to slow RAID
# - Compute hash
# - Index in database
```

### 2. **Background Job Queue** (Robust - 4 hours)
Use task queue (Celery, RQ, or simple threading):

```python
from queue import Queue
import threading

upload_queue = Queue()

def process_upload_worker():
    while True:
        job = upload_queue.get()
        process_upload(job)
        upload_queue.task_done()

# Start worker thread on app startup
threading.Thread(target=process_upload_worker, daemon=True).start()

@app.route('/api/upload')
def upload():
    # Quick save to staging
    staging_path = save_to_staging(file)
    
    # Queue for background processing
    job_id = uuid.uuid4()
    upload_queue.put({
        'id': job_id,
        'staging_path': staging_path,
        'destination': final_path
    })
    
    return jsonify({'status': 'queued', 'job_id': job_id})

@app.route('/api/upload/status/<job_id>')
def upload_status(job_id):
    # Frontend polls for completion
    return jsonify({'status': 'processing|complete|failed'})
```

### 3. **Streaming Upload** (Advanced - 6 hours)
Stream directly to final location with progress updates:

```python
from flask import stream_with_context, Response

@app.route('/api/upload/stream')
def upload_stream():
    def generate():
        # Stream chunks as they're written
        for chunk in request.stream:
            write_chunk(chunk)
            yield json.dumps({'progress': percent}) + '\n'
        
        # Compute hash incrementally (no re-read)
        yield json.dumps({'status': 'complete'}) + '\n'
    
    return Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson'
    )
```

### 4. **Skip MD5 on Upload** (Quick - 30 min)
Defer hash computation to background indexer:

```python
# Upload: Just save file, insert placeholder
file.save(file_path)
insert_model({
    'file_path': file_path,
    'file_hash': None,  # Compute later
    'needs_hash': True
})

# Background cron: Compute hashes for files with needs_hash=True
```

## Production Recommendations

### For Current Setup (Degraded RAID)
1. ✅ Use 5-minute timeout (already implemented)
2. **Mount options**: Use `async` mount flag for /content if possible
3. **Separate staging**: Upload to `/app/uploads` (local SSD), then background copy
4. **Batch processing**: Index multiple uploads in one pass

### For Future (Post-RAID Repair)
1. Keep two-stage upload (fast feedback)
2. Background job queue for robustness
3. Consider object storage (S3, MinIO) for uploads

### Docker-Specific
Current mounts are direct to slow RAID:
```bash
-v /Volumes/d-mini/ff-testing/3D:/content/3d-models
-v /Volumes/d-mini/ff-testing/PDF:/content/pdfs
```

Add staging volume on faster storage:
```bash
-v /Users/claw/projects/dam/staging:/app/staging  # Local SSD
```

Then move files from staging to final location in background.

## Testing with Slow Storage

### Verify Upload Completion
Even if UI times out, check if file actually finished:

```bash
# Watch for new files
docker exec fantasyfolio-test watch -n 1 ls -lht /content/3d-models/Upload-test1/

# Check logs for errors
docker logs fantasyfolio-test -f | grep -i error

# Monitor disk I/O
iostat -x 1  # On host
```

### Expected Behavior (v0.4.10)
- Upload progress shows during network transfer
- After 5 minutes: timeout message appears
- File may still be writing to RAID in background
- Refresh page to see if file appeared

## Cost/Benefit Analysis

| Solution | Effort | User Experience | Storage Impact |
|----------|--------|-----------------|----------------|
| Current (timeout) | ✅ Done | Warning after 5min | None |
| Two-stage upload | 2 hours | Instant feedback | Needs staging space |
| Background queue | 4 hours | Best (with polling UI) | Needs staging space |
| Skip MD5 | 30 min | Faster upload | Deferred hashing |
| Streaming | 6 hours | Real-time progress | None |

## Recommendation for v0.4.11
Implement **Two-Stage Upload** (Solution #1):
- Low effort (2 hours)
- Significant UX improvement
- Works with current degraded RAID
- Easy to test and rollback

**Implementation order:**
1. Add `/app/staging` directory
2. Modify upload endpoint to save to staging
3. Return immediately with upload ID
4. Background thread copies to final destination
5. Frontend polls `/api/upload/status/<id>` for completion
