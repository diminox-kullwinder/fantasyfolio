"""
Flask application factory for FantasyFolio.

Creates and configures the Flask application with blueprints,
error handlers, and middleware.
"""

import os
import logging
from pathlib import Path
from flask import Flask, jsonify, render_template

from fantasyfolio.config import get_config, Config


def create_app(config: Config = None) -> Flask:
    """Application factory for creating Flask app."""
    
    if config is None:
        config = get_config()
    
    # Initialize directories
    config.init_dirs()
    
    # Create Flask app
    app = Flask(
        __name__,
        static_folder=str(config.STATIC_DIR),
        template_folder=str(config.TEMPLATE_DIR)
    )
    
    # Load configuration
    app.config.from_object(config)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    
    # Configure logging
    configure_logging(app, config)
    
    # Initialize database
    from fantasyfolio.core.database import init_db, get_db
    with app.app_context():
        init_db()
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        try:
            # Check database connection
            db = get_db()
            with db.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'version': config.APP_VERSION
            })
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500
    
    # Main UI route
    @app.route('/')
    def index():
        """Serve the main UI."""
        return render_template('index.html')
    
    app.logger.info(f"FantasyFolio initialized (env: {os.environ.get('FANTASYFOLIO_ENV', 'development')})")
    
    return app


def configure_logging(app: Flask, config: Config):
    """Configure application logging."""
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_DIR / 'dam.log')
        ]
    )
    
    # Set Flask logger level
    app.logger.setLevel(log_level)
    
    # Reduce noise from werkzeug in production
    if not config.DEBUG:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)


def register_blueprints(app: Flask):
    """Register all API blueprints."""
    from fantasyfolio.api.assets import assets_bp
    from fantasyfolio.api.models import models_bp
    from fantasyfolio.api.search import search_bp
    from fantasyfolio.api.settings import settings_bp
    from fantasyfolio.api.indexer import indexer_bp
    from fantasyfolio.api.system import system_bp
    
    app.register_blueprint(assets_bp, url_prefix='/api')
    app.register_blueprint(models_bp, url_prefix='/api')
    app.register_blueprint(search_bp, url_prefix='/api')
    app.register_blueprint(settings_bp, url_prefix='/api')
    app.register_blueprint(indexer_bp, url_prefix='/api')
    app.register_blueprint(system_bp, url_prefix='/api')


def register_error_handlers(app: Flask):
    """Register error handlers."""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found', 'message': str(error)}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.exception(f"Unhandled exception: {error}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


def register_cli_commands(app: Flask):
    """Register CLI commands."""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database."""
        from fantasyfolio.core.database import init_db
        init_db()
        print("Database initialized.")
    
    @app.cli.command('index-pdfs')
    def index_pdfs_command():
        """Index PDF files."""
        from fantasyfolio.indexer.pdf import PDFIndexer
        indexer = PDFIndexer()
        indexer.run()
    
    @app.cli.command('index-models')
    def index_models_command():
        """Index 3D model files."""
        from fantasyfolio.indexer.models3d import ModelsIndexer
        indexer = ModelsIndexer()
        indexer.run()
