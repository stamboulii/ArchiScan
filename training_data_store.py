"""
Collecteur de donnees d'entrainement base sur SQLite.
Stocke les extractions, suit la validation, et surveille la disponibilite
pour l'entrainement ML dans le cadre de la Strategie Hybride Progressive.
"""

import sqlite3
import json
import hashlib
import shutil
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from config import TRAINING_DB_PATH, TRAINING_IMAGES_DIR, MIN_VALIDATED_SAMPLES, ensure_directories

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_hash TEXT NOT NULL,
    image_path TEXT NOT NULL,
    image_stored INTEGER DEFAULT 0,
    extracted_json TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    confidence REAL,
    validated_by_user INTEGER DEFAULT 0,
    user_corrected_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_key TEXT UNIQUE NOT NULL,
    stat_value REAL NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    samples_used INTEGER,
    model_type TEXT,
    model_path TEXT,
    accuracy REAL,
    status TEXT DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_extractions_validated
    ON extractions(validated_by_user);
CREATE INDEX IF NOT EXISTS idx_extractions_method
    ON extractions(extraction_method);
CREATE INDEX IF NOT EXISTS idx_extractions_hash
    ON extractions(image_hash);
"""


class TrainingDataStore:
    """
    Gere la base de donnees SQLite qui accumule les donnees
    d'entrainement de toutes les methodes d'extraction.

    Thread-safe: chaque thread obtient sa propre connexion SQLite
    via threading.local().
    """

    def __init__(self, db_path: str = None):
        ensure_directories()
        self.db_path = db_path or str(TRAINING_DB_PATH)
        self.images_dir = Path(TRAINING_IMAGES_DIR)
        self._local = threading.local()
        self._init_db()

    def _init_db(self):
        """Cree les tables si elles n'existent pas."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    def _get_raw_connection(self) -> sqlite3.Connection:
        """
        Retourne une connexion SQLite thread-local.
        Chaque thread a sa propre connexion, ce qui garantit la thread-safety.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            # Activer le WAL mode pour de meilleures perfs en concurrent
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    @contextmanager
    def _get_connection(self):
        """
        Context manager pour les operations base de donnees.
        Gere automatiquement le commit/rollback.

        Usage:
            with self._get_connection() as conn:
                conn.execute("INSERT ...")
        """
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _connect(self) -> sqlite3.Connection:
        """
        Cree une nouvelle connexion a la base de donnees.
        DEPRECATED: Utiliser _get_connection() a la place.
        Conserve pour compatibilite avec le code existant.
        """
        return self._get_raw_connection()

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Calcule le hash SHA256 d'un fichier."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def save_extraction(
        self,
        image_path: str,
        extracted_data: Dict,
        method: str,
        confidence: float = None,
        store_image: bool = True,
    ) -> int:
        """
        Sauvegarde un resultat d'extraction dans la base de donnees.

        Args:
            image_path: Chemin vers l'image source
            extracted_data: Le dictionnaire ParcelData extrait
            method: 'claude', 'tesseract', ou 'ml'
            confidence: Score de confiance optionnel (0.0-1.0)
            store_image: Si True, copie l'image dans training_images/

        Returns:
            L'ID de la ligne sauvegardee

        Raises:
            FileNotFoundError: Si l'image source n'existe pas
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image source introuvable: {image_path}")

        image_hash = self._hash_file(image_path)

        # Retirer _extraction_meta avant stockage
        clean_data = {k: v for k, v in extracted_data.items()
                      if not k.startswith('_')}
        extracted_json = json.dumps(clean_data, ensure_ascii=False)

        # Copie de l'image pour l'entrainement
        image_stored = 0
        if store_image:
            dest = self.images_dir / f"{image_hash}{Path(image_path).suffix}"
            if not dest.exists():
                try:
                    shutil.copy2(image_path, str(dest))
                    image_stored = 1
                except (IOError, OSError) as e:
                    logger.warning(f"Echec de la copie de l'image d'entrainement: {e}")
                    image_stored = 0
            else:
                image_stored = 1

        # Insertion en base avec rollback automatique
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO extractions
                (image_hash, image_path, image_stored, extracted_json,
                 extraction_method, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (image_hash, image_path, image_stored, extracted_json,
                  method, confidence))
            row_id = cursor.lastrowid

        self._update_statistics()
        logger.info(f"Extraction #{row_id} sauvegardee ({method}, conf={confidence})")
        return row_id

    def validate_extraction(
        self,
        extraction_id: int,
        corrected_data: Dict = None
    ):
        """
        Marque une extraction comme validee par l'utilisateur.
        Optionnellement stocke la version corrigee.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if corrected_data:
                clean = {k: v for k, v in corrected_data.items()
                         if not k.startswith('_')}
                corrected_json = json.dumps(clean, ensure_ascii=False)
                cursor.execute("""
                    UPDATE extractions
                    SET validated_by_user = 1,
                        user_corrected_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (corrected_json, extraction_id))
            else:
                cursor.execute("""
                    UPDATE extractions
                    SET validated_by_user = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (extraction_id,))

            if cursor.rowcount == 0:
                logger.warning(f"Extraction #{extraction_id} introuvable pour validation")

        self._update_statistics()
        logger.info(f"Extraction #{extraction_id} validee")

    def get_training_data(self, validated_only: bool = True) -> List[Dict]:
        """
        Recupere les donnees d'entrainement pour le modele ML.

        Returns:
            Liste de dicts avec image_path et target_json
        """
        conn = self._get_raw_connection()
        cursor = conn.cursor()

        if validated_only:
            cursor.execute("""
                SELECT image_hash, image_path, extracted_json,
                       user_corrected_json, extraction_method
                FROM extractions
                WHERE validated_by_user = 1
                ORDER BY created_at
            """)
        else:
            cursor.execute("""
                SELECT image_hash, image_path, extracted_json,
                       user_corrected_json, extraction_method
                FROM extractions
                ORDER BY created_at
            """)

        rows = cursor.fetchall()

        results = []
        for row in rows:
            target = row['user_corrected_json'] or row['extracted_json']

            # Valider que le JSON cible est bien forme
            try:
                json.loads(target)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"JSON invalide dans extraction (hash={row['image_hash'][:12]}...): {e}"
                )
                continue

            image_file = self.images_dir / f"{row['image_hash']}{Path(row['image_path']).suffix}"

            if not image_file.exists():
                logger.debug(f"Image d'entrainement manquante: {image_file}")

            results.append({
                'image_path': str(image_file) if image_file.exists() else row['image_path'],
                'target_json': target,
                'source_method': row['extraction_method'],
            })

        return results

    def get_statistics(self) -> Dict:
        """
        Obtient les statistiques actuelles de la collecte de donnees.
        """
        conn = self._get_raw_connection()
        cursor = conn.cursor()

        stats = {}
        cursor.execute("SELECT COUNT(*) FROM extractions")
        stats['total_extractions'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM extractions WHERE validated_by_user = 1")
        stats['validated_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM extractions WHERE extraction_method = 'claude'")
        stats['claude_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM extractions WHERE extraction_method = 'tesseract'")
        stats['tesseract_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM extractions WHERE extraction_method = 'ml'")
        stats['ml_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(confidence) FROM extractions WHERE confidence IS NOT NULL")
        avg_conf_result = cursor.fetchone()[0]
        stats['average_confidence'] = round(float(avg_conf_result), 3) if avg_conf_result is not None else 0.0

        stats['min_samples_needed'] = MIN_VALIDATED_SAMPLES
        stats['ready_for_training'] = stats['validated_count'] >= MIN_VALIDATED_SAMPLES

        # Protection contre division par zero
        if MIN_VALIDATED_SAMPLES > 0:
            stats['progress_percent'] = min(100, round(
                stats['validated_count'] / MIN_VALIDATED_SAMPLES * 100, 1
            ))
        else:
            stats['progress_percent'] = 100.0 if stats['validated_count'] > 0 else 0.0

        return stats

    def get_recent_extractions(self, limit: int = 20) -> List[Dict]:
        """Recupere les extractions les plus recentes pour l'affichage UI."""
        conn = self._get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, image_path, extraction_method, confidence,
                   validated_by_user, created_at
            FROM extractions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_extraction_by_id(self, extraction_id: int) -> Optional[Dict]:
        """Recupere une extraction par son ID."""
        conn = self._get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, image_path, extracted_json, extraction_method,
                   confidence, validated_by_user, user_corrected_json, created_at
            FROM extractions
            WHERE id = ?
        """, (extraction_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _update_statistics(self):
        """Met a jour la table de statistiques."""
        try:
            stats = self.get_statistics()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for key, value in stats.items():
                    if isinstance(value, (int, float, bool)):
                        cursor.execute("""
                            INSERT INTO statistics (stat_key, stat_value, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(stat_key)
                            DO UPDATE SET stat_value = ?, updated_at = CURRENT_TIMESTAMP
                        """, (key, float(value), float(value)))
        except Exception as e:
            logger.warning(f"Erreur mise a jour statistiques: {e}")

    def close(self):
        """Ferme la connexion thread-local si elle existe."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
