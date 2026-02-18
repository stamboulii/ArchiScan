"""
Tesseract Extractor - OCR avec Tesseract
========================================

Extracteur base sur Tesseract OCR pour les plans d'architecture.
Phase 0 de la strategie hybride.

Ce module est un wrapper qui utilise la logique existante
d'architecture_plan_extractor.py tout en integrant les nouveaux
composants (core.exceptions, core.parcel).
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
import re
from typing import Dict, Optional, List
from pathlib import Path
from dataclasses import asdict
import logging

from ..core.config import DEBUG_DIR, PROJECT_ROOT, ensure_directories
from ..core.parcel import ParcelData, normalize_parcel_data
from ..core.exceptions import ImageLoadError, ExtractionError

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Patterns regex pour l'extraction
TESSERACT_PATTERNS = {
    'parcelLabel': [
        r'\b([A-Z]\d{3})\b',  # Format A001
        r'\bLot\s*([A-Z]?\d{2,3})\b',  # Lot A01 ou Lot 001
    ],
    'typology': [
        r'\b(T[1-6])\b',  # T1, T2, etc.
        r'\b(F[1-6])\b',  # F1, F2, etc.
        r'\b(\d)\s*pièces?\b',  # 2 pièces
    ],
    'floor': [
        r'\b(RDC|R\.D\.C)\b',  # Rez-de-chaussée
        r'\bRez[- ]de[- ]chauss[ée]e\b',
        r'\b(R\+\d)\b',  # R+1, R+2
        r'\b([ÉE]tage\s*\d+)\b',  # Étage 1
        r'\b(\d)(?:er|ème)\s*[ÉE]tage\b',  # 1er étage
    ],
    'living_space': [
        r'(\d+[.,]\d+)\s*m[²2]',  # 41.72 m²
        r'Surface\s*:\s*(\d+[.,]\d+)',
        r'Habitable\s*:\s*(\d+[.,]\d+)',
    ],
    'orientation': [
        r'\b([NSEO])\b',  # N, S, E, O
        r'\b(Nord|Sud|Est|Ouest)\b',
        r'Orientation\s*:\s*([NSEO]|Nord|Sud|Est|Ouest)',
    ],
    'terrace': [
        r'Terrasse\s*:\s*(\d+[.,]\d+)\s*m[²2]',
        r'Terrasse\s*(\d+[.,]\d+)',
    ],
    'balcony': [
        r'Balcon\s*:\s*(\d+[.,]\d+)\s*m[²2]',
        r'Balcon\s*(\d+[.,]\d+)',
    ],
    'garden': [
        r'Jardin\s*:\s*(\d+[.,]\d+)\s*m[²2]',
        r'Jardin\s*(\d+[.,]\d+)',
    ],
    'parking': [
        r'Parking\s*(?:inclus|boxé|numéroté)?',
    ],
    'price': [
        r'(\d{3,6})\s*(?:€|EUR)',  # 185000 EUR
        r'Prix\s*:\s*(\d+)',
    ],
}


class ArchitecturePlanExtractor:
    """
    Extracteur principal pour les plans d'architecture.
    Utilise Tesseract OCR pour l'extraction du texte.
    """
    
    def __init__(self, tesseract_lang: str = "auto"):
        """
        Args:
            tesseract_lang: Langue Tesseract ('fra', 'eng', 'fra+eng', 'auto')
        """
        self._tesseract_lang = self._detect_tesseract_lang()
        self.patterns = TESSERACT_PATTERNS
        self.option_keywords = self._init_option_keywords()
    
    def _detect_tesseract_lang(self) -> str:
        """Detecte automatiquement la langue Tesseract installee."""
        try:
            available = pytesseract.get_languages(config='')
            if 'fra' in available and 'eng' in available:
                return 'fra+eng'
            elif 'fra' in available:
                return 'fra'
            elif 'eng' in available:
                return 'eng'
            else:
                return 'fra'  # Par defaut
        except Exception as e:
            logger.warning(f"Erreur detection langue Tesseract: {e}")
            return 'fra'
    
    def _init_option_keywords(self) -> Dict[str, list]:
        """Initialise les mots-cles pour la detection des options."""
        return {
            'terrace': ['terrasse', 'terrace'],
            'balcony': ['balcon', 'balcony'],
            'garden': ['jardin', 'garden'],
            'parking': ['parking', 'place de parking'],
            'garage': ['garage'],
            'duplex': ['duplex'],
            'loggia': ['loggia'],
            'winter garden': ['veranda', 'winter garden'],
        }
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Pretraite l'image pour ameliorer la qualite OCR.
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Image pretraitee (numpy array)
        """
        img = cv2.imread(image_path)
        
        if img is None:
            raise ImageLoadError(image_path)
        
        # Conversion en niveaux de gris
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # CLAHE pour ameliorer le contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Binarisation adaptive
        binary = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 3
        )
        
        # Denoising
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        
        return denoised
    
    def extract_text(self, image_path: str) -> str:
        """
        Extraite le texte de l'image avec Tesseract.
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Texte extrait
        """
        # Pretraitement
        processed = self.preprocess_image(image_path)
        
        # Configuration Tesseract
        custom_config = r'--oem 3 --psm 6'
        
        # Extraction OCR
        text = pytesseract.image_to_string(
            processed,
            lang=self._tesseract_lang,
            config=custom_config
        )
        
        return text
    
    def extract_field(self, text: str, field: str) -> str:
        """
        Extrait un champ specifique du texte avec les patterns regex.
        
        Args:
            text: Texte complet
            field: Nom du champ a extraire
            
        Returns:
            Valeur extraite ou chaîne vide
        """
        patterns = self.patterns.get(field, [])
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Retourner le premier groupe capture ou la totalite
                return match.group(1) if match.groups() else match.group(0)
        
        return ""
    
    def parse_plan(self, text: str) -> ParcelData:
        """
        Parse le texte pour extraire les donnees du plan.
        
        Args:
            text: Texte brut de l'OCR
            
        Returns:
            ParcelData avec les donnees extraites
        """
        parcel = ParcelData()
        
        # Extraction des champs simples
        parcel.parcelLabel = self.extract_field(text, 'parcelLabel')
        parcel.typology = self.extract_field(text, 'typology')
        parcel.floor = self.extract_field(text, 'floor')
        parcel.orientation = self.extract_field(text, 'orientation')
        parcel.living_space = self.extract_field(text, 'living_space')
        parcel.price = self.extract_field(text, 'price') or "N.C"
        
        # Extraction des surfaces detaillees
        surface_patterns = {
            'terrace': r'Terrasse\s*:\s*(\d+[.,]\d+)',
            'balcony': r'Balcon\s*:\s*(\d+[.,]\d+)',
            'garden': r'Jardin\s*:\s*(\d+[.,]\d+)',
        }
        
        for key, pattern in surface_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    parcel.surfaceDetail[key] = float(match.group(1).replace(',', '.'))
                except ValueError:
                    pass
        
        # Detection des options
        text_lower = text.lower()
        for option, keywords in self.option_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    parcel.option[option] = True
        
        # Determination du type de bien
        if parcel.typology:
            if parcel.typology.startswith('T') or parcel.typology.startswith('F'):
                parcel.parcelTypeId = 'appartment'
                parcel.parcelTypeLabel = 'appartment'
        
        return parcel
    
    def extract_from_image(self, image_path: str, save_debug: bool = True) -> Dict:
        """
        Extrait les donnees d'une image de plan.
        
        Args:
            image_path: Chemin vers l'image
            save_debug: Sauvegarder les fichiers de debug
            
        Returns:
            Dict avec les donnees extraites
        """
        logger.info(f"Debut extraction: {image_path}")
        
        # Extraction du texte
        text = self.extract_text(image_path)
        
        # Parsing des donnees
        parcel = self.parse_plan(text)
        
        # Sauvegarde du debug
        if save_debug:
            ensure_directories()
            
            # Image pretraitee
            processed = self.preprocess_image(image_path)
            debug_img_path = DEBUG_DIR / f"preprocessed_debug_{Path(image_path).stem}.png"
            cv2.imwrite(str(debug_img_path), processed)
            
            # Texte brut
            debug_text_path = DEBUG_DIR / f"extracted_text_debug_{Path(image_path).stem}.txt"
            with open(debug_text_path, 'w', encoding='utf-8') as f:
                f.write(text)
        
        result = parcel.to_dict()
        result['parcelLabel'] = parcel.parcelLabel
        
        # Ajouter le texte brut pour l'interface debug
        result['_raw_text'] = text if text else ""
        
        logger.info(f"Extraction terminee: {parcel.parcelLabel or 'Lot non detecte'}")
        
        return result
    
    def extract_batch(self, image_paths: list, save_debug: bool = False) -> Dict[str, Dict]:
        """
        Traite plusieurs images en batch.
        
        Args:
            image_paths: Liste des chemins d'images
            save_debug: Sauvegarder les fichiers de debug
            
        Returns:
            Dict {lot_id: donnees}
        """
        results = {}
        
        for i, image_path in enumerate(image_paths):
            logger.info(f"Traitement [{i+1}/{len(image_paths)}]: {image_path}")
            
            try:
                result = self.extract_from_image(image_path, save_debug=save_debug)
                lot_id = result.get('parcelLabel') or Path(image_path).stem
                results[lot_id] = result
            except Exception as e:
                logger.error(f"Erreur lors du traitement de {image_path}: {e}")
                results[Path(image_path).stem] = {
                    'error': str(e),
                    'parcelLabel': Path(image_path).stem
                }
        
        logger.info(f"Batch termine: {len(results)} lots traites")
        
        return results


# Backward compatibility alias
TesseractExtractor = ArchitecturePlanExtractor


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python -m archiextract.extractors.tesseract_extractor <image_path>")
        sys.exit(1)
    
    extractor = ArchitecturePlanExtractor()
    result = extractor.extract_from_image(sys.argv[1])
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
