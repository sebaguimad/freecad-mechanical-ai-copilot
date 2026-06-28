# core/parser.py

import re
from core.feature_plan import crear_feature_plan_eje


def extraer_segmentos(texto):
    """
    Extrae segmentos tipo:
    Ø20x60
    20x60
    D20x60

    Interpreta:
    primer número = diámetro
    segundo número = longitud
    """

    texto = texto.replace("Ø", "").replace("ø", "")
    texto = texto.replace("D", "").replace("d", "")

    patron = r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)"
    coincidencias = re.findall(patron, texto)

    segmentos = []

    for diametro, longitud in coincidencias:
        segmentos.append({
            "diametro": float(diametro),
            "longitud": float(longitud)
        })

    return segmentos


def prompt_a_feature_plan(prompt):
    segmentos = extraer_segmentos(prompt)

    if not segmentos:
        raise ValueError(
            "No se detectaron segmentos. Usa formato: Ø20x60, Ø30x120, Ø25x70"
        )

    return crear_feature_plan_eje(segmentos)