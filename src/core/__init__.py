"""
Core Module - Composants de base d'ArchiExtract
===============================================

Modules:
    config: Configuration centralisee
    exceptions: Exceptions personalisees
    parcel: Normalisation des donnees de lots
    base_extractor: Classe abstraite pour les extracteurs
"""

from .config import (
    get_config,
    get_secrets_manager,
    ensure_directories,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    PROJECT_ROOT,
    TEMP_DIR,
    DEBUG_DIR,
    TRAINING_DB_PATH,
    TRAINING_IMAGES_DIR,
    ML_MODEL_DIR,
    MIN_VALIDATED_SAMPLES,
    ML_CONFIDENCE_THRESHOLD,
    PHASE_AUTO,
    PHASE_TESSERACT,
    PHASE_CLAUDE,
    PHASE_ML,
    DEFAULT_PHASE,
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_UPLOAD_FORMATS,
)

from .parcel import (
    ParcelData,
    normalize_parcel_data,
    validate_parcel_data,
    normalize_typology,
    normalize_floor,
    normalize_orientation,
    DEFAULT_OPTIONS,
)

from .exceptions import (
    ArchiExtractError,
    ConfigurationError,
    MissingAPIKeyError,
    ExtractionError,
    ImageLoadError,
    PDFConversionError,
    APIError,
    ClaudeAPIError,
    MLError,
    MissingMLDependencyError,
    NoTrainedModelError,
    ValidationError,
)

from .base_extractor import (
    BaseExtractor,
    ExtractionResult,
)

__all__ = [
    # Config
    "get_config",
    "get_secrets_manager",
    "ensure_directories",
    "CLAUDE_API_KEY",
    "CLAUDE_MODEL",
    "CLAUDE_MAX_TOKENS",
    "PROJECT_ROOT",
    "TEMP_DIR",
    "DEBUG_DIR",
    "TRAINING_DB_PATH",
    "TRAINING_IMAGES_DIR",
    "ML_MODEL_DIR",
    "MIN_VALIDATED_SAMPLES",
    "ML_CONFIDENCE_THRESHOLD",
    "PHASE_AUTO",
    "PHASE_TESSERACT",
    "PHASE_CLAUDE",
    "PHASE_ML",
    "DEFAULT_PHASE",
    "SUPPORTED_IMAGE_FORMATS",
    "SUPPORTED_UPLOAD_FORMATS",
    # Parcel
    "ParcelData",
    "normalize_parcel_data",
    "validate_parcel_data",
    "normalize_typology",
    "normalize_floor",
    "normalize_orientation",
    "DEFAULT_OPTIONS",
    # Exceptions
    "ArchiExtractError",
    "ConfigurationError",
    "MissingAPIKeyError",
    "ExtractionError",
    "ImageLoadError",
    "PDFConversionError",
    "APIError",
    "ClaudeAPIError",
    "MLError",
    "MissingMLDependencyError",
    "NoTrainedModelError",
    "ValidationError",
    # Base Extractor
    "BaseExtractor",
    "ExtractionResult",
]
