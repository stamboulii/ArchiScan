"""
Metadata Extractor - Référence, étage, bâtiment, promoteur, adresse
"""

import re
import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class MetadataExtractor:

    REF_PATTERNS = [
        # Priorité 1: pattern explicite avec contexte
        r"Appartement\s+([A-Z]\d{2,4})",
        r"APPARTEMENT\s*[:\s]*([A-Z]\d{2,4})",
        r"LOT\s*[:\s]*([A-Z]?\d{2,4})",
        r"R[ÉE]F[ÉE]RENCE\s*[:\s]*(\w+)",
        # Priorité 2: code seul (A008, B13, C234)
        r"\b([A-Z]\d{3,4})\b",
        r"\b([A-Z]\d{2})\b",  # ← REMETTRE mais avec blacklist
    ]

    REF_BLACKLIST = {"R1", "R2", "R3", "T1", "T2", "T3", "T4", "T5", "T6",
                 "A1", "A2", "A3", "B1", "B2", "B3",  # trop courts/génériques
                 "DATE", "TYPE", "PLAN", "NOTA", "IND"}

    FLOOR_PATTERNS = [
        (r"NIVEAU\s*[:\s]*(Rez[- ]?de[- ]?chauss[éeè]e)", "RDC"),
        (r"\bRDC\b", "RDC"),
        (r"[Rr]ez[- ]?de[- ]?chauss[éeè]e", "RDC"),
        (r"NIVEAU\s*[:\s]*R\+(\d+)", lambda m: f"R+{m.group(1)}"),
        (r"\bR\+(\d+)\b", lambda m: f"R+{m.group(1)}"),
        (r"(\d+)\s*(?:er|e|[èe]me)\s*[ée]tage", lambda m: f"R+{m.group(1)}"),
    ]

    BUILDING_PATTERNS = [
        r"BATIMENT\s*[:\s]*([A-Z]\d?)",
        r"B[ÂA]T\.?\s*[:\s]*([A-Z]\d?)",
    ]

    PROMOTER_SIGNATURES = {
        r"faubourg[\s\-]?immobilier|SCCV\s*FI": "Faubourg Immobilier",
        r"nexity|NEXITY": "Nexity",
        r"bouygues|BOUYGUES\s*IMMOBILIER": "Bouygues Immobilier",
        r"vinci|VINCI\s*IMMOBILIER": "Vinci Immobilier",
        r"kaufman|KAUFMAN": "Kaufman & Broad",
        r"eiffage|EIFFAGE": "Eiffage Immobilier",
        r"cogedim|COGEDIM": "Cogedim",
        r"icade|ICADE": "Icade",
        r"altarea|ALTAREA": "Altarea",
        r"promogim|PROMOGIM": "Promogim",
        r"pitch[\s\-]?promotion": "Pitch Promotion",
    }

    LIVING_SPACE_PATTERNS = [
        r"TOTAL\s*SURFACE\s*HABITABLE\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*HABITABLE\s*[:\s]*(\d+[\.,]\d+)",
    ]

    ANNEX_SPACE_PATTERNS = [
        r"TOTAL\s*SURFACE\s*ANNEXE\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*ANNEXE\s*[:\s]*(\d+[\.,]\d+)",
    ]
 

    def extract(self, text: str, reference_hint: Optional[str] = None,
                spatial_metadata: Optional[List[str]] = None) -> Dict[str, Any]:

        full_text = text
        if spatial_metadata:
            full_text += " " + " ".join(spatial_metadata)

        return {
            "reference": self._extract_first(full_text, self.REF_PATTERNS,
                                              reference_hint or "UNKNOWN"),
            "floor": self._extract_floor(full_text),
            "building": self._extract_first(full_text, self.BUILDING_PATTERNS, ""),
            "promoter": self._detect_promoter(full_text),
            "living_space": self._extract_surface(full_text, self.LIVING_SPACE_PATTERNS),
            "annex_space": self._extract_surface(full_text, self.ANNEX_SPACE_PATTERNS),
            "address": self._extract_address(full_text),
            "typology_hint": self._extract_typology_hint(full_text),
        }

    def _extract_first(self, text, patterns, default):
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                ref = m.group(1).strip()
                if ref.upper() in self.REF_BLACKLIST:
                    continue
                # Au moins 1 lettre + 2 chiffres pour être valide
                if len(ref) >= 3 or re.match(r"^[A-Z]\d{2,}$", ref):
                    return ref
        return default

    def _extract_floor(self, text):
        for pattern, val in self.FLOOR_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return val(m) if callable(val) else val
        return ""

    def _detect_promoter(self, text):
        for pattern, name in self.PROMOTER_SIGNATURES.items():
            if re.search(pattern, text, re.IGNORECASE):
                return name
        return ""

    def _extract_surface(self, text, patterns):
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except ValueError:
                    pass
        return 0.0

    def _extract_address(self, text):
        m = re.search(
            r"(\d+[\s\-]?\w*\s+(?:rue|avenue|boulevard|quai|place|impasse)"
            r"[^,\n]{3,50})", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _extract_typology_hint(self, text):
        # Pattern "Appartement B13 -Type 2 -Niveau R+1"
        m = re.search(r"-?\s*Type\s*(\d+)", text, re.IGNORECASE)
        if m:
            return f"T{m.group(1)}"
        m = re.search(r"TYPE\s*[:\s]*(\d+)\s*pi[èe]ces?", text, re.IGNORECASE)
        if m:
            return f"T{m.group(1)}"
        m = re.search(r"(\d+)\s*pi[èe]ces?", text, re.IGNORECASE)
        if m:
            return f"T{m.group(1)}"
        return ""