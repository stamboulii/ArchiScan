# """
# Spatial Extractor - Extraction par position spatiale du tableau récapitulatif
# Méthode la plus fiable: analyse les blocs PyMuPDF par coordonnées
# """

# import re
# import logging
# from typing import List, Dict, Tuple

# logger = logging.getLogger(__name__)


# class SpatialExtractor:

#     TOTAL_KEYWORDS = [
#         "TOTAL SURFACE HABITABLE", "SURFACE HABITABLE", "TOTAL SH",
#     ]
#     ANNEX_KEYWORDS = [
#         "TOTAL SURFACE ANNEXE", "SURFACE ANNEXE", "TOTAL ANNEXE",
#         "TOTAL EXTERIEURS", "TOTAL EXT",
#     ]
#     SKIP_KEYWORDS = [
#         "BATIMENT", "APPARTEMENT", "NIVEAU", "TYPE", "LEGENDE",
#         "DATE", "IND", "PLAN", "ECHELLE", "SCCV", "VENTE", "TOTAL",
#     ]

#     def extract_from_pages(self, pages_data: List[Dict]) -> Dict:
#         """
#         Analyse les pages pour trouver le tableau récapitulatif.
#         Returns dict: table_rows, living_space, annex_space, metadata_lines, source
#         """
#         result = {
#             "table_rows": [],
#             "living_space": None,
#             "annex_space": None,
#             "metadata_lines": [],
#             "source": "spatial",
#         }
#         if not pages_data:
#             return result

#         for page_data in pages_data:
#             page_result = self._analyze_page(page_data)
#             if len(page_result["table_rows"]) > len(result["table_rows"]):
#                 result = page_result
#         return result

#     def _analyze_page(self, page_data: Dict) -> Dict:
#         width = page_data.get("width", 1000)
#         height = page_data.get("height", 1000)
#         blocks = page_data.get("blocks", [])

#         result = {
#             "table_rows": [],
#             "living_space": None,
#             "annex_space": None,
#             "metadata_lines": [],
#             "source": "spatial",
#         }

#         text_lines = self._extract_text_lines(blocks)
#         if not text_lines:
#             logger.info("  ⚠️ Aucune ligne de texte extraite")
#             return result

#         # DEBUG: Toutes les lignes avant filtrage (limité aux 30 premières)
#         logger.info(f"  📄 TOUTES LIGNES ({len(text_lines)} total):")
#         for l in text_lines[:30]:
#             logger.info(f"    x0={l['x0']:.0f} y0={l['y0']:.0f} | '{l['text']}'")

#         # Stratégie 1: zone droite (>50% largeur)
#         right_lines = [l for l in text_lines if l["x0"] > width * 0.50]
#         logger.info(f"  ➡️ Zone droite x>{width*0.50:.0f}: {len(right_lines)} lignes")
        
#         # Stratégie 2: fallback zone basse
#         if len(right_lines) < 3:
#             right_lines = [l for l in text_lines if l["y0"] > height * 0.50]
#             logger.info(f"  ⬇️ Fallback zone basse y>{height*0.50:.0f}: {len(right_lines)} lignes")

#         right_lines.sort(key=lambda l: l["y0"])

#         # DEBUG TEMPORAIRE
#         logger.info(f"  🔎 RIGHT LINES AVANT FUSION ({len(right_lines)} lignes):")
#         for l in right_lines:
#             logger.info(f"    x0={l['x0']:.0f} y0={l['y0']:.0f} | '{l['text']}'")

#         # NOUVEAU: Fusionner les lignes proches verticalement (même ligne logique)
#         merged_lines = self._merge_close_lines(right_lines)
#         logger.info(f"  🔗 MERGED LINES ({len(merged_lines)} lignes):")
#         for l in merged_lines:
#             logger.info(f"    '{l['text']}'")

#         for line in merged_lines:
#             text = line["text"].strip()
#             text_upper = text.upper()

#             # Détecter totaux
#             for kw in self.TOTAL_KEYWORDS:
#                 if kw in text_upper:
#                     m = re.search(r"(\d+[\.,]\d+)", text)
#                     if m:
#                         result["living_space"] = float(m.group(1).replace(",", "."))
#                         logger.info(f"    🏠 TOTAL SH trouvé: {result['living_space']}")

#             for kw in self.ANNEX_KEYWORDS:
#                 if kw in text_upper:
#                     m = re.search(r"(\d+[\.,]\d+)", text)
#                     if m:
#                         result["annex_space"] = float(m.group(1).replace(",", "."))
#                         logger.info(f"    📦 TOTAL ANNEXE trouvé: {result['annex_space']}")

#             # Skip métadonnées
#             if any(kw in text_upper for kw in self.SKIP_KEYWORDS):
#                 result["metadata_lines"].append(text)
#                 logger.info(f"    ⏭️ SKIP (métadonnée): '{text}'")
#                 continue

#             # Pattern 1: Format standard "Nom pièce    XX.XX m²" 
#             # Gère: "CHAMBRE 2 12.74 m ²" (espace avant ²)
#             match = re.match(
#                 r"^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\-'/\.\d]*\S)"
#                 r"\s+(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
#                 text
#             )
            
#             # Pattern 2: Format collé "ENTREE/DGT 9,85m²" 
#             if not match:
#                 match = re.match(
#                     r"^([A-Za-z\u00C0-\u017F/][A-Za-z\u00C0-\u017F\s\-'/\d]*?)"
#                     r"\s*(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
#                     text
#                 )
            
#             # Pattern 3: Format ultra-collé sans espace "CELLIER1,78m²"
#             if not match:
#                 match = re.match(
#                     r"^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\-'/\d]*?)"
#                     r"(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
#                     text
#                 )
                
#             if match:
#                 name = match.group(1).strip()
#                 surface_str = match.group(2).replace(",", ".")
#                 # Filtrer noms numériques
#                 if not re.match(r"^\d+$", name):
#                     result["table_rows"].append((name, surface_str))
#                     logger.info(f"    ✅ MATCH: '{name}' = {surface_str}m²")
#                 else:
#                     logger.info(f"    ❌ Rejeté (nom numérique): '{name}'")
#                 continue
            
#             # Log si aucun pattern ne matche mais contient un nombre
#             if re.search(r"\d+[\.,]\d+", text):
#                 logger.info(f"    ❌ NON MATCH (a nombre): '{text}'")

#         logger.info(f"  📊 RESULT FINAL: {len(result['table_rows'])} lignes, SH={result['living_space']}, Annex={result['annex_space']}")
#         for name, surf in result["table_rows"]:
#             logger.info(f"      - {name}: {surf}m²")
            
#         return result

#     def _merge_close_lines(self, lines: List[Dict], y_tol: float = 8.0, x_tol: float = 150.0) -> List[Dict]:
#         """
#         Fusionne les lignes qui sont proches verticalement (même ligne logique dans le PDF)
#         Ex: 'CHAMBRE 2' (y=460) et '12.74 m ²' (y=462) -> 'CHAMBRE 2 12.74 m ²'
#         """
#         if not lines:
#             return []
        
#         merged = []
#         current_group = [lines[0]]
        
#         for i in range(1, len(lines)):
#             prev = current_group[-1]
#             curr = lines[i]
            
#             # Si proche en Y et pas trop éloigné en X
#             y_diff = abs(curr["y0"] - prev["y0"])
#             x_diff = abs(curr["x0"] - prev["x0"])
            
#             if y_diff <= y_tol and x_diff <= x_tol:
#                 current_group.append(curr)
#             else:
#                 # Fusionner le groupe courant
#                 merged.append(self._combine_line_group(current_group))
#                 current_group = [curr]
        
#         # Ne pas oublier le dernier groupe
#         if current_group:
#             merged.append(self._combine_line_group(current_group))
        
#         return merged

#     def _combine_line_group(self, group: List[Dict]) -> Dict:
#         """Combine un groupe de lignes en une seule ligne"""
#         if len(group) == 1:
#             return group[0]
        
#         # Trier par X pour avoir l'ordre gauche-droite
#         group.sort(key=lambda l: l["x0"])
        
#         # Combiner les textes avec espace
#         combined_text = " ".join(l["text"] for l in group)
        
#         # Bounding box englobante
#         min_x0 = min(l["x0"] for l in group)
#         min_y0 = min(l["y0"] for l in group)
#         max_x1 = max(l["x1"] for l in group)
#         max_y1 = max(l["y1"] for l in group)
        
#         return {
#             "text": combined_text,
#             "x0": min_x0, "y0": min_y0,
#             "x1": max_x1, "y1": max_y1,
#         }

#     def _extract_text_lines(self, blocks: List[Dict]) -> List[Dict]:
#         """Extrait lignes de texte avec coordonnées depuis blocks PyMuPDF"""
#         lines = []
#         for block in blocks:
#             if block.get("type") != 0:  # Type 0 = texte
#                 continue
#             for line in block.get("lines", []):
#                 spans = line.get("spans", [])
#                 if not spans:
#                     continue
#                 text = " ".join(s.get("text", "") for s in spans).strip()
#                 if not text:
#                     continue
#                 bbox = line.get("bbox", [0, 0, 0, 0])
#                 lines.append({
#                     "text": text,
#                     "x0": bbox[0], "y0": bbox[1],
#                     "x1": bbox[2], "y1": bbox[3],
#                 })
#         return lines

#     def _find_aligned_pairs(self, lines: List[Dict], y_tol: float = 8.0) -> List[Tuple]:
#         """Fallback conservé pour compatibilité"""
#         pairs = []
#         used = set()
#         for i, line in enumerate(lines):
#             if i in used:
#                 continue
#             if re.search(r"\d+[\.,]\d+\s*m\s*[²2]?", line["text"]):
#                 continue
#             for j, other in enumerate(lines):
#                 if j in used or i == j:
#                     continue
#                 if abs(line["y0"] - other["y0"]) > y_tol:
#                     continue
#                 m = re.search(r"(\d+[\.,]\d+)\s*m\s*[²2]?", other["text"])
#                 if m:
#                     name = line["text"].strip()
#                     if len(name) >= 2 and not any(k in name.upper() for k in self.SKIP_KEYWORDS):
#                         pairs.append((name, m.group(1).replace(",", ".")))
#                         used.update([i, j])
#                         break
#         return pairs

#     def _find_consecutive_pairs(self, lines: List[Dict]) -> List[Tuple]:
#         """Fallback conservé pour compatibilité"""
#         pairs = []
#         i = 0
#         while i < len(lines) - 1:
#             text = lines[i]["text"].strip()
#             next_text = lines[i + 1]["text"].strip()

#             has_number = re.search(r"\d+[\.,]\d+\s*m\s*[²2]?", text)
#             next_match = re.match(r"^(\d+[\.,]\d+)\s*m\s*[²2]?\s*$", next_text)

#             if not has_number and next_match and len(text) >= 2:
#                 if not any(k in text.upper() for k in self.SKIP_KEYWORDS):
#                     pairs.append((text, next_match.group(1).replace(",", ".")))
#                     i += 2
#                     continue
#             i += 1
#         return pairs



"""
Spatial Extractor - Extraction par position spatiale du tableau récapitulatif
Méthode la plus fiable: analyse les blocs PyMuPDF par coordonnées
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class SpatialExtractor:

    TOTAL_KEYWORDS = [
        "TOTAL SURFACE HABITABLE", "SURFACE HABITABLE", "TOTAL SH",
    ]
    ANNEX_KEYWORDS = [
        "TOTAL SURFACE ANNEXE", "SURFACE ANNEXE", "TOTAL ANNEXE",
        "TOTAL EXTERIEURS", "TOTAL EXT",
    ]
    SKIP_KEYWORDS = [
        "BATIMENT", "APPARTEMENT", "NIVEAU", "TYPE", "LEGENDE",
        "DATE", "IND", "PLAN", "ECHELLE", "SCCV", "VENTE", "TOTAL",
    ]

    def extract_from_pages(self, pages_data: List[Dict], reference_hint: Optional[str] = None) -> Dict:
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
            page_result = self._analyze_page(page_data, reference_hint)
            if len(page_result["table_rows"]) > len(result["table_rows"]):
                result = page_result
        return result

    def _analyze_page(self, page_data: Dict, reference_hint: Optional[str] = None) -> Dict:
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
            logger.info("  ⚠️ Aucune ligne de texte extraite")
            return result

        # DEBUG: Toutes les lignes avant filtrage (limité aux 30 premières)
        logger.info(f"  📄 TOUTES LIGNES ({len(text_lines)} total):")
        for l in text_lines[:30]:
            logger.info(f"    x0={l['x0']:.0f} y0={l['y0']:.0f} | '{l['text']}'")

        # NOUVEAU: Stratégie de filtrage par référence si fournie
        target_lines = text_lines
        ref_y = None
        
        if reference_hint:
            ref_y = self._find_reference_position(text_lines, reference_hint)
            if ref_y:
                logger.info(f"  📍 Référence '{reference_hint}' trouvée à y={ref_y:.0f}")
                # Prendre les lignes au-dessus de la référence (même tableau)
                # et ignorer ce qui est trop en bas (autres appartements)
                target_lines = [l for l in text_lines if l["y0"] < ref_y + 100]
                logger.info(f"  🎯 Lignes au-dessus de référence: {len(target_lines)}")
        
        # Si pas de référence ou non trouvée, utiliser la zone haute (pas droite)
        if not ref_y:
            # Stratégie: moitié supérieure de la page (évite les autres appartements en bas)
            target_lines = [l for l in text_lines if l["y0"] < height * 0.65]
            logger.info(f"  ⬆️ Zone haute y<{height*0.65:.0f}: {len(target_lines)} lignes")

        # Filtrer les lignes avec des surfaces (contiennent "m²" ou "m ²" ou un nombre + m)
        surface_lines = []
        for line in target_lines:
            text = line["text"]
            # Détecter si c'est une ligne de surface (contient nombre + m)
            if re.search(r"\d+[\.,]\d+\s*m", text, re.IGNORECASE):
                surface_lines.append(line)
            # Ou si c'est un nom de pièce potentiel
            elif any(kw in text.upper() for kw in ["CHAMBRE", "SEJOUR", "CUISINE", "SDB", "SDE", "WC", "ENTREE", "BALCON"]):
                surface_lines.append(line)

        surface_lines.sort(key=lambda l: l["y0"])

        # DEBUG
        logger.info(f"  🔎 LIGNES AVEC SURFACES ({len(surface_lines)} lignes):")
        for l in surface_lines:
            logger.info(f"    x0={l['x0']:.0f} y0={l['y0']:.0f} | '{l['text']}'")

        # Fusionner les lignes proches verticalement
        merged_lines = self._merge_close_lines(surface_lines)
        logger.info(f"  🔗 MERGED LINES ({len(merged_lines)} lignes):")
        for l in merged_lines:
            logger.info(f"    '{l['text']}'")

        for line in merged_lines:
            text = line["text"].strip()
            text_upper = text.upper()

            # Détecter totaux
            for kw in self.TOTAL_KEYWORDS:
                if kw in text_upper:
                    m = re.search(r"(\d+[\.,]\d+)", text)
                    if m:
                        result["living_space"] = float(m.group(1).replace(",", "."))
                        logger.info(f"    🏠 TOTAL SH trouvé: {result['living_space']}")

            for kw in self.ANNEX_KEYWORDS:
                if kw in text_upper:
                    m = re.search(r"(\d+[\.,]\d+)", text)
                    if m:
                        result["annex_space"] = float(m.group(1).replace(",", "."))
                        logger.info(f"    📦 TOTAL ANNEXE trouvé: {result['annex_space']}")

            # Skip métadonnées
            if any(kw in text_upper for kw in self.SKIP_KEYWORDS):
                result["metadata_lines"].append(text)
                logger.info(f"    ⏭️ SKIP (métadonnée): '{text}'")
                continue

            # Pattern 1: Format standard "Nom pièce    XX.XX m²" 
            match = re.match(
                r"^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\-'/\.\d]*\S)"
                r"\s+(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
                text
            )
            
            # Pattern 2: Format collé "ENTREE/DGT 9,85m²" 
            if not match:
                match = re.match(
                    r"^([A-Za-z\u00C0-\u017F/][A-Za-z\u00C0-\u017F\s\-'/\d]*?)"
                    r"\s*(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
                    text
                )
            
            # Pattern 3: Format ultra-collé sans espace "CELLIER1,78m²"
            if not match:
                match = re.match(
                    r"^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\-'/\d]*?)"
                    r"(\d+[\.,]\d+)\s*m\s*[²2]?\s*$",
                    text
                )
                
            if match:
                name = match.group(1).strip()
                surface_str = match.group(2).replace(",", ".")
                # Filtrer noms numériques
                if not re.match(r"^\d+$", name):
                    result["table_rows"].append((name, surface_str))
                    logger.info(f"    ✅ MATCH: '{name}' = {surface_str}m²")
                else:
                    logger.info(f"    ❌ Rejeté (nom numérique): '{name}'")
                continue
            
            # Log si aucun pattern ne matche mais contient un nombre
            if re.search(r"\d+[\.,]\d+", text):
                logger.info(f"    ❌ NON MATCH (a nombre): '{text}'")

        logger.info(f"  📊 RESULT FINAL: {len(result['table_rows'])} lignes, SH={result['living_space']}, Annex={result['annex_space']}")
        for name, surf in result["table_rows"]:
            logger.info(f"      - {name}: {surf}m²")
            
        return result

    def _find_reference_position(self, lines: List[Dict], reference: str) -> Optional[float]:
        """Trouve la position Y de la référence dans le texte"""
        ref_upper = reference.upper()
        for line in lines:
            if ref_upper in line["text"].upper():
                return line["y0"]
        return None

    def _merge_close_lines(self, lines: List[Dict], y_tol: float = 8.0, x_tol: float = 150.0) -> List[Dict]:
        """
        Fusionne les lignes qui sont proches verticalement (même ligne logique dans le PDF)
        Ex: 'CHAMBRE 2' (y=460) et '12.74 m ²' (y=462) -> 'CHAMBRE 2 12.74 m ²'
        """
        if not lines:
            return []
        
        merged = []
        current_group = [lines[0]]
        
        for i in range(1, len(lines)):
            prev = current_group[-1]
            curr = lines[i]
            
            # Si proche en Y et pas trop éloigné en X
            y_diff = abs(curr["y0"] - prev["y0"])
            x_diff = abs(curr["x0"] - prev["x0"])
            
            if y_diff <= y_tol and x_diff <= x_tol:
                current_group.append(curr)
            else:
                # Fusionner le groupe courant
                merged.append(self._combine_line_group(current_group))
                current_group = [curr]
        
        # Ne pas oublier le dernier groupe
        if current_group:
            merged.append(self._combine_line_group(current_group))
        
        return merged

    def _combine_line_group(self, group: List[Dict]) -> Dict:
        """Combine un groupe de lignes en une seule ligne"""
        if len(group) == 1:
            return group[0]
        
        # Trier par X pour avoir l'ordre gauche-droite
        group.sort(key=lambda l: l["x0"])
        
        # Combiner les textes avec espace
        combined_text = " ".join(l["text"] for l in group)
        
        # Bounding box englobante
        min_x0 = min(l["x0"] for l in group)
        min_y0 = min(l["y0"] for l in group)
        max_x1 = max(l["x1"] for l in group)
        max_y1 = max(l["y1"] for l in group)
        
        return {
            "text": combined_text,
            "x0": min_x0, "y0": min_y0,
            "x1": max_x1, "y1": max_y1,
        }

    def _extract_text_lines(self, blocks: List[Dict]) -> List[Dict]:
        """Extrait lignes de texte avec coordonnées depuis blocks PyMuPDF"""
        lines = []
        for block in blocks:
            if block.get("type") != 0:  # Type 0 = texte
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