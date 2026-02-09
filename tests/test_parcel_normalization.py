"""
Tests pour la normalisation des donnees de lots.
Couvre: ParcelData, normalize_orientation, normalize_floor, clean_price, clean_surface.
"""

import pytest
from dataclasses import asdict


# ============================================================
# Tests ParcelData
# ============================================================

class TestParcelData:
    """Tests de la structure de donnees ParcelData."""

    def test_default_values(self, parcel_data):
        assert parcel_data.parcelLabel == ""
        assert parcel_data.parcelTypeId == "appartment"
        assert parcel_data.typology == ""
        assert parcel_data.price == "N.C"
        assert parcel_data.state == "available"
        assert parcel_data.surfaceDetail == {}
        assert parcel_data.customData is None

    def test_default_options(self, parcel_data):
        expected_options = {
            "garden", "terrace", "balcony", "parking",
            "winter garden", "garage", "loggia", "duplex"
        }
        assert set(parcel_data.option.keys()) == expected_options
        assert all(v is False for v in parcel_data.option.values())

    def test_to_dict(self, parcel_data):
        result = asdict(parcel_data)
        assert isinstance(result, dict)
        assert 'parcelLabel' in result
        assert 'option' in result
        assert 'surfaceDetail' in result

    def test_surface_detail_isolation(self):
        """Verifier que les instances ne partagent pas les memes dicts mutables."""
        from architecture_plan_extractor import ParcelData
        p1 = ParcelData()
        p2 = ParcelData()
        p1.surfaceDetail['terrace'] = 10.0
        assert 'terrace' not in p2.surfaceDetail

    def test_option_isolation(self):
        """Verifier que les instances ne partagent pas les memes dicts mutables."""
        from architecture_plan_extractor import ParcelData
        p1 = ParcelData()
        p2 = ParcelData()
        p1.option['garden'] = True
        assert p2.option['garden'] is False


# ============================================================
# Tests normalize_orientation
# ============================================================

class TestNormalizeOrientation:
    """Tests de normalisation des orientations."""

    @pytest.mark.parametrize("input_val, expected", [
        ("N", "N"),
        ("n", "N"),
        ("Nord", "N"),
        ("nord", "N"),
        ("S", "S"),
        ("Sud", "S"),
        ("E", "E"),
        ("Est", "E"),
        ("O", "O"),
        ("Ouest", "O"),
        ("o", "O"),
        ("w", "O"),  # W -> O
    ])
    def test_valid_orientations(self, extractor, input_val, expected):
        result = extractor.normalize_orientation(input_val)
        assert result == expected

    def test_empty_orientation(self, extractor):
        assert extractor.normalize_orientation("") == ""
        assert extractor.normalize_orientation(None) == ""

    def test_unknown_orientation(self, extractor):
        # Valeurs inconnues retournent en majuscule
        result = extractor.normalize_orientation("NE")
        assert result == "NE"


# ============================================================
# Tests normalize_floor
# ============================================================

class TestNormalizeFloor:
    """Tests de normalisation des etages."""

    @pytest.mark.parametrize("input_val, expected", [
        ("RDC", "RDC"),
        ("rdc", "RDC"),
        ("R.D.C", "RDC"),
        ("Rez-de-chaussee", "RDC"),
        ("rez de chaussee", "RDC"),
        ("R+1", "R+1"),
        ("r+1", "R+1"),
        ("R+2", "R+2"),
        ("R+3", "R+3"),
    ])
    def test_valid_floors(self, extractor, input_val, expected):
        result = extractor.normalize_floor(input_val)
        assert result == expected

    def test_empty_floor(self, extractor):
        assert extractor.normalize_floor("") == ""
        assert extractor.normalize_floor(None) == ""

    def test_etage_number(self, extractor):
        result = extractor.normalize_floor("Etage 2")
        assert "2" in result


# ============================================================
# Tests clean_price
# ============================================================

class TestCleanPrice:
    """Tests de nettoyage du prix."""

    @pytest.mark.parametrize("input_val, expected", [
        ("285 000", "285000"),
        ("185,000", "185.000"),
        ("120 500", "120500"),
        ("N.C", "N.C"),
    ])
    def test_clean_price(self, extractor, input_val, expected):
        result = extractor.clean_price(input_val)
        assert result == expected

    def test_empty_price(self, extractor):
        assert extractor.clean_price("") == "N.C"
        assert extractor.clean_price(None) == "N.C"


# ============================================================
# Tests clean_surface
# ============================================================

class TestCleanSurface:
    """Tests de nettoyage des surfaces."""

    @pytest.mark.parametrize("input_val, expected", [
        ("41,72", "41.72"),
        ("65.40", "65.40"),
        ("120,00", "120.00"),
    ])
    def test_clean_surface(self, extractor, input_val, expected):
        result = extractor.clean_surface(input_val)
        assert result == expected

    def test_empty_surface(self, extractor):
        assert extractor.clean_surface("") == ""
        assert extractor.clean_surface(None) == ""


# ============================================================
# Tests detect_options
# ============================================================

class TestDetectOptions:
    """Tests de detection des options dans le texte."""

    def test_detect_terrace(self, extractor):
        options = extractor.detect_options("Grande terrasse exposee sud")
        assert options['terrace'] is True

    def test_detect_balcony(self, extractor):
        options = extractor.detect_options("Avec balcon et vue mer")
        assert options['balcony'] is True

    def test_detect_garden(self, extractor):
        options = extractor.detect_options("Jardin privatif de 50m2")
        assert options['garden'] is True

    def test_detect_parking(self, extractor):
        options = extractor.detect_options("Parking en sous-sol inclus")
        assert options['parking'] is True

    def test_detect_stationnement(self, extractor):
        options = extractor.detect_options("Place de stationnement")
        assert options['parking'] is True

    def test_detect_garage(self, extractor):
        options = extractor.detect_options("Garage box ferme")
        assert options['garage'] is True

    def test_detect_loggia(self, extractor):
        options = extractor.detect_options("Loggia de 6m2")
        assert options['loggia'] is True

    def test_detect_duplex(self, extractor):
        options = extractor.detect_options("T4 duplex sur 2 niveaux")
        assert options['duplex'] is True

    def test_detect_winter_garden(self, extractor):
        options = extractor.detect_options("Jardin d'hiver vitré")
        assert options['winter garden'] is True

    def test_detect_multiple_options(self, extractor):
        text = "T3 avec terrasse, balcon, parking et garage"
        options = extractor.detect_options(text)
        assert options['terrace'] is True
        assert options['balcony'] is True
        assert options['parking'] is True
        assert options['garage'] is True
        assert options['garden'] is False

    def test_detect_no_options(self, extractor):
        options = extractor.detect_options("Studio vide sans rien")
        assert all(v is False for v in options.values())

    def test_case_insensitive(self, extractor):
        options = extractor.detect_options("TERRASSE et BALCON")
        assert options['terrace'] is True
        assert options['balcony'] is True
