"""
ArchiExtract - Package Principal
================================

Outil d'extraction automatique de donnees depuis les plans d'architecture.

Modules:
    core: Composants de base (config, exceptions, parcel)
    extractors: Extracteurs (tesseract, claude, ml)
    ui: Interface Streamlit
    ml: Pipeline Machine Learning

Installation:
    pip install -e .

Usage:
    import archiextract
    from archiextract import ArchitecturePlanExtractor
"""

__version__ = "1.0.0"
__author__ = "ArchiExtract Team"

# Imports principaux
from .core.config import (
    get_config,
    get_secrets_manager,
    ensure_directories,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    PROJECT_ROOT,
    TEMP_DIR,
    DEBUG_DIR,
)

from .core.parcel import ParcelData, normalize_parcel_data, validate_parcel_data
from .core.exceptions import (
    ExtractionError,
    ConfigurationError,
    APIError,
    MLError,
)

from .extractors.tesseract_extractor import ArchitecturePlanExtractor

__all__ = [
    # Version
    "__version__",
    # Configuration
    "get_config",
    "get_secrets_manager",
    "ensure_directories",
    "CLAUDE_API_KEY",
    "CLAUDE_MODEL",
    "PROJECT_ROOT",
    "TEMP_DIR",
    "DEBUG_DIR",
    # Parcel
    "ParcelData",
    "normalize_parcel_data",
    "validate_parcel_data",
    # Exceptions
    "ExtractionError",
    "ConfigurationError",
    "APIError",
    "MLError",
    # Extractors
    "ArchitecturePlanExtractor",
]
