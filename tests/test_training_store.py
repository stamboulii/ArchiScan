"""
Tests pour le TrainingDataStore (CRUD SQLite).
Couvre: save_extraction, validate_extraction, get_statistics, get_training_data.
"""

import json
import pytest
from pathlib import Path


# ============================================================
# Tests save_extraction
# ============================================================

class TestSaveExtraction:
    """Tests de sauvegarde des extractions."""

    def test_save_basic_extraction(self, data_store, tmp_image, sample_parcel_dict):
        row_id = data_store.save_extraction(
            image_path=tmp_image,
            extracted_data=sample_parcel_dict,
            method='claude',
            confidence=0.95,
        )
        assert row_id is not None
        assert row_id > 0

    def test_save_strips_metadata(self, data_store, tmp_image):
        data = {
            "parcelLabel": "A001",
            "_extraction_meta": {"method": "claude"},
            "_extraction_id": 42,
        }
        row_id = data_store.save_extraction(
            image_path=tmp_image,
            extracted_data=data,
            method='claude',
        )
        # Verifier que _extraction_meta n'est pas stocke
        extraction = data_store.get_extraction_by_id(row_id)
        stored_json = json.loads(extraction['extracted_json'])
        assert '_extraction_meta' not in stored_json
        assert '_extraction_id' not in stored_json
        assert stored_json['parcelLabel'] == "A001"

    def test_save_nonexistent_image_raises(self, data_store, sample_parcel_dict):
        with pytest.raises(FileNotFoundError):
            data_store.save_extraction(
                image_path="/nonexistent/image.png",
                extracted_data=sample_parcel_dict,
                method='claude',
            )

    def test_save_increments_id(self, data_store, tmp_image, sample_parcel_dict):
        id1 = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.9,
        )
        id2 = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.85,
        )
        assert id2 > id1

    def test_save_stores_image_copy(self, data_store, tmp_image, sample_parcel_dict):
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', store_image=True,
        )
        # Verifier qu'au moins un fichier a ete copie
        images = list(data_store.images_dir.iterdir())
        assert len(images) >= 1

    def test_save_without_image_copy(self, data_store, tmp_image, sample_parcel_dict):
        initial_count = len(list(data_store.images_dir.iterdir()))
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='tesseract', store_image=False,
        )
        final_count = len(list(data_store.images_dir.iterdir()))
        assert final_count == initial_count


# ============================================================
# Tests validate_extraction
# ============================================================

class TestValidateExtraction:
    """Tests de validation des extractions."""

    def test_validate_basic(self, data_store, tmp_image, sample_parcel_dict):
        row_id = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        data_store.validate_extraction(row_id)

        extraction = data_store.get_extraction_by_id(row_id)
        assert extraction['validated_by_user'] == 1

    def test_validate_with_correction(self, data_store, tmp_image, sample_parcel_dict):
        row_id = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.90,
        )

        corrected = sample_parcel_dict.copy()
        corrected['typology'] = 'T4'
        corrected['price'] = '300000'

        data_store.validate_extraction(row_id, corrected_data=corrected)

        extraction = data_store.get_extraction_by_id(row_id)
        assert extraction['validated_by_user'] == 1
        assert extraction['user_corrected_json'] is not None

        corrected_json = json.loads(extraction['user_corrected_json'])
        assert corrected_json['typology'] == 'T4'
        assert corrected_json['price'] == '300000'

    def test_validate_nonexistent_id(self, data_store):
        # Ne doit pas crasher, juste logger un warning
        data_store.validate_extraction(99999)


# ============================================================
# Tests get_statistics
# ============================================================

class TestGetStatistics:
    """Tests de recuperation des statistiques."""

    def test_empty_statistics(self, data_store):
        stats = data_store.get_statistics()
        assert stats['total_extractions'] == 0
        assert stats['validated_count'] == 0
        assert stats['claude_count'] == 0
        assert stats['tesseract_count'] == 0
        assert stats['ml_count'] == 0
        assert stats['average_confidence'] == 0.0
        assert stats['ready_for_training'] is False
        assert stats['progress_percent'] == 0.0

    def test_statistics_after_saves(self, data_store, tmp_image, sample_parcel_dict):
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='tesseract', confidence=0.70,
        )

        stats = data_store.get_statistics()
        assert stats['total_extractions'] == 2
        assert stats['claude_count'] == 1
        assert stats['tesseract_count'] == 1
        assert stats['average_confidence'] == pytest.approx(0.825, abs=0.001)

    def test_statistics_progress(self, data_store, tmp_image, sample_parcel_dict):
        # Sauvegarder et valider 1 extraction
        row_id = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        data_store.validate_extraction(row_id)

        stats = data_store.get_statistics()
        assert stats['validated_count'] == 1
        # 1/300 = 0.33%
        assert stats['progress_percent'] == pytest.approx(0.3, abs=0.1)


# ============================================================
# Tests get_training_data
# ============================================================

class TestGetTrainingData:
    """Tests de recuperation des donnees d'entrainement."""

    def test_empty_training_data(self, data_store):
        data = data_store.get_training_data()
        assert data == []

    def test_training_data_validated_only(self, data_store, tmp_image, sample_parcel_dict):
        id1 = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='tesseract', confidence=0.70,
        )

        # Valider seulement la premiere
        data_store.validate_extraction(id1)

        validated = data_store.get_training_data(validated_only=True)
        assert len(validated) == 1
        assert validated[0]['source_method'] == 'claude'

    def test_training_data_all(self, data_store, tmp_image, sample_parcel_dict):
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='tesseract', confidence=0.70,
        )

        all_data = data_store.get_training_data(validated_only=False)
        assert len(all_data) == 2

    def test_training_data_uses_corrected_json(self, data_store, tmp_image, sample_parcel_dict):
        row_id = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        corrected = sample_parcel_dict.copy()
        corrected['typology'] = 'T5'
        data_store.validate_extraction(row_id, corrected_data=corrected)

        training = data_store.get_training_data()
        assert len(training) == 1
        target = json.loads(training[0]['target_json'])
        assert target['typology'] == 'T5'


# ============================================================
# Tests get_recent_extractions
# ============================================================

class TestGetRecentExtractions:
    """Tests de recuperation des extractions recentes."""

    def test_empty_recent(self, data_store):
        recent = data_store.get_recent_extractions()
        assert recent == []

    def test_recent_with_limit(self, data_store, tmp_image, sample_parcel_dict):
        for _ in range(5):
            data_store.save_extraction(
                image_path=tmp_image, extracted_data=sample_parcel_dict,
                method='claude', confidence=0.90,
            )

        recent = data_store.get_recent_extractions(limit=3)
        assert len(recent) == 3

    def test_recent_order(self, data_store, tmp_image, sample_parcel_dict):
        id1 = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.90,
        )
        id2 = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='tesseract', confidence=0.70,
        )

        recent = data_store.get_recent_extractions(limit=2)
        # Le plus recent doit etre en premier
        assert recent[0]['id'] == id2
        assert recent[1]['id'] == id1


# ============================================================
# Tests get_extraction_by_id
# ============================================================

class TestGetExtractionById:
    """Tests de recuperation par ID."""

    def test_get_existing(self, data_store, tmp_image, sample_parcel_dict):
        row_id = data_store.save_extraction(
            image_path=tmp_image, extracted_data=sample_parcel_dict,
            method='claude', confidence=0.95,
        )
        extraction = data_store.get_extraction_by_id(row_id)
        assert extraction is not None
        assert extraction['id'] == row_id
        assert extraction['extraction_method'] == 'claude'

    def test_get_nonexistent(self, data_store):
        extraction = data_store.get_extraction_by_id(99999)
        assert extraction is None


# ============================================================
# Tests thread-safety (basique)
# ============================================================

class TestThreadSafety:
    """Tests basiques de thread-safety."""

    def test_concurrent_saves(self, data_store, tmp_image, sample_parcel_dict):
        import threading

        errors = []

        def save_extraction(i):
            try:
                data_store.save_extraction(
                    image_path=tmp_image,
                    extracted_data=sample_parcel_dict,
                    method='claude',
                    confidence=0.90 + i * 0.01,
                )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=save_extraction, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Erreurs de thread: {errors}"
        stats = data_store.get_statistics()
        assert stats['total_extractions'] == 5
