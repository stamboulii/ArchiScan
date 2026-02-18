"""
Claude Extractor - Claude Vision API
===================================

Extracteur utilisant l'API Claude Vision d'Anthropic.
Phase 1 de la strategie hybride.

Ce module est un wrapper qui utilise claude_vision_extractor.py
tout en integrant les nouveaux composants.
"""

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from ..core.config import (
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    TEMP_DIR,
    ensure_directories,
    get_secrets_manager,
)
from ..core.parcel import normalize_parcel_data
from ..core.exceptions import (
    ClaudeAPIError,
    APIResponseError,
    NoJSONFoundError,
    ExtractionError,
)

logger = logging.getLogger(__name__)

# Configuration du retry
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0


def encode_image(image_path: str) -> tuple:
    """Lit et encode une image en base64."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    
    media_type_map = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/png',
    }
    media_type = media_type_map.get(suffix, 'image/png')
    
    with open(image_path, 'rb') as f:
        base64_data = base64.b64encode(f.read()).decode('utf-8')
    
    return base64_data, media_type


class ClaudeVisionExtractor:
    """
    Extracteur utilisant l'API Claude Vision d'Anthropic.
    Haute precision pour les plans d'architecture.
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Args:
            api_key: Cle API Anthropic. Si None, utilise SecretsManager.
            model: Identifiant du modele Claude.
        """
        self._api_key_override = api_key
        self.model = model or CLAUDE_MODEL
        self.max_tokens = CLAUDE_MAX_TOKENS
        self._client = None
        self._secrets = get_secrets_manager()
    
    @property
    def api_key(self) -> str:
        """Recupere la cle API (SecretsManager ou override)."""
        if self._api_key_override:
            return self._api_key_override
        return self._secrets.get_claude_api_key()
    
    @property
    def client(self):
        """Initialise le client Anthropic."""
        if self._client is None:
            if not self.api_key:
                raise ClaudeAPIError(
                    "Pas de cle API Anthropic configuree. "
                    "Definissez ARCHI_CLAUDE_API_KEY dans votre fichier .env"
                )
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        return self._client
    
    def is_available(self) -> bool:
        """Verifie si Claude Vision est disponible (cle et credits valides)."""
        # Priorite a la cle saisie dans l'UI
        if self._api_key_override:
            # Tester si l'API est reellement accessible (pas d'erreur de credits)
            try:
                # Faire un petit test API pour verifier les credits
                test_response = self._make_test_api_call()
                return True
            except Exception as e:
                error_str = str(e).lower()
                if 'credit' in error_str or 'billing' in error_str or 'balance' in error_str:
                    logger.warning(f"Claude API non disponible: credits insuffisants")
                    return False
                # Autres erreurs (reseau, etc.) - considerer comme disponible temporairement
                logger.warning(f"Claude API indisponible temporairement: {e}")
                return False
        
        # Sinon, verifier SecretsManager
        try:
            self._secrets.validate_all_secrets('claude')
            # Tester aussi les credits
            try:
                test_response = self._make_test_api_call()
                return True
            except Exception as e:
                error_str = str(e).lower()
                if 'credit' in error_str or 'billing' in error_str or 'balance' in error_str:
                    logger.warning(f"Claude API: credits insuffisants")
                    return False
                return False
        except ValueError:
            return False
    
    def _make_test_api_call(self) -> bool:
        """Fait un appel test pour verifier les credits API."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "test"}]
            }
        ]
        # Utiliser un token unique pour le test
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1,
            messages=messages,
        )
        return True
    
    def _call_api_with_retry(self, messages: list) -> object:
        """Appelle l'API Claude avec retry et backoff exponentiel."""
        last_error = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=messages,
                )
                
                if not message.content or len(message.content) == 0:
                    raise APIResponseError("Reponse API vide")
                
                return message
            
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                is_retryable = any(x in error_msg.lower() for x in [
                    'rate_limit', 'overloaded', 'timeout', '500', '502', '503', '529'
                ])
                
                if is_retryable and attempt < MAX_RETRIES:
                    delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                    logger.warning(f"Tentative {attempt}/{MAX_RETRIES} echouee. Retry dans {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    raise
        
        raise ClaudeAPIError(f"Echec apres {MAX_RETRIES} tentatives: {last_error}")
    
    def _extract_json_from_response(self, text: str) -> Dict:
        """Extrait le JSON de la reponse Claude."""
        # Essayer de parser directement
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Chercher un bloc JSON dans le texte
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, text)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                raise NoJSONFoundError(text)
        
        raise NoJSONFoundError(text)
    
    def extract(self, image_path: str) -> Dict:
        """
        Extrait les donnees d'un plan d'architecture.
        
        Args:
            image_path: Chemin vers l'image du plan
            
        Returns:
            Dict avec les donnees extraites
        """
        if not Path(image_path).exists():
            raise ExtractionError(f"Fichier introuvable: {image_path}")
        
        # Verifier la disponibilite
        if not self.is_available():
            raise ClaudeAPIError("Claude Vision n'est pas disponible")
        
        # Encoder l'image
        base64_data, media_type = encode_image(image_path)
        
        if len(base64_data) == 0:
            raise ExtractionError(f"Fichier image vide: {image_path}")
        
        # Verifier les dimensions
        from PIL import Image
        img = Image.open(image_path)
        if img.width == 0 or img.height == 0:
            raise ExtractionError(f"Dimensions d'image invalides: {img.width}x{img.height}")
        
        # Preparer le message
        prompt = """Analyse ce plan d'architecture et extrais les informations du lot au format JSON:
        - parcelLabel: Reference du lot (ex: A001)
        - typology: Typologie (T1, T2, T3, etc.)
        - floor: Etage (RDC, R+1, etc.)
        - orientation: Orientation (N, S, E, O, NE, SE, NO, SO)
        - living_space: Surface habitable en m2
        - surfaceDetail: Details des surfaces (terrasse, balcon, jardin en m2)
        - option: Options presentes (parking, garage, etc.)
        - price: Prix si disponible
        - state: Statut (available, reserved, sold)
        
        Retourne uniquement le JSON, sans texte supplementaire."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        # Appel API
        response = self._call_api_with_retry(messages)
        raw_text = response.content[0].text
        
        # Extraction JSON
        raw_data = self._extract_json_from_response(raw_text)
        
        # Normalisation
        normalized = normalize_parcel_data(raw_data)
        
        # Ajouter le texte brut pour l'interface debug
        normalized['_raw_text'] = raw_text if raw_text else ""
        
        logger.info(f"Extraction Claude terminee: {normalized.get('parcelLabel', 'Inconnu')}")
        
        return normalized


# Backward compatibility alias
ClaudeExtractor = ClaudeVisionExtractor


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python -m archiextract.extractors.claude_extractor <image_path>")
        sys.exit(1)
    
    extractor = ClaudeVisionExtractor()
    result = extractor.extract(sys.argv[1])
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
