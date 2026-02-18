"""
Vue d'extraction : affichage et edition des donnees extraites d'un lot.
"""

import streamlit as st
from typing import Dict
import logging

from ui.styles import METHOD_COLORS, METHOD_LABELS

logger = logging.getLogger(__name__)


def display_parcel_data(data: dict, editable: bool = True, key_prefix: str = "") -> dict:
    """
    Affiche et permet l'edition des donnees d'un lot.

    Args:
        data: Dictionnaire des donnees du lot
        editable: Si True, les champs sont editables
        key_prefix: Prefix unique pour les IDs des widgets

    Returns:
        Dictionnaire des donnees (potentiellement modifiees)
    """
    st.subheader("Donnees extraites")

    # Afficher la methode d'extraction utilisee
    _display_extraction_meta(data)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        _display_main_fields(data, editable, key_prefix)

    with col2:
        _display_surface_fields(data, editable, key_prefix)

    _display_options(data, editable, key_prefix)

    return data


def _display_extraction_meta(data: dict):
    """Affiche la methode et la confiance de l'extraction."""
    meta = data.get('_extraction_meta', {})
    method = meta.get('method', 'inconnu')
    confidence = meta.get('confidence')

    color = METHOD_COLORS.get(method, '#666')
    label = METHOD_LABELS.get(method, method)

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(
            f"**Methode:** <span style='color:{color}; font-weight:bold'>{label}</span>",
            unsafe_allow_html=True
        )
    with col_m2:
        if confidence is not None:
            st.markdown(f"**Confiance:** {confidence:.0%}")


def _display_main_fields(data: dict, editable: bool, key_prefix: str = ""):
    """Affiche les champs principaux du lot."""
    st.markdown("### Informations principales")

    if editable:
        data['parcelLabel'] = st.text_input("Reference lot", data.get('parcelLabel', ''), key=f"{key_prefix}parcelLabel")
        data['typology'] = st.text_input("Typologie (T1, T2, etc.)", data.get('typology', ''), key=f"{key_prefix}typology")
        data['floor'] = st.text_input("Etage", data.get('floor', ''), key=f"{key_prefix}floor")
        data['orientation'] = st.text_input("Orientation", data.get('orientation', ''), key=f"{key_prefix}orientation")
        data['living_space'] = st.text_input("Surface habitable (m2)", data.get('living_space', ''), key=f"{key_prefix}living_space")
        data['price'] = st.text_input("Prix", data.get('price', 'N.C'), key=f"{key_prefix}price")
    else:
        st.write(f"**Reference lot:** {data.get('parcelLabel', 'N/A')}")
        st.write(f"**Typologie:** {data.get('typology', 'N/A')}")
        st.write(f"**Etage:** {data.get('floor', 'N/A')}")
        st.write(f"**Orientation:** {data.get('orientation', 'N/A')}")
        st.write(f"**Surface habitable:** {data.get('living_space', 'N/A')} m2")
        st.write(f"**Prix:** {data.get('price', 'N.C')}")


def _display_surface_fields(data: dict, editable: bool, key_prefix: str = ""):
    """Affiche toutes les surfaces (pieces et annexes)."""
    st.markdown("### Surfaces")
    
    surface_detail = data.get('surfaceDetail', {})
    
    if surface_detail:
        # Afficher toutes les surfaces dans un tableau
        surfaces_list = []
        for key, value in surface_detail.items():
            # Normaliser le nom pour l'affichage
            display_name = key.replace('_', ' ').title()
            surfaces_list.append({"Piece": display_name, "Surface (m2)": value})
        
        # Trier par surface (decroissant)
        surfaces_list.sort(key=lambda x: x["Surface (m2)"], reverse=True)
        
        # Afficher en tableau
        import pandas as pd
        df = pd.DataFrame(surfaces_list)
        st.dataframe(df, hide_index=True, width='stretch')
        
        # Afficher le total
        total = sum(surface_detail.values())
        st.markdown(f"**Total:** {total:.2f} m²")
    else:
        st.write("*Aucune surface*")


def _display_options(data: dict, editable: bool, key_prefix: str = ""):
    """Affiche les options (terrasse, parking, etc.)."""
    st.markdown("### Options disponibles")

    options = data.get('option', {})

    if editable:
        cols = st.columns(4)
        option_keys = list(options.keys())

        for i, option in enumerate(option_keys):
            with cols[i % 4]:
                options[option] = st.checkbox(
                    option.replace('_', ' ').title(),
                    value=options[option],
                    key=f"{key_prefix}option_{option}"
                )

        data['option'] = options
    else:
        active_options = [k.replace('_', ' ').title() for k, v in options.items() if v]
        if active_options:
            st.write(", ".join(active_options))
        else:
            st.write("*Aucune option*")


def render_extraction_results(extractor):
    """
    Affiche les resultats d'extraction avec boutons de sauvegarde/validation.

    Args:
        extractor: Instance de HybridExtractor
    """
    edited_data = display_parcel_data(
        st.session_state.extracted_data.copy(),
        editable=True
    )

    col_save, col_validate = st.columns(2)

    with col_save:
        if st.button("Sauvegarder", width='stretch'):
            parcel_id = edited_data.get('parcelLabel', 'LOT_001')
            st.session_state.all_parcels[parcel_id] = edited_data
            st.session_state.extracted_data = edited_data
            st.success("Modifications sauvegardees!")

    with col_validate:
        if st.button("Valider pour ML", type="primary", width='stretch'):
            # Methode robuste: valider ou creer l'extraction
            try:
                image_path = st.session_state.get('last_uploaded_file')
                extracted_data = st.session_state.get('extracted_data', {})
                meta = extracted_data.get('_extraction_meta', {})
                method = meta.get('method', 'unknown')
                confidence = meta.get('confidence', 0)
                
                if image_path and extracted_data:
                    extraction_id = extractor.validate_or_save(
                        image_path=image_path,
                        extracted_data=extracted_data,
                        method=method,
                        confidence=confidence,
                        corrected_data=edited_data
                    )
                    st.success(
                        f"Extraction validee et sauvegardee pour l'entrainement ML! (ID: {extraction_id})"
                    )
                    st.rerun()
                else:
                    st.error("Impossible de valider: donnees manquantes")
                    
            except Exception as e:
                st.error(f"Erreur de validation: {e}")
                logger.error(f"Erreur validation: {e}", exc_info=True)
