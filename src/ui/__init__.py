"""
ArchiExtract UI - Interface Streamlit
=====================================

Modules:
    streamlit_app: Application principale
    styles: Styles CSS
    sidebar: Navigation
    upload: Upload de fichiers
    extraction: Affichage des resultats
    export: Export des donnees
    training: Dashboard ML
"""

__version__ = "1.0.0"

__all__ = [
    'streamlit_app',
]

# Re-export pour faciliter les imports
try:
    from . import streamlit_app
    from . import styles
    from . import sidebar
    from . import upload_section
    from . import extraction_view
    from . import export_section
    from . import training_dashboard
except ImportError:
    # Streamlit pas installe, ne pas echouer l'import
    pass
