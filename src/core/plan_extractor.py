"""
PlanExtractor - Extracteur de plans d'architecture
================================================

Extracteur specifiquement con�u pour parser les plans de vente PDF.
Utilise des patterns regex pour extraire les donnees du texte OCR.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultat de la validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)


@dataclass
class PlanExtractorResult:
    """Resultat de l'extraction."""
    parcel_label: str = ""
    typology: str = ""
    floor: str = ""
    living_space: str = ""
    orientation: str = ""
    price: str = "N.C"
    surface_detail: Dict[str, float] = field(default_factory=dict)
    options: Dict[str, bool] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=ValidationResult)
    
    def to_json(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "parcelLabel": self.parcel_label,
            "typology": self.typology,
            "floor": self.floor,
            "living_space": self.living_space,
            "orientation": self.orientation,
            "price": self.price,
            "surfaceDetail": self.surface_detail,
            "options": self.options,
            "customData": self.custom_data,
            "validation": {
                "is_valid": self.validation.is_valid,
                "errors": self.validation.errors
            }
        }


class PlanExtractor:
    """
    Extracteur de plans d'architecture.
    
    Patterns supportes:
    - Chambres, Sejour, Cuisine, SDB, WC, etc.
    - Surfaces en m� ou m2
    - Typologie T1-T7
    - Etage RDC, R+1, R+2, etc.
    """
    
    # Patterns pour les pieces
    ROOM_PATTERNS = [
        # Chambres
        (r"CHAMBRE\s*(\d*)", "chambre"),
        (r"Chambre\s*(\d*)", "chambre"),
        # Sejour / Cuisine
        (r"SEJOUR/CUISINE", "sejour_cuisine"),
        (r"SEJUR/CUISINE", "sejour_cuisine"),
        (r"SEJOUR", "sejour"),
        (r"CUISINE", "cuisine"),
        # Salles de bain
        (r"S\.?D\.?B\.?", "salle_de_bain"),
        (r"SDB", "salle_de_bain"),
        # WC
        (r"\bWC\b", "wc"),
        # Entree
        (r"ENTREE", "entree"),
        # Degagement
        (r"\bDGT\b", "dgt"),
        # Reglement
        (r"\bRGT\b", "rgt"),
        # Balcons
        (r"BALCON", "balcon"),
    ]
    
    # Patterns pour les surfaces
    SURFACE_PATTERN = r"(\d+[.,]\d+)\s*m[²2°]?"
    
    def __init__(self):
        self.room_patterns = self.ROOM_PATTERNS
    
    def extract(self, text: str, parcel_hint: str = None) -> PlanExtractorResult:
        """
        Extrait les donnees du texte OCR.
        
        Args:
            text: Texte OCR du plan
            parcel_hint: Indice pour le lot (optionnel)
            
        Returns:
            PlanExtractorResult
        """
        result = PlanExtractorResult()
        
        # Nettoyer le texte
        lines = text.strip().split('\n')
        
        # 1. Extraire la reference du lot
        result.parcel_label = self._extract_parcel_label(lines, parcel_hint)
        
        # 2. Extraire la typologie
        result.typology = self._extract_typology(lines)
        
        # 3. Extraire l'etage
        result.floor = self._extract_floor(lines)
        
        # 4. Extraire les surfaces
        result.surface_detail = self._extract_surfaces(lines)
        
        # 5. Calculer la surface habitable totale
        if result.surface_detail:
            habitable = sum(
                v for k, v in result.surface_detail.items() 
                if k not in ['balcon', 'terrasse', 'jardin', 'loggia']
            )
            if habitable > 0:
                result.surface_detail['total_habitable'] = round(habitable, 2)
        
        # 6. Detecter les options
        result.options = self._extract_options(text)
        
        # 7. Extraire les donnees personnalisees
        result.custom_data = self._extract_custom_data(text)
        
        # 8. Valider
        result.validation = self._validate(result)
        
        return result
    
    def _extract_parcel_label(self, lines: List[str], hint: str = None) -> str:
        """Extrait la reference du lot."""
        # Si hint fourni, l'utiliser
        if hint:
            return hint
            
        # Chercher un pattern comme A104, B15, etc.
        for line in lines:
            line = line.strip()
            # Pattern: lettre + chiffres (ex: A104, B15)
            match = re.match(r'^([A-Z]\d{1,4})$', line)
            if match:
                # Exclure les mots courants
                if line.upper() not in ['RGT', 'DGT', 'WC', 'EP', 'VR', 'PF']:
                    return line
                    
        return ""
    
    def _extract_typology(self, lines: List[str]) -> str:
        """Extrait la typologie (T1, T2, T3, etc.)."""
        for line in lines:
            line = line.strip().upper()
            
            # Chercher "T1", "T2", etc.
            match = re.search(r'\b(T[1-7])\b', line)
            if match:
                return match.group(1)
                
            # Chercher "3 pieces", "4 pieces", etc.
            match = re.search(r'(\d+)\s*PIECES?', line)
            if match:
                return f"T{match.group(1)}"
                
        # Compter les chambres
        nb_chambres = sum(1 for l in lines if re.match(r'^CHAMBRE\s*\d*$', l.strip(), re.IGNORECASE))
        if nb_chambres > 0:
            return f"T{nb_chambres + 1}"  # T3 pour 2 chambres + sejour
            
        return ""
    
    def _extract_floor(self, lines: List[str]) -> str:
        """Extrait l'etage."""
        for line in lines:
            line = line.strip().upper()
            
            # RDC
            if re.match(r'^(RDC|R\.D\.C\.?)$', line):
                return "RDC"
                
            # R+1, R+2, etc.
            match = re.match(r'^R\+(\d+)$', line)
            if match:
                return f"R+{match.group(1)}"
                
            # 1er etage, 2eme etage
            match = re.match(r'^(\d+)(?:ER|EME)\s*ETAGE', line)
            if match:
                return f"R+{match.group(1)}"
                
        return ""
    
    def _extract_surfaces(self, lines: List[str]) -> Dict[str, float]:
        """Extrait les surfaces des pieces."""
        surfaces = {}
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Chercher le nom de la piece
            for pattern, room_key in self.room_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # La surface est sur la ligne suivante
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        match = re.search(self.SURFACE_PATTERN, next_line, re.IGNORECASE)
                        if match:
                            try:
                                value = float(match.group(1).replace(',', '.'))
                                
                                # Creer une cle unique
                                key = room_key
                                count = 1
                                while key in surfaces:
                                    key = f"{room_key}_{count}"
                                    count += 1
                                    
                                surfaces[key] = value
                            except ValueError:
                                pass
                    break
                    
        return surfaces
    
    def _extract_options(self, text: str) -> Dict[str, bool]:
        """Detecte les options."""
        text_lower = text.lower()
        
        options = {
            "balcony": "balcon" in text_lower,
            "terrace": "terrasse" in text_lower,
            "garden": "jardin" in text_lower,
            "parking": "parking" in text_lower or "stationnement" in text_lower,
            "garage": "garage" in text_lower,
            "loggia": "loggia" in text_lower,
        }
        
        return options
    
    def _extract_custom_data(self, text: str) -> Dict[str, Any]:
        """Extrait les donnees personnalisees."""
        custom = {}
        
        # Chercher le promoteur
        match = re.search(r'(SCCV\s+[\w\s]+)', text, re.IGNORECASE)
        if match:
            custom["promoteur"] = match.group(1).strip()
            
        # Chercher l'adresse
        match = re.search(r'(\d+\s+[\w\s]+,\s*\d+\s+\w+)', text)
        if match:
            custom["adresse"] = match.group(1).strip()
            
        # Chercher la date
        match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if match:
            custom["date"] = match.group(1)
            
        return custom
    
    def _validate(self, result: PlanExtractorResult) -> ValidationResult:
        """Valide les donnees extraites."""
        errors = []
        
        if not result.parcel_label:
            errors.append("Reference du lot manquante")
            
        if not result.living_space and not result.surface_detail:
            errors.append("Surface manquante")
            
        is_valid = len(errors) == 0
        
        return ValidationResult(is_valid=is_valid, errors=errors)


# Test
if __name__ == "__main__":
    TEST_OCR_B15 = """CHAMBRE 1
11.72 m²
CHAMBRE 2
9.02 m²
RGT
ENTREE
5.15 m²
S.D.B
4.98 m²
WC
2.79 m²
SEJUR/CUISINE
30.52 m²
DGT
1.44 m²
BALCON:
12.32 m²
SURFACE HABITABLE
65.62m²
B15
3
R+1
"""
    
    extractor = PlanExtractor()
    result = extractor.extract(TEST_OCR_B15, parcel_hint="B15")
    print(json.dumps(result.to_json(), indent=2, ensure_ascii=False))
