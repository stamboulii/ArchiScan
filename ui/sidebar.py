"""
Sidebar : configuration, phase actuelle, progression et options.
"""

import streamlit as st
from src.extractors.hybrid_extractor import HybridExtractor
from ui.styles import PHASE_ICONS


def get_extractor() -> HybridExtractor:
    """Obtient l'extracteur hybride depuis le session state."""
    return st.session_state.hybrid_extractor


def render_sidebar() -> tuple:
    """
    Affiche la sidebar avec configuration et statistiques.

    Returns:
        (batch_mode, export_format) - Options selectionnees par l'utilisateur
    """
    extractor = get_extractor()

    with st.sidebar:
        st.header("Configuration")

        # --- Cle API ---
        _render_api_key_section()

        # --- Phase actuelle ---
        _render_phase_section(extractor)

        # --- Progression entrainement ---
        _render_progress_section(extractor)

        # --- Methode forcee ---
        _render_method_selector()

        st.markdown("---")

        # --- Options ---
        st.markdown("### Options")
        export_format = st.selectbox("Format d'export", ["JSON", "CSV"])
        batch_mode = st.checkbox("Mode batch (plusieurs images)", value=False)

        st.markdown("---")
        st.metric("Lots traites", len(st.session_state.all_parcels))

    return batch_mode, export_format


def _render_api_key_section():
    """Section de configuration de la cle API."""
    st.markdown("### Cle API Claude")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=st.session_state.api_key,
        help="Obtenez votre cle sur console.anthropic.com"
    )
    if api_key != st.session_state.api_key:
        st.session_state.api_key = api_key
        method = st.session_state.force_method
        st.session_state.hybrid_extractor = HybridExtractor(
            api_key=api_key,
            force_method=method
        )
        st.rerun()


def _render_phase_section(extractor: HybridExtractor):
    """Affiche la phase operationnelle actuelle."""
    st.markdown("### Phase actuelle")
    phase_info = extractor.get_phase_description()
    phase = phase_info['phase']

    icon = PHASE_ICONS.get(phase, '\u26aa')
    st.markdown(f"{icon} **{phase_info['name']}**")
    st.caption(phase_info['description'])
    st.metric("Precision estimee", phase_info['accuracy'])


def _render_progress_section(extractor: HybridExtractor):
    """Affiche la progression de la collecte de donnees."""
    st.markdown("### Progression collecte")
    try:
        stats = extractor.get_statistics()
        progress = stats['progress_percent'] / 100.0
        st.progress(progress)
        st.caption(
            f"{stats['validated_count']} / {stats['min_samples_needed']} "
            f"echantillons valides"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total extractions", stats['total_extractions'])
        with col2:
            st.metric("Validees", stats['validated_count'])

        if stats.get('average_confidence', 0) > 0:
            st.metric("Confiance moyenne", f"{stats['average_confidence']:.1%}")

    except Exception as e:
        st.warning(f"Stats indisponibles: {e}")


def _render_method_selector():
    """Selecteur de methode d'extraction forcee."""
    st.markdown("### Methode d'extraction")
    method_options = {
        "Auto": None,
        "Claude Vision": "claude",
        "PyMuPDF (PDF direct)": "pymupdf",
        "Tesseract OCR": "tesseract",
        "Super Extractor (PyMuPDF + OCR + Validation)": "super",
        "ML Custom": "ml"
    }
    
    options_list = list(method_options.keys())
    
    # Get current index based on stored force_method
    current_method = st.session_state.get('force_method')
    current_index = 0
    for i, (label, value) in enumerate(method_options.items()):
        if value == current_method:
            current_index = i
            break
    
    selected = st.selectbox(
        "Forcer une methode",
        options_list,
        index=current_index,
        key="method_selector"
    )
    new_method = method_options[selected]
    if new_method != st.session_state.force_method:
        st.session_state.force_method = new_method
        st.session_state.hybrid_extractor = HybridExtractor(
            api_key=st.session_state.api_key or None,
            force_method=new_method
        )
        # Trigger re-extraction if there's existing data
        if st.session_state.extracted_data is not None:
            st.session_state.needs_re_extraction = True
