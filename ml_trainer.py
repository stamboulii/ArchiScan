"""
Pipeline d'entrainement ML et inference pour Phase 2-3.
Supporte Donut (document understanding transformer) comme modele principal.
"""

import json
import logging
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from config import ML_MODEL_DIR, ML_CONFIDENCE_THRESHOLD, ensure_directories

logger = logging.getLogger(__name__)


def normalize_parcel_data(raw: dict) -> dict:
    """
    Normalise un dict brut au format ParcelData.
    Fonction standalone pour eviter de coupler MLExtractor a ClaudeVisionExtractor.

    Args:
        raw: Dict brut issu du modele ML ou d'un parser JSON

    Returns:
        Dict conforme a la structure ParcelData
    """
    from architecture_plan_extractor import ParcelData

    parcel = ParcelData()

    parcel.parcelLabel = str(raw.get('parcelLabel', ''))
    parcel.parcelTypeId = str(raw.get('parcelTypeId', 'appartment'))
    parcel.parcelTypeLabel = str(raw.get('parcelTypeLabel', 'appartment'))
    parcel.typology = str(raw.get('typology', ''))
    parcel.floor = str(raw.get('floor', ''))
    parcel.orientation = str(raw.get('orientation', ''))
    parcel.price = str(raw.get('price', 'N.C')) or 'N.C'
    parcel.living_space = str(raw.get('living_space', ''))
    parcel.tva = str(raw.get('tva', ''))
    parcel.pinel = str(raw.get('pinel', ''))
    parcel.state = str(raw.get('state', 'available'))
    parcel.customData = raw.get('customData', None)

    # Surface detail: assurer les valeurs float
    sd = raw.get('surfaceDetail', {})
    if isinstance(sd, dict):
        parcel.surfaceDetail = {}
        for k, v in sd.items():
            if v is not None and v != "" and v != 0:
                try:
                    parcel.surfaceDetail[k] = float(v)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Surface '{k}' ignoree, valeur non convertible: '{v}' ({e})"
                    )

    # Options: assurer les valeurs bool, fusionner avec les defauts
    opts = raw.get('option', {})
    if isinstance(opts, dict):
        for key in parcel.option:
            if key in opts:
                parcel.option[key] = bool(opts[key])

    return asdict(parcel)


class MLExtractor:
    """
    Extracteur base sur un modele ML pour les plans d'architecture.
    Utilise un modele Donut fine-tune.
    """

    def __init__(self, model_path: str = None):
        self.model_dir = Path(model_path) if model_path else ML_MODEL_DIR
        self._model = None
        self._processor = None

    def is_available(self) -> bool:
        """Verifie si un modele entraine existe et peut etre charge."""
        model_config = self.model_dir / "config.json"
        return model_config.exists()

    def _load_model(self):
        """Charge le modele entraine (paresseux)."""
        if self._model is not None:
            return

        if not self.is_available():
            raise RuntimeError(f"Aucun modele entraine trouve dans {self.model_dir}")

        try:
            from transformers import DonutProcessor, VisionEncoderDecoderModel
        except ImportError:
            raise RuntimeError(
                "Les dependances ML ne sont pas installees. "
                "Executez: pip install torch transformers"
            )

        self._processor = DonutProcessor.from_pretrained(str(self.model_dir))
        self._model = VisionEncoderDecoderModel.from_pretrained(str(self.model_dir))
        self._model.eval()
        logger.info(f"Modele ML charge depuis {self.model_dir}")

    def extract_from_image(self, image_path: str, save_preprocessed: bool = True) -> Dict:
        """
        Extrait les donnees en utilisant le modele ML entraine.
        Interface compatible avec ArchitecturePlanExtractor.

        Args:
            image_path: Chemin vers l'image a traiter
            save_preprocessed: Ignore (garde pour compatibilite d'interface)

        Returns:
            Dict conforme a la structure ParcelData

        Raises:
            FileNotFoundError: Si l'image n'existe pas
            RuntimeError: Si le modele n'est pas disponible ou les deps manquent
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image introuvable: {image_path}")

        self._load_model()

        try:
            import torch
            from PIL import Image
        except ImportError:
            raise RuntimeError(
                "Les dependances ML ne sont pas installees. "
                "Executez: pip install torch Pillow"
            )

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as e:
            raise ValueError(f"Impossible d'ouvrir l'image {image_path}: {e}")

        # Preparer l'entree
        pixel_values = self._processor(image, return_tensors="pt").pixel_values

        # Generer
        with torch.no_grad():
            outputs = self._model.generate(
                pixel_values,
                max_length=self._model.decoder.config.max_position_embeddings,
                pad_token_id=self._processor.tokenizer.pad_token_id,
                eos_token_id=self._processor.tokenizer.eos_token_id,
                use_cache=True,
                num_beams=1,
                return_dict_in_generate=True,
                output_scores=True,
            )

        # Decoder
        sequences = outputs.sequences if hasattr(outputs, 'sequences') else outputs
        prediction = self._processor.batch_decode(sequences, skip_special_tokens=True)[0]

        # Calculer la confiance a partir des scores du modele (si disponibles)
        confidence = self._compute_confidence(outputs)

        # Parser le JSON predit
        try:
            result = json.loads(prediction)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{[\s\S]*\}', prediction)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(f"Impossible de parser le JSON du modele ML: {prediction[:200]}")
                    result = {}
            else:
                logger.warning(f"Aucun JSON dans la sortie du modele ML: {prediction[:200]}")
                result = {}

        # Verifier que le resultat n'est pas vide
        if not result or not any(v for k, v in result.items() if k != 'parcelTypeId'):
            logger.warning("Le modele ML n'a produit aucune donnee exploitable")

        # Normaliser au format ParcelData (fonction standalone)
        normalized = normalize_parcel_data(result)

        normalized['_extraction_meta'] = {
            'method': 'ml',
            'confidence': confidence,
            'model_path': str(self.model_dir),
            'raw_prediction_length': len(prediction),
        }

        return normalized

    @staticmethod
    def _compute_confidence(outputs) -> float:
        """
        Calcule un score de confiance a partir des scores de generation.

        Args:
            outputs: Sortie de model.generate() avec output_scores=True

        Returns:
            Score de confiance entre 0.0 et 1.0
        """
        try:
            import torch

            if hasattr(outputs, 'scores') and outputs.scores:
                # Moyenne des probabilites max sur les tokens generes
                all_probs = []
                for score in outputs.scores:
                    probs = torch.softmax(score, dim=-1)
                    max_prob = probs.max(dim=-1).values.mean().item()
                    all_probs.append(max_prob)
                confidence = sum(all_probs) / len(all_probs) if all_probs else ML_CONFIDENCE_THRESHOLD
                return round(min(max(confidence, 0.0), 1.0), 3)
        except Exception as e:
            logger.debug(f"Impossible de calculer la confiance depuis les scores: {e}")

        # Fallback: seuil configurable au lieu d'une valeur magique
        return ML_CONFIDENCE_THRESHOLD

    def extract_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        Traitement par lots, interface compatible.

        Args:
            image_paths: Liste des chemins vers les images

        Returns:
            Dict associant les labels de lots aux donnees extraites
        """
        if not image_paths:
            logger.warning("extract_batch appele avec une liste vide")
            return {}

        results = {}
        for i, path in enumerate(image_paths, 1):
            logger.info(f"ML Batch {i}/{len(image_paths)}: {path}")
            try:
                data = self.extract_from_image(path)
                label = data.get('parcelLabel', f'LOT_{i:03d}')
                results[label] = data
            except FileNotFoundError as e:
                logger.warning(f"Image manquante ignoree: {path} ({e})")
                results[f'MISSING_{i}'] = {"error": str(e), "file": path}
            except Exception as e:
                logger.error(f"Erreur ML pour {path}: {e}")
                results[f'ERROR_{i}'] = {"error": str(e), "file": path}
        return results


class MLTrainer:
    """
    Pipeline d'entrainement pour le modele ML custom.
    Prend les donnees validees depuis TrainingDataStore et fine-tune
    un modele Donut.
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else ML_MODEL_DIR

    def prepare_dataset(self, training_data: List[Dict]) -> tuple:
        """
        Convertit les donnees d'entrainement depuis SQLite au format
        requis pour le fine-tuning Donut.

        Args:
            training_data: Liste depuis TrainingDataStore.get_training_data()

        Returns:
            (train_dataset, val_dataset) comme objets HuggingFace Dataset

        Raises:
            RuntimeError: Si les dependances ML ne sont pas installees
            ValueError: Si pas assez de donnees d'entrainement
        """
        if not training_data:
            raise ValueError("Aucune donnee d'entrainement fournie (liste vide)")

        try:
            from datasets import Dataset
            from sklearn.model_selection import train_test_split
        except ImportError:
            raise RuntimeError(
                "Les dependances ML ne sont pas installees. "
                "Executez: pip install datasets scikit-learn"
            )

        records = []
        skipped = 0
        for item in training_data:
            image_path = item.get('image_path', '')
            if not image_path or not Path(image_path).exists():
                logger.warning(f"Image manquante ignoree: {image_path}")
                skipped += 1
                continue

            target_json = item.get('target_json', '')
            if not target_json:
                logger.warning(f"JSON cible vide pour {image_path}")
                skipped += 1
                continue

            # Valider que le JSON cible est bien forme
            try:
                json.loads(target_json) if isinstance(target_json, str) else target_json
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"JSON cible invalide pour {image_path}")
                skipped += 1
                continue

            records.append({
                'image_path': image_path,
                'target_json': target_json,
            })

        if skipped > 0:
            logger.info(f"Dataset: {len(records)} valides, {skipped} ignores sur {len(training_data)} total")

        if len(records) < 10:
            raise ValueError(
                f"Pas assez de donnees valides pour l'entrainement: {len(records)} "
                f"(minimum requis: 10, recommande: 300+)"
            )

        train_records, val_records = train_test_split(
            records, test_size=0.1, random_state=42
        )

        train_dataset = Dataset.from_list(train_records)
        val_dataset = Dataset.from_list(val_records)

        logger.info(f"Dataset prepare: {len(train_dataset)} train, {len(val_dataset)} val")
        return train_dataset, val_dataset

    def train(self, training_data: List[Dict], epochs: int = 30, batch_size: int = 2):
        """
        Fine-tune un modele Donut sur les donnees collectees.

        Cette methode sera completee quand 300+ echantillons valides
        seront disponibles. Le squelette montre la structure complete.

        Args:
            training_data: Liste depuis TrainingDataStore.get_training_data()
            epochs: Nombre d'epoques d'entrainement
            batch_size: Taille du batch

        Returns:
            Dict avec le statut de l'entrainement

        Raises:
            ValueError: Si les donnees sont insuffisantes
        """
        if not training_data:
            raise ValueError("Aucune donnee d'entrainement fournie")

        logger.info(f"Demarrage de l'entrainement ML avec {len(training_data)} echantillons")

        train_dataset, val_dataset = self.prepare_dataset(training_data)
        logger.info(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}")

        # Structure complete de l'entrainement Donut:
        #
        # 1. Charger le modele pre-entraine (naver-clova-ix/donut-base)
        # 2. Classe dataset custom qui charge les images et le JSON cible
        # 3. HuggingFace Trainer avec configuration appropriee
        # 4. GPU avec au moins 8GB VRAM
        #
        # L'implementation reelle sera ~150 lignes de code standard HuggingFace.

        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Structure du pipeline d'entrainement prete.")
        logger.info(f"Le modele sera sauvegarde dans: {self.output_dir}")

        # Enregistrer le run d'entrainement via le context manager thread-safe
        self._record_training_run(len(training_data))

        return {
            'status': 'pending',
            'samples_used': len(training_data),
            'train_size': len(train_dataset),
            'val_size': len(val_dataset),
            'output_dir': str(self.output_dir),
            'message': (
                "Pipeline d'entrainement configure. "
                "Pour lancer l'entrainement reel, un GPU est necessaire. "
                "Executez: pip install torch transformers datasets scikit-learn"
            )
        }

    def _record_training_run(self, samples_count: int):
        """
        Enregistre un run d'entrainement dans la base de donnees.
        Utilise le context manager thread-safe de TrainingDataStore.

        Args:
            samples_count: Nombre d'echantillons utilises
        """
        try:
            from training_data_store import TrainingDataStore
            store = TrainingDataStore()
            try:
                with store._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO training_runs
                        (samples_used, model_type, model_path, status)
                        VALUES (?, ?, ?, ?)
                    """, (samples_count, 'donut', str(self.output_dir), 'pending'))
            finally:
                store.close()
        except Exception as e:
            logger.warning(f"Impossible d'enregistrer le run d'entrainement: {e}")

    def export_dataset(self, training_data: List[Dict], output_path: str):
        """
        Exporte les donnees d'entrainement dans un format standard
        pour utilisation avec des outils externes.
        Cree un repertoire avec les images et un fichier metadata.json.

        Args:
            training_data: Liste des dicts d'entrainement
            output_path: Chemin du repertoire de sortie

        Returns:
            Dict avec le nombre d'echantillons exportes et le chemin

        Raises:
            ValueError: Si la liste d'entrainement est vide
        """
        if not training_data:
            raise ValueError("Aucune donnee d'entrainement a exporter")

        output = Path(output_path)
        output.mkdir(parents=True, exist_ok=True)
        images_dir = output / "images"
        images_dir.mkdir(exist_ok=True)

        metadata = []
        skipped = 0
        for i, item in enumerate(training_data):
            src = Path(item.get('image_path', ''))
            if not src.exists():
                logger.warning(f"Export: image manquante ignoree: {src}")
                skipped += 1
                continue

            dst = images_dir / f"{i:05d}{src.suffix}"
            try:
                shutil.copy2(str(src), str(dst))
            except (IOError, OSError) as e:
                logger.warning(f"Export: echec copie {src}: {e}")
                skipped += 1
                continue

            metadata.append({
                'file_name': dst.name,
                'target': item.get('target_json', '{}'),
            })

        with open(str(output / "metadata.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(
            f"{len(metadata)} echantillons exportes vers {output_path}"
            + (f" ({skipped} ignores)" if skipped else "")
        )
        return {
            'exported_count': len(metadata),
            'skipped_count': skipped,
            'output_path': str(output),
        }
