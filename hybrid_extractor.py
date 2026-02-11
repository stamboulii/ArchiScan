"""
Extracteur Hybride Progressif - Orchestre les methodes d'extraction.
Phase 0: Tesseract OCR (fallback / pas de cle API)
Phase 1: Claude Vision (+ collecte de donnees)
Phase 2: Pret pour entrainement (300+ echantillons valides)
Phase 3: Modele ML custom (avec Claude en fallback)
"""

import logging
from typing import Dict, List, Optional

from extraction_cache import ExtractionCache
from extraction_logger import get_logger, log_extraction_start, log_extraction_end, log_method_attempt, log_fallback

logger = logging.getLogger(__name__)


class HybridExtractor:
    """
    Extracteur principal qui route progressivement entre:
    - Tesseract OCR (fallback / pas de cle API)
    - Claude Vision API (Phase 1, haute precision)
    - Modele ML custom (Phase 3, apres entrainement)

    Meme interface que ArchitecturePlanExtractor pour remplacement direct.
    """

    def __init__(
        self,
        api_key: str = None,
        force_method: str = None,
        auto_validate: bool = False,
        enable_cache: bool = True,
        cache_max_size: int = 100,
    ):
        """
        Args:
            api_key: Cle API Anthropic (optionnel, lit depuis env/config)
            force_method: Forcer une methode specifique ('tesseract', 'claude', 'ml')
                         None = auto-detection de la meilleure methode
            auto_validate: Si True, marque automatiquement les extractions Claude
                          comme validees (pour le bootstrap)
            enable_cache: Si True, active le cache des extractions en memoire
            cache_max_size: Taille maximale du cache LRU
        """
        from config import ML_CONFIDENCE_THRESHOLD

        self.force_method = force_method
        self.auto_validate = auto_validate
        self.ml_confidence_threshold = ML_CONFIDENCE_THRESHOLD

        # Cache des extractions
        self._cache = ExtractionCache(max_size=cache_max_size) if enable_cache else None

        # Initialisation paresseuse des extracteurs
        self._tesseract = None
        self._claude = None
        self._ml = None
        self._store = None
        self._api_key = api_key

    @property
    def tesseract_extractor(self):
        if self._tesseract is None:
            from architecture_plan_extractor import ArchitecturePlanExtractor
            self._tesseract = ArchitecturePlanExtractor()
        return self._tesseract
    
    @tesseract_extractor.setter
    def tesseract_extractor(self, value):
        self._tesseract = value
    
    @tesseract_extractor.deleter
    def tesseract_extractor(self):
        self._tesseract = None

    @property
    def claude_extractor(self):
        if self._claude is None:
            from claude_vision_extractor import ClaudeVisionExtractor
            self._claude = ClaudeVisionExtractor(api_key=self._api_key)
        return self._claude
    
    @claude_extractor.setter
    def claude_extractor(self, value):
        self._claude = value
    
    @claude_extractor.deleter
    def claude_extractor(self):
        self._claude = None

    @property
    def ml_extractor(self):
        if self._ml is None:
            from ml_trainer import MLExtractor
            self._ml = MLExtractor()
        return self._ml
    
    @ml_extractor.setter
    def ml_extractor(self, value):
        self._ml = value
    
    @ml_extractor.deleter
    def ml_extractor(self):
        self._ml = None

    @property
    def data_store(self):
        if self._store is None:
            from training_data_store import TrainingDataStore
            self._store = TrainingDataStore()
        return self._store
    
    @data_store.setter
    def data_store(self, value):
        self._store = value
    
    @data_store.deleter
    def data_store(self):
        self._store = None

    def get_current_phase(self) -> int:
        """
        Determine la phase operationnelle actuelle.
        Phase 0: Tesseract (legacy, pas de cle API)
        Phase 1: Claude Vision (collecte de donnees)
        Phase 2: Assez de donnees, entrainement possible
        Phase 3: Modele ML disponible et charge
        """
        if self.force_method == 'ml':
            return 3
        if self.force_method == 'claude':
            return 1
        if self.force_method == 'tesseract':
            return 0

        # Auto-detection
        # Verifier si un modele ML existe
        try:
            if self.ml_extractor.is_available():
                return 3
        except Exception as e:
            logger.debug(f"Modele ML indisponible: {e}")

        # Verifier l'etat des donnees d'entrainement
        try:
            stats = self.data_store.get_statistics()
            if stats['ready_for_training']:
                return 2
        except Exception as e:
            logger.debug(f"Statistiques indisponibles: {e}")

        # Par defaut Phase 1 si Claude est disponible
        try:
            if self.claude_extractor.is_available():
                return 1
        except Exception as e:
            logger.debug(f"Claude Vision indisponible: {e}")

        return 0  # Fallback vers Tesseract

    def get_phase_description(self) -> Dict:
        """Obtient les infos de phase lisibles pour l'UI."""
        phase = self.get_current_phase()
        descriptions = {
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
                'description': 'Extraction par Claude Vision API + collecte de donnees',
                'method': 'claude',
                'accuracy': '~95%',
            },
            2: {
                'phase': 2,
                'name': 'Phase 2 - Pret pour entrainement',
                'description': 'Assez de donnees collectees, entrainement ML possible',
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
        }
        info = descriptions[phase]

        try:
            stats = self.data_store.get_statistics()
            info['training_stats'] = stats
        except Exception:
            info['training_stats'] = None

        return info

    def _determine_method(self) -> str:
        """Decide quelle methode d'extraction utiliser."""
        if self.force_method:
            return self.force_method

        phase = self.get_current_phase()

        if phase == 3:
            return 'ml'
        elif phase in (1, 2):
            return 'claude'
        else:
            return 'tesseract'

    def extract_from_image(
        self,
        image_path: str,
        save_preprocessed: bool = True,
        use_cache: bool = True,
    ) -> Dict:
        """
        Methode d'extraction principale. Route vers l'extracteur
        approprie selon la phase actuelle.

        Pour les PDFs multi-pages, extraire tous les lots de toutes les pages.

        Args:
            image_path: Chemin vers l'image ou PDF du plan
            save_preprocessed: Sauvegarder l'image preprocessee (compatibilite)
            use_cache: Si True, utilise le cache en memoire pour eviter
                      le retraitement d'images deja extraites
        """
        # Log le début de l'extraction
        log_extraction_start(image_path, self._determine_method())
        
        method = self._determine_method()
        phase = self.get_current_phase()
        logger.info(f"Extraction avec methode: {method} (Phase {phase})")

        # Gerer l'entree PDF
        is_pdf = image_path.lower().endswith('.pdf')
        if is_pdf:
            # Pour Claude: PDF directement supporte
            # Pour Tesseract: necessite conversion
            if method == 'claude':
                # Claude peut traiter le PDF directement
                actual_image_path = image_path
                logger.info(f"Extraction PDF directement avec Claude")
            else:
                # Tesseract necessite conversion
                from claude_vision_extractor import convert_pdf_to_images
                page_images = convert_pdf_to_images(image_path)
                if not page_images:
                    error = f"Impossible d'extraire les pages du PDF: {image_path}"
                    log_extraction_end(success=False, error=error)
                    raise ValueError(error)
                
                # Pour PDFs multi-pages, extraire tous les lots
                if len(page_images) > 1:
                    logger.info(f"PDF detecte avec {len(page_images)} pages - extraction multi-pages")
                    all_results = self._extract_all_pages(page_images, method)
                    
                    for page_result in all_results:
                        try:
                            extraction_id = self.data_store.save_extraction(
                                image_path=page_result.get('_image_path', image_path),
                                extracted_data=page_result,
                                method=page_result.get('_extraction_meta', {}).get('method', method),
                                confidence=page_result.get('_extraction_meta', {}).get('confidence'),
                            )
                            page_result['_extraction_id'] = extraction_id
                        except Exception as e:
                            logger.warning(f"Echec de sauvegarde: {e}")
                    
                    combined_result = self._combine_page_results(all_results)
                    log_extraction_end(success=True)
                    return combined_result
                else:
                    actual_image_path = page_images[0]
        else:
            actual_image_path = image_path

        # Verifier le cache (pour mono-page)
        if use_cache and self._cache is not None:
            cached_result = self._cache.get(actual_image_path)
            if cached_result is not None:
                logger.info("Resultat servi depuis le cache")
                return cached_result

        result = None

        try:
            if method == 'ml':
                result = self._extract_with_ml_fallback(actual_image_path)
            elif method == 'claude':
                result = self.claude_extractor.extract_from_image(actual_image_path)
            else:
                result = self.tesseract_extractor.extract_from_image(actual_image_path)
            
            # Log la tentative réussie
            log_method_attempt(method, True, result_keys=list(result.keys()) if result else [])
            
        except Exception as e:
            # Log la tentative échouée
            log_method_attempt(method, False, error=str(e))
            logger.warning(f"Methode primaire '{method}' echouee: {e}")
            
            # Log le fallback
            log_fallback(method, 'fallback', str(e))
            
            result = self._fallback_extract(actual_image_path, failed_method=method)

        # Sauvegarder dans le data store
        extraction_id = None
        try:
            meta = result.get('_extraction_meta', {})
            actual_method = meta.get('method', method)
            confidence = meta.get('confidence')

            extraction_id = self.data_store.save_extraction(
                image_path=actual_image_path,
                extracted_data=result,
                method=actual_method,
                confidence=confidence,
            )
            result['_extraction_id'] = extraction_id

            # Auto-valider les extractions Claude si configure
            if (self.auto_validate and actual_method == 'claude'
                    and confidence and confidence > 0.8):
                self.data_store.validate_extraction(extraction_id)

        except Exception as e:
            logger.warning(f"Echec de sauvegarde des donnees d'entrainement: {e}")

        # Stocker dans le cache
        if self._cache is not None:
            self._cache.put(actual_image_path, result)
        
        # Log la fin de l'extraction
        log_extraction_end(success=True, extraction_id=extraction_id)
        
        return result
    
    def _extract_all_pages(self, page_images: list, method: str) -> list:
        """Extraction de tous les lots de toutes les pages."""
        all_results = []
        
        for i, page_path in enumerate(page_images):
            logger.info(f"Extraction page {i+1}/{len(page_images)}: {page_path}")
            try:
                if method == 'claude':
                    result = self.claude_extractor.extract_from_image(page_path)
                elif method == 'ml':
                    result = self._extract_with_ml_fallback(page_path)
                else:
                    result = self.tesseract_extractor.extract_from_image(page_path)
                
                result['_image_path'] = page_path
                result['_page_number'] = i + 1
                all_results.append(result)
                
            except Exception as e:
                logger.warning(f"Echec extraction page {i+1}: {e}")
                all_results.append({
                    'error': str(e),
                    '_image_path': page_path,
                    '_page_number': i + 1
                })
        
        return all_results
    
    def _combine_page_results(self, page_results: list) -> dict:
        """Combine les resultats de plusieurs pages en un seul resultat."""
        combined = {
            'parcels': [],
            'all_parcels': {},
            '_extraction_meta': {
                'method': 'multi-page',
                'confidence': 0.0,
                'total_pages': len(page_results),
                'successful_pages': 0
            },
            '_page_results': page_results
        }
        
        total_confidence = 0.0
        
        for result in page_results:
            if 'error' in result:
                continue
            
            combined['_extraction_meta']['successful_pages'] += 1
            
            # Ajouter les lots
            parcels = result.get('parcels', [])
            if not parcels and result.get('parcelLabel'):
                # Format mono-lot
                parcels = [result]
            
            for parcel in parcels:
                label = parcel.get('parcelLabel', 'UNKNOWN')
                combined['parcels'].append(parcel)
                combined['all_parcels'][label] = parcel
            
            # Moyenne des confiance
            conf = result.get('_extraction_meta', {}).get('confidence', 0)
            if conf > 0:
                total_confidence += conf
        
        # Calculer la confiance moyenne
        successful = combined['_extraction_meta']['successful_pages']
        if successful > 0:
            combined['_extraction_meta']['confidence'] = total_confidence / successful
        
        # Copier les donnees du premier lot
        if page_results and 'parcelLabel' not in combined:
            first = page_results[0]
            for key in ['parcelLabel', 'typology', 'floor', 'orientation', 
                       'living_space', 'price', 'surfaceDetail', 'option', 
                       'tva', 'pinel', 'state']:
                if key in first:
                    combined[key] = first[key]
        
        return combined

    def _extract_with_ml_fallback(self, image_path: str) -> Dict:
        """
        Phase 3: Essayer le modele ML d'abord, fallback vers Claude
        si la confiance est basse.
        """
        try:
            result = self.ml_extractor.extract_from_image(image_path)
            meta = result.get('_extraction_meta', {})
            confidence = meta.get('confidence', 0.0)

            if confidence >= self.ml_confidence_threshold:
                logger.info(f"Extraction ML acceptee (confiance={confidence})")
                return result
            else:
                logger.info(
                    f"Confiance ML trop basse ({confidence} < {self.ml_confidence_threshold}), "
                    "fallback vers Claude"
                )
                if self.claude_extractor.is_available():
                    return self.claude_extractor.extract_from_image(image_path)
                return result

        except Exception as e:
            logger.warning(f"Extraction ML echouee: {e}, fallback vers Claude")
            if self.claude_extractor.is_available():
                return self.claude_extractor.extract_from_image(image_path)
            return self.tesseract_extractor.extract_from_image(image_path)

    def _fallback_extract(self, image_path: str, failed_method: str) -> Dict:
        """Cascade a travers les methodes d'extraction apres un echec."""
        fallback_order = ['claude', 'tesseract']

        for method in fallback_order:
            if method == failed_method:
                continue
            try:
                if method == 'claude' and self.claude_extractor.is_available():
                    log_method_attempt(method, True)
                    return self.claude_extractor.extract_from_image(image_path)
                elif method == 'tesseract':
                    result = self.tesseract_extractor.extract_from_image(image_path)
                    log_method_attempt(method, True, result_keys=list(result.keys()) if result else [])
                    return result
            except Exception as e:
                logger.warning(f"Methode fallback '{method}' aussi echouee: {e}")
                log_method_attempt(method, False, error=str(e))

        log_extraction_end(success=False, error="Toutes les methodes ont echoue")
        raise RuntimeError("Toutes les methodes d'extraction ont echoue")

    def extract_all_parcels(self, image_path: str) -> List[Dict]:
        """
        Extrait tous les lots d'une image ou PDF (multi-lots, multi-pages).
        Pour PDFs, extrait tous les lots de toutes les pages.
        """
        # Gerer l'entree PDF
        is_pdf = image_path.lower().endswith('.pdf')
        page_images = []
        if is_pdf:
            from claude_vision_extractor import convert_pdf_to_images
            page_images = convert_pdf_to_images(image_path)
            if not page_images:
                raise ValueError(f"Impossible d'extraire les pages du PDF: {image_path}")

        if self.claude_extractor.is_available():
            all_results = []
            
            # PDFs multi-pages: traiter toutes les pages
            if is_pdf and len(page_images) > 1:
                for i, page_path in enumerate(page_images):
                    logger.info(f"extract_all_parcels: page {i+1}/{len(page_images)}")
                    try:
                        results = self.claude_extractor.extract_all_parcels(page_path)
                        for r in results:
                            r['_page_number'] = i + 1
                        all_results.extend(results)
                    except Exception as e:
                        logger.warning(f"Echec extraction page {i+1}: {e}")
            else:
                # Image ou PDF mono-page
                actual = page_images[0] if page_images else image_path
                all_results = self.claude_extractor.extract_all_parcels(actual)
            
            # Sauvegarder chaque lot
            for result in all_results:
                try:
                    meta = result.get('_extraction_meta', {})
                    self.data_store.save_extraction(
                        image_path=result.get('_image_path', image_path),
                        extracted_data=result,
                        method=meta.get('method', 'claude'),
                        confidence=meta.get('confidence'),
                    )
                except Exception as e:
                    logger.warning(f"Echec sauvegarde lot: {e}")
            
            return all_results
        
        # Fallback: un seul lot via Tesseract
        if page_images:
            result = self.tesseract_extractor.extract_from_image(page_images[0])
        else:
            result = self.tesseract_extractor.extract_from_image(image_path)
        return [result]

    def extract_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        Traite plusieurs images. Compatible avec ArchitecturePlanExtractor.
        """
        results = {}
        for i, path in enumerate(image_paths, 1):
            logger.info(f"Batch {i}/{len(image_paths)}: {path}")
            try:
                data = self.extract_from_image(path)
                label = data.get('parcelLabel', f'LOT_{i:03d}')
                results[label] = data
            except Exception as e:
                logger.error(f"Erreur pour {path}: {e}")
                results[f'ERROR_{i}'] = {"error": str(e), "file": path}
        return results

    def validate_last_extraction(self, corrected_data: Dict = None):
        """
        Methode de commodite pour valider la derniere extraction.
        Appelee depuis l'UI Streamlit quand l'utilisateur clique "Valider".
        """
        recent = self.data_store.get_recent_extractions(limit=1)
        if recent:
            self.data_store.validate_extraction(
                recent[0]['id'],
                corrected_data=corrected_data
            )

    def validate_extraction_by_id(self, extraction_id: int, corrected_data: Dict = None):
        """Valide une extraction specifique par son ID."""
        self.data_store.validate_extraction(extraction_id, corrected_data=corrected_data)

    def get_statistics(self) -> Dict:
        """Proxy vers les statistiques du data store."""
        stats = self.data_store.get_statistics()
        if self._cache is not None:
            stats['cache'] = self._cache.get_stats()
        return stats

    def clear_cache(self):
        """Vide le cache d'extraction en memoire."""
        if self._cache is not None:
            self._cache.clear()

    def get_cache_stats(self) -> Optional[Dict]:
        """Retourne les statistiques du cache."""
        if self._cache is not None:
            return self._cache.get_stats()
        return None
