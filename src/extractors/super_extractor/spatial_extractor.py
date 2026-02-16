"""
Spatial Extractor - Extraction par position spatiale du tableau récapitulatif
Méthode la plus fiable: analyse les blocs PyMuPDF par coordonnées
"""

import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class SpatialExtractor:

    TOTAL_KEYWORDS = [
        "TOTAL SURFACE HABITABLE", "SURFACE HABITABLE", "TOTAL SH",
    ]
    ANNEX_KEYWORDS = [
        "TOTAL SURFACE ANNEXE", "SURFACE ANNEXE", "TOTAL ANNEXE",
        "TOTAL EXTERIEURS", "TOTAL EXT",  # ← AJOUTER
    ]
    SKIP_KEYWORDS = [
        "BATIMENT", "APPARTEMENT", "NIVEAU", "TYPE", "LEGENDE",
        "DATE", "IND", "PLAN", "ECHELLE", "SCCV", "VENTE", "TOTAL",
    ]

    def extract_from_pages(self, pages_data: List[Dict]) -> Dict:
        """
        Analyse les pages pour trouver le tableau récapitulatif.
        Returns dict: table_rows, living_space, annex_space, metadata_lines, source
        """
        result = {
            "table_rows": [],
            "living_space": None,
            "annex_space": None,
            "metadata_lines": [],
            "source": "spatial",
        }
        if not pages_data:
            return result

        for page_data in pages_data:
            page_result = self._analyze_page(page_data)
            if len(page_result["table_rows"]) > len(result["table_rows"]):
                result = page_result
        return result

    def _analyze_page(self, page_data: Dict) -> Dict:
        width = page_data.get("width", 1000)
        height = page_data.get("height", 1000)
        blocks = page_data.get("blocks", [])

        result = {
            "table_rows": [],
            "living_space": None,
            "annex_space": None,
            "metadata_lines": [],
            "source": "spatial",
        }

        text_lines = self._extract_text_lines(blocks)
        if not text_lines:
            return result

        # Stratégie 1: zone droite (>50% largeur)
        right_lines = [l for l in text_lines if l["x0"] > width * 0.50]
        # Stratégie 2: fallback zone basse
        if len(right_lines) < 3:
            right_lines = [l for l in text_lines if l["y0"] > height * 0.50]

        right_lines.sort(key=lambda l: l["y0"])

        for line in right_lines:
            text = line["text"].strip()
            text_upper = text.upper()

            # Détecter totaux
            for kw in self.TOTAL_KEYWORDS:
                if kw in text_upper:
                    m = re.search(r"(\d+[\.,]\d+)", text)
                    if m:
                        result["living_space"] = float(m.group(1).replace(",", "."))

            for kw in self.ANNEX_KEYWORDS:
                if kw in text_upper:
                    m = re.search(r"(\d+[\.,]\d+)", text)
                    if m:
                        result["annex_space"] = float(m.group(1).replace(",", "."))

            # Skip métadonnées
            if any(kw in text_upper for kw in self.SKIP_KEYWORDS):
                result["metadata_lines"].append(text)
                continue

            # Pattern: "Nom pièce    XX.XX m²"
            match = re.match(
                r"^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\-'/\.\d]*\S)"
                r"\s+(\d+[\.,]\d+)\s*m[²2]?\s*$",
                text
            )
            if not match:
                # Fallback: nom très court comme "WC", "SdB"
                match = re.match(
                    r"^([A-Za-z\u00C0-\u017F]{2,5})\s+(\d+[\.,]\d+)\s*m[²2]?\s*$",
                    text
                )

        # Fallback: paires alignées par position Y
        # Fallback: lignes consécutives (nom puis surface sur ligne suivante)
        if len(result["table_rows"]) < 3:
            consecutive = self._find_consecutive_pairs(right_lines)
            if len(consecutive) > len(result["table_rows"]):
                result["table_rows"] = consecutive

        return result

    def _extract_text_lines(self, blocks: List[Dict]) -> List[Dict]:
        """Extrait lignes de texte avec coordonnées depuis blocks PyMuPDF"""
        lines = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = " ".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                bbox = line.get("bbox", [0, 0, 0, 0])
                lines.append({
                    "text": text,
                    "x0": bbox[0], "y0": bbox[1],
                    "x1": bbox[2], "y1": bbox[3],
                })
        return lines

    def _find_aligned_pairs(self, lines: List[Dict], y_tol: float = 5.0) -> List[Tuple]:
        """
        Deux blocs sur la même ligne Y:
        - texte (nom pièce) à gauche
        - nombre m² à droite
        """
        pairs = []
        used = set()
        for i, line in enumerate(lines):
            if i in used:
                continue
            # Skip si c'est déjà un nombre
            if re.search(r"\d+[\.,]\d+\s*m[²2]?", line["text"]):
                continue
            for j, other in enumerate(lines):
                if j in used or i == j:
                    continue
                if abs(line["y0"] - other["y0"]) > y_tol:
                    continue
                m = re.search(r"(\d+[\.,]\d+)\s*m[²2]?", other["text"])
                if m:
                    name = line["text"].strip()
                    if len(name) >= 2 and not any(k in name.upper() for k in self.SKIP_KEYWORDS):
                        pairs.append((name, m.group(1).replace(",", ".")))
                        used.update([i, j])
                        break
        return pairs
    def _find_consecutive_pairs(self, lines: List[Dict]) -> List[Tuple]:
        """
        Détecte: ligne N = nom de pièce, ligne N+1 = surface
        Fréquent quand PyMuPDF split le tableau en blocs séparés
        """
        pairs = []
        i = 0
        while i < len(lines) - 1:
            text = lines[i]["text"].strip()
            next_text = lines[i + 1]["text"].strip()

            # Ligne actuelle = texte sans nombre
            has_number = re.search(r"\d+[\.,]\d+\s*m[²2]?", text)
            # Ligne suivante = nombre avec m²
            next_match = re.match(r"^(\d+[\.,]\d+)\s*m[²2]?\s*$", next_text)

            if not has_number and next_match and len(text) >= 2:
                if not any(k in text.upper() for k in self.SKIP_KEYWORDS):
                    pairs.append((text, next_match.group(1).replace(",", ".")))
                    i += 2
                    continue
            i += 1
        return pairs