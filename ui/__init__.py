"""
Modules UI Streamlit pour ArchiExtract.
Chaque module gere une section specifique de l'interface.

Structure:
    - styles.py: Styles CSS globaux
    - sidebar.py: Navigation et configuration
    - upload_section.py: Upload de fichiers
    - extraction_view.py: Affichage des resultats
    - export_section.py: Export des donnees
    - training_dashboard.py: Dashboard ML
"""

from ui.styles import apply_custom_styles
from ui.sidebar import render_sidebar
from ui.upload_section import handle_file_upload, render_upload_section
from ui.extraction_view import display_parcel_data, render_extraction_results
from ui.export_section import export_to_json, render_export_section
from ui.training_dashboard import render_training_dashboard

__version__ = "1.0.0"

__all__ = [
    # Styles
    'apply_custom_styles',
    # Navigation
    'render_sidebar',
    # Upload
    'handle_file_upload',
    'render_upload_section',
    # Resultats
    'display_parcel_data',
    'render_extraction_results',
    # Export
    'export_to_json',
    'render_export_section',
    # ML
    'render_training_dashboard',
    # Version
    '__version__',
]
