"""
Architecture Plan Extractor
Outil pour extraire automatiquement les données des plans d'architecture
et les convertir en format JSON structuré
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
import re
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import logging
from config import DEBUG_DIR, PROJECT_ROOT, ensure_directories

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ParcelData:
    """Structure de données pour un lot"""
    parcelLabel: str = ""
    parcelTypeId: str = "appartment"
    parcelTypeLabel: str = "appartment"
    orientation: str = ""
    typology: str = ""
    floor: str = ""
    price: str = "N.C"
    living_space: str = ""
    surfaceDetail: Dict[str, float] = None
    option: Dict[str, bool] = None
    tva: str = ""
    pinel: str = ""
    customData: Optional[Dict] = None
    state: str = "available"

    def __post_init__(self):
        if self.surfaceDetail is None:
            self.surfaceDetail = {}
        if self.option is None:
            self.option = {
                "garden": False,
                "terrace": False,
                "balcony": False,
                "parking": False,
                "winter garden": False,
                "garage": False,
                "loggia": False,
                "duplex": False
            }


class ArchitecturePlanExtractor:
    """Extracteur principal pour les plans d'architecture"""

    def __init__(self):
        # Detection automatique de la langue Tesseract
        self._tesseract_lang = self._detect_tesseract_lang()

        # Patterns regex pour l'extraction
        self.patterns = {
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
            'price': [
                r'Prix\s*:\s*(\d+[\s.,]\d+)\s*€',
                r'(\d+[\s.,]\d+)\s*€',
                r'(\d+\s*\d*)\s*€',
            ],
        }
        
        # Mots-clés pour détecter les options
        self.option_keywords = {
            'terrace': ['terrasse'],
            'balcony': ['balcon'],
            'garden': ['jardin'],
            'parking': ['parking', 'stationnement'],
            'garage': ['garage', 'box'],
            'loggia': ['loggia'],
            'winter garden': ['jardin d\'hiver', 'jardin hiver'],
            'duplex': ['duplex'],
        }

    @staticmethod
    def _detect_tesseract_lang() -> str:
        """
        Detecte automatiquement la meilleure langue Tesseract disponible.
        Prefere le francais ('fra') car les plans sont en francais.
        Fallback vers 'eng' si 'fra' n'est pas installe.

        Returns:
            Code langue Tesseract a utiliser
        """
        try:
            available_langs = pytesseract.get_languages()
            if 'fra' in available_langs:
                logger.info("Tesseract: langue francaise (fra) detectee")
                return 'fra'
            elif 'fra+eng' in available_langs or ('fra' in available_langs and 'eng' in available_langs):
                logger.info("Tesseract: utilisation fra+eng")
                return 'fra+eng'
            else:
                logger.warning(
                    f"Tesseract: langue 'fra' non disponible. "
                    f"Langues disponibles: {available_langs}. "
                    f"Installez le pack francais pour de meilleurs resultats: "
                    f"'sudo apt install tesseract-ocr-fra' (Linux) ou "
                    f"via l'installeur Tesseract (Windows)."
                )
                return 'eng'
        except Exception as e:
            logger.warning(f"Impossible de detecter les langues Tesseract: {e}. Fallback vers 'eng'.")
            return 'eng'

    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Prétraite l'image pour améliorer la qualité de l'OCR
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Image prétraitée en numpy array
        """
        logger.info(f"Prétraitement de l'image: {image_path}")
        
        # Lecture de l'image
        img = cv2.imread(image_path)
        
        if img is None:
            raise ValueError(f"Impossible de charger l'image: {image_path}")
        
        # Conversion en niveaux de gris
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Réduction du bruit
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Amélioration du contraste (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # Binarisation adaptative
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Sauvegarde de l'image prétraitée pour debug
        ensure_directories()
        cv2.imwrite(str(DEBUG_DIR / 'preprocessed_debug.png'), binary)
        
        return binary

    def extract_text_ocr(self, processed_image: np.ndarray) -> str:
        """
        Extrait le texte de l'image avec Tesseract OCR.
        Utilise automatiquement le francais si disponible.

        Args:
            processed_image: Image prétraitée

        Returns:
            Texte extrait
        """
        logger.info(f"Extraction du texte avec OCR (langue: {self._tesseract_lang})...")

        custom_config = f'--oem 3 --psm 6 -l {self._tesseract_lang}'

        # Conversion pour pytesseract
        pil_image = Image.fromarray(processed_image)

        # Extraction du texte
        try:
            text = pytesseract.image_to_string(pil_image, config=custom_config)
        except pytesseract.TesseractError as e:
            logger.warning(f"Erreur Tesseract avec langue '{self._tesseract_lang}': {e}")
            # Fallback vers anglais si la langue configuree echoue
            if self._tesseract_lang != 'eng':
                logger.info("Fallback vers Tesseract en anglais...")
                fallback_config = '--oem 3 --psm 6 -l eng'
                text = pytesseract.image_to_string(pil_image, config=fallback_config)
            else:
                raise

        logger.info(f"Texte extrait ({len(text)} caractères)")
        logger.debug(f"Texte brut:\n{text}")

        return text

    def extract_field(self, text: str, field_name: str) -> Optional[str]:
        """
        Extrait un champ spécifique du texte avec les patterns regex
        
        Args:
            text: Texte à analyser
            field_name: Nom du champ à extraire
            
        Returns:
            Valeur extraite ou None
        """
        if field_name not in self.patterns:
            return None
        
        patterns = self.patterns[field_name]
        if not isinstance(patterns, list):
            patterns = [patterns]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                logger.debug(f"Champ '{field_name}' trouvé: {value}")
                return value.strip()
        
        return None

    def detect_options(self, text: str) -> Dict[str, bool]:
        """
        Détecte la présence des options dans le texte
        
        Args:
            text: Texte à analyser
            
        Returns:
            Dictionnaire des options détectées
        """
        text_lower = text.lower()
        options = {
            "garden": False,
            "terrace": False,
            "balcony": False,
            "parking": False,
            "winter garden": False,
            "garage": False,
            "loggia": False,
            "duplex": False
        }
        
        for option, keywords in self.option_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    options[option] = True
                    logger.debug(f"Option '{option}' détectée")
                    break
        
        return options

    def normalize_orientation(self, orientation: str) -> str:
        """Normalise l'orientation en format court (N, S, E, O)"""
        if not orientation:
            return ""
        
        mapping = {
            'nord': 'N', 'n': 'N',
            'sud': 'S', 's': 'S',
            'est': 'E', 'e': 'E',
            'ouest': 'O', 'o': 'O', 'w': 'O'
        }
        
        return mapping.get(orientation.lower(), orientation.upper())

    def normalize_floor(self, floor: str) -> str:
        """Normalise le format de l'étage"""
        if not floor:
            return ""
        
        floor_lower = floor.lower()
        
        if 'rdc' in floor_lower or 'rez' in floor_lower:
            return 'RDC'
        
        # Extraction du numéro d'étage
        match = re.search(r'(\d+)', floor)
        if match:
            num = match.group(1)
            if 'r+' in floor_lower:
                return f'R+{num}'
            return f'Étage {num}'
        
        return floor

    def clean_price(self, price: str) -> str:
        """Nettoie le format du prix"""
        if not price:
            return "N.C"
        
        # Suppression des espaces dans les nombres
        price = price.replace(' ', '').replace(',', '.')
        return price

    def clean_surface(self, surface: str) -> str:
        """Nettoie le format de la surface"""
        if not surface:
            return ""
        
        # Remplacement de la virgule par un point
        return surface.replace(',', '.')

    def parse_plan(self, text: str) -> ParcelData:
        """
        Parse le texte extrait et crée un objet ParcelData
        
        Args:
            text: Texte extrait du plan
            
        Returns:
            Objet ParcelData rempli
        """
        logger.info("Parsing des données...")
        
        parcel = ParcelData()
        
        # Extraction des champs de base
        parcel.parcelLabel = self.extract_field(text, 'parcelLabel') or ""
        parcel.typology = self.extract_field(text, 'typology') or ""
        parcel.floor = self.normalize_floor(self.extract_field(text, 'floor') or "")
        parcel.orientation = self.normalize_orientation(self.extract_field(text, 'orientation') or "")
        
        # Surface habitable
        living_space = self.extract_field(text, 'living_space')
        parcel.living_space = self.clean_surface(living_space) if living_space else ""
        
        # Prix
        price = self.extract_field(text, 'price')
        parcel.price = self.clean_price(price) if price else "N.C"
        
        # Surfaces détaillées (avec protection contre les valeurs non numeriques)
        surface_fields = {
            'terrace': self.extract_field(text, 'terrace'),
            'balcony': self.extract_field(text, 'balcony'),
            'garden': self.extract_field(text, 'garden'),
        }

        for surface_name, surface_value in surface_fields.items():
            if surface_value:
                try:
                    parcel.surfaceDetail[surface_name] = float(self.clean_surface(surface_value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Surface '{surface_name}' non convertible: '{surface_value}' ({e})")
        
        # Détection des options
        parcel.option = self.detect_options(text)
        
        return parcel

    def extract_from_image(self, image_path: str, save_preprocessed: bool = True) -> Dict:
        """
        Méthode principale : extrait toutes les données d'une image
        
        Args:
            image_path: Chemin vers l'image du plan
            save_preprocessed: Sauvegarder l'image prétraitée
            
        Returns:
            Dictionnaire avec les données extraites
        """
        try:
            # Prétraitement
            processed_image = self.preprocess_image(image_path)
            
            # OCR
            text = self.extract_text_ocr(processed_image)
            
            # Sauvegarde du texte extrait pour debug
            ensure_directories()
            debug_text_path = DEBUG_DIR / 'extracted_text_debug.txt'
            with open(str(debug_text_path), 'w', encoding='utf-8') as f:
                f.write(text)

            # Parsing
            parcel_data = self.parse_plan(text)

            # Conversion en dictionnaire
            result = asdict(parcel_data)
            result['_extraction_meta'] = {
                'method': 'tesseract',
                'confidence': None,
                'raw_text': text[:500]
            }

            logger.info("Extraction terminée avec succès")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {str(e)}", exc_info=True)
            raise

    def extract_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        Traite plusieurs images en lot
        
        Args:
            image_paths: Liste des chemins vers les images
            
        Returns:
            Dictionnaire avec les données de tous les lots
        """
        results = {}
        
        for i, image_path in enumerate(image_paths, 1):
            logger.info(f"Traitement de l'image {i}/{len(image_paths)}: {image_path}")
            
            try:
                data = self.extract_from_image(image_path)
                parcel_label = data.get('parcelLabel', f'LOT_{i:03d}')
                results[parcel_label] = data
            except Exception as e:
                logger.error(f"Erreur pour {image_path}: {str(e)}")
                results[f'ERROR_{i}'] = {"error": str(e), "file": image_path}
        
        return results


def main():
    """Fonction principale pour tester l'extracteur"""
    
    # Exemple d'utilisation
    extractor = ArchitecturePlanExtractor()
    
    # Test avec une seule image
    image_path = str(PROJECT_ROOT / "sample_plan.png")

    try:
        result = extractor.extract_from_image(image_path)

        # Affichage du résultat
        print("\n" + "="*50)
        print("RÉSULTAT DE L'EXTRACTION")
        print("="*50)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Sauvegarde en JSON
        output_path = str(PROJECT_ROOT / "extracted_data.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({result['parcelLabel'] or 'LOT_001': result}, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Données sauvegardées dans: {output_path}")
        
    except Exception as e:
        print(f"\n✗ Erreur: {str(e)}")


if __name__ == "__main__":
    main()
