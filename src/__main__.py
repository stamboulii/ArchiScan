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


def split_pdf(input_pdf: str, output_dir: str, verbose: bool = False):
    """Diviser un PDF en pages individuelles.
    
    Args:
        input_pdf: Chemin vers le fichier PDF source
        output_dir: Repertoire de sortie pour les pages
        verbose: Mode verbeux
    """
    import fitz
    
    input_path = Path(input_pdf)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"Erreur: Fichier introuvable: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    with fitz.open(input_path) as doc:
        page_count = doc.page_count
        for page_index in range(page_count):
            new_pdf = fitz.open()
            new_pdf.insert_pdf(doc, from_page=page_index, to_page=page_index)

            file_name = output_path / f"{input_path.stem}_page_{page_index + 1}.pdf"
            new_pdf.save(str(file_name))
            new_pdf.close()
            
            if verbose:
                print(f"  - Page {page_index + 1}: {file_name.name}")

    print(f"[OK] Extraction terminee: {page_count} pages creees dans '{output_path}'")


def batch_process_files(paths: list, args):
    """Traiter plusieurs fichiers en mode batch.
    
    Args:
        paths: Liste de fichiers ou repertoires a traiter
        args: Arguments parses
    """
    import time
    from pathlib import Path
    
    # Collecter tous les fichiers a traiter
    files_to_process = []
    
    for path_str in paths:
        path = Path(path_str)
        if path.is_dir():
            # Ajouter tous les fichiers PDF/images du repertoire
            for ext in ['*.pdf', '*.png', '*.jpg', '*.jpeg']:
                files_to_process.extend(path.glob(ext))
        elif path.is_file():
            files_to_process.append(path)
    
    if not files_to_process:
        print("Erreur: Aucun fichier a traiter", file=sys.stderr)
        sys.exit(1)
    
    # Configuration du logging
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
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.setLevel(logging.WARNING)
    
    # Determiner le repertoire de sortie
    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Importer l'extracteur
    try:
        from .extractors.hybrid_extractor import HybridExtractor
        from .extractors.super_extractor.super_extractor import SuperExtractor
        
        extractor = HybridExtractor()
        super_extractor = SuperExtractor()
        
        if args.method == 'super':
            method = 'super'
        else:
            method = args.method
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
    except ImportError as e:
        print(f"Erreur d'importation: {e}", file=sys.stderr)
        print("Assurez-vous que les dependencies sont installees.", file=sys.stderr)
        sys.exit(1)
    
    # Traiter chaque fichier
    results = []
    start_time = time.time()
    
    print(f"[BATCH] Traitement de {len(files_to_process)} fichier(s)...")
    
    for i, file_path in enumerate(files_to_process, 1):
        if not args.quiet:
            print(f"  [{i}/{len(files_to_process)}] {file_path.name}...", end=' ', flush=True)
        
        try:
            if args.method == 'super':
                # Use SuperExtractor
                is_multipage = False
                if str(file_path).lower().endswith('.pdf'):
                    try:
                        import fitz
                        doc = fitz.open(str(file_path))
                        is_multipage = len(doc) > 1
                        doc.close()
                    except:
                        pass
                
                if is_multipage:
                    all_results = super_extractor.extract_all_pages(str(file_path))
                    combined = {}
                    for ref, result in all_results.items():
                        combined.update(result.to_legacy_format(include_raw_text=False))
                    file_result = combined
                else:
                    result = super_extractor.extract(str(file_path))
                    file_result = result.to_legacy_format(include_raw_text=False)
            else:
                # Use HybridExtractor
                file_result = extractor.extract(str(file_path))
            
            result_entry = {
                'file': str(file_path),
                'success': True,
                'data': file_result
            }
            
            if not args.quiet:
                print("OK")
            
            # Sauvegarder si output specifie
            if output_dir:
                output_file = output_dir / f"{file_path.stem}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(file_result, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            result_entry = {
                'file': str(file_path),
                'success': False,
                'error': str(e)
            }
            
            if not args.quiet:
                print(f"ERREUR: {e}")
        
        results.append(result_entry)
    
    total_time = time.time() - start_time
    
    # Resumer
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    if not args.quiet:
        print(f"\n[BATCH] Termine!")
        print(f"  Total: {len(results)} fichier(s)")
        print(f"  Reussis: {successful}")
        print(f"  Echecs: {failed}")
        print(f"  Temps: {total_time:.2f}s")
    
    # Sauvegarder le rapport JSON
    if output_dir:
        report = {
            'summary': {
                'total': len(results),
                'successful': successful,
                'failed': failed,
                'processing_time_seconds': total_time
            },
            'results': results
        }
        report_file = output_dir / 'batch_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        if not args.quiet:
            print(f"  Rapport: {report_file}")
    
    # Afficher le JSON selon le format specifie
    if args.format == 'data':
        # Afficher uniquement les donnees extraites
        for r in results:
            if r.get('success'):
                print(json.dumps(r.get('data', {}), indent=2, ensure_ascii=False))
    elif args.format == 'quiet':
        # Format minimal
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif not args.output:
        # Pas de fichier de sortie specifie, afficher a l'ecran
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.quiet:
        print(json.dumps(results, indent=2, ensure_ascii=False))


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
    python -m src --split pdfExample/A008.pdf --output output_pages
    python -m src --batch dir_with_pdfs/ --method super
    python -m src --batch file1.pdf file2.pdf --output results/
        """
    )
    
    # Split mode flag
    parser.add_argument(
        '--split', '-s',
        action='store_true',
        help='Diviser le PDF en pages individuelles'
    )
    
    # Batch mode flag
    parser.add_argument(
        '--batch', '-b',
        nargs='+',
        help='Traiter plusieurs fichiers ou un repertoire (batch mode)'
    )
    
    # Output format for batch mode
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'data', 'quiet'],
        default='json',
        help='Format de sortie: json (complet), data (donnees uniquement), quiet (minimal)'
    )
    
    # For split mode: input PDF (optional positional)
    parser.add_argument('input_pdf', nargs='?', help='Chemin vers le fichier PDF source')
    parser.add_argument(
        '--method', '-m',
        choices=['auto', 'tesseract', 'claude', 'super'],
        default='auto',
        help='Methode d\'extraction (defaut: auto)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Fichier de sortie JSON ou repertoire pour split'
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
    
    # Handle batch mode
    if args.batch:
        batch_process_files(args.batch, args)
        sys.exit(0)
    
    # Handle split mode with flag
    if args.split:
        if not args.input_pdf:
            print("Erreur: Veuillez specifier un fichier PDF a diviser", file=sys.stderr)
            sys.exit(1)
        output_dir = args.output if args.output else 'output_pages'
        split_pdf(args.input_pdf, output_dir, args.verbose)
        sys.exit(0)
    
    # Otherwise, use the original extraction logic
    if not args.input_pdf:
        parser.print_help()
        print("\nPour lancer l'interface Streamlit:")
        print("    streamlit run streamlit_app.py")
        sys.exit(1)
    
    image_path = Path(args.input_pdf)
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
            import fitz
            
            super_extractor = SuperExtractor()
            
            # Verifier si c'est un PDF multi-pages
            is_multipage = False
            if str(image_path).lower().endswith('.pdf'):
                try:
                    doc = fitz.open(str(image_path))
                    is_multipage = len(doc) > 1
                    doc.close()
                except:
                    pass
            
            if is_multipage:
                # Extraire toutes les pages
                all_results = super_extractor.extract_all_pages(str(image_path))
                
                if not all_results:
                    print(json.dumps({"error": "Aucun plan detecte"}, indent=2))
                    sys.exit(1)
                
                # Combiner tous les resultats en un seul JSON
                combined = {}
                for ref, result in all_results.items():
                    combined.update(result.to_legacy_format(include_raw_text=False))
                
                output = json.dumps(combined, indent=2, ensure_ascii=False)
            else:
                result = super_extractor.extract(str(image_path))
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
