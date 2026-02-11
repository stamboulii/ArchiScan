"""
PyMuPDF Extractor - Extraction Directe PDF
===========================================

Extracteur base sur PyMuPDF (fitz) pour les fichiers PDF.
Extraction directe du texte SANS conversion en image.
Methode propre et rapide pour les PDF textes.

Attributes:
    - Extraction directe du texte PDF
    - Preservation de la structure (tableaux, listes)
    - Detection des metadonnees PDF
    - Compatible avec les PDF hybrides (texte + images)
"""

import re
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from ..core.parcel import ParcelData, normalize_parcel_data, DEFAULT_OPTIONS
from ..core.exceptions import ExtractionError

logger = logging.getLogger(__name__)


@dataclass
class PyMuPDFExtractionResult:
    """Resultat de l'extraction PyMuPDF."""
    success: bool
    text: str = ""
    cleaned_text: str = ""
    raw_blocks: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    confidence: float = 0.0
    error: Optional[str] = None


class PyMuPDFExtractor:
    """
    Extracteur utilisant PyMuPDF pour l'extraction directe du texte.
    
    Avantages:
    - Pas de conversion PDF -> Image necessaire
    - Extraction rapide du texte natif
    - Conservation de la structure du document
    - Detection automatique du texte embedde
    
    Limites:
    - Ne fonctionne que sur les PDF avec texte extractible
    - Necessite un PDF avec couche texte (pas uniquement des images scannees)
    """
    
    # Patterns regex pour l'extraction des donnees de parcel
    PATTERNS = {
        'parcelLabel': [
            r'\b([A-Z]\d{3})\b',  # Format A001
            r'\bLot\s*[#]?\s*([A-Z]?\d{2,3})\b',  # Lot A01 ou Lot 001
            r'\bAppartement\s*[#]?\s*([A-Z]?\d{2,3})\b',
            r'\bN°\s*(?:Lot|Appartement)?\s*[:]?\s*([A-Z]?\d{2,3})\b',
        ],
        'typology': [
            r'\b(T[1-9])\b',  # T1, T2, T3, etc.
            r'\b(F[1-9])\b',  # F1, F2, etc.
            r'\b(\d)\s*pieces?\b',  # 2 pieces, 3 pieces
            r'\b(\d)P\b',  # 2P, 3P, 4P
            r'\bType\s*[T|F]\d\b',  # Type T2
        ],
        'floor': [
            r'\b(RDC|R\.D\.C\.?)\b',  # Rez-de-chaussee
            r'\bRez[- ]de[- ]chaussee\b',
            r'\b(R\+\d+)\b',  # R+1, R+2
            r'\bEtage\s*(\d+)\b',  # Etage 1
            r'\b(\d+)(?:er|eme)?\s*[eé]tage\b',  # 1er etage
            r'\b[Nn]iveau\s*(\d+)\b',
        ],
        'living_space': [
            r'Surface\s*(?:habitable|utile|Totale)?\s*[:]?\s*(\d+[.,]?\d*)',
            r'SH\s*[:]?\s*(\d+[.,]?\d*)',
            r'\((\d+[.,]?\d*)\s*m[²2]\)',
            # r'(\d+[.,]?\d*)\s*m[²2]',  # Trop generique, capture les balcons
        ],
        'orientation': [
            r'\b([NSEO])\b(?:\s*[-–]\s*([NSEO]))?',  # N, S-E, N-O
            r'\b(Nord|Sud|Est|Ouest)\b',
            r'\b(Nord[- ]Sud|Sud[- ]Nord|Est[- ]Ouest|Ouest[- ]Est)\b',
            r'Orientation\s*[:]?\s*([NSEO]|Nord|Sud|Est|Ouest)',
        ],
        'terrace': [
            r'Terrasse\s*[:]?\s*(\d+[.,]?\d*)\s*m[²2]',
            r'Terrasse\s*[:]?\s*(\d+[.,]?\d*)',
            r'Balcon[- ]Terrasse\s*[:]?\s*(\d+[.,]?\d*)',
        ],
        'balcony': [
            r'Balcon\s*[:]?\s*(\d+[.,]?\d*)\s*m[²2]',
            r'Balcon\s*[:]?\s*(\d+[.,]?\d*)',
        ],
        'garden': [
            r'Jardin\s*[:]?\s*(\d+[.,]?\d*)\s*m[²2]',
            r'Jardin\s*[:]?\s*(\d+[.,]?\d*)',
            r'Rez[- ]de[- ]jardin\s*[:]?\s*(\d+[.,]?\d*)',
        ],
        'price': [
            r'(\d{3,6})\s*(?:€|EUR)\s*(?:HT|TTC)?',
            r'Prix\s*(?:Total|Honnetaire|net)?\s*[:]?\s*(\d+)',
            r'(\d{3,6})\s*(?:€|EUR)',
            r'Co[ûu]ts?\s*(?:de)?\s*(?:construction|vente)?\s*[:]?\s*(\d+)',
        ],
        'parking': [
            r'Parking\s*(?:inclus|boxe|numerote)?\s*[:]?\s*(?:Oui|Numéro\s*\d+)?',
            r'Parking\s*[#]?\s*(\d+)',
            r'Boxe?\s*(?:Auto)?\s*[#]?\s*(\d+)',
            r'Emplacement\s*(?:Parking|Voiture)\s*[:]?\s*(\d+)',
        ],
        'cellar': [
            r'Cave\s*[:]?\s*(\d+[.,]?\d*)\s*m[²2]',
            r'Cave\s*[:]?\s*(?:Oui|№?\s*\d+)',
            r'Cellier\s*[:]?\s*(\d+[.,]?\d*)',
        ],
    }
    
    # Mots-cles pour les options/supplements
    OPTION_KEYWORDS = {
        'terrace': ['terrasse', 'terrasse bois', 'terrasse beton'],
        'balcony': ['balcon', 'balcon filant'],
        'garden': ['jardin prive', 'jardin', 'rdc jardin'],
        'parking': ['parking', 'boxe', 'garage', 'place de parking'],
        'cellar': ['cave', 'cellier', 'sout'],
        'duplex': ['duplex'],
        'loggia': ['loggia'],
        'winter garden': ['jardin d\'hiver', 'veranda', 'winter garden'],
    }
    
    # Patterns specifiques pour les pieces et surfaces
    # Patterns specifiques pour les pieces et surfaces
    # Ajout de [:\s]* pour gerer "BALCON: 9.57" ou "BALCON 9.57"
    ROOM_PATTERNS = {
        r"CHAMBRE\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("chambre_{}", "chambre"),
        r"S(?:EJOUR|ÉJOUR)/CUISINE\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("sejour_cuisine", "sejour"),
        r"ENTR[EÉ]E\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("entree", "entree"),
        r"(?:SDB|SALLE\s+DE\s+BAINS?)\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("salle_de_bain", "sdb"),
        r"(?:SDE|SALLE\s+D['\s]EAU)\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("salle_d_eau", "sde"),
        r"WC\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("wc", "wc"),
        r"CELLIER\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("cellier", "cellier"),
        r"BALCON\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("balcon", "exterieur"),
        r"JARDIN\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("jardin", "exterieur"),
        r"TERASSE\s*[:]?\s*(\d+(?:\.\d+)?)\s*m²": ("terrasse", "exterieur"),
    }
    
    def __init__(self):
        """Initialise l'extracteur PyMuPDF."""
        self.patterns = self.PATTERNS
        self.option_keywords = self.OPTION_KEYWORDS
        self.room_patterns = self.ROOM_PATTERNS
    
    def is_available(self) -> bool:
        """
        Verifie si PyMuPDF est disponible.
        
        Returns:
            True si PyMuPDF peut etre utilise
        """
        try:
            import fitz
            return True
        except ImportError:
            return False
    
    def extract(self, pdf_path: str, force: bool = False) -> PyMuPDFExtractionResult:
        """
        Extrait le texte d'un fichier PDF.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            force: Re-extraire meme si deja fait
            
        Returns:
            PyMuPDFExtractionResult avec les donnees extraites
        """
        import time
        start_time = time.time()
        
        try:
            pdf_path = str(Path(pdf_path).resolve())
            
            # Ouvrir le PDF
            doc = fitz.open(pdf_path)
            
            # Extraire le texte page par page
            full_text = ""
            raw_blocks = []
            metadata = {}
            
            for page_num, page in enumerate(doc):
                # Extraire le texte avec blocks pour avoir la structure
                blocks = page.get_text("blocks")
                page_text = page.get_text()
                
                full_text += f"\n--- Page {page_num + 1} ---\n"
                full_text += page_text
                
                for block in blocks:
                    if len(block) >= 4:
                        raw_blocks.append({
                            'page': page_num + 1,
                            'text': block[4] if len(block) > 4 else str(block),
                            'bbox': block[0:4],  # x0, y0, x1, y1
                        })
            
            # Recuperer les metadonnees du PDF
            metadata = {
                'page_count': doc.page_count,
                'metadata': doc.metadata,
                'pdf_path': pdf_path,
            }
            
            doc.close()
            
            # Nettoyer le texte
            cleaned_text = self._clean_text(full_text)
            
            # Parser les donnees de parcel
            parcel_data = self._parse_parcel_data(cleaned_text)
            
            # Calculer la confiance basee sur les donnees trouvees
            confidence = self._calculate_confidence(parcel_data)
            
            duration_ms = (time.time() - start_time) * 1000
            
            return PyMuPDFExtractionResult(
                success=True,
                text=full_text,
                cleaned_text=cleaned_text,
                raw_blocks=raw_blocks,
                metadata=metadata,
                confidence=confidence,
            )
            
        except Exception as e:
            logger.error(f"Erreur extraction PyMuPDF: {e}")
            return PyMuPDFExtractionResult(
                success=False,
                error=str(e),
                confidence=0.0,
            )
    
    def _clean_text(self, text: str) -> str:
        """
        Nettoie le texte extrait pour faciliter le parsing.
        
        Args:
            text: Texte brut extrait du PDF
            
        Returns:
            Texte nettoye
        """
        if not text:
            return ""
        
        # Remplacements de caracteres speciaux
        replacements = {
            '\u00A0': ' ',  # Espace insecable
            '\u202F': ' ',  # Espace fine
            '\u2000': ' ',  # Espace quadrat
            '\u200B': '',   # Espace zero
            '\u2009': ' ',  # Espace fine
            '\u2007': ' ',  # Espace figure
            '\u2008': ' ',  # Espace ponctuation
            '\u2011': '-',  # Tiret insecable
            '\u2013': '-',  # Tiret long
            '\u2014': '-',  # Tiret cadratin
            '\u2018': "'",  # Guillemet simple gauche
            '\u2019': "'",  # Guillemet simple droite
            '\u201C': '"',  # Guillemet double gauche
            '\u201D': '"',  # Guillemet double droite
            '\x0c': '\n',   # Saut de page
            '\r\n': '\n',
            '\r': '\n',
        }
        
        cleaned = text
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        # Normaliser les espaces multiples
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # Supprimer les lignes vides en double
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def _parse_parcel_data(self, text: str) -> Dict[str, Any]:
        """
        Parse le texte nettoye pour extraire les donnees de parcel.
        
        Args:
            text: Texte nettoye
            
        Returns:
            Dict avec les donnees extraites
        """
        result = {}
        
        # Recherche par patterns
        for field, patterns in self.patterns.items():
            value = None
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Prendre le groupe capture le plus pertinent
                    groups = [g for g in match.groups() if g]
                    if groups:
                        value = groups[-1]  # Dernier groupe capture
                        break
            
            if value:
                result[field] = value
        
        # Detection avancee des surfaces et typologie
        text_upper = text.upper()
        
        # Extraction surfaces détaillées D'ABORD
        surface_detail = {}
        total_habitable = 0.0
        total_exterieur = 0.0
        
        for pattern, (key, room_type) in self.room_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for i, match in enumerate(matches):
                try:
                    surface = float(match.replace(",", "."))
                    actual_key = key.format(i+1) if "{}" in key else key
                    surface_detail[actual_key] = surface
                    
                    if room_type == "exterieur":
                        total_exterieur += surface
                        # Mapper vers les champs standards
                        if "balcon" in key:
                            result['balcony'] = str(surface)
                        elif "jardin" in key:
                            result['garden'] = str(surface)
                        elif "terrasse" in key:
                            result['terrace'] = str(surface)
                    else:
                        total_habitable += surface
                except ValueError:
                    continue
        
        if surface_detail:
            result['surfaceDetail'] = surface_detail
        
        # Détection typologie via nombre de chambres detectees dans les surfaces
        nb_chambres_details = len([k for k in surface_detail.keys() if 'chambre' in k])
        
        if nb_chambres_details > 0:
            result['typology'] = f"T{nb_chambres_details + 1}"
        else:
            # Fallback regex simple si pas de details trouves
            nb_chambres_regex = len(re.findall(r"CHAMBRE\s+\d+", text, re.IGNORECASE))
            if nb_chambres_regex > 0:
                 result['typology'] = f"T{nb_chambres_regex + 1}"
        
        # Surface habitable totale (priorité au texte explicite, sinon somme)
        
        # Surface habitable totale (priorité au texte explicite, sinon somme)
        # Surface habitable totale (priorité au texte explicite, sinon somme)
        # Note: 'living_space' peut deja etre rempli par les patterns regex generiques (mais on les a restreints)
        
        # 1. Chercher explicitement "Surface Habitable" ou equivalent
        living_space_match = re.search(r"SURFACE\s+HABITABLE\s*[:]?\s*(\d+(?:\.\d+)?)", text_upper)
        if living_space_match:
             result['living_space'] = living_space_match.group(1)
        # 2. Sinon, utiliser la somme des pieces habitables si disponible
        elif total_habitable > 0:
             result['living_space'] = f"{total_habitable:.2f}"
        
        # Si toujours rien, on garde ce que les patterns generiques ont trouve (s'ils ont trouve qqch)
            
        # Détection étage amelioree
        if 'floor' not in result:
            if "RDC" in text_upper or "REZ-DE-CHAUSSEE" in text_upper:
                result['floor'] = "RDC"
            elif "R+1" in text_upper or "1ER" in text_upper:
                result['floor'] = "R+1"
            elif "R+2" in text_upper or "2EME" in text_upper:
                result['floor'] = "R+2"
        
        # Detection ref (fallback parcelLabel)
        if 'parcelLabel' not in result:
             match_ref = re.search(r'(B\d+|A\d+|T\d+)', text_upper)
             if match_ref:
                 result['parcelLabel'] = match_ref.group(1)
        
        # Detection des options par mots-cles
        options_found = []
        text_lower = text.lower()
        
        for option, keywords in self.option_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    options_found.append(option)
                    break
        
        if options_found:
            result['options'] = options_found
        
        return result
    
    def _calculate_confidence(self, parcel_data: Dict[str, Any]) -> float:
        """
        Calcule un score de confiance base sur les donnees trouvees.
        
        Args:
            parcel_data: Donnees extraites
            
        Returns:
            Score de confiance entre 0 et 1
        """
        if not parcel_data:
            return 0.0
        
        # Champs attendus pour un bon score
        important_fields = ['parcelLabel', 'living_space', 'typology', 'floor']
        optional_fields = ['orientation', 'terrace', 'balcony', 'garden', 'price', 'parking', 'cellar']
        
        score = 0.0
        
        # Points pour les champs importants trouves
        for field in important_fields:
            if field in parcel_data:
                score += 0.20
        
        # Points pour les champs optionnels
        for field in optional_fields:
            if field in parcel_data:
                score += 0.05
        
        # Bonus pour le nombre total de champs
        total_fields = len(parcel_data)
        if total_fields >= 5:
            score += 0.10
        elif total_fields >= 3:
            score += 0.05
        
        return min(score, 1.0)
    
    def to_parcel_data(self, extraction_result: PyMuPDFExtractionResult) -> ParcelData:
        """
        Convertit le resultat d'extraction en ParcelData normalise.
        
        Args:
            extraction_result: Resultat de l'extraction
            
        Returns:
            ParcelData normalise
        """
        raw_data = {}
        
        if extraction_result.success:
            # Utiliser les donnees parsees
            raw_data = self._parse_parcel_data(extraction_result.cleaned_text)
        
        # Normaliser les donnees
        normalized = normalize_parcel_data(raw_data)
        
        # Preparer surfaceDetail
        surface_detail = {}
        if normalized.get('terrace'):
            surface_detail['terrasse'] = float(normalized.get('terrace', 0))
        if normalized.get('balcony'):
            surface_detail['balcon'] = float(normalized.get('balcony', 0))
        if normalized.get('garden'):
            surface_detail['jardin'] = float(normalized.get('garden', 0))
            
        # Ajouter les details de pieces s'ils existent (venant de la logic custom)
        if raw_data.get('surfaceDetail'):
            surface_detail.update(raw_data.get('surfaceDetail'))
        if normalized.get('balcony'):
            surface_detail['balcon'] = float(normalized.get('balcony', 0))
        if normalized.get('garden'):
            surface_detail['jardin'] = float(normalized.get('garden', 0))
        
        # Preparer les options
        options = normalized.get('options', [])
        option_dict = {}
        if 'terrace' in options:
            option_dict['terrasse'] = True
        if 'balcony' in options:
            option_dict['balcon'] = True
        if 'garden' in options:
            option_dict['jardin'] = True
        if 'parking' in options:
            option_dict['parking'] = True
        if 'cellar' in options:
            option_dict['cave'] = True
            
        # Synchro: Si une surface est detectee, l'option est implicitement vraie
        if surface_detail.get('balcon', 0) > 0:
            option_dict['balcon'] = True
        if surface_detail.get('terrasse', 0) > 0:
            option_dict['terrasse'] = True
        if surface_detail.get('jardin', 0) > 0:
            option_dict['jardin'] = True
        
        # Creer un objet ParcelData
        return ParcelData(
            parcelLabel=normalized.get('parcel_label', ''),
            typology=normalized.get('typology', ''),
            floor=normalized.get('floor', ''),
            living_space=normalized.get('living_space', ''),
            orientation=normalized.get('orientation', ''),
            price=normalized.get('price', ''),
            surfaceDetail=surface_detail,
            option=option_dict if option_dict else DEFAULT_OPTIONS.copy(),
        )
    
    def extract_table_like_data(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extrait les donnees en format tableau du PDF.
        Utile pour les grilles de lots.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            
        Returns:
            Liste de dictionnaires representant les lignes du tableau
        """
        doc = fitz.open(pdf_path)
        table_rows = []
        
        for page in doc:
            # Essayer d'extraire en format dict/JSON
            tables = page.get_text("dict")
            
            for block in tables.get("blocks", []):
                if block.get("type") == 0:  # Type texte
                    for line in block.get("lines", []):
                        row_data = {}
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                # Essayer de parser les donnees de la ligne
                                parsed = self._parse_parcel_data(text)
                                if parsed:
                                    row_data.update(parsed)
                        
                        if row_data:
                            table_rows.append(row_data)
        
        doc.close()
        return table_rows
