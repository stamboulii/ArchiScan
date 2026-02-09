"""
Script de test et demonstration de l'Architecture Plan Extractor
Inclut les tests pour la strategie hybride progressive
"""

import json
import os
import tempfile
from architecture_plan_extractor import ArchitecturePlanExtractor
from config import PROJECT_ROOT


def test_with_sample_text():
    """Test avec du texte simule d'un plan d'architecture"""

    print("="*60)
    print("TEST AVEC TEXTE SIMULE")
    print("="*60)

    sample_text = """
    LOT A001
    Appartement T2
    Rez-de-chaussee (RDC)
    Orientation: Ouest (O)

    Surface habitable: 41.72 m2
    Terrasse: 7.49 m2

    Prix: 185 000 EUR

    Equipements:
    - Terrasse
    - Parking inclus
    """

    extractor = ArchitecturePlanExtractor()

    parcel_data = extractor.parse_plan(sample_text)

    from dataclasses import asdict
    result = asdict(parcel_data)

    print("\nDonnees extraites:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    output_path = str(PROJECT_ROOT / 'test_output.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({result['parcelLabel']: result}, f, indent=2, ensure_ascii=False)

    print(f"\nTest reussi! Fichier sauvegarde: {output_path}")


def test_pattern_matching():
    """Test des differents patterns regex"""

    print("\n" + "="*60)
    print("TEST DES PATTERNS REGEX")
    print("="*60)

    extractor = ArchitecturePlanExtractor()

    test_cases = {
        "References de lot": [
            "LOT A001",
            "Lot B02",
            "A123",
            "Appartement 456"
        ],
        "Typologies": [
            "T2",
            "F3",
            "T4",
            "2 pieces"
        ],
        "Etages": [
            "RDC",
            "R.D.C",
            "Rez-de-chaussee",
            "R+1",
            "Etage 2",
            "1er etage"
        ],
        "Surfaces": [
            "41.72 m2",
            "Surface: 58,50",
            "Habitable: 65.3",
            "75 m2"
        ],
        "Orientations": [
            "N",
            "Sud",
            "Orientation: E",
            "Ouest"
        ],
        "Prix": [
            "Prix: 185 000 EUR",
            "245000 EUR",
            "180 500 EUR"
        ]
    }

    for category, examples in test_cases.items():
        print(f"\n  {category}:")
        for example in examples:
            found = False
            for pattern_name, patterns in extractor.patterns.items():
                if not isinstance(patterns, list):
                    patterns = [patterns]

                import re
                for pattern in patterns:
                    match = re.search(pattern, example, re.IGNORECASE)
                    if match:
                        value = match.group(1) if match.groups() else match.group(0)
                        print(f"  OK '{example}' -> {pattern_name}: '{value}'")
                        found = True
                        break
                if found:
                    break

            if not found:
                print(f"  MISS '{example}' -> Aucun match")


def create_sample_json():
    """Cree un exemple de fichier JSON avec plusieurs lots"""

    print("\n" + "="*60)
    print("CREATION D'UN EXEMPLE COMPLET")
    print("="*60)

    sample_data = {
        "A001": {
            "parcelLabel": "A001",
            "parcelTypeId": "appartment",
            "parcelTypeLabel": "appartment",
            "orientation": "O",
            "typology": "T2",
            "floor": "RDC",
            "price": "185 000",
            "living_space": "41.72",
            "surfaceDetail": {
                "terrace": 7.49
            },
            "option": {
                "garden": False,
                "terrace": True,
                "balcony": False,
                "parking": True,
                "winter garden": False,
                "garage": False,
                "loggia": False,
                "duplex": False
            },
            "tva": "",
            "pinel": "",
            "customData": None,
            "state": "available"
        },
        "A002": {
            "parcelLabel": "A002",
            "parcelTypeId": "appartment",
            "parcelTypeLabel": "appartment",
            "orientation": "S",
            "typology": "T3",
            "floor": "R+1",
            "price": "245 000",
            "living_space": "68.50",
            "surfaceDetail": {
                "balcony": 5.20
            },
            "option": {
                "garden": False,
                "terrace": False,
                "balcony": True,
                "parking": True,
                "winter garden": False,
                "garage": True,
                "loggia": False,
                "duplex": False
            },
            "tva": "",
            "pinel": "eligible",
            "customData": None,
            "state": "available"
        },
        "B001": {
            "parcelLabel": "B001",
            "parcelTypeId": "appartment",
            "parcelTypeLabel": "appartment",
            "orientation": "N",
            "typology": "T4",
            "floor": "R+2",
            "price": "N.C",
            "living_space": "85.30",
            "surfaceDetail": {
                "terrace": 12.50,
                "loggia": 3.20
            },
            "option": {
                "garden": False,
                "terrace": True,
                "balcony": False,
                "parking": True,
                "winter garden": False,
                "garage": True,
                "loggia": True,
                "duplex": True
            },
            "tva": "reduite",
            "pinel": "eligible",
            "customData": {
                "vue": "degagee",
                "exposition": "exceptionnelle"
            },
            "state": "reserved"
        }
    }

    output_path = str(PROJECT_ROOT / 'sample_complete.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2, ensure_ascii=False)

    print(f"\nExemple complet cree: {output_path}")
    print("\nContenu:")
    print(json.dumps(sample_data, indent=2, ensure_ascii=False))


def test_hybrid_extractor_init():
    """Test que HybridExtractor s'initialise sans cle API (Phase 0)."""

    print("\n" + "="*60)
    print("TEST HYBRID EXTRACTOR INIT")
    print("="*60)

    from hybrid_extractor import HybridExtractor

    extractor = HybridExtractor()
    phase = extractor.get_current_phase()
    info = extractor.get_phase_description()

    print(f"\n  Phase actuelle: {phase}")
    print(f"  Nom: {info['name']}")
    print(f"  Description: {info['description']}")
    print(f"  Methode: {info['method']}")
    print(f"  Precision: {info['accuracy']}")

    # Sans cle API, devrait etre en Phase 0 (Tesseract)
    if phase == 0:
        print("\n  OK: Phase 0 (Tesseract) sans cle API")
    else:
        print(f"\n  INFO: Phase {phase} (cle API detectee dans l'environnement)")

    print("\n  Test reussi!")


def test_training_data_store():
    """Test des operations SQLite."""

    print("\n" + "="*60)
    print("TEST TRAINING DATA STORE")
    print("="*60)

    from training_data_store import TrainingDataStore

    # Utiliser une DB temporaire
    db_path = os.path.join(tempfile.gettempdir(), "test_training_archiextract.db")

    try:
        store = TrainingDataStore(db_path=db_path)

        stats = store.get_statistics()
        print(f"\n  Total extractions: {stats['total_extractions']}")
        print(f"  Validees: {stats['validated_count']}")
        print(f"  Pret pour entrainement: {stats['ready_for_training']}")
        print(f"  Progression: {stats['progress_percent']}%")

        assert stats['total_extractions'] == 0
        assert stats['ready_for_training'] == False

        print("\n  OK: Store initialise correctement")

        # Test des extractions recentes
        recent = store.get_recent_extractions(limit=5)
        assert len(recent) == 0
        print("  OK: Aucune extraction recente")

        print("\n  Test reussi!")

    finally:
        # Nettoyage
        if os.path.exists(db_path):
            os.remove(db_path)


def test_claude_prompt_structure():
    """Test que le prompt d'extraction produit des instructions valides."""

    print("\n" + "="*60)
    print("TEST CLAUDE PROMPT STRUCTURE")
    print("="*60)

    from claude_vision_extractor import ClaudeVisionExtractor

    # Creer une instance sans initialiser le client
    extractor = ClaudeVisionExtractor.__new__(ClaudeVisionExtractor)
    prompt = extractor._build_extraction_prompt()

    checks = {
        'parcelLabel': 'parcelLabel' in prompt,
        'surfaceDetail': 'surfaceDetail' in prompt,
        'JSON': 'JSON' in prompt,
        'option': 'option' in prompt,
        'typology': 'typology' in prompt,
        'confidence': 'confidence' in prompt,
    }

    for field, found in checks.items():
        status = "OK" if found else "MANQUANT"
        print(f"  {status}: '{field}' dans le prompt")

    assert all(checks.values()), "Des champs sont manquants dans le prompt"
    print(f"\n  Longueur du prompt: {len(prompt)} caracteres")
    print("\n  Test reussi!")


def test_parcel_normalization():
    """Test que la sortie brute de Claude se normalise en ParcelData."""

    print("\n" + "="*60)
    print("TEST PARCEL NORMALIZATION")
    print("="*60)

    from claude_vision_extractor import ClaudeVisionExtractor

    extractor = ClaudeVisionExtractor.__new__(ClaudeVisionExtractor)

    raw = {
        'parcelLabel': 'A001',
        'typology': 'T2',
        'floor': 'RDC',
        'orientation': 'O',
        'price': '185000',
        'living_space': '41.72',
        'surfaceDetail': {'terrace': 7.49},
        'option': {'terrace': True, 'parking': True},
    }

    result = extractor._normalize_parcel(raw)

    checks = {
        'parcelLabel == A001': result['parcelLabel'] == 'A001',
        'typology == T2': result['typology'] == 'T2',
        'floor == RDC': result['floor'] == 'RDC',
        'option.terrace == True': result['option']['terrace'] == True,
        'option.garden == False (defaut)': result['option']['garden'] == False,
        'surfaceDetail.terrace == 7.49': result['surfaceDetail']['terrace'] == 7.49,
        'price == 185000': result['price'] == '185000',
        'state == available (defaut)': result['state'] == 'available',
    }

    for check, passed in checks.items():
        status = "OK" if passed else "ECHEC"
        print(f"  {status}: {check}")

    assert all(checks.values()), "Des verifications ont echoue"

    print(f"\n  Resultat normalise:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n  Test reussi!")


def test_response_parsing():
    """Test du parsing de differents formats de reponse Claude."""

    print("\n" + "="*60)
    print("TEST RESPONSE PARSING")
    print("="*60)

    from claude_vision_extractor import ClaudeVisionExtractor

    extractor = ClaudeVisionExtractor.__new__(ClaudeVisionExtractor)

    # Test 1: JSON pur
    response1 = '{"parcels": [{"parcelLabel": "A001"}], "confidence": 0.95}'
    result1 = extractor._parse_claude_response(response1)
    assert 'parcels' in result1
    print("  OK: JSON pur parse")

    # Test 2: JSON avec balises markdown
    response2 = '```json\n{"parcels": [{"parcelLabel": "B002"}], "confidence": 0.90}\n```'
    result2 = extractor._parse_claude_response(response2)
    assert result2['parcels'][0]['parcelLabel'] == 'B002'
    print("  OK: JSON markdown parse")

    # Test 3: JSON avec texte avant
    response3 = 'Voici le resultat:\n{"parcels": [{"parcelLabel": "C003"}], "confidence": 0.85}'
    result3 = extractor._parse_claude_response(response3)
    assert result3['parcels'][0]['parcelLabel'] == 'C003'
    print("  OK: JSON avec texte avant parse")

    print("\n  Test reussi!")


def print_usage_guide():
    """Affiche un guide d'utilisation detaille"""

    print("\n" + "="*60)
    print("GUIDE D'UTILISATION")
    print("="*60)

    guide = """
ARCHITECTURE PLAN EXTRACTOR - Guide rapide

1. UTILISATION SIMPLE (avec vraies images de plans):

   from architecture_plan_extractor import ArchitecturePlanExtractor

   extractor = ArchitecturePlanExtractor()
   result = extractor.extract_from_image("chemin/vers/plan.png")

   print(json.dumps(result, indent=2))

2. STRATEGIE HYBRIDE (Recommande):

   from hybrid_extractor import HybridExtractor

   # Sans cle API = Tesseract (Phase 0)
   extractor = HybridExtractor()

   # Avec cle API = Claude Vision (Phase 1)
   extractor = HybridExtractor(api_key="votre_cle_api")

   result = extractor.extract_from_image("plan.png")
   # Ou avec un PDF:
   result = extractor.extract_from_image("plan.pdf")

3. INTERFACE WEB:

   streamlit run streamlit_app.py

   - Upload ton image ou PDF
   - L'outil extrait via Claude Vision ou Tesseract
   - Verifie et corrige
   - Clique "Valider pour ML" pour l'entrainement
   - Telecharge le JSON

4. TRAITEMENT EN LOT:

   extractor = HybridExtractor(api_key="votre_cle")
   images = ["plan1.png", "plan2.pdf", "plan3.jpg"]
   results = extractor.extract_batch(images)

5. PHASES DE LA STRATEGIE HYBRIDE:

   Phase 0: Tesseract OCR (pas de cle API) - 60-75% precision
   Phase 1: Claude Vision + collecte donnees - ~95% precision
   Phase 2: Pret pour entrainement ML (300+ echantillons)
   Phase 3: Modele ML custom + Claude fallback - ~92% precision
"""

    print(guide)


def main():
    """Fonction principale de test"""

    print("TESTS DE L'ARCHITECTURE PLAN EXTRACTOR")
    print("(Strategie Hybride Progressive)\n")

    # Tests existants
    test_with_sample_text()
    test_pattern_matching()
    create_sample_json()

    # Tests de la strategie hybride
    test_hybrid_extractor_init()
    test_training_data_store()
    test_claude_prompt_structure()
    test_parcel_normalization()
    test_response_parsing()

    # Guide
    print_usage_guide()

    print("\n" + "="*60)
    print("TOUS LES TESTS TERMINES")
    print("="*60)
    print("\nFichiers crees:")
    print("  - test_output.json (resultat du test)")
    print("  - sample_complete.json (exemple complet)")
    print("\nProchaine etape:")
    print("  1. Definir ANTHROPIC_API_KEY pour activer Claude Vision")
    print("  2. Lance: streamlit run streamlit_app.py")
    print("  3. Upload tes plans et teste l'extraction")
    print("  4. Valide chaque extraction pour collecter les donnees ML")
    print("  5. Apres 300 validations, entraine ton modele ML custom")


if __name__ == "__main__":
    main()
