import sqlite3
import json

conn = sqlite3.connect('training_data.db')
cursor = conn.cursor()

# Extractions total
cursor.execute('SELECT COUNT(*) FROM extractions')
total = cursor.fetchone()[0]
print(f"Total extractions: {total}")

# Extractions validees
cursor.execute('SELECT COUNT(*) FROM extractions WHERE validated_by_user=1')
validated = cursor.fetchone()[0]
print(f"Validees: {validated}")

# Liste des extractions validadas
cursor.execute('''
    SELECT id, image_path, extraction_method, confidence, extracted_json
    FROM extractions
    WHERE validated_by_user=1
    ORDER BY id DESC
''')

print("\n--- Extractions Validees ---")
for row in cursor.fetchall():
    print(f"\nID: {row[0]}")
    print(f"Fichier: {row[1]}")
    print(f"Methode: {row[2]}")
    print(f"Confiance: {row[3]}%")
    data = json.loads(row[4])
    print(f"ParcelLabel: {data.get('parcelLabel', 'N/A')}")
    print(f"Typology: {data.get('typology', 'N/A')}")
    print(f"Surface: {data.get('living_space', 'N/A')} m2")

conn.close()
