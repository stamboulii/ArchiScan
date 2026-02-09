"""
Tests pour la configuration Pydantic.
Couvre: validation des valeurs, variables d'environnement, valeurs par defaut.
"""

import os
import pytest
from pathlib import Path


# ============================================================
# Tests AppConfig
# ============================================================

class TestAppConfig:
    """Tests du modele de configuration Pydantic."""

    def test_default_values(self):
        from config import AppConfig
        cfg = AppConfig()
        assert cfg.claude_model == "claude-sonnet-4-5-20250514"
        assert cfg.claude_max_tokens == 4096
        assert cfg.min_confidence == 0.8
        assert cfg.min_validated_samples == 300
        assert cfg.ml_confidence_threshold == 0.85
        assert cfg.tesseract_lang == "auto"

    def test_custom_values(self):
        from config import AppConfig
        cfg = AppConfig(
            claude_api_key="sk-test-key",
            claude_model="claude-3-haiku-20240307",
            claude_max_tokens=2048,
            min_confidence=0.5,
            min_validated_samples=100,
            ml_confidence_threshold=0.90,
            tesseract_lang="fra",
        )
        assert cfg.claude_api_key == "sk-test-key"
        assert cfg.claude_model == "claude-3-haiku-20240307"
        assert cfg.claude_max_tokens == 2048
        assert cfg.min_confidence == 0.5
        assert cfg.min_validated_samples == 100
        assert cfg.ml_confidence_threshold == 0.90
        assert cfg.tesseract_lang == "fra"

    def test_confidence_range_validation(self):
        from config import AppConfig
        # Valeurs valides
        AppConfig(min_confidence=0.0)
        AppConfig(min_confidence=1.0)
        AppConfig(min_confidence=0.5)

        # Valeurs invalides
        with pytest.raises(ValueError):
            AppConfig(min_confidence=-0.1)
        with pytest.raises(ValueError):
            AppConfig(min_confidence=1.5)

    def test_ml_threshold_range_validation(self):
        from config import AppConfig
        AppConfig(ml_confidence_threshold=0.0)
        AppConfig(ml_confidence_threshold=1.0)

        with pytest.raises(ValueError):
            AppConfig(ml_confidence_threshold=-0.1)
        with pytest.raises(ValueError):
            AppConfig(ml_confidence_threshold=2.0)

    def test_max_tokens_positive(self):
        from config import AppConfig
        with pytest.raises(ValueError):
            AppConfig(claude_max_tokens=0)
        with pytest.raises(ValueError):
            AppConfig(claude_max_tokens=-100)

    def test_min_samples_positive(self):
        from config import AppConfig
        with pytest.raises(ValueError):
            AppConfig(min_validated_samples=-1)

    def test_tesseract_lang_valid_values(self):
        from config import AppConfig
        for lang in ["auto", "fra", "eng", "fra+eng"]:
            cfg = AppConfig(tesseract_lang=lang)
            assert cfg.tesseract_lang == lang


# ============================================================
# Tests ensure_directories
# ============================================================

class TestEnsureDirectories:
    """Tests de creation des repertoires."""

    def test_ensure_directories_creates(self, tmp_path):
        from config import ensure_directories

        # ensure_directories utilise les chemins globaux,
        # donc on verifie juste que la fonction ne crash pas
        ensure_directories()

    def test_ensure_directories_idempotent(self):
        from config import ensure_directories
        # Appeler 2 fois ne doit pas poser de probleme
        ensure_directories()
        ensure_directories()


# ============================================================
# Tests des constantes de base
# ============================================================

class TestConstants:
    """Tests des constantes du module config."""

    def test_project_root_exists(self):
        from config import PROJECT_ROOT
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_supported_formats(self):
        from config import SUPPORTED_IMAGE_FORMATS, SUPPORTED_UPLOAD_FORMATS
        assert '.png' in SUPPORTED_IMAGE_FORMATS
        assert '.jpg' in SUPPORTED_IMAGE_FORMATS
        assert 'png' in SUPPORTED_UPLOAD_FORMATS
        assert 'pdf' in SUPPORTED_UPLOAD_FORMATS

    def test_phase_constants(self):
        from config import PHASE_AUTO, PHASE_TESSERACT, PHASE_CLAUDE, PHASE_ML
        assert PHASE_AUTO == "auto"
        assert PHASE_TESSERACT == "tesseract"
        assert PHASE_CLAUDE == "claude"
        assert PHASE_ML == "ml"
