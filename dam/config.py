"""
Configuration management for DAM.

Supports multiple environments: development, staging, production.
Configuration is loaded from environment variables and/or .env files.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Base configuration."""
    
    # Application
    APP_NAME = "Digital Asset Manager"
    APP_VERSION = "1.0.0"
    SECRET_KEY = os.environ.get("DAM_SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = Path(os.environ.get("DAM_DATA_DIR", BASE_DIR / "data"))
    LOG_DIR = Path(os.environ.get("DAM_LOG_DIR", BASE_DIR / "logs"))
    THUMBNAIL_DIR = Path(os.environ.get("DAM_THUMBNAIL_DIR", BASE_DIR / "thumbnails"))
    STATIC_DIR = BASE_DIR / "static"
    TEMPLATE_DIR = BASE_DIR / "templates"
    
    # Database
    DATABASE_PATH = Path(os.environ.get("DAM_DATABASE_PATH", DATA_DIR / "dam.db"))
    DATABASE_TIMEOUT = int(os.environ.get("DAM_DATABASE_TIMEOUT", "30"))
    
    # Content roots (can be overridden by database settings)
    PDF_ROOT = os.environ.get("DAM_PDF_ROOT", "")
    MODELS_3D_ROOT = os.environ.get("DAM_3D_ROOT", "")
    SMB_PATHS = os.environ.get("DAM_SMB_PATHS", "")  # Comma-separated
    
    # Server
    HOST = os.environ.get("DAM_HOST", "0.0.0.0")
    PORT = int(os.environ.get("DAM_PORT", "8888"))
    DEBUG = False
    TESTING = False
    
    # Indexing
    INDEX_BATCH_SIZE = int(os.environ.get("DAM_INDEX_BATCH_SIZE", "100"))
    THUMBNAIL_SIZE = (200, 280)  # Width, Height
    
    # Logging
    LOG_LEVEL = os.environ.get("DAM_LOG_LEVEL", "INFO")
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
            raise ValueError("DAM_SECRET_KEY must be set in production")


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
        env = os.environ.get("DAM_ENV", "development")
    
    config_class = config_map.get(env.lower(), DevelopmentConfig)
    return config_class()
