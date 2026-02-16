"""
SuperExtractor v2.1 - Extracteur Universel de Plans Immobiliers
===============================================================

Gère tous les formats de plans:
- Appartements, maisons, bureaux, commerces
- PDF natifs ou scannés (OCR auto)
- Validation mathématique intégrée
- Format de sortie compatible legacy

Usage:
    from super_extractor import extract_plan_data_legacy
    data = extract_plan_data_legacy("plan.pdf", "B13")

    # Ou avec plus de contrôle:
    extractor = SuperExtractor(use_ocr=True)
    result = extractor.extract("plan.pdf", "B13")
    print(result.to_legacy_format())
"""

import re
import logging
import json
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RoomType(Enum):
    """Types de pièces standardisés"""
    ENTRY = "entree"
    LIVING_ROOM = "sejour"
    KITCHEN = "cuisine"
    LIVING_KITCHEN = "sejour_cuisine"
    BEDROOM = "chambre"
    BATHROOM = "salle_de_bain"
    SHOWER_ROOM = "salle_d_eau"
    WC = "wc"
    CIRCULATION = "circulation"
    STORAGE = "storage"
    BALCONY = "balcon"
    TERRACE = "terrasse"
    GARDEN = "jardin"
    LOGGIA = "loggia"
    PATIO = "patio"
    PARKING = "parking"
    CELLAR = "cave"


@dataclass
class ExtractedRoom:
    """Une pièce extraite du plan"""
    name_raw: str
    name_normalized: str
    surface: float
    room_type: RoomType
    is_exterior: bool = False
    room_number: Optional[int] = None
    source: str = "unknown"


@dataclass  
class ExtractionResult:
    """Résultat complet d'extraction"""
    reference: str = ""
    property_type: str = "appartment"
    typology: str = ""
    floor: str = ""
    living_space: float = 0.0
    rooms: List[ExtractedRoom] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)

    def to_legacy_format(self) -> Dict[str, Any]:
        """Convertit au format legacy attendu par l'utilisateur"""
        surface_detail = {}
        for r in self.rooms:
            key = r.name_normalized
            surface_detail[key] = r.surface

        return {
            self.reference: {
                "parcelTypeId": self.property_type,
                "parcelTypeLabel": "Appartement" if self.property_type == "appartment" else "Maison",
                "typology": self.typology,
                "floor": self.floor,
                "orientation": "",
                "price": "N.C",
                "living_space": str(self.living_space),
                "surfaceDetail": surface_detail,
                "option": {
                    "balcony": any(r.room_type == RoomType.BALCONY for r in self.rooms),
                    "terrace": any(r.room_type == RoomType.TERRACE for r in self.rooms),
                    "garden": any(r.room_type == RoomType.GARDEN for r in self.rooms),
                    "loggia": any(r.room_type == RoomType.LOGGIA for r in self.rooms),
                    "parking": any(r.room_type == RoomType.PARKING for r in self.rooms),
                },
                "tva": "",
                "pinel": "",
                "state": "available",
                "customData": {
                    "sources": self.sources,
                    "method": "super_extractor_v2"
                },
                "_validation": {
                    "is_valid": len(self.validation_errors) == 0,
                    "errors": self.validation_errors,
                    "warnings": self.validation_warnings
                }
            }
        }


class SuperExtractor:
    """
    Extracteur universel de plans immobiliers PDF.

    Combine PyMuPDF (extraction rapide) et OCR (fallback pour scans).
    """

    # Patterns de surfaces - ordre de priorité
    SURFACE_PATTERNS = [
        # Format: NOM PIÈCE 00.00 m² (le plus courant)
        r"([A-Z][A-Z\s\-/\.\d]*?)\s*(\d+[\.,]\d+)\s*m[²2]",
        # Format avec : NOM: 00.00 m²
        r"([A-Z][A-Z\s\-/\.\d]*?)\s*:\s*(\d+[\.,]\d+)\s*m[²2]",
    ]

    # Mapping des noms de pièces vers types standardisés
    ROOM_ALIASES = {
        # Entrée / Circulation
        r"^(ENTREE|ENTR[ÉE]E|HALL|VESTIBULE|DGT|D\.G\.T|D[ÉE]GAGEMENT|COULOIR|PALIER)$": RoomType.ENTRY,

        # Séjour / Salon
        r"^(SEJOUR|S[ÉE]JOUR|SALON|RECEPTION|R[ÉE]CEPTION|LIVING|DOUBLE SEJOUR)$": RoomType.LIVING_ROOM,

        # Cuisine
        r"^CUISINE": RoomType.KITCHEN,

        # Séjour/Cuisine combiné
        r"^(SEJOUR|S[ÉE]JOUR|RECEPTION).*(CUISINE|KITCHEN)": RoomType.LIVING_KITCHEN,
        r"^CUISINE.*(SEJOUR|S[ÉE]JOUR|RECEPTION)": RoomType.LIVING_KITCHEN,

        # Chambres (avec capture du numéro)
        r"^CHAMBRE\s*(\d*)$": RoomType.BEDROOM,
        r"^CH\.?\s*(\d+)$": RoomType.BEDROOM,
        r"^CH\s+(\d+)$": RoomType.BEDROOM,

        # Salle de bain
        r"^(SALLE DE BAINS?|SDB|S\.D\.B\.?)$": RoomType.BATHROOM,

        # Salle d'eau  
        r"^(SALLE D'EAU|SDE|S\.D\.E\.?)$": RoomType.SHOWER_ROOM,

        # WC
        r"^(WC|W\.C\.?|TOILETT?E?S?|RGT WC|RGT W\.C\.?)$": RoomType.WC,

        # Rangement
        r"^(DRESSING|PLACARD|CELLIER|BUANDERIE)$": RoomType.STORAGE,

        # Extérieur - Balcon
        r"^BALCON\s*(\d*)$": RoomType.BALCONY,

        # Extérieur - Terrasse
        r"^TERRASSE\s*(\d*)$": RoomType.TERRACE,

        # Extérieur - Jardin
        r"^JARDIN": RoomType.GARDEN,

        # Extérieur - Loggia
        r"^LOGGIA": RoomType.LOGGIA,

        # Extérieur - Patio
        r"^PATIO": RoomType.PATIO,

        # Parking / Garage
        r"^PARKING": RoomType.PARKING,
        r"^GARAGE": RoomType.PARKING,
        r"^BOX": RoomType.PARKING,

        # Cave
        r"^CAVE": RoomType.CELLAR,
    }

    # Patterns pour référence du bien
    REF_PATTERNS = [
        r"\b([A-Z]\d{2,4})\b",  # B13, A123, T45
        r"Lot\s*:?\s*(\w+)",
        r"Appartement\s*:?\s*(\w+)",
        r"R[ÉE]f[ÉE]rence\s*:?\s*(\w+)",
    ]

    # Patterns pour étage
    FLOOR_PATTERNS = [
        (r"\bRDC\b", "RDC"),
        (r"rez[- ]?de[- ]?chauss[éeè]e", "RDC"),
        (r"\bR\+(\d+)\b", lambda m: f"R+{m.group(1)}"),
        (r"(\d+)\s*(?:er|e|ème|eme)\s*(?:étage|etage)", lambda m: f"R+{m.group(1)}"),
        (r"premier\s*(?:étage|etage)", "R+1"),
        (r"deuxième\s*(?:étage|etage)", "R+2"),
        (r"troisième\s*(?:étage|etage)", "R+3"),
    ]

    def __init__(self, use_ocr: bool = True, tesseract_path: Optional[str] = None):
        """
        Initialise l'extracteur.

        Args:
            use_ocr: Active l'OCR comme fallback si PyMuPDF donne peu de résultats
            tesseract_path: Chemin vers l'exécutable tesseract (optionnel)
        """
        self.use_ocr = use_ocr
        self.tesseract_path = tesseract_path

    def extract(self, pdf_path: str, reference_hint: Optional[str] = None) -> ExtractionResult:
        """
        Extrait les données d'un plan PDF.

        Args:
            pdf_path: Chemin vers le fichier PDF
            reference_hint: Référence attendue (ex: "B13")

        Returns:
            ExtractionResult avec toutes les données structurées
        """
        logger.info(f"🔍 Extraction: {pdf_path}")

        result = ExtractionResult()
        path = Path(pdf_path)

        if not path.exists():
            result.validation_errors.append(f"Fichier non trouvé: {pdf_path}")
            return result

        # Étape 1: Extraction PyMuPDF
        text_pymupdf = self._extract_pymupdf(path)
        rooms_pymupdf = self._extract_rooms(text_pymupdf, "pymupdf")
        meta_pymupdf = self._extract_metadata(text_pymupdf)

        logger.info(f"  📄 PyMuPDF: {len(rooms_pymupdf)} pièces trouvées")

        # Étape 2: OCR si nécessaire et autorisé
        rooms_ocr = []
        meta_ocr = {}

        if self.use_ocr and len(rooms_pymupdf) < 3:
            logger.info("  🔄 OCR activé (fallback)")
            text_ocr = self._extract_ocr(path)
            rooms_ocr = self._extract_rooms(text_ocr, "ocr")
            meta_ocr = self._extract_metadata(text_ocr)
            logger.info(f"  🔍 OCR: {len(rooms_ocr)} pièces trouvées")

        # Étape 3: Fusion intelligente
        all_rooms = self._merge_rooms(rooms_pymupdf, rooms_ocr)
        metadata = self._merge_metadata(meta_pymupdf, meta_ocr, reference_hint)

        logger.info(f"  🔀 Total: {len(all_rooms)} pièces uniques")

        # Étape 4: Construction du résultat
        result.reference = metadata.get("reference", reference_hint or "UNKNOWN")
        result.floor = metadata.get("floor", "")
        result.living_space = metadata.get("living_space", 0.0)
        result.rooms = all_rooms
        result.sources = {r.name_normalized: r.source for r in all_rooms}

        # Détection automatique
        result.typology = self._detect_typology(all_rooms)
        result.property_type = self._detect_property_type(all_rooms)

        # Étape 5: Validation mathématique
        self._validate(result)

        logger.info(f"  ✅ Extraction terminée: {result.typology}, {result.floor}")

        return result

    def _extract_pymupdf(self, path: Path) -> str:
        """Extraction texte avec PyMuPDF (fitz)"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return self._clean_text(text)
        except ImportError:
            logger.error("PyMuPDF (fitz) non installé: pip install pymupdf")
            return ""
        except Exception as e:
            logger.warning(f"PyMuPDF error: {e}")
            return ""

    def _extract_ocr(self, path: Path) -> str:
        """Extraction texte avec Tesseract OCR"""
        try:
            import fitz
            from PIL import Image
            import pytesseract

            doc = fitz.open(path)
            text = ""

            for page in doc:
                # Rendu haute résolution pour meilleur OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # OCR avec config optimisée
                config = r"--oem 3 --psm 6"
                page_text = pytesseract.image_to_string(img, lang="fra+eng", config=config)
                text += page_text + "\n"

            doc.close()
            return self._clean_text(text)
        except ImportError as e:
            logger.error(f"OCR dépendances manquantes: {e}")
            return ""
        except Exception as e:
            logger.warning(f"OCR error: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """
        Nettoie et normalise le texte extrait.

        - Normalise les espaces
        - Convertit les virgules françaises en points pour les nombres
        """
        # Normalise les espaces multiples
        text = re.sub(r"\s+", " ", text)

        # Normalise les nombres: "4,38 m²" -> "4.38 m²"
        # Capture les nombres au format XX,XX suivis d'unités
        text = re.sub(r"(\d),(\d{2})\s*m", r"\1.\2 m", text)

        return text.strip()

    def _extract_rooms(self, text: str, source: str) -> List[ExtractedRoom]:
        """
        Extrait les pièces et leurs surfaces du texte.

        Args:
            text: Texte nettoyé du PDF
            source: "pymupdf" ou "ocr" pour traçabilité

        Returns:
            Liste de ExtractedRoom
        """
        rooms = []
        seen = {}  # Évite les doublons

        for pattern in self.SURFACE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                name_raw = match.group(1).strip().upper()
                surface_str = match.group(2)

                # Filtres de qualité
                if len(name_raw) < 2 or len(name_raw) > 50:
                    continue

                # Conversion surface
                try:
                    surface = float(surface_str.replace(",", "."))
                except ValueError:
                    continue

                # Ignore les valeurs aberrantes
                if surface < 0.5 or surface > 500:
                    continue

                # Skip les totaux et métadonnées
                skip_keywords = ["TOTAL", "SURFACE HABITABLE", "ANNEXE", "PLAN", "VENTE"]
                if any(kw in name_raw for kw in skip_keywords):
                    continue

                # Normalisation du nom
                room_type, number, name_norm = self._normalize_room(name_raw)
                if not room_type:
                    continue  # Pièce non reconnue

                # Détermine si extérieur
                is_exterior = room_type in [
                    RoomType.BALCONY, RoomType.TERRACE, RoomType.GARDEN,
                    RoomType.LOGGIA, RoomType.PARKING, RoomType.CELLAR
                ]

                # Gestion des doublons
                if name_norm in seen:
                    existing = seen[name_norm]
                    if surface > existing.surface:
                        existing.surface = surface
                        existing.source = source
                    continue

                room = ExtractedRoom(
                    name_raw=name_raw,
                    name_normalized=name_norm,
                    surface=surface,
                    room_type=room_type,
                    is_exterior=is_exterior,
                    room_number=number,
                    source=source
                )

                seen[name_norm] = room
                rooms.append(room)

        return rooms

    def _normalize_room(self, name: str) -> Tuple[Optional[RoomType], Optional[int], str]:
        """
        Normalise un nom de pièce vers un type standard.

        Returns:
            Tuple (RoomType, room_number, normalized_name)
        """
        name_clean = name.strip()

        for pattern, room_type in self.ROOM_ALIASES.items():
            match = re.match(pattern, name_clean, re.IGNORECASE)
            if match:
                # Extraction numéro de pièce si présent
                number = None
                if len(match.groups()) > 0:
                    num_str = match.group(1)
                    if num_str:
                        try:
                            number = int(num_str)
                        except ValueError:
                            pass

                # Génère le nom normalisé
                if number:
                    norm_name = f"{room_type.value}_{number}"
                else:
                    norm_name = room_type.value

                return room_type, number, norm_name

        return None, None, ""

    def _merge_rooms(self, rooms1: List[ExtractedRoom], rooms2: List[ExtractedRoom]) -> List[ExtractedRoom]:
        """
        Fusionne deux listes de pièces (PyMuPDF + OCR).

        Stratégie:
        - Garde toutes les pièces uniques
        - En cas de doublon, garde la valeur la plus grande (souvent plus précise)
        """
        merged = {r.name_normalized: r for r in rooms1}

        for r in rooms2:
            if r.name_normalized in merged:
                existing = merged[r.name_normalized]
                # Garde la plus grande surface si cohérente
                if r.surface > existing.surface:
                    merged[r.name_normalized] = r
            else:
                merged[r.name_normalized] = r

        return list(merged.values())

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Extrait les métadonnées du document.

        Returns:
            Dict avec reference, floor, living_space, etc.
        """
        meta = {}

        # Référence du bien
        for pattern in self.REF_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                meta["reference"] = match.group(1)
                break

        # Étage
        for pattern, val_or_func in self.FLOOR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if callable(val_or_func):
                    meta["floor"] = val_or_func(match)
                else:
                    meta["floor"] = val_or_func
                break

        # Surface habitable totale
        # Cherche "SURFACE HABITABLE 44.91m²" ou variantes
        sh_patterns = [
            r"SURFACE\s+HABITABLE\s*[:\s]*(\d+[\.,]\d+)",
            r"Surface\s+habitable\s*[:\s]*(\d+[\.,]\d+)",
            r"SHON\s*[:\s]*(\d+[\.,]\d+)",
        ]
        for pattern in sh_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    meta["living_space"] = float(match.group(1).replace(",", "."))
                    break
                except:
                    pass

        return meta

    def _merge_metadata(self, meta1: Dict, meta2: Dict, hint: Optional[str]) -> Dict:
        """Fusionne métadonnées PyMuPDF et OCR"""
        merged = meta1.copy()

        for key, val in meta2.items():
            if key not in merged or not merged[key]:
                merged[key] = val

        # Utilise le hint si aucune référence trouvée
        if hint and not merged.get("reference"):
            merged["reference"] = hint

        return merged

    def _detect_typology(self, rooms: List[ExtractedRoom]) -> str:
        """
        Détecte la typologie (T2, T3, Studio, etc.).

        Règles:
        - Compte les chambres (bedroom)
        - T{n_chambres + 1} (le +1 est le séjour)
        - 0 chambres + séjour = Studio
        """
        bedrooms = sum(1 for r in rooms if r.room_type == RoomType.BEDROOM)

        if bedrooms == 0:
            # Vérifie s'il y a un séjour/cuisine
            has_living = any(r.room_type in [RoomType.LIVING_ROOM, RoomType.LIVING_KITCHEN] 
                           for r in rooms)
            return "Studio" if has_living else "T1"

        return f"T{bedrooms + 1}"

    def _detect_property_type(self, rooms: List[ExtractedRoom]) -> str:
        """
        Détecte si c'est un appartement ou une maison.

        Heuristiques:
        - Présence de jardin + cave -> maison
        - Sinon appartement par défaut
        """
        has_garden = any(r.room_type == RoomType.GARDEN for r in rooms)
        has_cellar = any(r.room_type == RoomType.CELLAR for r in rooms)

        if has_garden and has_cellar:
            return "house"

        return "appartment"

    def _validate(self, result: ExtractionResult):
        """
        Valide la cohérence mathématique des surfaces.

        Vérifie que la somme des pièces intérieures correspond à la surface habitable déclarée.
        """
        # Calcule somme des pièces intérieures
        interior_sum = sum(r.surface for r in result.rooms if not r.is_exterior)

        if result.living_space > 0:
            diff = abs(interior_sum - result.living_space)

            if diff > 1.0:  # Tolérance 1m²
                result.validation_errors.append(
                    f"Surface mismatch: calc={interior_sum:.2f}m², "
                    f"expected={result.living_space:.2f}m², diff={diff:.2f}m²"
                )
            elif diff > 0.1:  # Petit écart possible (arrondis)
                result.validation_warnings.append(f"Surface gap: {diff:.2f}m²")

        # Vérifications de base
        if not result.rooms:
            result.validation_errors.append("No rooms detected")

        if not any(r.room_type == RoomType.BEDROOM for r in result.rooms):
            if not any(r.room_type in [RoomType.LIVING_ROOM, RoomType.LIVING_KITCHEN] 
                      for r in result.rooms):
                result.validation_warnings.append("No bedroom or living room detected")


# =============================================================================
# FONCTIONS PUBLIQUES (API simple)
# =============================================================================

def extract_plan_data(pdf_path: str, reference_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Fonction simple pour extraire les données d'un plan.

    Args:
        pdf_path: Chemin vers le PDF
        reference_hint: Référence attendue (ex: "B13")

    Returns:
        Dict au format legacy
    """
    extractor = SuperExtractor()
    result = extractor.extract(pdf_path, reference_hint)
    return result.to_legacy_format()


def extract_plan_data_legacy(pdf_path: str, reference_hint: Optional[str] = None) -> Dict[str, Any]:
    """Alias pour compatibilité avec l'ancien code"""
    return extract_plan_data(pdf_path, reference_hint)


def batch_extract(pdf_paths: List[str], hints: Optional[List[str]] = None) -> Dict[str, Dict]:
    """
    Extraction batch de plusieurs PDFs.

    Args:
        pdf_paths: Liste des chemins PDF
        hints: Liste optionnelle des références attendues

    Returns:
        Dict {reference: data}
    """
    extractor = SuperExtractor()
    results = {}

    for i, path in enumerate(pdf_paths):
        hint = hints[i] if hints and i < len(hints) else None
        result = extractor.extract(path, hint)
        data = result.to_legacy_format()
        results.update(data)

    return results

