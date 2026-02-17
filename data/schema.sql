-- DAM Database Schema
-- Digital Asset Manager for RPG PDFs

-- Main assets table
CREATE TABLE IF NOT EXISTS assets (
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
    tags TEXT,  -- JSON array
    
    -- Thumbnails
    thumbnail_path TEXT,
    has_thumbnail INTEGER DEFAULT 0,
    deleted_at TEXT
);

-- Full-text search table for asset metadata
-- Note: Page text is searchable via pages_fts table
CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
    title,
    author,
    publisher,
    filename,
    content='assets',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
    INSERT INTO assets_fts(rowid, title, author, publisher, filename)
    VALUES (new.id, new.title, new.author, new.publisher, new.filename);
END;

CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, title, author, publisher, filename)
    VALUES ('delete', old.id, old.title, old.author, old.publisher, old.filename);
END;

CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, title, author, publisher, filename)
    VALUES ('delete', old.id, old.title, old.author, old.publisher, old.filename);
    INSERT INTO assets_fts(rowid, title, author, publisher, filename)
    VALUES (new.id, new.title, new.author, new.publisher, new.filename);
END;

-- Collections/folders virtual organization
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES collections(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: assets in collections
CREATE TABLE IF NOT EXISTS asset_collections (
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, collection_id)
);

-- Tags table for normalized tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, tag_id)
);

-- Page-level text for search with page numbers
CREATE TABLE IF NOT EXISTS asset_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    page_num INTEGER NOT NULL,
    text_content TEXT,
    UNIQUE(asset_id, page_num)
);

-- Full-text search on pages
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    text_content,
    content='asset_pages',
    content_rowid='id'
);

-- Triggers for page FTS
CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON asset_pages BEGIN
    INSERT INTO pages_fts(rowid, text_content) VALUES (new.id, new.text_content);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON asset_pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, text_content) VALUES ('delete', old.id, old.text_content);
END;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_assets_folder ON assets(folder_path);
CREATE INDEX IF NOT EXISTS idx_assets_publisher ON assets(publisher);
CREATE INDEX IF NOT EXISTS idx_assets_game_system ON assets(game_system);
CREATE INDEX IF NOT EXISTS idx_assets_filename ON assets(filename);
CREATE INDEX IF NOT EXISTS idx_pages_asset ON asset_pages(asset_id);

-- PDF Bookmarks/TOC
CREATE TABLE IF NOT EXISTS asset_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    level INTEGER NOT NULL,
    title TEXT NOT NULL,
    page_num INTEGER,
    UNIQUE(asset_id, level, title, page_num)
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_asset ON asset_bookmarks(asset_id);

-- Application Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value) VALUES 
    ('pdf_root', ''),
    ('3d_root', ''),
    ('smb_paths', '[]');

-- 3D Model Assets
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    title TEXT,
    format TEXT,  -- stl, 3mf, obj
    file_size INTEGER,
    file_hash TEXT,
    
    -- Source info (for files inside ZIPs)
    archive_path TEXT,  -- path to ZIP if extracted from archive
    archive_member TEXT,  -- path within ZIP
    
    -- Organization
    folder_path TEXT,
    collection TEXT,  -- e.g., "Titans of Adventure Set14"
    creator TEXT,  -- e.g., "Loot Studios"
    
    -- Model metadata
    vertex_count INTEGER,
    face_count INTEGER,
    has_supports INTEGER DEFAULT 0,  -- supported version
    
    -- Preview
    preview_image TEXT,  -- path to JPG if found in same archive
    has_thumbnail INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TEXT,
    modified_at TEXT,
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Thumbnail tracking (new system)
    thumb_storage TEXT,
    volume_id INTEGER,
    thumb_path TEXT,
    thumb_rendered_at TEXT,
    thumb_source_mtime INTEGER,
    
    deleted_at TEXT
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_models_folder ON models(folder_path);
CREATE INDEX IF NOT EXISTS idx_models_format ON models(format);
CREATE INDEX IF NOT EXISTS idx_models_archive ON models(archive_path);
CREATE INDEX IF NOT EXISTS idx_models_collection ON models(collection);

-- Full-text search for 3D models
CREATE VIRTUAL TABLE IF NOT EXISTS models_fts USING fts5(
    filename,
    title,
    collection,
    creator,
    content='models',
    content_rowid='id'
);

-- Triggers for FTS sync
CREATE TRIGGER IF NOT EXISTS models_ai AFTER INSERT ON models BEGIN
    INSERT INTO models_fts(rowid, filename, title, collection, creator)
    VALUES (new.id, new.filename, new.title, new.collection, new.creator);
END;

CREATE TRIGGER IF NOT EXISTS models_ad AFTER DELETE ON models BEGIN
    INSERT INTO models_fts(models_fts, rowid, filename, title, collection, creator)
    VALUES ('delete', old.id, old.filename, old.title, old.collection, old.creator);
END;

CREATE TRIGGER IF NOT EXISTS models_au AFTER UPDATE ON models BEGIN
    INSERT INTO models_fts(models_fts, rowid, filename, title, collection, creator)
    VALUES ('delete', old.id, old.filename, old.title, old.collection, old.creator);
    INSERT INTO models_fts(rowid, filename, title, collection, creator)
    VALUES (new.id, new.filename, new.title, new.collection, new.creator);
END;

-- Asset Locations table for configurable content paths
CREATE TABLE IF NOT EXISTS asset_locations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    location_type TEXT NOT NULL DEFAULT 'local',
    path TEXT NOT NULL,
    ssh_host TEXT,
    ssh_key_path TEXT,
    ssh_user TEXT,
    ssh_port INTEGER DEFAULT 22,
    mount_check_path TEXT,
    enabled INTEGER DEFAULT 1,
    is_primary INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for asset locations
CREATE INDEX IF NOT EXISTS idx_asset_locations_asset_type ON asset_locations(asset_type);
CREATE INDEX IF NOT EXISTS idx_asset_locations_enabled ON asset_locations(enabled);

-- Volumes table for volume/mount tracking
CREATE TABLE IF NOT EXISTS volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    mount_path TEXT,
    volume_type TEXT DEFAULT 'local',
    is_readonly INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_volumes_path ON volumes(path);
CREATE INDEX IF NOT EXISTS idx_volumes_enabled ON volumes(enabled);
