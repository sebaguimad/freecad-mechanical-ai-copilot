# core/local_ai_parser.py

import json
import os
import re
import urllib.request
import urllib.error

from core.feature_plan import crear_feature_plan_eje
from core.plan_validator import validar_y_corregir_design_spec


OLLAMA_URL = "http://localhost:11434/api/generate"


DESIGN_SPEC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string"
        },
        "units": {
            "type": "string"
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
                        "anyOf": [
                            {"type": "number"},
                            {"type": "null"}
                        ]
                    }
                },
                "required": [
                    "tramo_index",
                    "ancho",
                    "profundidad",
                    "longitud",
                    "offset_desde_inicio"
                ]
            }
        },
        "filetes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "radio": {"type": "number"}
                },
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
                    "lado": {
                        "type": "string",
                        "enum": ["izquierdo", "derecho"]
                    }
                },
                "required": [
                    "tramo_index",
                    "diametro_nominal",
                    "longitud",
                    "lado"
                ]
            }
        },
        "missing_data": {
            "type": "array",
            "items": {"type": "string"}
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "intent",
        "units",
        "segmentos",
        "chaveteros",
        "filetes",
        "roscas",
        "missing_data",
        "assumptions"
    ]
}


SYSTEM_PROMPT = """
Eres un asistente CAD mecánico local para FreeCAD.

Convierte instrucciones en lenguaje natural a una especificación JSON para generar
un eje escalonado en FreeCAD.

Reglas obligatorias:
- Responde SOLO JSON válido.
- No escribas explicación.
- No escribas código Python.
- Las unidades son mm.
- intent debe ser crear_eje_escalonado.
- units debe ser mm.
- segmentos representa tramos cilíndricos en orden de izquierda a derecha.
- Cada segmento tiene diametro y longitud.
- tramo_index parte desde 0.
- Si el usuario dice tramo 1, usar tramo_index = 0.
- Si dice tramo 2, usar tramo_index = 1.
- Si dice tramo central, usar el tramo del medio.
- Si pide un eje con extremos delgados y centro robusto, propón 3 segmentos.
- Si pide longitud total pero no da todas las longitudes, reparte longitudes razonables.
- Si pide chavetero pero no da medidas, usa ancho 8, profundidad 3.3, longitud 40.
- Si pide rosca M20 sin longitud, usa longitud 20.
- Si pide rosca derecha, ubicarla en el último tramo.
- Si pide rosca izquierda, ubicarla en el primer tramo.
- Si falta información técnica, agregarla en missing_data.
- No inventes features fuera de: segmentos, chaveteros, filetes, roscas.
/no_think
""".strip()


def obtener_modelo_ollama():
    return os.environ.get("AI_CAD_OLLAMA_MODEL", "qwen3:8b").strip()


def limpiar_json_respuesta(texto):
    """
    Algunos modelos locales pueden devolver texto extra.
    Esta función intenta quedarse solo con el objeto JSON.
    """

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
            "Ollama respondió, pero no se encontró un objeto JSON.\n"
            f"Respuesta recibida:\n{texto}"
        )

    return json.loads(match.group(0))


def llamar_ollama(prompt_usuario):
    modelo = obtener_modelo_ollama()

    prompt = f"""
{SYSTEM_PROMPT}

Instrucción del usuario:
{prompt_usuario}

Devuelve SOLO JSON válido.
""".strip()

    payload = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": DESIGN_SPEC_SCHEMA,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9
        }
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)

    except urllib.error.URLError as e:
        raise RuntimeError(
            "No se pudo conectar con Ollama.\n\n"
            "Verifica que Ollama esté instalado y ejecutándose.\n"
            "Prueba en PowerShell:\n"
            "ollama run qwen3:8b\n\n"
            f"Detalle:\n{str(e)}"
        )

    if "error" in data:
        raise RuntimeError(
            "Ollama respondió con error:\n"
            f"{data['error']}"
        )

    respuesta = data.get("response", "").strip()

    if not respuesta:
        raise RuntimeError(
            "Ollama no devolvió contenido en el campo response.\n"
            f"Respuesta completa:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        )

    return limpiar_json_respuesta(respuesta)


def validar_design_spec(spec):
    if spec.get("intent") != "crear_eje_escalonado":
        raise ValueError(
            f"Intent no soportado: {spec.get('intent')}"
        )

    if spec.get("units") != "mm":
        raise ValueError(
            f"Unidades no soportadas: {spec.get('units')}. Usa mm."
        )

    segmentos = spec.get("segmentos", [])

    if not segmentos:
        raise ValueError(
            "La IA local no generó segmentos para el eje."
        )

    for i, seg in enumerate(segmentos):
        if seg["diametro"] <= 0:
            raise ValueError(f"Diámetro inválido en segmento {i}.")

        if seg["longitud"] <= 0:
            raise ValueError(f"Longitud inválida en segmento {i}.")

    n = len(segmentos)

    for chav in spec.get("chaveteros", []):
        idx = chav["tramo_index"]

        if idx < 0 or idx >= n:
            raise ValueError(
                f"tramo_index inválido en chavetero: {idx}"
            )

        if chav["ancho"] <= 0:
            raise ValueError("Ancho de chavetero inválido.")

        if chav["profundidad"] <= 0:
            raise ValueError("Profundidad de chavetero inválida.")

        if chav["longitud"] <= 0:
            raise ValueError("Longitud de chavetero inválida.")

    for ros in spec.get("roscas", []):
        idx = ros["tramo_index"]

        if idx < 0 or idx >= n:
            raise ValueError(
                f"tramo_index inválido en rosca: {idx}"
            )

        if ros["diametro_nominal"] <= 0:
            raise ValueError("Diámetro nominal de rosca inválido.")

        if ros["longitud"] <= 0:
            raise ValueError("Longitud de rosca inválida.")

    for fil in spec.get("filetes", []):
        if fil["radio"] <= 0:
            raise ValueError("Radio de filete inválido.")

    return True


def prompt_a_feature_plan_ollama(prompt_usuario):
    """
    Convierte lenguaje natural a feature_plan usando Ollama local.
    Luego valida y corrige la especificación antes de generar el plan CAD.
    """

    raw_spec = llamar_ollama(prompt_usuario)
    validar_design_spec(raw_spec)

    corrected_spec, validation_report = validar_y_corregir_design_spec(
        spec=raw_spec,
        prompt=prompt_usuario
    )

    if validation_report["status"] == "error":
        raise ValueError(
            "El validador encontró errores críticos:\n"
            f"{json.dumps(validation_report, indent=2, ensure_ascii=False)}"
        )

    feature_plan = crear_feature_plan_eje(
        segmentos=corrected_spec["segmentos"],
        chaveteros=corrected_spec.get("chaveteros", []),
        filetes=corrected_spec.get("filetes", []),
        roscas=corrected_spec.get("roscas", [])
    )

    feature_plan["local_ai_raw_spec"] = raw_spec
    feature_plan["local_ai_spec"] = corrected_spec
    feature_plan["plan_validation_report"] = validation_report
    feature_plan["local_ai_model"] = obtener_modelo_ollama()
    feature_plan["local_ai_mode"] = True

    return feature_plan