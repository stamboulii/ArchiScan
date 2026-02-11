"""
Normalisation des donnees de lots d'architecture.
Fournit des fonctions pour convertir les donnees brutes en format standardise.

Classes:
    ParcelData: Dataclass standard pour les donnees d'un lot

Fonctions:
    normalize_parcel_data: Normalise un dict brut au format ParcelData
    validate_parcel_data: Valide les donnees d'un lot
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration des Options par Defaut
# =============================================================================

DEFAULT_OPTIONS = {
    'garden': False,
    'terrace': False,
    'balcony': False,
    'parking': False,
    'winter garden': False,
    'garage': False,
    'loggia': False,
    'duplex': False,
}


# =============================================================================
# ParcelData - Structure Standard des Donnees d'un Lot
# =============================================================================

@dataclass
class ParcelData:
    """
    Structure de donnees standard pour un lot d'appartement.
    
    Attributes:
        parcelLabel: Reference du lot (ex: A001, B002)
        parcelTypeId: Type de bien (ex: appartment, studio)
        parcelTypeLabel: Label du type (ex: appartement, studio)
        typology: Typologie (ex: T1, T2, T3, F2)
        floor: Etage (ex: RDC, R+1, R+2)
        orientation: Orientation (ex: N, S, E, O, NE, SE)
        price: Prix en euros (ex: 185000, N.C)
        living_space: Surface habitable en m2
        surfaceDetail: Details des surfaces (terrasse, balcon, etc.)
        option: Options du lot (parking, garage, etc.)
        tva: Taux de TVA applicable
        pinel: Eligibility Pinel (oui/non)
        state: Statut du lot (available, reserved, sold)
        customData: Donnees personnalisees
    """
    
    parcelLabel: str = ""
    parcelTypeId: str = "appartment"
    parcelTypeLabel: str = "appartment"
    typology: str = ""
    floor: str = ""
    orientation: str = ""
    price: str = "N.C"
    living_space: str = ""
    surfaceDetail: Dict[str, float] = field(default_factory=dict)
    option: Dict[str, bool] = field(default_factory=lambda: DEFAULT_OPTIONS.copy())
    tva: str = ""
    pinel: str = ""
    state: str = "available"
    customData: Optional[Dict[str, Any]] = None
    
    # Alias pour compatibilite
    @property
    def surface_annexe(self) -> float:
        """Retourne la surface totale annexe (terrasse + balcon + etc.)."""
        return sum(self.surfaceDetail.values())
    
    def to_dict(self, lot_id: str = None) -> Dict:
        """
        Convertit le ParcelData en dict pour serialisation JSON.
        
        Args:
            lot_id: Optionnel, cle du lot dans le dict parent
            
        Returns:
            Dict conforme au format de sortie attendu
        """
        result = asdict(self)
        
        # Nettoyer les valeurs nulles/vides
        if result['living_space'] == '':
            result['living_space'] = None
            
        if not result['surfaceDetail']:
            result['surfaceDetail'] = {}
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ParcelData':
        """
        Cree un ParcelData a partir d'un dict.
        
        Args:
            data: Dict avec les donnees du lot
            
        Returns:
            Instance ParcelData
        """
        return normalize_parcel_data(data)


# =============================================================================
# Fonctions de Normalisation
# =============================================================================

def normalize_parcel_data(raw: Dict) -> Dict:
    """
    Normalise un dict brut au format ParcelData.
    Fonction standalone pour eviter de coupler les modules.
    
    Args:
        raw: Dict brut issu du modele ML ou d'un parser JSON
        
    Returns:
        Dict conforme a la structure ParcelData
    """
    parcel = ParcelData()
    
    # Champs simples (strings)
    parcel.parcelLabel = str(raw.get('parcelLabel', '')).strip()
    parcel.parcelTypeId = str(raw.get('parcelTypeId', 'appartment')).strip()
    parcel.parcelTypeLabel = str(raw.get('parcelTypeLabel', 'appartment')).strip()
    parcel.typology = str(raw.get('typology', '')).strip()
    parcel.floor = str(raw.get('floor', '')).strip()
    parcel.orientation = str(raw.get('orientation', '')).strip()
    
    # Prix avec valeur par defaut
    raw_price = raw.get('price')
    parcel.price = str(raw_price) if raw_price else 'N.C'
    
    # Surface habitable
    parcel.living_space = str(raw.get('living_space', '')).strip()
    
    # Champs optionnels
    parcel.tva = str(raw.get('tva', '')).strip()
    parcel.pinel = str(raw.get('pinel', '')).strip()
    parcel.state = str(raw.get('state', 'available')).strip()
    parcel.customData = raw.get('customData', None)
    
    # Surface detail: assurer les valeurs float
    sd = raw.get('surfaceDetail', {})
    if isinstance(sd, dict):
        normalized_sd = {}
        for k, v in sd.items():
            if v is not None and v != "" and v != 0:
                try:
                    normalized_sd[k] = float(v)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Surface '{k}' ignoree, valeur non convertible: '{v}' ({e})"
                    )
        parcel.surfaceDetail = normalized_sd
    
    # Options: assurer les valeurs bool, fusionner avec les defauts
    opts = raw.get('option', {})
    if isinstance(opts, dict):
        normalized_opts = DEFAULT_OPTIONS.copy()
        for key, value in opts.items():
            normalized_opts[key] = bool(value)
        parcel.option = normalized_opts
    
    return asdict(parcel)


def validate_parcel_data(data: Dict) -> tuple[bool, list]:
    """
    Valide les donnees d'un lot.
    
    Args:
        data: Dict avec les donnees du lot
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Verifier les champs obligatoires
    if not data.get('parcelLabel'):
        errors.append("parcelLabel est requis")
    
    # Verifier la surface
    living_space = data.get('living_space', '')
    if living_space:
        try:
            float(living_space)
        except ValueError:
            errors.append(f"Surface habitable invalide: '{living_space}'")
    
    # Verifier le prix
    price = data.get('price', '')
    if price and price != 'N.C':
        try:
            # Enlever les espaces et caracteres speciaux
            price_clean = ''.join(c for c in str(price) if c.isdigit() or c == '.')
            float(price_clean)
        except ValueError:
            errors.append(f"Prix invalide: '{price}'")
    
    return len(errors) == 0, errors


# =============================================================================
# Mapping et Transformations
# =============================================================================

# Mapping typologie standard
TYPOLOGY_MAP = {
    't1': 'T1', 'f1': 'F1', '1_piece': 'T1', '1 piece': 'T1',
    't2': 'T2', 'f2': 'F2', '2_pieces': 'T2', '2 pieces': 'T2',
    't3': 'T3', 'f3': 'F3', '3_pieces': 'T3', '3 pieces': 'T3',
    't4': 'T4', 'f4': 'F4', '4_pieces': 'T4', '4 pieces': 'T4',
    't5': 'T5', 'f5': 'F5', '5_pieces': 'T5', '5 pieces': 'T5',
    'studio': 'T1',
    'duplex': 'Duplex',
}


def normalize_typology(typology: str) -> str:
    """
    Normalise une typologie au format standard.
    
    Args:
        typology: Typologie brute (ex: "2 pieces", "F3")
        
    Returns:
        Typologie normalisee (ex: "T2")
    """
    if not typology:
        return ""
    
    typology_lower = typology.lower().strip()
    
    # Recherche dans le mapping
    for key, value in TYPOLOGY_MAP.items():
        if key in typology_lower:
            return value
    
    # Retourner la valeur originale si pas de correspondance
    return typology


# Mapping etage standard
FLOOR_MAP = {
    'rdc': 'RDC', 'r.d.c': 'RDC', 'rez-de-chaussee': 'RDC', 'rez de chaussee': 'RDC',
    'r+1': 'R+1', 'r+2': 'R+2', 'r+3': 'R+3',
    'r1': 'R+1', 'r2': 'R+2', 'r3': 'R+3',
    'etage 1': 'R+1', 'etage 2': 'R+2', 'niveau 1': 'R+1',
}


def normalize_floor(floor: str) -> str:
    """
    Normalise un etage au format standard.
    
    Args:
        floor: Etage brut (ex: "Rez-de-chaussee", "R.D.C")
        
    Returns:
        Etage normalise (ex: "RDC")
    """
    if not floor:
        return ""
    
    floor_lower = floor.lower().strip()
    
    # Recherche dans le mapping
    for key, value in FLOOR_MAP.items():
        if key in floor_lower:
            return value
    
    # Retourner la valeur originale
    return floor


# Mapping orientation standard
ORIENTATION_MAP = {
    'nord': 'N', 'north': 'N',
    'sud': 'S', 'south': 'S',
    'est': 'E', 'east': 'E',
    'ouest': 'O', 'west': 'O',
    'ne': 'NE', 'nord-est': 'NE', 'north-east': 'NE',
    'nw': 'NO', 'nord-ouest': 'NO', 'north-west': 'NO',
    'se': 'SE', 'sud-est': 'SE', 'south-east': 'SE',
    'so': 'SO', 'sud-ouest': 'SO', 'south-west': 'SO',
}


def normalize_orientation(orientation: str) -> str:
    """
    Normalise une orientation au format standard.
    
    Args:
        orientation: Orientation brute (ex: "Nord-Est", "NW")
        
    Returns:
        Orientation normalisee (ex: "NE")
    """
    if not orientation:
        return ""
    
    orientation_lower = orientation.lower().strip()
    
    # Recherche dans le mapping
    for key, value in ORIENTATION_MAP.items():
        if key in orientation_lower:
            return value
    
    # Retourner la valeur originale
    return orientation
