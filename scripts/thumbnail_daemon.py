#!/usr/bin/env python3
"""
Thumbnail Rendering Daemon (v2 - Tiered Processing).

Two parallel pools based on file size:
- Fast lane: Files < 30MB, 28 workers, high throughput
- Slow lane: Files > 30MB, 4 workers, dedicated for large files

This prevents large files from blocking the queue.
"""

import os
import sys
import logging
import time
import signal
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Thread
from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env.local to get DAM_DATABASE_PATH and other config
env_local = Path(__file__).parent.parent / '.env.local'
if env_local.exists():
    load_dotenv(env_local)

from dam.config import get_config
from dam.core.database import get_connection, get_model_by_id

# Logging
log_file = Path(__file__).parent.parent / 'logs' / 'thumbnail_daemon.log'
log_file.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

shutdown = Event()

# Configuration
SIZE_THRESHOLD_MB = 30  # Files above this go to slow lane
FAST_WORKERS = 12
SLOW_WORKERS = 2
FAST_BATCH = 100
SLOW_BATCH = 10
FAST_TIMEOUT = 120  # 2 min for small files
SLOW_TIMEOUT = 600  # 10 min for large files
CHECK_INTERVAL = 5  # seconds between batch checks


def signal_handler(sig, frame):
    logger.info("Shutdown signal received")
    shutdown.set()


def render_one(model_id: int, timeout_sec: int = 120) -> bool:
    """Render a single model's thumbnail."""
    import tempfile
    import zipfile
    
    try:
        config = get_config()
        model = get_model_by_id(model_id)
        
        if not model:
            return False
        
        # Check cache
        cached = config.THUMBNAIL_DIR / "3d" / f"{model_id}.png"
        if cached.exists():
            return True
        
        fmt = model.get('format', '').lower()
        if fmt not in ('stl', 'obj', '3mf'):
            return True
        
        # Prepare model file for rendering
        model_file = None
        temp_file = None
        
        if model.get('archive_path') and model.get('archive_member'):
            # Extract from ZIP to temp file
            archive_path = Path(model['archive_path'])
            if not archive_path.exists():
                return False
            
            try:
                with tempfile.NamedTemporaryFile(suffix=f'.{fmt}', delete=False) as tf:
                    temp_file = tf.name
                    with zipfile.ZipFile(archive_path, 'r') as zf:
                        data = zf.read(model['archive_member'])
                        tf.write(data)
                model_file = temp_file
            except Exception:
                return False
        
        elif model.get('file_path'):
            file_path = Path(model['file_path'])
            if file_path.exists():
                model_file = str(file_path)
            else:
                return False
        
        if not model_file:
            return False
        
        # Render using stl-thumb
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ['stl-thumb', '-s', '512', model_file, str(cached)],
                capture_output=True,
                timeout=timeout_sec
            )
            if result.returncode == 0:
                # Update database
                try:
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE models SET has_thumbnail = 1 WHERE id = ?",
                            (model_id,)
                        )
                        conn.commit()
                except Exception as e:
                    logger.error(f"DB update failed for {model_id}: {e}")
                return True
            else:
                return False
        except subprocess.TimeoutExpired:
            logger.warning(f"✗ {model_id}: timeout after {timeout_sec}s")
            return False
        except FileNotFoundError:
            logger.error("stl-thumb not installed")
            return False
        finally:
            if temp_file:
                Path(temp_file).unlink(missing_ok=True)
    
    except Exception as e:
        logger.error(f"Model {model_id}: {e}")
        return False


def get_pending_by_size(config):
    """Get pending models partitioned by file size."""
    threshold_bytes = SIZE_THRESHOLD_MB * 1024 * 1024
    
    fast_queue = []
    slow_queue = []
    
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, file_size FROM models 
            WHERE format IN ('stl', 'obj', '3mf')
            ORDER BY file_size ASC
        """).fetchall()
    
    for row in rows:
        model_id = row['id']
        file_size = row['file_size'] or 0
        
        thumb = config.THUMBNAIL_DIR / "3d" / f"{model_id}.png"
        if not thumb.exists():
            if file_size < threshold_bytes:
                fast_queue.append(model_id)
            else:
                slow_queue.append(model_id)
    
    return fast_queue, slow_queue


def process_batch(executor, queue, batch_size, timeout, lane_name):
    """Process a batch of models and return results."""
    if not queue:
        return 0, 0, []
    
    batch = queue[:batch_size]
    futures = {executor.submit(render_one, mid, timeout): mid for mid in batch}
    
    done, failed = 0, 0
    completed_ids = []
    
    try:
        for future in as_completed(futures, timeout=timeout + 60):
            model_id = futures[future]
            try:
                if future.result():
                    done += 1
                    completed_ids.append(model_id)
                    # Get filename for logging
                    model = get_model_by_id(model_id)
                    if model:
                        logger.info(f"✓ [{lane_name}] {model_id}: {model['filename']}")
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.debug(f"✗ [{lane_name}] {model_id}: {e}")
    except Exception as e:
        logger.error(f"[{lane_name}] Batch error: {e}")
    
    return done, failed, completed_ids


def run_fast_lane(config):
    """Fast lane worker - processes small files."""
    logger.info(f"[FAST] Starting with {FAST_WORKERS} workers, batch {FAST_BATCH}, timeout {FAST_TIMEOUT}s")
    
    with ThreadPoolExecutor(max_workers=FAST_WORKERS) as executor:
        iteration = 0
        while not shutdown.is_set():
            iteration += 1
            
            fast_queue, _ = get_pending_by_size(config)
            
            if fast_queue:
                logger.info(f"[FAST #{iteration}] {len(fast_queue)} pending (< {SIZE_THRESHOLD_MB}MB)")
                done, failed, _ = process_batch(
                    executor, fast_queue, FAST_BATCH, FAST_TIMEOUT, "FAST"
                )
                logger.info(f"[FAST #{iteration}] Done: {done} ✓, {failed} ✗")
            else:
                logger.info(f"[FAST #{iteration}] Queue empty - fast lane complete")
            
            if shutdown.wait(CHECK_INTERVAL):
                break
    
    logger.info("[FAST] Lane stopped")


def run_slow_lane(config):
    """Slow lane worker - processes large files."""
    logger.info(f"[SLOW] Starting with {SLOW_WORKERS} workers, batch {SLOW_BATCH}, timeout {SLOW_TIMEOUT}s")
    
    with ThreadPoolExecutor(max_workers=SLOW_WORKERS) as executor:
        iteration = 0
        while not shutdown.is_set():
            iteration += 1
            
            _, slow_queue = get_pending_by_size(config)
            
            if slow_queue:
                logger.info(f"[SLOW #{iteration}] {len(slow_queue)} pending (> {SIZE_THRESHOLD_MB}MB)")
                done, failed, _ = process_batch(
                    executor, slow_queue, SLOW_BATCH, SLOW_TIMEOUT, "SLOW"
                )
                logger.info(f"[SLOW #{iteration}] Done: {done} ✓, {failed} ✗")
            else:
                logger.info(f"[SLOW #{iteration}] Queue empty - slow lane complete")
            
            if shutdown.wait(CHECK_INTERVAL * 2):  # Check less frequently for slow lane
                break
    
    logger.info("[SLOW] Lane stopped")


def main():
    """Main daemon with parallel fast/slow lanes."""
    logger.info("=" * 60)
    logger.info("Thumbnail daemon v2 (Tiered Processing) starting")
    logger.info(f"  Fast lane: {FAST_WORKERS} workers, < {SIZE_THRESHOLD_MB}MB files")
    logger.info(f"  Slow lane: {SLOW_WORKERS} workers, > {SIZE_THRESHOLD_MB}MB files")
    logger.info("=" * 60)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    config = get_config()
    
    # Get initial counts
    fast_queue, slow_queue = get_pending_by_size(config)
    logger.info(f"Initial queue: {len(fast_queue)} fast + {len(slow_queue)} slow = {len(fast_queue) + len(slow_queue)} total")
    
    # Start both lanes as parallel threads
    fast_thread = Thread(target=run_fast_lane, args=(config,), name="FastLane")
    slow_thread = Thread(target=run_slow_lane, args=(config,), name="SlowLane")
    
    fast_thread.start()
    slow_thread.start()
    
    # Wait for shutdown or completion
    while not shutdown.is_set():
        if not fast_thread.is_alive() and not slow_thread.is_alive():
            logger.info("Both lanes completed")
            break
        shutdown.wait(10)
    
    # Wait for threads to finish
    fast_thread.join(timeout=30)
    slow_thread.join(timeout=30)
    
    logger.info("Daemon stopped")


if __name__ == '__main__':
    main()
