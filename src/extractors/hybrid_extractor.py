"""
Hybrid Extractor - Orchestrateur Hybride
======================================

Orchestre les differentes methodes d'extraction (Tesseract, Claude, ML).
Strategie Hybride Progressive.

Ce module est un wrapper qui utilise hybrid_extractor.py
tout en integrant les nouveaux composants.
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from ..core.config import (
    PHASE_AUTO,
    PHASE_TESSERACT,
    PHASE_CLAUDE,
    PHASE_ML,
    PHASE_PYMUPDF,
    ML_CONFIDENCE_THRESHOLD,
)
from ..core.exceptions import ExtractionError
from .tesseract_extractor import ArchitecturePlanExtractor
from .claude_extractor import ClaudeVisionExtractor
from .pymupdf_extractor import PyMuPDFExtractor

logger = logging.getLogger(__name__)


class HybridExtractor:
    """
    Extracteur hybride qui route entre Tesseract, Claude, PyMuPDF et ML.
    
    Strategie:
    - Phase 0: Tesseract OCR (gratuit, moins precis, pour images scannes)
    - Phase 1: Claude Vision API (precis, payant)
    - Phase 2: PyMuPDF (extraction directe PDF, rapide et propre)
    - Phase 3: Modele ML custom (apres entrainement)
    """
    
    def __init__(
        self,
        api_key: str = None,
        force_method: str = None,
        auto_validate: bool = False,
    ):
        """
        Args:
            api_key: Cle API Anthropic
            force_method: Forcer une methode ('tesseract', 'claude', 'pymupdf', 'ml')
            auto_validate: Marquer automatiquement les extractions comme valides
        """
        self.force_method = force_method
        self.auto_validate = auto_validate
        self.ml_confidence_threshold = ML_CONFIDENCE_THRESHOLD
        
        # Initialisation paresseuse
        self._tesseract = None
        self._claude = None
        self._pymupdf = None
        self._training_store = None
        self._data_store = None
        self._api_key = api_key
    
    @property
    def data_store(self):
        """Acces au TrainingDataStore."""
        if self._data_store is None:
            from training_data_store import TrainingDataStore
            self._data_store = TrainingDataStore()
        return self._data_store
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques du data store."""
        try:
            return self.data_store.get_statistics()
        except Exception:
            return {'total_extractions': 0, 'validated_count': 0}
    
    def validate_extraction_by_id(self, extraction_id: int, corrected_data: Dict = None):
        """Valide une extraction et la marque comme correcte pour le ML."""
        return self.data_store.validate_extraction(extraction_id, corrected_data)
    
    @property
    def tesseract_extractor(self) -> ArchitecturePlanExtractor:
        """Extracteur Tesseract."""
        if self._tesseract is None:
            self._tesseract = ArchitecturePlanExtractor()
        return self._tesseract
    
    @property
    def claude_extractor(self) -> ClaudeVisionExtractor:
        """Extracteur Claude."""
        if self._claude is None:
            self._claude = ClaudeVisionExtractor(api_key=self._api_key)
        return self._claude
    
    @property
    def pymupdf_extractor(self) -> PyMuPDFExtractor:
        """Extracteur PyMuPDF pour les fichiers PDF."""
        if self._pymupdf is None:
            self._pymupdf = PyMuPDFExtractor()
        return self._pymupdf
    
    def is_pdf_text_extractable(self, pdf_path: str) -> bool:
        """
        Verifie si un PDF contient du texte extractible.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            
        Returns:
            True si le PDF contient du texte extractible
        """
        try:
            result = self.pymupdf_extractor.extract(pdf_path)
            # Seuil reduit : certains plans ont peu de texte extractible
            return result.success and len(result.cleaned_text) > 10
        except Exception:
            return False
    
    def get_current_phase(self) -> int:
        """Determine la phase operationnelle actuelle."""
        if self.force_method == PHASE_TESSERACT:
            return 0
        elif self.force_method == PHASE_CLAUDE:
            return 1
        elif self.force_method == PHASE_PYMUPDF:
            return 4
        elif self.force_method == PHASE_ML:
            return 3
        
        # Auto-detection
        if self.claude_extractor.is_available():
            return 1
        
        # Fallback to Tesseract only if available
        if self._is_tesseract_available():
            return 0
        
        # No method available
        return -1
    
    def get_phase_description(self) -> Dict:
        """
        Obtient les informations de phase pour l'interface utilisateur.
        
        Returns:
            Dict avec les details de la phase actuelle
        """
        phase = self.get_current_phase()
        descriptions = {
            -1: {
                'phase': -1,
                'name': 'Erreur',
                'description': 'Aucune methode d\'extraction disponible. Verifiez votre configuration.',
                'method': 'none',
                'accuracy': '0%',
            },
            0: {
                'phase': 0,
                'name': 'Mode Legacy',
                'description': 'Tesseract OCR + Regex (pas de cle API configuree)',
                'method': 'tesseract',
                'accuracy': '60-75%',
            },
            1: {
                'phase': 1,
                'name': 'Phase 1 - Claude Vision',
                'description': 'Extraction par Claude Vision API',
                'method': 'claude',
                'accuracy': '~95%',
            },
            2: {
                'phase': 2,
                'name': 'Phase 2 - Pret pour entrainement',
                'description': 'Donnees collectees, entrainement ML possible',
                'method': 'claude',
                'accuracy': '~95%',
            },
            3: {
                'phase': 3,
                'name': 'Phase 3 - Modele ML Custom',
                'description': 'Modele ML independant avec Claude en fallback',
                'method': 'ml',
                'accuracy': '~92%+',
            },
            4: {
                'phase': 4,
                'name': 'PyMuPDF - Extraction Directe',
                'description': 'Extraction texte PDF directe (rapide, sans OCR)',
                'method': 'pymupdf',
                'accuracy': '70-90%',
            },
        }
        return descriptions.get(phase, descriptions[0])
    
    def _determine_method(self) -> str:
        """Determine la methode d'extraction a utiliser."""
        if self.force_method:
            return self.force_method
        
        # Phase 1: Claude si disponible
        if self.claude_extractor.is_available():
            return PHASE_CLAUDE
        
        # Phase 0: Tesseract seulement si disponible
        if self._is_tesseract_available():
            return PHASE_TESSERACT
        
        # Aucune methode disponible
        return 'none'
    
    def extract_from_image(self, image_path: str) -> Dict:
        """
        Methode principale d'extraction compatible avec l'API existante.
        
        Args:
            image_path: Chemin vers l'image ou PDF
            
        Returns:
            Dict avec les donnees extraites
        """
        method = self._determine_method()
        logger.info(f"Extraction avec methode: {method}")
        
        if method == PHASE_CLAUDE:
            result = self._extract_with_claude(image_path)
        else:
            result = self._extract_with_tesseract(image_path)
        
        # Sauvegarder dans le data store
        try:
            extraction_id = self.data_store.save_extraction(
                image_path=image_path,
                extracted_data=result,
                method=method,
                confidence=result.get('_extraction_meta', {}).get('confidence'),
            )
            result['_extraction_id'] = extraction_id
        except Exception as e:
            logger.warning(f"Echec sauvegarde data store: {e}")
        
        return result
    
    def extract_from_pdf(self, pdf_path: str) -> Dict:
        """
        Extrait les donnees d'un fichier PDF en utilisant PyMuPDF.
        Methode preferentielle pour les PDF avec texte extractible.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            
        Returns:
            Dict avec les donnees extraites
        """
        import time
        start_time = time.time()
        
        try:
            # Verifier si PyMuPDF est disponible
            if not self.pymupdf_extractor.is_available():
                raise ExtractionError("PyMuPDF n'est pas disponible")
            
            # Verifier si le PDF contient du texte extractible
            if not self.is_pdf_text_extractable(pdf_path):
                logger.warning(
                    f"Le PDF {pdf_path} ne contient pas de texte extractible. "
                    f"Fallback vers Tesseract OCR."
                )
                # Fallback vers Tesseract
                tess_result = self._extract_with_tesseract(pdf_path)
                if '_extraction_meta' in tess_result:
                    tess_result['_extraction_meta']['fallback_reason'] = "PDF sans texte detecte (image scannee)"
                return tess_result
            
            # Extraction avec PyMuPDF
            result = self.pymupdf_extractor.extract(pdf_path)
            
            if not result.success:
                raise ExtractionError(result.error or "Erreur extraction PyMuPDF")
            
            # Convertir en format standard
            parcel_data = self.pymupdf_extractor.to_parcel_data(result)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Utiliser to_dict() pour obtenir la structure correcte
            extracted_data = parcel_data.to_dict()
            
            # S'assurer que parcelLabel est present (parfois mappe differemment dans to_dict)
            if parcel_data.parcelLabel:
                extracted_data['parcelLabel'] = parcel_data.parcelLabel
            else:
                # Fallback sur le nom du fichier
                extracted_data['parcelLabel'] = Path(pdf_path).stem
            
            
            extracted_data['_extraction_meta'] = {
                'method': PHASE_PYMUPDF,
                'confidence': result.confidence,
                'duration_ms': duration_ms,
                'text_length': len(result.cleaned_text),
            }
            extracted_data['_raw_text'] = result.cleaned_text[:500] if result.cleaned_text else ""
            
            # Sauvegarder dans le data store
            try:
                extraction_id = self.data_store.save_extraction(
                    pdf_path=pdf_path,
                    extracted_data=extracted_data,
                    method=PHASE_PYMUPDF,
                    confidence=result.confidence,
                )
                extracted_data['_extraction_id'] = extraction_id
            except Exception as e:
                logger.warning(f"Echec sauvegarde data store: {e}")
            
            logger.info(f"Extraction PyMuPDF terminee en {duration_ms:.2f}ms")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Erreur extraction PDF: {e}")
            # Fallback vers Tesseract
            logger.info("Fallback vers Tesseract OCR")
            tess_result = self._extract_with_tesseract(pdf_path)
            if '_extraction_meta' in tess_result:
                tess_result['_extraction_meta']['fallback_reason'] = f"Echec PyMuPDF: {str(e)}"
            return tess_result
    
    def extract(self, image_path: str) -> Dict:
        """
        Extrait les donnees en utilisant la meilleure methode disponible.
        
        Args:
            image_path: Chemin vers l'image du plan
            
        Returns:
            Dict avec les donnees extraites
        """
        method = self._determine_method()
        logger.info(f"Methode d'extraction: {method}")
        
        if method == 'none':
            raise ExtractionError(
                "Aucune methode d'extraction n'est disponible.\n"
                "- Claude API: Credits insuffisants ou non configure\n"
                "- Tesseract: Non configure (TESSDATA_PREFIX manquant)\n"
                "Veuillez verifier votre configuration."
            )
        
        if method == PHASE_CLAUDE:
            return self._extract_with_claude(image_path)
        elif method == PHASE_TESSERACT:
            return self._extract_with_tesseract(image_path)
        else:
            raise ExtractionError(f"Methode d'extraction non supportee: {method}")
    
    def _extract_with_tesseract(self, image_path: str) -> Dict:
        """Extraction avec Tesseract OCR."""
        # Verifier si Tesseract est disponible
        if not self._is_tesseract_available():
            raise ExtractionError(
                "Tesseract OCR n'est pas configure. \n"
                "Sur Windows avec Scoop: TESSDATA_PREFIX doit pointer vers le dossier tessdata.\n"
                "Exemple: set TESSDATA_PREFIX=C:\\Users\\MSI\\scoop\\persist\\tesseract\\tessdata\n"
                "Ou ajoutez des credits Anthropic pour utiliser Claude Vision."
            )
            
        try:
            # Convertir PDF en image si necessaire
            from src.core.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            actual_path = image_path
            
            if image_path.lower().endswith('.pdf'):
                logger.info(f"Conversion PDF en image pour Tesseract: {image_path}")
                pages = pdf_processor.convert_pdf_to_images(image_path)
                if pages:
                    actual_path = pages[0].image_path
                else:
                    raise ExtractionError("Impossible de convertir le PDF en image")
            
            result = self.tesseract_extractor.extract_from_image(actual_path)
            
            # Ajouter les metadonnees manquantes
            if '_extraction_meta' not in result:
                result['_extraction_meta'] = {
                    'method': PHASE_TESSERACT,
                    'confidence': 0.7,  # Confiance par defaut pour Tesseract
                    'model': 'tesseract-ocr'
                }
            
            return result
        except Exception as e:
            logger.error(f"Tesseract echoue: {e}")
            raise ExtractionError(f"Extraction Tesseract echouee: {e}")
    
    def _is_tesseract_available(self) -> bool:
        """Verifie si Tesseract est correctement configure."""
        try:
            import subprocess
            import os
            
            # Verifier la commande tesseract
            result = subprocess.run(
                ['tesseract', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
            
            # Verifier si un dossier tessdata local existe (priorite)
            local_tessdata = os.path.join(os.getcwd(), 'tessdata')
            if os.path.exists(os.path.join(local_tessdata, 'eng.traineddata')):
                os.environ['TESSDATA_PREFIX'] = local_tessdata
                logger.info(f"Using local TESSDATA_PREFIX: {local_tessdata}")
                return True

            # Verifier TESSDATA_PREFIX environment variable
            tessdata_prefix = os.environ.get('TESSDATA_PREFIX', '')
            if not tessdata_prefix:
                # Essayer de detecter automatiquement sur Windows
                scoop_tessdata = r'C:\Users\MSI\scoop\persist\tesseract\tessdata'
                if os.path.exists(scoop_tessdata):
                    os.environ['TESSDATA_PREFIX'] = scoop_tessdata
                    logger.info(f"TESSDATA_PREFIX automatiquement configure: {scoop_tessdata}")
                    return True
                logger.warning("TESSDATA_PREFIX non configure")
                return False
            
            # Verifier que le repertoire tessdata existe
            if not os.path.isdir(tessdata_prefix):
                logger.warning(f"Repertoire TESSDATA_PREFIX inexistant: {tessdata_prefix}")
                return False
            
            # Verifier les fichiers de langue
            eng_path = os.path.join(tessdata_prefix, 'eng.traineddata')
            if not os.path.exists(eng_path):
                logger.warning(f"Fichier de langue manquant: {eng_path}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Erreur verification Tesseract: {e}")
            return False
        except Exception:
            return False
    
    def _extract_with_claude(self, image_path: str) -> Dict:
        """Extraction avec Claude Vision."""
        try:
            # Convertir PDF en image si necessaire
            from src.core.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            actual_path = image_path
            
            if image_path.lower().endswith('.pdf'):
                logger.info(f"Conversion PDF en image: {image_path}")
                pages = pdf_processor.convert_pdf_to_images(image_path)
                if pages:
                    actual_path = pages[0].image_path  # Utiliser la premiere page
                else:
                    raise ExtractionError("Impossible de convertir le PDF en image")
            
            result = self.claude_extractor.extract(actual_path)
            
            # Auto-validation pour bootstrap
            if self.auto_validate:
                logger.info("Auto-validation activee (resultat marque comme valide)")
            
            return result
        except Exception as e:
            error_str = str(e).lower()
            # Verifier si c'est une erreur de credits/facturation
            if 'credit' in error_str or 'billing' in error_str or 'balance' in error_str:
                logger.error(f"Claude indisponible (credits epuises): {e}")
                raise ClaudeAPIError(
                    "Credits Anthropic insuffisants. Achetez des credits sur console.anthropic.com "
                    "ou utilisez des images (PNG/JPG) avec Tesseract OCR."
                )
            
            logger.error(f"Claude echoue: {e}")
            # Fallback vers Tesseract uniquement pour images
            if image_path.lower().endswith('.pdf'):
                raise ClaudeAPIError(
                    "Claude echoue et Tesseract ne supporte pas les PDFs. "
                    "Achetez des credits Anthropic pour traiter les PDFs."
                )
            
            logger.info("Fall back vers Tesseract...")
            return self._extract_with_tesseract(image_path)
    
    def extract_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        Traite plusieurs images.
        
        Args:
            image_paths: Liste des chemins
            
        Returns:
            Dict {image_path: resultat}
        """
        results = {}
        
        for i, image_path in enumerate(image_paths):
            logger.info(f"[{i+1}/{len(image_paths)}] {image_path}")
            
            try:
                results[image_path] = self.extract(image_path)
            except Exception as e:
                logger.error(f"Erreur sur {image_path}: {e}")
                results[image_path] = {'error': str(e)}
        
        success = sum(1 for r in results.values() if 'error' not in r)
        logger.info(f"Termine: {success}/{len(results)} extractions reussies")
        
        return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m archiextract.extractors.hybrid_extractor <image_path>")
        sys.exit(1)
    
    extractor = HybridExtractor()
    result = extractor.extract(sys.argv[1])
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
