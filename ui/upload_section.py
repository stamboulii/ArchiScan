"""
Section d'upload : gestion des fichiers (images et PDF) et mode batch.
"""

import logging
import streamlit as st
from pathlib import Path
from PIL import Image

from config import TEMP_DIR, SUPPORTED_UPLOAD_FORMATS, ensure_directories

logger = logging.getLogger(__name__)


def handle_file_upload(uploaded_file) -> tuple:
    """
    Gere l'upload d'un fichier et retourne (temp_path, display_image).
    Supporte PDF et images.

    Args:
        uploaded_file: Objet UploadedFile de Streamlit

    Returns:
        (temp_path, display_image) - Chemin temporaire et image pour affichage
    """
    ensure_directories()

    temp_path = str(TEMP_DIR / uploaded_file.name)

    try:
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    except IOError as e:
        logger.error(f"Erreur d'ecriture du fichier temporaire: {e}")
        st.error(f"Impossible de sauvegarder le fichier: {e}")
        return None, None

    # Gerer les PDFs
    if uploaded_file.name.lower().endswith('.pdf'):
        try:
            from claude_vision_extractor import convert_pdf_to_images
            pages = convert_pdf_to_images(temp_path)
            if pages:
                display_image = Image.open(pages[0])
            else:
                display_image = None
                st.warning("Impossible d'extraire les pages du PDF")
        except Exception as e:
            logger.error(f"Erreur de conversion PDF: {e}")
            display_image = None
            st.warning(f"Erreur de conversion PDF: {e}")
    else:
        try:
            display_image = Image.open(temp_path)
        except Exception as e:
            logger.error(f"Erreur d'ouverture de l'image: {e}")
            display_image = None
            st.warning(f"Impossible d'ouvrir l'image: {e}")

    return temp_path, display_image


def render_upload_section(extractor, batch_mode: bool):
    """
    Rendu de la section d'upload selon le mode (single ou batch).

    Args:
        extractor: Instance de HybridExtractor
        batch_mode: True pour le mode batch (multi-fichiers)
    """
    if not batch_mode:
        _render_single_upload(extractor)
    else:
        _render_batch_upload(extractor)


def _render_single_upload(extractor):
    """Mode image unique : upload, affichage et extraction."""
    uploaded_file = st.file_uploader(
        "Choisissez une image ou un PDF du plan",
        type=SUPPORTED_UPLOAD_FORMATS,
        help="Formats acceptes: PNG, JPG, JPEG, PDF"
    )

    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Image uploadee")

            temp_path, display_image = handle_file_upload(uploaded_file)

            if display_image:
                st.image(display_image, use_container_width=True)
            else:
                st.warning("Impossible d'afficher l'image")

            # Bouton d'extraction
            if temp_path and st.button(
                "Extraire les donnees", type="primary", use_container_width=True
            ):
                _run_extraction(extractor, temp_path)

        with col2:
            if st.session_state.extracted_data is not None:
                from ui.extraction_view import render_extraction_results
                render_extraction_results(extractor)


def _render_batch_upload(extractor):
    """Mode batch : upload multiple et traitement en lot."""
    st.subheader("Mode Batch - Traitement multiple")

    uploaded_files = st.file_uploader(
        "Choisissez plusieurs fichiers",
        type=SUPPORTED_UPLOAD_FORMATS,
        accept_multiple_files=True
    )

    if uploaded_files:
        st.info(f"{len(uploaded_files)} fichier(s) selectionne(s)")

        auto_validate = st.checkbox(
            "Auto-valider les extractions Claude (confiance > 80%)",
            value=False,
            help="Marque automatiquement les extractions Claude comme validees pour le ML"
        )

        if st.button("Traiter tous les fichiers", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            if auto_validate:
                extractor.auto_validate = True

            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Traitement de {uploaded_file.name}...")

                try:
                    temp_path, _ = handle_file_upload(uploaded_file)
                    if temp_path:
                        result = extractor.extract_from_image(temp_path)
                        parcel_id = result.get('parcelLabel', f'LOT_{i+1:03d}')
                        st.session_state.all_parcels[parcel_id] = result
                except Exception as e:
                    st.error(f"Erreur pour {uploaded_file.name}: {str(e)}")

                progress_bar.progress((i + 1) / len(uploaded_files))

            extractor.auto_validate = False
            status_text.text("Traitement termine!")
            st.success(f"{len(st.session_state.all_parcels)} lot(s) extrait(s)")


def _run_extraction(extractor, temp_path: str):
    """Execute l'extraction et met a jour le session state."""
    from config import DEBUG_DIR

    with st.spinner("Extraction en cours..."):
        try:
            result = extractor.extract_from_image(temp_path)

            st.session_state.extracted_data = result
            st.session_state.last_extraction_id = result.get('_extraction_id')

            # Ajout a la collection
            parcel_id = result.get(
                'parcelLabel',
                f'LOT_{len(st.session_state.all_parcels) + 1}'
            )
            st.session_state.all_parcels[parcel_id] = result

            # Message de succes avec methode
            from ui.styles import METHOD_LABELS
            meta = result.get('_extraction_meta', {})
            method = meta.get('method', 'inconnu')
            st.success(
                f"Extraction reussie via {METHOD_LABELS.get(method, method)}!"
            )

            # Debug OCR
            debug_text_path = DEBUG_DIR / 'extracted_text_debug.txt'
            if debug_text_path.exists():
                with st.expander("Texte OCR brut (debug)"):
                    with open(str(debug_text_path), 'r', encoding='utf-8') as f:
                        st.code(f.read())

        except Exception as e:
            st.error(f"Erreur lors de l'extraction: {str(e)}")
            st.exception(e)
