"""
Extracteur de plans de vente immobiliers
Méthode : Regex + Validation mathématique (sans LLM)
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class RoomType(Enum):
    """Types de pièces normalisés"""
    ENTRANCE = "entree"
    LIVING_KITCHEN = "sejour_cuisine"
    LIVING = "sejour"
    KITCHEN = "cuisine"
    BEDROOM = "chambre"
    BATHROOM = "salle_de_bain"
    SHOWER_ROOM = "salle_d_eau"
    TOILET = "wc"
    STORAGE = "cellier"
    DRESSING = "dressing"
    TECHNICAL = "dgt"  # Dispositif Gestion Technique
    BALCONY = "balcon"
    TERRACE = "terrasse"
    GARDEN = "jardin"
    LOGGIA = "loggia"
    HALLWAY = "circulation"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Résultat de validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    calculated_total: Optional[float]
    expected_total: Optional[float]
    difference: Optional[float]


@dataclass
class ExtractionResult:
    """Résultat d'extraction complet"""
    parcel_label: str
    parcel_type_id: str
    parcel_type_label: str
    typology: str
    floor: str
    orientation: Optional[str]
    price: str
    living_space: str
    surface_detail: Dict[str, float]
    option: Dict[str, bool]
    tva: str
    pinel: str
    state: str
    custom_data: Dict
    validation: ValidationResult
    
    def to_json(self) -> Dict:
        """Convertit en format JSON de sortie"""
        return {
            self.parcel_label: {
                "parcelTypeId": self.parcel_type_id,
                "parcelTypeLabel": self.parcel_type_label,
                "typology": self.typology,
                "floor": self.floor,
                "orientation": self.orientation or "",
                "price": self.price,
                "living_space": self.living_space,
                "surfaceDetail": self.surface_detail,
                "option": self.option,
                "tva": self.tva,
                "pinel": self.pinel,
                "state": self.state,
                "customData": self.custom_data,
                "_validation": {
                    "is_valid": self.validation.is_valid,
                    "errors": self.validation.errors,
                    "warnings": self.validation.warnings
                } if self.validation.errors or self.validation.warnings else None
            }
        }


class PlanExtractor:
    """
    Extracteur de données de plans de vente immobiliers
    Basé sur des regex strictes et validation mathématique
    """
    
    def __init__(self):
        # Patterns pour surfaces (format: NOM + ESPACE + NOMBRE + m²)
        self.surface_patterns = [
            # Format: CHAMBRE 1\n11.72 m² ou CHAMBRE 1 11.72 m²
            r"([A-ZÉÈÀÇ\s\./]+?)\s*[:\n]?\s*(\d+[,.]\d+)\s*m[²2]",
        ]
        
        # Patterns métadonnées
        self.patterns = {
            "reference": r"\b(B\d+|A\d+|T\d+)\b",
            "promoter": r"SCCV\s+([A-Z\s]+?)(?:,|\d|$)",
            "address": r"(\d+\s+(?:rue|chemin|avenue|quai)[^,\n]+)",
            "city": r"(\d{5}\s+[A-Z\-]+)",
            "total_habitable": r"SURFACE\s+HABITABLE\s*[:\n]?\s*(\d+[,.]\d+)",
            "total_annexe": r"(?:TOTAL\s+SURFACE\s+ANNEXE|BALCON\s*\d+)\s*[:\n]?\s*(\d+[,.]\d+)",
            "floor": r"(RDC|R\+1|R\+2|1er|2e|3e|1\s*er\s*étage|2\s*e\s*étage)",
            "date": r"Date\s*[:\n]?\s*(\d{2}[/.]\d{2}[/.]\d{4})",
            "energy": r"Indice\s*[:\n]?\s*([A-E])",
        }
        
        # Mapping normalisation noms de pièces
        self.room_mapping = {
            # Entrée/Circulation
            "entree": RoomType.ENTRANCE,
            "entrée": RoomType.ENTRANCE,
            "dgt": RoomType.TECHNICAL,
            "cellier": RoomType.STORAGE,
            "circulation": RoomType.HALLWAY,
            "rgt": RoomType.HALLWAY,  # Rangement ?
            
            # Séjour/Cuisine
            "sejour": RoomType.LIVING,
            "séjour": RoomType.LIVING,
            "cuisine": RoomType.KITCHEN,
            "sejour/cuisine": RoomType.LIVING_KITCHEN,
            "séjour/cuisine": RoomType.LIVING_KITCHEN,
            "reception": RoomType.LIVING_KITCHEN,
            "réception": RoomType.LIVING_KITCHEN,
            
            # Chambres
            "chambre": RoomType.BEDROOM,
            "chambres": RoomType.BEDROOM,
            "dressing": RoomType.DRESSING,
            
            # Sanitaires
            "sdb": RoomType.BATHROOM,
            "s.d.b": RoomType.BATHROOM,
            "salle de bain": RoomType.BATHROOM,
            "salle d'eau": RoomType.SHOWER_ROOM,
            "sde": RoomType.SHOWER_ROOM,
            "s.d.e": RoomType.SHOWER_ROOM,
            "wc": RoomType.TOILET,
            "toilette": RoomType.TOILET,
            
            # Extérieur
            "balcon": RoomType.BALCONY,
            "balcony": RoomType.BALCONY,
            "terrasse": RoomType.TERRACE,
            "terrace": RoomType.TERRACE,
            "jardin": RoomType.GARDEN,
            "garden": RoomType.GARDEN,
            "loggia": RoomType.LOGGIA,
        }
        
        # Dimensions à ignorer (patterns de cotes)
        self.dimension_patterns = [
            r"^\d{2,4}$",  # Nombres isolés (98, 283, 711...)
            r"^\d\.\d{2}$",  # 1.95, 2.51...
            r"^\d{1,2},\d{2}$",  # 1,95, 2,51...
        ]
    
    def extract(self, ocr_text: str, parcel_hint: Optional[str] = None) -> ExtractionResult:
        """
        Extrait les données d'un plan de vente
        
        Args:
            ocr_text: Texte brut du PDF (OCR)
            parcel_hint: Référence attendue (optionnel, pour validation)
        
        Returns:
            ExtractionResult avec validation
        """
        # 1. Nettoyage
        clean_text = self._clean_text(ocr_text)
        
        # 2. Extraction métadonnées
        metadata = self._extract_metadata(clean_text)
        
        # 3. Extraction surfaces
        surfaces = self._extract_surfaces(clean_text)
        
        # 4. Détection typologie et étage
        typology = self._detect_typology(surfaces)
        floor = self._detect_floor(clean_text, metadata)
        
        # 5. Détection options
        options = self._detect_options(clean_text, surfaces)
        
        # 6. Validation
        validation = self._validate(surfaces, metadata)
        
        # 7. Construction résultat
        reference = metadata.get("reference") or parcel_hint or "UNKNOWN"
        
        # Si hint fourni et différent de détecté → warning
        if parcel_hint and metadata.get("reference") and parcel_hint != metadata["reference"]:
            validation.warnings.append(
                f"Référence détectée ({metadata['reference']}) différente du hint ({parcel_hint})"
            )
        
        # Format surface_detail selon votre spec
        surface_detail = {}
        for key, value in surfaces.items():
            # Convertir enum en string
            if isinstance(key, RoomType):
                surface_detail[key.value] = value
            else:
                surface_detail[key] = value
        
        # Ajouter totals si présents
        if metadata.get("total_habitable"):
            surface_detail["total_habitable"] = float(metadata["total_habitable"].replace(",", "."))
        if metadata.get("total_annexe"):
            surface_detail["total_annexe"] = float(metadata["total_annexe"].replace(",", "."))
        
        custom_data = {
            "promoter": metadata.get("promoter"),
            "address": metadata.get("address"),
            "city": metadata.get("city"),
            "date": metadata.get("date"),
            "energy_index": metadata.get("energy"),
        }
        # Filtrer les None
        custom_data = {k: v for k, v in custom_data.items() if v is not None}
        
        return ExtractionResult(
            parcel_label=reference,
            parcel_type_id="appartment",
            parcel_type_label="appartment",
            typology=typology,
            floor=floor,
            orientation=None,  # Non présent dans ce type de plan
            price="N.C",
            living_space=metadata.get("total_habitable", "0"),
            surface_detail=surface_detail,
            option=options,
            tva="",
            pinel="",
            state="available",
            custom_data=custom_data,
            validation=validation
        )
    
    def _clean_text(self, text: str) -> str:
        """Nettoie et normalise le texte OCR"""
        # Normalise les sauts de ligne
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Normalise séparateurs décimaux (virgule → point)
        # Mais attention aux milliers ! On assume que c'est toujours décimal pour les surfaces
        text = re.sub(r'(\d),(\d{2})(?=\s*m[²2])', r'\1.\2', text)
        
        # Supprime les espaces multiples
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def _extract_metadata(self, text: str) -> Dict[str, Optional[str]]:
        """Extrait les métadonnées du plan"""
        metadata = {}
        
        for key, pattern in self.patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                metadata[key] = value
        
        return metadata
    
    def _extract_surfaces(self, text: str) -> Dict[RoomType, float]:
        """
        Extrait les surfaces par pièce
        Gère les doublons (Chambre 1, Chambre 2...)
        """
        surfaces = {}
        room_counts = {}
        
        # Trouve toutes les occurrences
        # Format: NOM [numéro] [séparateur] nombre m²
        pattern = r"([A-ZÉÈÀÇ][A-ZÉÈÀÇ\s\./]+?)(?:\s+(\d))?\s*[:\n]?\s*(\d+[,.]\d+)\s*m[²2]"
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for name, number, surface_str in matches:
            name_clean = name.strip().lower()
            surface = float(surface_str.replace(",", "."))
            
            # Ignore les dimensions linéaires (pas de contexte m²)
            if self._is_likely_dimension(name_clean, surface):
                continue
            
            # Normalise le nom
            room_type = self._normalize_room_name(name_clean)
            
            # Gère les doublons
            if number:
                key = f"{room_type.value}_{number}"
            elif room_type in room_counts:
                room_counts[room_type] += 1
                key = f"{room_type.value}_{room_counts[room_type]}"
            else:
                room_counts[room_type] = 1
                key = room_type.value
            
            # Évite les écrasements (prend le plus grand si doublon)
            if key in surfaces:
                if surface > surfaces[key]:
                    surfaces[key] = surface
            else:
                surfaces[key] = surface
        
        return surfaces
    
    def _is_likely_dimension(self, name: str, value: float) -> bool:
        """Détermine si c'est une dimension linéaire et non une surface"""
        # Si pas de nom de pièce reconnaissable et valeur < 10
        # c'est probablement une cote en mètres (1.95, 2.51...)
        if name in ["", "m", "cm"] or len(name) < 2:
            if value < 10:
                return True
        
        # Si le "nom" ressemble à un nombre (erreur OCR)
        if re.match(r'^\d+$', name.replace(" ", "")):
            return True
        
        return False
    
    def _normalize_room_name(self, name: str) -> RoomType:
        """Normalise un nom de pièce vers un RoomType"""
        name_clean = name.strip().lower()
        
        # Supprime les articles et espaces multiples
        name_clean = re.sub(r'\s+', ' ', name_clean)
        
        # Cherche match exact
        if name_clean in self.room_mapping:
            return self.room_mapping[name_clean]
        
        # Cherche match partiel
        for pattern, room_type in self.room_mapping.items():
            if pattern in name_clean or name_clean in pattern:
                return room_type
        
        return RoomType.UNKNOWN
    
    def _detect_typology(self, surfaces: Dict) -> str:
        """Détecte la typologie (T2, T3, T4...)"""
        # Compte les chambres
        bedrooms = [k for k in surfaces.keys() if "chambre" in str(k)]
        nb_bedrooms = len(bedrooms)
        
        # Typologie: T2 = 1 chambre, T3 = 2 chambres, etc.
        # Ou Studio si 0 chambres
        if nb_bedrooms == 0:
            return "Studio"
        else:
            return f"T{nb_bedrooms + 1}"
    
    def _detect_floor(self, text: str, metadata: Dict) -> str:
        """Détecte l'étage"""
        # Priorité au pattern détecté
        if metadata.get("floor"):
            floor = metadata["floor"].upper()
            # Normalise
            floor = floor.replace("ÈRE", "ER").replace("ÈME", "E")
            if "RDC" in floor:
                return "RDC"
            elif "R+1" in floor or "1ER" in floor:
                return "R+1"
            elif "R+2" in floor or "2E" in floor:
                return "R+2"
            return floor
        
        # Déduction du contexte
        if "rez-de-chaussée" in text.lower() or "rdc" in text.lower():
            return "RDC"
        
        return "unknown"
    
    def _detect_options(self, text: str, surfaces: Dict) -> Dict[str, bool]:
        """Détecte les options (balcon, jardin, etc.)"""
        text_lower = text.lower()
        
        return {
            "garden": "jardin" in text_lower and RoomType.GARDEN in surfaces,
            "terrace": "terrasse" in text_lower and RoomType.TERRACE in surfaces,
            "balcony": "balcon" in text_lower and RoomType.BALCONY in surfaces,
            "parking": "parking" in text_lower,
            "winter_garden": "jardin d'hiver" in text_lower or "véranda" in text_lower,
            "garage": "garage" in text_lower,
            "loggia": "loggia" in text_lower and RoomType.LOGGIA in surfaces,
            "duplex": "duplex" in text_lower,
        }
    
    def _validate(self, surfaces: Dict, metadata: Dict) -> ValidationResult:
        """Valide la cohérence des données extraites"""
        errors = []
        warnings = []
        
        calculated_total = 0.0
        expected_total = None
        difference = None
        
        # Calcul de la somme des pièces (hors extérieur et totals)
        exterior_types = {RoomType.BALCONY, RoomType.TERRACE, RoomType.GARDEN, RoomType.LOGGIA}
        
        for key, value in surfaces.items():
            if isinstance(key, RoomType):
                if key not in exterior_types:
                    calculated_total += value
            elif isinstance(key, str):
                if not any(ext in key for ext in ["balcon", "terrasse", "jardin", "loggia", "total"]):
                    calculated_total += value
        
        # Vérifie contre le total déclaré
        if metadata.get("total_habitable"):
            try:
                expected_total = float(metadata["total_habitable"].replace(",", "."))
                difference = abs(calculated_total - expected_total)
                
                # Tolérance de 1 m² (arrondis)
                if difference > 1.0:
                    errors.append(
                        f"Surface mismatch: calculée={calculated_total:.2f}, "
                        f"attendue={expected_total:.2f}, écart={difference:.2f}"
                    )
                elif difference > 0.1:
                    warnings.append(
                        f"Petit écart de surface: {difference:.2f} m²"
                    )
            except ValueError:
                errors.append(f"Format de total invalide: {metadata['total_habitable']}")
        
        # Vérifie présence minimum
        if not surfaces:
            errors.append("Aucune surface extraite")
        
        if not any("chambre" in str(k) for k in surfaces.keys()):
            warnings.append("Aucune chambre détectée")
        
        if not any("sejour" in str(k) or "cuisine" in str(k) for k in surfaces.keys()):
            warnings.append("Aucun séjour/cuisine détecté")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            calculated_total=calculated_total,
            expected_total=expected_total,
            difference=difference
        )