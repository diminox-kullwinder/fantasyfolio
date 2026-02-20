CREATE TABLE asset_bookmarks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  level INTEGER NOT NULL,
  title TEXT NOT NULL,
  page_num INTEGER,
  UNIQUE(asset_id, level, title, page_num)
)
CREATE TABLE asset_collections(
  asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
  PRIMARY KEY(asset_id, collection_id)
)
CREATE TABLE asset_locations(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  -- Type of assets: 'documents' or 'models'
  asset_type TEXT NOT NULL CHECK(asset_type IN('documents', 'models')),
  -- Location type: local, local_mount(SMB/NFS), remote_sftp
  location_type TEXT NOT NULL CHECK(location_type IN('local', 'local_mount', 'remote_sftp')),
  -- Path configuration
  path TEXT NOT NULL, -- Local path or remote path
  -- Remote connection(for remote_sftp)
  ssh_host TEXT, -- SSH host or config alias
  ssh_key_path TEXT, -- Path to SSH private key(optional if using config)
  ssh_user TEXT, -- SSH username(optional if in host or config)
  ssh_port INTEGER DEFAULT 22, -- SSH port
  -- Mount info(for local_mount)
  mount_check_path TEXT, -- Path to check if mounted(e.g., .mounted marker)
  -- Status
  enabled INTEGER NOT NULL DEFAULT 1,
  is_primary INTEGER NOT NULL DEFAULT 0, -- Primary location for new uploads
  -- Metadata
  created_at TEXT NOT NULL DEFAULT(datetime('now')),
  updated_at TEXT NOT NULL DEFAULT(datetime('now')),
  last_indexed_at TEXT,
  last_status TEXT, -- 'online',
  'offline',
  'error'
  last_status_message TEXT
)
CREATE TABLE asset_pages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  page_num INTEGER NOT NULL,
  text_content TEXT,
  UNIQUE(asset_id, page_num)
)
CREATE TABLE asset_tags(
  asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY(asset_id, tag_id)
)
CREATE TABLE assets(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path TEXT UNIQUE NOT NULL,
  filename TEXT NOT NULL,
  title TEXT,
  author TEXT,
  publisher TEXT,
  page_count INTEGER,
  file_size INTEGER,
  file_hash TEXT,
  created_at TEXT,
  modified_at TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
  -- Extracted metadata
  pdf_creator TEXT,
  pdf_producer TEXT,
  pdf_creation_date TEXT,
  pdf_mod_date TEXT,
  -- Organization
  folder_path TEXT,
  game_system TEXT,
  category TEXT,
  tags TEXT, -- JSON array
  -- Thumbnails
  thumbnail_path TEXT,
  has_thumbnail INTEGER DEFAULT 0
  ,
  deleted_at TEXT DEFAULT NULL,
  volume_id TEXT REFERENCES volumes(id),
  relative_path TEXT,
  file_size_bytes INTEGER,
  file_mtime INTEGER,
  partial_hash TEXT,
  full_hash TEXT,
  index_status TEXT DEFAULT 'indexed',
  last_indexed_at TEXT,
  last_verified_at TEXT,
  last_seen_at TEXT,
  missing_since TEXT,
  thumb_storage TEXT,
  thumb_rendered_at TEXT,
  thumb_source_mtime INTEGER,
  force_reindex INTEGER DEFAULT 0,
  force_rerender INTEGER DEFAULT 0,
  is_duplicate INTEGER DEFAULT 0,
  duplicate_of_id INTEGER
)
CREATE VIRTUAL TABLE assets_fts USING fts5(
  title,
  author,
  publisher,
  filename,
  text_content,
  content='assets',
  content_rowid='id'
)
CREATE TABLE change_journal(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT(datetime('now')),
  -- What changed
  entity_type TEXT NOT NULL, -- 'asset' or 'model'
  entity_id INTEGER NOT NULL,
  -- Change details
  action TEXT NOT NULL, -- 'create',
  'update',
  'delete',
  'restore'
  field_name TEXT, -- Which field changed(for updates)
  old_value TEXT, -- Previous value(JSON for complex)
  new_value TEXT, -- New value
  -- Context
  source TEXT, -- 'indexer',
  'api',
  'manual',
  'cleanup'
  user_info TEXT, -- Optional user context
  -- Indexes for efficient queries
  FOREIGN KEY(entity_id) REFERENCES assets(id) ON DELETE SET NULL
)
CREATE TABLE collections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  parent_id INTEGER REFERENCES collections(id),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
CREATE TABLE job_errors(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER REFERENCES scan_jobs(id) ON DELETE CASCADE,
  asset_type TEXT,
  asset_id INTEGER,
  file_path TEXT,
  error_type TEXT,
  error_message TEXT,
  created_at TEXT DEFAULT(datetime('now'))
)
CREATE TABLE models(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path TEXT UNIQUE NOT NULL,
  filename TEXT NOT NULL,
  title TEXT,
  format TEXT, -- stl, 3mf, obj
  file_size INTEGER,
  file_hash TEXT,
  -- Source info(for files inside ZIPs)
  archive_path TEXT, -- path to ZIP if extracted from archive
  archive_member TEXT, -- path within ZIP
  -- Organization
  folder_path TEXT,
  collection TEXT, -- e.g., "Titans of Adventure Set14"
  creator TEXT, -- e.g., "Loot Studios"
  -- Model metadata
  vertex_count INTEGER,
  face_count INTEGER,
  has_supports INTEGER DEFAULT 0, -- supported version
  -- Preview
  preview_image TEXT, -- path to JPG if found in same archive
  has_thumbnail INTEGER DEFAULT 0,
  -- Timestamps
  created_at TEXT,
  modified_at TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
  ,
  deleted_at TEXT DEFAULT NULL,
  volume_id TEXT REFERENCES volumes(id),
  relative_path TEXT,
  file_size_bytes INTEGER,
  file_mtime INTEGER,
  partial_hash TEXT,
  full_hash TEXT,
  index_status TEXT DEFAULT 'indexed',
  last_indexed_at TEXT,
  last_verified_at TEXT,
  last_seen_at TEXT,
  missing_since TEXT,
  thumb_storage TEXT,
  thumb_path TEXT,
  thumb_rendered_at TEXT,
  thumb_source_mtime INTEGER,
  force_reindex INTEGER DEFAULT 0,
  force_rerender INTEGER DEFAULT 0,
  is_duplicate INTEGER DEFAULT 0,
  duplicate_of_id INTEGER
)
CREATE VIRTUAL TABLE models_fts USING fts5(
  filename,
  title,
  collection,
  creator,
  content='models',
  content_rowid='id'
)
CREATE VIRTUAL TABLE pages_fts USING fts5(
  text_content,
  content='asset_pages',
  content_rowid='id'
)
CREATE TABLE scan_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_type TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  target_path TEXT,
  -- Settings
  force_mode INTEGER DEFAULT 0,
  recursive INTEGER DEFAULT 1,
  include_thumbnails INTEGER DEFAULT 1,
  priority INTEGER DEFAULT 5,
  -- Status
  status TEXT DEFAULT 'pending',
  phase TEXT,
  progress_current INTEGER DEFAULT 0,
  progress_total INTEGER,
  current_item TEXT,
  -- Timing
  created_at TEXT DEFAULT(datetime('now')),
  scheduled_for TEXT,
  started_at TEXT,
  completed_at TEXT,
  -- Results
  items_processed INTEGER DEFAULT 0,
  items_skipped INTEGER DEFAULT 0,
  items_failed INTEGER DEFAULT 0,
  items_missing INTEGER DEFAULT 0,
  error_message TEXT,
  -- Metadata
  created_by TEXT
)
CREATE TABLE settings(
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
CREATE TABLE sqlite_sequence(name,seq)
CREATE TABLE tags(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL
)
CREATE TABLE volumes(
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  mount_path TEXT NOT NULL,
  volume_uuid TEXT,
  -- Status
  status TEXT DEFAULT 'online',
  last_seen_at TEXT,
  last_indexed_at TEXT,
  -- Settings
  is_readonly INTEGER DEFAULT 0,
  index_priority INTEGER DEFAULT 0,
  -- Timestamps
  created_at TEXT DEFAULT(datetime('now')),
  updated_at TEXT DEFAULT(datetime('now'))
)
