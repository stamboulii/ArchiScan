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
            clean[key] = {k: v for k, v in value.items() if not k.startswith('_')}
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
            display_data[k] = {dk: dv for dk, dv in v.items() if not dk.startswith('_')}
        else:
            display_data[k] = v
    st.json(display_data)
