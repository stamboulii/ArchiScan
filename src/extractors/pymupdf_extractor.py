"""
PyMuPDF Extractor V5.3 - PRODUCTION READY
Critical fix: Filter out category totals that are sums of other rooms

Issue example from A105:
- Réception: 41.97 m² (category total: Séjour 34.65 + Cuisine 7.32)
- Réception: 15.05 m² (actual room)

The extractor was creating both "reception: 41.97" and "reception_1: 15.05"
Now it validates values and skips category totals.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import fitz

from ..core.parcel import ParcelData, DEFAULT_OPTIONS

logger = logging.getLogger(__name__)


@dataclass
class PyMuPDFExtractionResult:
    success: bool
    text: str = ""
    cleaned_text: str = ""
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    raw_blocks: List = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    confidence: float = 0.0
    error: Optional[str] = None


class PyMuPDFExtractor:

    PATTERNS = {
        "parcelLabel": [r"\b([A-Z]\d{2,4})\b"],
        "typology": [r"\bT([1-9])\b", r"\b(\d)\s*pi[èe]ces?\b"],
        "floor": [
            r"\b(RDC|R\+\d+)\b",
            r"\b(\d+)(?:er|ème|e)\s+étage\b",
            r"\bétage\s+(\d+)\b",
        ],
        "living_space": [
            r"(?:TOTAL\s+)?SURFACE\s+HABITABLE[:\s]*(\d+[.,]\d+)",
            r"TOTAL\s+SURFACE\s+HABITABLE.*?(\d+[.,]\d+)",
        ],
    }

    OPTION_KEYWORDS = {
        "terrace": ["terrasse"],
        "balcony": ["balcon"],
        "garden": ["jardin"],
    }

    # Room patterns - order matters!
    ROOM_PATTERNS = [
        (r"CHAMBRE\s*\d*", "chambre", True),
        (r"Chambre\s*\d*", "chambre", True),
        (r"SEJOUR[/ ]*CUISINE", "sejour", True),
        (r"SÉJOUR[/ ]*CUISINE", "sejour", True),
        (r"SEJUR[ /CUI]*", "sejour", True),
        (r"SEJOUR", "sejour", True),
        (r"SÉJOUR", "sejour", True),
        (r"CUISINE", "cuisine", True),
        (r"RÉCEPTION", "reception", True),
        (r"RECEPTION", "reception", True),
        (r"ENTREE", "entree", True),
        (r"ENTRÉE", "entree", True),
        (r"\bDGT\b", "dgt", True),
        (r"DÉGAGEMENT", "dgt", True),
        (r"DEGAGEMENT", "dgt", True),
        (r"S\.?D\.?B\.?", "salle_de_bain", True),
        (r"SDB", "salle_de_bain", True),
        (r"SALLE\s+DE\s+BAINS?", "salle_de_bain", True),
        (r"SALLE\s+D['']EAU", "salle_d_eau", True),
        (r"S\.?d\.?E\.?", "salle_d_eau", True),
        (r"SDE\b", "salle_d_eau", True),
        (r"\bWC\b", "wc", True),
        (r"BALCON\s*\d*:?", "balcon", True),
        (r"TERRASSE\s*\d*:?", "terrasse", True),
        (r"JARDIN\s*\d*:?", "jardin", True),
        (r"LOGGIA\s*\d*:?", "loggia", True),
        (r"DRESSING", "dressing", True),
        (r"PLACARD", "placard", True),
        (r"CELLIER", "cellier", True),
    ]

    def __init__(self):
        self.patterns = self.PATTERNS
        self.option_keywords = self.OPTION_KEYWORDS
        self.room_patterns = self.ROOM_PATTERNS

    def is_available(self) -> bool:
        try:
            import fitz
            return True
        except ImportError:
            return False

    def extract(self, pdf_path: str, force: bool = False) -> PyMuPDFExtractionResult:
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            doc = fitz.open(pdf_path)
            metadata = doc.metadata or {}

            full_text = ""
            raw_blocks = []

            for page in doc:
                full_text += page.get_text()
                raw_blocks.extend(page.get_text("blocks"))

            doc.close()

            if not full_text.strip():
                return PyMuPDFExtractionResult(
                    success=False,
                    error="No extractable text (scanned PDF?)"
                )

            cleaned = self._clean_text(full_text)
            parsed = self._parse_parcel_data(cleaned)
            confidence = self._calculate_confidence(parsed)

            return PyMuPDFExtractionResult(
                success=True,
                text=full_text,
                cleaned_text=cleaned,
                parsed_data=parsed,
                raw_blocks=raw_blocks,
                metadata=metadata,
                confidence=confidence,
            )

        except Exception as e:
            logger.exception("Extraction failed")
            return PyMuPDFExtractionResult(success=False, error=str(e))

    def _clean_text(self, text: str) -> str:
        text = text.replace("\xa0", " ").replace("\r", "")
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def _extract_cartouche_block(self, text: str) -> Dict[str, str]:
        result = {}
        lines = text.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            m = re.match(r'^([A-Z]\d{1,3})$', line)
            if m and len(line) >= 2:
                excluded = ['RGT', 'DGT', 'WC', 'SDB', 'EP', 'VR', 'PF', 'SDE', 'BSO', 'FF', 'SO', 'GC']
                if line.upper() not in excluded:
                    result["parcelLabel"] = line
                    result["appartement"] = line
                    break

        for i, line in enumerate(lines):
            line = line.strip()

            if re.match(r"^APPARTEMENT$", line, re.IGNORECASE):
                for j in range(i + 1, min(i + 8, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if re.match(r'^(BATIMENT|NIVEAU|TYPE|PLOT)$', next_line, re.IGNORECASE):
                        continue
                    m = re.match(r'^-?([A-Z]\d{1,3})$', next_line)
                    if m:
                        result["parcelLabel"] = m.group(1)
                        result["appartement"] = m.group(1)
                        break

            elif re.match(r"^(BATIMENT|PLOT)$", line, re.IGNORECASE):
                if i + 1 < len(lines):
                    val = lines[i + 1].strip()
                    if val and len(val) <= 3 and not re.match(r'^(NB|Le|La|Les|Il|Pour|Dans)', val, re.IGNORECASE):
                        result["batiment"] = val

            elif re.match(r"^NIVEAU$", line, re.IGNORECASE) or re.match(r"^TYPE$", line, re.IGNORECASE):
                for j in range(i + 1, min(i + 5, len(lines))):
                    val = lines[j].strip()
                    if not val:
                        continue
                    
                    val = re.sub(r'^-?\s*', '', val)
                    
                    floor_match = re.match(r'^(\d+)(?:er|ème|e)?\s*étage$', val, re.IGNORECASE)
                    if floor_match:
                        result["niveau"] = val
                        floor_num = floor_match.group(1)
                        if floor_num == "0":
                            result["floor"] = "RDC"
                        else:
                            result["floor"] = f"R+{floor_num}"
                        break
                    
                    elif re.match(r'^R\+\d+$', val, re.IGNORECASE):
                        result["niveau"] = val.upper()
                        result["floor"] = val.upper()
                        break
                    
                    elif re.match(r'^RDC$', val, re.IGNORECASE):
                        result["niveau"] = "RDC"
                        result["floor"] = "RDC"
                        break
                    
                    elif re.match(r'^\d+$', val):
                        result["niveau"] = val
                        if val == "0":
                            result["floor"] = "RDC"
                        else:
                            result["floor"] = f"R+{val}"
                        break

            elif re.match(r"^\d+\s*pi[èe]ces?$", line, re.IGNORECASE):
                m = re.match(r"^(\d+)", line)
                if m:
                    result["typology"] = f"T{m.group(1)}"

            if "SCCV" in line or "SCI" in line:
                result["promoteur"] = line.strip()

        return result

    def _is_category_total(self, surface_detail: Dict[str, float], candidate_value: float, 
                          room_key: str, tolerance: float = 0.5) -> bool:
        """
        Check if a value is likely a category total (sum of other rooms).
        
        Example: Réception 41.97 = Séjour 34.65 + Cuisine 7.32
        """
        # Don't check for very small values or specific room types
        if candidate_value < 10:
            return False
        
        # These room types are commonly used as category labels
        category_rooms = ["reception", "sejour"]
        if room_key not in category_rooms:
            return False
        
        # Check if candidate value equals sum of any 2+ existing rooms
        values = list(surface_detail.values())
        
        # Try pairs
        for i, val1 in enumerate(values):
            for val2 in values[i+1:]:
                total = val1 + val2
                if abs(total - candidate_value) < tolerance:
                    logger.info(f"Detected category total: {room_key} {candidate_value} ≈ {val1} + {val2}")
                    return True
        
        # Try triples
        for i, val1 in enumerate(values):
            for j, val2 in enumerate(values[i+1:], i+1):
                for val3 in values[j+1:]:
                    total = val1 + val2 + val3
                    if abs(total - candidate_value) < tolerance:
                        logger.info(f"Detected category total: {room_key} {candidate_value} ≈ {val1} + {val2} + {val3}")
                        return True
        
        return False

    def _parse_parcel_data(self, text: str) -> Dict[str, Any]:
        result = {}

        # Generic patterns
        for field_name, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1) if match.groups() else match.group(0)
                    result[field_name] = self._normalize_value(field_name, value)
                    break

        # Cartouche
        cartouche = self._extract_cartouche_block(text)
        result.update(cartouche)

        # Room surfaces
        surface_detail = {}
        lines = text.split("\n")
        
        # Find stopping point
        stop_index = len(lines)
        for i, line in enumerate(lines):
            if re.search(r"(?:TOTAL\s+)?SURFACE\s+HABITABLE", line, re.IGNORECASE):
                stop_index = min(i + 15, len(lines))
                break

        for i, line in enumerate(lines):
            if i >= stop_index:
                break
                
            line_clean = line.strip()

            for pattern, key, has_surface in self.room_patterns:
                if re.search(pattern, line_clean, re.IGNORECASE):
                    if has_surface and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        m = re.search(r'(\d+[.,]\d+)', next_line)
                        if m:
                            val = self._safe_float(m.group(1))
                            if val:
                                # Check if this is a category total
                                if self._is_category_total(surface_detail, val, key):
                                    logger.info(f"Skipping category total: {key} = {val}")
                                    break
                                
                                # Always index bedrooms
                                if key == "chambre":
                                    count = 1
                                    while f"{key}_{count}" in surface_detail:
                                        count += 1
                                    surface_detail[f"{key}_{count}"] = val
                                # Handle duplicates
                                elif key in surface_detail:
                                    count = 1
                                    while f"{key}_{count}" in surface_detail:
                                        count += 1
                                    surface_detail[f"{key}_{count}"] = val
                                else:
                                    surface_detail[key] = val
                    break

        if surface_detail:
            result["surfaceDetail"] = surface_detail
            
            # Calculate totals
            if "living_space" in result:
                try:
                    total_hab = float(result["living_space"].replace(",", "."))
                    surface_detail["total_habitable"] = total_hab
                except:
                    pass
            
            # Calculate total_annexe (outdoor spaces only)
            total_annexe = 0.0
            for k, v in surface_detail.items():
                if any(k.startswith(outdoor) for outdoor in ["balcon", "terrasse", "jardin", "loggia"]):
                    total_annexe += v
            if total_annexe > 0:
                surface_detail["total_annexe"] = round(total_annexe, 2)

        # Calculate typology from bedroom count if not found
        if "typology" not in result and surface_detail:
            bedroom_count = sum(1 for k in surface_detail.keys() if k.startswith("chambre"))
            if bedroom_count > 0:
                result["typology"] = f"T{bedroom_count + 1}"
                logger.info(f"Calculated typology from {bedroom_count} bedrooms: {result['typology']}")

        # Options
        text_lower = text.lower()
        options = []
        for opt, keywords in self.OPTION_KEYWORDS.items():
            for keyword in keywords:
                pattern = rf"\b{keyword}\b.{{0,50}}?(\d+[.,]\d+)"
                match = re.search(pattern, text_lower, re.IGNORECASE)
                
                in_surface_detail = any(
                    keyword in k.lower() for k in surface_detail.keys()
                ) if surface_detail else False
                
                if match or in_surface_detail:
                    options.append(opt)
                    break
        
        if options:
            result["options"] = options

        return result

    def _normalize_value(self, field: str, value: str) -> str:
        value = value.strip()
        
        if field == "living_space":
            return value.replace(",", ".")
        
        if field == "floor":
            if re.match(r'^\d+(?:er|ème|e)?\s*étage$', value, re.IGNORECASE):
                floor_num = re.match(r'^(\d+)', value).group(1)
                if floor_num == "0":
                    return "RDC"
                return f"R+{floor_num}"
            return value.upper()
        
        if field == "typology":
            if value.isdigit():
                return f"T{value}"
            return value.upper()
        
        return value.upper()

    def _safe_float(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "."))
        except Exception:
            return None

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        if not data:
            return 0.0
        score = 0
        
        critical_fields = ["parcelLabel", "living_space", "typology", "floor"]
        score += sum(1 for f in critical_fields if f in data) * 0.2
        
        if "surfaceDetail" in data:
            room_count = len(data["surfaceDetail"])
            if room_count >= 5:
                score += 0.15
            elif room_count >= 3:
                score += 0.10
            else:
                score += 0.05
        
        if "options" in data:
            score += 0.05
        
        return min(score, 1.0)

    def to_parcel_data(self, extraction_result: PyMuPDFExtractionResult) -> ParcelData:
        raw_data = extraction_result.parsed_data or {}

        option_dict = DEFAULT_OPTIONS.copy()
        for opt in raw_data.get("options", []):
            if opt in option_dict:
                option_dict[opt] = True

        custom = {}
        for k in ["promoteur", "batiment", "niveau", "appartement"]:
            if raw_data.get(k):
                custom[k] = raw_data[k]

        surface_detail = {}
        for k, v in raw_data.get("surfaceDetail", {}).items():
            if isinstance(v, (int, float)):
                surface_detail[k] = float(v)
            elif isinstance(v, str):
                try:
                    surface_detail[k] = float(v.replace(",", "."))
                except:
                    pass

        return ParcelData(
            parcelLabel=raw_data.get("parcelLabel", ""),
            typology=raw_data.get("typology", ""),
            floor=raw_data.get("floor", ""),
            living_space=raw_data.get("living_space", ""),
            surfaceDetail=surface_detail,
            option=option_dict,
            customData=custom if custom else None,
        )