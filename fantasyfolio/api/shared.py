"""
Shared/Guest Link API endpoints for FantasyFolio.

Public routes for accessing collections via guest tokens (no authentication required).
"""

import hashlib
import io
import logging
import zipfile
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template_string, send_file
from pathlib import Path

from fantasyfolio.core.database import get_db

logger = logging.getLogger(__name__)

shared_bp = Blueprint('shared', __name__, url_prefix='/shared')


# Simple embedded template for guest access
GUEST_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ collection.name }} - Shared Collection</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    :root {
      --bg-primary: #1a1a2e;
      --bg-secondary: #16213e;
      --bg-card: rgba(255,255,255,0.05);
      --text-primary: #e4e4e4;
      --text-secondary: #888;
      --accent: #4dabf7;
      --border: rgba(255,255,255,0.1);
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
      color: var(--text-primary);
      min-height: 100vh;
      padding: 20px;
    }
    
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    
    .header {
      background: var(--bg-card);
      padding: 24px;
      border-radius: 12px;
      margin-bottom: 24px;
      border: 1px solid var(--border);
    }
    
    .header h1 {
      font-size: 2rem;
      margin-bottom: 8px;
      color: var(--accent);
    }
    
    .header p {
      color: var(--text-secondary);
    }
    
    .info-bar {
      display: flex;
      gap: 24px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      font-size: 0.9rem;
    }
    
    .info-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    }
    
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      transition: all 0.2s;
      cursor: pointer;
    }
    
    .card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
      box-shadow: 0 4px 12px rgba(77, 171, 247, 0.2);
    }
    
    .card-thumb {
      width: 100%;
      aspect-ratio: 1;
      background: var(--bg-secondary);
      border-radius: 4px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 3rem;
    }
    
    .card-thumb img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    
    .card-name {
      font-size: 0.9rem;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .card-type {
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-top: 4px;
    }
    
    .password-form {
      max-width: 400px;
      margin: 100px auto;
      background: var(--bg-card);
      padding: 32px;
      border-radius: 12px;
      border: 1px solid var(--border);
    }
    
    .password-form h2 {
      margin-bottom: 16px;
      color: var(--accent);
    }
    
    .password-form input {
      width: 100%;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg-secondary);
      color: var(--text-primary);
      font-size: 1rem;
      margin-bottom: 16px;
    }
    
    .password-form button {
      width: 100%;
      padding: 12px;
      background: var(--accent);
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    
    .password-form button:hover {
      background: #74c0fc;
    }
    
    .error {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 16px;
    }
    
    .empty {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-secondary);
    }
    
    .download-btn {
      background: var(--accent);
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: all 0.2s;
      margin-left: auto;
    }
    
    .download-btn:hover {
      background: #74c0fc;
    }
  </style>
</head>
<body>
  <div class="container">
    {% if password_required and not password_valid %}
      <form class="password-form" method="POST">
        <h2>🔒 Password Required</h2>
        {% if error %}
          <div class="error">{{ error }}</div>
        {% endif %}
        <input type="password" name="password" placeholder="Enter password" autofocus required>
        <button type="submit">Unlock</button>
      </form>
    {% else %}
      <div class="header">
        <h1>📁 {{ collection.name }}</h1>
        {% if collection.description %}
          <p>{{ collection.description }}</p>
        {% endif %}
        <div class="info-bar">
          <div class="info-item">
            <span>📊</span>
            <span>{{ items|length }} items</span>
          </div>
          <div class="info-item">
            <span>👁️</span>
            <span>{{ permission }} access</span>
          </div>
          {% if expires_at %}
          <div class="info-item">
            <span>⏰</span>
            <span>Expires {{ expires_at }}</span>
          </div>
          {% endif %}
          {% if can_download %}
            <button class="download-btn" onclick="alert('Bulk download coming soon')">⬇️ Download All</button>
          {% endif %}
        </div>
      </div>
      
      {% if items %}
      <div class="grid">
        {% for item in items %}
        <div class="card" onclick="viewItem('{{ item.asset_type }}', {{ item.asset_id }}, '{{ token }}')">
          <div class="card-thumb">
            {% if item.has_thumbnail %}
              {% if item.asset_type == 'model' %}
                <img src="/api/models/{{ item.asset_id }}/preview" alt="{{ item.filename }}" onerror="this.parentElement.innerHTML='🎲'">
              {% else %}
                <img src="/api/thumbnail/{{ item.asset_db_id }}" alt="{{ item.filename }}" onerror="this.parentElement.innerHTML='📄'">
              {% endif %}
            {% elif item.asset_type == 'model' %}
              🎲
            {% else %}
              📄
            {% endif %}
          </div>
          <div class="card-name">{{ item.filename or 'Untitled' }}</div>
          <div class="card-type">{{ item.asset_type }}</div>
        </div>
        {% endfor %}
      </div>
      {% else %}
      <div class="empty">
        <p>This collection is empty.</p>
      </div>
      {% endif %}
    {% endif %}
  </div>
  
  <script>
    function viewItem(type, id, token) {
      const canDownload = {{ 'true' if can_download else 'false' }};
      if (canDownload) {
        // Download the file
        const url = `/shared/${token}/download/${type}/${id}`;
        window.open(url, '_blank');
      } else {
        alert('View-only access - downloads not permitted with this link');
      }
    }
  </script>
</body>
</html>
"""


@shared_bp.route('/<token>', methods=['GET', 'POST'])
def access_shared_collection(token):
    """
    Access a shared collection via guest token.
    
    No authentication required. Validates:
    - Token hash
    - Expiry
    - Password (if set)
    - Download limits (if set)
    """
    db = get_db()
    
    # Hash the token to find the share
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    share = db.fetchone("""
        SELECT * FROM collection_shares 
        WHERE guest_token_hash = ?
    """, (token_hash,))
    
    if not share:
        return "Invalid or expired link", 404
    
    # Check expiry
    if share['expires_at']:
        expires = datetime.fromisoformat(share['expires_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if now > expires:
            return "This link has expired", 410
    
    # Check download limit
    if share['max_downloads'] and share['download_count'] >= share['max_downloads']:
        return "Download limit reached", 403
    
    # Password check
    password_required = bool(share['password_hash'])
    password_valid = False
    error = None
    
    if password_required:
        if request.method == 'POST':
            password = request.form.get('password', '')
            
            try:
                from argon2 import PasswordHasher
                from argon2.exceptions import VerifyMismatchError
                
                ph = PasswordHasher()
                ph.verify(share['password_hash'], password)
                password_valid = True
            except VerifyMismatchError:
                error = "Incorrect password"
            except Exception as e:
                logger.error(f"Password verification error: {e}")
                error = "Authentication error"
        
        if not password_valid:
            return render_template_string(
                GUEST_TEMPLATE,
                password_required=True,
                password_valid=False,
                error=error
            )
    
    # Get collection
    collection = db.fetchone("""
        SELECT * FROM user_collections 
        WHERE id = ?
    """, (share['collection_id'],))
    
    if not collection:
        return "Collection not found", 404
    
    # Get collection items with thumbnail info (both PDFs and 3D models)
    items = db.fetchall("""
        SELECT ci.asset_type, ci.asset_id, ci.sort_order, ci.added_at,
               COALESCE(a.filename, m.filename) as filename,
               COALESCE(a.thumbnail_path, m.preview_image) as thumbnail_path,
               COALESCE(a.has_thumbnail, m.has_thumbnail, 0) as has_thumbnail,
               COALESCE(a.id, m.id) as asset_db_id
        FROM collection_items ci
        LEFT JOIN assets a ON ci.asset_type = 'pdf' AND ci.asset_id = a.id
        LEFT JOIN models m ON ci.asset_type = 'model' AND ci.asset_id = m.id
        WHERE ci.collection_id = ?
        ORDER BY ci.sort_order, ci.added_at
    """, (collection['id'],))
    
    # Update access timestamp
    with db.connection() as conn:
        conn.execute("""
            UPDATE collection_shares 
            SET last_accessed_at = ?
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), share['id']))
    
    # Format expiry for display
    expires_display = None
    if share['expires_at']:
        expires = datetime.fromisoformat(share['expires_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = expires - now
        if delta.days > 0:
            expires_display = f"in {delta.days} days"
        elif delta.seconds > 3600:
            expires_display = f"in {delta.seconds // 3600} hours"
        else:
            expires_display = "soon"
    
    return render_template_string(
        GUEST_TEMPLATE,
        password_required=password_required,
        password_valid=True,
        collection=collection,
        items=items,
        permission=share['permission'],
        can_download=share['permission'] in ('download', 'edit'),
        expires_at=expires_display,
        token=token,
        error=None
    )


@shared_bp.route('/<token>/download/<asset_type>/<int:asset_id>')
def download_shared_asset(token, asset_type, asset_id):
    """Download an asset from a shared collection (if permission allows)."""
    db = get_db()
    
    # Validate token and permission
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    share = db.fetchone("""
        SELECT * FROM collection_shares 
        WHERE guest_token_hash = ?
    """, (token_hash,))
    
    if not share:
        return "Invalid link", 404
    
    if share['permission'] not in ('download', 'edit'):
        return "Download not allowed with this link", 403
    
    # Check expiry
    if share['expires_at']:
        expires = datetime.fromisoformat(share['expires_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if now > expires:
            return "Link expired", 410
    
    # Get asset info from the correct table
    if asset_type == 'pdf':
        asset = db.fetchone("SELECT * FROM assets WHERE id = ?", (asset_id,))
    elif asset_type == 'model':
        asset = db.fetchone("""
            SELECT id, filename, file_path, archive_path, archive_member 
            FROM models WHERE id = ?
        """, (asset_id,))
    else:
        return "Invalid asset type", 400
    
    if not asset:
        return "Asset not found", 404
    
    # Increment download count
    with db.connection() as conn:
        conn.execute("""
            UPDATE collection_shares 
            SET download_count = download_count + 1
            WHERE id = ?
        """, (share['id'],))
        conn.commit()
    
    # Serve the file (handle both regular files and archive members)
    try:
        # For 3D models in archives (zipped files)
        if asset_type == 'model' and asset.get('archive_path') and asset.get('archive_member'):
            archive_path = Path(asset['archive_path'])
            if not archive_path.exists():
                return f"Archive file not found: {asset['archive_path']}", 404
            
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    data = zf.read(asset['archive_member'])
                return send_file(
                    io.BytesIO(data),
                    as_attachment=True,
                    download_name=asset['filename'],
                    mimetype='application/octet-stream'
                )
            except KeyError:
                return f"File '{asset['archive_member']}' not found in archive", 404
            except zipfile.BadZipFile:
                return f"Archive file is corrupted: {asset['archive_path']}", 500
        
        # Regular file (not in archive)
        file_path = Path(asset['file_path'])
        if not file_path.exists():
            return f"File not found: {asset['file_path']}", 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=asset['filename']
        )
    except Exception as e:
        logger.error(f"Failed to serve file {asset_type}/{asset_id}: {e}")
        return f"Failed to download file: {str(e)}", 500
