"""
Dashboard d'entrainement ML : statistiques, progression et export.
"""

import streamlit as st
import pandas as pd
from pathlib import Path

from config import TEMP_DIR


def render_training_dashboard(extractor):
    """
    Rendu du dashboard d'entrainement ML.
    Affiche les metriques, la progression et les extractions recentes.

    Args:
        extractor: Instance de HybridExtractor
    """
    st.markdown("---")
    st.subheader("Dashboard d'entrainement ML")

    try:
        stats = extractor.get_statistics()

        _display_metrics(stats)
        _display_progress(stats)
        _display_training_action(stats, extractor)
        _display_recent_extractions()

    except Exception as e:
        st.warning(f"Dashboard indisponible: {e}")


def _display_metrics(stats: dict):
    """Affiche les metriques principales."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total extractions", stats['total_extractions'])
    with col2:
        st.metric("Validees", stats['validated_count'])
    with col3:
        st.metric("Via Claude", stats['claude_count'])
    with col4:
        st.metric("Via Tesseract", stats['tesseract_count'])


def _display_progress(stats: dict):
    """Affiche la barre de progression vers l'entrainement ML."""
    progress = stats['progress_percent'] / 100.0
    st.progress(progress)


def _display_training_action(stats: dict, extractor):
    """Affiche le bouton d'export ou le message de progression."""
    if stats['ready_for_training']:
        st.success(
            f"Pret pour l'entrainement ML! "
            f"{stats['validated_count']} echantillons valides disponibles."
        )
        if st.button("Exporter les donnees d'entrainement"):
            _export_training_data(extractor)
    else:
        remaining = stats['min_samples_needed'] - stats['validated_count']
        st.info(
            f"Encore {remaining} extractions validees necessaires "
            f"avant l'entrainement ML ({stats['progress_percent']:.1f}%)"
        )


def _export_training_data(extractor):
    """Exporte les donnees d'entrainement pour le modele ML."""
    try:
        from ml_trainer import MLTrainer
        trainer = MLTrainer()
        training_data = st.session_state.data_store.get_training_data()
        result = trainer.export_dataset(
            training_data,
            str(Path(TEMP_DIR) / "training_export")
        )
        st.success(
            f"{result['exported_count']} echantillons exportes vers "
            f"{result['output_path']}"
        )
    except ImportError:
        st.error("Module ml_trainer non disponible. Verifiez l'installation.")
    except Exception as e:
        st.error(f"Erreur lors de l'export: {e}")


def _display_recent_extractions():
    """Affiche les extractions recentes dans un expander."""
    with st.expander("Extractions recentes"):
        try:
            recent = st.session_state.data_store.get_recent_extractions(limit=10)
            if recent:
                df_recent = pd.DataFrame(recent)
                df_recent['validated'] = df_recent['validated_by_user'].map(
                    {0: 'Non', 1: 'Oui'}
                )
                df_recent['confidence'] = df_recent['confidence'].apply(
                    lambda x: f"{x:.0%}" if x is not None else "-"
                )
                st.dataframe(
                    df_recent[['id', 'extraction_method', 'confidence', 'validated', 'created_at']],
                    column_config={
                        'id': 'ID',
                        'extraction_method': 'Methode',
                        'confidence': 'Confiance',
                        'validated': 'Validee',
                        'created_at': 'Date',
                    }
                )
            else:
                st.info("Aucune extraction recente")
        except Exception as e:
            st.warning(f"Impossible de charger les extractions recentes: {e}")
