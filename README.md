# 🏗️ Architecture Plan Extractor

Outil Python pour extraire automatiquement les données des plans d'architecture et les convertir en format JSON structuré.

## 📋 Fonctionnalités

- ✅ Extraction OCR automatique avec Tesseract
- ✅ Prétraitement d'image avancé pour améliorer la qualité OCR
- ✅ Parsing intelligent avec patterns regex configurables
- ✅ Interface web interactive avec Streamlit
- ✅ Mode batch pour traiter plusieurs images
- ✅ Édition manuelle des données extraites
- ✅ Export JSON conforme au schéma cible
- ✅ Fichiers de debug pour amélioration continue

## 🎯 Données extraites

L'outil extrait automatiquement:
- **Référence du lot** (A001, B002, etc.)
- **Typologie** (T1, T2, T3, etc.)
- **Étage** (RDC, R+1, etc.)
- **Orientation** (N, S, E, O)
- **Surface habitable** (en m²)
- **Prix** (si disponible)
- **Surfaces annexes** (terrasse, balcon, jardin)
- **Options** (parking, garage, duplex, etc.)

## 📦 Installation

### Prérequis

1. **Python 3.8+**
2. **Tesseract OCR**

#### Installation de Tesseract

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
- Télécharger depuis: https://github.com/UB-Mannheim/tesseract/wiki
- Ajouter Tesseract au PATH système

### Installation des dépendances Python

```bash
# Cloner ou télécharger les fichiers
cd architecture-plan-extractor

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## 🚀 Utilisation

### Option 1: Interface Web (Recommandé)

```bash
streamlit run streamlit_app.py
```

L'application s'ouvrira automatiquement dans votre navigateur à l'adresse `http://localhost:8501`

#### Workflow dans l'interface:
1. Uploadez une image du plan d'architecture
2. Cliquez sur "Extraire les données"
3. Vérifiez et corrigez les données si nécessaire
4. Téléchargez le fichier JSON

### Option 2: Script Python direct

```python
from architecture_plan_extractor import ArchitecturePlanExtractor

# Initialisation
extractor = ArchitecturePlanExtractor()

# Extraction d'une seule image
result = extractor.extract_from_image("chemin/vers/plan.png")

# Affichage
import json
print(json.dumps(result, indent=2, ensure_ascii=False))

# Sauvegarde
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
```

### Option 3: Mode Batch

```python
from architecture_plan_extractor import ArchitecturePlanExtractor

extractor = ArchitecturePlanExtractor()

# Liste des images
images = [
    "plan_lot_A001.png",
    "plan_lot_A002.png",
    "plan_lot_A003.png"
]

# Extraction batch
results = extractor.extract_batch(images)

# Sauvegarde
import json
with open("all_lots.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
```

## 📝 Format de sortie

```json
{
  "A001": {
    "parcelLabel": "A001",
    "parcelTypeId": "appartment",
    "parcelTypeLabel": "appartment",
    "orientation": "O",
    "typology": "T2",
    "floor": "RDC",
    "price": "N.C",
    "living space": "41.72",
    "surfaceDetail": {
      "terrace": 7.49
    },
    "option": {
      "garden": false,
      "terrace": true,
      "balcony": false,
      "parking": false,
      "winter garden": false,
      "garage": false,
      "loggia": false,
      "duplex": false
    },
    "tva": "",
    "pinel": "",
    "customData": null,
    "state": "available"
  }
}
```

## ⚙️ Configuration avancée

### Personnalisation des patterns regex

Vous pouvez modifier les patterns dans `architecture_plan_extractor.py`:

```python
self.patterns = {
    'parcelLabel': [
        r'\b([A-Z]\d{3})\b',  # Format A001
        r'\bVotre pattern personnalisé\b',
    ],
    # ... autres patterns
}
```

### Amélioration de l'OCR

Si l'OCR ne donne pas de bons résultats:

1. **Ajuster le prétraitement** dans `preprocess_image()`:
```python
# Augmenter le contraste
clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

# Ajuster la binarisation
binary = cv2.adaptiveThreshold(enhanced, 255, 
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
    cv2.THRESH_BINARY, 15, 3)  # Paramètres ajustés
```

2. **Modifier la configuration Tesseract**:
```python
# Mode de segmentation différent
custom_config = r'--oem 3 --psm 11 -l fra'  # PSM 11 pour texte épars
```

3. **Utiliser EasyOCR** (alternative):
```python
# Décommenter dans requirements.txt
# Dans le code:
import easyocr
reader = easyocr.Reader(['fr'])
text = reader.readtext(image_path, detail=0)
```

## 🐛 Debugging

L'outil génère des fichiers de debug:
- `preprocessed_debug.png` - Image après prétraitement
- `extracted_text_debug.txt` - Texte brut extrait par l'OCR

Ces fichiers se trouvent dans `/home/claude/` ou le répertoire de travail.

### Problèmes courants

**1. Tesseract non trouvé**
```bash
# Vérifier l'installation
tesseract --version

# Si besoin, spécifier le chemin dans le code:
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

**2. Mauvaise qualité OCR**
- Vérifier que l'image est en haute résolution (300 DPI minimum)
- S'assurer que le texte est lisible et contrasté
- Essayer différents modes PSM de Tesseract
- Utiliser le prétraitement plus agressif

**3. Patterns non détectés**
- Examiner `extracted_text_debug.txt` pour voir le texte OCR
- Ajuster les patterns regex en conséquence
- Ajouter des variations de format

## 📊 Exemples d'utilisation

### Exemple 1: Extraction simple
```python
from architecture_plan_extractor import ArchitecturePlanExtractor

extractor = ArchitecturePlanExtractor()
data = extractor.extract_from_image("plan.png")

print(f"Lot: {data['parcelLabel']}")
print(f"Type: {data['typology']}")
print(f"Surface: {data['living_space']} m²")
```

### Exemple 2: Validation et corrections
```python
data = extractor.extract_from_image("plan.png")

# Vérification
if not data['parcelLabel']:
    data['parcelLabel'] = input("Entrez la référence du lot: ")

if not data['typology']:
    data['typology'] = input("Entrez la typologie: ")

# Sauvegarde après correction
with open("corrected.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Exemple 3: Traitement d'un dossier complet
```python
import os
from pathlib import Path

extractor = ArchitecturePlanExtractor()
plans_dir = Path("plans_architecture")

results = {}
for image_file in plans_dir.glob("*.png"):
    print(f"Traitement de {image_file.name}...")
    data = extractor.extract_from_image(str(image_file))
    lot_id = data['parcelLabel'] or image_file.stem
    results[lot_id] = data

# Export final
with open("tous_les_lots.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
```

## 🔧 Développement

### Structure du projet
```
architecture-plan-extractor/
├── architecture_plan_extractor.py  # Module principal
├── streamlit_app.py                # Interface web
├── requirements.txt                # Dépendances
├── README.md                       # Documentation
└── tests/                          # Tests unitaires (à créer)
```

### Ajouter de nouvelles fonctionnalités

1. **Nouveau champ à extraire:**
```python
# Dans __init__()
self.patterns['nouveau_champ'] = [r'votre_pattern']

# Dans parse_plan()
parcel.nouveau_champ = self.extract_field(text, 'nouveau_champ')
```

2. **Nouveau type de document:**
```python
class BlueprintExtractor(ArchitecturePlanExtractor):
    def preprocess_blueprint(self, image_path):
        # Prétraitement spécifique
        pass
```

## 📈 Amélioration continue

Pour améliorer la précision:
1. Collecter des exemples de plans avec annotations
2. Analyser les fichiers de debug pour identifier les erreurs
3. Affiner les patterns regex
4. Ajuster les paramètres de prétraitement

## 📄 Licence

Ce projet est fourni tel quel pour usage interne.

## 🤝 Support

Pour toute question ou amélioration:
1. Examiner les fichiers de debug
2. Vérifier la qualité de l'image source
3. Consulter les logs d'erreur

## 🎯 Roadmap

- [ ] Support des PDFs multi-pages
- [ ] Détection automatique des zones de texte
- [ ] API REST pour intégration
- [ ] Base de données pour historique
- [ ] Machine Learning pour améliorer la détection
- [ ] Export vers d'autres formats (Excel, CSV)
- [ ] Validation automatique des données
- [ ] Interface de correction collaborative
