"""
BaseExtractor - Classe abstraite pour standardiser les extracteurs.
Tous les extracteurs (Tesseract, Claude, ML) doivent heriter de cette classe.

Fournit:
- Interface commune (extract, is_available)
- Gestion du cache
- Metriques de performance
- Logging structure
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any

from exceptions import ExtractionError


logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """
    Resultat standardise d'une extraction.
    
    Attributes:
        success: True si l'extraction a reussi
        data: Donnees extraites (dict JSON)
        confidence: Score de confiance (0.0-1.0)
        method: Methode d'extraction utilisee
        duration_ms: Duree de l'extraction en millisecondes
        error: Message d'erreur si echec
        metadata: Informations supplementaires
    """
    success: bool
    data: Dict = field(default_factory=dict)
    confidence: float = 0.0
    method: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convertit le resultat en dict pour serialisation."""
        return {
            'success': self.success,
            'data': self.data,
            'confidence': self.confidence,
            'method': self.method,
            'duration_ms': round(self.duration_ms, 2),
            'error': self.error,
            'metadata': self.metadata
        }


class BaseExtractor(ABC):
    """
    Classe abstraite pour tous les extracteurs.
    
    Les extracteurs concrets doivent implementer:
    - _extract_impl(): Logique d'extraction specifique
    - is_available(): Verifier si l'extracteur est pret
    
    Attributes:
        name: Nom de l'extracteur (ex: "tesseract", "claude", "ml")
        enable_cache: Activer le cache des resultats
        cache_max_size: Taille maximale du cache LRU
    """
    
    def __init__(
        self,
        name: str,
        enable_cache: bool = True,
        cache_max_size: int = 100,
    ):
        """
        Args:
            name: Nom de l'extracteur
            enable_cache: Activer le cache des extractions
            cache_max_size: Nombre maximum d'entrees dans le cache
        """
        self.name = name
        self.enable_cache = enable_cache
        self._cache: Dict[str, ExtractionResult] = {}
        self._cache_max_size = cache_max_size
        self._stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'cache_hits': 0,
            'total_duration_ms': 0.0,
        }
    
    # =========================================================================
    # Methodes Abstraites (a implanter dans les sous-classes)
    # =========================================================================
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifie si l'extracteur est disponible et pre a fonctionner.
        
        Returns:
            True si l'extracteur peut etre utilise
        """
        pass
    
    @abstractmethod
    def _extract_impl(self, image_path: str) -> ExtractionResult:
        """
        Implementation specifique de l'extraction.
        
        Args:
            image_path: Chemin vers l'image a traiter
            
        Returns:
            ExtractionResult avec les donnees extraites
            
        Raises:
            ExtractionError: Si l'extraction echoue
        """
        pass
    
    # =========================================================================
    # Methodes Publiques
    # =========================================================================
    
    def extract(self, image_path: str, force: bool = False) -> ExtractionResult:
        """
        Extrait les donnees d'une image avec gestion du cache et des erreurs.
        
        Args:
            image_path: Chemin vers l'image
            force: Ignorer le cache et re-extraire
            
        Returns:
            ExtractionResult standardise
        """
        image_path = str(Path(image_path).resolve())
        
        # Verifier le cache si actif
        if self.enable_cache and not force:
            cached = self._get_from_cache(image_path)
            if cached:
                self._stats['cache_hits'] += 1
                logger.debug(f"Cache HIT pour {Path(image_path).name}")
                return cached
        
        # Mesurer le temps d'execution
        start_time = time.perf_counter()
        self._stats['total_extractions'] += 1
        
        try:
            # Appel de l'implementation specifique
            result = self._extract_impl(image_path)
            result.method = self.name
            result.success = True
            
            self._stats['successful_extractions'] += 1
            
        except ExtractionError as e:
            # Erreur d'extraction deja formatee
            result = ExtractionResult(
                success=False,
                error=str(e),
                method=self.name,
                metadata={'exception_type': type(e).__name__}
            )
            self._stats['failed_extractions'] += 1
            logger.warning(f"Extraction echouee: {e}")
            
        except Exception as e:
            # Erreur inattendue
            result = ExtractionResult(
                success=False,
                error=f"Erreur inattendue: {str(e)}",
                method=self.name,
                metadata={
                    'exception_type': type(e).__name__,
                    'exception_module': type(e).__module__
                }
            )
            self._stats['failed_extractions'] += 1
            logger.error(f"Erreur critique lors de l'extraction: {e}", exc_info=True)
        
        # Mesurer la duree
        duration_ms = (time.perf_counter() - start_time) * 1000
        result.duration_ms = duration_ms
        self._stats['total_duration_ms'] += duration_ms
        
        # Stocker dans le cache si succes
        if self.enable_cache and result.success:
            self._add_to_cache(image_path, result)
        
        return result
    
    def extract_batch(
        self,
        image_paths: list,
        show_progress: bool = True,
        force: bool = False,
    ) -> Dict[str, ExtractionResult]:
        """
        Extrait les donnees de plusieurs images.
        
        Args:
            image_paths: Liste des chemins d'images
            show_progress: Afficher une barre de progression
            force: Re-extraire meme si en cache
            
        Returns:
            Dict {image_path: ExtractionResult}
        """
        results = {}
        total = len(image_paths)
        
        for i, image_path in enumerate(image_paths):
            if show_progress:
                logger.info(f"Extraction [{i+1}/{total}]: {Path(image_path).name}")
            
            results[image_path] = self.extract(image_path, force=force)
        
        # Resumer
        success_count = sum(1 for r in results.values() if r.success)
        logger.info(
            f"Batch termine: {success_count}/{total} extractions reussies "
            f"({success_count/total*100:.1f}%)"
        )
        
        return results
    
    def get_stats(self) -> Dict:
        """
        Retourne les statistiques de l'extracteur.
        
        Returns:
            Dict avec les statistiques
        """
        total = self._stats['total_extractions']
        avg_duration = (
            self._stats['total_duration_ms'] / total
            if total > 0 else 0
        )
        
        return {
            'name': self.name,
            'total_extractions': total,
            'successful': self._stats['successful_extractions'],
            'failed': self._stats['failed_extractions'],
            'cache_hits': self._stats['cache_hits'],
            'cache_size': len(self._cache),
            'avg_duration_ms': round(avg_duration, 2),
            'success_rate': round(
                self._stats['successful_extractions'] / total * 100
                if total > 0 else 0, 2
            )
        }
    
    def clear_cache(self):
        """Vide le cache des extractions."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache vide ({cache_size} entrees supprimees)")
    
    # =========================================================================
    # Methodes Privees (Cache)
    # =========================================================================
    
    def _get_from_cache(self, image_path: str) -> Optional[ExtractionResult]:
        """Recupere un resultat depuis le cache."""
        return self._cache.get(image_path)
    
    def _add_to_cache(self, image_path: str, result: ExtractionResult):
        """Ajoute un resultat au cache avec eviction LRU."""
        # Eviction si cache plein
        while len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[image_path] = result
    
    # =========================================================================
    # Context Manager
    # =========================================================================
    
    def __enter__(self):
        """Context manager pour utilisation avec 'with'."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Nettoie le cache a la sortie du context manager."""
        self.clear_cache()
        return False
