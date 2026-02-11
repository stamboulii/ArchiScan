"""
PDF Utilities - Support multi-pages et conversion
==============================================

Fonctions pour:
- Conversion PDF -> Images
- Extraction multi-pages
- Detection de format
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """Representation d'une page PDF."""
    page_num: int
    image_path: str
    width: int
    height: int


class PDFProcessor:
    """
    Processeur PDF pour la conversion en images.
    Supporte les PDFs multi-pages.
    """
    
    SUPPORTED_FORMATS = {'.pdf'}
    
    def __init__(self, dpi: int = 200):
        """
        Args:
            dpi: Resolution de rendu (defaut: 200)
        """
        self.dpi = dpi
    
    def is_pdf(self, file_path: str) -> bool:
        """Verifie si le fichier est un PDF."""
        path = Path(file_path)
        return path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def convert_pdf_to_images(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        dpi: Optional[int] = None,
    ) -> List[PDFPage]:
        """
        Convertit un PDF en images (une par page).
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            output_dir: Repertoire de sortie (defaut: temporaire)
            dpi: Resolution de rendu (defaut: celle de l'instance)
            
        Returns:
            Liste des pages avec chemins des images
        """
        from ..core.config import TEMP_DIR, ensure_directories
        
        if dpi is None:
            dpi = self.dpi
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF introuvable: {pdf_path}")
        
        if output_dir is None:
            output_dir = TEMP_DIR / "pdf_pages"
        else:
            output_dir = Path(output_dir)
        
        ensure_directories()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pages = []
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) n'est pas installe. Installez: pip install PyMuPDF")
            raise ImportError(
                "PyMuPDF requis pour le traitement PDF. "
                "Installez-le avec: pip install PyMuPDF"
            )
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Calcul du zoom pour la resolution desiree
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                
                # Rendu de la page en image
                pix = page.get_pixmap(matrix=mat)
                
                # Sauvegarde de l'image
                output_path = output_dir / f"{pdf_path.stem}_page_{page_num + 1}.png"
                pix.save(str(output_path))
                
                # Creation de l'objet Page
                page_info = PDFPage(
                    page_num=page_num + 1,
                    image_path=str(output_path),
                    width=int(pix.width),
                    height=int(pix.height)
                )
                pages.append(page_info)
                
                logger.info(f"PDF page {page_num + 1} -> {output_path}")
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Erreur lors de la conversion PDF: {e}")
            raise RuntimeError(f"Impossible de convertir le PDF: {e}")
        
        return pages
    
    def extract_all_pages(
        self,
        pdf_path: str,
        extractor_func,
        output_dir: Optional[str] = None,
    ) -> List[dict]:
        """
        Extrait les donnees de toutes les pages d'un PDF.
        
        Args:
            pdf_path: Chemin vers le PDF
            extractor_func: Fonction d'extraction (image_path) -> dict
            output_dir: Repertoire temporaire pour les images
            
        Returns:
            Liste des resultats par page
        """
        pages = self.convert_pdf_to_images(pdf_path, output_dir)
        results = []
        
        for page in pages:
            logger.info(f"Traitement page {page.page_num}/{len(pages)}")
            
            try:
                result = extractor_func(page.image_path)
                result['pdf_page'] = page.page_num
                result['pdf_image_path'] = page.image_path
                results.append(result)
            except Exception as e:
                logger.error(f"Erreur page {page.page_num}: {e}")
                results.append({
                    'pdf_page': page.page_num,
                    'error': str(e),
                    'pdf_image_path': page.image_path
                })
        
        return results


def detect_file_format(file_path: str) -> str:
    """
    Detecte le format d'un fichier.
    
    Returns:
        'pdf', 'image', ou 'unknown'
    """
    path = Path(file_path)
    
    if not path.exists():
        return 'unknown'
    
    # PDF
    if path.suffix.lower() == '.pdf':
        return 'pdf'
    
    # Images
    image_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif', '.webp'}
    if path.suffix.lower() in image_formats:
        return 'image'
    
    return 'unknown'


def get_page_count(file_path: str) -> int:
    """
    Retourne le nombre de pages d'un fichier.
    
    Args:
        file_path: Chemin vers le fichier
        
    Returns:
        Nombre de pages (1 pour les images)
    """
    path = Path(file_path)
    
    if not path.exists():
        return 0
    
    if path.suffix.lower() == '.pdf':
        try:
            import fitz
            doc = fitz.open(path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0
    
    # Les images ont une seule page
    return 1


if __name__ == "__main__":
    # Test basique
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.core.pdf_utils <pdf_file>")
        sys.exit(1)
    
    processor = PDFProcessor(dpi=150)
    
    if processor.is_pdf(sys.argv[1]):
        pages = processor.convert_pdf_to_images(sys.argv[1])
        print(f"Nombre de pages: {len(pages)}")
        for page in pages:
            print(f"  Page {page.page_num}: {page.image_path} ({page.width}x{page.height})")
    else:
        print("Pas un PDF")
