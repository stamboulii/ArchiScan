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
            import fitz  # PyMuPDF pour convertir PDF en image
            # Convertir la premiere page du PDF en image pour l'affichage
            doc = fitz.open(temp_path)
            page = doc.load_page(0)  # Premiere page
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Haute resolution
            doc.close()
            # Convertir en PIL Image
            import io
            img_data = io.BytesIO(pix.tobytes())
            display_image = Image.open(img_data)
            st.info(f"PDF detecte: {uploaded_file.name}\nApercu de la premiere page ci-dessous.")
        except Exception as e:
            logger.error(f"Erreur de conversion PDF en image: {e}")
            display_image = None
            st.warning(f"PDF detected but preview unavailable: {e}")
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
                st.image(display_image, width='stretch')
            else:
                st.warning("Impossible d'afficher l'image")

            # Bouton d'extraction
            if temp_path and st.button(
                "Extraire les donnees", type="primary", width='stretch'
            ):
                _run_extraction(extractor, temp_path)

            # Auto-extraction si le fichier est deja charge et la methode a change
            if temp_path and st.session_state.get('needs_re_extraction', False):
                st.session_state.needs_re_extraction = False
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
                        # Verifier si on doit utiliser PyMuPDF
                        force_method = st.session_state.get('force_method')
                        
                        # Utiliser extract_from_pdf pour les fichiers PDF UNIQUEMENT si PyMuPDF est selectionne
                        if temp_path.lower().endswith('.pdf') and force_method == 'pymupdf':
                            result = extractor.extract_from_pdf(temp_path)
                        else:
                            result = extractor.extract_from_image(temp_path)
                        parcel_id = result.get('parcelLabel', f'LOT_{i+1:03d}')
                        
                        # Stocker l'extraction_id pour la validation
                        result['_batch_index'] = i
                        result['_source_file'] = uploaded_file.name
                        
                        st.session_state.all_parcels[parcel_id] = result
                except Exception as e:
                    st.error(f"Erreur pour {uploaded_file.name}: {str(e)}")

                progress_bar.progress((i + 1) / len(uploaded_files))

            extractor.auto_validate = False
            st.rerun()
    
    # Afficher les resultats s'il y en a (independamment de uploaded_files)
    if st.session_state.all_parcels:
        _render_batch_results(extractor)


def _render_batch_results(extractor):
    """Affiche les resultats du batch et permet l'edition/validation."""
    st.success(f"{len(st.session_state.all_parcels)} lot(s) extrait(s)")
    
    st.markdown("### Resultats d'extraction")
    
    # Tableau resume
    import pandas as pd
    df = pd.DataFrame([
        {
            'Lot': k,
            'Fichier': v.get('_source_file', 'N/A'),
            ' Methode': v.get('_extraction_meta', {}).get('method', 'N/A')
        }
        for k, v in st.session_state.all_parcels.items()
    ])
    st.dataframe(df, width='stretch')
    
    # Actions en masse
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Valider tous pour ML", type="primary"):
            count = 0
            for parcel_id, data in st.session_state.all_parcels.items():
                try:
                    extraction_id = data.get('_extraction_id')
                    if extraction_id:
                        extractor.validate_extraction_by_id(
                            extraction_id,
                            corrected_data=data
                        )
                        count += 1
                except Exception as e:
                    st.error(f"Erreur pour {parcel_id}: {e}")
            st.success(f"{count} lot(s) valide(s) pour ML!")
    
    with col2:
        if st.button("Effacer tous les resultats"):
            st.session_state.all_parcels = {}
            st.session_state.extracted_data = None
            st.rerun()
    
    with col3:
        if st.button("Rafraichir"):
            st.rerun()
    
    # Edition detaillee avec onglets
    st.markdown("#### Edition detaillee")
    
    parcel_ids = list(st.session_state.all_parcels.keys())
    
    # Creer les onglets pour chaque lot
    tabs = st.tabs([f"{pid}" for pid in parcel_ids])
    
    for i, (parcel_id, tab) in enumerate(zip(parcel_ids, tabs)):
        with tab:
            data = st.session_state.all_parcels[parcel_id]
            from ui.extraction_view import display_parcel_data
            edited = display_parcel_data(data.copy(), editable=True, key_prefix=f"batch_{parcel_id}_parcel_")
            
            # Stocker les modifications
            st.session_state.all_parcels[parcel_id] = edited
            
            # Boutons
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Sauvegarder", key=f'save_{parcel_id}'):
                    st.session_state.all_parcels[parcel_id] = edited
                    st.success(f"Sauvegarde pour {parcel_id}")
            with c2:
                if st.button(f"Valider pour ML", type="primary", key=f'val_{parcel_id}'):
                    try:
                        extraction_id = data.get('_extraction_id')
                        if extraction_id:
                            extractor.validate_extraction_by_id(extraction_id, corrected_data=edited)
                            st.success(f"{parcel_id} valide pour ML!")
                    except Exception as e:
                        st.error(f"Erreur: {e}")


def _run_extraction(extractor, temp_path: str):
    """Execute l'extraction et met a jour le session state."""
    from config import DEBUG_DIR, PHASE_PYMUPDF, PHASE_SUPER
    
    # Stocker le chemin du fichier pour permettre re-extraction
    st.session_state.last_uploaded_file = temp_path
    
    with st.spinner("Extraction en cours..."):
        try:
            # Verifier si on doit utiliser PyMuPDF ou SuperExtractor (both for PDFs)
            force_method = st.session_state.get('force_method')
            
            # Utiliser extract_from_pdf pour les fichiers PDF UNIQUEMENT si PyMuPDF ou Super est selectionne
            if temp_path.lower().endswith('.pdf') and force_method in [PHASE_PYMUPDF, PHASE_SUPER]:
                result = extractor.extract_from_pdf(temp_path)
            else:
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
            
            # Afficher la raison du fallback si present
            if 'fallback_reason' in meta:
                st.warning(f"Note: {meta['fallback_reason']}")

            # Debug OCR
            debug_text_path = DEBUG_DIR / 'extracted_text_debug.txt'
            if debug_text_path.exists():
                with st.expander("Texte OCR brut (debug)"):
                    with open(str(debug_text_path), 'r', encoding='utf-8') as f:
                        st.code(f.read())

        except Exception as e:
            st.error(f"Erreur lors de l'extraction: {str(e)}")
            st.exception(e)
