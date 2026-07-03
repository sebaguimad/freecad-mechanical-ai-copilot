# core/parser.py
"""
Parser simple sin IA: "Ø20x60, Ø30x120, Ø25x70" → plan de eje escalonado.
Ahora reutiliza el planner formal del dominio shaft.
"""

import re

from domains.shaft.validator import validate
from domains.shaft.planner import build_plan


def extraer_segmentos(texto):
    """
    Extrae segmentos tipo Ø20x60, 20x60, D20x60.
    Primer número = diámetro, segundo = longitud.
    """
    texto = texto.replace("Ø", "").replace("ø", "")
    texto = texto.replace("D", "").replace("d", "")

    patron = r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)"
    coincidencias = re.findall(patron, texto)

    return [
        {"diametro": float(diametro), "longitud": float(longitud)}
        for diametro, longitud in coincidencias
    ]


def prompt_a_feature_plan(prompt):
    segmentos = extraer_segmentos(prompt)

    if not segmentos:
        raise ValueError(
            "No se detectaron segmentos. Usa formato: Ø20x60, Ø30x120, Ø25x70"
        )

    spec = {
        "intent": "crear_eje_escalonado",
        "units": "mm",
        "longitud_total": None,
        "segmentos": segmentos,
        "chaveteros": [],
        "filetes": [],
        "roscas": [],
        "missing_data": [],
        "assumptions": ["Plan generado con el parser simple, sin IA."]
    }

    corrected, reporte = validate(spec, prompt=prompt)

    if reporte["status"] == "error":
        detalles = "\n".join(f"- {e}" for e in reporte["errors"])
        raise ValueError(f"Segmentos inválidos:\n{detalles}")

    return build_plan(corrected, validation_report=reporte)
