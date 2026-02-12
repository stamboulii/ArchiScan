import sqlite3
conn = sqlite3.connect('training_data.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM extractions')
total = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM extractions WHERE validated_by_user=1')
validated = cursor.fetchone()[0]
cursor.execute('SELECT MAX(id) FROM extractions')
max_id = cursor.fetchone()[0]
conn.close()

with open('db_status.txt', 'w') as f:
    f.write(f"Total: {total}\n")
    f.write(f"Validees: {validated}\n")
    f.write(f"Max ID: {max_id}\n")

print(f"Total: {total}")
print(f"Validees: {validated}")
print(f"Max ID: {max_id}")
