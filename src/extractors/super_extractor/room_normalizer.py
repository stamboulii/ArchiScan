"""
Room Normalizer - Normalisation intelligente des noms de pièces
Clé: Réception est DISTINCT de Séjour (ne fusionne plus)
"""

import re
import logging
from typing import Tuple, Optional

from .models import RoomType

logger = logging.getLogger(__name__)


class RoomNormalizer:

    # (pattern, name_template, RoomType, is_exterior)
    # Ordre: composites et spécifiques EN PREMIER
    ROOM_ALIASES = [
        # === Composites ===
        (r"^(SEJOUR|S[ÉE]JOUR|SALON|RECEPTION|R[ÉE]CEPTION)\s*/?\s*CUISINE",
         "sejour_cuisine", RoomType.LIVING_KITCHEN, False),
        (r"^CUISINE\s*/?\s*(SEJOUR|S[ÉE]JOUR|SALON)",
         "sejour_cuisine", RoomType.LIVING_KITCHEN, False),
        (r"^PI[ÈE]CE\s*(DE\s*VIE|PRINCIPALE)",
         "sejour_cuisine", RoomType.LIVING_KITCHEN, False),

        # === Réception (DISTINCT de séjour) ===
        (r"^(RECEPTION|R[ÉE]CEPTION)$",
         "reception", RoomType.RECEPTION, False),

        # === Séjour / Salon ===
        (r"^(SEJOUR|S[ÉE]JOUR|SALON|LIVING|DOUBLE\s*SEJOUR)$",
         "sejour", RoomType.LIVING_ROOM, False),

        # === Cuisine ===
        (r"^(CUISINE|KITCHENETTE|COIN\s*CUISINE)$",
         "cuisine", RoomType.KITCHEN, False),

        # === Entrée ===
        (r"^(ENTREE|ENTR[ÉE]E|HALL\s*D['\u2019]?ENTREE|HALL|VESTIBULE)$",
         "entree", RoomType.ENTRY, False),
        (r"^(DGT|D\.G\.T\.?|D[ÉE]GAGEMENT|COULOIR|PALIER|CIRCULATION)$",
         "circulation", RoomType.CIRCULATION, False),

        # === Chambres ===
        (r"^CHAMBRE\s*(\d+)$", "chambre_{n}", RoomType.BEDROOM, False),
        (r"^CHAMBRE$", "chambre", RoomType.BEDROOM, False),
        (r"^CH\.?\s*(\d+)$", "chambre_{n}", RoomType.BEDROOM, False),
        (r"^SUITE\s*PARENTALE\s*(\d*)$", "chambre_{n}", RoomType.BEDROOM, False),

        # === Salle de bain ===
        (r"^(SALLE\s*DE\s*BAINS?|SDB|S\.?\s*D\.?\s*B\.?)$",
         "salle_de_bain", RoomType.BATHROOM, False),
        (r"^(SALLE\s*DE\s*BAINS?|SDB|S\.?\s*D\.?\s*B\.?)\s*(\d+)$",
         "salle_de_bain_{n}", RoomType.BATHROOM, False),

        # === Salle d'eau ===
        (r"^(SALLE\s*D['\u2019]?\s*EAU|SDE|S\.?\s*D\.?\s*E\.?)$",
         "salle_d_eau", RoomType.SHOWER_ROOM, False),

        # === WC ===
        (r"^(WC|W\.?\s*C\.?|TOILETT?E?S?)$", "wc", RoomType.WC, False),
        (r"^(RGT\s*WC|RGT\s*W\.?\s*C\.?)$", "wc", RoomType.WC, False),

        # === Rangements ===
        (r"^(DRESSING\s*\d*)$", "dressing", RoomType.DRESSING, False),
        (r"^(PLACARD|CELLIER|BUANDERIE|LINGERIE|RANGEMENT|RGT)$",
         "storage", RoomType.STORAGE, False),

        # === Extérieur ===
        (r"^BALCON\s*(\d*)$", "balcon", RoomType.BALCONY, True),
        (r"^TERRASSE\s*(\d*)$", "terrasse", RoomType.TERRACE, True),
        (r"^(JARDIN|JARDINET)\s*(\d*)$", "jardin", RoomType.GARDEN, True),
        (r"^LOGGIA\s*(\d*)$", "loggia", RoomType.LOGGIA, True),
        (r"^(PARKING|GARAGE|BOX|STATIONNEMENT)\s*(\d*)$",
         "parking", RoomType.PARKING, True),
        (r"^CAVE\s*(\d*)$", "cave", RoomType.CELLAR, True),
    ]

    def __init__(self):
        self._seen_names = {}

    def reset(self):
        """Reset entre deux extractions"""
        self._seen_names = {}

    def normalize(self, name_raw: str) -> Tuple[Optional[str], Optional[RoomType], Optional[int], bool, float]:
        """
        Returns: (name_normalized, room_type, room_number, is_exterior, confidence)
        Returns (None, None, None, False, 0.0) si non reconnu
        """
        name_clean = re.sub(r"\s+", " ", name_raw.strip().upper())

        for pattern, name_template, room_type, is_exterior in self.ROOM_ALIASES:
            match = re.match(pattern, name_clean, re.IGNORECASE)
            if match:
                # Extraire numéro si présent
                number = None
                for g in match.groups():
                    if g and g.isdigit():
                        number = int(g)
                        break

                # Construire nom normalisé
                if "{n}" in name_template:
                    if number:
                        norm_name = name_template.replace("{n}", str(number))
                    else:
                        norm_name = name_template.replace("_{n}", "")
                else:
                    norm_name = name_template

                # Dédoublonnage
                norm_name = self._deduplicate(norm_name)
                confidence = 0.95 if number or len(name_clean) > 3 else 0.8
                return norm_name, room_type, number, is_exterior, confidence

        logger.warning(f"Pièce non reconnue: '{name_raw}'")
        return None, None, None, False, 0.0

    def _deduplicate(self, name: str) -> str:
        """Si 'sejour' existe déjà, retourne 'sejour_2'"""
        if name not in self._seen_names:
            self._seen_names[name] = 1
            return name
        self._seen_names[name] += 1
        return f"{name}_{self._seen_names[name]}"