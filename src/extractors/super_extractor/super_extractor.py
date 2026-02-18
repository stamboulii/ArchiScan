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
        # Format standard: NOM 00.00 m²
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s+(\d+[\.,]\d+)\s*m[²2]",
        # Format collé: NOM 00.00m²  (pas d'espace avant m²)
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s+(\d+[\.,]\d+)m[²2]",
        # Format avec : NOM: 00.00 m²
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s*:\s*(\d+[\.,]\d+)\s*m[²2]",
        # Format tableau: NOM    00,00m²  (espaces multiples, virgule)
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.\d]*?)\s{2,}(\d+[\.,]\d+)\s*m[²2]?",
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
        result.raw_text = primary_text
        logger.info(
            f"  📄 Texte: {len(primary_text)} chars, "
            f"source={text_data['primary_source']}"
        )

        # ── ÉTAPE 2: Extraction spatiale (tableau récap) ──────
        spatial_data = self.spatial_extractor.extract_from_pages(
            text_data["pages_data"], 
            reference_hint=reference_hint
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
            self.normalizer.reset()
            rooms = self._rooms_from_table(spatial_rows, "spatial")
            logger.info(f"  ✅ {len(rooms)} pièces depuis tableau spatial")

        # Priorité 2: regex sur texte PyMuPDF (si spatial insuffisant)
        # Check if spatial extraction found enough rooms
        spatial_calc = sum(r.surface for r in rooms)
        # Trigger regex if:
        # - Less than 10 rooms from spatial, OR
        # - Surface is less than typical (e.g., < 110m² for a typical apartment)
        # This helps find missing rooms like WC, SDB, CHAMBRE 1 that don't have labels
        needs_regex = len(rooms) < 10 or spatial_calc < 110
        
        if needs_regex and text_data["text_pymupdf"]:
            self.normalizer.reset()
            rooms_regex = self._rooms_from_regex(
                text_data["text_pymupdf"], "pymupdf"
            )
            rooms = self._merge_rooms(rooms, rooms_regex)
            logger.info(f"  📝 +regex PyMuPDF → {len(rooms)} pièces")

        # Priorité 3: regex sur texte OCR
        if len(rooms) < 3 and text_data["text_ocr"]:
            self.normalizer.reset()
            rooms_ocr = self._rooms_from_regex(text_data["text_ocr"], "ocr")
            rooms = self._merge_rooms(rooms, rooms_ocr)
            logger.info(f"  🔍 +regex OCR → {len(rooms)} pièces")

        # Étape 3b: Dédoublonnage final
        rooms = self._final_dedup(rooms)

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
        # ── ÉTAPE 5b: Filtrage multi-appartement ─────────────
        if result.living_space > 0:
            result.rooms = self._filter_by_reference(
                result.rooms, result.reference, result.living_space
            )
            result.sources = {r.name_normalized: r.source for r in result.rooms}


        # ── ÉTAPE 6: Typology + property type ─────────────────
        # Prefer room-based detection over metadata hint (more reliable)
        room_typology = self._detect_typology(rooms)
        meta_typology = meta.get("typology_hint", "")
        
        # Use meta hint only if it seems reasonable (not empty, matches bedroom count)
        bedrooms = sum(1 for r in rooms if r.room_type == RoomType.BEDROOM)
        if meta_typology and meta_typology != room_typology:
            # Check if meta hint is close to what we'd expect
            expected_from_rooms = f"T{bedrooms + 1}" if bedrooms > 0 else "Studio"
            if meta_typology == expected_from_rooms:
                result.typology = meta_typology
            else:
                logger.info(f"  ℹ️ Typology: meta_hint={meta_typology}, room_calc={room_typology}, using={room_typology}")
                result.typology = room_typology
        else:
            result.typology = room_typology
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

    # def _rooms_from_regex(self, text, source):
    #     """Extrait les pièces par regex depuis le texte brut (fallback)"""
    #     rooms = []
    #     for pattern in self.SURFACE_PATTERNS:
    #         for match in re.finditer(pattern, text, re.IGNORECASE):
    #             name_raw = match.group(1).strip()
    #             surface_str = match.group(2)

    #             if len(name_raw) < 2 or len(name_raw) > 50:
    #                 continue
    #             try:
    #                 surface = float(surface_str.replace(",", "."))
    #             except ValueError:
    #                 continue
    #             if surface < 0.5 or surface > 500:
    #                 continue
    #             if any(kw in name_raw.upper() for kw in self.SKIP_KEYWORDS):
    #                 continue

    #             norm, rtype, num, ext, conf = self.normalizer.normalize(name_raw)
    #             if not rtype:
    #                 continue

    #             rooms.append(ExtractedRoom(
    #                 name_raw=name_raw,
    #                 name_normalized=norm,
    #                 surface=surface,
    #                 room_type=rtype,
    #                 is_exterior=ext,
    #                 room_number=num,
    #                 source=source,
    #                 confidence=conf * 0.85,  # Moins fiable que spatial
    #             ))
    #     return rooms

    # def _rooms_from_regex(self, text, source):
    #     rooms = []
    #     seen_surfaces = {}  # (room_type, surface) → déjà vu
        
    #     for pattern in self.SURFACE_PATTERNS:
    #         for match in re.finditer(pattern, text, re.IGNORECASE):
    #             name_raw = match.group(1).strip()
    #             surface_str = match.group(2)

    #             if len(name_raw) < 2 or len(name_raw) > 50:
    #                 continue
    #             try:
    #                 surface = float(surface_str.replace(",", "."))
    #             except ValueError:
    #                 continue
    #             if surface < 0.5 or surface > 500:
    #                 continue
    #             if any(kw in name_raw.upper() for kw in self.SKIP_KEYWORDS):
    #                 continue

    #             norm, rtype, num, ext, conf = self.normalizer.normalize(name_raw)
    #             if not rtype:
    #                 continue

    #             # ── Anti-doublon intra-source ──
    #             # Même type + même surface = même pièce vue 2 fois
    #             dedup_key = (rtype, round(surface, 2))
    #             if dedup_key in seen_surfaces:
    #                 logger.debug(
    #                     f"  Doublon intra-source ignoré: '{name_raw}' "
    #                     f"{surface}m² (déjà vu comme '{seen_surfaces[dedup_key]}')"
    #                 )
    #                 continue
    #             seen_surfaces[dedup_key] = name_raw

    #             rooms.append(ExtractedRoom(
    #                 name_raw=name_raw,
    #                 name_normalized=norm,
    #                 surface=surface,
    #                 room_type=rtype,
    #                 is_exterior=ext,
    #                 room_number=num,
    #                 source=source,
    #                 confidence=conf * 0.85,
    #             ))
    #     return rooms
    
    def _rooms_from_regex(self, text, source):
        rooms = []
        seen_surfaces = {}

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

                # ── Nettoyage du nom brut ──
                name_raw = self._clean_room_name(name_raw)
                if len(name_raw) < 2:
                    continue

                norm, rtype, num, ext, conf = self.normalizer.normalize(name_raw)
                if not rtype:
                    continue

                dedup_key = (rtype, round(surface, 2))
                if dedup_key in seen_surfaces:
                    continue
                seen_surfaces[dedup_key] = name_raw

                rooms.append(ExtractedRoom(
                    name_raw=name_raw,
                    name_normalized=norm,
                    surface=surface,
                    room_type=rtype,
                    is_exterior=ext,
                    room_number=num,
                    source=source,
                    confidence=conf * 0.85,
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
                # Prefer spatial source over regex, regardless of surface difference
                # This prevents duplicates from multi-apartment PDFs
                if existing.source == "spatial":
                    logger.debug(f"  Doublon SKIP (spatial优先): '{r.name_raw}' vs '{existing.name_raw}'")
                    continue  # Skip - keep spatial
                # If both are regex, check if surfaces are close
                if abs(r.surface - existing.surface) < 0.5:
                    logger.debug(
                        f"  Doublon détecté: '{r.name_raw}' = '{existing.name_raw}'"
                    )
                    continue  # Skip ce doublon

            merged[r.name_normalized] = r
            type_index[(r.room_type, r.room_number)] = r

        return list(merged.values())
    def _clean_room_name(self, name: str) -> str:
        """
        Nettoie le nom brut en supprimant le bruit technique des plans.
        'PP80 PP80 ENTREE' → 'ENTREE'
        'A ENTREE' → 'ENTREE'
        """
        # Supprimer les codes techniques courants
        noise_patterns = [
            r"\bPP\d+\b",          # PP80, PP90
            r"\bPF\w*\b",          # PFOB, PFC
            r"\bVR\b",             # Volet roulant
            r"\bOB\b",             # Oscillo-battant
            r"\bFAV\b",            # Fenêtre
            r"\bRGT\b",            # Rangement (contexte légende)
            r"\b\d{2,3}\s*x\s*\d{2,3}\b",  # Dimensions: 90 x 220
            r"\bfixe\b",
            r"\bOPALIN\b",
            r"\bgarde[\-\s]?corps\b",
            r"\bballon\s*thermo\b",
        ]
        
        cleaned = name
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Supprimer les lettres isolées en début (ex: "A ENTREE" → "ENTREE")
        cleaned = re.sub(r"^[A-Z]\s+", "", cleaned.strip())
        
        # Nettoyer les espaces multiples
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        return cleaned

    def _detect_typology(self, rooms):
        """
        Detect typology: T1, T2, T3, T4, T5, etc.
        Tn = n rooms (bedrooms) + living room
        """
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
        # T2 = 1 bedroom + living, T3 = 2 bedrooms + living, etc.
        return f"T{bedrooms + 1}"

    def _detect_property_type(self, rooms):
        has_garden = any(r.room_type == RoomType.GARDEN for r in rooms)
        has_cellar = any(r.room_type == RoomType.CELLAR for r in rooms)
        return "house" if has_garden and has_cellar else "appartment"

    # def _final_dedup(self, rooms):
    #     """
    #     Dédoublonnage final: supprime les pièces avec même type + même surface.
    #     Garde celle avec la meilleure confiance.
    #     """
    #     seen = {}  # (room_type, surface_arrondie) → ExtractedRoom
    #     deduped = []

    #     for r in rooms:
    #         key = (r.room_type, round(r.surface, 1))

    #         if key in seen:
    #             existing = seen[key]
    #             logger.info(
    #                 f"  🔄 Doublon final supprimé: '{r.name_raw}' ({r.surface}m²) "
    #                 f"= '{existing.name_raw}' ({existing.surface}m²)"
    #             )
    #             # Garde celui avec meilleure confiance
    #             if r.confidence > existing.confidence:
    #                 deduped.remove(existing)
    #                 seen[key] = r
    #                 deduped.append(r)
    #             continue

    #         seen[key] = r
    #         deduped.append(r)

    #     if len(deduped) < len(rooms):
    #         logger.info(
    #             f"  🧹 Dédoublonnage: {len(rooms)} → {len(deduped)} pièces"
    #         )

    #     return deduped

    def _final_dedup(self, rooms):
        """
        Dédoublonnage final: supprime les pièces avec même type + même numéro + même surface.
        Pour les chambres avec numéro différent, garde les deux.
        """
        seen = {}  # (room_type, room_number, surface_arrondie) → ExtractedRoom
        deduped = []

        for r in rooms:
            # Clé incluant le numéro de pièce pour différencier chambre_1 et chambre_2
            room_num = r.room_number if r.room_number else 0
            # Utiliser surface arrondie à 1 décimale pour comparaison
            key = (r.room_type, room_num, round(r.surface, 1))

            if key in seen:
                existing = seen[key]
                logger.info(
                    f"  🔄 Doublon final supprimé: '{r.name_raw}' ({r.surface}m²) "
                    f"= '{existing.name_raw}' ({existing.surface}m²)"
                )
                # Garde celui avec meilleure confiance
                if r.confidence > existing.confidence:
                    deduped.remove(existing)
                    seen[key] = r
                    deduped.append(r)
                continue

            seen[key] = r
            deduped.append(r)

        if len(deduped) < len(rooms):
            logger.info(
                f"  🧹 Dédoublonnage: {len(rooms)} → {len(deduped)} pièces"
            )

        return deduped
    
    def _filter_by_reference(self, rooms, reference, living_space):
        if living_space <= 0 or len(rooms) < 3:
            return rooms

        interior = [r for r in rooms if not r.is_exterior and not r.is_composite]
        exterior = [r for r in rooms if r.is_exterior]

        calc = sum(r.surface for r in interior)
        diff = abs(calc - living_space)

        if diff <= 1.0:
            return rooms

        # Also check for essential rooms that should always be kept
        essential_types = {"wc", "salle_de_bain", "salle_d_eau", "entree", "circulation", "storage"}
        essential_rooms = [r for r in interior if r.name_normalized.split("_")[0] in essential_types]
        
        # Identify rooms from spatial extraction (more reliable)
        spatial_sources = {r.source for r in rooms if r.source == "spatial"}
        spatial_rooms = {r.name_normalized for r in rooms if r.source == "spatial"}
        
        if calc > living_space * 1.10:
            logger.info(
                f"  🔍 Multi-appart détecté: calc={calc:.2f} >> "
                f"declared={living_space:.2f}. Filtrage..."
            )
            
            # First try to find subset that includes spatial rooms (they're more reliable)
            if spatial_rooms:
                # Filter interior to prioritize rooms that exist in spatial extraction
                spatial_priority = []
                other_rooms = []
                for r in interior:
                    base_name = r.name_normalized.split("_")[0]
                    # Check if this room type exists in spatial
                    if any(spatial_name.split("_")[0] == base_name for spatial_name in spatial_rooms):
                        spatial_priority.append(r)
                    else:
                        other_rooms.append(r)
                
                # Try finding best subset prioritizing spatial rooms
                best = self._find_best_subset(spatial_priority + other_rooms, living_space)
            else:
                best = self._find_best_subset(interior, living_space)
            if best:
                # Always keep essential rooms (WC, SDB, entrance, etc.)
                essential_in_best = {r.name_normalized.split("_")[0] for r in best}
                missing_essential = [r for r in essential_rooms 
                                   if r.name_normalized.split("_")[0] not in essential_in_best]
                
                if missing_essential:
                    logger.info(f"  🔧 Ajout {len(missing_essential)} pièces essentielles: "
                              f"{[r.name_normalized for r in missing_essential]}")
                    best = best + missing_essential
                
                # Keep only ONE room per type+number combination
                # This removes duplicates from multi-apartment extraction
                # Prefer: 1) spatial source, 2) larger surface
                by_type_num = {}
                for r in best:
                    key = r.name_normalized  # Use full normalized name as key
                    if key not in by_type_num:
                        by_type_num[key] = r
                    else:
                        # Keep the one from spatial source or with larger surface
                        existing = by_type_num[key]
                        if r.source == "spatial" and existing.source != "spatial":
                            by_type_num[key] = r
                        elif r.source == existing.source and r.surface > existing.surface:
                            by_type_num[key] = r
                best = list(by_type_num.values())
                
                # Also deduplicate exterior rooms
                ext_by_type = {}
                for r in exterior:
                    base = r.name_normalized.split("_")[0]
                    if base not in ext_by_type or r.surface > ext_by_type[base].surface:
                        ext_by_type[base] = r
                exterior = list(ext_by_type.values())
                
                result = best + exterior
                logger.info(
                    f"  ✅ Filtré: {len(rooms)} → {len(result)} pièces"
                )
                return result

        return rooms

    def _filter_exteriors(self, exterior_rooms):
        """Dédoublonne les extérieurs: garde 1 par type (le plus grand)"""
        by_type = {}
        for r in exterior_rooms:
            if r.room_type not in by_type or r.surface > by_type[r.room_type].surface:
                by_type[r.room_type] = r
        return list(by_type.values())

    def _find_best_subset(self, rooms, target):
        """
        Trouve le sous-ensemble cohérent dont la somme ≈ target.
        Priorise la cohérence (pas de doublons de type) avant la somme.
        
        IMPORTANT: Only keep one room per type+number combination.
        """
        from itertools import combinations

        n = len(rooms)
        best_diff = float("inf")
        best_combo = None

        min_size = max(3, n // 2)
        max_size = min(n, n - 1) if n > 3 else n

        for size in range(min_size, max_size + 1):
            # Limiter les combinaisons pour éviter explosion
            if self._comb_count(n, size) > 50000:
                continue

            for combo in combinations(rooms, size):
                total = sum(r.surface for r in combo)
                diff = abs(total - target)

                if diff >= best_diff:
                    continue

                # Vérifier la cohérence: pas de doublon de type sans numéro
                if self._has_type_conflict(combo):
                    continue

                best_diff = diff
                best_combo = list(combo)

                if diff < 0.5:
                    return best_combo

        if best_combo and best_diff < 2.0:
            return best_combo
        return None

    def _has_type_conflict(self, combo):
        """
        Vérifie qu'un sous-ensemble est cohérent:
        - Pas 2 séjour/cuisine (1 seul par appart)
        - Pas 2 entrées
        """
        unique_types = [
            RoomType.LIVING_KITCHEN,
            RoomType.LIVING_ROOM,
            RoomType.ENTRY,
            RoomType.RECEPTION,
        ]
        for rt in unique_types:
            count = sum(1 for r in combo if r.room_type == rt)
            if count > 1:
                return True  # Conflit
        return False

    def _comb_count(self, n, r):
        """Nombre de combinaisons C(n,r)"""
        from math import comb
        return comb(n, r)


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