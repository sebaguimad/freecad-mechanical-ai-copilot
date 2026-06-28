# core/ai_parser.py
# Opción para usar OpenAI
import json
import os
import urllib.request
import urllib.error

from core.feature_plan import crear_feature_plan_eje


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


DESIGN_SPEC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "description": "Intención detectada. Para este MVP debe ser crear_eje_escalonado."
        },
        "units": {
            "type": "string",
            "description": "Unidades del diseño. Para este MVP usar mm."
        },
        "segmentos": {
            "type": "array",
            "description": "Tramos cilíndricos del eje, en orden de izquierda a derecha.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "diametro": {
                        "type": "number",
                        "description": "Diámetro del tramo en mm."
                    },
                    "longitud": {
                        "type": "number",
                        "description": "Longitud del tramo en mm."
                    }
                },
                "required": ["diametro", "longitud"]
            }
        },
        "chaveteros": {
            "type": "array",
            "description": "Chaveteros rectangulares simplificados.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tramo_index": {
                        "type": "integer",
                        "description": "Índice del tramo donde se ubica el chavetero. Parte en 0."
                    },
                    "ancho": {
                        "type": "number",
                        "description": "Ancho del chavetero en mm."
                    },
                    "profundidad": {
                        "type": "number",
                        "description": "Profundidad del chavetero en mm."
                    },
                    "longitud": {
                        "type": "number",
                        "description": "Longitud axial del chavetero en mm."
                    },
                    "offset_desde_inicio": {
                        "anyOf": [
                            {"type": "number"},
                            {"type": "null"}
                        ],
                        "description": "Distancia desde el inicio del tramo. Null si se centra automáticamente."
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
            "description": "Filetes simplificados.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "radio": {
                        "type": "number",
                        "description": "Radio del filete en mm."
                    }
                },
                "required": ["radio"]
            }
        },
        "roscas": {
            "type": "array",
            "description": "Zonas roscadas simplificadas.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tramo_index": {
                        "type": "integer",
                        "description": "Índice del tramo donde se aplica la rosca. Parte en 0."
                    },
                    "diametro_nominal": {
                        "type": "number",
                        "description": "Diámetro nominal de la rosca en mm."
                    },
                    "longitud": {
                        "type": "number",
                        "description": "Longitud axial de la zona roscada en mm."
                    },
                    "lado": {
                        "type": "string",
                        "enum": ["izquierdo", "derecho"],
                        "description": "Extremo del tramo donde se ubica la rosca."
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
            "description": "Datos importantes que el usuario no entregó.",
            "items": {
                "type": "string"
            }
        },
        "assumptions": {
            "type": "array",
            "description": "Supuestos técnicos realizados.",
            "items": {
                "type": "string"
            }
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
Eres un asistente CAD mecánico para FreeCAD.

Tu tarea es convertir instrucciones en lenguaje natural a una especificación técnica JSON
para generar ejes escalonados.

Reglas obligatorias:
- No generes código Python.
- No generes texto explicativo.
- Solo devuelve datos estructurados según el esquema.
- Las unidades deben ser milímetros.
- El intent debe ser crear_eje_escalonado.
- Los segmentos son cilindros ordenados de izquierda a derecha.
- tramo_index parte desde 0.
- Si el usuario dice "tramo 1", usar tramo_index = 0.
- Si dice "tramo 2", usar tramo_index = 1.
- Si dice "tramo central", usar el tramo del medio.
- Si el usuario pide chavetero pero no da medidas, usa ancho 8, profundidad 3.3, longitud 40.
- Si el usuario pide rosca M20 y no da longitud, usa longitud 20.
- Si el usuario pide extremos delgados y centro robusto, propone 3 tramos razonables.
- Si falta información, ponla en missing_data, pero genera una propuesta razonable si es posible.
- No inventes geometrías fuera de estas features: cilindros, chavetero, filete, rosca simplificada.
""".strip()


def _obtener_api_key():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "No se encontró OPENAI_API_KEY.\n"
            "Configúrala en PowerShell con:\n"
            'setx OPENAI_API_KEY "TU_API_KEY_AQUI"\n'
            "Luego cierra y abre FreeCAD nuevamente."
        )

    return api_key


def _obtener_modelo():
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()


def _extraer_texto_respuesta(data):
    """
    Extrae el texto desde una respuesta de la Responses API.
    Soporta varias formas de respuesta para mayor robustez.
    """

    if "output_text" in data and data["output_text"]:
        return data["output_text"]

    partes = []

    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                partes.append(content.get("text", ""))

            elif "text" in content:
                partes.append(content.get("text", ""))

    texto = "".join(partes).strip()

    if not texto:
        raise RuntimeError(
            "La API respondió, pero no se pudo extraer texto JSON.\n"
            f"Respuesta completa:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        )

    return texto


def _llamar_openai_structured(prompt_usuario):
    api_key = _obtener_api_key()
    modelo = _obtener_modelo()

    payload = {
        "model": modelo,
        "input": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt_usuario
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "shaft_design_spec",
                "strict": True,
                "schema": DESIGN_SPEC_SCHEMA
            }
        },
        "max_output_tokens": 2500
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Error HTTP llamando a OpenAI.\n"
            f"Código: {e.code}\n"
            f"Detalle:\n{error_body}"
        )

    except urllib.error.URLError as e:
        raise RuntimeError(
            "No se pudo conectar con OpenAI.\n"
            f"Detalle: {str(e)}"
        )

    texto = _extraer_texto_respuesta(data)

    try:
        return json.loads(texto)

    except json.JSONDecodeError:
        raise RuntimeError(
            "La IA respondió, pero el contenido no es JSON válido.\n"
            f"Contenido recibido:\n{texto}"
        )


def _validar_design_spec(spec):
    if spec.get("intent") != "crear_eje_escalonado":
        raise ValueError(
            f"Intent no soportado: {spec.get('intent')}"
        )

    if spec.get("units") != "mm":
        raise ValueError(
            "Por ahora solo se soportan unidades en mm."
        )

    segmentos = spec.get("segmentos", [])

    if not segmentos:
        raise ValueError(
            "La IA no generó segmentos para el eje."
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

        if chav["ancho"] <= 0 or chav["profundidad"] <= 0 or chav["longitud"] <= 0:
            raise ValueError(
                "Dimensiones inválidas en chavetero."
            )

    for ros in spec.get("roscas", []):
        idx = ros["tramo_index"]

        if idx < 0 or idx >= n:
            raise ValueError(
                f"tramo_index inválido en rosca: {idx}"
            )

        if ros["diametro_nominal"] <= 0 or ros["longitud"] <= 0:
            raise ValueError(
                "Dimensiones inválidas en rosca."
            )

    for fil in spec.get("filetes", []):
        if fil["radio"] <= 0:
            raise ValueError(
                "Radio inválido en filete."
            )

    return True


def prompt_a_feature_plan_ia(prompt_usuario):
    """
    Convierte lenguaje natural libre a feature_plan usando OpenAI.
    Luego reutiliza el generador de feature_plan existente del Workbench.
    """

    spec = _llamar_openai_structured(prompt_usuario)
    _validar_design_spec(spec)

    feature_plan = crear_feature_plan_eje(
        segmentos=spec["segmentos"],
        chaveteros=spec.get("chaveteros", []),
        filetes=spec.get("filetes", []),
        roscas=spec.get("roscas", [])
    )

    feature_plan["ai_spec"] = spec
    feature_plan["ai_model"] = _obtener_modelo()
    feature_plan["ai_mode"] = True

    return feature_plan