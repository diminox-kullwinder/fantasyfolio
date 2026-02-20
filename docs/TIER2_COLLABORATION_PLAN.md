# FantasyFolio Tier 2: Collaboration Layer Implementation Plan

## Overview
Build on Tier 1 auth to add advanced collections, sharing, notifications, and AI-powered features.

**Prerequisites:** Tier 1 SSO & User Management complete

---

## 📋 DECISIONS (2026-02-19)

| Decision | Choice | Notes |
|----------|--------|-------|
| **Public Collections** | ❌ Disabled | Commercial assets have distribution restrictions |
| **Sharing Model** | Explicit only | Specific users OR time-limited guest links |
| **Campaigns (GM sharing)** | ✅ Yes | Share collections with campaign members |

---

## Phase 1: Smart Collections (Week 4)

### 1.1 Smart Filter Schema
```json
{
  "type": "smart",
  "filter": {
    "operator": "AND",  // AND, OR
    "conditions": [
      { "field": "tags", "op": "contains", "value": "dragon" },
      { "field": "format", "op": "in", "value": ["stl", "obj"] },
      { "field": "indexed_at", "op": "gte", "value": "2024-01-01" },
      { "field": "volume_id", "op": "eq", "value": "uuid-here" }
    ]
  },
  "sort": { "field": "filename", "order": "asc" },
  "limit": 500
}
```

### 1.2 Smart Collection Engine
- `fantasyfolio/services/smart_collections.py`
  - Parse filter JSON → SQL WHERE clause
  - Cache results with TTL (5 min)
  - Invalidate on relevant asset changes
  - Support nested AND/OR groups

### 1.3 API Extensions
```
POST   /api/collections/:id/preview    # Preview smart filter results
GET    /api/collections/:id/refresh    # Force refresh smart collection
GET    /api/filter-fields              # Available fields for smart filters
```

---

## Phase 2: Advanced Sharing & Campaigns (Week 4-5)

### 2.1 Campaign (GM Sharing) Schema
```sql
CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    invite_code TEXT UNIQUE,  -- Short code for joining
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE campaign_members (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    role TEXT DEFAULT 'player',  -- gm, player
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
    invited_by TEXT REFERENCES users(id),
    UNIQUE(campaign_id, user_id)
);

CREATE TABLE campaign_collections (
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    shared_at TEXT DEFAULT CURRENT_TIMESTAMP,
    shared_by TEXT REFERENCES users(id),
    PRIMARY KEY(campaign_id, collection_id)
);
```

### 2.2 Campaign API
```
GET    /api/campaigns                      # List my campaigns
POST   /api/campaigns                      # Create campaign
GET    /api/campaigns/:id                  # Get campaign details
PATCH  /api/campaigns/:id                  # Update campaign
DELETE /api/campaigns/:id                  # Delete campaign

POST   /api/campaigns/:id/invite           # Generate invite
POST   /api/campaigns/join/:code           # Join via invite code
DELETE /api/campaigns/:id/members/:userId  # Remove member
PATCH  /api/campaigns/:id/members/:userId  # Change member role

POST   /api/campaigns/:id/collections      # Share collection to campaign
DELETE /api/campaigns/:id/collections/:cid # Unshare collection
```

### 2.3 Guest Link Enhancements
```sql
ALTER TABLE collection_shares ADD COLUMN 
    max_downloads INTEGER,      -- NULL = unlimited
    download_count INTEGER DEFAULT 0,
    password_hash TEXT,         -- Optional password protection
    allowed_ips TEXT;           -- JSON array of allowed IP ranges
```

---

## Phase 3: Notification Engine (Week 5-6)

### 3.1 Notification Schema
```sql
CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,  -- collection_shared, asset_added, campaign_invite, etc.
    title TEXT NOT NULL,
    body TEXT,
    data BLOB,  -- JSON: relevant IDs, links
    read_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notification_queue (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,  -- email, discord_webhook, in_app
    payload BLOB NOT NULL,  -- JSON
    scheduled_for TEXT NOT NULL,
    sent_at TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0
);
```

### 3.2 Notification Types
| Type | Trigger | Channels |
|------|---------|----------|
| `collection_shared` | Collection shared with user | in_app, email |
| `collection_updated` | Items added to shared collection | in_app, email, webhook |
| `campaign_invite` | Invited to campaign | in_app, email |
| `campaign_update` | New collection shared to campaign | in_app, webhook |
| `guest_link_accessed` | Someone used your guest link | in_app |
| `asset_ready` | Upload processing complete | in_app |

### 3.3 Notification Service
- `fantasyfolio/services/notifications.py`
  - Queue-based delivery (background worker)
  - Frequency batching (immediate/daily/weekly digest)
  - Quiet hours respect
  - Webhook retry with exponential backoff

### 3.4 Discord Webhook Integration
```python
def send_discord_notification(webhook_url: str, notification: dict):
    embed = {
        "title": notification["title"],
        "description": notification["body"],
        "color": 0x5865F2,  # Discord blurple
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "FantasyFolio"}
    }
    requests.post(webhook_url, json={"embeds": [embed]})
```

---

## Phase 4: Bulk Operations (Week 6)

### 4.1 Bulk Download
```
POST   /api/bulk/download
Body: {
  "items": [
    {"type": "model", "id": 123},
    {"type": "asset", "id": 456}
  ],
  "format": "zip",  // zip, individual
  "flatten": false  // true = no folder structure
}
Response: { "job_id": "uuid", "status": "processing" }

GET    /api/bulk/download/:jobId/status
GET    /api/bulk/download/:jobId/file  // Download when ready
```

### 4.2 Bulk Metadata Update
```
PATCH  /api/bulk/metadata
Body: {
  "items": [
    {"type": "model", "id": 123},
    {"type": "model", "id": 124}
  ],
  "updates": {
    "tags": {"add": ["printed"], "remove": ["todo"]},
    "collection": "uuid"
  }
}
```

### 4.3 Bulk Move/Organize
```
POST   /api/bulk/move
Body: {
  "items": [...],
  "destination": {
    "collection_id": "uuid",
    // OR
    "folder_path": "/Organized/Dragons"
  }
}
```

---

## Phase 5: Tagging & Auto-Organization (Week 7)

### 5.1 Tag Management Schema
```sql
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT,  -- genre, creature, style, source, etc.
    color TEXT,     -- Hex color for UI
    created_by TEXT REFERENCES users(id),
    usage_count INTEGER DEFAULT 0
);

CREATE TABLE tag_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    tags BLOB NOT NULL,  -- JSON array of tag names
    created_by TEXT REFERENCES users(id),
    is_public INTEGER DEFAULT 0
);
```

### 5.2 Auto-Move Rules
```sql
CREATE TABLE auto_rules (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    trigger TEXT NOT NULL,  -- on_upload, on_tag, on_index
    conditions BLOB NOT NULL,  -- JSON filter (same as smart collections)
    actions BLOB NOT NULL,  -- JSON: add_tags, move_to_collection, etc.
    priority INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 5.3 Auto-Rule Actions
```json
{
  "actions": [
    {"type": "add_tags", "tags": ["new", "unreviewed"]},
    {"type": "add_to_collection", "collection_id": "uuid"},
    {"type": "move_to_folder", "path": "/Inbox/{year}/{month}"},
    {"type": "notify", "message": "New {format} uploaded: {filename}"}
  ]
}
```

---

## Phase 6: AI Integration (Week 7-8)

### 6.1 AI Tagging Service
- Integration with vision model (Claude/GPT-4V)
- Analyze thumbnail → suggest tags
- RPG-specific vocabulary:
  - Genres: Grimdark, High Fantasy, Steampunk, Sci-Fi
  - Creatures: Dragon, Undead, Humanoid, Beast, Construct
  - Styles: Heroic, Chibi, Realistic, Stylized
  - Use: Terrain, Mini, Prop, Vehicle, Building

### 6.2 AI Tagging API
```
POST   /api/ai/suggest-tags/:assetType/:id
Response: {
  "suggestions": [
    {"tag": "dragon", "confidence": 0.95, "category": "creature"},
    {"tag": "grimdark", "confidence": 0.72, "category": "genre"}
  ]
}

POST   /api/ai/bulk-tag
Body: { "items": [...], "auto_apply_threshold": 0.8 }
```

### 6.3 AI-Generated Collection
```json
{
  "type": "ai_curated",
  "ai_prompt": "Fantasy dungeon terrain suitable for a vampire lair",
  "refresh_frequency": "weekly",
  "max_items": 50
}
```

---

## Implementation Timeline

| Week | Phase | Focus |
|------|-------|-------|
| 4 | 1 | Smart Collections |
| 4-5 | 2 | Campaigns & Advanced Sharing |
| 5-6 | 3 | Notification Engine |
| 6 | 4 | Bulk Operations |
| 7 | 5 | Tagging & Auto-Rules |
| 7-8 | 6 | AI Integration |

---

## UI Components Needed

### Collection Views
- Collection grid/list with drag-drop reorder
- Smart collection filter builder (visual query builder)
- Share modal with permission controls
- Guest link generator with QR code

### Campaign Management
- Campaign dashboard
- Member management
- Shared collections view

### Notifications
- Bell icon with unread count
- Notification dropdown/drawer
- Notification settings page
- Discord webhook setup wizard

### Bulk Operations
- Multi-select mode in asset grid
- Bulk action toolbar
- Download progress modal
- Metadata bulk editor

---

## Dependencies

```
# Add to requirements.txt
celery>=5.3.0         # Background task queue
redis>=5.0.0          # Celery broker
anthropic>=0.18.0     # AI tagging (Claude)
# OR
openai>=1.12.0        # AI tagging (GPT-4V)
qrcode>=7.4.0         # Guest link QR codes
```

---

## Success Criteria

- [ ] Smart collections auto-update when matching assets added
- [ ] Campaigns allow GM to share multiple collections with players
- [ ] Guest links work without login, respect time/download limits
- [ ] Discord webhook fires when shared collection updated
- [ ] Email digests aggregate notifications by frequency setting
- [ ] Bulk download creates ZIP with folder structure preserved
- [ ] Auto-rules trigger on upload and apply tags/moves
- [ ] AI suggests relevant RPG tags with >80% user acceptance rate
