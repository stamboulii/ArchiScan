# 🚀 Guide de démarrage rapide

## Installation en 3 étapes

### 1. Installation de Tesseract OCR

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-fra
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Windows:**
- Télécharger: https://github.com/UB-Mannheim/tesseract/wiki
- Ajouter au PATH: `C:\Program Files\Tesseract-OCR`

### 2. Installation des dépendances Python

```bash
# Avec le script d'installation (recommandé)
bash install.sh

# OU manuellement
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 3. Test de l'installation

```bash
python test_extractor.py
```

---

## Utilisation rapide

### Option A: Interface Web (plus facile)

```bash
streamlit run streamlit_app.py
```

Puis dans le navigateur:
1. Upload une image de plan
2. Clic sur "Extraire les données"
3. Vérifie/corrige les données
4. Télécharge le JSON

### Option B: Script Python

```python
from architecture_plan_extractor import ArchitecturePlanExtractor

extractor = ArchitecturePlanExtractor()
result = extractor.extract_from_image("mon_plan.png")

import json
print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## Résolution de problèmes

### ❌ "Tesseract not found"
```bash
# Vérifier l'installation
tesseract --version

# Si installé mais non trouvé, ajouter au PATH ou spécifier le chemin:
# Dans le code Python:
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

### ❌ "Fra language not found"
```bash
# Installer le pack français
sudo apt-get install tesseract-ocr-fra  # Linux
brew install tesseract-lang             # macOS

# OU modifier le code pour utiliser 'eng' (anglais) qui détecte quand même le français
```

### ❌ Mauvaise qualité d'extraction

1. **Vérifier l'image:**
   - Résolution minimum: 300 DPI
   - Format: PNG ou JPG haute qualité
   - Texte contrasté (noir sur blanc)

2. **Examiner les fichiers de debug:**
   - `preprocessed_debug.png` - voir l'image traitée
   - `extracted_text_debug.txt` - voir le texte OCR

3. **Ajuster le prétraitement:**
   ```python
   # Dans architecture_plan_extractor.py, méthode preprocess_image()
   clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
   ```

4. **Tester différents modes PSM:**
   ```python
   # Dans extract_text_ocr()
   custom_config = r'--oem 3 --psm 11 -l eng'  # Essayer psm 3, 6, 11
   ```

---

## Exemple complet

```python
from architecture_plan_extractor import ArchitecturePlanExtractor
import json

# Initialisation
extractor = ArchitecturePlanExtractor()

# Extraction d'un plan
result = extractor.extract_from_image("plan_A001.png")

# Affichage
print(f"Lot: {result['parcelLabel']}")
print(f"Type: {result['typology']}")
print(f"Étage: {result['floor']}")
print(f"Surface: {result['living_space']} m²")

# Sauvegarde
with open("output.json", "w", encoding="utf-8") as f:
    json.dump({result['parcelLabel']: result}, f, indent=2, ensure_ascii=False)

print("✅ Données sauvegardées dans output.json")
```

---

## Traitement en lot

```python
import glob
from architecture_plan_extractor import ArchitecturePlanExtractor

extractor = ArchitecturePlanExtractor()

# Tous les PNG dans un dossier
plans = glob.glob("plans/*.png")

# Extraction
results = extractor.extract_batch(plans)

# Sauvegarde
with open("tous_les_lots.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"✅ {len(results)} lots extraits")
```

---

## Personnalisation

### Ajouter un nouveau pattern

```python
# Dans architecture_plan_extractor.py, méthode __init__()

self.patterns['mon_champ'] = [
    r'Mon Pattern 1',
    r'Mon Pattern 2 alternatif'
]
```

### Ajouter une nouvelle option

```python
# Dans __init__()
self.option_keywords['ma_nouvelle_option'] = ['mot-clé1', 'mot-clé2']

# Dans ParcelData
option: Dict[str, bool] = None

def __post_init__(self):
    if self.option is None:
        self.option = {
            # ... options existantes
            "ma_nouvelle_option": False
        }
```

---

## Commandes utiles

```bash
# Lancer l'interface web
streamlit run streamlit_app.py

# Exécuter les tests
python test_extractor.py

# Extraction simple
python architecture_plan_extractor.py

# Activer l'environnement virtuel
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Désactiver l'environnement
deactivate
```

---

## Support

Pour plus d'informations, consulter:
- **README.md** - Documentation complète
- **test_extractor.py** - Exemples de code
- Fichiers de debug - Pour comprendre les problèmes

---

## Checklist avant de commencer

- [ ] Python 3.8+ installé
- [ ] Tesseract OCR installé
- [ ] Dépendances Python installées (`pip install -r requirements.txt`)
- [ ] Tests passés (`python test_extractor.py`)
- [ ] Images de plans prêtes (300 DPI, haute qualité)

**Prêt à extraire! 🚀**
