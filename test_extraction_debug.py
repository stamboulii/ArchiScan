"""Test d'extraction debug."""
import sys
print("1. Script started", file=sys.stderr)

from hybrid_extractor import HybridExtractor
print("2. HybridExtractor imported", file=sys.stderr)

from PIL import Image
import tempfile
import os

print("3. Creating test image...", file=sys.stderr)
img = Image.new('RGB', (800, 600), color='white')
with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
    img.save(f.name)
    temp_path = f.name

print(f"4. Temp file: {temp_path}", file=sys.stderr)

try:
    e = HybridExtractor()
    print(f"5. Phase: {e.get_current_phase()}", file=sys.stderr)
    print("6. Starting extraction...", file=sys.stderr)
    result = e.extract_from_image(temp_path)
    print(f"7. SUCCESS - Keys: {list(result.keys())}", file=sys.stderr)
except Exception as ex:
    print(f"8. ERROR: {type(ex).__name__} - {str(ex)[:500]}", file=sys.stderr)
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(temp_path):
        os.unlink(temp_path)
