"""
Tests pour le pattern matching regex de l'extracteur Tesseract.
Couvre: parcelLabel, typology, floor, living_space, orientation, surfaces, prix.
"""

import pytest


# ============================================================
# Tests extract_field : parcelLabel
# ============================================================

class TestParcelLabelExtraction:
    """Tests d'extraction des references de lots."""

    @pytest.mark.parametrize("text, expected", [
        ("Lot A001 - T3", "A001"),
        ("LOT B102", "B102"),
        ("Reference: C205", "C205"),
        ("Appartement D003 disponible", "D003"),
        ("Lot 042 en vente", "042"),
        ("Lot A01 au RDC", "A01"),
    ])
    def test_parcel_label_found(self, extractor, text, expected):
        result = extractor.extract_field(text, 'parcelLabel')
        assert result == expected

    def test_parcel_label_not_found(self, extractor):
        result = extractor.extract_field("Aucune reference ici", 'parcelLabel')
        assert result is None


# ============================================================
# Tests extract_field : typology
# ============================================================

class TestTypologyExtraction:
    """Tests d'extraction de la typologie (T1-T6, F1-F6)."""

    @pytest.mark.parametrize("text, expected", [
        ("T1 - Studio", "T1"),
        ("Appartement T2", "T2"),
        ("Grand T3 lumineux", "T3"),
        ("T4 familial", "T4"),
        ("T5 de standing", "T5"),
        ("F2 rénové", "F2"),
        ("F3 avec terrasse", "F3"),
        ("2 pièces", "2"),
        ("3 pieces", "3"),
    ])
    def test_typology_found(self, extractor, text, expected):
        result = extractor.extract_field(text, 'typology')
        assert result == expected

    def test_typology_not_found(self, extractor):
        result = extractor.extract_field("Maison sans typologie", 'typology')
        assert result is None


# ============================================================
# Tests extract_field : floor
# ============================================================

class TestFloorExtraction:
    """Tests d'extraction de l'etage."""

    @pytest.mark.parametrize("text, expected", [
        ("RDC", "RDC"),
        ("R.D.C", "R.D.C"),
        ("R+1", "R+1"),
        ("R+2", "R+2"),
        ("R+3", "R+3"),
        ("Étage 2", "Étage 2"),
        ("Etage 1", "Etage 1"),
    ])
    def test_floor_found(self, extractor, text, expected):
        result = extractor.extract_field(text, 'floor')
        assert result is not None
        assert expected in result or result in expected

    def test_floor_not_found(self, extractor):
        result = extractor.extract_field("Pas d'etage mentionne", 'floor')
        assert result is None


# ============================================================
# Tests extract_field : living_space
# ============================================================

class TestLivingSpaceExtraction:
    """Tests d'extraction de la surface habitable."""

    @pytest.mark.parametrize("text, expected", [
        ("41.72 m²", "41.72"),
        ("65,40 m2", "65,40"),
        ("Surface: 89.50", "89.50"),
        ("Habitable: 120,00", "120,00"),
        ("Surface : 55.30 m²", "55.30"),
    ])
    def test_living_space_found(self, extractor, text, expected):
        result = extractor.extract_field(text, 'living_space')
        assert result == expected

    def test_living_space_not_found(self, extractor):
        result = extractor.extract_field("Pas de surface", 'living_space')
        assert result is None


# ============================================================
# Tests extract_field : orientation
# ============================================================

class TestOrientationExtraction:
    """Tests d'extraction de l'orientation."""

    @pytest.mark.parametrize("text, expected", [
        ("Orientation: N", "N"),
        ("Orientation: S", "S"),
        ("Orientation: E", "E"),
        ("Orientation: O", "O"),
        ("Nord", "Nord"),
        ("Sud", "Sud"),
        ("Est", "Est"),
        ("Ouest", "Ouest"),
    ])
    def test_orientation_found(self, extractor, text, expected):
        result = extractor.extract_field(text, 'orientation')
        assert result is not None

    def test_orientation_not_found(self, extractor):
        result = extractor.extract_field("xxx yyy zzz 123", 'orientation')
        assert result is None


# ============================================================
# Tests extract_field : surfaces annexes
# ============================================================

class TestSurfaceExtraction:
    """Tests d'extraction des surfaces annexes."""

    @pytest.mark.parametrize("text, field, expected", [
        ("Terrasse: 12.50 m²", "terrace", "12.50"),
        ("Terrasse 8,30", "terrace", "8,30"),
        ("Balcon: 4.20 m²", "balcony", "4.20"),
        ("Balcon 3,50", "balcony", "3,50"),
        ("Jardin: 45.00 m²", "garden", "45.00"),
        ("Jardin 120,50", "garden", "120,50"),
    ])
    def test_surface_found(self, extractor, text, field, expected):
        result = extractor.extract_field(text, field)
        assert result == expected


# ============================================================
# Tests extract_field : prix
# ============================================================

class TestPriceExtraction:
    """Tests d'extraction du prix."""

    @pytest.mark.parametrize("text, expected_contains", [
        ("Prix: 285 000 €", "285"),
        ("185 000 €", "185"),
        ("Prix: 120.000 €", "120"),
    ])
    def test_price_found(self, extractor, text, expected_contains):
        result = extractor.extract_field(text, 'price')
        assert result is not None
        assert expected_contains in result


# ============================================================
# Tests extract_field : champ inconnu
# ============================================================

class TestUnknownField:
    """Tests pour un champ qui n'existe pas dans les patterns."""

    def test_unknown_field_returns_none(self, extractor):
        result = extractor.extract_field("texte quelconque", 'nonexistent_field')
        assert result is None


# ============================================================
# Test du texte OCR complet
# ============================================================

class TestFullOCRParsing:
    """Tests de parsing complet a partir d'un texte OCR simule."""

    def test_parse_complete_text(self, extractor, sample_ocr_text):
        parcel = extractor.parse_plan(sample_ocr_text)

        assert parcel.parcelLabel == "A001"
        assert parcel.typology == "T3"
        assert "1" in parcel.floor  # R+1 ou equivalent
        assert parcel.living_space == "65.40"
        assert parcel.option['parking'] is True
        assert parcel.option['terrace'] is True
        assert parcel.option['balcony'] is True

    def test_parse_empty_text(self, extractor):
        parcel = extractor.parse_plan("")
        assert parcel.parcelLabel == ""
        assert parcel.typology == ""
        assert parcel.floor == ""
        assert parcel.living_space == ""
        assert parcel.price == "N.C"
