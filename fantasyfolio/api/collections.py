"""
Collections API endpoints for FantasyFolio.

Handles:
- Collection CRUD (create, read, update, delete)
- Collection items (add, remove, reorder)
- Collection sharing (with users, guest links)
"""

import json
import logging
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, request, jsonify

from fantasyfolio.api.auth import require_auth, get_current_user
from fantasyfolio.core.database import get_db, get_setting
from fantasyfolio.services.email import get_email_service
from fantasyfolio.services.email_templates import collection_share_invite_email

logger = logging.getLogger(__name__)

collections_bp = Blueprint('collections', __name__, url_prefix='/api/collections')


# ==================== Collection CRUD ====================

@collections_bp.route('', methods=['GET'])
@require_auth
def list_collections():
    """List current user's collections.
    
    Query params:
        include_shared: Include collections shared with me (default: true)
    """
    user = request.current_user
    include_shared = request.args.get('include_shared', 'true').lower() == 'true'
    
    db = get_db()
    
    # Get owned collections (flat list with parent info)
    owned = db.fetchall("""
        SELECT * FROM user_collections 
        WHERE owner_id = ? 
        ORDER BY name
    """, (user['id'],))
    
    # Get shared collections
    shared = []
    if include_shared:
        shared = db.fetchall("""
            SELECT c.*, cs.permission, u.display_name as owner_name
            FROM user_collections c
            JOIN collection_shares cs ON c.id = cs.collection_id
            JOIN users u ON c.owner_id = u.id
            WHERE cs.shared_with_user_id = ?
            ORDER BY c.updated_at DESC
        """, (user['id'],))
    
    return jsonify({
        'owned': owned,
        'shared': shared
    })


@collections_bp.route('', methods=['POST'])
@require_auth
def create_collection():
    """Create a new collection.
    
    Body:
        name: Collection name (required)
        description: Optional description
        visibility: 'private' or 'shared' (default: private)
        parent_collection_id: Parent collection for nesting (optional)
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Collection name required'}), 400
    
    parent_id = data.get('parent_collection_id')
    
    # Verify parent exists and user owns it
    if parent_id:
        db = get_db()
        parent = db.fetchone("SELECT * FROM user_collections WHERE id = ? AND owner_id = ?", 
                            (parent_id, user['id']))
        if not parent:
            return jsonify({'error': 'Parent collection not found or access denied'}), 404
    
    collection_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    db = get_db()
    with db.connection() as conn:
        conn.execute("""
            INSERT INTO user_collections (id, owner_id, name, description, visibility, parent_collection_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            collection_id,
            user['id'],
            name,
            data.get('description', '').strip() or None,
            data.get('visibility', 'private'),
            parent_id,
            now, now
        ))
        conn.commit()
    
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ?", (collection_id,))
    logger.info(f"Collection created: {name} by {user['email']}")
    
    return jsonify(collection), 201


@collections_bp.route('/<collection_id>', methods=['GET'])
@require_auth
def get_collection(collection_id):
    """Get collection details with items."""
    user = request.current_user
    db = get_db()
    
    # Get collection (check ownership or share access)
    collection = db.fetchone("""
        SELECT c.*, u.display_name as owner_name
        FROM user_collections c
        JOIN users u ON c.owner_id = u.id
        WHERE c.id = ?
    """, (collection_id,))
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    # Check access
    if collection['owner_id'] != user['id']:
        share = db.fetchone("""
            SELECT * FROM collection_shares 
            WHERE collection_id = ? AND shared_with_user_id = ?
        """, (collection_id, user['id']))
        if not share:
            return jsonify({'error': 'Access denied'}), 403
        collection = dict(collection)
        collection['permission'] = share['permission']
    
    # Get items with asset details
    items = db.fetchall("""
        SELECT ci.*, 
            CASE 
                WHEN ci.asset_type = 'model' THEN m.filename
                WHEN ci.asset_type = 'pdf' THEN a.filename
            END as filename,
            CASE 
                WHEN ci.asset_type = 'model' THEN m.format
                WHEN ci.asset_type = 'pdf' THEN 'pdf'
            END as format,
            CASE 
                WHEN ci.asset_type = 'model' THEN m.has_thumbnail
                WHEN ci.asset_type = 'pdf' THEN a.has_thumbnail
            END as has_thumbnail
        FROM collection_items ci
        LEFT JOIN models m ON ci.asset_type = 'model' AND ci.asset_id = m.id
        LEFT JOIN assets a ON ci.asset_type = 'pdf' AND ci.asset_id = a.id
        WHERE ci.collection_id = ?
        ORDER BY ci.sort_order, ci.added_at
    """, (collection_id,))
    
    result = dict(collection)
    result['items'] = items
    
    return jsonify(result)


@collections_bp.route('/<collection_id>', methods=['PATCH'])
@require_auth
def update_collection(collection_id):
    """Update collection details.
    
    Body:
        name: New name
        description: New description
        visibility: New visibility
        parent_collection_id: New parent (null to unnest)
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # Check ownership
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ? AND owner_id = ?", 
                            (collection_id, user['id']))
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    # Verify parent if being changed
    if 'parent_collection_id' in data:
        parent_id = data['parent_collection_id']
        if parent_id:  # Allow null to unnest
            parent = db.fetchone("SELECT * FROM user_collections WHERE id = ? AND owner_id = ?", 
                                (parent_id, user['id']))
            if not parent:
                return jsonify({'error': 'Parent collection not found or access denied'}), 404
            
            # Prevent circular nesting
            if parent_id == collection_id:
                return jsonify({'error': 'Cannot nest collection into itself'}), 400
    
    # Build update
    updates = {}
    if 'name' in data:
        updates['name'] = data['name'].strip()
    if 'description' in data:
        updates['description'] = data['description'].strip() or None
    if 'visibility' in data and data['visibility'] in ('private', 'shared'):
        updates['visibility'] = data['visibility']
    if 'parent_collection_id' in data:
        updates['parent_collection_id'] = data['parent_collection_id']
    
    if not updates:
        return jsonify({'error': 'No valid updates provided'}), 400
    
    updates['updated_at'] = datetime.utcnow().isoformat()
    
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    
    with db.connection() as conn:
        conn.execute(f"UPDATE user_collections SET {set_clause} WHERE id = ?", values)
        conn.commit()
    
    return get_collection(collection_id)


@collections_bp.route('/<collection_id>', methods=['DELETE'])
@require_auth
def delete_collection(collection_id):
    """Delete a collection."""
    user = request.current_user
    db = get_db()
    
    # Check ownership
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
                            (collection_id, user['id']))
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    with db.connection() as conn:
        # Items and shares cascade delete
        conn.execute("DELETE FROM user_collections WHERE id = ?", (collection_id,))
        conn.commit()
    
    logger.info(f"Collection deleted: {collection['name']} by {user['email']}")
    return jsonify({'message': 'Collection deleted'})


# ==================== Collection Items ====================

@collections_bp.route('/<collection_id>/items', methods=['POST'])
@require_auth
def add_items(collection_id):
    """Add items to a collection.
    
    Body:
        items: Array of {asset_type: 'model'|'pdf', asset_id: int}
        
    Or single item:
        asset_type: 'model' or 'pdf'
        asset_id: int
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # Check ownership or edit permission
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ?", (collection_id,))
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    can_edit = collection['owner_id'] == user['id']
    if not can_edit:
        share = db.fetchone("""
            SELECT * FROM collection_shares 
            WHERE collection_id = ? AND shared_with_user_id = ? AND permission = 'edit'
        """, (collection_id, user['id']))
        can_edit = share is not None
    
    if not can_edit:
        return jsonify({'error': 'Access denied'}), 403
    
    # Handle single item or array
    items = data.get('items', [])
    if not items and 'asset_type' in data:
        items = [{'asset_type': data['asset_type'], 'asset_id': data['asset_id']}]
    
    if not items:
        return jsonify({'error': 'No items provided'}), 400
    
    now = datetime.utcnow().isoformat()
    added = 0
    
    with db.connection() as conn:
        for item in items:
            asset_type = item.get('asset_type')
            asset_id = item.get('asset_id')
            
            if asset_type not in ('model', 'pdf') or not asset_id:
                continue
            
            try:
                item_id = str(uuid4())
                conn.execute("""
                    INSERT INTO collection_items (id, collection_id, asset_type, asset_id, added_at, added_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (item_id, collection_id, asset_type, asset_id, now, user['id']))
                added += 1
            except Exception as e:
                # Likely duplicate, skip
                if 'UNIQUE constraint' not in str(e):
                    logger.error(f"Error adding item: {e}")
        
        # Update item count
        conn.execute("""
            UPDATE user_collections SET item_count = (
                SELECT COUNT(*) FROM collection_items WHERE collection_id = ?
            ), updated_at = ? WHERE id = ?
        """, (collection_id, now, collection_id))
        conn.commit()
    
    return jsonify({'added': added})


@collections_bp.route('/<collection_id>/items/<item_id>', methods=['DELETE'])
@require_auth
def remove_item(collection_id, item_id):
    """Remove an item from a collection."""
    user = request.current_user
    db = get_db()
    
    # Check ownership or edit permission
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ?", (collection_id,))
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    can_edit = collection['owner_id'] == user['id']
    if not can_edit:
        share = db.fetchone("""
            SELECT * FROM collection_shares 
            WHERE collection_id = ? AND shared_with_user_id = ? AND permission = 'edit'
        """, (collection_id, user['id']))
        can_edit = share is not None
    
    if not can_edit:
        return jsonify({'error': 'Access denied'}), 403
    
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        conn.execute("DELETE FROM collection_items WHERE id = ? AND collection_id = ?", 
                    (item_id, collection_id))
        conn.execute("""
            UPDATE user_collections SET item_count = (
                SELECT COUNT(*) FROM collection_items WHERE collection_id = ?
            ), updated_at = ? WHERE id = ?
        """, (collection_id, now, collection_id))
        conn.commit()
    
    return jsonify({'message': 'Item removed'})


# ==================== Quick Add (by asset ID) ====================

@collections_bp.route('/quick-add', methods=['POST'])
@require_auth
def quick_add():
    """Quick add an asset to a collection (or create new collection).
    
    Body:
        asset_type: 'model' or 'pdf'
        asset_id: int
        collection_id: existing collection ID (optional)
        new_collection_name: create new collection with this name (optional)
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    asset_type = data.get('asset_type')
    asset_id = data.get('asset_id')
    
    if asset_type not in ('model', 'pdf') or not asset_id:
        return jsonify({'error': 'asset_type and asset_id required'}), 400
    
    collection_id = data.get('collection_id')
    new_name = data.get('new_collection_name', '').strip()
    
    # Create new collection if requested
    if new_name and not collection_id:
        collection_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO user_collections (id, owner_id, name, visibility, created_at, updated_at)
                VALUES (?, ?, ?, 'private', ?, ?)
            """, (collection_id, user['id'], new_name, now, now))
            conn.commit()
    
    if not collection_id:
        return jsonify({'error': 'collection_id or new_collection_name required'}), 400
    
    # Verify collection access
    collection = db.fetchone("SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
                            (collection_id, user['id']))
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    # Add item
    now = datetime.utcnow().isoformat()
    item_id = str(uuid4())
    
    try:
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO collection_items (id, collection_id, asset_type, asset_id, added_at, added_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, collection_id, asset_type, asset_id, now, user['id']))
            conn.execute("""
                UPDATE user_collections SET item_count = item_count + 1, updated_at = ? WHERE id = ?
            """, (now, collection_id))
            conn.commit()
    except Exception as e:
        if 'UNIQUE constraint' in str(e):
            return jsonify({'error': 'Item already in collection'}), 409
        raise
    
    return jsonify({
        'collection_id': collection_id,
        'collection_name': collection['name'] if collection else new_name,
        'item_id': item_id
    })


# ==================== User's Collections for an Asset ====================

@collections_bp.route('/for-asset', methods=['GET'])
@require_auth
def collections_for_asset():
    """Get which of user's collections contain a specific asset.
    
    Query params:
        asset_type: 'model' or 'pdf'
        asset_id: int
    """
    user = request.current_user
    asset_type = request.args.get('asset_type')
    asset_id = request.args.get('asset_id')
    
    if not asset_type or not asset_id:
        return jsonify({'error': 'asset_type and asset_id required'}), 400
    
    db = get_db()
    
    # Get all user's collections with flag if asset is in it
    collections = db.fetchall("""
        SELECT c.id, c.name, c.item_count,
            EXISTS(
                SELECT 1 FROM collection_items ci 
                WHERE ci.collection_id = c.id 
                AND ci.asset_type = ? AND ci.asset_id = ?
            ) as contains_asset
        FROM user_collections c
        WHERE c.owner_id = ?
        ORDER BY c.name
    """, (asset_type, asset_id, user['id']))
    
    return jsonify({'collections': collections})


# ==================== Collection Sharing ====================

@collections_bp.route('/<collection_id>/shares', methods=['GET'])
@require_auth
def list_shares(collection_id):
    """List all shares for a collection (owner only).
    
    Returns:
        - User shares (shared with specific users)
        - Guest links (public links with optional password/expiry)
    """
    user = request.current_user
    db = get_db()
    
    # Verify ownership
    collection = db.fetchone(
        "SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
        (collection_id, user['id'])
    )
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    # Get user shares
    user_shares = db.fetchall("""
        SELECT cs.*, u.email, u.display_name
        FROM collection_shares cs
        JOIN users u ON cs.shared_with_user_id = u.id
        WHERE cs.collection_id = ? AND cs.shared_with_user_id IS NOT NULL
        ORDER BY cs.created_at DESC
    """, (collection_id,))
    
    # Get guest links
    guest_links = db.fetchall("""
        SELECT * FROM collection_shares
        WHERE collection_id = ? AND guest_token_hash IS NOT NULL
        ORDER BY created_at DESC
    """, (collection_id,))
    
    return jsonify({
        'user_shares': user_shares,
        'guest_links': guest_links
    })


@collections_bp.route('/<collection_id>/share', methods=['POST'])
@require_auth
def create_share(collection_id):
    """Share a collection with a user or create a guest link.
    
    Body:
        email: Email address to share with (for user share)
        permission: 'view', 'download', or 'edit' (default: 'view')
        send_email: Send invitation email (default: true)
        
        OR for guest link:
        guest_link: true
        expires_at: Optional expiry timestamp
        password: Optional password
        max_downloads: Optional download limit
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # Verify ownership
    collection = db.fetchone(
        "SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
        (collection_id, user['id'])
    )
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    permission = data.get('permission', 'view')
    if permission not in ('view', 'download', 'edit'):
        return jsonify({'error': 'Invalid permission level'}), 400
    
    share_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    # Guest link creation
    if data.get('guest_link'):
        import secrets
        guest_token = secrets.token_urlsafe(32)
        
        # Hash the token for storage
        import hashlib
        token_hash = hashlib.sha256(guest_token.encode()).hexdigest()
        
        # Optional password
        password_hash = None
        if data.get('password'):
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            password_hash = ph.hash(data['password'])
        
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO collection_shares 
                (id, collection_id, guest_token_hash, permission, expires_at, 
                 max_downloads, password_hash, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                share_id, collection_id, token_hash, permission,
                data.get('expires_at'), data.get('max_downloads'),
                password_hash, now, user['id']
            ))
            conn.commit()  # CRITICAL: Must commit transaction!
        
        # Send email if recipient provided
        recipient_email = data.get('recipient_email')
        if recipient_email:
            try:
                email_service = get_email_service()
                if email_service.is_configured():
                    # Build full guest link URL using configured base URL
                    base_url = get_setting('app_base_url') or request.host_url.rstrip('/')
                    guest_url = f"{base_url}/shared/{guest_token}"
                    
                    # Format expiry for email
                    expires_display = None
                    if data.get('expires_at'):
                        from datetime import timezone
                        expires = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        delta = expires - now
                        if delta.days > 0:
                            expires_display = f"{delta.days} days"
                        else:
                            expires_display = "soon"
                    
                    html_body, text_body = collection_share_invite_email(
                        inviter_name=user.get('display_name') or user['email'],
                        collection_name=collection['name'],
                        collection_url=guest_url,
                        permissions=permission,
                        expiry_date=expires_display
                    )
                    
                    success = email_service.send(
                        to_address=recipient_email,
                        subject=f"{user.get('display_name', 'Someone')} shared a collection with you",
                        html_body=html_body,
                        text_body=text_body
                    )
                    
                    if success:
                        logger.info(f"✅ Guest link email sent to {recipient_email}")
                    else:
                        logger.error(f"❌ Failed to send guest link email to {recipient_email}")
            except Exception as e:
                logger.error(f"Failed to send guest link email: {e}", exc_info=True)
                # Don't fail the link creation if email fails
        
        return jsonify({
            'id': share_id,
            'guest_token': guest_token,  # Only time this is revealed
            'url': f"/shared/{guest_token}",
            'permission': permission,
            'expires_at': data.get('expires_at'),
            'max_downloads': data.get('max_downloads'),
            'has_password': bool(password_hash),
            'email_sent': bool(recipient_email)
        }), 201
    
    # User share creation
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'Email address required'}), 400
    
    # Find or invite user
    target_user = db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
    
    if not target_user:
        # TODO: Create pending invitation for non-users
        return jsonify({'error': 'User not found. Invitations coming soon.'}), 404
    
    # Check if already shared
    existing = db.fetchone("""
        SELECT * FROM collection_shares 
        WHERE collection_id = ? AND shared_with_user_id = ?
    """, (collection_id, target_user['id']))
    
    if existing:
        return jsonify({'error': 'Collection already shared with this user'}), 409
    
    # Create share
    with db.connection() as conn:
        conn.execute("""
            INSERT INTO collection_shares 
            (id, collection_id, shared_with_user_id, permission, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (share_id, collection_id, target_user['id'], permission, now, user['id']))
        conn.commit()  # CRITICAL: Must commit transaction!
    
    # Send email notification
    send_email = data.get('send_email', True)
    logger.info(f"Attempting to send share invite (send_email={send_email})")
    
    if send_email:
        try:
            email_service = get_email_service()
            logger.info(f"Email service configured: {email_service.is_configured()}")
            
            if email_service.is_configured():
                # Build full URL to collection view using configured base URL
                base_url = get_setting('app_base_url') or request.host_url.rstrip('/')
                collection_url = f"{base_url}/?view=collection&id={collection_id}"  # Direct link to collection
                
                html_body, text_body = collection_share_invite_email(
                    inviter_name=user.get('display_name') or user['email'],
                    collection_name=collection['name'],
                    collection_url=collection_url,
                    permissions=permission
                )
                
                logger.info(f"Sending share invite to {email}")
                success = email_service.send(
                    to_address=email,
                    subject=f"{user.get('display_name', 'Someone')} shared a collection with you",
                    html_body=html_body,
                    text_body=text_body
                )
                
                if success:
                    logger.info(f"✅ Share invite sent to {email} for collection {collection_id}")
                else:
                    logger.error(f"❌ Email service returned False for {email}")
            else:
                logger.warning(f"Email service not configured, skipping invite to {email}")
        except Exception as e:
            logger.error(f"Failed to send share invite email: {e}", exc_info=True)
            # Don't fail the share creation if email fails
    
    return jsonify({
        'id': share_id,
        'collection_id': collection_id,
        'shared_with': {
            'user_id': target_user['id'],
            'email': target_user['email'],
            'display_name': target_user.get('display_name')
        },
        'permission': permission,
        'created_at': now
    }), 201


@collections_bp.route('/<collection_id>/shares/<share_id>', methods=['DELETE'])
@require_auth
def revoke_share(collection_id, share_id):
    """Revoke a collection share (owner only)."""
    user = request.current_user
    db = get_db()
    
    # Verify ownership
    collection = db.fetchone(
        "SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
        (collection_id, user['id'])
    )
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    # Delete share
    with db.connection() as conn:
        cursor = conn.execute("""
            DELETE FROM collection_shares 
            WHERE id = ? AND collection_id = ?
        """, (share_id, collection_id))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Share not found'}), 404
        
        conn.commit()  # CRITICAL: Must commit transaction!
    
    logger.info(f"Share {share_id} revoked for collection {collection_id}")
    return jsonify({'success': True})


@collections_bp.route('/<collection_id>/shares/<share_id>', methods=['PATCH'])
@require_auth
def update_share(collection_id, share_id):
    """Update share permissions or settings (owner only).
    
    Body:
        permission: 'view', 'download', or 'edit'
        expires_at: Update expiry (guest links only)
        max_downloads: Update download limit (guest links only)
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # Verify ownership
    collection = db.fetchone(
        "SELECT * FROM user_collections WHERE id = ? AND owner_id = ?",
        (collection_id, user['id'])
    )
    if not collection:
        return jsonify({'error': 'Collection not found or access denied'}), 404
    
    # Get existing share
    share = db.fetchone(
        "SELECT * FROM collection_shares WHERE id = ? AND collection_id = ?",
        (share_id, collection_id)
    )
    if not share:
        return jsonify({'error': 'Share not found'}), 404
    
    # Build update
    updates = []
    params = []
    
    if 'permission' in data:
        if data['permission'] not in ('view', 'download', 'edit'):
            return jsonify({'error': 'Invalid permission level'}), 400
        updates.append("permission = ?")
        params.append(data['permission'])
    
    if 'expires_at' in data and share['guest_token_hash']:
        updates.append("expires_at = ?")
        params.append(data['expires_at'])
    
    if 'max_downloads' in data and share['guest_token_hash']:
        updates.append("max_downloads = ?")
        params.append(data['max_downloads'])
    
    if not updates:
        return jsonify({'error': 'No valid updates provided'}), 400
    
    params.extend([share_id, collection_id])
    
    with db.connection() as conn:
        conn.execute(f"""
            UPDATE collection_shares 
            SET {', '.join(updates)}
            WHERE id = ? AND collection_id = ?
        """, params)
        conn.commit()  # CRITICAL: Must commit transaction!
    
    # Get updated share
    updated_share = db.fetchone(
        "SELECT * FROM collection_shares WHERE id = ?", (share_id,)
    )
    
    logger.info(f"Share {share_id} updated for collection {collection_id}")
    return jsonify(updated_share)
