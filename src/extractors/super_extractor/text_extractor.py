"""
Text Extractor - Extraction texte brut (PyMuPDF + OCR fallback)
"""

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TextExtractor:

    def __init__(self, use_ocr: bool = True, tesseract_path: Optional[str] = None):
        self.use_ocr = use_ocr
        self.tesseract_path = tesseract_path

    def extract(self, pdf_path: str) -> dict:
        """
        Returns dict:
            text_pymupdf, text_ocr, primary_source, pages_data
        """
        path = Path(pdf_path)
        result = {
            "text_pymupdf": "",
            "text_ocr": "",
            "primary_source": "pymupdf",
            "pages_data": [],
        }

        if not path.exists():
            logger.error(f"Fichier non trouvé: {pdf_path}")
            return result

        # Étape 1: PyMuPDF
        text_pymupdf, pages_data = self._extract_pymupdf(path)
        result["text_pymupdf"] = text_pymupdf
        result["pages_data"] = pages_data

        # Étape 2: OCR si peu de texte
        has_enough = len(text_pymupdf.strip()) > 50
        surface_count = len(re.findall(r"\d+[\.,]\d+\s*m[²2]", text_pymupdf))

        if self.use_ocr and (not has_enough or surface_count < 3):
            logger.info("OCR activé (texte PyMuPDF insuffisant)")
            text_ocr = self._extract_ocr(path)
            result["text_ocr"] = text_ocr
            ocr_surfaces = len(re.findall(r"\d+[\.,]\d+\s*m[²2]", text_ocr))
            if ocr_surfaces > surface_count:
                result["primary_source"] = "ocr"

        return result

    def _extract_pymupdf(self, path: Path) -> tuple:
        """Texte + données structurelles pour spatial_extractor"""
        try:
            import fitz
            doc = fitz.open(path)
            full_text = ""
            pages_data = []

            for page_num, page in enumerate(doc):
                full_text += page.get_text() + "\n"
                text_dict = page.get_text("dict")
                pages_data.append({
                    "page_num": page_num,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "blocks": text_dict.get("blocks", []),
                })

            doc.close()
            return self._clean_text(full_text), pages_data
        except ImportError:
            logger.error("PyMuPDF non installé: pip install pymupdf")
            return "", []
        except Exception as e:
            logger.warning(f"PyMuPDF error: {e}")
            return "", []

    def _extract_ocr(self, path: Path) -> str:
        """OCR avec Tesseract"""
        try:
            import fitz
            from PIL import Image
            import pytesseract

            if self.tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

            doc = fitz.open(path)
            text = ""
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text += pytesseract.image_to_string(
                    img, lang="fra+eng", config="--oem 3 --psm 6"
                ) + "\n"
            doc.close()
            return self._clean_text(text)
        except ImportError as e:
            logger.error(f"OCR dépendances manquantes: {e}")
            return ""
        except Exception as e:
            logger.warning(f"OCR error: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        # Convertir virgules françaises → points (avec ET sans espace avant m)
        text = re.sub(r"(\d),(\d{2})\s*m", r"\1.\2 m", text)
        text = re.sub(r"(\d),(\d{2})m", r"\1.\2 m", text)
        return text.strip()