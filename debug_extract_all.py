"""Debug script to test extract_all_pages"""
import sys
sys.path.insert(0, '.')

from src.extractors.super_extractor import SuperExtractor
import logging

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

extractor = SuperExtractor()

# Test extract_all_pages
print("=" * 60)
print("Testing extract_all_pages on Multipages.pdf")
print("=" * 60)

results = extractor.extract_all_pages('./pdfExample/Multipages.pdf', None)

print("\nResults:")
print(f"  Type: {type(results)}")
print(f"  Keys count: {len(results)}")
print(f"  First 5 keys: {list(results.keys())[:5]}")

# Check first result
for k, v in list(results.items())[:2]:
    print(f"\nKey: {k!r}")
    print(f"  Value type: {type(v).__name__}")
    if hasattr(v, 'living_space'):
        print(f"  living_space: {v.living_space}")
        print(f"  rooms count: {len(v.rooms)}")
        print(f"  reference: {v.reference}")
    elif isinstance(v, dict):
        print(f"  Dict keys: {list(v.keys())}")
