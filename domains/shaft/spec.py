# domains/shaft/spec.py
"""
Schema y prompt del dominio shaft (eje escalonado).

Mejora clave respecto a la versión anterior:
la IA ahora devuelve "longitud_total" como campo explícito (nullable),
de modo que el validador NO necesita re-parsear el prompt con regex
frágiles para saber la longitud objetivo.
"""

from ai.ollama_client import generar_json


SHAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string"},
        "units": {"type": "string"},
        "longitud_total": {
            "anyOf": [{"type": "number"}, {"type": "null"}]
        },
        "segmentos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "diametro": {"type": "number"},
                    "longitud": {"type": "number"}
                },
                "required": ["diametro", "longitud"]
            }
        },
        "chaveteros": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tramo_index": {"type": "integer"},
                    "ancho": {"type": "number"},
                    "profundidad": {"type": "number"},
                    "longitud": {"type": "number"},
                    "offset_desde_inicio": {
                        "anyOf": [{"type": "number"}, {"type": "null"}]
                    }
                },
                "required": ["tramo_index", "ancho", "profundidad",
                             "longitud", "offset_desde_inicio"]
            }
        },
        "filetes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"radio": {"type": "number"}},
                "required": ["radio"]
            }
        },
        "roscas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tramo_index": {"type": "integer"},
                    "diametro_nominal": {"type": "number"},
                    "longitud": {"type": "number"},
                    "lado": {"type": "string", "enum": ["izquierdo", "derecho"]}
                },
                "required": ["tramo_index", "diametro_nominal", "longitud", "lado"]
            }
        },
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["intent", "units", "longitud_total", "segmentos", "chaveteros",
                 "filetes", "roscas", "missing_data", "assumptions"]
}


SYSTEM_PROMPT_SHAFT = """
Eres un asistente CAD mecánico local para FreeCAD.

Convierte instrucciones en lenguaje natural a una especificación JSON para
generar un eje escalonado en FreeCAD.

Reglas obligatorias:
- Responde SOLO JSON válido, sin explicación ni código.
- Las unidades son mm.
- intent debe ser crear_eje_escalonado.
- units debe ser mm.
- longitud_total: si el usuario indica la longitud total del eje, ponla aquí.
  Si no la indica, usa null.
- segmentos representa tramos cilíndricos en orden de izquierda a derecha,
  cada uno con diametro y longitud.
- tramo_index parte desde 0. Si el usuario dice tramo 1, usar tramo_index = 0.
  Si dice tramo central, usar el tramo del medio.
- Si pide extremos delgados y centro robusto, propón 3 segmentos.
- Si da longitud total pero no todas las longitudes, reparte longitudes
  razonables cuya suma sea la longitud total.
- Si pide chavetero sin medidas, usa ancho 8, profundidad 3.3, longitud 40.
- Si pide rosca M20 sin longitud, usa longitud 20.
- Rosca derecha va en el último tramo; rosca izquierda en el primero.
- Si falta información técnica, decláralo en missing_data.
- Toda suposición que hagas, decláralo en assumptions.
- No inventes features fuera de: segmentos, chaveteros, filetes, roscas.
/no_think
""".strip()


def generar_design_request(prompt_usuario):
    spec = generar_json(
        system_prompt=SYSTEM_PROMPT_SHAFT,
        user_prompt=prompt_usuario,
        schema=SHAFT_SCHEMA
    )

    return {
        "family": "shaft",
        "intent": spec.get("intent", "crear_eje_escalonado"),
        "confidence": 0.9,
        "units": "mm",
        "spec": spec,
        "missing_data": spec.get("missing_data", []),
        "assumptions": spec.get("assumptions", [])
    }
