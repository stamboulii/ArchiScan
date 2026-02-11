"""
Tests pour le module ml_trainer.py (MLExtractor, MLTrainer, normalize_parcel_data).
Couvre la normalisation, l'extracteur ML, le trainer, et l'export de dataset.
"""

import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


# ============================================================
# Tests: normalize_parcel_data (fonction standalone)
# ============================================================

class TestNormalizeParcelData:
    """Tests pour la fonction normalize_parcel_data."""

    def test_normalize_complete_parcel(self, sample_parcel_dict):
        """Normalise un dict complet sans perte de donnees."""
        from ml_trainer import normalize_parcel_data
        result = normalize_parcel_data(sample_parcel_dict)

        assert result['parcelLabel'] == 'A001'
        assert result['typology'] == 'T3'
        assert result['floor'] == 'R+1'
        assert result['orientation'] == 'S'
        assert result['price'] == '285000'
        assert result['living_space'] == '65.40'
        assert result['state'] == 'available'
        assert result['tva'] == '20'

    def test_normalize_empty_dict(self):
        """Un dict vide produit des valeurs par defaut."""
        from ml_trainer import normalize_parcel_data
        result = normalize_parcel_data({})

        assert result['parcelLabel'] == ''
        assert result['typology'] == ''
        assert result['price'] == 'N.C'
        assert result['state'] == 'available'
        assert result['parcelTypeId'] == 'appartment'
        assert result['parcelTypeLabel'] == 'appartment'
        assert result['living_space'] == ''
        assert result['customData'] is None

    def test_normalize_surface_detail_valid(self):
        """Les surfaces valides sont converties en float."""
        from ml_trainer import normalize_parcel_data
        raw = {'surfaceDetail': {'terrace': '12.5', 'balcony': 4.2}}
        result = normalize_parcel_data(raw)

        assert result['surfaceDetail']['terrace'] == 12.5
        assert result['surfaceDetail']['balcony'] == 4.2

    def test_normalize_surface_detail_invalid_values(self):
        """Les surfaces invalides sont ignorees sans erreur."""
        from ml_trainer import normalize_parcel_data
        raw = {'surfaceDetail': {'terrace': 'abc', 'balcony': None, 'garden': 0, 'loggia': ''}}
        result = normalize_parcel_data(raw)

        # abc est invalide -> ignore, None/0/"" -> ignores aussi
        assert 'terrace' not in result['surfaceDetail']
        assert 'balcony' not in result['surfaceDetail']
        assert 'garden' not in result['surfaceDetail']
        assert 'loggia' not in result['surfaceDetail']

    def test_normalize_surface_detail_not_dict(self):
        """surfaceDetail non-dict est ignore."""
        from ml_trainer import normalize_parcel_data
        raw = {'surfaceDetail': 'invalid'}
        result = normalize_parcel_data(raw)
        # Le default de ParcelData est utilise
        assert isinstance(result['surfaceDetail'], dict)

    def test_normalize_options_merge_defaults(self):
        """Les options partielles sont fusionnees avec les defauts."""
        from ml_trainer import normalize_parcel_data
        raw = {'option': {'terrace': True, 'parking': True}}
        result = normalize_parcel_data(raw)

        assert result['option']['terrace'] is True
        assert result['option']['parking'] is True
        # Les autres restent a False (defaut)
        assert result['option']['garden'] is False
        assert result['option']['duplex'] is False

    def test_normalize_options_not_dict(self):
        """option non-dict garde les defauts."""
        from ml_trainer import normalize_parcel_data
        raw = {'option': 'invalid'}
        result = normalize_parcel_data(raw)
        assert all(v is False for v in result['option'].values())

    def test_normalize_price_empty_becomes_nc(self):
        """Un prix vide devient 'N.C'. None -> 'None' via str(), 0 -> '0'."""
        from ml_trainer import normalize_parcel_data

        # Vide string -> N.C (via `or 'N.C'`)
        result = normalize_parcel_data({'price': ''})
        assert result['price'] == 'N.C'

        # None -> 'N.C' car None est falsy
        result = normalize_parcel_data({'price': None})
        assert result['price'] == 'N.C'

        # 0 -> 'N.C' car 0 est falsy
        result = normalize_parcel_data({'price': 0})
        assert result['price'] == 'N.C'

        # Pas de prix -> default 'N.C'
        result = normalize_parcel_data({})
        assert result['price'] == 'N.C'

    def test_normalize_preserves_custom_data(self):
        """customData est preserve tel quel."""
        from ml_trainer import normalize_parcel_data
        custom = {'extra_field': 'value', 'nested': {'a': 1}}
        result = normalize_parcel_data({'customData': custom})
        assert result['customData'] == custom

    def test_normalize_type_coercion(self):
        """Les valeurs numeriques sont converties en string."""
        from ml_trainer import normalize_parcel_data
        raw = {
            'parcelLabel': 123,
            'typology': 3,
            'floor': 2,
            'price': 285000,
            'living_space': 65.4,
        }
        result = normalize_parcel_data(raw)
        assert result['parcelLabel'] == '123'
        assert result['typology'] == '3'
        assert result['floor'] == '2'
        assert result['price'] == '285000'
        assert result['living_space'] == '65.4'


# ============================================================
# Tests: MLExtractor
# ============================================================

class TestMLExtractor:
    """Tests pour la classe MLExtractor."""

    def test_init_default_model_dir(self):
        """Initialisation avec le repertoire modele par defaut."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor()
        from config import ML_MODEL_DIR
        assert extractor.model_dir == ML_MODEL_DIR
        assert extractor._model is None
        assert extractor._processor is None

    def test_init_custom_model_dir(self, tmp_path):
        """Initialisation avec un repertoire modele custom."""
        from ml_trainer import MLExtractor
        custom_dir = str(tmp_path / "custom_model")
        extractor = MLExtractor(model_path=custom_dir)
        assert extractor.model_dir == Path(custom_dir)

    def test_is_available_no_model(self, tmp_path):
        """is_available retourne False sans config.json."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path / "empty_model"))
        assert extractor.is_available() is False

    def test_is_available_with_config(self, tmp_path):
        """is_available retourne True avec config.json present."""
        from ml_trainer import MLExtractor
        model_dir = tmp_path / "valid_model"
        model_dir.mkdir()
        (model_dir / "config.json").write_text('{}')
        extractor = MLExtractor(model_path=str(model_dir))
        assert extractor.is_available() is True

    def test_load_model_no_model_raises(self, tmp_path):
        """_load_model leve RuntimeError sans modele."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path / "nomodel"))
        with pytest.raises(RuntimeError, match="Aucun modele entraine"):
            extractor._load_model()

    def test_load_model_no_transformers_raises(self, tmp_path):
        """_load_model leve RuntimeError sans transformers installe."""
        from ml_trainer import MLExtractor
        model_dir = tmp_path / "model_no_deps"
        model_dir.mkdir()
        (model_dir / "config.json").write_text('{}')
        extractor = MLExtractor(model_path=str(model_dir))

        with patch.dict('sys.modules', {'transformers': None}):
            with pytest.raises(RuntimeError, match="dependances ML"):
                extractor._load_model()

    def test_load_model_cached(self, tmp_path):
        """_load_model ne recharge pas si deja charge."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path))
        extractor._model = MagicMock()  # Simulate already loaded
        extractor._load_model()  # Should return immediately
        # No error = success (didn't try to reload)

    def test_extract_from_image_file_not_found(self, tmp_path):
        """extract_from_image leve FileNotFoundError pour image inexistante."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path))
        with pytest.raises(FileNotFoundError, match="Image introuvable"):
            extractor.extract_from_image(str(tmp_path / "missing.png"))

    def test_extract_batch_empty_list(self, tmp_path):
        """extract_batch avec liste vide retourne dict vide."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path))
        result = extractor.extract_batch([])
        assert result == {}

    def test_extract_batch_with_missing_files(self, tmp_path):
        """extract_batch gere les fichiers manquants gracieusement."""
        from ml_trainer import MLExtractor
        extractor = MLExtractor(model_path=str(tmp_path))
        result = extractor.extract_batch([
            str(tmp_path / "missing1.png"),
            str(tmp_path / "missing2.png"),
        ])
        assert 'MISSING_1' in result
        assert 'MISSING_2' in result
        assert 'error' in result['MISSING_1']

    def test_compute_confidence_no_scores(self):
        """_compute_confidence retourne le seuil par defaut sans scores."""
        from ml_trainer import MLExtractor
        from config import ML_CONFIDENCE_THRESHOLD

        outputs = MagicMock()
        outputs.scores = None
        confidence = MLExtractor._compute_confidence(outputs)
        assert confidence == ML_CONFIDENCE_THRESHOLD

    def test_compute_confidence_empty_scores(self):
        """_compute_confidence retourne le seuil par defaut avec scores vides."""
        from ml_trainer import MLExtractor
        from config import ML_CONFIDENCE_THRESHOLD

        outputs = MagicMock()
        outputs.scores = []
        confidence = MLExtractor._compute_confidence(outputs)
        assert confidence == ML_CONFIDENCE_THRESHOLD

    def test_compute_confidence_with_scores(self):
        """_compute_confidence calcule correctement depuis les scores."""
        from ml_trainer import MLExtractor

        try:
            import torch
        except ImportError:
            pytest.skip("torch non installe")

        # Creer des faux scores avec des probas connues
        score1 = torch.tensor([[0.0, 0.0, 10.0]])  # max prob ~1.0 apres softmax
        score2 = torch.tensor([[0.0, 0.0, 10.0]])

        outputs = MagicMock()
        outputs.scores = [score1, score2]

        confidence = MLExtractor._compute_confidence(outputs)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.9  # Avec des scores aussi nets, confiance haute

    def test_compute_confidence_handles_exception(self):
        """_compute_confidence ne plante pas sur exception."""
        from ml_trainer import MLExtractor
        from config import ML_CONFIDENCE_THRESHOLD

        outputs = MagicMock()
        outputs.scores = MagicMock(side_effect=Exception("boom"))

        confidence = MLExtractor._compute_confidence(outputs)
        assert confidence == ML_CONFIDENCE_THRESHOLD


# ============================================================
# Tests: MLTrainer
# ============================================================

class TestMLTrainer:
    """Tests pour la classe MLTrainer."""

    def test_init_default_output_dir(self):
        """Initialisation avec le repertoire de sortie par defaut."""
        from ml_trainer import MLTrainer
        from config import ML_MODEL_DIR
        trainer = MLTrainer()
        assert trainer.output_dir == ML_MODEL_DIR

    def test_init_custom_output_dir(self, tmp_path):
        """Initialisation avec un repertoire custom."""
        from ml_trainer import MLTrainer
        custom = str(tmp_path / "custom_out")
        trainer = MLTrainer(output_dir=custom)
        assert trainer.output_dir == Path(custom)

    def test_prepare_dataset_empty_raises(self):
        """prepare_dataset leve ValueError sur liste vide."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        with pytest.raises(ValueError, match="liste vide"):
            trainer.prepare_dataset([])

    def test_prepare_dataset_too_few_raises(self, tmp_image):
        """prepare_dataset leve ValueError avec < 10 echantillons valides."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()

        # Seulement 5 echantillons valides
        data = [
            {'image_path': tmp_image, 'target_json': '{"parcelLabel": "A001"}'}
            for _ in range(5)
        ]

        try:
            with pytest.raises(ValueError, match="Pas assez de donnees valides"):
                trainer.prepare_dataset(data)
        except RuntimeError:
            pytest.skip("datasets/sklearn non installe")

    def test_prepare_dataset_skips_missing_images(self, tmp_path, tmp_image):
        """prepare_dataset ignore les images manquantes."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()

        # 12 valides + 3 avec images manquantes
        data = [
            {'image_path': tmp_image, 'target_json': json.dumps({"parcelLabel": f"LOT_{i}"})}
            for i in range(12)
        ]
        data.extend([
            {'image_path': str(tmp_path / f"missing_{i}.png"), 'target_json': '{}'}
            for i in range(3)
        ])

        try:
            train_ds, val_ds = trainer.prepare_dataset(data)
            # 12 valides: 90% train, 10% val
            assert len(train_ds) + len(val_ds) == 12
        except RuntimeError:
            pytest.skip("datasets/sklearn non installe")

    def test_prepare_dataset_skips_empty_json(self, tmp_image):
        """prepare_dataset ignore les entrees sans JSON cible."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()

        data = [
            {'image_path': tmp_image, 'target_json': json.dumps({"label": f"L{i}"})}
            for i in range(12)
        ]
        # Ajouter des entrees avec JSON vide
        data.append({'image_path': tmp_image, 'target_json': ''})
        data.append({'image_path': tmp_image, 'target_json': None})

        try:
            train_ds, val_ds = trainer.prepare_dataset(data)
            assert len(train_ds) + len(val_ds) == 12
        except RuntimeError:
            pytest.skip("datasets/sklearn non installe")

    def test_prepare_dataset_skips_invalid_json(self, tmp_image):
        """prepare_dataset ignore les entrees avec JSON invalide."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()

        data = [
            {'image_path': tmp_image, 'target_json': json.dumps({"label": f"L{i}"})}
            for i in range(12)
        ]
        data.append({'image_path': tmp_image, 'target_json': 'not valid json {'})

        try:
            train_ds, val_ds = trainer.prepare_dataset(data)
            assert len(train_ds) + len(val_ds) == 12
        except RuntimeError:
            pytest.skip("datasets/sklearn non installe")

    def test_train_empty_data_raises(self):
        """train leve ValueError sur donnees vides."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        with pytest.raises(ValueError, match="Aucune donnee"):
            trainer.train([])

    def test_train_none_data_raises(self):
        """train leve ValueError sur None."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        with pytest.raises(ValueError, match="Aucune donnee"):
            trainer.train(None)

    def test_train_returns_pending_status(self, tmp_path, tmp_image):
        """train retourne un status 'pending' avec le bon format."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer(output_dir=str(tmp_path / "model_out"))

        data = [
            {'image_path': tmp_image, 'target_json': json.dumps({"parcelLabel": f"LOT_{i}"})}
            for i in range(15)
        ]

        try:
            # Patcher _record_training_run pour eviter les deps DB
            with patch.object(trainer, '_record_training_run'):
                result = trainer.train(data)

            assert result['status'] == 'pending'
            assert result['samples_used'] == 15
            assert 'train_size' in result
            assert 'val_size' in result
            assert result['train_size'] + result['val_size'] == 15
            assert 'output_dir' in result
            assert 'message' in result
        except RuntimeError:
            pytest.skip("datasets/sklearn non installe")

    def test_record_training_run_handles_error(self, tmp_path):
        """_record_training_run ne plante pas sur erreur DB."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer(output_dir=str(tmp_path))

        # Mock TrainingDataStore dans le scope ou il est importe (localement dans _record_training_run)
        with patch('training_data_store.TrainingDataStore', side_effect=Exception("DB error")):
            # Patcher au bon endroit: l'import local dans _record_training_run
            import ml_trainer as ml_mod
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            # Approche: tester que la methode ne leve pas d'exception
            # en utilisant un store reel mais temporaire
            trainer._record_training_run(100)
            # Pas d'exception = succes

    def test_record_training_run_uses_context_manager(self, tmp_path):
        """_record_training_run utilise _get_connection() au lieu de _connect()."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer(output_dir=str(tmp_path))

        mock_store = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Configurer le context manager correctement
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_store._get_connection.return_value = mock_ctx

        # Le TrainingDataStore est importe localement dans _record_training_run
        # Il faut patcher au niveau du module training_data_store
        with patch('training_data_store.TrainingDataStore', return_value=mock_store):
            trainer._record_training_run(50)

        # Verifier que _get_connection() est appele, pas _connect()
        mock_store._get_connection.assert_called_once()
        mock_store._connect.assert_not_called()
        mock_store.close.assert_called_once()


# ============================================================
# Tests: MLTrainer.export_dataset
# ============================================================

class TestMLTrainerExport:
    """Tests pour l'export de dataset."""

    def test_export_empty_raises(self, tmp_path):
        """export_dataset leve ValueError sur liste vide."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        with pytest.raises(ValueError, match="Aucune donnee"):
            trainer.export_dataset([], str(tmp_path / "export"))

    def test_export_creates_structure(self, tmp_path, tmp_image):
        """export_dataset cree la bonne structure de repertoires."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        output_dir = str(tmp_path / "export_output")

        data = [
            {
                'image_path': tmp_image,
                'target_json': json.dumps({"parcelLabel": "A001"}),
            }
        ]

        result = trainer.export_dataset(data, output_dir)

        assert result['exported_count'] == 1
        assert result['skipped_count'] == 0
        assert Path(output_dir).exists()
        assert (Path(output_dir) / "images").exists()
        assert (Path(output_dir) / "metadata.json").exists()

    def test_export_metadata_content(self, tmp_path, tmp_image):
        """export_dataset genere un metadata.json correct."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        output_dir = str(tmp_path / "export_meta")

        data = [
            {
                'image_path': tmp_image,
                'target_json': json.dumps({"parcelLabel": "LOT_001"}),
            },
            {
                'image_path': tmp_image,
                'target_json': json.dumps({"parcelLabel": "LOT_002"}),
            },
        ]

        result = trainer.export_dataset(data, output_dir)
        assert result['exported_count'] == 2

        # Verifier le contenu du metadata.json
        with open(Path(output_dir) / "metadata.json", 'r') as f:
            metadata = json.load(f)

        assert len(metadata) == 2
        assert metadata[0]['file_name'] == '00000.png'
        assert metadata[1]['file_name'] == '00001.png'
        assert 'target' in metadata[0]

    def test_export_skips_missing_images(self, tmp_path, tmp_image):
        """export_dataset ignore les images manquantes."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        output_dir = str(tmp_path / "export_skip")

        data = [
            {'image_path': tmp_image, 'target_json': '{"label": "ok"}'},
            {'image_path': str(tmp_path / "missing.png"), 'target_json': '{"label": "skip"}'},
        ]

        result = trainer.export_dataset(data, output_dir)
        assert result['exported_count'] == 1
        assert result['skipped_count'] == 1

    def test_export_handles_copy_error(self, tmp_path, tmp_image):
        """export_dataset gere les erreurs de copie sans crash."""
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        output_dir = str(tmp_path / "export_err")

        data = [
            {'image_path': tmp_image, 'target_json': '{"label": "test"}'},
        ]

        with patch('shutil.copy2', side_effect=IOError("permission denied")):
            result = trainer.export_dataset(data, output_dir)

        assert result['exported_count'] == 0
        assert result['skipped_count'] == 1


# ============================================================
# Tests: Integration / compatibilite d'interface
# ============================================================

class TestMLIntegration:
    """Tests d'integration et de compatibilite d'interface."""

    def test_normalize_parcel_data_matches_claude_extractor(self, sample_parcel_dict):
        """normalize_parcel_data produit le meme resultat que _normalize_parcel de Claude."""
        from ml_trainer import normalize_parcel_data
        from claude_vision_extractor import ClaudeVisionExtractor

        ml_result = normalize_parcel_data(sample_parcel_dict)

        # Comparer avec le resultat de ClaudeVisionExtractor
        claude_ext = ClaudeVisionExtractor.__new__(ClaudeVisionExtractor)
        claude_result = claude_ext._normalize_parcel(sample_parcel_dict)

        # Les deux doivent etre identiques
        assert ml_result == claude_result

    def test_normalize_parcel_data_matches_claude_empty(self):
        """Les resultats sont identiques pour un dict vide aussi."""
        from ml_trainer import normalize_parcel_data
        from claude_vision_extractor import ClaudeVisionExtractor

        ml_result = normalize_parcel_data({})
        claude_ext = ClaudeVisionExtractor.__new__(ClaudeVisionExtractor)
        claude_result = claude_ext._normalize_parcel({})

        assert ml_result == claude_result

    def test_ml_extractor_interface_compatible(self):
        """MLExtractor a la meme interface que les autres extracteurs."""
        from ml_trainer import MLExtractor

        extractor = MLExtractor()
        assert hasattr(extractor, 'extract_from_image')
        assert hasattr(extractor, 'extract_batch')
        assert hasattr(extractor, 'is_available')

    def test_ml_confidence_threshold_from_config(self):
        """ML_CONFIDENCE_THRESHOLD est charge depuis la config."""
        from config import ML_CONFIDENCE_THRESHOLD
        assert isinstance(ML_CONFIDENCE_THRESHOLD, float)
        assert 0.0 <= ML_CONFIDENCE_THRESHOLD <= 1.0

    def test_no_more_connect_usage(self):
        """Verifie que _connect() n'est plus utilise dans ml_trainer.py."""
        import inspect
        from ml_trainer import MLTrainer

        source = inspect.getsource(MLTrainer)
        # _connect() ne doit plus apparaitre dans le code
        assert '_connect()' not in source
        # _get_connection() doit etre utilise a la place
        assert '_get_connection()' in source

    def test_no_more_new_antipattern(self):
        """Verifie que __new__() anti-pattern n'est plus utilise."""
        import inspect
        from ml_trainer import MLExtractor

        source = inspect.getsource(MLExtractor)
        assert '__new__' not in source

    def test_normalize_standalone_no_claude_dependency(self):
        """normalize_parcel_data n'importe pas ClaudeVisionExtractor dans le code executable."""
        import inspect
        import re
        from ml_trainer import normalize_parcel_data

        source = inspect.getsource(normalize_parcel_data)
        # Retirer les commentaires et docstrings pour ne verifier que le code executif
        # Supprimer les lignes de commentaires
        code_lines = [
            line for line in source.split('\n')
            if not line.strip().startswith('#') and not line.strip().startswith('"""')
        ]
        executable_code = '\n'.join(code_lines)
        # Verifier qu'il n'y a pas d'import de ClaudeVisionExtractor
        assert 'from claude_vision_extractor import' not in executable_code
        assert 'import ClaudeVisionExtractor' not in executable_code
