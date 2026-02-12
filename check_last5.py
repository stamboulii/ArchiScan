import sqlite3

conn = sqlite3.connect('training_data.db')
cursor = conn.cursor()

# Get last 5 extractions
cursor.execute('''
    SELECT id, validated_by_user, extraction_method, SUBSTR(extracted_json, 1, 100)
    FROM extractions
    ORDER BY id DESC
    LIMIT 5
''')
print("Last 5 extractions:")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Validee: {row[1]}, Methode: {row[2]}")
    print(f"  Data: {row[3]}...")

conn.close()
