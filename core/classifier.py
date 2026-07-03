# core/classifier.py
"""
Clasificador de intención.

Paso 1 del pipeline universal:
  prompt del usuario → familia (shaft | frame_structure | custom)

Si la IA no está segura, cae a "custom", que es el dominio universal.
Incluye un pre-clasificador por palabras clave para ahorrar una llamada
al modelo en los casos obvios.
"""

from ai.ollama_client import generar_json
from core.capabilities import capabilities_como_texto


CLASSIFIER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "family": {
            "type": "string",
            "enum": ["shaft", "frame_structure", "custom"]
        },
        "confidence": {"type": "number"},
        "motivo": {"type": "string"}
    },
    "required": ["family", "confidence", "motivo"]
}


SYSTEM_PROMPT_CLASSIFIER = f"""
Eres un clasificador de pedidos de diseño mecánico CAD.

Tu única tarea: leer la instrucción del usuario y decidir qué familia
del sistema debe procesarla.

{capabilities_como_texto()}

Reglas:
- Responde SOLO JSON válido.
- family debe ser exactamente uno de: shaft, frame_structure, custom.
- shaft: SOLO si el pedido es un eje de transmisión escalonado.
- frame_structure: SOLO si es una estructura de perfiles/tubos soldados
  (mesa, bastidor, marco, carro, plataforma, banco de trabajo).
- custom: para TODO lo demás (engranajes, bridas, poleas, soportes,
  bujes, placas con agujeros, ménsulas, piezas raras).
- Si dudas entre dos familias, usa custom.
- confidence entre 0.0 y 1.0.
/no_think
""".strip()


_SHAFT_KEYWORDS = ("eje escalonado", "eje de transmis", "chavetero", "tramo")
_FRAME_KEYWORDS = ("mesa", "bastidor", "marco soldado", "banco de trabajo",
                   "estructura de perfil", "estructura de tubo", "carro metálico",
                   "plataforma")


def _clasificar_por_keywords(prompt):
    """
    Atajo determinista para casos obvios. Devuelve None si no hay match claro.
    """
    texto = prompt.lower()

    es_shaft = any(k in texto for k in _SHAFT_KEYWORDS) or (
        "eje" in texto and ("Ø".lower() in texto or "diametro" in texto
                            or "diámetro" in texto or "rosca" in texto)
    )
    es_frame = any(k in texto for k in _FRAME_KEYWORDS)

    if es_shaft and not es_frame:
        return {"family": "shaft", "confidence": 0.9,
                "motivo": "Palabras clave de eje detectadas."}
    if es_frame and not es_shaft:
        return {"family": "frame_structure", "confidence": 0.9,
                "motivo": "Palabras clave de estructura detectadas."}
    return None


def clasificar_prompt(prompt, usar_ia=True):
    atajo = _clasificar_por_keywords(prompt)
    if atajo is not None:
        return atajo

    if not usar_ia:
        return {"family": "custom", "confidence": 0.5,
                "motivo": "Clasificación por defecto sin IA."}

    resultado = generar_json(
        system_prompt=SYSTEM_PROMPT_CLASSIFIER,
        user_prompt=prompt,
        schema=CLASSIFIER_SCHEMA
    )

    family = resultado.get("family", "custom")
    if family not in ("shaft", "frame_structure", "custom"):
        family = "custom"

    try:
        confidence = float(resultado.get("confidence", 0.5))
    except Exception:
        confidence = 0.5

    # Con baja confianza, custom es el camino más seguro y universal.
    if confidence < 0.55 and family != "custom":
        return {"family": "custom", "confidence": confidence,
                "motivo": f"Confianza baja ({confidence:.2f}); se usa dominio universal."}

    return {"family": family, "confidence": confidence,
            "motivo": resultado.get("motivo", "")}
