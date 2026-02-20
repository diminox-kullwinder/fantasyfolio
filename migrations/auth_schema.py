"""
Migration 006: Authentication & User Management Schema

Adds tables for:
- Users (email/password + OAuth)
- OAuth provider links
- User sessions (refresh tokens)
- Email verification tokens
- User settings/preferences
- Collections (user-owned)
- Collection items and sharing

Run with: python -m migrations.006_auth_schema
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_ADDITIONS = """
-- ==================== Users ====================

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,  -- UUID
    email TEXT UNIQUE NOT NULL,
    email_verified INTEGER DEFAULT 0,
    password_hash TEXT,  -- NULL for SSO-only users
    display_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'player',  -- admin, gm, player, guest
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ==================== OAuth Provider Links ====================

CREATE TABLE IF NOT EXISTS user_oauth (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,  -- discord, google, apple
    provider_user_id TEXT NOT NULL,
    provider_email TEXT,
    provider_username TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_oauth_user ON user_oauth(user_id);
CREATE INDEX IF NOT EXISTS idx_user_oauth_provider ON user_oauth(provider, provider_user_id);

-- ==================== User Sessions ====================

CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL,
    device_info TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(refresh_token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

-- ==================== Email Verification Tokens ====================

CREATE TABLE IF NOT EXISTS email_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    token_type TEXT NOT NULL,  -- verify, reset, magic_link
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_tokens_hash ON email_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_email_tokens_user ON email_tokens(user_id);

-- ==================== User Settings ====================

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    timezone TEXT DEFAULT 'UTC',
    locale TEXT DEFAULT 'en-US',
    theme TEXT DEFAULT 'dark',  -- dark, light, parchment
    
    -- Dashboard preferences (JSON)
    dashboard_config TEXT DEFAULT '{}',
    
    -- Notification preferences (JSON)  
    notification_prefs TEXT DEFAULT '{}',
    
    -- View preferences
    default_view TEXT DEFAULT 'grid',  -- grid, list, compact
    items_per_page INTEGER DEFAULT 50,
    
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ==================== User Collections ====================

CREATE TABLE IF NOT EXISTS user_collections (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    cover_asset_id INTEGER,  -- Reference to asset for cover image
    visibility TEXT DEFAULT 'private',  -- private, shared (no public)
    collection_type TEXT DEFAULT 'manual',  -- manual, smart
    smart_filter TEXT,  -- JSON: filter criteria for smart collections
    sort_order TEXT DEFAULT 'added_at',  -- added_at, filename, custom
    item_count INTEGER DEFAULT 0,  -- Cached count
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collections_owner ON user_collections(owner_id);
CREATE INDEX IF NOT EXISTS idx_collections_visibility ON user_collections(visibility);

-- ==================== Collection Items ====================

CREATE TABLE IF NOT EXISTS collection_items (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL,  -- model, pdf
    asset_id INTEGER NOT NULL,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT REFERENCES users(id),
    sort_order INTEGER,
    notes TEXT,
    UNIQUE(collection_id, asset_type, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_asset ON collection_items(asset_type, asset_id);

-- ==================== Collection Shares ====================

CREATE TABLE IF NOT EXISTS collection_shares (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
    
    -- Either shared with specific user OR guest link
    shared_with_user_id TEXT REFERENCES users(id),
    guest_token_hash TEXT,  -- For guest links (no login required)
    
    permission TEXT DEFAULT 'view',  -- view, download, edit
    
    -- Limits for guest links
    expires_at TEXT,
    max_downloads INTEGER,
    download_count INTEGER DEFAULT 0,
    password_hash TEXT,  -- Optional password for guest links
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT REFERENCES users(id),
    last_accessed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_shares_collection ON collection_shares(collection_id);
CREATE INDEX IF NOT EXISTS idx_shares_user ON collection_shares(shared_with_user_id);
CREATE INDEX IF NOT EXISTS idx_shares_guest ON collection_shares(guest_token_hash);

-- ==================== Schema Version ====================
-- Note: settings table may not exist in fresh databases
-- Version tracking is optional for this migration
"""


def run_migration(db_path: Path) -> bool:
    """Run the auth schema migration."""
    logger.info(f"Running auth migration on {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Execute schema additions
        conn.executescript(SCHEMA_ADDITIONS)
        conn.commit()
        
        # Verify tables were created
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'users', 'user_oauth', 'user_sessions', 
                'email_tokens', 'user_settings',
                'user_collections', 'collection_items', 'collection_shares'
            )
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Created tables: {tables}")
        conn.close()
        
        if len(tables) >= 8:
            logger.info("✅ Auth migration completed successfully")
            return True
        else:
            logger.error(f"❌ Expected 8 tables, got {len(tables)}")
            return False
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # Default to test database
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/dam.db")
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    success = run_migration(db_path)
    sys.exit(0 if success else 1)
