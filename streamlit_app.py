"""
Interface Streamlit pour l'extracteur de plans d'architecture.
Application web avec strategie hybride progressive (Claude Vision + ML).

Point d'entree principal - delegue aux modules UI:
  ui/styles.py            - CSS et constantes visuelles
  ui/sidebar.py           - Configuration et statistiques
  ui/upload_section.py    - Upload et traitement des fichiers
  ui/extraction_view.py   - Affichage et edition des donnees
  ui/export_section.py    - Export JSON/CSV et recapitulatif
  ui/training_dashboard.py - Dashboard d'entrainement ML
"""

import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="ArchiExtract - Hybrid",
    page_icon="🏗️",
    layout="wide"
)

# Imports depuis la nouvelle structure src/
from src.extractors.hybrid_extractor import HybridExtractor
from training_data_store import TrainingDataStore

from ui.styles import apply_custom_styles
from ui.sidebar import render_sidebar, get_extractor
from ui.upload_section import render_upload_section
from ui.export_section import render_export_section
from ui.training_dashboard import render_training_dashboard


def initialize_session_state():
    """Initialise les variables de session."""
    defaults = {
        'extracted_data': None,
        'all_parcels': {},
        'api_key': '',
        'force_method': None,
        'last_extraction_id': None,
        'hybrid_extractor': HybridExtractor(),
        'data_store': TrainingDataStore(),
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def main():
    """Fonction principale de l'application."""

    initialize_session_state()
    apply_custom_styles()

    # En-tete
    st.markdown(
        '<div class="main-header">ArchiExtract - Hybrid</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="info-box">
    <strong>Strategie Hybride Progressive:</strong>
    <ol>
        <li>Uploadez une image ou un PDF de plan d'architecture</li>
        <li>L'outil extrait automatiquement les donnees (Claude Vision ou Tesseract)</li>
        <li>Verifiez, corrigez si necessaire, et <strong>validez</strong> pour l'entrainement ML</li>
        <li>Apres 300 validations, un modele ML custom peut etre entraine</li>
    </ol>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Sidebar (retourne les options selectionnees)
    batch_mode, export_format = render_sidebar()

    # Section principale d'upload et extraction
    extractor = get_extractor()
    render_upload_section(extractor, batch_mode)

    # Section d'export
    render_export_section()

    # Dashboard d'entrainement ML
    render_training_dashboard(extractor)


if __name__ == "__main__":
    main()
