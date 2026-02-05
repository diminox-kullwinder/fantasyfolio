# Digital Asset Manager (DAM)

A self-hosted web application for managing and browsing digital asset libraries, specifically designed for:
- **RPG PDF collections** (rulebooks, adventures, supplements)
- **3D printable miniatures** (STL, 3MF, OBJ files from Patreon packs)

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
- 🖼️ Preview images from Patreon packs
- 🔎 Search by collection, creator, or filename
- 📦 Support for STL, 3MF, and OBJ formats
- 💾 Direct model file downloads

### 3D Model Viewer (Three.js)
- 🎮 **Interactive 3D preview** - View STL models directly in the browser
- 🔄 **Orbit controls** - Rotate, pan, and zoom with mouse/touch
- 💡 **Professional lighting** - Ambient and directional lighting for best visualization
- 📐 **Grid overlay** - Reference grid for scale context
- 🎨 **Clean rendering** - Anti-aliased WebGL rendering
- 📱 **Responsive** - Works on desktop and mobile browsers

The viewer uses Three.js (r128) with STLLoader and OrbitControls, loaded from CDN for fast startup.

### General
- 🌐 Modern responsive web interface
- 🚀 Fast SQLite database with FTS5 full-text search
- ⚙️ Configurable content roots via web UI
- 📊 Statistics and usage overview
- 🔌 REST API for integrations

## Quick Start

### Prerequisites

- Python 3.10 or higher
- 2GB+ RAM recommended
- Sufficient storage for your asset library

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/dam.git
cd dam

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python -m dam.cli init-db

# Start the server
python -m dam.cli run
```

Open http://localhost:8888 in your browser.

### Configuration

DAM can be configured via environment variables or a `.env` file:

```bash
# Copy the example config
cp config/.env.example .env

# Edit with your settings
nano .env
```

Key configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `DAM_ENV` | Environment (development/production) | development |
| `DAM_HOST` | Server bind address | 0.0.0.0 |
| `DAM_PORT` | Server port | 8888 |
| `DAM_DATABASE_PATH` | SQLite database location | data/dam.db |
| `DAM_PDF_ROOT` | Default PDF library path | (none) |
| `DAM_3D_ROOT` | Default 3D models path | (none) |
| `DAM_SECRET_KEY` | Flask secret key | (auto-generated) |
| `DAM_LOG_LEVEL` | Logging level | INFO |

## Usage

### Web Interface

1. Navigate to http://localhost:8888
2. Use the **Settings** (gear icon) to configure your content paths
3. Click **Index** to scan your libraries
4. Browse and search your assets!

### CLI Commands

```bash
# Initialize database
python -m dam.cli init-db

# Start web server
python -m dam.cli run

# Index PDFs
python -m dam.cli index-pdfs /path/to/pdfs

# Index 3D models
python -m dam.cli index-models /path/to/models

# Show statistics
python -m dam.cli stats
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/stats` | GET | Overall statistics |
| `/api/assets` | GET | List PDF assets |
| `/api/assets/<id>` | GET | Get asset details |
| `/api/assets/<id>/thumbnail` | GET | Get PDF thumbnail |
| `/api/assets/<id>/render/<page>` | GET | Render PDF page as image |
| `/api/models` | GET | List 3D models |
| `/api/models/<id>` | GET | Get model details |
| `/api/models/<id>/preview` | GET | Get model preview image |
| `/api/models/<id>/stl` | GET | **Get STL file for 3D viewer** |
| `/api/models/<id>/download` | GET | Download model file |
| `/api/search` | GET | Unified search |
| `/api/settings` | GET/POST | Application settings |
| `/api/index` | POST | Trigger indexing |

#### 3D Viewer Integration

The web UI includes an interactive Three.js-based STL viewer. When viewing a model:
1. Click "3D Preview" to open the viewer modal
2. The viewer fetches the STL from `/api/models/<id>/stl`
3. Models inside ZIP archives are extracted on-the-fly
4. Use mouse to rotate (drag), zoom (scroll), and pan (right-drag)

See [API Documentation](docs/API.md) for full details.

## Deployment

### Docker (Recommended)

```bash
# Build the image
docker build -t dam .

# Run with Docker Compose
docker-compose up -d
```

### Manual Deployment

For production deployments, use a production WSGI server:

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8888 "dam.app:create_app()"
```

### Nginx Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name dam.example.com;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Development

### Project Structure

```
dam/
├── dam/                    # Main Python package
│   ├── api/               # API blueprints
│   ├── core/              # Core business logic
│   ├── indexer/           # Indexing services
│   └── utils/             # Utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
├── static/                # Static files
├── templates/             # Jinja templates
├── data/                  # Database and schema
├── logs/                  # Application logs
├── thumbnails/            # Generated thumbnails
└── config/                # Configuration templates
```

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=dam
```

### Code Style

This project uses:
- `black` for code formatting
- `flake8` for linting
- `mypy` for type checking

```bash
# Format code
black dam/

# Run linters
flake8 dam/
mypy dam/
```

## Troubleshooting

### Common Issues

**Database locked error**
- Ensure only one indexing process runs at a time
- Check disk space and permissions

**PDF thumbnails not generating**
- Ensure PyMuPDF is installed correctly
- Check that the PDF file is not corrupted

**3D models not found in ZIPs**
- Verify the archive is not corrupted
- Check for supported file extensions (stl, 3mf, obj)

### Logs

Logs are stored in the `logs/` directory:
- `dam.log` - Main application log
- `index_pdf.log` - PDF indexer log
- `index_3d.log` - 3D model indexer log

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linters
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

### Backend
- [Flask](https://flask.palletsprojects.com/) — Web framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF processing and rendering
- [SQLite](https://sqlite.org/) with FTS5 — Database and full-text search
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Gunicorn](https://gunicorn.org/) — Production WSGI server

### 3D Model Processing
- [Three.js](https://threejs.org/) — In-browser 3D model viewer (with STLLoader and OrbitControls)
- [numpy-stl](https://github.com/WoLpH/numpy-stl) — STL file parsing
- [Matplotlib](https://matplotlib.org/) — Server-side thumbnail rendering
- [NumPy](https://numpy.org/) — Numerical computing for 3D operations
