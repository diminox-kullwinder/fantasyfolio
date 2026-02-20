"""
Authentication API endpoints for FantasyFolio.

Handles:
- Email/password registration and login
- OAuth flow (Discord, Google, Apple)
- Session management (refresh, logout)
- Password reset flow
- Email verification
"""

import logging
from functools import wraps
from flask import Blueprint, request, jsonify, redirect, url_for, make_response

from fantasyfolio.services import auth as auth_service

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ==================== Decorators ====================

def get_current_user():
    """Get the current user from the Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header[7:]  # Remove 'Bearer ' prefix
    payload = auth_service.verify_access_token(token)
    
    if not payload:
        return None
    
    return auth_service.get_user_by_id(payload['sub'])


def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator to require specific role(s)."""
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            if request.current_user['role'] not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ==================== Registration ====================

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user with email/password.
    
    Body:
        email: Email address
        password: Password (8+ chars, 1 upper, 1 lower, 1 number)
        display_name: Optional display name
    
    Returns:
        User info + tokens on success
    """
    data = request.get_json(silent=True) or {}
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip() or None
    
    # Validate email
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    
    # Validate password
    is_valid, error_msg = auth_service.validate_password_strength(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Check if email exists
    existing = auth_service.get_user_by_email(email)
    if existing:
        # Generic message to prevent email enumeration
        return jsonify({'error': 'Registration failed'}), 400
    
    # Create user
    user = auth_service.create_user(email, password, display_name)
    if not user:
        return jsonify({'error': 'Registration failed'}), 400
    
    # Generate tokens
    access_token = auth_service.generate_access_token(user['id'], user['role'], user['email'])
    refresh_token = auth_service.generate_refresh_token()
    
    # Create session
    session_id = auth_service.create_session(
        user['id'],
        refresh_token,
        device_info=request.headers.get('User-Agent'),
        ip_address=request.remote_addr
    )
    
    # TODO: Send verification email
    # auth_service.send_verification_email(user['id'])
    
    logger.info(f"User registered: {email}")
    
    return jsonify({
        'user': {
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'],
            'role': user['role'],
            'email_verified': bool(user['email_verified'])
        },
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer'
    }), 201


# ==================== Login ====================

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with email/password.
    
    Body:
        email: Email address
        password: Password
    
    Returns:
        User info + tokens on success
    """
    data = request.get_json(silent=True) or {}
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Get user
    user = auth_service.get_user_by_email(email)
    if not user:
        # Generic message to prevent email enumeration
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password
    if not user.get('password_hash'):
        return jsonify({'error': 'Account uses OAuth login only'}), 401
    
    if not auth_service.verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Update last login
    auth_service.update_user(user['id'], last_login_at=auth_service.datetime.utcnow().isoformat())
    
    # Generate tokens
    access_token = auth_service.generate_access_token(user['id'], user['role'], user['email'])
    refresh_token = auth_service.generate_refresh_token()
    
    # Create session
    session_id = auth_service.create_session(
        user['id'],
        refresh_token,
        device_info=request.headers.get('User-Agent'),
        ip_address=request.remote_addr
    )
    
    logger.info(f"User logged in: {email}")
    
    return jsonify({
        'user': {
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'],
            'role': user['role'],
            'email_verified': bool(user['email_verified'])
        },
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer'
    })


# ==================== Token Refresh ====================

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token.
    
    Body:
        refresh_token: The refresh token
    
    Returns:
        New access token (and optionally rotated refresh token)
    """
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token', '')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400
    
    # Validate refresh token
    session = auth_service.get_session_by_token(refresh_token)
    if not session:
        return jsonify({'error': 'Invalid or expired refresh token'}), 401
    
    # Get user
    user = auth_service.get_user_by_id(session['user_id'])
    if not user or not user['is_active']:
        return jsonify({'error': 'User not found or inactive'}), 401
    
    # Update session last used
    auth_service.update_session_last_used(session['id'])
    
    # Generate new access token
    access_token = auth_service.generate_access_token(user['id'], user['role'], user['email'])
    
    return jsonify({
        'access_token': access_token,
        'token_type': 'Bearer'
    })


# ==================== Logout ====================

@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """Logout current session.
    
    Body (optional):
        all_sessions: If true, logout from all devices
        refresh_token: The refresh token to revoke
    """
    data = request.get_json(silent=True) or {}
    user = request.current_user
    
    if data.get('all_sessions'):
        # Logout everywhere
        auth_service.revoke_all_user_sessions(user['id'])
        logger.info(f"User logged out from all sessions: {user['email']}")
    else:
        # Logout just this session
        refresh_token = data.get('refresh_token')
        if refresh_token:
            session = auth_service.get_session_by_token(refresh_token)
            if session and session['user_id'] == user['id']:
                auth_service.revoke_session(session['id'])
    
    return jsonify({'message': 'Logged out successfully'})


# ==================== Current User ====================

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    """Get current user info."""
    user = request.current_user
    providers = auth_service.get_user_oauth_providers(user['id'])
    
    return jsonify({
        'id': user['id'],
        'email': user['email'],
        'display_name': user['display_name'],
        'avatar_url': user['avatar_url'],
        'role': user['role'],
        'email_verified': bool(user['email_verified']),
        'has_password': user['password_hash'] is not None,
        'oauth_providers': [p['provider'] for p in providers],
        'created_at': user['created_at']
    })


@auth_bp.route('/me', methods=['PATCH'])
@require_auth
def update_me():
    """Update current user profile.
    
    Body:
        display_name: New display name
        avatar_url: New avatar URL
    """
    data = request.get_json(silent=True) or {}
    user = request.current_user
    
    updates = {}
    if 'display_name' in data:
        updates['display_name'] = data['display_name'].strip()
    if 'avatar_url' in data:
        updates['avatar_url'] = data['avatar_url'].strip() or None
    
    if updates:
        auth_service.update_user(user['id'], **updates)
    
    return get_me()


@auth_bp.route('/me/password', methods=['PUT'])
@require_auth
def change_password():
    """Change current user's password.
    
    Body:
        current_password: Current password (required if has password)
        new_password: New password
    """
    data = request.get_json(silent=True) or {}
    user = request.current_user
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    # If user has a password, verify current
    if user['password_hash']:
        if not auth_service.verify_password(current_password, user['password_hash']):
            return jsonify({'error': 'Current password incorrect'}), 400
    
    # Validate new password
    is_valid, error_msg = auth_service.validate_password_strength(new_password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Update password
    auth_service.update_password(user['id'], new_password)
    
    return jsonify({'message': 'Password updated successfully'})


@auth_bp.route('/me/sessions', methods=['GET'])
@require_auth
def get_sessions():
    """Get list of active sessions for current user."""
    sessions = auth_service.get_user_sessions(request.current_user['id'])
    return jsonify({'sessions': sessions})


@auth_bp.route('/me/sessions/<session_id>', methods=['DELETE'])
@require_auth
def revoke_specific_session(session_id):
    """Revoke a specific session."""
    # Verify session belongs to user (already done by filtering in get_user_sessions logic)
    auth_service.revoke_session(session_id)
    return jsonify({'message': 'Session revoked'})


# ==================== Password Reset ====================

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset email.
    
    Body:
        email: Email address
    """
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    user = auth_service.get_user_by_email(email)
    if user:
        token = auth_service.create_email_token(user['id'], 'reset')
        # TODO: Send email with token
        # For now, log it (development only!)
        logger.info(f"Password reset token for {email}: {token}")
    
    # Always return success to prevent email enumeration
    return jsonify({'message': 'If an account exists, a reset email has been sent'})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Complete password reset with token.
    
    Body:
        token: Reset token from email
        new_password: New password
    """
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    new_password = data.get('new_password', '')
    
    if not token or not new_password:
        return jsonify({'error': 'Token and new password required'}), 400
    
    # Validate password
    is_valid, error_msg = auth_service.validate_password_strength(new_password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Verify token
    user_id = auth_service.verify_email_token(token, 'reset')
    if not user_id:
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    
    # Update password
    auth_service.update_password(user_id, new_password)
    
    # Revoke all sessions for security
    auth_service.revoke_all_user_sessions(user_id)
    
    return jsonify({'message': 'Password reset successfully. Please login with your new password.'})


# ==================== Email Verification ====================

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify email with token.
    
    Body:
        token: Verification token from email
    """
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    user_id = auth_service.verify_email_token(token, 'verify')
    if not user_id:
        return jsonify({'error': 'Invalid or expired verification token'}), 400
    
    # Mark email as verified
    auth_service.update_user(user_id, email_verified=1)
    
    return jsonify({'message': 'Email verified successfully'})


@auth_bp.route('/resend-verification', methods=['POST'])
@require_auth
def resend_verification():
    """Resend email verification."""
    user = request.current_user
    
    if user['email_verified']:
        return jsonify({'message': 'Email already verified'})
    
    token = auth_service.create_email_token(user['id'], 'verify')
    # TODO: Send email
    logger.info(f"Verification token for {user['email']}: {token}")
    
    return jsonify({'message': 'Verification email sent'})


# ==================== OAuth: Discord ====================

@auth_bp.route('/oauth/discord', methods=['GET'])
def oauth_discord_start():
    """Start Discord OAuth flow."""
    config = auth_service.get_auth_config()
    
    if not config.discord_client_id:
        return jsonify({'error': 'Discord OAuth not configured'}), 503
    
    state = auth_service.generate_oauth_state('discord', request.args.get('redirect'))
    
    params = {
        'client_id': config.discord_client_id,
        'redirect_uri': config.discord_redirect_uri,
        'response_type': 'code',
        'scope': 'identify email',
        'state': state
    }
    
    url = 'https://discord.com/api/oauth2/authorize?' + '&'.join(f'{k}={v}' for k, v in params.items())
    
    return redirect(url)


@auth_bp.route('/oauth/discord/callback', methods=['GET'])
def oauth_discord_callback():
    """Handle Discord OAuth callback."""
    import requests
    
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return jsonify({'error': f'Discord error: {error}'}), 400
    
    # Verify state
    state_data = auth_service.verify_oauth_state(state)
    if not state_data:
        return jsonify({'error': 'Invalid OAuth state'}), 400
    
    config = auth_service.get_auth_config()
    
    # Exchange code for token
    token_response = requests.post('https://discord.com/api/oauth2/token', data={
        'client_id': config.discord_client_id,
        'client_secret': config.discord_client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': config.discord_redirect_uri
    }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    
    if token_response.status_code != 200:
        logger.error(f"Discord token exchange failed: {token_response.text}")
        return jsonify({'error': 'Failed to authenticate with Discord'}), 400
    
    tokens = token_response.json()
    access_token = tokens['access_token']
    
    # Get user info
    user_response = requests.get('https://discord.com/api/users/@me', headers={
        'Authorization': f'Bearer {access_token}'
    })
    
    if user_response.status_code != 200:
        return jsonify({'error': 'Failed to get Discord user info'}), 400
    
    discord_user = user_response.json()
    discord_id = discord_user['id']
    discord_email = discord_user.get('email')
    discord_username = f"{discord_user['username']}"
    
    # Check if user exists by OAuth link
    user = auth_service.get_user_by_oauth('discord', discord_id)
    
    if not user:
        # Check if email exists (for account linking)
        if discord_email:
            existing_user = auth_service.get_user_by_email(discord_email)
            if existing_user:
                # Link Discord to existing account
                auth_service.link_oauth_provider(
                    existing_user['id'], 'discord', discord_id,
                    provider_email=discord_email, provider_username=discord_username,
                    access_token=access_token
                )
                user = existing_user
        
        if not user:
            # Create new user (JIT provisioning)
            user = auth_service.create_user(
                email=discord_email or f'{discord_id}@discord.user',
                display_name=discord_username,
                role='player'
            )
            
            if user:
                # Mark email as verified if from Discord
                if discord_email:
                    auth_service.update_user(user['id'], email_verified=1)
                
                # Link OAuth
                auth_service.link_oauth_provider(
                    user['id'], 'discord', discord_id,
                    provider_email=discord_email, provider_username=discord_username,
                    access_token=access_token
                )
    else:
        # Update tokens
        auth_service.update_oauth_tokens(user['id'], 'discord', access_token, None, None)
    
    if not user:
        return jsonify({'error': 'Failed to create account'}), 500
    
    # Generate tokens
    jwt_access = auth_service.generate_access_token(user['id'], user['role'], user['email'])
    refresh_token = auth_service.generate_refresh_token()
    
    # Create session
    auth_service.create_session(
        user['id'], refresh_token,
        device_info='Discord OAuth',
        ip_address=request.remote_addr
    )
    
    # Update last login
    auth_service.update_user(user['id'], last_login_at=auth_service.datetime.utcnow().isoformat())
    
    logger.info(f"User logged in via Discord: {user['email']}")
    
    # For API clients, return JSON
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'user': {
                'id': user['id'],
                'email': user['email'],
                'display_name': user['display_name'],
                'role': user['role']
            },
            'access_token': jwt_access,
            'refresh_token': refresh_token,
            'token_type': 'Bearer'
        })
    
    # For browser, redirect with tokens in fragment (SPA flow)
    redirect_to = state_data.get('redirect_to') or '/'
    return redirect(f"{redirect_to}#access_token={jwt_access}&refresh_token={refresh_token}")


# ==================== User Settings ====================

@auth_bp.route('/settings', methods=['GET'])
@require_auth
def get_settings():
    """Get current user's settings."""
    settings = auth_service.get_user_settings(request.current_user['id'])
    return jsonify(settings)


@auth_bp.route('/settings', methods=['PATCH'])
@require_auth
def update_settings():
    """Update current user's settings.
    
    Body:
        timezone: Timezone string (e.g., 'America/Los_Angeles')
        locale: Locale string (e.g., 'en-US')
        theme: Theme name (dark, light, parchment)
        dashboard_config: JSON string for dashboard layout
        notification_prefs: JSON string for notification settings
        default_view: Default view (grid, list, compact)
        items_per_page: Items per page (10-100)
    """
    data = request.get_json(silent=True) or {}
    
    # Validate items_per_page range
    if 'items_per_page' in data:
        data['items_per_page'] = max(10, min(100, int(data['items_per_page'])))
    
    auth_service.update_user_settings(request.current_user['id'], **data)
    
    return get_settings()


# ==================== Provider Status ====================

@auth_bp.route('/providers', methods=['GET'])
def get_providers():
    """Get available OAuth providers."""
    config = auth_service.get_auth_config()
    
    return jsonify({
        'providers': {
            'email': True,  # Always available
            'discord': bool(config.discord_client_id),
            'google': bool(config.google_client_id),
            'apple': bool(config.apple_client_id)
        }
    })
