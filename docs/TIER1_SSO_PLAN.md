# FantasyFolio Tier 1: SSO & User Management Implementation Plan

## Overview
Add multi-provider SSO authentication, user management, and foundational collection features to FantasyFolio.

---

## Phase 1: Database Schema & Core Auth (Week 1)

### 1.1 Database Schema Additions

```sql
-- Users table
CREATE TABLE users (
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

-- SSO provider links (one user can have multiple providers)
CREATE TABLE user_oauth (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,  -- discord, google, apple
    provider_user_id TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);

-- User preferences/settings
CREATE TABLE user_settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    timezone TEXT DEFAULT 'UTC',
    locale TEXT DEFAULT 'en-US',
    theme TEXT DEFAULT 'dark',  -- dark, light, parchment
    dashboard_layout BLOB,  -- JSON: pinned tags, recent assets, etc.
    notification_prefs BLOB,  -- JSON: email/webhook rules
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sessions (for JWT refresh tokens)
CREATE TABLE user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL,
    device_info TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

-- Email verification tokens
CREATE TABLE email_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    token_type TEXT NOT NULL,  -- verify, reset
    expires_at TEXT NOT NULL,
    used_at TEXT
);
```

### 1.2 Core Auth Service
- `fantasyfolio/services/auth.py`
  - Password hashing (argon2)
  - JWT generation/validation
  - Session management
  - Email token generation

### 1.3 Dependencies
```
# Add to requirements.txt
authlib>=1.3.0        # OAuth client
PyJWT>=2.8.0          # JWT tokens
argon2-cffi>=23.1.0   # Password hashing
python-jose>=3.3.0    # JWT with JWK support
```

---

## Phase 2: OAuth Provider Integration (Week 1-2)

### 2.1 Provider Setup

| Provider | Client Type | Scopes | Notes |
|----------|-------------|--------|-------|
| Discord | OAuth2 | `identify`, `email` | Community-focused |
| Google | OIDC | `openid`, `email`, `profile` | Broad reach |
| Apple | OIDC | `email`, `name` | iOS users |

### 2.2 API Endpoints
```
POST   /api/auth/register          # Email/password signup
POST   /api/auth/login             # Email/password login
POST   /api/auth/logout            # Revoke session
POST   /api/auth/refresh           # Refresh JWT
POST   /api/auth/verify-email      # Verify email token
POST   /api/auth/forgot-password   # Request reset
POST   /api/auth/reset-password    # Complete reset

GET    /api/auth/oauth/:provider   # Initiate OAuth flow
GET    /api/auth/oauth/:provider/callback  # OAuth callback
POST   /api/auth/oauth/:provider/link      # Link to existing account

GET    /api/auth/me                # Current user info
PATCH  /api/auth/me                # Update profile
```

### 2.3 JIT Provisioning Flow
1. User clicks "Sign in with Discord"
2. OAuth flow completes, we receive provider user ID + email
3. Check if `user_oauth` record exists:
   - **Yes**: Log them in, update tokens
   - **No**: Check if email exists in `users`:
     - **Yes**: Prompt to link accounts (security)
     - **No**: Auto-create user with role="player", create `user_oauth` link

---

## Phase 3: User Settings & Preferences (Week 2)

### 3.1 Settings API
```
GET    /api/user/settings          # Get all settings
PATCH  /api/user/settings          # Update settings
GET    /api/user/dashboard         # Get dashboard config
PATCH  /api/user/dashboard         # Update pinned items
```

### 3.2 Dashboard Personalization
```json
{
  "pinnedTags": ["dragon", "dungeon", "npc"],
  "recentLimit": 10,
  "showRecentlyUploaded": true,
  "showRecentlyModified": true,
  "defaultSort": {
    "models": { "field": "indexed_at", "order": "desc" },
    "assets": { "field": "created_at", "order": "desc" }
  },
  "defaultView": "grid"  // grid, list, compact
}
```

### 3.3 Notification Settings Schema
```json
{
  "rules": [
    {
      "id": "uuid",
      "name": "Collection Updates",
      "trigger": "collection_update",
      "scope": ["collection:abc123", "volume:xyz789"],
      "frequency": "immediate",  // immediate, daily, weekly
      "channels": ["email", "discord_webhook"]
    }
  ],
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "email_enabled": true,
  "quiet_hours": { "start": "22:00", "end": "08:00", "timezone": "America/Los_Angeles" }
}
```

---

## Phase 4: Basic Collections (Week 2-3)

### 4.1 Collections Schema
```sql
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    cover_image_url TEXT,
    visibility TEXT DEFAULT 'private',  -- private, shared, public
    collection_type TEXT DEFAULT 'manual',  -- manual, smart
    smart_filter BLOB,  -- JSON: filter criteria for smart collections
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE collection_items (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL,  -- model, asset (pdf)
    asset_id INTEGER NOT NULL,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT REFERENCES users(id),
    sort_order INTEGER,
    notes TEXT,
    UNIQUE(collection_id, asset_type, asset_id)
);

CREATE TABLE collection_shares (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    shared_with_user_id TEXT REFERENCES users(id),  -- NULL for guest links
    permission TEXT DEFAULT 'view',  -- view, download, edit
    guest_token_hash TEXT,  -- For guest links
    expires_at TEXT,  -- For time-bound shares
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT REFERENCES users(id)
);
```

### 4.2 Collection API
```
GET    /api/collections                    # List user's collections
POST   /api/collections                    # Create collection
GET    /api/collections/:id                # Get collection details
PATCH  /api/collections/:id                # Update collection
DELETE /api/collections/:id                # Delete collection

POST   /api/collections/:id/items          # Add items
DELETE /api/collections/:id/items/:itemId  # Remove item
PATCH  /api/collections/:id/items/reorder  # Reorder items

POST   /api/collections/:id/share          # Share with user
DELETE /api/collections/:id/share/:shareId # Revoke share
POST   /api/collections/:id/guest-link     # Generate guest link

GET    /api/shared/collections             # Collections shared with me
GET    /api/guest/:token                   # Access guest link
```

---

## Phase 5: UI Integration (Week 3)

### 5.1 New Pages/Components
- `/login` - Login page with OAuth buttons
- `/register` - Email signup form
- `/settings` - User settings page
- `/collections` - Collection management
- Collection sidebar in main view
- "Add to Collection" context menu

### 5.2 Auth State Management
- JWT stored in httpOnly cookie (secure)
- Refresh token rotation
- Auto-refresh before expiry
- Logout clears all tokens

---

## Implementation Order

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | 1.1-1.3 | DB schema, auth service, password auth |
| 1-2 | 2.1-2.3 | Discord OAuth, Google OAuth, Apple OAuth |
| 2 | 3.1-3.3 | User settings, dashboard personalization |
| 2-3 | 4.1-4.2 | Collections CRUD, sharing, guest links |
| 3 | 5.1-5.2 | UI integration, login flow |

---

## Technical Decisions

### JWT Strategy
- **Access Token**: 15 min expiry, contains user ID + role
- **Refresh Token**: 7 day expiry, stored in DB for revocation
- **Cookie**: httpOnly, secure, sameSite=strict

### Password Requirements
- Minimum 8 characters
- At least 1 uppercase, 1 lowercase, 1 number
- Argon2id hashing

### Rate Limiting
- Login: 5 attempts per minute per IP
- Registration: 3 per hour per IP
- Password reset: 3 per hour per email

---

## Config Additions

```yaml
# Add to gateway config
auth:
  jwt_secret: "CHANGE_ME_IN_PRODUCTION"
  jwt_algorithm: "HS256"
  access_token_expiry_minutes: 15
  refresh_token_expiry_days: 7
  
  oauth:
    discord:
      client_id: ""
      client_secret: ""
      redirect_uri: "https://yourapp.com/api/auth/oauth/discord/callback"
    google:
      client_id: ""
      client_secret: ""
      redirect_uri: "https://yourapp.com/api/auth/oauth/google/callback"
    apple:
      client_id: ""
      team_id: ""
      key_id: ""
      private_key_path: ""
      redirect_uri: "https://yourapp.com/api/auth/oauth/apple/callback"
  
  email:
    provider: "smtp"  # or sendgrid, ses
    from_address: "noreply@fantasyfolio.app"
    smtp_host: ""
    smtp_port: 587
    smtp_user: ""
    smtp_password: ""
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| OAuth provider downtime | Email fallback always available |
| Token theft | Short expiry + refresh rotation |
| Email enumeration | Generic error messages |
| Brute force | Rate limiting + account lockout |

---

## Success Criteria

- [ ] User can sign up with email/password
- [ ] User can sign in with Discord/Google/Apple
- [ ] User can link multiple OAuth providers
- [ ] User can customize dashboard
- [ ] User can create/manage collections
- [ ] User can share collections with other users
- [ ] User can generate time-limited guest links
- [ ] All auth flows work on mobile browsers
