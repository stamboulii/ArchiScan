"""
Tests pour le HybridExtractor.
Couvre: detection de phase, routing des methodes, fallback.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ============================================================
# Tests get_current_phase
# ============================================================

class TestGetCurrentPhase:
    """Tests de detection de la phase operationnelle."""

    def test_force_tesseract(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor(force_method='tesseract')
        assert ext.get_current_phase() == 0

    def test_force_claude(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor(force_method='claude')
        assert ext.get_current_phase() == 1

    def test_force_ml(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor(force_method='ml')
        assert ext.get_current_phase() == 3

    def test_auto_fallback_to_tesseract(self):
        """Sans cle API ni modele ML, doit tomber en phase 0."""
        from hybrid_extractor import HybridExtractor
        with patch('hybrid_extractor.HybridExtractor.ml_extractor',
                   new_callable=PropertyMock) as mock_ml, \
             patch('hybrid_extractor.HybridExtractor.claude_extractor',
                   new_callable=PropertyMock) as mock_claude, \
             patch('hybrid_extractor.HybridExtractor.data_store',
                   new_callable=PropertyMock) as mock_store:
            mock_ml.side_effect = Exception("No ML")
            mock_claude.return_value = MagicMock(is_available=MagicMock(return_value=False))
            mock_store.side_effect = Exception("No store")

            ext = HybridExtractor()
            assert ext.get_current_phase() == 0


# ============================================================
# Tests _determine_method
# ============================================================

class TestDetermineMethod:
    """Tests du choix de methode d'extraction."""

    def test_forced_method(self):
        from hybrid_extractor import HybridExtractor

        ext = HybridExtractor(force_method='tesseract')
        assert ext._determine_method() == 'tesseract'

        ext = HybridExtractor(force_method='claude')
        assert ext._determine_method() == 'claude'

        ext = HybridExtractor(force_method='ml')
        assert ext._determine_method() == 'ml'

    def test_auto_method_maps_phases(self):
        from hybrid_extractor import HybridExtractor

        ext = HybridExtractor()

        with patch.object(ext, 'get_current_phase', return_value=0):
            assert ext._determine_method() == 'tesseract'

        with patch.object(ext, 'get_current_phase', return_value=1):
            assert ext._determine_method() == 'claude'

        with patch.object(ext, 'get_current_phase', return_value=2):
            assert ext._determine_method() == 'claude'

        with patch.object(ext, 'get_current_phase', return_value=3):
            assert ext._determine_method() == 'ml'


# ============================================================
# Tests get_phase_description
# ============================================================

class TestGetPhaseDescription:
    """Tests des descriptions de phase pour l'UI."""

    @pytest.mark.parametrize("force_method, expected_phase", [
        ('tesseract', 0),
        ('claude', 1),
        ('ml', 3),
    ])
    def test_phase_descriptions(self, force_method, expected_phase):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor(force_method=force_method)

        with patch.object(ext, 'data_store', new_callable=PropertyMock) as mock:
            mock.side_effect = Exception("No store")
            desc = ext.get_phase_description()

        assert desc['phase'] == expected_phase
        assert 'name' in desc
        assert 'description' in desc
        assert 'method' in desc
        assert 'accuracy' in desc


# ============================================================
# Tests _fallback_extract
# ============================================================

class TestFallbackExtract:
    """Tests du mecanisme de fallback entre extracteurs."""

    def test_fallback_from_claude_to_tesseract(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor()

        mock_result = {'parcelLabel': 'TEST', '_extraction_meta': {'method': 'tesseract'}}

        with patch.object(ext, 'tesseract_extractor') as mock_tess:
            mock_tess.extract_from_image.return_value = mock_result
            result = ext._fallback_extract('/fake/path.png', failed_method='claude')

        assert result['parcelLabel'] == 'TEST'

    def test_fallback_from_tesseract_to_claude(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor()

        mock_result = {'parcelLabel': 'TEST', '_extraction_meta': {'method': 'claude'}}

        with patch.object(ext, 'claude_extractor') as mock_claude:
            mock_claude.is_available.return_value = True
            mock_claude.extract_from_image.return_value = mock_result
            result = ext._fallback_extract('/fake/path.png', failed_method='tesseract')

        assert result['parcelLabel'] == 'TEST'

    def test_all_fallbacks_fail_raises(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor()

        with patch.object(ext, 'claude_extractor') as mock_claude, \
             patch.object(ext, 'tesseract_extractor') as mock_tess:
            mock_claude.is_available.return_value = False
            mock_tess.extract_from_image.side_effect = Exception("OCR failed")

            with pytest.raises(RuntimeError, match="Toutes les methodes"):
                ext._fallback_extract('/fake/path.png', failed_method='ml')


# ============================================================
# Tests auto_validate
# ============================================================

class TestAutoValidate:
    """Tests de l'auto-validation des extractions Claude."""

    def test_auto_validate_flag(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor(auto_validate=True)
        assert ext.auto_validate is True

        ext2 = HybridExtractor(auto_validate=False)
        assert ext2.auto_validate is False

    def test_auto_validate_default_false(self):
        from hybrid_extractor import HybridExtractor
        ext = HybridExtractor()
        assert ext.auto_validate is False
