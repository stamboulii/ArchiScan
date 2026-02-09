"""
Modules UI Streamlit pour ArchiExtract.
Chaque module gere une section specifique de l'interface.
"""

from ui.styles import apply_custom_styles
from ui.sidebar import render_sidebar
from ui.upload_section import handle_file_upload, render_upload_section
from ui.extraction_view import display_parcel_data, render_extraction_results
from ui.export_section import export_to_json, render_export_section
from ui.training_dashboard import render_training_dashboard

__all__ = [
    'apply_custom_styles',
    'render_sidebar',
    'handle_file_upload',
    'render_upload_section',
    'display_parcel_data',
    'render_extraction_results',
    'export_to_json',
    'render_export_section',
    'render_training_dashboard',
]
