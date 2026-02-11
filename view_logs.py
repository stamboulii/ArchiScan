#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour visualiser et analyser les logs d'extraction.
Usage: python view_logs.py [options]
"""

import json
import sys
import io
from pathlib import Path
from datetime import datetime

# Force UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

LOG_FILE = Path("extraction_log.jsonl")


def read_logs(log_file: Path = None) -> list:
    """Lit tous les logs depuis le fichier."""
    log_file = log_file or LOG_FILE
    if not log_file.exists():
        print(f"❌ Fichier de log non trouvé: {log_file}")
        return []
    
    logs = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    return logs


def show_recent_sessions(n: int = 5):
    """Affiche les n sessions les plus récentes."""
    logs = read_logs()
    if not logs:
        print("Aucun log trouvé.")
        return
    
    # Grouper par session_id
    sessions = {}
    for entry in logs:
        sid = entry.get('session_id', 'unknown')
        if sid not in sessions:
            sessions[sid] = []
        sessions[sid].append(entry)
    
    # Trier par timestamp
    sorted_sessions = sorted(sessions.items(), key=lambda x: x[1][0]['timestamp'], reverse=True)
    
    print(f"\n📊 {len(sorted_sessions)} sessions trouvées\n")
    
    for i, (session_id, entries) in enumerate(sorted_sessions[:n], 1):
        first_entry = entries[0]
        last_entry = entries[-1]
        
        print(f"Session {i}: {session_id}")
        print(f"   Début: {first_entry['timestamp']}")
        print(f"   Événements: {len(entries)}")
        
        # Compter les succès/échecs
        successes = sum(1 for e in entries if e.get('success') == True)
        failures = sum(1 for e in entries if e.get('success') == False)
        print(f"   Succès: {successes}, Échecs: {failures}")
        print()


def show_session_details(session_id: str):
    """Affiche les détails d'une session spécifique."""
    logs = read_logs()
    session_logs = [e for e in logs if e.get('session_id') == session_id]
    
    if not session_logs:
        print(f"Session '{session_id}' non trouvée.")
        return
    
    print(f"\n📋 Détails de la session: {session_id}")
    print(f"Nombre d'événements: {len(session_logs)}\n")
    print("-" * 60)
    
    for i, entry in enumerate(session_logs, 1):
        timestamp = entry.get('timestamp', '')[:19]
        event = entry.get('event', 'unknown')
        status = entry.get('status', '')
        method = entry.get('method', '')
        error = entry.get('error', '')
        success = entry.get('success')
        
        status_icon = "✅" if success else "❌" if success == False else "⏳"
        
        print(f"{i:3}. [{timestamp}] {status_icon} {event}")
        
        if method:
            print(f"     Méthode: {method}")
        if error:
            print(f"     Erreur: {error[:100]}")
        if status:
            print(f"     Statut: {status}")
        print()


def show_all_errors():
    """Affiche tous les événements en erreur."""
    logs = read_logs()
    errors = [e for e in logs if e.get('success') == False]
    
    if not errors:
        print("\n✅ Aucune erreur trouvée dans les logs.")
        return
    
    print(f"\n❌ {len(errors)} erreurs trouvées:\n")
    
    for i, entry in enumerate(errors, 1):
        timestamp = entry.get('timestamp', '')[:19]
        event = entry.get('event', 'unknown')
        error = entry.get('error', '')
        method = entry.get('method', '')
        
        print(f"{i}. [{timestamp}] {event}")
        if method:
            print(f"   Méthode: {method}")
        print(f"   Erreur: {error[:150]}")
        print()


def export_session_csv(session_id: str, output_file: str = None):
    """Exporte une session en CSV."""
    import csv
    
    logs = read_logs()
    session_logs = [e for e in logs if e.get('session_id') == session_id]
    
    if not session_logs:
        print(f"Session '{session_id}' non trouvée.")
        return
    
    output_file = output_file or f"session_{session_id}.csv"
    
    fieldnames = ['timestamp', 'session_id', 'event', 'method', 'success', 'error', 'details']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in session_logs:
            row = {k: entry.get(k, '') for k in fieldnames}
            row['details'] = json.dumps(entry.get('details', {}), ensure_ascii=False)
            writer.writerow(row)
    
    print(f"\n📁 Session exportée vers: {output_file}")


def show_help():
    """Affiche l'aide."""
    print("""
🔍 Visionneur de Logs ArchiExtract

Usage: python view_logs.py [commande]

Commandes:
    (rien)          Affiche les sessions récentes
    errors          Affiche toutes les erreurs
    details <id>    Affiche les détails d'une session
    export <id>     Exporte une session en CSV
    help            Affiche cette aide

Exemples:
    python view_logs.py
    python view_logs.py errors
    python view_logs.py details session_20250101_120000
    python view_logs.py export session_20250101_120000

Fichier de log: extraction_log.jsonl
""")


def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 2:
        show_recent_sessions()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'help' or command == '--help':
        show_help()
    elif command == 'errors':
        show_all_errors()
    elif command == 'details':
        if len(sys.argv) < 3:
            print("❌ ID de session requis: python view_logs.py details <session_id>")
            return
        show_session_details(sys.argv[2])
    elif command == 'export':
        if len(sys.argv) < 3:
            print("❌ ID de session requis: python view_logs.py export <session_id>")
            return
        output_file = sys.argv[3] if len(sys.argv) > 3 else None
        export_session_csv(sys.argv[2], output_file)
    elif command == 'sessions':
        show_recent_sessions(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        print(f"❌ Commande inconnue: {command}")
        show_help()


if __name__ == "__main__":
    main()
