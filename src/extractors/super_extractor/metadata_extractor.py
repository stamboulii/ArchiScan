"""
Metadata Extractor - Référence, étage, bâtiment, promoteur, adresse
"""

import re
import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class MetadataExtractor:

    REF_PATTERNS = [
        # Priorité 0: Logement code "A 101", "B 203"
        r"Logement\s*[:\s]*([A-Z]\s*\d{3,4})",
        r"\b([A-Z])\s(\d{3,4})\b",  # standalone "A 101"
        # Priorité 1: pattern explicite avec contexte
        r"Appartement\s+([A-Z]\d{2,4})",
        r"APPARTEMENT\s*[:\s]*([A-Z]\d{2,4})",
        r"LOT\s*[:\s]*([A-Z]?\d{2,4})",
        r"R[ÉE]F[ÉE]RENCE\s*[:\s]*(\w+)",
        # Priorité 1b: format Bâtiment-Lot "B2-402", "B1-101"
        r"NUMERO\s*LOT[^\n]{0,40}?(\b[A-Z]\d{1,2}-\d{3,4}\b)",
        r"\b([A-Z]\d{1,2}-\d{3,4})\b",  # B2-402, B1-101
        # Priorité 2: code seul (A008, B13, C234)
        r"\b([A-Z]\d{3,4})\b",
        r"\b([A-Z]\d{2})\b",  # ← REMETTRE mais avec blacklist
    ]

    REF_BLACKLIST = {"R1", "R2", "R3", "T1", "T2", "T3", "T4", "T5", "T6",
                 "A1", "A2", "A3", "B1", "B2", "B3",  # trop courts/génériques
                 "DATE", "TYPE", "PLAN", "NOTA", "IND",
                 # Articles de loi CCH (faux positifs)
                 "L261", "R261", "L111", "R111", "L123", "R123",
                 "L151", "R151", "L152", "R152", "L421", "R421",
                 # Height codes from architectural drawings (Hauteur XXX cm)
                 "H180", "H214", "H250", "H360", "H110", "H160", "H200",
                 "H220", "H240", "H270", "H300", "H320", "H350", "H400"}

    FLOOR_PATTERNS = [
        # Numeric floor codes: "Etage 001", "Etage 002" — keep as-is
        (r"\bEtage\b.{0,300}?\b(0\d{2})\b", lambda m: m.group(1)),  # "Etage ... 001"
        (r"\bEtage\s+(\d{3})\b", lambda m: m.group(1)),
        # Combinaison RDC + ETAGE (indique une maison avec plusieurs niveaux)
        (r"REZ\s*DE\s*CHAUSSEE\s*(ETAGE|\+|/)\s*ETAGE", "RDC+1"),
        (r"RDC\s*(ETAGE|\+|/)\s*ETAGE", "RDC+1"),
        (r"REZ[- ]?DE[- ]?CHAUSSEE\s+ETAGE", "RDC+1"),
        # Niveau unique RDC
        (r"NIVEAU\s*[:\s]*(Rez[- ]?de[- ]?chauss[éeè]e)", "RDC"),
        (r"\bRDC\b", "RDC"),
        (r"[Rr]ez[- ]?de[- ]?chauss[éeè]e\s+(?!ETAGE|ETG)", "RDC"),  # RDC seul, pas suivi de ETAGE
        # Patterns pour étage
        (r"NIVEAU\s*[:\s]*(1er\s*[ée]tage|Premier\s*[ée]tage|1re\s*[ée]tage)", "R+1"),
        (r"\bR\+1\b", "R+1"),
        (r"(1er\s*[ée]tage|Premier\s*[ée]tage|1re\s*[ée]tage)", "R+1"),
        (r"(\d+)\s*(?:er|e|[èe]me)\s*[ée]tage", lambda m: f"R+{m.group(1)}"),
        (r"NIVEAU\s*[:\s]*R\+(\d+)", lambda m: f"R+{m.group(1)}"),
        (r"\bR\+(\d+)\b", lambda m: f"R+{m.group(1)}"),
        # "duplex au 1er étage", "duplex au 2eme étage", "duplex au 2ème étage"
        (r"duplex\s+au\s+1er?\s*[ée]tage", "R+1"),
        (r"duplex\s+au\s+2[eè]me?\s*[ée]tage", "R+2"),
        (r"duplex\s+au\s+(\d+)[eè]me?\s*[ée]tage", lambda m: f"R+{m.group(1)}"),
        # "au 1er étage", "au 2ème étage" (standalone)
        (r"au\s+1er?\s*[ée]tage", "R+1"),
        (r"au\s+(\d+)[eè]me?\s*[ée]tage", lambda m: f"R+{m.group(1)}"),
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
        r"groupe\s*duval|GROUPE\s*DUVAL|duval": "Groupe Duval",
        r"ink\s*architectes|INK": "Ink Architectes",
        r"pitch[\s\-]?promotion": "Pitch Promotion",
    }

    LIVING_SPACE_PATTERNS = [
        r"TOTAL\s*SURFACE\s*HABITABLE\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*HABITABLE\s*[:\s]*(\d+[\.,]\d+)",
    ]

    ANNEX_SPACE_PATTERNS = [
        r"TOTAL\s*SURFACE\s*ANNEXE\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*ANNEXE\s*[:\s]*(\d+[\.,]\d+)",
        r"TOTAL\s*EXT[ÉE]RIEURS?\s*[:\s]*(\d+[\.,]\d+)",
    ]
    
    # Nouvelles patterns pour surface propriété et espaces verts
    PROPERTY_SPACE_PATTERNS = [
        # Patterns simples (sans accents pour éviter les problèmes d'encodage)
        r"TOTAL\s+PROPRIETE\s+(\d+[\.,]\d+)",
        r"TOTAL\s+PROPRIETE\s+(\d+[\.,]\d+)\s*m",
        r"TOTAL\s*PROPRI[ÉE]T[ÉÈ]\s*[:\s]*(\d+[\.,]\d+)\s*m",
        r"TOTAL\s*PROPRI[ÉE]T[ÉÈ]\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*PROPRI[ÉE]T[ÉÈ]\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*DU\s*LOT\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*TERRAIN\s*[:\s]*(\d+[\.,]\d+)",
        r"SUPERFICIE\s*[:\s]*(\d+[\.,]\d+)",
    ]
    
    # Patterns pour gérer les newlines (texte sur plusieurs lignes)
    PROPERTY_SPACE_PATTERNS_MULTILINE = [
        r"TOTAL\s+PROPRIETE\s*\n?\s*(\d+[\.,]\d+)\s*m",
        r"TOTAL\s+PROPRIETE\s*\n?\s*(\d+[\.,]\d+)",
    ]
    
    GARDEN_SPACE_PATTERNS = [
        r"SURFACE\s*ESPACES\s*VERTS\s*[:\s]*(\d+[\.,]\d+)",
        r"SURFACE\s*JARDIN\s*[:\s]*(\d+[\.,]\d+)",
        r"JARDIN\s*PRIVATIF\s*[:\s]*(\d+[\.,]\d+)",
        r"ESPACES\s*VERTS\s*[:\s]*(\d+[\.,]\d+)",
    ]
 

    def extract(self, text: str, reference_hint: Optional[str] = None,
                spatial_metadata: Optional[List[str]] = None) -> Dict[str, Any]:

        full_text = text
        if spatial_metadata:
            full_text += " " + " ".join(spatial_metadata)

        # Combiner les patterns normaux et multilignes pour surface_propriete
        property_patterns = self.PROPERTY_SPACE_PATTERNS + self.PROPERTY_SPACE_PATTERNS_MULTILINE
        
        # Extract program name
        program = self._extract_program(full_text)

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
            "program": program,
            "surface_propriete": self._extract_surface(full_text, property_patterns),
            "surface_espaces_verts": self._extract_surface(full_text, self.GARDEN_SPACE_PATTERNS),
        }

    PROGRAM_PATTERNS = [
        r"(?:Résidence|Domaine|Les?|Le|La|Villa|Programme)\s+[A-Z][A-Za-zÀ-ÿ'\s\-]{3,40}",
    ]

    def _extract_program(self, text: str) -> str:
        """Extract program/residence name from text."""
        for p in self.PROGRAM_PATTERNS:
            m = re.search(p, text)
            if m:
                name = m.group(0).strip()
                # Trim at street/address keywords
                name = re.split(
                    r'\s+(?:Rue|Avenue|Boulevard|All[ée]e|Impasse|Place|Chemin|Route)\b',
                    name, flags=re.IGNORECASE)[0].strip()
                # Filter out false positives
                if len(name) > 8 and not any(w in name.upper() for w in
                        ['SURFACE', 'PLAN', 'ETAGE', 'TOTAL', 'TYPE']):
                    return name
        return ""

    def _extract_first(self, text, patterns, default):
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                # Handle patterns with 2 groups (e.g. r"\b([A-Z])\s(\d{3,4})\b")
                if m.lastindex and m.lastindex >= 2:
                    ref = "".join(g for g in m.groups() if g).strip()
                else:
                    ref = m.group(1).strip()
                ref = re.sub(r'\s+', '', ref)  # "A 101" → "A101"
                if ref.upper() in self.REF_BLACKLIST:
                    continue
                # Rejeter si la ref est dans "L261-15" (article de loi)
                if re.search(rf"\\b{re.escape(ref)}-\\d{{1,2}}\\b", text, re.IGNORECASE):
                    continue
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