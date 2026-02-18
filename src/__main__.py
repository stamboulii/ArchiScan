"""
ArchiExtract - Point d'entree principal
=======================================
"""

# ============================================
# CONFIGURER LE LOGGING AVANT TOUT IMPORT
# ============================================
import sys
import logging

# Creer un logger null pour eviter les logs par defaut
logging.basicConfig(
    level=logging.CRITICAL,
    handlers=[logging.NullHandler()]
)

# Maintenant on peut continuer avec les imports normaux
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
    python -m src pdfExample/A008.pdf
    python -m src pdfExample/A008.pdf --method super
    python -m src pdfExample/A008.pdf --method super -v
    python -m src --help
        """
    )
    
    parser.add_argument('image', nargs='?', help='Chemin vers l\'image du plan')
    parser.add_argument(
        '--method', '-m',
        choices=['auto', 'tesseract', 'claude', 'super'],
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
        help='Mode verbeux (affiche tous les logs)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Mode silencieux: affiche uniquement le JSON'
    )
    
    args = parser.parse_args()
    
    if not args.image:
        parser.print_help()
        print("\nPour lancer l'interface Streamlit:")
        print("    streamlit run streamlit_app.py")
        sys.exit(1)
    
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Erreur: Fichier introuvable: {image_path}", file=sys.stderr)
        sys.exit(1)
    
    # Configuration du logging APRES les imports
    # Supprimer le handler null et reconfigurer
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    if args.verbose:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    elif args.quiet:
        root_logger.addHandler(logging.NullHandler())
        root_logger.setLevel(logging.CRITICAL)
    else:
        # Par defaut: WARNING uniquement
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.WARNING)
    
    # Importation dynamique pour eviter les erreurs si les deps manquent
    try:
        from .extractors.hybrid_extractor import HybridExtractor
        
        extractor = HybridExtractor()
        
        if args.method == 'super':
            # Use SuperExtractor for better PDF extraction
            from .extractors.super_extractor.super_extractor import SuperExtractor
            from .extractors.super_extractor.models import ExtractionResult
            
            super_extractor = SuperExtractor()
            result = super_extractor.extract(str(image_path))
            
            # Use legacy format which handles serialization properly
            # include_raw_text=False pour eviter d'afficher le texte brut dans la CLI
            output = json.dumps(result.to_legacy_format(include_raw_text=False), indent=2, ensure_ascii=False)
            print(output)
            
            # Sauvegarde si demande
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                if not args.quiet:
                    print(f"\nResultat sauvegarde dans: {args.output}")
            sys.exit(0)
        
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
        if not args.quiet:
            print(f"\nResultat sauvegarde dans: {args.output}")


if __name__ == "__main__":
    main()
