#!/usr/bin/env python
"""
CLI for extracting data from architectural plans and outputting clean JSON.
Uses SuperExtractor for extraction.

Supports:
- Single page PDFs
- Multi-page PDFs (returns first lot by default)
- Multi-lot PDFs with --all flag (returns all lots)
"""
import json
import sys
import argparse
import logging
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def setup_logging():
    """Disable all logging to output clean JSON only."""
    # Configure root logger to suppress everything BEFORE importing modules
    logging.basicConfig(
        level=logging.CRITICAL,
        handlers=[
            logging.NullHandler()
        ]
    )
    
    # Disable all existing loggers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add null handler
    root_logger.addHandler(logging.NullHandler())
    
    # Disable all module loggers
    for name in logging.Logger.manager.loggerDict.copy():
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logger.addHandler(logging.NullHandler())


# Setup logging before importing extractor
setup_logging()

from src.extractors.super_extractor import SuperExtractor


def extract_to_json(pdf_path: str, reference: str = None, extract_all: bool = False) -> dict:
    """
    Extract data from PDF and return clean JSON in parcel format.
    
    Args:
        pdf_path: Path to PDF file
        reference: Reference hint (optional)
        extract_all: If True, extract ALL lots from multi-page PDF
    
    Returns:
        Single dict for single lot, or dict with all lots for multi-page PDF
    """
    extractor = SuperExtractor()
    
    if extract_all:
        # Extract all pages/lots
        all_results = extractor.extract_all_pages(pdf_path, reference)
        
        if not all_results:
            return {"error": "No plans found in PDF"}
        
        # Convert all results to JSON format
        output = {}
        for ref, result in all_results.items():
            # Handle nested floor results (duplex/maison)
            if isinstance(result, dict):
                # This is a dict of floor results: {"A18_R+1": result1, "A18_R+2": result2}
                for floor_ref, floor_result in result.items():
                    if hasattr(floor_result, 'to_legacy_format'):
                        # to_legacy_format returns {ref: {...}}, extract inner dict
                        result_dict = floor_result.to_legacy_format()
                        # Get the inner dict using the reference as key
                        inner_key = floor_result.reference if floor_result.reference else floor_ref
                        if inner_key in result_dict:
                            parcel_data = _build_parcel_data(result_dict[inner_key])
                        else:
                            # Get first key if reference not found
                            first_key = list(result_dict.keys())[0]
                            parcel_data = _build_parcel_data(result_dict[first_key])
                    else:
                        # Already a dict
                        parcel_data = _build_parcel_data(floor_result)
                    parcel_data["floor"] = floor_ref
                    output[floor_ref] = parcel_data
            elif hasattr(result, 'to_legacy_format'):
                # to_legacy_format returns {ref: {...}}, extract inner dict
                result_dict = result.to_legacy_format()
                # Get the inner dict using the reference as key
                if ref in result_dict:
                    parcel_data = _build_parcel_data(result_dict[ref])
                else:
                    # Get first key if reference not found
                    first_key = list(result_dict.keys())[0]
                    parcel_data = _build_parcel_data(result_dict[first_key])
                output[ref] = parcel_data
            else:
                # Already a dict
                parcel_data = _build_parcel_data(result)
                output[ref] = parcel_data
        
        return output
    else:
        # Single extraction (default behavior)
        result = extractor.extract(pdf_path, reference)
        
        if hasattr(result, 'to_legacy_format'):
            result_dict = result.to_legacy_format()
        else:
            result_dict = result
        
        return _build_parcel_data(result_dict)


def _build_parcel_data(result) -> dict:
    """Build parcel data dict from extraction result (object or dict)."""
    # Handle both dict and object results
    if hasattr(result, 'reference'):
        # It's an ExtractionResult object
        ref = result.reference
        typology = result.typology
        floor = result.floor
        living_space = result.living_space
        rooms = result.rooms
        validation_errors = result.validation_errors
        validation_warnings = result.validation_warnings
    else:
        # It's a dict - check for different key formats
        ref = result.get('reference', '')
        typology = result.get('typology', '')
        floor = result.get('floor', '')
        
        # Handle living_space - can be string or float
        living_space = result.get('living_space', 0)
        if isinstance(living_space, str):
            try:
                living_space = float(living_space)
            except (ValueError, TypeError):
                living_space = 0
        
        # Handle rooms - can be in 'rooms' or 'surfaceDetail' (which is a dict, not list)
        rooms = result.get('rooms', [])
        if not rooms and 'surfaceDetail' in result:
            # surfaceDetail is a dict {name: surface}, convert to list format
            surface_detail_dict = result.get('surfaceDetail', {})
            rooms = []
            for name, surface in surface_detail_dict.items():
                rooms.append({
                    'name_normalized': name,
                    'surface': surface,
                    'room_type': 'UNKNOWN',
                    'is_exterior': False
                })
        
        validation_errors = result.get('validation_errors', result.get('_validation', {}).get('errors', []))
        validation_warnings = result.get('validation_warnings', result.get('_validation', {}).get('warnings', []))
    
    # Build clean JSON structure
    parcel_data = {
        "parcelLabel": ref or "",
        "parcelTypeId": result.get('parcelTypeId', 'appartment') if hasattr(result, 'get') else 'appartment',
        "parcelTypeLabel": result.get('parcelTypeLabel', 'Appartement') if hasattr(result, 'get') else 'Appartement',
        "orientation": result.get('orientation', '') if hasattr(result, 'get') else '',
        "typology": typology or "",
        "floor": floor or "",
        "price": "N.C",
        "living space": str(living_space) if living_space else "0",
        "surfaceDetail": _build_surface_detail(rooms),
        "option": _build_options(rooms, floor),
        "tva": "",
        "pinel": True,
        "customData": None,
        "state": "available",
        # Validation fields
        "validate": {
            "is_valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    
    return parcel_data


def _build_surface_detail(rooms: list) -> list:
    """Build surface detail array from rooms list."""
    surfaces = []
    for room in rooms:
        # Handle both dict and object rooms
        if isinstance(room, dict):
            name = room.get('name_normalized', room.get('name', ''))
            surface = room.get('surface', 0)
            room_type = room.get('room_type', '')
            if hasattr(room_type, 'name'):
                room_type = room_type.name
            is_exterior = room.get('is_exterior', False)
        else:
            name = room.name_normalized
            surface = room.surface
            room_type = room.room_type.name if hasattr(room.room_type, 'name') else str(room.room_type)
            is_exterior = room.is_exterior
        
        if not is_exterior:
            surfaces.append({
                "name": name,
                "surface": surface,
                "type": room_type
            })
    return surfaces


def _build_options(rooms: list, floor: str = None) -> dict:
    """Build options from extracted data."""
    # Check for exterior spaces - check both room_type and room name
    has_garden = False
    has_terrace = False
    has_balcony = False
    has_loggia = False
    has_garage = False
    has_parking = False
    
    for room in rooms:
        # Get room name and type
        if isinstance(room, dict):
            room_name = room.get('name_normalized', '').lower()
            room_type = room.get('room_type', '')
            if hasattr(room_type, 'name'):
                room_type = room_type.name
        else:
            room_name = getattr(room, 'name_normalized', '').lower()
            room_type = room.room_type.name if hasattr(room.room_type, 'name') else str(room.room_type)
        
        # Check room_type first
        if room_type == "GARDEN":
            has_garden = True
        elif room_type in ["TERRACE", "PORCHE"]:
            has_terrace = True
        elif room_type == "BALCONY":
            has_balcony = True
        elif room_type == "LOGGIA":
            has_loggia = True
        elif room_type == "GARAGE":
            has_garage = True
        elif room_type == "PARKING":
            has_parking = True
        
        # Also check room name for common exterior terms
        if not has_garden and ('jardin' in room_name or 'garden' in room_name):
            has_garden = True
        if not has_terrace and ('terrasse' in room_name or 'terrace' in room_name):
            has_terrace = True
        if not has_balcony and ('balcon' in room_name or 'balcony' in room_name):
            has_balcony = True
        if not has_loggia and ('loggia' in room_name):
            has_loggia = True
        if not has_garage and ('garage' in room_name):
            has_garage = True
        if not has_parking and ('parking' in room_name or 'place' in room_name):
            has_parking = True
    
    # Check if duplex (multiple floors)
    is_duplex = False
    if floor:
        floor_upper = floor.upper()
        is_duplex = ("RDC" in floor_upper and "+1" in floor_upper) or \
                    ("," in floor) or ("/" in floor)
    
    return {
        "balcony": has_balcony,
        "terrace": has_terrace,
        "garden": has_garden,
        "parking": has_parking,
        "winter garden": False,
        "garage": has_garage,
        "loggia": has_loggia,
        "duplex": is_duplex
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract architectural plan data to clean JSON"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file to extract"
    )
    parser.add_argument(
        "-r", "--reference",
        help="Reference/Lot number (optional)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (optional, prints to stdout if not specified)"
    )
    parser.add_argument(
        "-p", "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all logging output"
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Extract ALL lots from multi-page PDF (returns dict with all lots)"
    )
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.pdf_path).exists():
        print(f"Error: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Extract data
        parcel_data = extract_to_json(args.pdf_path, args.reference, args.all)
        
        # Output JSON
        indent = 4 if args.pretty else None
        json_output = json.dumps(parcel_data, indent=indent, ensure_ascii=False)
        
        if args.output:
            Path(args.output).write_text(json_output, encoding="utf-8")
            print(f"Output written to: {args.output}")
        else:
            print(json_output)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
