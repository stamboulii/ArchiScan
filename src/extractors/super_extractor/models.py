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
    property_type: str = "appartment"
    typology: str = ""
    floor: str = ""
    building: str = ""
    program_name: str = ""
    address: str = ""
    living_space: float = 0.0
    annex_space: float = 0.0
    rooms: List[ExtractedRoom] = field(default_factory=list)
    composites: Dict[str, List[str]] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
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

    def to_legacy_format(self) -> Dict[str, Any]:
        surface_detail = {r.name_normalized: r.surface for r in self.rooms}

        return {
            self.reference: {
                "parcelTypeId": self.property_type,
                "parcelTypeLabel": self._property_label(),
                "typology": self.typology,
                "floor": self.floor,
                "building": self.building,
                "orientation": "",
                "price": "N.C",
                "living_space": str(self.living_space),
                "annex_space": str(self.annex_space),
                "surfaceDetail": surface_detail,
                "surfaceComposites": self.composites,
                "surfaceTotals": {
                    "habitable": self.living_space,
                    "habitable_calc": self.interior_surface_calc,
                    "annexe": self.annex_space,
                    "annexe_calc": self.annex_surface_calc,
                },
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
                    "method": "super_extractor_v3",
                    "promoter": self.promoter_detected,
                    "address": self.address,
                    "program": self.program_name,
                },
                "_validation": {
                    "is_valid": len(self.validation_errors) == 0,
                    "errors": self.validation_errors,
                    "warnings": self.validation_warnings,
                },
            }
        }

    def _property_label(self) -> str:
        return {"appartment": "Appartement", "house": "Maison",
                "commercial": "Commerce", "office": "Bureau"
                }.get(self.property_type, "Appartement")