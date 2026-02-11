"""
ArchiExtract - Point d'entree principal
=======================================

Usage:
    python -m archiextract <image_path>
    python -m archiextract --help
    
    streamlit run archiextract.ui.streamlit_app
"""

import sys
import json
import argparse
from pathlib import Path


def main():
    """Point d'entree principal."""
    parser = argparse.ArgumentParser(
        description="ArchiExtract - Extraction automatique de donnees depuis les plans d'architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
    python -m archiextract plan.png
    python -m archiextract plan.png --method claude
    python -m archiextract --help
        """
    )
    
    parser.add_argument('image', nargs='?', help='Chemin vers l\'image du plan')
    parser.add_argument(
        '--method', '-m',
        choices=['auto', 'tesseract', 'claude'],
        default='auto',
        help='Methode d\'extraction (defaut: auto)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Fichier de sortie JSON'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mode verbeux'
    )
    
    args = parser.parse_args()
    
    if not args.image:
        parser.print_help()
        print("\nPour lancer l'interface Streamlit:")
        print("    streamlit run archiextract.ui.streamlit_app")
        sys.exit(1)
    
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Erreur: Fichier introuvable: {image_path}", file=sys.stderr)
        sys.exit(1)
    
    # Configuration du logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO)
    
    # Importation dynamique pour eviter les erreurs si les deps manquent
    try:
        from .extractors.hybrid_extractor import HybridExtractor
        
        extractor = HybridExtractor()
        
        if args.method != 'auto':
            from .core.config import (
                PHASE_TESSERACT,
                PHASE_CLAUDE,
                PHASE_AUTO,
            )
            method_map = {
                'tesseract': PHASE_TESSERACT,
                'claude': PHASE_CLAUDE,
                'auto': PHASE_AUTO,
            }
            extractor.force_method = method_map.get(args.method)
        
        result = extractor.extract(str(image_path))
        
    except ImportError as e:
        print(f"Erreur d'importation: {e}", file=sys.stderr)
        print("Assurez-vous que les dependencies sont installees.", file=sys.stderr)
        sys.exit(1)
    
    # Affichage
    output = json.dumps(result, indent=2, ensure_ascii=False)
    print(output)
    
    # Sauvegarde si demande
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\nResultat sauvegarde dans: {args.output}")


if __name__ == "__main__":
    main()
