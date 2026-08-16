# ai/feature_patch_critic.py
"""Convierte feedback CAD en cambios puntuales sobre un Feature Plan existente."""

import json

from ai.ollama_client import generar_json


PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "strategy": {"type": "string", "enum": ["patch", "regenerate"]},
        "summary": {"type": "string"},
        "patches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "update_feature", "replace_feature", "insert_feature",
                            "delete_feature", "suppress_feature", "unsuppress_feature"
                        ]
                    },
                    "target_feature_id": {"type": "string"},
                    "position": {"type": "string"},
                    "changes": {"type": "object", "additionalProperties": True},
                    "feature": {"type": "object", "additionalProperties": True},
                    "reason": {"type": "string"},
                },
                "required": ["action", "reason"],
            },
        },
    },
    "required": ["strategy", "summary", "patches"],
}


SYSTEM_PROMPT = """
Eres un agente CAD que corrige un FEATURE PLAN existente sin empezar de cero.

Objetivo: conservar todas las operaciones correctas y modificar SOLO lo necesario.
Prefiere strategy=patch siempre que el error pueda localizarse en uno o pocos
features. Usa strategy=regenerate solo si la estrategia completa de modelado es
incorrecta o si no puedes identificar de forma segura que feature debe cambiar.

Acciones permitidas:
- update_feature: cambia parametros de un feature. target_feature_id + changes.
- replace_feature: reemplaza el contenido de un feature conservando su id.
- insert_feature: agrega feature antes/despues de target_feature_id; incluye feature.
- delete_feature: elimina un feature.
- suppress_feature / unsuppress_feature: desactiva/reactiva sin perder historial.

REGLAS IMPORTANTES:
- No cambies ids existentes con update_feature.
- No inventes referencias a features futuros.
- Si modificas un solid_add/solid_cut, normalmente cambia dentro de shape.
  Ejemplo: {"changes":{"shape":{"diameter":42}}}.
- Para mover un agujero: modifica shape.position del solid_cut correspondiente.
- Para cambiar un patron: modifica count/spacing/direction del feature de patron.
- Para cambiar simetria: modifica plane/offset del feature mirror.
- Para filetes: modifica radius. Para chaflanes: distance.
- Conserva lo que ya coincide con la referencia.
- Devuelve pocos patches, concretos y trazables.
- Si necesitas una operacion nueva, usa insert_feature con un id nuevo unico.

Devuelve SOLO JSON valido.
""".strip()


def proponer_patches(feature_plan, critic, inspection=None, prompt_usuario=""):
    contexto = (
        f"PROMPT ORIGINAL:\n{prompt_usuario}\n\n"
        f"FEEDBACK DEL REVISOR:\n{json.dumps(critic, ensure_ascii=False)}\n\n"
        f"INSPECCION FREECAD:\n{json.dumps(inspection or {}, ensure_ascii=False)}\n\n"
        f"FEATURE PLAN ACTUAL:\n{json.dumps(feature_plan, ensure_ascii=False)}"
    )
    return generar_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=contexto,
        schema=PATCH_SCHEMA,
        temperature=0.05,
    )
