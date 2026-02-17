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
            # ══════════════════════════════════════════
            # COMPOSITES (toujours EN PREMIER)
            # ══════════════════════════════════════════
            (r"^(SEJOUR|S[ÉE]JOUR|SALON|RECEPTION|R[ÉE]CEPTION)\s*/?\s*CUISINE",
            "sejour_cuisine", RoomType.LIVING_KITCHEN, False),
            (r"^CUISINE\s*/?\s*(SEJOUR|S[ÉE]JOUR|SALON)",
            "sejour_cuisine", RoomType.LIVING_KITCHEN, False),
            (r"^PI[ÈE]CE\s*(DE\s*VIE|PRINCIPALE|A\s*VIVRE)",
            "sejour_cuisine", RoomType.LIVING_KITCHEN, False),
            (r"^(LIVING|ESPACE)\s*/?\s*(CUISINE|KITCHEN)",
            "sejour_cuisine", RoomType.LIVING_KITCHEN, False),

            # SDB/WC combiné
            (r"^(SDB\s*/\s*WC|SDB\s*WC|SALLE\s*DE\s*BAINS?\s*/?\s*WC)$",
            "salle_de_bain", RoomType.BATHROOM, False),
            (r"^(WC\s*/\s*SDB|WC\s*SDB)$",
            "salle_de_bain", RoomType.BATHROOM, False),

            # SDE/WC combiné (salle d'eau + WC)
            (r"^(SDE\s*/\s*WC|SDE\s*WC|SALLE\s*D['\u2019]?\s*EAU\s*/?\s*WC)$",
            "salle_d_eau", RoomType.SHOWER_ROOM, False),
            (r"^(WC\s*/\s*SDE|WC\s*SDE)$",
            "salle_d_eau", RoomType.SHOWER_ROOM, False),

            # ══════════════════════════════════════════
            # RÉCEPTION (distinct de séjour)
            # ══════════════════════════════════════════
            (r"^(RECEPTION|R[ÉE]CEPTION|PIECE\s*DE\s*RECEPTION)$",
             "reception", RoomType.RECEPTION, False),

            # ══════════════════════════════════════════
            # SÉJOUR / SALON
            # ══════════════════════════════════════════
            (r"^(SEJOUR|S[ÉE]JOUR|SALON|LIVING|DOUBLE\s*S[ÉE]JOUR|"
            r"SALLE\s*[AÀ]\s*MANGER|SAM|PIECE\s*PRINCIPALE)$",
            "sejour", RoomType.LIVING_ROOM, False),

            # ══════════════════════════════════════════
            # CUISINE
            # ══════════════════════════════════════════
            (r"^(CUISINE|KITCHENETTE|COIN\s*CUISINE|CUISINE\s*[ÉE]QUIP[ÉE]E|"
            r"ESPACE\s*CUISINE|CUISINE\s*AM[ÉE]RICAINE|OFFICE)$",
            "cuisine", RoomType.KITCHEN, False),

            # === Entrée/DGT combiné (AVANT le pattern entrée simple) ===
            (r"^(ENTREE\s*/\s*DGT|ENTR[ÉEée]E\s*/\s*D[ÉE]GAGEMENT|"
            r"HALL\s*/\s*DGT|ENTR[ÉEée]E\s*/\s*CIRCULATION)$",
            "entree", RoomType.ENTRY, False),

            # ══════════════════════════════════════════
            # ENTRÉE / HALL
            # ══════════════════════════════════════════
            (r"^(ENTR[ÉEée]E|HALL\s*D['\u2019]?ENTR[ÉEée]E|HALL|VESTIBULE|"
            r"SAS\s*D['\u2019]?ENTR[ÉEée]E|SAS|ACCUEIL)$",
            "entree", RoomType.ENTRY, False),

            # ══════════════════════════════════════════
            # CIRCULATION / DÉGAGEMENT
            # ══════════════════════════════════════════
            (r"^(DGT|D\.G\.T\.?|D[ÉE]GAGEMENT|COULOIR|PALIER|CIRCULATION|"
            r"DIST\.?|DISTRIBUTION|PASSAGE|COURSIVE)$",
            "circulation", RoomType.CIRCULATION, False),

            # ══════════════════════════════════════════
            # CHAMBRES
            # ══════════════════════════════════════════
            (r"^CHAMBRE\s*(\d+)$", "chambre_{n}", RoomType.BEDROOM, False),
            (r"^CHAMBRE$", "chambre", RoomType.BEDROOM, False),
            (r"^CH\.?\s*(\d+)$", "chambre_{n}", RoomType.BEDROOM, False),
            (r"^SUITE\s*PARENTALE\s*(\d*)$", "chambre_{n}", RoomType.BEDROOM, False),
            (r"^(BUREAU|OFFICE|CABINET)\s*(\d*)$", "chambre_{n}", RoomType.BEDROOM, False),
            (r"^CHAMBRE\s*D['\u2019]?\s*(AMIS?|ENFANTS?)\s*(\d*)$",
            "chambre_{n}", RoomType.BEDROOM, False),
            (r"^CH\s*(\d+)$", "chambre_{n}", RoomType.BEDROOM, False),
            (r"^CHAMBRE\s*PARENTALE$", "chambre_1", RoomType.BEDROOM, False),
            (r"^CHAMBRE\s*/\s*BUREAU\s*(\d*)$", "chambre_{n}", RoomType.BEDROOM, False),

            # ══════════════════════════════════════════
            # SALLE DE BAIN
            # ══════════════════════════════════════════
            (r"^(SALLE\s*DE\s*BAINS?|SDB|S\.?\s*D\.?\s*B\.?|BAIN)\s*(\d+)$",
            "salle_de_bain_{n}", RoomType.BATHROOM, False),
            (r"^(SALLE\s*DE\s*BAINS?|SDB|S\.?\s*D\.?\s*B\.?|BAIN)$",
            "salle_de_bain", RoomType.BATHROOM, False),
            (r"^(SALLE\s*DE\s*BAINS?\s*PARENTALE)$",
            "salle_de_bain_1", RoomType.BATHROOM, False),

            # ══════════════════════════════════════════
            # SALLE D'EAU
            # ══════════════════════════════════════════
            (r"^(SALLE\s*D['\u2019]?\s*EAU|SDE|S\.?\s*D\.?\s*E\.?|EAU)\s*(\d+)$",
            "salle_d_eau_{n}", RoomType.SHOWER_ROOM, False),
            (r"^(SALLE\s*D['\u2019]?\s*EAU|SDE|S\.?\s*D\.?\s*E\.?|EAU)$",
            "salle_d_eau", RoomType.SHOWER_ROOM, False),

            # ══════════════════════════════════════════
            # WC / TOILETTES
            # ══════════════════════════════════════════
            (r"^(WC|W\.?\s*C\.?|TOILETT?E?S?)\s*(\d+)$",
            "wc_{n}", RoomType.WC, False),
            (r"^(WC|W\.?\s*C\.?|TOILETT?E?S?)$",
            "wc", RoomType.WC, False),
            (r"^(RGT\s*WC|RGT\s*W\.?\s*C\.?)$",
            "wc", RoomType.WC, False),

            # ══════════════════════════════════════════
            # RANGEMENTS
            # ══════════════════════════════════════════
            (r"^(DRESSING)\s*(\d*)$", "dressing", RoomType.DRESSING, False),
            (r"^(PLACARD|CELLIER|BUANDERIE|LINGERIE|RANGEMENT|RGT|"
            r"LOCAL\s*TECHNIQUE|LOCAL\s*POUSSETTE|CELLIER\s*/\s*BUANDERIE|"
            r"GRENIER|REMISE|D[ÉE]BARRAS|CAVE\s*INT[ÉE]RIEURE)$",
            "storage", RoomType.STORAGE, False),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - BALCON
            # ══════════════════════════════════════════
            (r"^BALCON(?:Y)?\s*:?\s*(\d*)$", "balcon{n}", RoomType.BALCONY, True),
            (r"^BALCON:\s*(\d+[\.,]\d+)", "balcon", RoomType.BALCONY, True),
            (r"^BALCON\s*(\d+)$", "balcon_{n}", RoomType.BALCONY, True),
            
            # ══════════════════════════════════════════
            # EXTÉRIEUR - JARDIN
            # ══════════════════════════════════════════
            (r"^JARDIN\s*:?\s*(\d+[\.,]\d+)", "jardin", RoomType.GARDEN, True),
            (r"^JARDIN\s*(\d+)$", "jardin", RoomType.GARDEN, True),
            (r"^BALCON:\s*(\d+[\.,]\d+)", "balcon", RoomType.BALCONY, True),
            (r"^BALCON\s*(\d+)$", "balcon_{n}", RoomType.BALCONY, True),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - TERRASSE
            # ══════════════════════════════════════════
            (r"^TERRASSE\s*(\d*)$", "terrasse", RoomType.TERRACE, True),
            (r"^(TERRASSE\s*COUVERTE)\s*(\d*)$", "terrasse", RoomType.TERRACE, True),
            (r"^(ROOF\s*TOP|TOIT\s*TERRASSE)\s*(\d*)$", "terrasse", RoomType.TERRACE, True),
            (r"^(SOLARIUM)\s*(\d*)$", "terrasse", RoomType.TERRACE, True),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - JARDIN
            # ══════════════════════════════════════════
            (r"^(JARDIN|JARDINET|JARDIN\s*PRIVATIF)\s*(\d*)$",
            "jardin", RoomType.GARDEN, True),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - LOGGIA
            # ══════════════════════════════════════════
            (r"^(LOGGIA|LOGIA)\s*(\d*)$", "loggia", RoomType.LOGGIA, True),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - PATIO / COUR
            # ══════════════════════════════════════════
            (r"^(PATIO|COUR|COURETTE|COUR\s*ANGLAISE)\s*(\d*)$",
            "patio", RoomType.PATIO, True),

            # ══════════════════════════════════════════
            # PARKING / GARAGE
            # ══════════════════════════════════════════
            (r"^(PARKING|GARAGE|BOX|STATIONNEMENT|PLACE\s*DE\s*PARKING)\s*(\d*)$",
            "parking", RoomType.PARKING, True),

            # ══════════════════════════════════════════
            # CAVE
            # ══════════════════════════════════════════
            (r"^(CAVE|SOUS[\s\-]?SOL)\s*(\d*)$", "cave", RoomType.CELLAR, True),

            # ══════════════════════════════════════════
            # EXTÉRIEUR - VÉRANDA (bonus)
            # ══════════════════════════════════════════
            (r"^(V[ÉE]RANDA|PERGOLA|AUVENT)\s*(\d*)$",
            "terrasse", RoomType.TERRACE, True),
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
                        # Remove both _{n} and {n}
                        norm_name = name_template.replace("_{n}", "").replace("{n}", "")
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