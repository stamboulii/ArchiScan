"""
Fixtures partagees pour les tests ArchiExtract.
"""

import os
import sys
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import asdict

# Ajouter le repertoire racine au path pour les imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root():
    """Retourne le chemin racine du projet."""
    return PROJECT_ROOT


@pytest.fixture
def extractor():
    """Instance d'ArchitecturePlanExtractor pour les tests."""
    from architecture_plan_extractor import ArchitecturePlanExtractor
    return ArchitecturePlanExtractor()


@pytest.fixture
def parcel_data():
    """Instance vierge de ParcelData."""
    from architecture_plan_extractor import ParcelData
    return ParcelData()


@pytest.fixture
def sample_parcel_dict():
    """Dictionnaire d'un lot complet pour les tests."""
    return {
        "parcelLabel": "A001",
        "parcelTypeId": "appartment",
        "parcelTypeLabel": "appartment",
        "typology": "T3",
        "floor": "R+1",
        "orientation": "S",
        "price": "285000",
        "living_space": "65.40",
        "surfaceDetail": {"terrace": 12.5, "balcony": 4.2},
        "option": {
            "garden": False,
            "terrace": True,
            "balcony": True,
            "parking": True,
            "winter garden": False,
            "garage": False,
            "loggia": False,
            "duplex": False,
        },
        "tva": "20",
        "pinel": "",
        "customData": None,
        "state": "available",
    }


@pytest.fixture
def sample_ocr_text():
    """Texte OCR simule pour les tests de pattern matching."""
    return """
    RESIDENCE LES JARDINS
    LOT A001 - T3
    Etage R+1
    Orientation: Sud
    Surface habitable: 65,40 m2
    Terrasse: 12,50 m2
    Balcon: 4,20 m2
    Prix: 285 000 €
    Parking inclus
    TVA 20%
    """


@pytest.fixture
def sample_claude_response():
    """Reponse JSON simulee de Claude Vision."""
    return json.dumps({
        "parcels": [
            {
                "parcelLabel": "A001",
                "parcelTypeId": "appartment",
                "parcelTypeLabel": "appartment",
                "typology": "T3",
                "floor": "R+1",
                "orientation": "S",
                "price": "285000",
                "living_space": "65.40",
                "surfaceDetail": {"terrace": 12.5},
                "option": {
                    "garden": False,
                    "terrace": True,
                    "balcony": False,
                    "parking": True,
                    "winter garden": False,
                    "garage": False,
                    "loggia": False,
                    "duplex": False,
                },
                "tva": "20",
                "pinel": "",
                "customData": None,
                "state": "available",
            }
        ],
        "confidence": 0.95,
        "notes": "Extraction reussie",
    })


@pytest.fixture
def tmp_db(tmp_path):
    """Base de donnees SQLite temporaire pour les tests."""
    db_path = str(tmp_path / "test_training.db")
    return db_path


@pytest.fixture
def data_store(tmp_db, tmp_path):
    """
    Instance de TrainingDataStore avec base temporaire.
    Patch les chemins pour utiliser des repertoires temporaires.
    """
    with patch('training_data_store.TRAINING_DB_PATH', tmp_db), \
         patch('training_data_store.TRAINING_IMAGES_DIR', str(tmp_path / "images")), \
         patch('training_data_store.ensure_directories'):
        images_dir = tmp_path / "images"
        images_dir.mkdir(exist_ok=True)

        from training_data_store import TrainingDataStore
        store = TrainingDataStore(db_path=tmp_db)
        store.images_dir = images_dir
        yield store
        store.close()


@pytest.fixture
def tmp_image(tmp_path):
    """Cree une image PNG temporaire valide pour les tests."""
    import struct
    import zlib

    img_path = tmp_path / "test_plan.png"

    # Creer un PNG 10x10 noir minimal valide
    width, height = 10, 10
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter byte
        raw_data += b'\x00\x00\x00' * width  # RGB pixels

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk + crc

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += make_chunk(b'IDAT', zlib.compress(raw_data))
    png += make_chunk(b'IEND', b'')

    img_path.write_bytes(png)
    return str(img_path)
