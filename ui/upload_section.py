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
                        
                        # Utiliser extract_from_pdf pour les fichiers PDF UNIQUEMENT si PyMuPDF ou Super est selectionne
                        if temp_path.lower().endswith('.pdf') and force_method in ['pymupdf', 'super']:
                            result = extractor.extract_from_pdf(temp_path, force_method=force_method)
                        else:
                            result = extractor.extract_from_image(temp_path)
                        
                        # Aplatir les donnees si necessaire
                        has_nested_data = False
                        if result and len(result) > 0:
                            for key in list(result.keys()):
                                if isinstance(result[key], dict):
                                    # Verifier si c'est une cle de type reference
                                    if key.startswith('LOT_') or (len(key) <= 4 and key[0].isalpha()):
                                        nested_data = result[key]
                                        result = nested_data.copy()
                                        result['_extraction_meta'] = {'method': force_method or 'unknown'}
                                        if '_validation' not in result:
                                            result['_validation'] = {'is_valid': True, 'errors': [], 'warnings': []}
                                        has_nested_data = True
                                        break
                            
                            # Si aucune donnee imbriquee trouveee, verifier si deja aplatie
                            if not has_nested_data:
                                if 'parcelLabel' not in result and 'typology' not in result:
                                    # Format different - creer lot par defaut
                                    result = {
                                        'parcelLabel': f'LOT_{i+1:03d}',
                                        'typology': '',
                                        'floor': '',
                                        'orientation': '',
                                        'living_space': '',
                                        'price': 'N.C',
                                        'surfaceDetail': {},
                                        'option': {},
                                        '_extraction_meta': {'method': force_method or 'unknown'}
                                    }
                        
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
            
            logger.info(f"_run_extraction: force_method={force_method}, temp_path={temp_path}")
            
            # Utiliser extract_from_pdf pour les fichiers PDF UNIQUEMENT si PyMuPDF ou Super est selectionne
            if temp_path.lower().endswith('.pdf') and force_method in [PHASE_PYMUPDF, PHASE_SUPER]:
                result = extractor.extract_from_pdf(temp_path, force_method=force_method)
            else:
                result = extractor.extract_from_image(temp_path)

            logger.info(f"Result keys after extraction: {list(result.keys())}")

            st.session_state.extracted_data = result
            
            # Detecter si c'est un resultat multi-pages (plusieurs references)
            plan_refs = [k for k in result.keys()
                        if isinstance(result[k], dict) and
                        (k.startswith('LOT_') or k.startswith('PAGE_') or
                         (len(k) <= 5 and k[0].isalpha() and not k.startswith('_')))]
            
            if len(plan_refs) > 1:
                # Multi-pages: ajouter tous les plans a la collection
                logger.info(f"Multi-pages detecte: {len(plan_refs)} plans")
                for ref in plan_refs:
                    nested_data = result[ref]
                    parcel_data = nested_data.copy()
                    parcel_data['parcelLabel'] = ref
                    parcel_data['_extraction_meta'] = result.get('_extraction_meta', {'method': force_method or 'super'})
                    if '_validation' in nested_data:
                        parcel_data['_validation'] = nested_data['_validation']
                    st.session_state.all_parcels[ref] = parcel_data
                
                # Afficher le premier plan comme donnees courantes
                first_ref = plan_refs[0]
                st.session_state.extracted_data = st.session_state.all_parcels[first_ref]
                
            elif len(plan_refs) == 1:
                # Un seul plan: aplatir
                key = plan_refs[0]
                nested_data = result[key]
                logger.info(f"Flattening key: {key}")
                st.session_state.extracted_data = nested_data.copy()
                st.session_state.extracted_data['_extraction_meta'] = result.get('_extraction_meta', {'method': force_method or 'super'})
                
                # Ajouter _validation - TOUJOURS
                if '_validation' in nested_data:
                    st.session_state.extracted_data['_validation'] = nested_data['_validation']
                    logger.info(f"_validation trouve: {nested_data['_validation']}")
                else:
                    st.session_state.extracted_data['_validation'] = {
                        'is_valid': True,
                        'errors': [],
                        'warnings': []
                    }
                    logger.info("_validation non trouve, utilisation du defaut")
                
                # Ajout a la collection
                parcel_id = st.session_state.extracted_data.get('parcelLabel', key)
                st.session_state.all_parcels[parcel_id] = st.session_state.extracted_data
            
            else:
                # Pas de cle de type reference trouvee - les donnees sont peut-etre deja aplaties
                # ou c'est un format different. On les stocke telles quelles.
                logger.info(f"Aucune cle de reference trouvee. Keys disponibles: {list(result.keys())}")
                
                # Verifier si les donnees ont deja les champs attendus (donnees deja aplaties)
                if 'parcelLabel' in result or 'typology' in result:
                    st.session_state.extracted_data = result
                    parcel_id = result.get('parcelLabel', 'UNKNOWN')
                    st.session_state.all_parcels[parcel_id] = result
                else:
                    # C'est un format different - creer un lot par defaut
                    st.session_state.extracted_data = {
                        'parcelLabel': 'LOT_001',
                        'typology': '',
                        'floor': '',
                        'orientation': '',
                        'living_space': '',
                        'price': 'N.C',
                        'surfaceDetail': {},
                        'option': {},
                        '_extraction_meta': {'method': force_method or 'unknown'}
                    }
                    st.session_state.all_parcels['LOT_001'] = st.session_state.extracted_data
            
            st.session_state.last_extraction_id = result.get('_extraction_id')

            # Message de succes avec methode
            from ui.styles import METHOD_LABELS
            meta = result.get('_extraction_meta', {})
            method = meta.get('method', 'inconnu')
            
            # Afficher le nombre de plans si multi-pages
            pages_count = meta.get('pages_count', 0)
            if pages_count > 1:
                st.success(
                    f"Extraction reussie via {METHOD_LABELS.get(method, method)}! "
                    f"({pages_count} plans trouves)"
                )
            else:
                st.success(
                    f"Extraction reussie via {METHOD_LABELS.get(method, method)}!"
                )
            
            # Afficher la raison du fallback si present
            if 'fallback_reason' in meta:
                st.warning(f"Note: {meta['fallback_reason']}")

            # Debug OCR - afficher le texte brut et la validation de l'extraction
            raw_text = st.session_state.extracted_data.get('_raw_text', '')
            validation = st.session_state.extracted_data.get('_validation', {})
            
            # Afficher validation en premier (plus importante)
            if validation:
                with st.expander("Validation et Texte OCR (debug)"):
                    st.subheader("Validation")
                    is_valid = validation.get('is_valid', False)
                    if is_valid:
                        st.success("✓ Extraction valide")
                    else:
                        st.error("✗ Extraction invalide")
                        
                    errors = validation.get('errors', [])
                    if errors:
                        st.markdown("**Erreurs:**")
                        for err in errors:
                            st.markdown(f"- {err}")
                            
                    warnings = validation.get('warnings', [])
                    if warnings:
                        st.markdown("**Avertissements:**")
                        for warn in warnings:
                            st.markdown(f"- {warn}")
                    
                    st.markdown("---")
                    st.subheader("Texte OCR brut")
                    if raw_text:
                        st.code(raw_text, language='text')
                    else:
                        st.write("*Aucun texte OCR disponible*")
            elif raw_text:
                # Fallback: seulement le texte OCR
                with st.expander("Texte OCR brut (debug)"):
                    st.code(raw_text, language='text')

        except Exception as e:
            st.error(f"Erreur lors de l'extraction: {str(e)}")
            st.exception(e)
