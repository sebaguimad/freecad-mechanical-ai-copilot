# ai/model_critic.py
"""Critico visual para comparar referencia vs resultado generado en FreeCAD."""

import json

from ai.ollama_client import generar_json_desde_imagenes, generar_json


CRITIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["accept", "regenerate"]},
        "score": {"type": "number"},
        "summary": {"type": "string"},
        "problems": {"type": "array", "items": {"type": "string"}},
        "correction_instructions": {"type": "string"},
    },
    "required": ["decision", "score", "summary", "problems", "correction_instructions"],
}


SYSTEM_PROMPT_VISUAL_CRITIC = """
Eres un revisor CAD mecanico. Debes evaluar si un modelo CAD generado es una
recreacion APROXIMADA razonable de una referencia. No exijas copia exacta.

Las imagenes se entregan en este orden:
1) imagen/plano de referencia original;
2+) capturas del modelo generado en FreeCAD (isometrica, frontal, lateral).

Evalua:
- silueta y topologia general;
- numero y posicion relativa de cuerpos, agujeros, brazos y salientes;
- simetrias y patrones;
- proporciones globales;
- si la estrategia CAD elegida tiene sentido.

No penalices detalles pequenos, color, material, textura, iluminacion ni acabado.
Si la forma principal coincide razonablemente, usa decision=accept.
Si hay errores estructurales claros, usa decision=regenerate y escribe instrucciones
concretas para corregir el siguiente intento.

score: 0 a 1. Usa accept normalmente desde 0.70 si no hay errores estructurales.
Devuelve SOLO JSON.
""".strip()


SYSTEM_PROMPT_GEOMETRIC_CRITIC = """
Eres un revisor CAD mecanico. Recibiras un prompt original, un feature plan,
el resultado de ejecucion y metricas geometricas de FreeCAD. Decide si el modelo
es suficientemente coherente para una recreacion aproximada.

Regenera si hay errores de ejecucion, shape invalido, volumen cero, ausencia de
solidos, dimensiones absurdas o multiples cuerpos desconectados cuando el pedido
parece requerir una sola pieza. No exijas precision de fabricacion.

Devuelve SOLO JSON con decision, score, summary, problems y correction_instructions.
""".strip()


def criticar_con_referencia(reference_image, generated_images, prompt_usuario,
                            inspection, feature_plan):
    paths = [reference_image] + list(generated_images or [])
    contexto = (
        f"PROMPT ORIGINAL:\n{prompt_usuario}\n\n"
        f"INSPECCION FREECAD:\n{json.dumps(inspection, ensure_ascii=False)}\n\n"
        f"FEATURE PLAN:\n{json.dumps(feature_plan, ensure_ascii=False)}"
    )
    return generar_json_desde_imagenes(
        system_prompt=SYSTEM_PROMPT_VISUAL_CRITIC,
        image_paths=paths,
        user_prompt=contexto,
        schema=CRITIC_SCHEMA,
        temperature=0.05,
    )


def criticar_sin_referencia(prompt_usuario, inspection, feature_plan, execution):
    contexto = (
        f"PROMPT ORIGINAL:\n{prompt_usuario}\n\n"
        f"INSPECCION FREECAD:\n{json.dumps(inspection, ensure_ascii=False)}\n\n"
        f"EJECUCION:\n{json.dumps(execution, ensure_ascii=False)}\n\n"
        f"FEATURE PLAN:\n{json.dumps(feature_plan, ensure_ascii=False)}"
    )
    return generar_json(
        system_prompt=SYSTEM_PROMPT_GEOMETRIC_CRITIC,
        user_prompt=contexto,
        schema=CRITIC_SCHEMA,
        temperature=0.05,
    )
