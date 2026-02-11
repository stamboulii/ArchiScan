"""
Extracteur Claude Vision API pour les plans d'architecture.
Phase 1 de la Strategie Hybride Progressive.
"""

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from config import (
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
    TEMP_DIR, ensure_directories,
    get_secrets_manager
)

logger = logging.getLogger(__name__)

# Configuration du retry
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # secondes
RETRY_MAX_DELAY = 30.0  # secondes


def convert_pdf_to_images(pdf_path: str, dpi: int = 150) -> List[str]:
    """
    Convertit un fichier PDF en images individuelles par page.
    Utilise PyMuPDF (fitz) avec compression pour reduire la taille.

    Args:
        pdf_path: Chemin vers le fichier PDF
        dpi: Resolution en DPI pour le rendu (150 par defaut pour taille reduite)

    Returns:
        Liste des chemins vers les images generees
    """
    import traceback
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) n'est pas installe. Installez-le avec: pip install PyMuPDF")
        return []

    # Verifier le chemin
    logger.info(f"Tentative d'ouverture du PDF: {pdf_path}")
    
    if not Path(pdf_path).exists():
        logger.error(f"Fichier PDF introuvable: {pdf_path}")
        abs_path = Path(pdf_path).resolve()
        logger.info(f"Essai avec chemin absolu: {abs_path}")
        if abs_path.exists():
            pdf_path = str(abs_path)
        else:
            logger.error(f"Fichier PDF non trouve meme avec le chemin absolu")
            return []

    # Verifier la taille du fichier
    file_size = Path(pdf_path).stat().st_size
    logger.info(f"Taille du PDF: {file_size / (1024*1024):.2f} MB")

    ensure_directories()
    doc = None
    image_paths = []

    try:
        logger.info(f"Ouverture du PDF avec PyMuPDF...")
        doc = fitz.open(pdf_path)
        logger.info(f"PDF ouvert: {len(doc)} pages")

        for page_num in range(len(doc)):
            try:
                page = doc.load_page(page_num)
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # Utiliser JPEG avec compression
                output_path = TEMP_DIR / f"pdf_page_{page_num + 1}.jpg"
                pix.save(str(output_path), jpegquality=85)
                
                file_size_kb = output_path.stat().st_size / 1024
                logger.info(f"Page {page_num + 1} generee: {file_size_kb:.1f} KB")
                
                image_paths.append(str(output_path))
            except Exception as page_error:
                logger.error(f"Erreur page {page_num + 1}: {page_error}")
                continue

    except Exception as e:
        logger.error(f"Erreur lors de la conversion PDF '{pdf_path}': {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if doc:
            doc.close()

    if not image_paths:
        logger.error(f"Aucune page n'a pu etre extraite du PDF")
    else:
        logger.info(f"Conversion terminee: {len(image_paths)} pages")
    
    return image_paths


class ClaudeVisionExtractor:
    """
    Extrait les donnees de lots a partir d'images de plans d'architecture
    en utilisant l'API Claude Vision d'Anthropic.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Args:
            api_key: Cle API Anthropic. Si None, lit depuis SecretsManager securise.
            model: Identifiant du modele Claude. Par defaut depuis config.
        """
        self._api_key_override = api_key  # Pour compatibilite retour
        self.model = model or CLAUDE_MODEL
        self.max_tokens = CLAUDE_MAX_TOKENS
        self._client = None
        self._secrets = get_secrets_manager()
    
    @property
    def api_key(self) -> str:
        """Recupere la cle API (depuis SecretsManager ou override)."""
        if self._api_key_override:
            return self._api_key_override
        return self._secrets.get_claude_api_key()

    @property
    def client(self):
        """Initialise le client Anthropic de maniere paresseuse."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Pas de cle API Anthropic configuree. "
                    "Definissez la variable d'environnement ANTHROPIC_API_KEY "
                    "ou passez le parametre api_key."
                )
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def _call_api_with_retry(self, messages: list) -> object:
        """
        Appelle l'API Claude avec retry et backoff exponentiel.
        Gere les erreurs de rate limit, timeout et reseau.

        Args:
            messages: Liste des messages a envoyer a l'API

        Returns:
            Objet message de reponse de l'API

        Raises:
            Exception: Si toutes les tentatives echouent
        """
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=messages,
                )

                # Validation de la reponse
                if not message.content or len(message.content) == 0:
                    raise ValueError("Reponse API vide: aucun contenu retourne")

                return message

            except ValueError:
                # Pas de retry pour les erreurs de validation
                raise

            except Exception as e:
                last_error = e
                error_name = type(e).__name__
                error_msg = str(e)

                # Detecter les erreurs recuperables
                is_rate_limit = 'rate_limit' in error_msg.lower() or '429' in error_msg
                is_overloaded = 'overloaded' in error_msg.lower() or '529' in error_msg
                is_timeout = 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower()
                is_server_error = '500' in error_msg or '502' in error_msg or '503' in error_msg

                is_retryable = is_rate_limit or is_overloaded or is_timeout or is_server_error

                if is_retryable and attempt < MAX_RETRIES:
                    # Backoff exponentiel avec jitter
                    delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                    logger.warning(
                        f"Tentative {attempt}/{MAX_RETRIES} echouee ({error_name}: {error_msg}). "
                        f"Nouvelle tentative dans {delay:.1f}s..."
                    )
                    time.sleep(delay)
                elif not is_retryable:
                    # Erreur non recuperable (auth, format, etc.)
                    logger.error(f"Erreur API non recuperable ({error_name}): {error_msg}")
                    raise
                else:
                    logger.error(
                        f"Tentative {attempt}/{MAX_RETRIES} echouee ({error_name}): {error_msg}. "
                        f"Toutes les tentatives epuisees."
                    )

        raise RuntimeError(
            f"Echec apres {MAX_RETRIES} tentatives. Derniere erreur: {last_error}"
        )

    def is_available(self) -> bool:
        """Verifie si Claude Vision est disponible (cle UI ou SecretsManager)."""
        # Priorite a la cle saisie dans l'UI
        if self._api_key_override:
            return True
        
        # Sinon, verifier SecretsManager
        try:
            self._secrets.validate_all_secrets('claude')
            return True
        except ValueError:
            return False

    def _encode_image(self, image_path: str) -> tuple:
        """
        Lit et encode en base64 un fichier image ou PDF.
        Compresse automatiquement si necessaire pour respecter la limite Claude API (5MB).

        Args:
            image_path: Chemin vers l'image ou le PDF

        Returns:
            (base64_data, media_type)
        """
        path = Path(image_path)
        suffix = path.suffix.lower()
        
        # Verifier si c'est un PDF
        if suffix == '.pdf':
            return self._encode_pdf(image_path)
        
        # Pour les images
        media_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/png',
        }
        media_type = media_type_map.get(suffix, 'image/png')

        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {image_path}")

        with open(image_path, 'rb') as f:
            raw_data = f.read()

        file_size = len(raw_data)
        logger.info(f"Taille fichier: {file_size / (1024*1024):.2f} MB")

        if file_size == 0:
            raise ValueError(f"Fichier vide: {image_path}")

        # Compresser si l'image est trop grande (> 2MB)
        max_size = 5 * 1024 * 1024  # 5MB limite Claude API

        if file_size > 2 * 1024 * 1024:
            logger.warning(f"Fichier trop grand ({file_size / (1024*1024):.2f}MB), compression necessaire")

            try:
                from PIL import Image as PILImage
                import io
                img = PILImage.open(image_path)

                if img.width == 0 or img.height == 0:
                    raise ValueError(f"Dimensions invalides: {img.width}x{img.height}")

                # Reduction progressive
                max_dim = 2048
                ratio = min(max_dim / img.width, max_dim / img.height)
                if ratio < 1:
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, PILImage.LANCZOS)
                    logger.info(f"Redimensionne a: {new_size}")

                # Compression JPEG
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85, optimize=True)
                compressed_data = buf.getvalue()

                # Si toujours trop gros, reduire qualite
                if len(compressed_data) > max_size:
                    logger.warning(f"Encore trop gros, reduction supplementaire")
                    buf2 = io.BytesIO()
                    img.save(buf2, format='JPEG', quality=60, optimize=True)
                    compressed_data = buf2.getvalue()

                raw_data = compressed_data
                media_type = 'image/jpeg'
                logger.info(f"Apres compression: {len(raw_data) / (1024*1024):.2f} MB")

            except Exception as e:
                logger.error(f"Erreur compression: {e}")
                raise ValueError(f"Impossible de compresser le fichier: {e}")

        image_data = base64.b64encode(raw_data).decode('utf-8')
        return image_data, media_type
    
    def _encode_pdf(self, pdf_path: str) -> tuple:
        """
        Convertit un PDF en image JPEG pour Claude API.
        Claude Vision ne supporte pas les PDFs directement.

        Returns:
            (base64_data, media_type)
        """
        import io
        
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF introuvable: {pdf_path}")

        try:
            import fitz
        except ImportError:
            raise ValueError("PyMuPDF (fitz) requis pour convertir les PDFs")

        logger.info(f"Conversion PDF en image: {pdf_path}")
        
        # Ouvrir le PDF
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            raise ValueError("PDF vide")
        
        # Convertir la premiere page en image
        page = doc.load_page(0)
        zoom = 2.0  # Haute qualite
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        doc.close()
        
        # Convertir en image JPEG
        img_data = pix.tobytes("jpeg")
        file_size = len(img_data)
        logger.info(f"PDF converti: {file_size / 1024:.1f} KB")
        
        # Compresser si trop grand (> 4MB)
        max_size = 4 * 1024 * 1024
        if file_size > max_size:
            logger.warning(f"Image trop grande, compression supplementaire")
            
            from PIL import Image as PILImage
            img = PILImage.open(io.BytesIO(img_data))
            
            # Reduire la taille
            max_dim = 2048
            ratio = min(max_dim / img.width, max_dim / img.height)
            if ratio < 1:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, PILImage.LANCZOS)
            
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80, optimize=True)
            img_data = buf.getvalue()
            logger.info(f"Apres compression: {len(img_data) / 1024:.1f} KB")
        
        image_data = base64.b64encode(img_data).decode('utf-8')
        return image_data, 'image/jpeg'

    def _build_extraction_prompt(self) -> str:
        """
        Construit le prompt structure qui demande a Claude
        d'extraire les donnees de lots du plan.
        """
        return """Tu es un expert en extraction de donnees a partir de plans d'architecture immobiliers francais (plans de vente, plans de commercialisation).

Analyse cette image de plan d'architecture et extrais TOUTES les informations suivantes au format JSON.

INSTRUCTIONS CRITIQUES:
1. Extrais CHAQUE lot/appartement visible sur le plan comme un objet separe
2. Si une information n'est pas visible, utilise "" pour les strings et "N.C" pour le prix
3. Les surfaces doivent etre des nombres (pas de texte)
4. Cherche dans les cartouches, les legendes, les tableaux et annotations

CHAMPS A EXTRAIRE pour chaque lot:
- parcelLabel: reference du lot (ex: "A001", "B102", "LOT 23")
- typology: type T1, T2, T3, T4, T5, T6 ou F1, F2, etc.
- floor: etage - "RDC" pour rez-de-chaussee, "R+1", "R+2", etc., ou "Etage 1", etc.
- orientation: une ou plusieurs lettres parmi N, S, E, O (Nord, Sud, Est, Ouest)
- price: prix en euros (nombre pur sans symbole, ex: "185000") ou "N.C" si non communique
- living_space: surface habitable en m2 (nombre, ex: "41.72")
- surfaceDetail: objet avec les surfaces annexes en m2 :
  - "terrace": surface terrasse
  - "balcony": surface balcon
  - "garden": surface jardin
  - "loggia": surface loggia
  (uniquement les surfaces qui existent)
- option: objet booleen pour la presence de:
  - "garden": jardin
  - "terrace": terrasse
  - "balcony": balcon
  - "parking": parking/stationnement
  - "winter garden": jardin d'hiver
  - "garage": garage/box
  - "loggia": loggia
  - "duplex": duplex
- tva: taux TVA si mentionne (ex: "5.5", "20", "reduite")
- pinel: eligibilite Pinel si mentionnee ("eligible", "")
- state: etat du lot ("available", "reserved", "sold") si visible

REPONDS UNIQUEMENT avec un JSON valide au format suivant (pas de texte avant ou apres):
{
  "parcels": [
    {
      "parcelLabel": "...",
      "parcelTypeId": "appartment",
      "parcelTypeLabel": "appartment",
      "typology": "...",
      "floor": "...",
      "orientation": "...",
      "price": "...",
      "living_space": "...",
      "surfaceDetail": {},
      "option": {
        "garden": false,
        "terrace": false,
        "balcony": false,
        "parking": false,
        "winter garden": false,
        "garage": false,
        "loggia": false,
        "duplex": false
      },
      "tva": "",
      "pinel": "",
      "customData": null,
      "state": "available"
    }
  ],
  "confidence": 0.95,
  "notes": "observations sur la qualite de l'image ou les donnees manquantes"
}"""

    def _parse_claude_response(self, response_text: str) -> dict:
        """
        Parse la reponse de Claude en donnees structurees.
        Gere les problemes potentiels de formatage JSON.
        """
        text = response_text.strip()

        # Retirer les balises de code markdown si presentes
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:])
            if text.endswith('```'):
                text = text[:-3].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Echec du parsing JSON direct: {e}")
            # Tenter de trouver le JSON dans le texte
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Impossible de parser la reponse Claude comme JSON: {text[:200]}"
                    )
            else:
                raise ValueError(
                    f"Aucun JSON trouve dans la reponse Claude: {text[:200]}"
                )

        return data

    def _normalize_parcel(self, raw: dict) -> dict:
        """
        Normalise un dict brut de Claude au format ParcelData.
        Assure que tous les champs requis existent avec les bons types.
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

    def extract_from_image(self, image_path: str, save_preprocessed: bool = True) -> Dict:
        """
        Extrait les donnees de lot d'une seule image de plan.
        Interface compatible avec ArchitecturePlanExtractor.

        Args:
            image_path: Chemin vers le fichier image
            save_preprocessed: Ignore (garde pour compatibilite d'interface)

        Returns:
            Dict correspondant a la structure ParcelData
        """
        logger.info(f"Extraction avec Claude Vision: {image_path}")

        image_data, media_type = self._encode_image(image_path)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": self._build_extraction_prompt(),
                    },
                ],
            }
        ]

        message = self._call_api_with_retry(messages)

        response_text = message.content[0].text
        parsed = self._parse_claude_response(response_text)

        confidence = parsed.get('confidence', 0.95)
        parcels = parsed.get('parcels', [])

        if len(parcels) == 0:
            logger.warning("Claude n'a retourne aucun lot")
            from architecture_plan_extractor import ParcelData
            result = asdict(ParcelData())
            result['_extraction_meta'] = {
                'method': 'claude',
                'confidence': 0.0,
                'success': False,
                'notes': parsed.get('notes', 'Aucun lot detecte dans l\'image'),
                'raw_response': response_text[:1000]
            }
            return result

        # Retourner le premier lot (compatibilite interface single-parcel)
        result = self._normalize_parcel(parcels[0])
        result['_extraction_meta'] = {
            'method': 'claude',
            'confidence': confidence,
            'notes': parsed.get('notes', ''),
            'total_parcels_found': len(parcels),
            'model_used': self.model,
            'input_tokens': message.usage.input_tokens,
            'output_tokens': message.usage.output_tokens,
        }

        return result

    def extract_all_parcels(self, image_path: str) -> List[Dict]:
        """
        Extrait TOUS les lots d'une image (peut contenir plusieurs lots).

        Returns:
            Liste de dicts ParcelData
        """
        logger.info(f"Extraction de tous les lots avec Claude Vision: {image_path}")

        image_data, media_type = self._encode_image(image_path)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": self._build_extraction_prompt(),
                    },
                ],
            }
        ]

        message = self._call_api_with_retry(messages)

        response_text = message.content[0].text
        parsed = self._parse_claude_response(response_text)
        parcels = parsed.get('parcels', [])
        confidence = parsed.get('confidence', 0.95)

        results = []
        for raw_parcel in parcels:
            normalized = self._normalize_parcel(raw_parcel)
            normalized['_extraction_meta'] = {
                'method': 'claude',
                'confidence': confidence,
                'model_used': self.model,
            }
            results.append(normalized)

        return results

    def extract_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        Traite plusieurs images. Compatible avec ArchitecturePlanExtractor.

        Args:
            image_paths: Liste des chemins vers les images

        Returns:
            Dict associant les labels de lots aux donnees extraites
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
