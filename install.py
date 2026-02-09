#!/usr/bin/env python3
"""
Script d'installation cross-platform pour ArchiExtract.
Fonctionne sur Windows, macOS et Linux.

Usage:
    python install.py              # Installation complete
    python install.py --check      # Verifier l'installation sans rien installer
    python install.py --no-venv    # Installer sans environnement virtuel
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"

# Couleurs terminal (desactivees sur Windows sans support ANSI)
USE_COLORS = sys.platform != 'win32' or os.environ.get('TERM')

def _c(text, code):
    if USE_COLORS:
        return f"\033[{code}m{text}\033[0m"
    return text

def green(text): return _c(text, '32')
def yellow(text): return _c(text, '33')
def red(text): return _c(text, '31')
def bold(text): return _c(text, '1')


# ============================================================
# Fonctions utilitaires
# ============================================================

def run_command(cmd, capture=True, check=False):
    """Execute une commande et retourne le resultat."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            timeout=300,
        )
        return result
    except subprocess.TimeoutExpired:
        print(red("  TIMEOUT: la commande a pris trop de temps"))
        return None
    except FileNotFoundError:
        return None


def find_executable(name):
    """Cherche un executable dans le PATH."""
    return shutil.which(name)


# ============================================================
# Verifications
# ============================================================

def check_python():
    """Verifie la version de Python."""
    print(bold("\n[1/5] Verification de Python..."))

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(red(f"  ERREUR: Python 3.8+ requis, version actuelle: {version_str}"))
        print(f"  Telechargez Python depuis: https://www.python.org/downloads/")
        return False

    print(green(f"  OK Python {version_str} detecte"))
    return True


def check_tesseract():
    """Verifie si Tesseract OCR est installe."""
    print(bold("\n[2/5] Verification de Tesseract OCR..."))

    tesseract_path = find_executable("tesseract")

    if not tesseract_path:
        print(yellow("  ATTENTION: Tesseract OCR n'est pas installe"))
        print()
        print("  Instructions d'installation:")

        if sys.platform == 'win32':
            print("    Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            print("    Apres installation, ajoutez le repertoire au PATH")
            print("    (ex: C:\\Program Files\\Tesseract-OCR)")
        elif sys.platform == 'darwin':
            print("    macOS:   brew install tesseract tesseract-lang")
        else:
            print("    Linux:   sudo apt-get install tesseract-ocr tesseract-ocr-fra")
            print("    Fedora:  sudo dnf install tesseract tesseract-langpack-fra")

        print()
        print("  ArchiExtract fonctionnera sans Tesseract (via Claude Vision API)")
        print("  mais le mode fallback OCR ne sera pas disponible.")
        return True  # Non bloquant

    # Verifier la version
    result = run_command(["tesseract", "--version"])
    if result and result.returncode == 0:
        version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
        print(green(f"  OK {version_line.strip()}"))
    else:
        print(green(f"  OK Tesseract trouve: {tesseract_path}"))

    # Verifier la langue francaise
    result = run_command(["tesseract", "--list-langs"])
    output = (result.stdout or '') + (result.stderr or '') if result else ''
    if 'fra' in output:
        print(green("  OK Pack francais (fra) installe"))
    else:
        print(yellow("  ATTENTION: Pack francais (fra) non detecte"))
        if sys.platform == 'win32':
            print("    Reinstallez Tesseract en cochant 'French' dans les langues")
        elif sys.platform == 'darwin':
            print("    Installez: brew install tesseract-lang")
        else:
            print("    Installez: sudo apt-get install tesseract-ocr-fra")
        print("    L'outil utilisera l'anglais en attendant (detection francais partielle)")

    return True


def check_pip():
    """Verifie que pip est disponible."""
    result = run_command([sys.executable, "-m", "pip", "--version"])
    if result and result.returncode == 0:
        return True

    print(red("  ERREUR: pip n'est pas disponible"))
    print("  Installez pip: https://pip.pypa.io/en/stable/installation/")
    return False


# ============================================================
# Installation
# ============================================================

def create_venv():
    """Cree un environnement virtuel Python."""
    print(bold("\n[3/5] Configuration de l'environnement virtuel..."))

    if VENV_DIR.exists():
        print(f"  Environnement virtuel existant: {VENV_DIR}")
        response = input("  Le recreer? (o/n) [n]: ").strip().lower()
        if response in ('o', 'oui', 'y', 'yes'):
            shutil.rmtree(str(VENV_DIR))
            print("  Ancien environnement supprime")
        else:
            print("  Conservation de l'environnement existant")
            return True

    print(f"  Creation de l'environnement virtuel dans {VENV_DIR}...")
    result = run_command([sys.executable, "-m", "venv", str(VENV_DIR)])

    if result and result.returncode == 0:
        print(green("  OK Environnement virtuel cree"))
        return True
    else:
        print(red("  ERREUR: Impossible de creer l'environnement virtuel"))
        if result and result.stderr:
            print(f"  Details: {result.stderr[:200]}")
        return False


def get_venv_pip():
    """Retourne le chemin vers pip dans le venv."""
    if sys.platform == 'win32':
        pip_path = VENV_DIR / "Scripts" / "pip.exe"
        python_path = VENV_DIR / "Scripts" / "python.exe"
    else:
        pip_path = VENV_DIR / "bin" / "pip"
        python_path = VENV_DIR / "bin" / "python"

    if pip_path.exists():
        return str(pip_path), str(python_path)

    # Fallback vers le pip systeme
    return sys.executable + " -m pip", sys.executable


def install_dependencies(use_venv=True):
    """Installe les dependances Python."""
    print(bold("\n[4/5] Installation des dependances..."))

    if not REQUIREMENTS_FILE.exists():
        print(red(f"  ERREUR: {REQUIREMENTS_FILE} introuvable"))
        return False

    if use_venv and VENV_DIR.exists():
        pip_cmd, python_cmd = get_venv_pip()
        print(f"  Utilisation du pip du venv: {pip_cmd}")
    else:
        pip_cmd = f"{sys.executable} -m pip"
        python_cmd = sys.executable
        print(f"  Utilisation du pip systeme")

    # Mise a jour de pip
    print("  Mise a jour de pip...")
    if isinstance(pip_cmd, str) and ' ' in pip_cmd:
        upgrade_cmd = pip_cmd.split() + ["install", "--upgrade", "pip"]
    else:
        upgrade_cmd = [pip_cmd, "install", "--upgrade", "pip"]
    run_command(upgrade_cmd)

    # Installation des dependances
    print(f"  Installation depuis {REQUIREMENTS_FILE}...")
    if isinstance(pip_cmd, str) and ' ' in pip_cmd:
        install_cmd = pip_cmd.split() + ["install", "-r", str(REQUIREMENTS_FILE)]
    else:
        install_cmd = [pip_cmd, "install", "-r", str(REQUIREMENTS_FILE)]

    result = run_command(install_cmd, capture=False)

    if result and result.returncode == 0:
        print(green("  OK Dependances installees avec succes"))

        # Installer pytest pour les tests
        print("  Installation de pytest (tests)...")
        if isinstance(pip_cmd, str) and ' ' in pip_cmd:
            test_cmd = pip_cmd.split() + ["install", "pytest"]
        else:
            test_cmd = [pip_cmd, "install", "pytest"]
        run_command(test_cmd, capture=False)

        return True
    else:
        print(red("  ERREUR: Echec de l'installation des dependances"))
        return False


def run_tests(use_venv=True):
    """Execute les tests pour verifier l'installation."""
    print(bold("\n[5/5] Verification de l'installation..."))

    if use_venv and VENV_DIR.exists():
        _, python_cmd = get_venv_pip()
    else:
        python_cmd = sys.executable

    # Test d'import basique
    test_script = (
        "import sys; "
        "sys.path.insert(0, '.'); "
        "from config import AppConfig, ensure_directories; "
        "from architecture_plan_extractor import ParcelData, ArchitecturePlanExtractor; "
        "from extraction_cache import ExtractionCache; "
        "print('Imports OK'); "
        "ensure_directories(); "
        "print('Directories OK'); "
        "cfg = AppConfig(); "
        "print(f'Config OK (model={cfg.claude_model})'); "
    )

    result = run_command(
        [python_cmd, "-c", test_script],
        capture=True,
    )

    if result and result.returncode == 0:
        for line in result.stdout.strip().split('\n'):
            print(green(f"  OK {line}"))
        return True
    else:
        print(yellow("  ATTENTION: Certains tests ont echoue"))
        if result and result.stderr:
            print(f"  Details: {result.stderr[:300]}")
        return False


# ============================================================
# Affichage final
# ============================================================

def print_summary(use_venv=True, success=True):
    """Affiche le resume de l'installation."""
    print()
    print("=" * 55)

    if success:
        print(green(bold("  INSTALLATION TERMINEE AVEC SUCCES")))
    else:
        print(yellow(bold("  INSTALLATION TERMINEE AVEC DES AVERTISSEMENTS")))

    print("=" * 55)
    print()
    print(bold("Prochaines etapes:"))
    print()

    if use_venv:
        if sys.platform == 'win32':
            activate = f"  {VENV_DIR}\\Scripts\\activate"
        else:
            activate = f"  source {VENV_DIR}/bin/activate"

        print(f"1. Activer l'environnement virtuel:")
        print(f"   {activate}")
        print()

    print(f"2. Lancer l'interface web:")
    print(f"   streamlit run streamlit_app.py")
    print()
    print(f"3. Lancer les tests:")
    print(f"   pytest tests/ -v")
    print()
    print(f"4. Configuration optionnelle:")
    print(f"   export ANTHROPIC_API_KEY=sk-votre-cle")
    if sys.platform == 'win32':
        print(f"   (Windows: set ANTHROPIC_API_KEY=sk-votre-cle)")
    print()
    print(f"Documentation: README.md")
    print()


# ============================================================
# Point d'entree
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Installation d'ArchiExtract"
    )
    parser.add_argument(
        '--check', action='store_true',
        help="Verifier l'installation sans rien installer"
    )
    parser.add_argument(
        '--no-venv', action='store_true',
        help="Installer sans environnement virtuel"
    )
    args = parser.parse_args()

    print()
    print(bold("=" * 55))
    print(bold("  ARCHIEXTRACT - Installation"))
    print(bold("=" * 55))

    use_venv = not args.no_venv
    all_ok = True

    # Etape 1: Python
    if not check_python():
        sys.exit(1)

    # Etape 2: Tesseract (non bloquant)
    check_tesseract()

    if args.check:
        # Mode verification uniquement
        if not check_pip():
            all_ok = False
        print()
        if all_ok:
            print(green("Toutes les verifications sont passees."))
        else:
            print(yellow("Certaines verifications ont echoue."))
        sys.exit(0 if all_ok else 1)

    # Etape 3: Venv
    if use_venv:
        if not create_venv():
            print(yellow("  Poursuite sans environnement virtuel..."))
            use_venv = False

    # Etape 4: Dependances
    if not install_dependencies(use_venv=use_venv):
        all_ok = False

    # Etape 5: Tests
    if not run_tests(use_venv=use_venv):
        all_ok = False

    # Resume
    print_summary(use_venv=use_venv, success=all_ok)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
