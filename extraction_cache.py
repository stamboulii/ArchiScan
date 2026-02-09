"""
Cache en memoire pour les extractions ArchiExtract.
Evite de retraiter une image deja extraite dans la meme session.

Fonctionne par hash SHA256 du fichier image.
Cache LRU avec taille maximale configurable.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Taille par defaut du cache (nombre d'entrees)
DEFAULT_MAX_SIZE = 100

# Duree de vie par defaut (secondes). 0 = pas d'expiration.
DEFAULT_TTL = 0


class ExtractionCache:
    """
    Cache LRU en memoire pour les resultats d'extraction.
    Cle = hash SHA256 du fichier image.
    Valeur = dict du resultat d'extraction.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL):
        """
        Args:
            max_size: Nombre maximum d'entrees dans le cache
            ttl: Duree de vie en secondes (0 = pas d'expiration)
        """
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl = ttl

        # Statistiques
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Calcule le hash SHA256 d'un fichier."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(f"Impossible de hasher le fichier {file_path}: {e}")
            return ""

    def get(self, image_path: str) -> Optional[Dict]:
        """
        Recupere un resultat d'extraction depuis le cache.

        Args:
            image_path: Chemin vers l'image

        Returns:
            Le dict du resultat d'extraction, ou None si absent/expire
        """
        if not Path(image_path).exists():
            return None

        img_hash = self._hash_file(image_path)
        if not img_hash:
            return None

        if img_hash not in self._cache:
            self.misses += 1
            return None

        # Verifier l'expiration TTL
        if self.ttl > 0:
            cached_at = self._timestamps.get(img_hash, 0)
            if time.time() - cached_at > self.ttl:
                logger.debug(f"Cache expire pour {image_path} (hash={img_hash[:12]}...)")
                self._evict(img_hash)
                self.misses += 1
                return None

        # Deplacer en fin (LRU: most recently used)
        self._cache.move_to_end(img_hash)
        self.hits += 1
        logger.info(f"Cache HIT pour {Path(image_path).name} (hash={img_hash[:12]}...)")

        return self._cache[img_hash].copy()

    def put(self, image_path: str, result: Dict):
        """
        Stocke un resultat d'extraction dans le cache.

        Args:
            image_path: Chemin vers l'image
            result: Dict du resultat d'extraction
        """
        if not Path(image_path).exists():
            return

        img_hash = self._hash_file(image_path)
        if not img_hash:
            return

        # Eviction si le cache est plein
        while len(self._cache) >= self.max_size:
            evicted_key, _ = self._cache.popitem(last=False)  # Supprimer le plus ancien
            self._timestamps.pop(evicted_key, None)
            logger.debug(f"Cache eviction LRU: {evicted_key[:12]}...")

        self._cache[img_hash] = result.copy()
        self._timestamps[img_hash] = time.time()
        logger.debug(f"Cache PUT pour {Path(image_path).name} (hash={img_hash[:12]}...)")

    def invalidate(self, image_path: str):
        """Invalide l'entree de cache pour une image donnee."""
        img_hash = self._hash_file(image_path)
        if img_hash:
            self._evict(img_hash)

    def clear(self):
        """Vide tout le cache."""
        count = len(self._cache)
        self._cache.clear()
        self._timestamps.clear()
        self.hits = 0
        self.misses = 0
        logger.info(f"Cache vide ({count} entrees supprimees)")

    def _evict(self, key: str):
        """Supprime une entree du cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    @property
    def size(self) -> int:
        """Nombre d'entrees dans le cache."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Taux de cache hit (0.0 - 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict:
        """Retourne les statistiques du cache."""
        return {
            'size': self.size,
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(self.hit_rate, 3),
            'ttl': self.ttl,
        }
