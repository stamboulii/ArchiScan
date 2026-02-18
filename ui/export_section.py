"""
Section d'export : tableau recapitulatif, telechargement JSON, reinitialisation.
"""

import json
import streamlit as st
import pandas as pd
from typing import Dict


def export_to_json(data: dict) -> str:
    """
    Exporte les donnees en JSON (nettoie les metadonnees internes).

    Args:
        data: Dictionnaire des lots

    Returns:
        Chaine JSON formatee
    """
    clean = {}
    for key, value in data.items():
        if isinstance(value, dict):
            parcel_dict = {}
            for k, v in value.items():
                # Garder seulement _validation (pas _raw_text ni _extraction_meta)
                if k == '_validation':
                    parcel_dict[k] = v
                # Ne pas dupliquer parcelLabel comme champ s'il est egal a la cle
                elif k == 'parcelLabel' and v == key:
                    continue
                # Filtrer les autres champs_
                elif not k.startswith('_'):
                    parcel_dict[k] = v
            clean[key] = parcel_dict
        else:
            clean[key] = value
    return json.dumps(clean, indent=2, ensure_ascii=False)


def render_export_section():
    """
    Rendu de la section d'export des donnees.
    Affiche le tableau, le bouton de telechargement et le JSON complet.
    """
    if not st.session_state.all_parcels:
        return

    st.markdown("---")
    st.subheader("Export des donnees")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Voir le tableau recapitulatif", width='stretch'):
            _display_summary_table()

    with col2:
        json_data = export_to_json(st.session_state.all_parcels)
        st.download_button(
            label="Telecharger JSON",
            data=json_data,
            file_name="architecture_plans.json",
            mime="application/json",
        )

    with col3:
        if st.button("Reinitialiser tout", type="secondary", width='stretch'):
            st.session_state.all_parcels = {}
            st.session_state.extracted_data = None
            st.session_state.last_extraction_id = None
            st.rerun()

    with st.expander("Voir le JSON complet"):
        _display_clean_json()


def _display_summary_table():
    """Affiche le tableau recapitulatif de tous les lots."""
    df_data = []
    for parcel_id, data in st.session_state.all_parcels.items():
        meta = data.get('_extraction_meta', {})
        df_data.append({
            'Lot': data.get('parcelLabel', parcel_id),
            'Type': data.get('typology', ''),
            'Etage': data.get('floor', ''),
            'Surface': data.get('living_space', ''),
            'Prix': data.get('price', ''),
            'Methode': meta.get('method', '-'),
        })

    df = pd.DataFrame(df_data)
    st.dataframe(df, width='stretch')


def _display_clean_json():
    """Affiche le JSON complet sans metadonnees internes."""
    display_data = {}
    for k, v in st.session_state.all_parcels.items():
        if isinstance(v, dict):
            # Garder uniquement _validation (pas _raw_text ni _extraction_meta)
            parcel_dict = {}
            for dk, dv in v.items():
                # Garder seulement _validation
                if dk == '_validation':
                    parcel_dict[dk] = dv
                # Ne pas dupliquer parcelLabel comme champ s'il est egal a la cle
                elif dk == 'parcelLabel' and dv == k:
                    continue
                # Filtrer les autres champs_
                elif not dk.startswith('_'):
                    parcel_dict[dk] = dv
            # Ne pas dupliquer parcelLabel comme champ s'il est egal a la cle
            if parcel_dict.get('parcelLabel') == k:
                parcel_dict.pop('parcelLabel', None)
            display_data[k] = parcel_dict
        else:
            display_data[k] = v
    st.json(display_data)
