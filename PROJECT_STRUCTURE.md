# 📁 Structure du projet

```
architecture-plan-extractor/
│
├── 📄 architecture_plan_extractor.py   # Module principal d'extraction
├── 🌐 streamlit_app.py                 # Interface web Streamlit
├── 🧪 test_extractor.py                # Tests et exemples
│
├── 📦 requirements.txt                  # Dépendances Python
├── 🔧 install.sh                       # Script d'installation
│
├── 📖 README.md                        # Documentation complète
├── 🚀 QUICKSTART.md                    # Guide de démarrage rapide
├── 📁 PROJECT_STRUCTURE.md             # Ce fichier
│
└── 📊 sample_complete.json             # Exemple de sortie JSON
```

## 🎯 Description des fichiers

### Fichiers principaux

**architecture_plan_extractor.py**
- Module Python principal
- Contient la classe `ArchitecturePlanExtractor`
- Gère le prétraitement d'image, l'OCR et le parsing
- Peut être importé dans d'autres scripts

**streamlit_app.py**
- Interface utilisateur web interactive
- Upload d'images, extraction, édition et export
- Mode single image et mode batch
- Lancer avec: `streamlit run streamlit_app.py`

**test_extractor.py**
- Script de test et démonstration
- Exemples d'utilisation
- Tests des patterns regex
- Génération de données d'exemple

### Documentation

**README.md**
- Documentation technique complète
- Guide d'installation détaillé
- Exemples de code
- Résolution de problèmes
- Configuration avancée

**QUICKSTART.md**
- Guide de démarrage rapide
- Installation en 3 étapes
- Exemples simples
- Résolution de problèmes courants

**PROJECT_STRUCTURE.md**
- Structure du projet (ce fichier)
- Description de chaque fichier
- Organisation recommandée

### Configuration

**requirements.txt**
- Liste de toutes les dépendances Python
- Installation avec: `pip install -r requirements.txt`

**install.sh**
- Script bash d'installation automatique
- Vérifie les prérequis
- Crée l'environnement virtuel
- Installe les dépendances

### Exemples

**sample_complete.json**
- Exemple de fichier JSON de sortie
- Contient 3 lots différents avec diverses configurations
- Référence pour le format attendu

## 🔄 Workflow typique

1. **Installation initiale**
   ```bash
   bash install.sh
   ```

2. **Activation de l'environnement**
   ```bash
   source venv/bin/activate
   ```

3. **Utilisation**
   - Interface web: `streamlit run streamlit_app.py`
   - Script: `python architecture_plan_extractor.py`
   - Tests: `python test_extractor.py`

## 📂 Organisation recommandée de vos données

```
votre_projet/
│
├── architecture-plan-extractor/  # Dossier de l'outil
│   ├── architecture_plan_extractor.py
│   ├── streamlit_app.py
│   └── ...
│
├── plans/                         # Vos images de plans
│   ├── plan_A001.png
│   ├── plan_A002.png
│   └── ...
│
└── outputs/                       # Résultats extraits
    ├── lots_batiment_A.json
    ├── lots_batiment_B.json
    └── ...
```

## 🎨 Personnalisation

Pour adapter l'outil à vos besoins:

1. **Patterns regex**: Modifier dans `architecture_plan_extractor.py` → `__init__()` → `self.patterns`
2. **Options**: Ajouter dans `ParcelData` et `self.option_keywords`
3. **Prétraitement**: Ajuster dans `preprocess_image()`
4. **Interface**: Personnaliser `streamlit_app.py`

## 🔧 Fichiers générés lors de l'exécution

L'outil génère des fichiers temporaires et de debug:

- `preprocessed_debug.png` - Image après prétraitement
- `extracted_text_debug.txt` - Texte OCR brut
- `venv/` - Environnement virtuel Python (créé par install.sh)

Ces fichiers peuvent être supprimés sans problème.

## 📝 Notes importantes

- Les fichiers Python utilisent l'encodage UTF-8
- Les JSON de sortie sont en UTF-8 avec `ensure_ascii=False`
- L'outil nécessite Tesseract OCR installé sur le système
- Les images doivent être de bonne qualité (300 DPI recommandé)

## 🚀 Déploiement

Pour déployer sur un serveur ou partager avec une équipe:

1. Copier tous les fichiers sur le serveur
2. Installer Tesseract OCR
3. Exécuter `install.sh`
4. Lancer Streamlit: `streamlit run streamlit_app.py --server.port 8501`

## 📞 Support

En cas de problème:
1. Consulter README.md pour la documentation complète
2. Vérifier QUICKSTART.md pour les problèmes courants
3. Examiner les fichiers de debug
4. Lire les logs dans la console
