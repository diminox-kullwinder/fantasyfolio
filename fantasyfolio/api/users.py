"""
User Management API for FantasyFolio.

Admin endpoints for listing and managing users.
"""

import logging
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, request, jsonify
from argon2 import PasswordHasher

from fantasyfolio.api.auth import require_auth
from fantasyfolio.core.database import get_db

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


@users_bp.route('', methods=['GET'])
@require_auth
def list_users():
    """
    List all users (admin/GM only in future, for now any authenticated user).
    
    Query params:
        search: Filter by email or display_name
        role: Filter by role
        limit: Max results (default: 100)
    """
    user = request.current_user
    db = get_db()
    
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role')
    limit = int(request.args.get('limit', 100))
    
    # Build query
    query = "SELECT id, email, email_verified, display_name, avatar_url, role, created_at, last_login_at, is_active FROM users"
    params = []
    conditions = []
    
    if search:
        conditions.append("(email LIKE ? OR display_name LIKE ?)")
        params.extend([f'%{search}%', f'%{search}%'])
    
    if role_filter:
        conditions.append("role = ?")
        params.append(role_filter)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    users = db.fetchall(query, tuple(params))
    
    return jsonify({'users': users, 'total': len(users)})


@users_bp.route('', methods=['POST'])
@require_auth
def create_user():
    """
    Create a new user (admin only in future).
    
    Body:
        email: Email address (required)
        password: Password (required if not OAuth-only)
        display_name: Display name
        role: Role (admin, gm, player, guest) - default: player
    """
    user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    display_name = data.get('display_name', '').strip()
    role = data.get('role', 'player')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    # Check if user already exists
    existing = db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        return jsonify({'error': 'User already exists with this email'}), 409
    
    # Hash password if provided
    password_hash = None
    if password:
        ph = PasswordHasher()
        password_hash = ph.hash(password)
    
    # Create user
    user_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        conn.execute("""
            INSERT INTO users (id, email, email_verified, password_hash, display_name, role, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, 1, password_hash, display_name or email.split('@')[0], role, now, 1))
        conn.commit()
    
    logger.info(f"User created: {email} by {user['email']}")
    
    return jsonify({
        'id': user_id,
        'email': email,
        'display_name': display_name or email.split('@')[0],
        'role': role,
        'created_at': now
    }), 201


@users_bp.route('/<user_id>', methods=['PATCH'])
@require_auth
def update_user(user_id):
    """
    Update user details (admin only in future, or self).
    
    Body:
        display_name: New display name
        role: New role (admin only)
        is_active: Active status (admin only)
    """
    current_user = request.current_user
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # Get target user
    target_user = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Build updates
    updates = []
    params = []
    
    if 'display_name' in data:
        updates.append("display_name = ?")
        params.append(data['display_name'])
    
    if 'role' in data:
        # TODO: Check if current user is admin
        updates.append("role = ?")
        params.append(data['role'])
    
    if 'is_active' in data:
        # TODO: Check if current user is admin
        updates.append("is_active = ?")
        params.append(1 if data['is_active'] else 0)
    
    if not updates:
        return jsonify({'error': 'No updates provided'}), 400
    
    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(user_id)
    
    with db.connection() as conn:
        conn.execute(f"""
            UPDATE users 
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        conn.commit()
    
    # Get updated user
    updated_user = db.fetchone("SELECT id, email, display_name, role, is_active FROM users WHERE id = ?", (user_id,))
    
    logger.info(f"User updated: {target_user['email']} by {current_user['email']}")
    return jsonify(updated_user)


@users_bp.route('/<user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id):
    """
    Delete/deactivate a user (admin only).
    
    Soft delete - sets is_active to 0.
    """
    current_user = request.current_user
    db = get_db()
    
    # Get target user
    target_user = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Can't delete self
    if user_id == current_user['id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    # Soft delete
    with db.connection() as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
    
    logger.info(f"User deactivated: {target_user['email']} by {current_user['email']}")
    return jsonify({'success': True})
