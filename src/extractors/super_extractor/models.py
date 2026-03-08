"""
Models - Dataclasses et enums partagés
"""

from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RoomType(Enum):
    ENTRY = "entree"
    LIVING_ROOM = "sejour"
    KITCHEN = "cuisine"
    LIVING_KITCHEN = "sejour_cuisine"
    RECEPTION = "reception"
    BEDROOM = "chambre"
    BATHROOM = "salle_de_bain"
    SHOWER_ROOM = "salle_d_eau"
    WC = "wc"
    CIRCULATION = "circulation"
    STORAGE = "storage"
    DRESSING = "dressing"
    BALCONY = "balcon"
    TERRACE = "terrasse"
    GARDEN = "jardin"
    LOGGIA = "loggia"
    PATIO = "patio"
    PARKING = "parking"
    CELLAR = "cave"
    UNKNOWN = "unknown"


EXTERIOR_ROOM_TYPES = {
    RoomType.BALCONY, RoomType.TERRACE, RoomType.GARDEN,
    RoomType.LOGGIA, RoomType.PATIO, RoomType.PARKING, RoomType.CELLAR,
}

SURFACE_RANGES = {
    RoomType.ENTRY: (1.0, 25.0),
    RoomType.LIVING_ROOM: (8.0, 80.0),
    RoomType.KITCHEN: (3.0, 40.0),
    RoomType.LIVING_KITCHEN: (15.0, 100.0),
    RoomType.RECEPTION: (15.0, 120.0),
    RoomType.BEDROOM: (5.0, 40.0),
    RoomType.BATHROOM: (2.0, 20.0),
    RoomType.SHOWER_ROOM: (2.0, 15.0),
    RoomType.WC: (0.8, 10.0),
    RoomType.CIRCULATION: (1.0, 20.0),
    RoomType.STORAGE: (0.5, 15.0),
    RoomType.DRESSING: (1.0, 20.0),
    RoomType.BALCONY: (1.0, 70.0),
    RoomType.TERRACE: (2.0, 200.0),
    RoomType.GARDEN: (5.0, 5000.0),
    RoomType.LOGGIA: (2.0, 30.0),
    RoomType.PARKING: (8.0, 40.0),
    RoomType.CELLAR: (2.0, 50.0),
}


@dataclass
class ExtractedRoom:
    name_raw: str
    name_normalized: str
    surface: float
    room_type: RoomType
    is_exterior: bool = False
    is_composite: bool = False
    room_number: Optional[int] = None
    source: str = "unknown"
    confidence: float = 1.0
    bbox: Optional[Tuple[float, float, float, float]] = None
    children: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    reference: str = ""
    parcel_label: str = ""  # Label du lot (ex: "M011")
    page_number: int = 0  # Numéro de page d'où vient l'extraction
    property_type: str = "appartment"
    property_type_hint: str = ""  # Hint from metadata (e.g., "magasin" from MAGASIN reference)
    typology: str = ""
    floor: str = ""
    building: str = ""
    program_name: str = ""
    address: str = ""
    living_space: float = 0.0
    annex_space: float = 0.0
    # Nouveaux champs pour maisons
    surface_propriete: float = 0.0
    surface_espaces_verts: float = 0.0
    niveaux: List[str] = field(default_factory=list)
    rooms: List[ExtractedRoom] = field(default_factory=list)
    composites: Dict[str, List[str]] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    floor_results: "List[Any]" = field(default_factory=list)  # pour duplex/maison multi-niveaux
    promoter_detected: str = ""

    @property
    def interior_rooms(self) -> List[ExtractedRoom]:
        """Pièces intérieures hors composites (évite double-comptage)"""
        return [r for r in self.rooms if not r.is_exterior and not r.is_composite]

    @property
    def exterior_rooms(self) -> List[ExtractedRoom]:
        return [r for r in self.rooms if r.is_exterior]

    @property
    def interior_surface_calc(self) -> float:
        return round(sum(r.surface for r in self.interior_rooms), 2)

    @property
    def annex_surface_calc(self) -> float:
        return round(sum(r.surface for r in self.exterior_rooms), 2)

    def to_legacy_format(self, include_raw_text: bool = False) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)
        
        surface_detail = {r.name_normalized: r.surface for r in self.rooms}
        
        # Determine options
        has_garden  = (
            any(r.room_type == RoomType.GARDEN for r in self.rooms)
            or self.surface_espaces_verts > 0  # fallback: détecté dans les métadonnées
        )
        has_balcony = any(r.room_type == RoomType.BALCONY for r in self.rooms)
        has_terrace = any(r.room_type == RoomType.TERRACE for r in self.rooms)
        has_loggia = any(r.room_type == RoomType.LOGGIA for r in self.rooms)
        has_duplex = self.floor and ('duplex' in self.floor.lower() or 'R+' in self.floor and '+' in self.floor)
        
        # Fallback: detect terrace and balcony from raw text if not found in rooms
        # Also check for exterior spaces like "Terrasse", "Balcon", "Jardin", "Exterieur", "Loggia"
        if self.raw_text:
            raw_lower = self.raw_text.lower()
            # Check for terrace
            if not has_terrace:
                has_terrace = 'terrasse' in raw_lower
            # Check for balcony (also check for "Balcon" without accent)
            if not has_balcony:
                has_balcony = 'balcon' in raw_lower
            # Check for loggia
            if not has_loggia:
                has_loggia = 'loggia' in raw_lower
            # Check for garden
            if not has_garden:
                has_garden = 'jardin' in raw_lower or 'espaces verts' in raw_lower
            # Check for exterior (balcony/terrace indicator)
            if not has_balcony and not has_terrace:
                has_balcony = 'exterieur' in raw_lower or 'exterieur' in raw_lower
        has_loggia = has_loggia or any(r.room_type == RoomType.LOGGIA for r in self.rooms)
        # Parking pur: type PARKING dont le nom normalisé NE contient PAS 'garage'
        has_parking = any(
            r.room_type == RoomType.PARKING and "garage" not in r.name_normalized.lower()
            for r in self.rooms
        )
        # Garage: type PARKING dont le nom normalisé contient 'garage' (ou 'box')
        # OU cave/cellar (il arrive que le garage soit classé en cave pour les maisons)
        has_garage = (
            any(
                r.room_type == RoomType.PARKING
                and ("garage" in r.name_normalized.lower() or "box" in r.name_normalized.lower())
                for r in self.rooms
            )
            or any(r.room_type == RoomType.CELLAR for r in self.rooms)
        )
        
        result = {
            self.reference: {
                "parcelTypeId": self.property_type,
                "parcelTypeLabel": self._property_label(),
                "typology": self.typology,
                "floor": self.floor,
                "building": self.building,
                "orientation": "",
                "price": "N.C",
                "living_space": str(self.living_space) if self.living_space else str(self.interior_surface_calc),
                "annex_space": str(self.annex_space if self.annex_space else self.annex_surface_calc),
                "surfaceDetail": surface_detail,
                "surfaceComposites": self.composites,
                "multi_floor_surfaces": getattr(self, 'multi_floor_surfaces', {}),  # Add floor surfaces
                "surfaceTotals": {
                    "habitable": self.living_space if self.living_space else self.interior_surface_calc,
                    "habitable_calc": self.interior_surface_calc,
                    "annexe": self.annex_space if self.annex_space else self.annex_surface_calc,
                    "annexe_calc": self.annex_surface_calc,
                },
                "option": {
                    "balcony": has_balcony,
                    "terrace": has_terrace,
                    "garden": has_garden,
                    "loggia": has_loggia,
                    "duplex": has_duplex,
                    "parking": has_parking,
                    "garage": has_garage,
                },
                "tva": "",
                "pinel": "",
                "state": "available",
                "customData": {
                    "sources": self.sources,
                    "method": "super_extractor_v3",
                    "promoter": self.promoter_detected,
                    "address": self.address,
                    "program": self.program_name,
                    # Nouveaux champs pour maisons
                    "surface_propriete_totale": self.surface_propriete,
                    "surface_espaces_verts": self.surface_espaces_verts,
                    "niveaux": self.niveaux if self.niveaux else self._floor_to_niveaux(self.floor),
                },
                "pageNumber": self.page_number,
                "parcelLabel": self.parcel_label or self.reference,
                "_validation": {
                    "is_valid": len(self.validation_errors) == 0,
                    "errors": self.validation_errors,
                    "warnings": self.validation_warnings,
                },
            }
        }
        
        # Debug: afficher la cle et la presence de _validation
        logger.info(f"to_legacy_format: reference={self.reference}, has_validation={'_validation' in result[self.reference]}")
        
        # Ajouter le texte brut seulement si demande
        if include_raw_text and self.raw_text:
            result[self.reference]['_raw_text'] = self.raw_text

        # Si multi-niveaux (duplex/maison): imbriquer les résultats par étage
        if self.floor_results:
            nested = {}
            for floor_result in self.floor_results:
                floor_legacy = floor_result.to_legacy_format(include_raw_text=False)
                # floor_legacy = {"A18": {...}} → on veut {"A18_R+1": {...}}
                floor_key = f"{floor_result.reference}_{floor_result.floor}"
                inner = list(floor_legacy.values())[0]
                inner["floor_key"] = floor_key
                nested[floor_key] = inner
            # Remplacer le contenu par la structure imbriquée
            result[self.reference] = nested

        return result
    
    def _floor_to_niveaux(self, floor: str) -> List[str]:
        """Convertit le floor string en liste de niveaux."""
        if not floor:
            return []
        floor_upper = floor.upper()
        niveaux = []
        if "RDC" in floor_upper or floor == "RDC":
            niveaux.append("Rez-de-chaussée")
        # Chercher les etages (R+1, R+2, etc.)
        import re
        for match in re.finditer(r"R\+(\d+)", floor_upper):
            niveau = int(match.group(1))
            if niveau == 1:
                niveaux.append("Étage")
            else:
                niveaux.append(f"{niveau}e étage")
        return niveaux

    def _property_label(self) -> str:
        return {"appartment": "Appartement", "house": "Maison",
                "commercial": "Commerce", "magasin": "Magasin", "office": "Bureau"
                }.get(self.property_type, "Appartement")