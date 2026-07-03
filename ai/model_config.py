# ai/model_config.py
"""
Configuración central de modelos de IA local (Ollama).

Se puede cambiar sin tocar código usando variables de entorno:
  AI_CAD_OLLAMA_URL
  AI_CAD_OLLAMA_MODEL
  AI_CAD_OLLAMA_VISION_MODEL
"""

import os

OLLAMA_URL = os.environ.get(
    "AI_CAD_OLLAMA_URL",
    "http://localhost:11434/api/generate"
).strip()

TEXT_MODEL = os.environ.get(
    "AI_CAD_OLLAMA_MODEL",
    "qwen3:8b"
).strip()

VISION_MODEL = os.environ.get(
    "AI_CAD_OLLAMA_VISION_MODEL",
    "qwen2.5vl:7b"
).strip()

# Timeouts en segundos
TEXT_TIMEOUT = int(os.environ.get("AI_CAD_TEXT_TIMEOUT", "300"))
VISION_TIMEOUT = int(os.environ.get("AI_CAD_VISION_TIMEOUT", "600"))
