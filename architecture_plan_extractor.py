"""
Architecture Plan Extractor
Outil pour extraire automatiquement les données des plans d'architecture
et les convertir en format JSON structuré
"""

import os
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

# Configuration TESSDATA_PREFIX pour Tesseract (Windows scoop)
tesseract_path = r"C:\Users\MSI\scoop\apps\tesseract\current"
tessdata_path = os.path.join(tesseract_path, "tessdata")
if os.path.exists(tessdata_path):
    os.environ["TESSDATA_PREFIX"] = tessdata_path
    # Configurer pytesseract pour utiliser le bon chemin
    pytesseract.pytesseract.tesseract_cmd = os.path.join(tesseract_path, "tesseract.exe")

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

        # Classe de caractères pour le symbole m² (gère les encodages cassés)
        # PyMuPDF/Tesseract produisent: ² (\u00b2), 2, ° (\u00b0), \uFFFD (replacement char)
        self._m2_pattern = r'm[²2°\uFFFD]'

        # Patterns regex pour l'extraction
        self.patterns = {
            'parcelLabel': [
                r'Appartement\s*[:\-]?\s*([A-Z]\d{2,4})',  # Appartement B01, Appartement: A001
                r'\b([A-Z]\d{2,4})\b',  # Format B01, A001, B24
                r'\bLot\s*[:\-]?\s*([A-Z]?\d{2,4})\b',  # Lot B01, Lot 001, Lot: A23
            ],
            'typology': [
                r'\b(T[1-6])\b',  # T1, T2, etc.
                r'\b(F[1-6])\b',  # F1, F2, etc.
                r'[Tt]ype\s*[:\-]?\s*(\d)',  # Type 4, Type: 3, -Type\n4
                r'\b(\d)\s*(?:pièces?|pieces?|pi[eè]ces?)\b',  # 2 pièces, 3 pieces
            ],
            'floor': [
                r'\b(RDC|R\.D\.C\.?)\b',  # Rez-de-chaussée
                r'\bRez[- ]?de[- ]?chauss[ée]e\b',
                r'[Nn]iveau\s*[:\-]?\s*(RDC|R\+\d+)',  # Niveau RDC, Niveau R+1
                r'\b(R\+\d+)\b',  # R+1, R+2
                r'\b([ÉEe]tage\s*\d+)\b',  # Étage 1
                r'\b(\d+)\s*(?:er|[eè]me)\s*[ÉEe]tage\b',  # 1er étage, 2ème étage
            ],
            'living_space': [
                # Pattern prioritaire: SURFACE HABITABLE suivie de la valeur
                r'SURFACE\s+HABITABLE\s*[:\-]?\s*(\d+[.,]\d+)',
                r'Surface\s+[Hh]abitable\s*[:\-]?\s*(\d+[.,]\d+)',
                # Patterns generiques avec m² (tous encodages)
                r'(\d+[.,]\d+)\s*' + self._m2_pattern,
                r'Surface\s*[:\-]?\s*(\d+[.,]\d+)',
                r'Habitable\s*[:\-]?\s*(\d+[.,]\d+)',
            ],
            'orientation': [
                r'Orientation\s*[:\-]?\s*([NSEO]+|Nord|Sud|Est|Ouest)',
                r'\b(Nord|Sud|Est|Ouest)\b',
                # Note: on ne met PAS \b([NSEO])\b seul ici car il matche
                # des lettres isolées (E de "Echelle", etc.)
            ],
            'terrace': [
                r'Terrasse\s*[:\-]?\s*(\d+[.,]\d+)\s*' + self._m2_pattern,
                r'Terrasse\s*\d*\s*[:\-]?\s*(\d+[.,]\d+)',
            ],
            'balcony': [
                r'Balcon\s*[:\-]?\s*(\d+[.,]\d+)\s*' + self._m2_pattern,
                r'Balcon\s*\d*\s*[:\-]?\s*(\d+[.,]\d+)',
            ],
            'garden': [
                r'Jardin\s*[:\-]?\s*(\d+[.,]\d+)\s*' + self._m2_pattern,
                r'Jardin\s*(?:\d\s+)?[:\-]?\s*(\d+[.,]\d+)',  # "Jardin 1 50.25" ou "Jardin 120,50"
            ],
            'loggia': [
                r'Loggia\s*[:\-]?\s*(\d+[.,]\d+)\s*' + self._m2_pattern,
                r'Loggia\s*(?:\d\s+)?[:\-]?\s*(\d+[.,]\d+)',
            ],
            'total_ext': [
                r'TOTAL\s+EXT[ÉE]RIEURS?\s*[:\-]?\s*(\d+[.,]\d+)',
            ],
            'price': [
                r'Prix\s*[:\-]?\s*(\d[\d\s.,]+)\s*[€\u20AC]',
                r'(\d[\d\s.,]+)\s*[€\u20AC]',
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

    def extract_text_pdf(self, pdf_path: str) -> str:
        """
        Extrait le texte vectoriel directement depuis un PDF avec PyMuPDF.
        Plus fiable que l'OCR pour les PDFs AutoCAD qui contiennent du texte embarqué.

        Args:
            pdf_path: Chemin vers le fichier PDF

        Returns:
            Texte extrait, ou chaîne vide si échec
        """
        try:
            import fitz
        except ImportError:
            logger.debug("PyMuPDF non disponible pour extraction texte PDF")
            return ""

        try:
            doc = fitz.open(pdf_path)
            all_text = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    all_text.append(text)
            doc.close()

            combined = "\n".join(all_text)
            if combined.strip():
                logger.info(f"Texte PDF vectoriel extrait: {len(combined)} caractères")
            return combined
        except Exception as e:
            logger.warning(f"Échec extraction texte PDF: {e}")
            return ""

    def extract_text_ocr(self, processed_image) -> str:
        """
        Extrait le texte de l'image avec Tesseract OCR.
        Utilise automatiquement le francais si disponible.

        Args:
            processed_image: Image prétraitée (numpy ndarray ou chemin string)

        Returns:
            Texte extrait
        """
        logger.info(f"Extraction du texte avec OCR (langue: {self._tesseract_lang})...")

        # Gestion flexible du type d'entrée : ndarray ou chemin fichier
        if isinstance(processed_image, (str, os.PathLike)):
            # C'est un chemin de fichier, on le charge
            logger.debug(f"extract_text_ocr: chargement depuis le chemin {processed_image}")
            pil_image = Image.open(processed_image)
        elif isinstance(processed_image, np.ndarray):
            pil_image = Image.fromarray(processed_image)
        elif isinstance(processed_image, Image.Image):
            pil_image = processed_image
        else:
            raise TypeError(
                f"extract_text_ocr attend un ndarray, un chemin ou une PIL Image, "
                f"reçu: {type(processed_image).__name__}"
            )

        # Extraction du texte via subprocess (plus fiable pour Tesseract scoop)
        import subprocess
        tesseract_cmd = r"C:\Users\MSI\scoop\apps\tesseract\current\tesseract.exe"
        tessdata_dir = r"C:\Users\MSI\scoop\apps\tesseract\current\tessdata"

        try:
            # Sauvegarder l'image temporaire
            ensure_directories()
            temp_img_path = DEBUG_DIR / "temp_ocr.png"
            pil_image.save(temp_img_path)

            # Appeler tesseract directement avec --tessdata-dir
            result = subprocess.run(
                [tesseract_cmd, str(temp_img_path), "stdout",
                 "--tessdata-dir", tessdata_dir, "--oem", "3", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                text = result.stdout
                logger.info(f"Tesseract CLI: texte extrait ({len(text)} caractères)")
                return text.strip()
            else:
                logger.warning(f"Tesseract CLI error: {result.stderr}")
        except Exception as e:
            logger.warning(f"Tesseract CLI failed: {e}")

        # Fallback vers pytesseract si CLI échoue
        logger.info("Fallback vers pytesseract...")
        custom_config = f'--oem 3 --psm 6 -l {self._tesseract_lang}'
        try:
            text = pytesseract.image_to_string(pil_image, config=custom_config)
        except pytesseract.TesseractError as e:
            logger.warning(f"Erreur Tesseract avec langue '{self._tesseract_lang}': {e}")
            text = ""

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
        
        if 'rdc' in floor_lower or 'r.d.c' in floor_lower or 'rez' in floor_lower:
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

    def _extract_cartouche_block(self, text: str) -> dict:
        """
        Extrait les données du bloc cartouche AutoCAD.
        Dans les plans de vente, le cartouche contient souvent un bloc structuré :
            Appartement
            -Type
            -Niveau
        suivi plus loin des valeurs :
            B01
            4
            RDC

        Args:
            text: Texte brut du plan

        Returns:
            Dict avec les champs trouvés dans le cartouche
        """
        result = {}
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Stratégie : trouver un label de lot (format [A-Z]\d{2,4}) isolé sur sa ligne,
        # suivi d'un chiffre seul (typology) et d'un niveau (RDC, R+1, etc.)
        for i, line in enumerate(lines):
            # Chercher un label de lot isolé sur la ligne
            if re.match(r'^[A-Z]\d{2,4}$', line):
                candidate_label = line

                # Vérifier les lignes suivantes pour typology et floor
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # Chiffre seul = typology (ex: "4" → T4)
                    if re.match(r'^\d$', next_line):
                        result['typology'] = f'T{next_line}'
                        result['parcelLabel'] = candidate_label

                        if i + 2 < len(lines):
                            floor_line = lines[i + 2]
                            if re.match(r'^(RDC|R\+\d+)$', floor_line, re.IGNORECASE):
                                result['floor'] = floor_line

                        logger.debug(f"Cartouche détecté: {result}")
                        return result

        return result

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

        # Étape 0 : Tenter l'extraction du bloc cartouche AutoCAD
        cartouche = self._extract_cartouche_block(text)

        # Extraction des champs de base (cartouche prioritaire, puis regex)
        parcel.parcelLabel = cartouche.get('parcelLabel') or self.extract_field(text, 'parcelLabel') or ""
        parcel.typology = cartouche.get('typology') or self.extract_field(text, 'typology') or ""
        parcel.floor = self.normalize_floor(
            cartouche.get('floor') or self.extract_field(text, 'floor') or ""
        )
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
            'loggia': self.extract_field(text, 'loggia'),
        }

        for surface_name, surface_value in surface_fields.items():
            if surface_value:
                try:
                    parcel.surfaceDetail[surface_name] = float(self.clean_surface(surface_value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Surface '{surface_name}' non convertible: '{surface_value}' ({e})")

        # Total extérieurs (informatif)
        total_ext = self.extract_field(text, 'total_ext')
        if total_ext:
            try:
                parcel.surfaceDetail['total_exterieurs'] = float(self.clean_surface(total_ext))
            except (ValueError, TypeError):
                pass
        
        # Détection des options
        parcel.option = self.detect_options(text)
        
        return parcel

    def extract_from_image(self, image_path: str, save_preprocessed: bool = True) -> Dict:
        """
        Méthode principale : extrait toutes les données d'une image ou d'un PDF.

        Stratégie d'extraction :
        1. Si c'est un PDF → extraire le texte vectoriel avec PyMuPDF (rapide, fiable)
        2. Sinon (ou si le texte PDF est insuffisant) → OCR Tesseract sur l'image
        3. Si les deux sources existent → fusionner (PDF prioritaire)

        Args:
            image_path: Chemin vers l'image ou le PDF du plan
            save_preprocessed: Sauvegarder l'image prétraitée

        Returns:
            Dictionnaire avec les données extraites
        """
        try:
            text = ""
            extraction_source = "tesseract"

            # Étape 1 : Tenter l'extraction de texte vectoriel PDF
            if image_path.lower().endswith('.pdf'):
                pdf_text = self.extract_text_pdf(image_path)
                if pdf_text and len(pdf_text.strip()) > 50:
                    text = pdf_text
                    extraction_source = "pdf_text"
                    logger.info(f"Texte vectoriel PDF utilisé ({len(text)} chars)")

            # Étape 2 : OCR si pas de texte PDF ou texte insuffisant
            if not text or len(text.strip()) < 50:
                processed_image = self.preprocess_image(image_path)
                ocr_text = self.extract_text_ocr(processed_image)
                if ocr_text:
                    if text:
                        # Fusionner : le texte PDF + OCR pour maximiser la couverture
                        text = text + "\n" + ocr_text
                        extraction_source = "pdf_text+tesseract"
                    else:
                        text = ocr_text
                        extraction_source = "tesseract"

            # Sauvegarde du texte extrait pour debug
            ensure_directories()
            debug_text_path = DEBUG_DIR / 'extracted_text_debug.txt'
            with open(str(debug_text_path), 'w', encoding='utf-8') as f:
                f.write(f"=== SOURCE: {extraction_source} ===\n\n{text}")

            # Parsing
            parcel_data = self.parse_plan(text)

            # Conversion en dictionnaire
            result = asdict(parcel_data)
            result['_extraction_meta'] = {
                'method': 'tesseract',
                'extraction_source': extraction_source,
                'confidence': None,
                'raw_text': text[:500]
            }

            logger.info(f"Extraction terminée avec succès (source: {extraction_source})")
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
