# FantasyFolio

A self-hosted web application for managing and browsing digital asset libraries, specifically designed for:
- **RPG PDF collections** (rulebooks, adventures, supplements)
- **3D printable miniatures** (STL, 3MF, OBJ files from Patreon packs)

> **Note**: This project was formerly known as "DAM" (Digital Asset Manager). The `DAM_*` environment variables are still supported for backward compatibility.

## Features

### PDF Management
- 📚 Browse and search your PDF library with full-text search
- 🔍 Search within PDF content with page-level results
- 📖 In-browser PDF page viewer with zoom controls
- 📑 Table of contents / bookmark extraction
- 🏷️ Automatic publisher and game system detection
- 📥 Download individual files

### 3D Model Management
- 🎲 Index 3D models including files inside ZIP archives
- 🖼️ Preview images extracted from Patreon packs (when available)
- 🔎 Search by collection, creator, or filename
- 📦 Support for **STL, 3MF, OBJ, GLB, and glTF** formats
- 🎛️ Filter by file format dropdown
- 💾 Direct model file downloads
- 🔄 Sort by name, size, format, or collection

### 3D Thumbnail Rendering
Automatic thumbnail generation with tiered processing:
- **Fast lane**: Small files (<30MB) — 18+ parallel workers
- **Slow lane**: Large files (>30MB) — dedicated workers with longer timeouts
- Uses [f3d](https://f3d.app/) for high-quality headless rendering (supports all formats)
- Optimized camera angle for miniature models (front view, slight downward angle)
- Fallback to stl-thumb or PIL software renderer when needed

### 3D Model Viewer (Three.js)
- 🎮 **Interactive 3D preview** — View STL, OBJ, 3MF, and GLB models in browser
- 🔄 **Orbit controls** — Rotate, pan, and zoom with mouse/touch
- 💡 **Professional lighting** — Ambient and directional lighting
- 📱 **Responsive** — Works on desktop and mobile

### General
- 🌐 Modern responsive web interface
- 🚀 Fast SQLite database with FTS5 full-text search
- ⚙️ Configurable content roots via web UI
- 🔌 REST API for integrations
- 🐳 Docker support with pre-built images

## Quick Start

### Docker (Recommended)

```bash
# Pull and run
docker pull ghcr.io/diminox-kullwinder/fantasyfolio:latest

# Or use Docker Compose
git clone https://github.com/diminox-kullwinder/fantasyfolio.git
cd fantasyfolio
cp .env.example .env
# Edit .env with your paths
docker compose up -d
```

Open http://localhost:8888 in your browser.

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/diminox-kullwinder/fantasyfolio.git
cd fantasyfolio

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m fantasyfolio.cli run
```

## Configuration

FantasyFolio can be configured via environment variables or a `.env` file:

```bash
cp .env.example .env
nano .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `FANTASYFOLIO_ENV` | Environment (development/production) | development |
| `FANTASYFOLIO_HOST` | Server bind address | 0.0.0.0 |
| `FANTASYFOLIO_PORT` | Server port | 8888 |
| `FANTASYFOLIO_DATABASE_PATH` | SQLite database location | data/fantasyfolio.db |
| `FANTASYFOLIO_PDF_ROOT` | Default PDF library path | (none) |
| `FANTASYFOLIO_3D_ROOT` | Default 3D models path | (none) |
| `FANTASYFOLIO_SECRET_KEY` | Flask secret key | (auto-generated) |
| `FANTASYFOLIO_LOG_LEVEL` | Logging level | INFO |

> **Backward Compatibility**: `DAM_*` environment variables are still supported.

## Usage

### Web Interface

1. Navigate to http://localhost:8888
2. Use the **Settings** (gear icon) to configure your content paths
3. Click **Index** to scan your libraries
4. Browse and search your assets!

### CLI Commands

```bash
# Start web server
python -m fantasyfolio.cli run

# Index PDFs
python -m fantasyfolio.cli index-pdfs /path/to/pdfs

# Index 3D models
python -m fantasyfolio.cli index-models /path/to/models

# Show statistics
python -m fantasyfolio.cli stats

# Compute hashes for deduplication
python -m fantasyfolio.cli compute-hashes

# Detect duplicates
python -m fantasyfolio.cli detect-duplicates
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/health` | GET | Health check |
| `/api/stats` | GET | Overall statistics |
| `/api/assets` | GET | List PDF assets |
| `/api/models` | GET | List 3D models |
| `/api/models/<id>/stl` | GET | Get STL file for 3D viewer |
| `/api/search` | GET | Unified search |
| `/api/settings` | GET/POST | Application settings |

## Project Structure

```
fantasyfolio/
├── fantasyfolio/          # Main Python package
│   ├── api/               # API blueprints
│   ├── core/              # Core business logic
│   ├── indexer/           # Indexing services
│   └── services/          # Background services
├── scripts/               # Utility scripts
│   └── thumbnail_daemon.py
├── tests/                 # Test suite
├── docs/                  # Documentation
├── templates/             # Jinja templates
└── docker-compose.yml     # Docker deployment
```

## Development

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest tests/ -v

# Format code
black fantasyfolio/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/) — Web framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF processing
- [stl-thumb](https://github.com/unlimitedbacon/stl-thumb) — 3D thumbnail rendering
- [Three.js](https://threejs.org/) — In-browser 3D viewer
- [SQLite](https://sqlite.org/) with FTS5 — Database and full-text search
