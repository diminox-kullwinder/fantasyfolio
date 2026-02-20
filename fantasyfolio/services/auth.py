"""
Authentication service for FantasyFolio.

Handles:
- Password hashing (argon2)
- JWT token generation/validation
- Session management
- Email token generation (verify, reset)
- OAuth state management
"""

import os
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False
    logger.warning("argon2-cffi not installed, using fallback password hashing")

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("PyJWT not installed, token features disabled")


# ==================== Configuration ====================

class AuthConfig:
    """Auth configuration with sensible defaults."""
    
    def __init__(self):
        self.jwt_secret = os.environ.get('JWT_SECRET', 'CHANGE_ME_IN_PRODUCTION_' + secrets.token_hex(16))
        self.jwt_algorithm = 'HS256'
        self.access_token_expiry_minutes = 15
        self.refresh_token_expiry_days = 7
        self.email_token_expiry_hours = 24
        self.password_reset_expiry_hours = 1
        
        # OAuth providers (loaded from env)
        self.discord_client_id = os.environ.get('DISCORD_CLIENT_ID', '')
        self.discord_client_secret = os.environ.get('DISCORD_CLIENT_SECRET', '')
        self.discord_redirect_uri = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:8008/api/auth/oauth/discord/callback')
        
        self.google_client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        self.google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
        self.google_redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:8008/api/auth/oauth/google/callback')
        
        self.apple_client_id = os.environ.get('APPLE_CLIENT_ID', '')
        self.apple_team_id = os.environ.get('APPLE_TEAM_ID', '')
        self.apple_key_id = os.environ.get('APPLE_KEY_ID', '')
        self.apple_redirect_uri = os.environ.get('APPLE_REDIRECT_URI', 'http://localhost:8008/api/auth/oauth/apple/callback')
        
        if 'CHANGE_ME' in self.jwt_secret:
            logger.warning("⚠️  Using auto-generated JWT secret. Set JWT_SECRET env var for production!")


_config: Optional[AuthConfig] = None

def get_auth_config() -> AuthConfig:
    global _config
    if _config is None:
        _config = AuthConfig()
    return _config


# ==================== Password Hashing ====================

if ARGON2_AVAILABLE:
    _hasher = PasswordHasher()
    
    def hash_password(password: str) -> str:
        """Hash a password using Argon2id."""
        return _hasher.hash(password)
    
    def verify_password(password: str, hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            _hasher.verify(hash, password)
            return True
        except VerifyMismatchError:
            return False
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
else:
    # Fallback to SHA-256 with salt (less secure but functional)
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256 with random salt (fallback)."""
        salt = secrets.token_hex(16)
        hash_val = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"sha256${salt}${hash_val}"
    
    def verify_password(password: str, hash: str) -> bool:
        """Verify a password against its hash (fallback)."""
        try:
            parts = hash.split('$')
            if len(parts) != 3 or parts[0] != 'sha256':
                return False
            salt, stored_hash = parts[1], parts[2]
            computed = hashlib.sha256((salt + password).encode()).hexdigest()
            return secrets.compare_digest(computed, stored_hash)
        except Exception:
            return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate password meets requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least 1 uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least 1 lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least 1 number"
    return True, ""


# ==================== JWT Tokens ====================

def generate_access_token(user_id: str, role: str, email: str) -> str:
    """Generate a short-lived access token."""
    if not JWT_AVAILABLE:
        raise RuntimeError("PyJWT not installed")
    
    config = get_auth_config()
    now = datetime.utcnow()
    
    payload = {
        'sub': user_id,
        'role': role,
        'email': email,
        'type': 'access',
        'iat': now,
        'exp': now + timedelta(minutes=config.access_token_expiry_minutes)
    }
    
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


def generate_refresh_token() -> str:
    """Generate a secure random refresh token."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode an access token.
    
    Returns:
        Decoded payload if valid, None otherwise
    """
    if not JWT_AVAILABLE:
        return None
    
    config = get_auth_config()
    
    try:
        payload = jwt.decode(
            token, 
            config.jwt_secret, 
            algorithms=[config.jwt_algorithm]
        )
        if payload.get('type') != 'access':
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return None


# ==================== Email Tokens ====================

def generate_email_token() -> str:
    """Generate a secure token for email verification/reset."""
    return secrets.token_urlsafe(32)


def hash_email_token(token: str) -> str:
    """Hash an email token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ==================== OAuth State ====================

# In-memory state store (replace with Redis for production)
_oauth_states: Dict[str, Dict[str, Any]] = {}


def generate_oauth_state(provider: str, redirect_to: Optional[str] = None) -> str:
    """Generate and store OAuth state parameter."""
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        'provider': provider,
        'redirect_to': redirect_to,
        'created_at': datetime.utcnow().isoformat()
    }
    # Clean old states (>10 minutes)
    _cleanup_old_states()
    return state


def verify_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Verify OAuth state and return stored data."""
    data = _oauth_states.pop(state, None)
    if data is None:
        return None
    
    # Check age (max 10 minutes)
    created = datetime.fromisoformat(data['created_at'])
    if datetime.utcnow() - created > timedelta(minutes=10):
        return None
    
    return data


def _cleanup_old_states():
    """Remove OAuth states older than 10 minutes."""
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    old_keys = [
        k for k, v in _oauth_states.items()
        if datetime.fromisoformat(v['created_at']) < cutoff
    ]
    for k in old_keys:
        _oauth_states.pop(k, None)


# ==================== User ID Generation ====================

def generate_user_id() -> str:
    """Generate a unique user ID."""
    return str(uuid4())


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid4())


# ==================== Database Operations ====================

from fantasyfolio.core.database import get_db


def create_user(
    email: str,
    password: Optional[str] = None,
    display_name: Optional[str] = None,
    role: str = 'player'
) -> Optional[Dict[str, Any]]:
    """Create a new user with email/password.
    
    Args:
        email: User's email address
        password: Password (optional for SSO-only users)
        display_name: Display name (defaults to email prefix)
        role: User role (admin, gm, player, guest)
    
    Returns:
        User dict if created, None if email already exists
    """
    db = get_db()
    user_id = generate_user_id()
    now = datetime.utcnow().isoformat()
    
    # Default display name to email prefix
    if not display_name:
        display_name = email.split('@')[0]
    
    # Hash password if provided
    password_hash = hash_password(password) if password else None
    
    try:
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO users (id, email, password_hash, display_name, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, email.lower(), password_hash, display_name, role, now, now))
            conn.commit()
        
        return get_user_by_id(user_id)
    
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            logger.info(f"User already exists: {email}")
            return None
        raise


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    return get_db().fetchone("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email address."""
    return get_db().fetchone("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.lower(),))


def update_user(user_id: str, **updates) -> bool:
    """Update user fields."""
    db = get_db()
    allowed_fields = {'display_name', 'avatar_url', 'role', 'email_verified', 'last_login_at'}
    
    fields = {k: v for k, v in updates.items() if k in allowed_fields}
    if not fields:
        return False
    
    fields['updated_at'] = datetime.utcnow().isoformat()
    
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    
    with db.connection() as conn:
        cursor = conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def update_password(user_id: str, new_password: str) -> bool:
    """Update user's password."""
    db = get_db()
    password_hash = hash_password(new_password)
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, now, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# ==================== Session Operations ====================

def create_session(
    user_id: str,
    refresh_token: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """Create a new user session.
    
    Returns:
        Session ID
    """
    db = get_db()
    config = get_auth_config()
    session_id = generate_session_id()
    now = datetime.utcnow()
    expires_at = now + timedelta(days=config.refresh_token_expiry_days)
    
    with db.connection() as conn:
        conn.execute("""
            INSERT INTO user_sessions 
            (id, user_id, refresh_token_hash, device_info, ip_address, user_agent, created_at, expires_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, user_id, hash_refresh_token(refresh_token),
            device_info, ip_address, user_agent,
            now.isoformat(), expires_at.isoformat(), now.isoformat()
        ))
        conn.commit()
    
    return session_id


def get_session_by_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """Get session by refresh token (validates expiry and revocation)."""
    db = get_db()
    token_hash = hash_refresh_token(refresh_token)
    now = datetime.utcnow().isoformat()
    
    return db.fetchone("""
        SELECT * FROM user_sessions 
        WHERE refresh_token_hash = ? 
        AND expires_at > ? 
        AND revoked_at IS NULL
    """, (token_hash, now))


def update_session_last_used(session_id: str):
    """Update session last_used_at timestamp."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        conn.execute("UPDATE user_sessions SET last_used_at = ? WHERE id = ?", (now, session_id))
        conn.commit()


def revoke_session(session_id: str):
    """Revoke a session."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE id = ?", (now, session_id))
        conn.commit()


def revoke_all_user_sessions(user_id: str, except_session: Optional[str] = None):
    """Revoke all sessions for a user (logout everywhere)."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        if except_session:
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND id != ? AND revoked_at IS NULL",
                (now, user_id, except_session)
            )
        else:
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, user_id)
            )
        conn.commit()


def get_user_sessions(user_id: str) -> list:
    """Get all active sessions for a user."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    
    return db.fetchall("""
        SELECT id, device_info, ip_address, user_agent, created_at, last_used_at
        FROM user_sessions 
        WHERE user_id = ? AND expires_at > ? AND revoked_at IS NULL
        ORDER BY last_used_at DESC
    """, (user_id, now))


# ==================== OAuth Link Operations ====================

def link_oauth_provider(
    user_id: str,
    provider: str,
    provider_user_id: str,
    provider_email: Optional[str] = None,
    provider_username: Optional[str] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    token_expires_at: Optional[str] = None
) -> bool:
    """Link an OAuth provider to a user account."""
    db = get_db()
    link_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    try:
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO user_oauth 
                (id, user_id, provider, provider_user_id, provider_email, provider_username, 
                 access_token, refresh_token, token_expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                link_id, user_id, provider, provider_user_id, provider_email, provider_username,
                access_token, refresh_token, token_expires_at, now, now
            ))
            conn.commit()
        return True
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            # Provider already linked, update tokens
            return update_oauth_tokens(user_id, provider, access_token, refresh_token, token_expires_at)
        raise


def get_user_by_oauth(provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by OAuth provider link."""
    db = get_db()
    
    link = db.fetchone("""
        SELECT user_id FROM user_oauth 
        WHERE provider = ? AND provider_user_id = ?
    """, (provider, provider_user_id))
    
    if link:
        return get_user_by_id(link['user_id'])
    return None


def update_oauth_tokens(
    user_id: str,
    provider: str,
    access_token: Optional[str],
    refresh_token: Optional[str],
    token_expires_at: Optional[str]
) -> bool:
    """Update OAuth tokens for a provider link."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    
    with db.connection() as conn:
        cursor = conn.execute("""
            UPDATE user_oauth 
            SET access_token = ?, refresh_token = ?, token_expires_at = ?, updated_at = ?
            WHERE user_id = ? AND provider = ?
        """, (access_token, refresh_token, token_expires_at, now, user_id, provider))
        conn.commit()
        return cursor.rowcount > 0


def get_user_oauth_providers(user_id: str) -> list:
    """Get all OAuth providers linked to a user."""
    return get_db().fetchall("""
        SELECT provider, provider_email, provider_username, created_at
        FROM user_oauth WHERE user_id = ?
    """, (user_id,))


def unlink_oauth_provider(user_id: str, provider: str) -> bool:
    """Unlink an OAuth provider from a user account."""
    db = get_db()
    
    # Check user has password or other providers before unlinking
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    providers = get_user_oauth_providers(user_id)
    has_password = user.get('password_hash') is not None
    
    if not has_password and len(providers) <= 1:
        raise ValueError("Cannot unlink last login method. Set a password first.")
    
    with db.connection() as conn:
        cursor = conn.execute(
            "DELETE FROM user_oauth WHERE user_id = ? AND provider = ?",
            (user_id, provider)
        )
        conn.commit()
        return cursor.rowcount > 0


# ==================== Email Token Operations ====================

def create_email_token(user_id: str, token_type: str) -> str:
    """Create an email verification/reset token.
    
    Args:
        user_id: User ID
        token_type: 'verify', 'reset', or 'magic_link'
    
    Returns:
        The raw token (send to user, store hash)
    """
    db = get_db()
    config = get_auth_config()
    
    token = generate_email_token()
    token_id = str(uuid4())
    now = datetime.utcnow()
    
    if token_type == 'reset':
        expires_at = now + timedelta(hours=config.password_reset_expiry_hours)
    else:
        expires_at = now + timedelta(hours=config.email_token_expiry_hours)
    
    with db.connection() as conn:
        # Invalidate any existing tokens of this type
        conn.execute(
            "UPDATE email_tokens SET used_at = ? WHERE user_id = ? AND token_type = ? AND used_at IS NULL",
            (now.isoformat(), user_id, token_type)
        )
        
        # Create new token
        conn.execute("""
            INSERT INTO email_tokens (id, user_id, token_hash, token_type, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (token_id, user_id, hash_email_token(token), token_type, expires_at.isoformat(), now.isoformat()))
        conn.commit()
    
    return token


def verify_email_token(token: str, token_type: str) -> Optional[str]:
    """Verify an email token and return user_id if valid.
    
    Also marks the token as used.
    
    Returns:
        user_id if token is valid, None otherwise
    """
    db = get_db()
    token_hash = hash_email_token(token)
    now = datetime.utcnow().isoformat()
    
    result = db.fetchone("""
        SELECT id, user_id FROM email_tokens 
        WHERE token_hash = ? AND token_type = ? AND expires_at > ? AND used_at IS NULL
    """, (token_hash, token_type, now))
    
    if result:
        # Mark as used
        with db.connection() as conn:
            conn.execute("UPDATE email_tokens SET used_at = ? WHERE id = ?", (now, result['id']))
            conn.commit()
        return result['user_id']
    
    return None


# ==================== User Settings Operations ====================

def get_user_settings(user_id: str) -> Dict[str, Any]:
    """Get user settings, creating defaults if needed."""
    db = get_db()
    
    settings = db.fetchone("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    
    if not settings:
        # Create default settings
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO user_settings (user_id) VALUES (?)
            """, (user_id,))
            conn.commit()
        settings = db.fetchone("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    
    return dict(settings) if settings else {}


def update_user_settings(user_id: str, **updates) -> bool:
    """Update user settings."""
    db = get_db()
    
    # Ensure settings row exists
    get_user_settings(user_id)
    
    allowed_fields = {
        'timezone', 'locale', 'theme', 'dashboard_config', 
        'notification_prefs', 'default_view', 'items_per_page'
    }
    
    fields = {k: v for k, v in updates.items() if k in allowed_fields}
    if not fields:
        return False
    
    fields['updated_at'] = datetime.utcnow().isoformat()
    
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    
    with db.connection() as conn:
        cursor = conn.execute(f"UPDATE user_settings SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        return cursor.rowcount > 0
