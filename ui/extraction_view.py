"""
Vue d'extraction : affichage et edition des donnees extraites d'un lot.
"""

import streamlit as st
from typing import Dict

from ui.styles import METHOD_COLORS, METHOD_LABELS


def display_parcel_data(data: dict, editable: bool = True) -> dict:
    """
    Affiche et permet l'edition des donnees d'un lot.

    Args:
        data: Dictionnaire des donnees du lot
        editable: Si True, les champs sont editables

    Returns:
        Dictionnaire des donnees (potentiellement modifiees)
    """
    st.subheader("Donnees extraites")

    # Afficher la methode d'extraction utilisee
    _display_extraction_meta(data)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        _display_main_fields(data, editable)

    with col2:
        _display_surface_fields(data, editable)

    _display_options(data, editable)

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


def _display_main_fields(data: dict, editable: bool):
    """Affiche les champs principaux du lot."""
    st.markdown("### Informations principales")

    if editable:
        data['parcelLabel'] = st.text_input("Reference lot", data.get('parcelLabel', ''))
        data['typology'] = st.text_input("Typologie (T1, T2, etc.)", data.get('typology', ''))
        data['floor'] = st.text_input("Etage", data.get('floor', ''))
        data['orientation'] = st.text_input("Orientation", data.get('orientation', ''))
        data['living_space'] = st.text_input("Surface habitable (m2)", data.get('living_space', ''))
        data['price'] = st.text_input("Prix", data.get('price', 'N.C'))
    else:
        st.write(f"**Reference lot:** {data.get('parcelLabel', 'N/A')}")
        st.write(f"**Typologie:** {data.get('typology', 'N/A')}")
        st.write(f"**Etage:** {data.get('floor', 'N/A')}")
        st.write(f"**Orientation:** {data.get('orientation', 'N/A')}")
        st.write(f"**Surface habitable:** {data.get('living_space', 'N/A')} m2")
        st.write(f"**Prix:** {data.get('price', 'N.C')}")


def _display_surface_fields(data: dict, editable: bool):
    """Affiche les surfaces annexes."""
    st.markdown("### Surfaces annexes")

    surface_detail = data.get('surfaceDetail', {})

    if editable:
        terrace = st.number_input(
            "Terrasse (m2)", value=surface_detail.get('terrace', 0.0), step=0.01
        )
        balcony = st.number_input(
            "Balcon (m2)", value=surface_detail.get('balcony', 0.0), step=0.01
        )
        garden = st.number_input(
            "Jardin (m2)", value=surface_detail.get('garden', 0.0), step=0.01
        )

        data['surfaceDetail'] = {}
        if terrace > 0:
            data['surfaceDetail']['terrace'] = terrace
        if balcony > 0:
            data['surfaceDetail']['balcony'] = balcony
        if garden > 0:
            data['surfaceDetail']['garden'] = garden
    else:
        if surface_detail:
            for key, value in surface_detail.items():
                st.write(f"**{key.capitalize()}:** {value} m2")
        else:
            st.write("*Aucune surface annexe*")


def _display_options(data: dict, editable: bool):
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
                    value=options[option]
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
        if st.button("Sauvegarder", use_container_width=True):
            parcel_id = edited_data.get('parcelLabel', 'LOT_001')
            st.session_state.all_parcels[parcel_id] = edited_data
            st.session_state.extracted_data = edited_data
            st.success("Modifications sauvegardees!")

    with col_validate:
        if st.button("Valider pour ML", type="primary", use_container_width=True):
            extraction_id = st.session_state.last_extraction_id
            if extraction_id:
                extractor.validate_extraction_by_id(
                    extraction_id,
                    corrected_data=edited_data
                )
                st.success(
                    "Extraction validee et sauvegardee pour l'entrainement ML!"
                )
            else:
                extractor.validate_last_extraction(corrected_data=edited_data)
                st.success("Extraction validee!")
