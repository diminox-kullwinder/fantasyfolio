"""
Configuration management for FantasyFolio.

Supports multiple environments: development, staging, production.
Configuration is loaded from environment variables and/or .env files.

Note: For backward compatibility, both FANTASYFOLIO_* and DAM_* env vars are supported.
FANTASYFOLIO_* takes precedence if both are set.
"""

import os
from pathlib import Path
from typing import Optional


def get_env(new_key: str, old_key: str, default: str = "") -> str:
    """Get env var with backward compatibility. New key takes precedence."""
    return os.environ.get(new_key, os.environ.get(old_key, default))


class Config:
    """Base configuration."""
    
    # Application
    APP_NAME = "FantasyFolio"
    APP_VERSION = "0.4.14"
    SECRET_KEY = get_env("FANTASYFOLIO_SECRET_KEY", "DAM_SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = Path(get_env("FANTASYFOLIO_DATA_DIR", "DAM_DATA_DIR", "") or BASE_DIR / "data")
    LOG_DIR = Path(get_env("FANTASYFOLIO_LOG_DIR", "DAM_LOG_DIR", "") or BASE_DIR / "logs")
    THUMBNAIL_DIR = Path(get_env("FANTASYFOLIO_THUMBNAIL_DIR", "DAM_THUMBNAIL_DIR", "") or DATA_DIR / "thumbnails")
    STATIC_DIR = BASE_DIR / "static"
    TEMPLATE_DIR = BASE_DIR / "templates"
    
    # Database
    DATABASE_PATH = Path(get_env("FANTASYFOLIO_DATABASE_PATH", "DAM_DATABASE_PATH", "") or DATA_DIR / "fantasyfolio.db")
    DATABASE_TIMEOUT = int(get_env("FANTASYFOLIO_DATABASE_TIMEOUT", "DAM_DATABASE_TIMEOUT", "30"))
    
    # Content roots (can be overridden by database settings)
    PDF_ROOT = get_env("FANTASYFOLIO_PDF_ROOT", "DAM_PDF_ROOT", "")
    MODELS_3D_ROOT = get_env("FANTASYFOLIO_3D_ROOT", "DAM_3D_ROOT", "")
    SMB_PATHS = get_env("FANTASYFOLIO_SMB_PATHS", "DAM_SMB_PATHS", "")  # Comma-separated
    
    # Server
    HOST = get_env("FANTASYFOLIO_HOST", "DAM_HOST", "0.0.0.0")
    PORT = int(get_env("FANTASYFOLIO_PORT", "DAM_PORT", "8888"))
    DEBUG = False
    TESTING = False
    
    # Indexing
    INDEX_BATCH_SIZE = int(get_env("FANTASYFOLIO_INDEX_BATCH_SIZE", "DAM_INDEX_BATCH_SIZE", "100"))
    THUMBNAIL_SIZE = (200, 280)  # Width, Height
    
    # Logging
    LOG_LEVEL = get_env("FANTASYFOLIO_LOG_LEVEL", "DAM_LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    @classmethod
    def init_dirs(cls):
        """Ensure required directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        (cls.THUMBNAIL_DIR / "pdf").mkdir(exist_ok=True)
        (cls.THUMBNAIL_DIR / "3d").mkdir(exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    TEMPLATES_AUTO_RELOAD = True


class StagingConfig(Config):
    """Staging configuration."""
    DEBUG = False
    LOG_LEVEL = "INFO"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = "WARNING"
    
    def __init__(self):
        # Validate production requirements
        if self.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError("FANTASYFOLIO_SECRET_KEY must be set in production")


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    DATABASE_PATH = Path(":memory:")


# Configuration mapping
config_map = {
    "development": DevelopmentConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(env: Optional[str] = None) -> Config:
    """Get configuration for the specified environment."""
    if env is None:
        env = get_env("FANTASYFOLIO_ENV", "DAM_ENV", "development")
    
    config_class = config_map.get(env.lower(), DevelopmentConfig)
    return config_class()
