"""Pipeline universal de texto: clasificar -> design_request -> validar -> plan."""

# Instalar el executor avanzado como reemplazo compatible antes de que el panel
# importe FeatureExecutor desde core.executor. Asi no rompemos codigo legado.
import core.executor as _executor_module
from core.executor_advanced import AdvancedFeatureExecutor
_executor_module.FeatureExecutor = AdvancedFeatureExecutor

from core.classifier import clasificar_prompt
from core.domain_router import process_design_request
from core.logger import registrar_evento
from ai.ollama_client import generar_json

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
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["family", "intent", "confidence", "units", "spec", "missing_data", "assumptions"],
}

SYSTEM_PROMPT_FRAME_TEXT = """
Eres un asistente CAD para FreeCAD especializado en estructuras de perfiles
soldados: mesas industriales, bastidores, marcos, carros y plataformas.
Convierte la instruccion del usuario en una especificacion parametrica.

Devuelve SOLO JSON con:
{
  "family":"frame_structure",
  "intent":"crear_estructura_parametrica",
  "confidence":0.0,
  "units":"mm",
  "spec":{
    "structure_type":"industrial_table | frame | cart | bracket | platform | unknown",
    "overall_dimensions":{"length":n,"width":n,"height":n},
    "top":{"enabled":true,"type":"plate","length":n,"width":n,"thickness":n,"position":[n,n,n]},
    "default_profile":{"section":"square_tube","width":n,"height":n,"thickness":n},
    "members":[{"id":"s","role":"leg | cross_member | rail | diagonal | support | unknown","profile":{"section":"square_tube","width":n,"height":n,"thickness":n},"start":[n,n,n],"end":[n,n,n]}],
    "plates":[],"connections":[],"bom_enabled":true
  },
  "missing_data":[],"assumptions":[]
}
Reglas: usa mm; toda medida no indicada va en assumptions. Para una mesa sin
medidas usa 1200x700x850, cubierta 6 y tubo 40x40x3. /no_think
""".strip()


def _generar_design_request_frame_texto(prompt):
    req = generar_json(system_prompt=SYSTEM_PROMPT_FRAME_TEXT, user_prompt=prompt, schema=FRAME_TEXT_SCHEMA)
    req["family"] = "frame_structure"
    req.setdefault("intent", "crear_estructura_parametrica")
    req.setdefault("units", "mm")
    req.setdefault("spec", {})
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])
    return req


def prompt_a_resultado_universal(prompt_usuario):
    clasificacion = clasificar_prompt(prompt_usuario)
    family = clasificacion["family"]
    registrar_evento({
        "stage": "classification",
        "family": family,
        "confidence": clasificacion.get("confidence"),
        "motivo": clasificacion.get("motivo", ""),
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
    return prompt_a_resultado_universal(prompt_usuario)["feature_plan"]
