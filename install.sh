#!/bin/bash

# Script d'installation pour Architecture Plan Extractor
# Usage: bash install.sh

echo "🏗️  INSTALLATION DE ARCHITECTURE PLAN EXTRACTOR"
echo "================================================"
echo ""

# Vérification de Python
echo "📦 Vérification de Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé!"
    echo "   Installez Python 3.8+ depuis https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "   ✅ Python $PYTHON_VERSION détecté"

# Vérification de Tesseract
echo ""
echo "📦 Vérification de Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
    echo "⚠️  Tesseract OCR n'est pas installé!"
    echo ""
    echo "Installation requise:"
    echo "  • Linux (Ubuntu/Debian): sudo apt-get install tesseract-ocr tesseract-ocr-fra"
    echo "  • macOS: brew install tesseract tesseract-lang"
    echo "  • Windows: https://github.com/UB-Mannheim/tesseract/wiki"
    echo ""
    read -p "Voulez-vous continuer sans Tesseract? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    TESSERACT_VERSION=$(tesseract --version 2>&1 | head -1 | cut -d' ' -f2)
    echo "   ✅ Tesseract $TESSERACT_VERSION détecté"
    
    # Vérification de la langue française
    if tesseract --list-langs 2>&1 | grep -q "fra"; then
        echo "   ✅ Pack français installé"
    else
        echo "   ⚠️  Pack français non détecté"
        echo "      L'outil utilisera l'anglais (peut détecter le français quand même)"
    fi
fi

# Création de l'environnement virtuel
echo ""
echo "🔧 Configuration de l'environnement virtuel..."
if [ -d "venv" ]; then
    echo "   ℹ️  Environnement virtuel existant détecté"
    read -p "   Voulez-vous le recréer? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo "   ✅ Environnement virtuel recréé"
    fi
else
    python3 -m venv venv
    echo "   ✅ Environnement virtuel créé"
fi

# Activation de l'environnement
echo ""
echo "🔌 Activation de l'environnement virtuel..."
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

if [ $? -eq 0 ]; then
    echo "   ✅ Environnement activé"
else
    echo "   ⚠️  Impossible d'activer l'environnement automatiquement"
    echo "      Activez-le manuellement:"
    echo "        • Linux/Mac: source venv/bin/activate"
    echo "        • Windows: venv\\Scripts\\activate"
fi

# Installation des dépendances
echo ""
echo "📥 Installation des dépendances Python..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "   ✅ Toutes les dépendances sont installées"
else
    echo "   ❌ Erreur lors de l'installation des dépendances"
    exit 1
fi

# Test de l'installation
echo ""
echo "🧪 Test de l'installation..."
python test_extractor.py > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "   ✅ Tests passés avec succès"
else
    echo "   ⚠️  Les tests ont échoué, mais l'installation est terminée"
fi

# Résumé
echo ""
echo "================================================"
echo "✅ INSTALLATION TERMINÉE"
echo "================================================"
echo ""
echo "📚 Prochaines étapes:"
echo ""
echo "1. Activer l'environnement (si pas déjà fait):"
echo "   source venv/bin/activate  # Linux/Mac"
echo "   venv\\Scripts\\activate    # Windows"
echo ""
echo "2. Lancer l'interface web:"
echo "   streamlit run streamlit_app.py"
echo ""
echo "3. Ou utiliser le script Python directement:"
echo "   python architecture_plan_extractor.py"
echo ""
echo "4. Voir les exemples:"
echo "   python test_extractor.py"
echo ""
echo "📖 Documentation complète: README.md"
echo ""
