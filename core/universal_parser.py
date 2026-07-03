# core/universal_parser.py
"""
Pipeline universal de texto:

  prompt del usuario
    → clasificador (shaft | frame_structure | custom)
    → generación del design_request con el schema de esa familia
    → router: validar → corregir → plan → resumen

Este es el punto de entrada que usa el botón principal del panel.
"""

from core.classifier import clasificar_prompt
from core.domain_router import process_design_request
from core.logger import registrar_evento
from ai.ollama_client import generar_json


# Schema de frame_structure para pedidos por TEXTO (reutiliza el formato
# del parser de visión, sin imagen).
FRAME_TEXT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "family": {"type": "string"},
        "intent": {"type": "string"},
        "confidence": {"type": "number"},
        "units": {"type": "string"},
        "spec": {"type": "object", "additionalProperties": True},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["family", "intent", "confidence", "units", "spec",
                 "missing_data", "assumptions"]
}


SYSTEM_PROMPT_FRAME_TEXT = """
Eres un asistente CAD para FreeCAD especializado en estructuras de
perfiles soldados (mesas industriales, bastidores, marcos, carros,
plataformas, bancos de trabajo).

Convierte la instrucción del usuario en una especificación paramétrica.

Devuelve SOLO JSON con este formato:
{
  "family": "frame_structure",
  "intent": "crear_estructura_parametrica",
  "confidence": 0.0,
  "units": "mm",
  "spec": {
    "structure_type": "industrial_table | frame | cart | bracket | platform | unknown",
    "overall_dimensions": {"length": n, "width": n, "height": n},
    "top": {"enabled": true, "type": "plate", "length": n, "width": n, "thickness": n, "position": [n,n,n]},
    "default_profile": {"section": "square_tube", "width": n, "height": n, "thickness": n},
    "members": [{"id": "s", "role": "leg | cross_member | rail | diagonal | support | unknown",
                 "profile": {"section": "square_tube", "width": n, "height": n, "thickness": n},
                 "start": [n,n,n], "end": [n,n,n]}],
    "plates": [],
    "connections": [],
    "bom_enabled": true
  },
  "missing_data": [],
  "assumptions": []
}

Reglas:
- Usa mm.
- Si es una mesa industrial sin medidas: largo 1200, ancho 700, alto 850,
  cubierta 6 mm, tubo 40x40x3, y decláralo en assumptions.
- Toda medida no indicada por el usuario va en assumptions.
/no_think
""".strip()


def _generar_design_request_frame_texto(prompt):
    req = generar_json(
        system_prompt=SYSTEM_PROMPT_FRAME_TEXT,
        user_prompt=prompt,
        schema=FRAME_TEXT_SCHEMA
    )
    req["family"] = "frame_structure"
    req.setdefault("intent", "crear_estructura_parametrica")
    req.setdefault("units", "mm")
    req.setdefault("spec", {})
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])
    return req


def prompt_a_resultado_universal(prompt_usuario):
    """
    Devuelve el resultado completo del router:
    {domain, feature_plan, summary, corrected_spec, validation_report, ...}
    """
    clasificacion = clasificar_prompt(prompt_usuario)
    family = clasificacion["family"]

    registrar_evento({
        "stage": "classification",
        "family": family,
        "confidence": clasificacion.get("confidence"),
        "motivo": clasificacion.get("motivo", "")
    })

    if family == "shaft":
        from domains.shaft.spec import generar_design_request
        design_request = generar_design_request(prompt_usuario)

    elif family == "frame_structure":
        design_request = _generar_design_request_frame_texto(prompt_usuario)

    else:
        from domains.custom.spec import generar_design_request
        design_request = generar_design_request(prompt_usuario)

    resultado = process_design_request(design_request, prompt_usuario)
    resultado["classification"] = clasificacion
    return resultado


def prompt_a_feature_plan_universal(prompt_usuario):
    """
    Versión que devuelve solo el feature_plan (compatibilidad con el panel
    y scripts existentes).
    """
    return prompt_a_resultado_universal(prompt_usuario)["feature_plan"]
