"""
Tests pour l'extracteur PyMuPDF.
"""

import pytest
import os
from pathlib import Path

# Ajouter le repertoire parent au path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.pymupdf_extractor import PyMuPDFExtractor, PyMuPDFExtractionResult


class TestPyMuPDFExtractor:
    """Tests pour PyMuPDFExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Fixture pour creer un extracteur PyMuPDF."""
        return PyMuPDFExtractor()
    
    @pytest.fixture
    def sample_pdf(self):
        """Chemin vers un PDF de test."""
        return str(Path(__file__).parent.parent / "pdfExample" / "B01.pdf")
    
    def test_is_available(self, extractor):
        """Test si PyMuPDF est disponible."""
        assert extractor.is_available() is True
    
    def test_extract_from_pdf(self, extractor, sample_pdf):
        """Test l'extraction d'un PDF."""
        if not os.path.exists(sample_pdf):
            pytest.skip(f"PDF de test non trouve: {sample_pdf}")
        
        result = extractor.extract(sample_pdf)
        
        assert isinstance(result, PyMuPDFExtractionResult)
        assert result.success or result.text != ""
        assert result.metadata.get('page_count') > 0
    
    def test_clean_text(self, extractor):
        """Test le nettoyage du texte."""
        # Texte avec caracteres speciaux
        dirty_text = "Surface\u00A0:\u202F41,72\u00A0m2\n\n\n\n"
        cleaned = extractor._clean_text(dirty_text)
        
        assert '\u00A0' not in cleaned
        assert '\u202F' not in cleaned
        assert 'm2' in cleaned
        # Pas de sauts de ligne multiples
        assert '\n\n\n\n' not in cleaned
    
    def test_parse_parcel_data(self, extractor):
        """Test le parsing des donnees de parcel."""
        text = """
PLAN DE VENTE - Batiment B01

Lot A101 - T2
Surface: 45.20 m2
Etage: RDC
Orientation: Sud-Ouest
Terrasse: 8.50 m2
Parking inclus

Lot A102 - T3
Surface: 62.30 m2
Etage: R+1
"""
        result = extractor._parse_parcel_data(text)
        
        # Verifier que les donnees sont parsees
        assert result is not None
    
    def test_calculate_confidence(self, extractor):
        """Test le calcul de confiance."""
        # Donnees completes
        complete_data = {
            'parcelLabel': 'A101',
            'typology': 'T2',
            'living_space': '45.20',
            'floor': 'RDC',
            'orientation': 'Sud-Ouest',
            'terrace': '8.50',
        }
        confidence = extractor._calculate_confidence(complete_data)
        assert confidence > 0.5
        
        # Donnees incompletes
        incomplete_data = {'parcelLabel': 'A101'}
        confidence = extractor._calculate_confidence(incomplete_data)
        assert confidence < 0.5
        
        # Pas de donnees
        confidence = extractor._calculate_confidence({})
        assert confidence == 0.0
    
    def test_to_parcel_data(self, extractor, sample_pdf):
        """Test la conversion vers ParcelData."""
        if not os.path.exists(sample_pdf):
            pytest.skip(f"PDF de test non trouve: {sample_pdf}")
        
        result = extractor.extract(sample_pdf)
        parcel_data = extractor.to_parcel_data(result)
        
        # Verifier que la conversion fonctionne
        assert parcel_data is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
