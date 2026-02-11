"""
Styles CSS personnalises pour l'application ArchiExtract.
"""

import streamlit as st


# Couleurs par methode d'extraction
METHOD_COLORS = {
    'claude': '#4285f4',
    'tesseract': '#ff9800',
    'ml': '#4caf50',
    'pymupdf': '#9c27b0',
}

METHOD_LABELS = {
    'claude': 'Claude Vision',
    'tesseract': 'Tesseract OCR',
    'ml': 'ML Custom',
    'pymupdf': 'PyMuPDF',
}

PHASE_ICONS = {
    0: '\U0001f7e0',  # orange circle
    1: '\U0001f535',  # blue circle
    2: '\U0001f7e3',  # purple circle
    3: '\U0001f7e2',  # green circle
    4: '\U0001f52c',  # crystal ball (purple)
}


def apply_custom_styles():
    """Applique le CSS personnalise a l'application Streamlit."""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 1rem;
        }
        .phase-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-weight: bold;
            font-size: 0.85rem;
        }
        .phase-0 { background-color: #ffa500; color: white; }
        .phase-1 { background-color: #4285f4; color: white; }
        .phase-2 { background-color: #9c27b0; color: white; }
        .phase-3 { background-color: #4caf50; color: white; }
        .phase-4 { background-color: #9c27b0; color: white; }
        .method-claude { color: #4285f4; font-weight: bold; }
        .method-tesseract { color: #ff9800; font-weight: bold; }
        .method-ml { color: #4caf50; font-weight: bold; }
        .method-pymupdf { color: #9c27b0; font-weight: bold; }
        .success-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .error-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .info-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }
    </style>
    """, unsafe_allow_html=True)
