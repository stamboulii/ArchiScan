"""
SuperExtractor v3 - Orchestrateur principal
============================================

Pipeline:
1. TextExtractor     → texte brut (PyMuPDF + OCR)
2. SpatialExtractor  → tableau récapitulatif par positions
3. RoomNormalizer    → normalisation des noms
4. CompositeResolver → Réception = Séjour + Cuisine
5. MetadataExtractor → référence, étage, promoteur
6. PlanValidator     → validation mathématique

Usage:
    extractor = SuperExtractor()
    result = extractor.extract("plan.pdf", "A008")
    data = result.to_legacy_format()  # dict
"""

import re
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List

from .models import RoomType, ExtractedRoom, ExtractionResult, EXTERIOR_ROOM_TYPES
from .text_extractor import TextExtractor
from .spatial_extractor import SpatialExtractor
from .room_normalizer import RoomNormalizer
from .composite_resolver import CompositeResolver
from .metadata_extractor import MetadataExtractor
from .plan_validator import PlanValidator

logger = logging.getLogger(__name__)


class SuperExtractor:

    SURFACE_PATTERNS = [
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s+(\d+[\.,]\d+)\s*m[²2]",
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s*:\s*(\d+[\.,]\d+)\s*m[²2]",
    ]

    SKIP_KEYWORDS = [
        "TOTAL", "SURFACE HABITABLE", "SURFACE ANNEXE",
        "PLAN", "VENTE", "DATE", "IND", "ECHELLE",
    ]

    def __init__(self, use_ocr: bool = True, tesseract_path: Optional[str] = None):
        self.text_extractor = TextExtractor(
            use_ocr=use_ocr, tesseract_path=tesseract_path
        )
        self.spatial_extractor = SpatialExtractor()
        self.normalizer = RoomNormalizer()
        self.composite_resolver = CompositeResolver()
        self.metadata_extractor = MetadataExtractor()
        self.validator = PlanValidator()

    def extract(
        self, pdf_path: str, reference_hint: Optional[str] = None
    ) -> ExtractionResult:
        """
        Point d'entrée principal.

        Args:
            pdf_path: Chemin vers le fichier PDF
            reference_hint: Référence attendue (ex: "A008")

        Returns:
            ExtractionResult (appeler .to_legacy_format() pour obtenir un dict)
        """
        logger.info(f"🔍 SuperExtractor v3: {pdf_path}")
        result = ExtractionResult()
        path = Path(pdf_path)

        if not path.exists():
            result.validation_errors.append(f"Fichier non trouvé: {pdf_path}")
            return result

        # Reset normalizer pour cette extraction
        self.normalizer.reset()

        # ── ÉTAPE 1: Extraction texte brut ────────────────────
        text_data = self.text_extractor.extract(pdf_path)
        primary_text = text_data["text_pymupdf"] or text_data["text_ocr"]
        result.raw_text = primary_text[:1000]
        logger.info(
            f"  📄 Texte: {len(primary_text)} chars, "
            f"source={text_data['primary_source']}"
        )

        # ── ÉTAPE 2: Extraction spatiale (tableau récap) ──────
        spatial_data = self.spatial_extractor.extract_from_pages(
            text_data["pages_data"]
        )
        spatial_rows = spatial_data["table_rows"]
        logger.info(f"  📐 Spatial: {len(spatial_rows)} lignes de tableau")
        logger.info(f"  📐 Spatial rows trouvées:")
        for name, surface in spatial_rows:
            logger.info(f"    '{name}' → {surface}")
        logger.info(f"  📄 Texte brut (500 chars):")
        logger.info(primary_text[:500])

        # ── ÉTAPE 3: Construction des pièces ──────────────────
        rooms = []

        # # Priorité 1: tableau spatial (le plus fiable)
        # if spatial_rows:
        #     rooms = self._rooms_from_table(spatial_rows, "spatial")
        #     logger.info(f"  ✅ {len(rooms)} pièces depuis tableau spatial")

        # # Priorité 2: regex sur texte PyMuPDF
        # if len(rooms) < 3:
        #     rooms_regex = self._rooms_from_regex(
        #         text_data["text_pymupdf"], "pymupdf"
        #     )
        #     rooms = self._merge_rooms(rooms, rooms_regex)
        #     logger.info(f"  📝 +regex PyMuPDF → {len(rooms)} pièces")

        # # Priorité 3: regex sur texte OCR
        # if len(rooms) < 3 and text_data["text_ocr"]:
        #     rooms_ocr = self._rooms_from_regex(text_data["text_ocr"], "ocr")
        #     rooms = self._merge_rooms(rooms, rooms_ocr)
        #     logger.info(f"  🔍 +regex OCR → {len(rooms)} pièces")
        # ── ÉTAPE 3: Construction des pièces ──────────────────

        # Priorité 1: tableau spatial (le plus fiable)
        if spatial_rows:
            self.normalizer.reset()  # Reset pour cette source
            rooms = self._rooms_from_table(spatial_rows, "spatial")
            logger.info(f"  ✅ {len(rooms)} pièces depuis tableau spatial")

        # Priorité 2: regex sur texte PyMuPDF
        if len(rooms) < 3:
            self.normalizer.reset()  # Reset pour cette source
            rooms_regex = self._rooms_from_regex(
                text_data["text_pymupdf"], "pymupdf"
            )
            rooms = self._merge_rooms(rooms, rooms_regex)
            logger.info(f"  📝 +regex PyMuPDF → {len(rooms)} pièces")

        # Priorité 3: regex sur texte OCR
        if len(rooms) < 3 and text_data["text_ocr"]:
            self.normalizer.reset()  # Reset pour cette source
            rooms_ocr = self._rooms_from_regex(text_data["text_ocr"], "ocr")
            rooms = self._merge_rooms(rooms, rooms_ocr)
            logger.info(f"  🔍 +regex OCR → {len(rooms)} pièces")   

        result.rooms = rooms
        result.sources = {r.name_normalized: r.source for r in rooms}

        # ── ÉTAPE 4: Résolution composites ────────────────────
        result.rooms, result.composites = self.composite_resolver.resolve(
            result.rooms
        )
        if result.composites:
            logger.info(f"  🔗 Composites: {result.composites}")

        # ── ÉTAPE 5: Métadonnées ──────────────────────────────
        meta = self.metadata_extractor.extract(
            primary_text,
            reference_hint=reference_hint,
            spatial_metadata=spatial_data.get("metadata_lines"),
        )

        result.reference = meta.get("reference", reference_hint or "UNKNOWN")
        result.floor = meta.get("floor", "")
        result.building = meta.get("building", "")
        result.promoter_detected = meta.get("promoter", "")
        result.address = meta.get("address", "")

        # Surfaces: spatial a priorité sur metadata
        result.living_space = (
            spatial_data.get("living_space")
            or meta.get("living_space", 0.0)
        )
        result.annex_space = (
            spatial_data.get("annex_space")
            or meta.get("annex_space", 0.0)
        )

        # ── ÉTAPE 6: Typology + property type ─────────────────
        result.typology = (
            meta.get("typology_hint") or self._detect_typology(rooms)
        )
        result.property_type = self._detect_property_type(rooms)

        # ── ÉTAPE 7: Validation ───────────────────────────────
        self.validator.validate(result)

        logger.info(
            f"  ✅ {result.reference} | {result.typology} | {result.floor} | "
            f"{len(result.rooms)} pièces | "
            f"valid={len(result.validation_errors) == 0}"
        )
        return result

    # ─── Méthodes internes ────────────────────────────────

    def _rooms_from_table(self, rows, source):
        """Convertit les lignes du tableau spatial en ExtractedRoom"""
        rooms = []
        for name_raw, surface_str in rows:
            try:
                surface = float(surface_str)
            except ValueError:
                continue
            if surface < 0.5 or surface > 500:
                continue

            norm, rtype, num, ext, conf = self.normalizer.normalize(name_raw)
            if not rtype:
                logger.debug(f"Pièce non reconnue (table): '{name_raw}'")
                continue

            rooms.append(ExtractedRoom(
                name_raw=name_raw,
                name_normalized=norm,
                surface=surface,
                room_type=rtype,
                is_exterior=ext,
                room_number=num,
                source=source,
                confidence=conf,
            ))
        return rooms

    def _rooms_from_regex(self, text, source):
        """Extrait les pièces par regex depuis le texte brut (fallback)"""
        rooms = []
        for pattern in self.SURFACE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name_raw = match.group(1).strip()
                surface_str = match.group(2)

                if len(name_raw) < 2 or len(name_raw) > 50:
                    continue
                try:
                    surface = float(surface_str.replace(",", "."))
                except ValueError:
                    continue
                if surface < 0.5 or surface > 500:
                    continue
                if any(kw in name_raw.upper() for kw in self.SKIP_KEYWORDS):
                    continue

                norm, rtype, num, ext, conf = self.normalizer.normalize(name_raw)
                if not rtype:
                    continue

                rooms.append(ExtractedRoom(
                    name_raw=name_raw,
                    name_normalized=norm,
                    surface=surface,
                    room_type=rtype,
                    is_exterior=ext,
                    room_number=num,
                    source=source,
                    confidence=conf * 0.85,  # Moins fiable que spatial
                ))
        return rooms

    def _merge_rooms(self, primary, secondary):
        """
        Fusionne deux listes. Primary a priorité.
        Détecte les doublons par (room_type, room_number) en plus du nom.
        """
        merged = {r.name_normalized: r for r in primary}

        # Index secondaire par (type, number) pour détecter les vrais doublons
        type_index = {}
        for r in primary:
            key = (r.room_type, r.room_number)
            type_index[key] = r

        for r in secondary:
            # Check 1: même nom normalisé
            if r.name_normalized in merged:
                existing = merged[r.name_normalized]
                if r.confidence > existing.confidence:
                    merged[r.name_normalized] = r
                continue

            # Check 2: même (type, number) = vrai doublon avec nom différent
            type_key = (r.room_type, r.room_number)
            if type_key in type_index:
                existing = type_index[type_key]
                # Vérifie que les surfaces sont proches (même pièce)
                if abs(r.surface - existing.surface) < 0.5:
                    logger.debug(
                        f"  Doublon détecté: '{r.name_raw}' = '{existing.name_raw}'"
                    )
                    continue  # Skip ce doublon

            merged[r.name_normalized] = r
            type_index[(r.room_type, r.room_number)] = r

        return list(merged.values())

    def _detect_typology(self, rooms):
        bedrooms = sum(1 for r in rooms if r.room_type == RoomType.BEDROOM)
        if bedrooms == 0:
            has_living = any(
                r.room_type in [
                    RoomType.LIVING_ROOM, RoomType.LIVING_KITCHEN,
                    RoomType.RECEPTION,
                ]
                for r in rooms
            )
            return "Studio" if has_living else "T1"
        return f"T{bedrooms + 1}"

    def _detect_property_type(self, rooms):
        has_garden = any(r.room_type == RoomType.GARDEN for r in rooms)
        has_cellar = any(r.room_type == RoomType.CELLAR for r in rooms)
        return "house" if has_garden and has_cellar else "appartment"


# ═══════════════════════════════════════════════
# API PUBLIQUE
# ═══════════════════════════════════════════════

def extract_plan_data(pdf_path: str, reference_hint: Optional[str] = None) -> Dict[str, Any]:
    """Extrait et retourne directement le format legacy (dict)"""
    extractor = SuperExtractor()
    result = extractor.extract(pdf_path, reference_hint)
    return result.to_legacy_format()


def extract_plan_data_legacy(pdf_path: str, reference_hint: Optional[str] = None) -> Dict[str, Any]:
    """Alias pour compatibilité"""
    return extract_plan_data(pdf_path, reference_hint)


def batch_extract(pdf_paths: List[str], hints: Optional[List[str]] = None) -> Dict[str, Dict]:
    """Extraction batch de plusieurs PDFs"""
    extractor = SuperExtractor()
    results = {}
    for i, path in enumerate(pdf_paths):
        hint = hints[i] if hints and i < len(hints) else None
        results.update(extractor.extract(path, hint).to_legacy_format())
    return results