"""
Tests pour le cache d'extraction en memoire.
Couvre: get, put, eviction LRU, TTL, statistiques.
"""

import time
import pytest
from pathlib import Path


# ============================================================
# Tests de base
# ============================================================

class TestCacheBasic:
    """Tests des operations de base du cache."""

    @pytest.fixture
    def cache(self):
        from extraction_cache import ExtractionCache
        return ExtractionCache(max_size=10)

    def test_put_and_get(self, cache, tmp_image):
        data = {'parcelLabel': 'A001', 'typology': 'T2'}
        cache.put(tmp_image, data)
        result = cache.get(tmp_image)
        assert result is not None
        assert result['parcelLabel'] == 'A001'

    def test_get_miss(self, cache, tmp_image):
        result = cache.get(tmp_image)
        assert result is None

    def test_get_nonexistent_file(self, cache):
        result = cache.get('/nonexistent/file.png')
        assert result is None

    def test_put_nonexistent_file(self, cache):
        # Ne doit pas crasher
        cache.put('/nonexistent/file.png', {'data': 'test'})
        assert cache.size == 0

    def test_returns_copy(self, cache, tmp_image):
        """Verifier que get() retourne une copie, pas la reference."""
        original = {'parcelLabel': 'A001'}
        cache.put(tmp_image, original)

        result = cache.get(tmp_image)
        result['parcelLabel'] = 'MODIFIED'

        # L'original dans le cache ne doit pas etre modifie
        result2 = cache.get(tmp_image)
        assert result2['parcelLabel'] == 'A001'

    def test_size(self, cache, tmp_path):
        assert cache.size == 0

        for i in range(3):
            img = tmp_path / f"test_{i}.png"
            img.write_bytes(f"image_{i}".encode())
            cache.put(str(img), {'id': i})

        assert cache.size == 3


# ============================================================
# Tests LRU eviction
# ============================================================

class TestCacheLRU:
    """Tests de l'eviction LRU."""

    def test_eviction_when_full(self, tmp_path):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=3)

        images = []
        for i in range(5):
            img = tmp_path / f"img_{i}.png"
            img.write_bytes(f"content_{i}".encode())
            images.append(str(img))
            cache.put(str(img), {'id': i})

        # Seules les 3 dernieres doivent rester
        assert cache.size == 3
        assert cache.get(images[0]) is None  # Evicte
        assert cache.get(images[1]) is None  # Evicte
        assert cache.get(images[4]) is not None  # Present

    def test_lru_access_refreshes(self, tmp_path):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=3)

        imgs = []
        for i in range(3):
            img = tmp_path / f"img_{i}.png"
            img.write_bytes(f"content_{i}".encode())
            imgs.append(str(img))
            cache.put(str(img), {'id': i})

        # Acceder a img_0 pour le rafraichir (le rendre "recent")
        cache.get(imgs[0])

        # Ajouter une 4eme image -> img_1 doit etre evicte (le plus ancien)
        img_new = tmp_path / "img_new.png"
        img_new.write_bytes(b"new_content")
        cache.put(str(img_new), {'id': 'new'})

        assert cache.get(imgs[0]) is not None  # Rafraichi, donc garde
        assert cache.get(imgs[1]) is None       # Evicte


# ============================================================
# Tests TTL
# ============================================================

class TestCacheTTL:
    """Tests de l'expiration TTL."""

    def test_ttl_expiration(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=10, ttl=1)  # 1 seconde

        cache.put(tmp_image, {'data': 'test'})
        assert cache.get(tmp_image) is not None

        time.sleep(1.1)
        assert cache.get(tmp_image) is None  # Expire

    def test_no_ttl(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=10, ttl=0)  # Pas de TTL

        cache.put(tmp_image, {'data': 'test'})
        # Pas besoin d'attendre, TTL=0 signifie pas d'expiration
        assert cache.get(tmp_image) is not None


# ============================================================
# Tests statistiques
# ============================================================

class TestCacheStats:
    """Tests des statistiques du cache."""

    def test_hit_miss_tracking(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=10)

        cache.get(tmp_image)  # Miss
        cache.get(tmp_image)  # Miss
        cache.put(tmp_image, {'data': 'test'})
        cache.get(tmp_image)  # Hit
        cache.get(tmp_image)  # Hit
        cache.get(tmp_image)  # Hit

        assert cache.hits == 3
        assert cache.misses == 2
        assert cache.hit_rate == pytest.approx(0.6, abs=0.01)

    def test_get_stats(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=50, ttl=300)

        stats = cache.get_stats()
        assert stats['size'] == 0
        assert stats['max_size'] == 50
        assert stats['ttl'] == 300
        assert stats['hits'] == 0
        assert stats['misses'] == 0


# ============================================================
# Tests clear et invalidate
# ============================================================

class TestCacheClearInvalidate:
    """Tests du vidage et de l'invalidation."""

    def test_clear(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=10)

        cache.put(tmp_image, {'data': 'test'})
        assert cache.size == 1

        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_invalidate(self, tmp_image):
        from extraction_cache import ExtractionCache
        cache = ExtractionCache(max_size=10)

        cache.put(tmp_image, {'data': 'test'})
        assert cache.get(tmp_image) is not None

        cache.invalidate(tmp_image)
        assert cache.get(tmp_image) is None
