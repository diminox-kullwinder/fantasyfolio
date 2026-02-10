"""API blueprints for FantasyFolio."""

from fantasyfolio.api.assets import assets_bp
from fantasyfolio.api.models import models_bp
from fantasyfolio.api.search import search_bp
from fantasyfolio.api.settings import settings_bp
from fantasyfolio.api.indexer import indexer_bp
from fantasyfolio.api.system import system_bp

__all__ = ['assets_bp', 'models_bp', 'search_bp', 'settings_bp', 'indexer_bp', 'system_bp']
