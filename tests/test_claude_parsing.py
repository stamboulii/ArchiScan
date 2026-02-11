"""
Tests pour le parsing des reponses Claude Vision.
Couvre: _parse_claude_response, _normalize_parcel, _encode_image.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ============================================================
# Tests _parse_claude_response
# ============================================================

class TestParseClaudeResponse:
    """Tests du parsing JSON des reponses Claude."""

    @pytest.fixture
    def claude_extractor(self):
        from claude_vision_extractor import ClaudeVisionExtractor
        return ClaudeVisionExtractor(api_key="test-key")

    def test_parse_valid_json(self, claude_extractor, sample_claude_response):
        result = claude_extractor._parse_claude_response(sample_claude_response)
        assert 'parcels' in result
        assert result['confidence'] == 0.95
        assert len(result['parcels']) == 1
        assert result['parcels'][0]['parcelLabel'] == 'A001'

    def test_parse_json_with_markdown_code_block(self, claude_extractor, sample_claude_response):
        wrapped = f"```json\n{sample_claude_response}\n```"
        result = claude_extractor._parse_claude_response(wrapped)
        assert 'parcels' in result

    def test_parse_json_with_surrounding_text(self, claude_extractor, sample_claude_response):
        wrapped = f"Voici le resultat:\n{sample_claude_response}\nFin."
        result = claude_extractor._parse_claude_response(wrapped)
        assert 'parcels' in result

    def test_parse_invalid_json_raises(self, claude_extractor):
        with pytest.raises(ValueError, match="Aucun JSON"):
            claude_extractor._parse_claude_response("Pas du JSON du tout")

    def test_parse_empty_string_raises(self, claude_extractor):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            claude_extractor._parse_claude_response("")

    def test_parse_malformed_json_raises(self, claude_extractor):
        with pytest.raises(ValueError):
            claude_extractor._parse_claude_response("{invalid: json, }")


# ============================================================
# Tests _normalize_parcel
# ============================================================

class TestNormalizeParcel:
    """Tests de normalisation des donnees brutes en ParcelData."""

    @pytest.fixture
    def claude_extractor(self):
        from claude_vision_extractor import ClaudeVisionExtractor
        return ClaudeVisionExtractor(api_key="test-key")

    def test_normalize_complete_parcel(self, claude_extractor, sample_parcel_dict):
        result = claude_extractor._normalize_parcel(sample_parcel_dict)
        assert result['parcelLabel'] == "A001"
        assert result['typology'] == "T3"
        assert result['floor'] == "R+1"
        assert result['price'] == "285000"
        assert result['living_space'] == "65.40"
        assert result['surfaceDetail']['terrace'] == 12.5

    def test_normalize_empty_parcel(self, claude_extractor):
        result = claude_extractor._normalize_parcel({})
        assert result['parcelLabel'] == ""
        assert result['price'] == "N.C"
        assert result['state'] == "available"
        assert result['parcelTypeId'] == "appartment"
        # Options doivent etre initialisees
        assert isinstance(result['option'], dict)
        assert len(result['option']) == 8

    def test_normalize_surface_detail_types(self, claude_extractor):
        raw = {"surfaceDetail": {"terrace": "12.5", "balcony": 4, "garden": "abc"}}
        result = claude_extractor._normalize_parcel(raw)
        assert result['surfaceDetail']['terrace'] == 12.5
        assert result['surfaceDetail']['balcony'] == 4.0
        # "abc" est ignore (non convertible)
        assert 'garden' not in result['surfaceDetail']

    def test_normalize_surface_detail_empty_values(self, claude_extractor):
        raw = {"surfaceDetail": {"terrace": "", "balcony": None, "garden": 0}}
        result = claude_extractor._normalize_parcel(raw)
        # Toutes sont filtrees (vides/None/0)
        assert result['surfaceDetail'] == {}

    def test_normalize_options_merge(self, claude_extractor):
        raw = {"option": {"terrace": True, "parking": True}}
        result = claude_extractor._normalize_parcel(raw)
        assert result['option']['terrace'] is True
        assert result['option']['parking'] is True
        # Les options non specifiees restent False
        assert result['option']['garden'] is False
        assert result['option']['duplex'] is False

    def test_normalize_preserves_custom_data(self, claude_extractor):
        raw = {"customData": {"notes": "RAS"}}
        result = claude_extractor._normalize_parcel(raw)
        assert result['customData'] == {"notes": "RAS"}


# ============================================================
# Tests _encode_image
# ============================================================

class TestEncodeImage:
    """Tests de l'encodage d'images en base64."""

    @pytest.fixture
    def claude_extractor(self):
        from claude_vision_extractor import ClaudeVisionExtractor
        return ClaudeVisionExtractor(api_key="test-key")

    def test_encode_valid_image(self, claude_extractor, tmp_image):
        data, media_type = claude_extractor._encode_image(tmp_image)
        assert isinstance(data, str)
        assert len(data) > 0
        assert media_type == 'image/png'

    def test_encode_nonexistent_image_raises(self, claude_extractor):
        with pytest.raises(FileNotFoundError):
            claude_extractor._encode_image("/nonexistent/path.png")

    def test_encode_empty_file_raises(self, claude_extractor, tmp_path):
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")
        with pytest.raises(ValueError, match="vide"):
            claude_extractor._encode_image(str(empty_file))

    def test_media_type_mapping(self, claude_extractor, tmp_path):
        """Verifier les types MIME pour differentes extensions."""
        test_cases = {
            'test.png': 'image/png',
            'test.jpg': 'image/jpeg',
            'test.jpeg': 'image/jpeg',
            'test.gif': 'image/gif',
            'test.webp': 'image/webp',
        }
        for filename, expected_type in test_cases.items():
            img_path = tmp_path / filename
            img_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            data, media_type = claude_extractor._encode_image(str(img_path))
            assert media_type == expected_type, f"Expected {expected_type} for {filename}"


# ============================================================
# Tests is_available
# ============================================================

class TestIsAvailable:
    """Tests de disponibilite de Claude Vision."""

    def test_available_with_key(self):
        from claude_vision_extractor import ClaudeVisionExtractor
        from unittest.mock import patch
        
        # Patch the config to have a valid API key
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = "sk-test-key"
            ext = ClaudeVisionExtractor(api_key="sk-test-key")
            assert ext.is_available() is True

    def test_not_available_without_key(self):
        from claude_vision_extractor import ClaudeVisionExtractor
        from unittest.mock import patch
        
        # Patch the config to have no API key (need to patch the singleton's config too)
        with patch('config._config') as mock_config, \
             patch('config._secrets_manager._config') as mock_singleton_config:
            mock_config.claude_api_key = ""
            mock_singleton_config.claude_api_key = ""
            ext = ClaudeVisionExtractor(api_key='')
            assert ext.is_available() is False
