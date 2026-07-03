# core/local_ai_parser.py
"""
Compatibilidad con el nombre histórico.

La lógica real vive ahora en:
  core/universal_parser.py  (clasificación + generación por familia)
  ai/ollama_client.py       (transporte)
  domains/*/spec.py         (schemas y prompts)
"""

from core.universal_parser import (
    prompt_a_feature_plan_universal,
    prompt_a_resultado_universal
)


def prompt_a_feature_plan_ollama(prompt_usuario):
    return prompt_a_feature_plan_universal(prompt_usuario)
