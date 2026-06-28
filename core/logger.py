# core/logger.py

import json
import time
from pathlib import Path

LOG_DIR = Path.home() / "AIDibujanteLogs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = LOG_DIR / "cad_generation_log.jsonl"


def registrar_evento(evento):
    evento["timestamp"] = time.time()

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def obtener_ruta_log():
    return str(LOG_PATH)