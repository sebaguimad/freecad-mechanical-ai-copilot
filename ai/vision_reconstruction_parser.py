# ai/vision_reconstruction_parser.py

import base64
import json
import os
import urllib.request
import urllib.error

from ai.json_repair import limpiar_json_respuesta

try:
    from ai.model_config import OLLAMA_URL, VISION_MODEL
except Exception:
    OLLAMA_URL = os.environ.get("AI_CAD_OLLAMA_URL", "http://localhost:11434/api/generate").strip()
    VISION_MODEL = os.environ.get("AI_CAD_OLLAMA_VISION_MODEL", "qwen2.5vl:7b").strip()


FRAME_STRUCTURE_SCHEMA = {
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
    "required": ["family", "intent", "confidence", "units", "spec", "missing_data", "assumptions"]
}


SYSTEM_PROMPT_FRAME_VISION = """
Eres un asistente CAD mecánico para FreeCAD especializado en reconstrucción paramétrica aproximada desde imágenes.

Tu tarea NO es copiar exactamente la imagen.
Tu tarea es interpretar la estructura visible y generar una especificación paramétrica editable.

Debes analizar imágenes de:
- mesas industriales
- bastidores
- soportes
- marcos soldados
- carros metálicos
- estructuras con perfiles
- bancos de trabajo
- plataformas simples

Devuelve SOLO JSON válido con este formato:

{
  "family": "frame_structure",
  "intent": "crear_estructura_parametrica",
  "confidence": 0.0,
  "units": "mm",
  "spec": {
    "structure_type": "industrial_table | frame | cart | bracket | platform | unknown",
    "overall_dimensions": {"length": number, "width": number, "height": number},
    "top": {"enabled": true, "type": "plate", "length": number, "width": number, "thickness": number, "position": [number, number, number]},
    "default_profile": {"section": "square_tube", "width": number, "height": number, "thickness": number},
    "members": [
      {"id": "string", "role": "leg | cross_member | rail | diagonal | support | unknown", "profile": {"section": "square_tube", "width": number, "height": number, "thickness": number}, "start": [number, number, number], "end": [number, number, number]}
    ],
    "plates": [
      {"id": "string", "role": "base_plate | gusset | mounting_plate | top | unknown", "length": number, "width": number, "thickness": number, "position": [number, number, number]}
    ],
    "connections": [{"type": "welded | bolted | unknown", "members": ["string"], "note": "string"}],
    "bom_enabled": true
  },
  "missing_data": [],
  "assumptions": []
}

Reglas:
- Responde SOLO JSON.
- No escribas explicación fuera del JSON.
- Usa mm.
- Si la imagen no tiene cotas, estima dimensiones industriales razonables y decláralas en assumptions.
- Si ves una mesa industrial, usa por defecto: largo 1200 mm, ancho 700 mm, alto 850 mm, cubierta 6 mm, tubo 40x40x3 mm, salvo que el usuario indique otra cosa.
- Representa patas, travesaños y diagonales como members entre dos puntos 3D.
- No inventes detalles invisibles sin declararlos como assumptions.
- Si hay incertidumbre alta, baja confidence y agrega missing_data.
- Evita geometrías orgánicas. Simplifica todo como perfiles, placas y uniones.
""".strip()


def _imagen_a_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def imagen_a_design_request_estructura(image_path, prompt_usuario=""):
    image_b64 = _imagen_a_base64(image_path)

    prompt = f"""
{SYSTEM_PROMPT_FRAME_VISION}

Instrucción adicional del usuario:
{prompt_usuario}

Devuelve SOLO JSON válido.
""".strip()

    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": FRAME_STRUCTURE_SCHEMA,
        "images": [image_b64],
        "options": {"temperature": 0.1, "top_p": 0.9}
    }

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=body, method="POST", headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Error HTTP llamando a Ollama Vision. Modelo: {VISION_MODEL}. Código: {e.code}. Detalle:\n{detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"No se pudo conectar con Ollama Vision. Prueba: ollama run {VISION_MODEL}. Detalle: {str(e)}")

    if "error" in data:
        raise RuntimeError(f"Ollama Vision respondió error: {data['error']}")

    respuesta = data.get("response", "").strip()
    if not respuesta:
        raise RuntimeError("Ollama Vision no devolvió contenido en response.")

    req = limpiar_json_respuesta(respuesta)
    req["family"] = "frame_structure"
    req.setdefault("intent", "crear_estructura_parametrica")
    req.setdefault("confidence", 0.5)
    req.setdefault("units", "mm")
    req.setdefault("spec", {})
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])
    req["source_image"] = image_path
    return req
