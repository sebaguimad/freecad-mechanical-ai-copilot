# ai/model_config.py

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