"""
Configuration centralisee pour ArchiExtract.
Tous les chemins, cles API et constantes en un seul endroit.
Validation avec Pydantic. Supporte les variables d'environnement (prefixe ARCHI_).
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# Repertoire racine du projet (ou se trouve ce fichier)
PROJECT_ROOT = Path(__file__).parent.resolve()


# ============================================================
# Modele de configuration valide par Pydantic
# ============================================================

class AppConfig(BaseModel):
    """
    Configuration de l'application ArchiExtract.
    Toutes les valeurs sont validees au chargement.

    Les variables d'environnement sont lues avec le prefixe ARCHI_:
      ARCHI_CLAUDE_API_KEY, ARCHI_CLAUDE_MODEL, etc.
    Ou via les noms historiques: ANTHROPIC_API_KEY.
    """

    # Claude API - OBLIGATOIRE pour Phase 1+
    # Ne pas mettre de valeur par defaut! Doit etre fourni via variable d'environnement
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096

    # Seuils
    min_confidence: float = 0.8
    min_validated_samples: int = 300
    ml_confidence_threshold: float = 0.85

    # Tesseract
    tesseract_lang: str = "auto"  # "auto", "fra", "eng", "fra+eng"

    # Chemins (optionnels, calcules depuis PROJECT_ROOT si absents)
    temp_dir: Optional[str] = None
    debug_dir: Optional[str] = None
    training_db_path: Optional[str] = None
    training_images_dir: Optional[str] = None
    ml_model_dir: Optional[str] = None

    @field_validator('min_confidence', 'ml_confidence_threshold')
    @classmethod
    def check_confidence_range(cls, v, info):
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                f"{info.field_name} doit etre entre 0.0 et 1.0, recu: {v}"
            )
        return v

    @field_validator('claude_max_tokens')
    @classmethod
    def check_max_tokens_positive(cls, v):
        if v <= 0:
            raise ValueError(f"claude_max_tokens doit etre > 0, recu: {v}")
        return v

    @field_validator('min_validated_samples')
    @classmethod
    def check_min_samples_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"min_validated_samples doit etre >= 0, recu: {v}")
        return v

    @field_validator('claude_api_key')
    @classmethod
    def check_api_key_required(cls, v):
        """Verifie que la cle API Claude est fournie."""
        if not v or not v.strip():
            raise ValueError(
                "La cle API Claude est obligatoire. "
                "Configurez-la via la variable d'environnement ARCHI_CLAUDE_API_KEY "
                "ou creez un fichier .env a la racine du projet."
            )
        return v.strip()


# ============================================================
# Chargement de la configuration
# ============================================================

def _load_config() -> AppConfig:
    """
    Charge la configuration depuis les variables d'environnement.
    Supporte le prefixe ARCHI_ et les noms historiques.
    """
    env_values = {}

    # Cle API : ARCHI_CLAUDE_API_KEY ou ANTHROPIC_API_KEY
    api_key = os.environ.get("ARCHI_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        env_values['claude_api_key'] = api_key

    # Modele Claude
    model = os.environ.get("ARCHI_CLAUDE_MODEL")
    if model:
        env_values['claude_model'] = model

    # Max tokens
    max_tokens = os.environ.get("ARCHI_CLAUDE_MAX_TOKENS")
    if max_tokens:
        env_values['claude_max_tokens'] = int(max_tokens)

    # Seuils
    min_conf = os.environ.get("ARCHI_MIN_CONFIDENCE")
    if min_conf:
        env_values['min_confidence'] = float(min_conf)

    min_samples = os.environ.get("ARCHI_MIN_VALIDATED_SAMPLES")
    if min_samples:
        env_values['min_validated_samples'] = int(min_samples)

    ml_threshold = os.environ.get("ARCHI_ML_CONFIDENCE_THRESHOLD")
    if ml_threshold:
        env_values['ml_confidence_threshold'] = float(ml_threshold)

    # Tesseract
    tess_lang = os.environ.get("ARCHI_TESSERACT_LANG")
    if tess_lang:
        env_values['tesseract_lang'] = tess_lang

    return AppConfig(**env_values)


# Singleton de configuration
_config = _load_config()


# ============================================================
# Variables retro-compatibles (utilises dans tout le projet)
# ============================================================

# Repertoire temporaire (adapte a l'OS)
TEMP_DIR = Path(_config.temp_dir) if _config.temp_dir else Path(tempfile.gettempdir()) / "archiextract"

# Repertoire pour les fichiers de debug
DEBUG_DIR = Path(_config.debug_dir) if _config.debug_dir else PROJECT_ROOT / "debug_output"

# Base de donnees d'entrainement
TRAINING_DB_PATH = Path(_config.training_db_path) if _config.training_db_path else PROJECT_ROOT / "training_data.db"
TRAINING_IMAGES_DIR = Path(_config.training_images_dir) if _config.training_images_dir else PROJECT_ROOT / "training_images"

# Repertoire du modele ML
ML_MODEL_DIR = Path(_config.ml_model_dir) if _config.ml_model_dir else PROJECT_ROOT / "ml_models"

# Configuration Claude API
CLAUDE_API_KEY = _config.claude_api_key
CLAUDE_MODEL = _config.claude_model
CLAUDE_MAX_TOKENS = _config.claude_max_tokens

# Constantes de phase
PHASE_AUTO = "auto"
PHASE_TESSERACT = "tesseract"
PHASE_CLAUDE = "claude"
PHASE_PYMUPDF = "pymupdf"
PHASE_ML = "ml"
PHASE_SUPER = "super"  # SuperExtractor: PyMuPDF + OCR + Validation
DEFAULT_PHASE = PHASE_AUTO

# Seuils d'entrainement
MIN_VALIDATED_SAMPLES = _config.min_validated_samples
ML_CONFIDENCE_THRESHOLD = _config.ml_confidence_threshold

# Formats supportes
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
SUPPORTED_UPLOAD_FORMATS = ['png', 'jpg', 'jpeg', 'pdf']


def ensure_directories():
    """Cree les repertoires necessaires s'ils n'existent pas."""
    for d in [TEMP_DIR, DEBUG_DIR, TRAINING_IMAGES_DIR, ML_MODEL_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_config() -> AppConfig:
    """Retourne la configuration actuelle (singleton)."""
    return _config


def reload_config() -> AppConfig:
    """Recharge la configuration depuis les variables d'environnement."""
    global _config
    _config = _load_config()
    return _config


# =============================================================================
# Gestionnaire de Secrets - Securite Avancee
# =============================================================================

class SecretsManager:
    """
    Gestionnaire de secrets pour ArchiExtract.
    Fournit des方法 securisees pour acceder aux credentials.
    
    Fonctionnalites:
    - Masquage des secrets dans les logs
    - Audit des acces aux credentials
    - Validation de la presence des secrets requis
    """
    
    # Secrets requis pour chaque phase
    REQUIRED_SECRETS = {
        'claude': ['claude_api_key'],
        'tesseract': [],  # Pas de secret pour Tesseract local
    }
    
    def __init__(self):
        self._config = _config
        self._audit_log = []
    
    def _mask_secret(self, secret: str, visible_chars: int = 4) -> str:
        """
        Masque un secret pour l'affichage securise.
        
        Args:
            secret: Le secret a masquer
            visible_chars: Nombre de caracteres visibles a la fin
            
        Returns:
            Secret masque (ex: "sk-ant-****-abcd")
        """
        if not secret or len(secret) <= visible_chars:
            return "****"
        return secret[:visible_chars] + "****"
    
    def get_claude_api_key(self) -> str:
        """
        Recupere la cle API Claude de maniere securisee.
        
        Returns:
            La cle API Claude
            
        Raises:
            ValueError: Si la cle n'est pas configuree
        """
        secret = self._config.claude_api_key
        if not secret:
            logger.error("Tentative d'acces a la cle API Claude non configuree")
            raise ValueError(
                "La cle API Claude n'est pas configuree. "
                "Definissez ARCHI_CLAUDE_API_KEY dans votre fichier .env"
            )
        
        # Audit log (sans reveler le secret complet)
        masked = self._mask_secret(secret)
        self._audit_log.append({
            'timestamp': str(Path(__file__).resolve()),
            'action': 'get_claude_api_key',
            'source': 'config',
            'masked_key': masked
        })
        logger.info(f"[AUDIT] Acces a la cle API Claude autorise (cle: {masked})")
        
        return secret
    
    def validate_all_secrets(self, required_level: str = 'claude') -> bool:
        """
        Valide que tous les secrets requis sont presentes.
        
        Args:
            required_level: Niveau de securite requis ('claude', 'tesseract')
            
        Returns:
            True si tous les secrets sont presents
            
        Raises:
            ValueError: Si un secret requis est manquant
        """
        required = self.REQUIRED_SECRETS.get(required_level, [])
        missing = []
        
        for secret_name in required:
            value = getattr(self._config, secret_name, None)
            if not value:
                missing.append(secret_name)
        
        if missing:
            error_msg = (
                f"Secrets manquants pour le niveau '{required_level}': {missing}. "
                f"Veuillez configurer les variables d'environnement: {', '.join(missing)}"
            )
            logger.error(f"[AUDIT] ECHEC de validation des secrets: {missing}")
            raise ValueError(error_msg)
        
        logger.info(f"[AUDIT] Validation des secrets reussie pour le niveau '{required_level}'")
        return True
    
    def get_audit_log(self) -> list:
        """Retourne l'historique des acces aux secrets."""
        return self._audit_log.copy()
    
    def clear_audit_log(self):
        """Vide l'historique des acces aux secrets."""
        self._audit_log.clear()


# Singleton du gestionnaire de secrets
_secrets_manager = SecretsManager()


def get_secrets_manager() -> SecretsManager:
    """Retourne le gestionnaire de secrets (singleton)."""
    return _secrets_manager
