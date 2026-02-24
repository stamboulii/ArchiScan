#!/usr/bin/env python3
"""
Script d'installation de Tesseract OCR pour ArchiExtract.
Telecharge et configure Tesseract automatiquement.
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path


# Configuration
TESSERACT_VERSION = "5.3.1.20230401"
TESSERACT_URL = f"https://github.com/UB-Mannheim/tesseract/releases/download/tesseract-ocr-w64-{TESSERACT_VERSION}.exe"
# Pour Windows, on utilise le zip portable
TESSERACT_ZIP_URL = f"https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-{TESSERACT_VERSION}.exe"


def get_tesseract_dir():
    """Retourne le repertoire Tesseract dans le projet."""
    project_root = Path(__file__).parent
    tessdata_dir = project_root / "tesseract"
    return tessdata_dir


def check_tesseract_installed():
    """Verifie si Tesseract est deja installe."""
    # Verifier dans le repertoire local
    tess_dir = get_tesseract_dir()
    tesseract_exe = tess_dir / "tesseract.exe"
    
    if tesseract_exe.exists():
        return True, tess_dir
    
    # Verifier dans les chemins systeme
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return True, Path(path).parent
    
    return False, None


def download_tesseract_windows():
    """Telecharge Tesseract pour Windows."""
    import platform
    
    if platform.system() != "Windows":
        print("Ce script est uniquement pour Windows.")
        print("Pour Linux/Mac, installez Tesseract avec:")
        print("  - Ubuntu/Debian: sudo apt install tesseract-ocr")
        print("  - Mac: brew install tesseract")
        return False
    
    print("Telechargement de Tesseract OCR...")
    print(f"Version: {TESSERACT_VERSION}")
    
    # URL du zip portable
    zip_url = f"https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-{TESSERACT_VERSION}.exe"
    
    tess_dir = get_tesseract_dir()
    tess_dir.mkdir(exist_ok=True)
    
    zip_path = tess_dir / "tesseract-installer.exe"
    
    try:
        # Telecharger l'installeur
        urllib.request.urlretrieve(zip_url, zip_path)
        print(f"Telecharge: {zip_path}")
        
        # Executer l'installeur en mode silent
        print("Installation de Tesseract...")
        result = subprocess.run(
            [str(zip_path), "/S", "/D=" + str(tess_dir)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("Tesseract installe avec succes!")
            
            # Verifier l'installation
            tesseract_exe = tess_dir / "tesseract.exe"
            if tesseract_exe.exists():
                print(f"Executable: {tesseract_exe}")
                
                # Definir TESSDATA_PREFIX
                tessdata = tess_dir / "tessdata"
                if not tessdata.exists():
                    tessdata = tess_dir / "tessdata"
                
                print(f"\nTESSDATA_PREFIX={tess_dir}")
                print(f"Pour Windows, ajoutez a votre environment:")
                print(f'  set TESSDATA_PREFIX={tess_dir}')
                
                return True
        
    except Exception as e:
        print(f"Erreur: {e}")
    
    return False


def install_system_tesseract():
    """Installe Tesseract via les gestionnaires de paquets."""
    print("Installation de Tesseract via le gestionnaire de paquets...")
    
    # Detecter le systeme
    if sys.platform == "win32":
        print("Windows detecte.")
        print("Options d'installation:")
        print("  1. Download: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  2. Via Scoop: scoop install tesseract")
        print("  3. Via Chocolatey: choco install tesseract")
        return False
    
    elif sys.platform == "darwin":
        # Mac
        print("Mac detecte.")
        result = subprocess.run(["brew", "install", "tesseract"], capture_output=True, text=True)
        return result.returncode == 0
    
    else:
        # Linux
        print("Linux detecte.")
        result = subprocess.run(["sudo", "apt", "install", "tesseract-ocr"], capture_output=True, text=True)
        return result.returncode == 0


def main():
    print("=" * 60)
    print("Installation de Tesseract OCR pour ArchiExtract")
    print("=" * 60)
    
    # Verifier si deja installe
    installed, path = check_tesseract_installed()
    if installed:
        print(f"Tesseract deja installe: {path}")
        return 0
    
    print("\nTesseract n'est pas installe.")
    print("\nChoix d'installation:")
    print("  1. Telecharger automatiquement (Windows)")
    print("  2. Installer via le systeme (Linux/Mac)")
    print("  3. Quitter")
    
    try:
        choice = input("\nVotre choix (1/2/3): ").strip()
    except KeyboardInterrupt:
        return 1
    
    if choice == "1":
        if sys.platform == "win32":
            success = download_tesseract_windows()
        else:
            print("Telechargement automatique uniquement pour Windows.")
            success = install_system_tesseract()
    elif choice == "2":
        success = install_system_tesseract()
    else:
        print("Annulation.")
        return 1
    
    if success:
        print("\nInstallation terminee!")
    else:
        print("\nEchec de l'installation. Suivez les instructions manuelles.")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
