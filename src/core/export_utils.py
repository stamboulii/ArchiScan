"""
Export Utilities - Export vers Excel/CSV
======================================

Fonctions pour exporter les donnees extraites:
- JSON (deja supporte)
- CSV
- Excel (XLSX)
- Excel multi-feuille (un lot par feuille)
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Aplatit un dict imbrique pour l'export CSV.
    
    Args:
        d: Dict a aplatir
        parent_key: Cle parente pour la recursion
        sep: Separateur entre les cles
        
    Returns:
        Dict aplati
    """
    items = {}
    
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, sep))
        elif isinstance(value, list):
            # Convertir les listes en strings
            items[new_key] = ', '.join(str(v) for v in value) if value else ''
        else:
            items[new_key] = value
    
    return items


def export_to_csv(
    data: Dict[str, Dict],
    output_path: str,
    include_metadata: bool = True,
) -> str:
    """
    Exporte les donnees vers un fichier CSV.
    
    Args:
        data: Dict {lot_id: parcel_data}
        output_path: Chemin du fichier CSV de sortie
        include_metadata: Inclure les metadonnees
            
    Returns:
        Chemin du fichier cree
    """
    output_path = Path(output_path)
    
    # Verifier qu'il y a des donnees
    if not data:
        logger.warning("Aucune donnee a exporter")
        return ""
    
    # Preparer les lignes
    rows = []
    flat_fields = set()
    
    for lot_id, parcel_data in data.items():
        # Aplatir les donnees du lot
        flat_data = flatten_dict(parcel_data)
        flat_data['lot_id'] = lot_id
        rows.append(flat_data)
        
        # Collecter tous les champs
        flat_fields.update(flat_data.keys())
    
    # Ordonner les champs (lot_id en premier)
    fieldnames = ['lot_id'] + sorted([f for f in flat_fields if f != 'lot_id'])
    
    # Ecrire le CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"CSV export: {output_path}")
    
    return str(output_path)


def export_to_excel(
    data: Dict[str, Dict],
    output_path: str,
    sheet_name: str = "Lots",
    include_metadata: bool = True,
) -> str:
    """
    Exporte les donnees vers un fichier Excel (XLSX).
    
    Args:
        data: Dict {lot_id: parcel_data}
        output_path: Chemin du fichier Excel de sortie
        sheet_name: Nom de la feuille
        include_metadata: Inclure les metadonnees
            
    Returns:
        Chemin du fichier cree
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.error(
            "openpyxl requis pour l'export Excel. "
            "Installez-le: pip install openpyxl"
        )
        raise ImportError(
            "openpyxl n'est pas installe. "
            "Pour l'export Excel: pip install openpyxl"
        )
    
    output_path = Path(output_path)
    
    if not data:
        logger.warning("Aucune donnee a exporter")
        return ""
    
    # Creer le workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    
    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center", wrap_text=True)
    
    # Preparer les donnees
    rows = []
    flat_fields = set()
    
    for lot_id, parcel_data in data.items():
        flat_data = flatten_dict(parcel_data)
        flat_data['lot_id'] = lot_id
        rows.append(flat_data)
        flat_fields.update(flat_data.keys())
    
    # Ordonner les champs
    fieldnames = ['lot_id'] + sorted([f for f in flat_fields if f != 'lot_id'])
    
    # Ecrire les headers
    for col, field in enumerate(fieldnames, 1):
        cell = ws.cell(row=1, column=col, value=field)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
    
    # Ecrire les donnees
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, field in enumerate(fieldnames, 1):
            value = row_data.get(field, '')
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(horizontal="left")
    
    # Ajuster la largeur des colonnes
    for col_idx, field in enumerate(fieldnames, 1):
        max_width = max(len(str(field)), 15)  # Minimum 15
        ws.column_dimensions[get_column_letter(col_idx)].width = max_width
    
    # Sauvegarder
    wb.save(str(output_path))
    
    logger.info(f"Excel export: {output_path}")
    
    return str(output_path)


def export_multi_sheet(
    data: Dict[str, Dict],
    output_path: str,
    lot_per_sheet: bool = True,
) -> str:
    """
    Exporte les donnees vers un Excel multi-feuille.
    
    Args:
        data: Dict {lot_id: parcel_data}
        output_path: Chemin du fichier Excel de sortie
        lot_per_sheet: Un lot par feuille (sinon toutes les donnees sur une feuille)
        
    Returns:
        Chemin du fichier cree
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError("openpyxl requis. pip install openpyxl")
    
    output_path = Path(output_path)
    
    if not data:
        logger.warning("Aucune donnee a exporter")
        return ""
    
    wb = openpyxl.Workbook()
    
    if lot_per_sheet:
        # Creer une feuille par lot
        ws_index = wb.create_sheet("Index")
        ws_index.cell(row=1, column=1, value="Lot ID")
        ws_index.cell(row=1, column=2, value="Feuille")
        
        row_idx = 2
        for lot_id, parcel_data in sorted(data.items()):
            # Creer la feuille pour ce lot
            safe_name = lot_id[:31]  # Excel limite a 31 caracteres
            ws = wb.create_sheet(safe_name)
            
            # Ecrire les donnees
            row = 1
            for key, value in sorted(parcel_data.items()):
                if isinstance(value, dict):
                    # Sous-dict
                    ws.cell(row=row, column=1, value=f"{key} (dict)")
                    for sub_key, sub_value in sorted(value.items()):
                        ws.cell(row=row, column=2, value=sub_key)
                        ws.cell(row=row, column=3, value=str(sub_value))
                        row += 1
                elif isinstance(value, list):
                    ws.cell(row=row, column=1, value=f"{key} (list)")
                    ws.cell(row=row, column=2, value=', '.join(str(v) for v in value))
                    row += 1
                else:
                    ws.cell(row=row, column=1, value=key)
                    ws.cell(row=row, column=2, value=str(value))
                row += 1
            
            # Ajouter a l'index
            ws_index.cell(row=row_idx, column=1, value=lot_id)
            ws_index.cell(row=row_idx, column=2, value=safe_name)
            row_idx += 1
    else:
        # Toutes les donnees sur une seule feuille
        ws = wb.active
        ws.title = "Tous les lots"
        
        # Flatten et preparer
        rows = []
        all_fields = set()
        
        for lot_id, parcel_data in data.items():
            flat_data = flatten_dict(parcel_data)
            flat_data['lot_id'] = lot_id
            rows.append(flat_data)
            all_fields.update(flat_data.keys())
        
        fieldnames = ['lot_id'] + sorted([f for f in all_fields if f != 'lot_id'])
        
        # Headers
        for col, field in enumerate(fieldnames, 1):
            ws.cell(row=1, column=col, value=field)
        
        # Donnees
        for row_idx, row_data in enumerate(rows, 2):
            for col_idx, field in enumerate(fieldnames, 1):
                ws.cell(row=row_idx, column=col_idx, value=str(row_data.get(field, '')))
    
    wb.save(str(output_path))
    
    logger.info(f"Multi-sheet Excel export: {output_path}")
    
    return str(output_path)


def export_summary(
    data: Dict[str, Dict],
    output_path: str,
    format: str = "txt",
) -> str:
    """
    Exporte un resume textuel des lots.
    
    Args:
        data: Dict {lot_id: parcel_data}
        output_path: Chemin du fichier de sortie
        format: Format de sortie ('txt' ou 'md')
        
    Returns:
        Chemin du fichier cree
    """
    output_path = Path(output_path)
    
    if not data:
        return ""
    
    lines = []
    
    if format == "md":
        lines.append("# Resume des Lots\n")
        lines.append(f"Total: {len(data)} lots\n\n")
        lines.append("| Lot | Type | Etage | Surface | Prix | Statut |")
        lines.append("|-----|------|-------|---------|------|--------|")
    
    for lot_id, parcel_data in sorted(data.items()):
        typology = parcel_data.get('typology', 'N.C')
        floor = parcel_data.get('floor', 'N.C')
        living_space = parcel_data.get('living_space', 'N.C')
        price = parcel_data.get('price', 'N.C')
        state = parcel_data.get('state', 'available')
        
        if format == "md":
            lines.append(f"| {lot_id} | {typology} | {floor} | {living_space} m² | {price} | {state} |")
        else:
            lines.append(f"[{lot_id}] {typology} - {floor} - {living_space} m² - {price} - {state}")
    
    content = '\n'.join(lines)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Summary export ({format}): {output_path}")
    
    return str(output_path)


def detect_export_format(output_path: str) -> str:
    """
    Detecte le format d'export a partir de l'extension.
    
    Returns:
        'csv', 'excel', 'multi', 'summary', 'json', ou 'auto'
    """
    path = Path(output_path)
    suffix = path.suffix.lower()
    
    format_map = {
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.json': 'json',
        '.txt': 'summary',
        '.md': 'summary',
    }
    
    return format_map.get(suffix, 'json')


def auto_export(
    data: Dict[str, Dict],
    output_path: str,
    multi_sheet: bool = False,
) -> str:
    """
    Exporte automatiquement selon l'extension du fichier.
    
    Args:
        data: Dict {lot_id: parcel_data}
        output_path: Chemin du fichier de sortie
        multi_sheet: Pour Excel, creer plusieurs feuilles
            
    Returns:
        Chemin du fichier cree
    """
    format = detect_export_format(output_path)
    
    if format == 'csv':
        return export_to_csv(data, output_path)
    elif format == 'excel':
        if multi_sheet:
            return export_multi_sheet(data, output_path)
        return export_to_excel(data, output_path)
    elif format == 'summary':
        suffix = Path(output_path).suffix.lower()
        return export_summary(data, output_path, format='md' if suffix == '.md' else 'txt')
    else:
        # JSON par defaut
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON export: {output_path}")
        return output_path


if __name__ == "__main__":
    # Test basique
    test_data = {
        "A001": {
            "parcelLabel": "A001",
            "typology": "T2",
            "floor": "RDC",
            "living_space": "41.72",
            "price": "185000",
            "state": "available",
            "surfaceDetail": {"terrasse": 7.49},
            "option": {"terrasse": True, "parking": False}
        },
        "B002": {
            "parcelLabel": "B002",
            "typology": "T3",
            "floor": "R+1",
            "living_space": "65.50",
            "price": "250000",
            "state": "reserved",
            "surfaceDetail": {"balcon": 8.0},
            "option": {"balcony": True, "parking": True}
        }
    }
    
    # Test CSV
    export_to_csv(test_data, "test_export.csv")
    
    # Test Excel
    try:
        export_to_excel(test_data, "test_export.xlsx")
        export_multi_sheet(test_data, "test_export_multi.xlsx")
    except ImportError:
        print("openpyxl non installe, skips Excel tests")
    
    # Test Summary
    export_summary(test_data, "test_export.md", format="md")
    
    print("Tests d'export termines")
