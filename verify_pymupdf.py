
import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.extractors.hybrid_extractor import HybridExtractor, PHASE_PYMUPDF

def test_extraction(pdf_path):
    print(f"Testing extraction on: {pdf_path}")
    
    # Initialize extractor with PyMuPDF forced
    extractor = HybridExtractor(force_method=PHASE_PYMUPDF)
    
    try:
        # Run extraction
        if pdf_path.lower().endswith('.pdf'):
             result = extractor.extract_from_pdf(pdf_path)
             raw_text = result.get('_raw_text', '')
             print(f"\n--- Extracted Data ---")
             print(f"Parcel Label: {result.get('parcelLabel')}")
             print(f"Typology: {result.get('typology')}")
             
             import re
             matches = re.findall(r"CHAMBRE\s+\d+", raw_text.upper())
             print(f"DEBUG: Matches for 'CHAMBRE \d+': {matches}")
             
             if 'B11' in raw_text:
                 print("FOUND 'B11' in text!")
             else:
                 print("NOT FOUND 'B11' in text (Fallback expected).")
             
             print("-----------------------------------")
        else:
             print("Not a PDF file")
             return

        # Print result
        print("\n--- Extraction Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Check if fallback happened
        meta = result.get('_extraction_meta', {})
        method = meta.get('method')
        # Save result to file for reliable checking
        with open('extraction_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        print(f"\nSUCCESS: Extracted using PyMuPDF. Result saved to extraction_result.json")
            
    except Exception as e:
        print(f"\nERROR: Extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    pdf_path = "pdfExample/B11.pdf"
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        
    test_extraction(pdf_path)
