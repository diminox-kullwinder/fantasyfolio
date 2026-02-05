"""API blueprints for DAM."""

from dam.api.assets import assets_bp
from dam.api.models import models_bp
from dam.api.search import search_bp
from dam.api.settings import settings_bp
from dam.api.indexer import indexer_bp

__all__ = ['assets_bp', 'models_bp', 'search_bp', 'settings_bp', 'indexer_bp']
