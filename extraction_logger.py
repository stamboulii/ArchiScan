"""
Système de logging pour le debugging des extractions ArchiExtract.
Enregistre chaque étape du processus dans un fichier de log.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import contextmanager

# Configuration du logger principal
LOG_FILE = Path("extraction_log.jsonl")

# Logger pour ce module
logger = logging.getLogger(__name__)


class ExtractionLogger:
    """
    Logger structuré pour les extractions.
    Écrit les logs au format JSON Lines pour faciliter l'analyse.
    """
    
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or LOG_FILE
        self.session_id = self._generate_session_id()
        self._ensure_log_file()
    
    def _generate_session_id(self) -> str:
        """Génère un ID de session unique."""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _ensure_log_file(self):
        """Crée le fichier de log s'il n'existe pas."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_extraction_start(self, image_path: str, method: str = "auto") -> dict:
        """Log le début d'une extraction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "extraction_start",
            "image_path": str(image_path),
            "method": method,
            "status": "started"
        }
        self._write_entry(entry)
        return entry
    
    def log_extraction_step(self, step_name: str, details: Dict = None, status: str = "running"):
        """Log une étape de l'extraction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "extraction_step",
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        self._write_entry(entry)
        return entry
    
    def log_method_attempt(self, method: str, success: bool, error: str = None, result_keys: list = None):
        """Log une tentative de méthode d'extraction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "method_attempt",
            "method": method,
            "success": success,
            "error": error,
            "result_keys": result_keys
        }
        self._write_entry(entry)
        return entry
    
    def log_claude_api_call(self, model: str, tokens_used: int = None, response_time_ms: int = None, 
                           success: bool = True, error: str = None):
        """Log un appel à l'API Claude."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "claude_api_call",
            "model": model,
            "tokens_used": tokens_used,
            "response_time_ms": response_time_ms,
            "success": success,
            "error": error
        }
        self._write_entry(entry)
        return entry
    
    def log_tesseract_ocr(self, image_path: str, text_length: int, success: bool, error: str = None):
        """Log une exécution Tesseract OCR."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "tesseract_ocr",
            "image_path": str(image_path),
            "text_length": text_length,
            "success": success,
            "error": error
        }
        self._write_entry(entry)
        return entry
    
    def log_extraction_result(self, extraction_id: int, method: str, confidence: float = None, 
                            validation_status: str = "pending"):
        """Log le résultat final de l'extraction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "extraction_result",
            "extraction_id": extraction_id,
            "method": method,
            "confidence": confidence,
            "validation_status": validation_status
        }
        self._write_entry(entry)
        return entry
    
    def log_fallback(self, from_method: str, to_method: str, reason: str):
        """Log un basculement de méthode (fallback)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "fallback",
            "from_method": from_method,
            "to_method": to_method,
            "reason": reason
        }
        self._write_entry(entry)
        return entry
    
    def log_extraction_end(self, success: bool, extraction_id: int = None, error: str = None):
        """Log la fin d'une extraction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "extraction_end",
            "success": success,
            "extraction_id": extraction_id,
            "error": error,
            "duration_ms": self._get_duration()
        }
        self._write_entry(entry)
        return entry
    
    def log_phase_transition(self, from_phase: int, to_phase: int, reason: str):
        """Log un changement de phase."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event": "phase_transition",
            "from_phase": from_phase,
            "to_phase": to_phase,
            "reason": reason
        }
        self._write_entry(entry)
        return entry
    
    def _write_entry(self, entry: dict):
        """Écrit une entrée dans le fichier de log."""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[LOG ERROR] Cannot write to log file: {e}")
    
    def _get_duration(self) -> int:
        """Calcule la durée de la session en millisecondes."""
        # Cette méthode serait améliorée avec un计时器 réel
        return 0
    
    def get_session_logs(self) -> list:
        """Récupère tous les logs de la session actuelle."""
        logs = []
        if self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get('session_id') == self.session_id:
                            logs.append(entry)
        return logs
    
    def export_session_report(self, output_path: Path = None) -> str:
        """Exporte un rapport lisible de la session."""
        if output_path is None:
            output_path = Path(f"report_{self.session_id}.txt")
        
        logs = self.get_session_logs()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"RAPPORT D'EXTRACTION\n")
            f.write(f"{'='*50}\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Nombre d'entrées: {len(logs)}\n")
            f.write(f"{'='*50}\n\n")
            
            for i, entry in enumerate(logs, 1):
                f.write(f"[{i}] {entry['timestamp']}\n")
                f.write(f"    Événement: {entry['event']}\n")
                for key, value in entry.items():
                    if key not in ['timestamp', 'session_id', 'event']:
                        f.write(f"    {key}: {value}\n")
                f.write("\n")
        
        return str(output_path)


# Instance globale du logger
_extraction_logger: Optional[ExtractionLogger] = None


def get_logger() -> ExtractionLogger:
    """Récupère l'instance globale du logger."""
    global _extraction_logger
    if _extraction_logger is None:
        _extraction_logger = ExtractionLogger()
    return _extraction_logger


def log_extraction_start(image_path: str, method: str = "auto") -> dict:
    """Convenience function pour logger le début d'une extraction."""
    return get_logger().log_extraction_start(image_path, method)


def log_extraction_end(success: bool, extraction_id: int = None, error: str = None):
    """Convenience function pour logger la fin d'une extraction."""
    get_logger().log_extraction_end(success, extraction_id, error)


def log_method_attempt(method: str, success: bool, error: str = None, result_keys: list = None):
    """Convenience function pour logger une tentative de méthode."""
    get_logger().log_method_attempt(method, success, error, result_keys)


def log_fallback(from_method: str, to_method: str, reason: str):
    """Convenience function pour logger un fallback."""
    get_logger().log_fallback(from_method, to_method, reason)


def log_tesseract_ocr(image_path: str, text_length: int, success: bool, error: str = None):
    """Convenience function pour logger une exécution Tesseract."""
    get_logger().log_tesseract_ocr(image_path, text_length, success, error)


def log_claude_api_call(model: str, tokens_used: int = None, response_time_ms: int = None,
                       success: bool = True, error: str = None):
    """Convenience function pour logger un appel API Claude."""
    get_logger().log_claude_api_call(model, tokens_used, response_time_ms, success, error)


# Context manager pour les sessions d'extraction
@contextmanager
def extraction_session(image_path: str, method: str = "auto"):
    """Context manager pour une session d'extraction avec logging automatique."""
    logger = get_logger()
    logger.log_extraction_start(image_path, method)
    try:
        yield logger
        logger.log_extraction_end(success=True)
    except Exception as e:
        logger.log_extraction_end(success=False, error=str(e))
        raise


if __name__ == "__main__":
    # Test du logger
    print("Test du système de logging...")
    
    log = ExtractionLogger()
    
    # Log de test
    log.log_extraction_start("/path/to/plan.png", "claude")
    log.log_method_attempt("claude", False, "Credit limit reached")
    log.log_fallback("claude", "tesseract", "API error")
    log.log_tesseract_ocr("/path/to/plan.png", 150, True)
    log.log_extraction_end(success=True, extraction_id=1)
    
    print(f"\nLogs écrits dans: {log.log_file}")
    print("\nContenu du fichier:")
    if log.log_file.exists():
        with open(log.log_file, 'r') as f:
            print(f.read())
    
    # Exporter le rapport
    report_path = log.export_session_report()
    print(f"\nRapport exporté vers: {report_path}")
