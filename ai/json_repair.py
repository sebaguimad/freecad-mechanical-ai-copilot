# ai/json_repair.py

import json
import re


def limpiar_json_respuesta(texto):
    """
    Extrae JSON válido desde una respuesta del modelo.
    """
    if texto is None:
        raise ValueError("Respuesta vacía: no hay texto para parsear.")

    texto = texto.strip()

    if texto.startswith("```"):
        texto = texto.replace("```json", "")
        texto = texto.replace("```", "")
        texto = texto.strip()

    try:
        return json.loads(texto)
    except Exception:
        pass

    match = re.search(r"\{.*\}", texto, flags=re.DOTALL)

    if not match:
        raise ValueError(
            "No se encontró JSON válido en la respuesta de la IA.\n"
            f"Respuesta recibida:\n{texto}"
        )

    return json.loads(match.group(0))