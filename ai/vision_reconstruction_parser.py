# ai/vision_reconstruction_parser.py
"""
Reconstrucción paramétrica aproximada desde imágenes (estructuras de
perfiles). Refactorizado para usar ai/ollama_client.py: ya no duplica
la lógica HTTP ni el saneo de JSON.
"""

from ai.ollama_client import generar_json_desde_imagen


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
    "required": ["family", "intent", "confidence", "units", "spec",
                 "missing_data", "assumptions"]
}


SYSTEM_PROMPT_FRAME_VISION = """
Eres un asistente CAD mecánico para FreeCAD especializado en reconstrucción
paramétrica aproximada desde imágenes.

Tu tarea NO es copiar exactamente la imagen: es interpretar la estructura
visible y generar una especificación paramétrica editable.

Debes analizar imágenes de: mesas industriales, bastidores, soportes,
marcos soldados, carros metálicos, estructuras con perfiles, bancos de
trabajo, plataformas simples.

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
- Responde SOLO JSON, en mm.
- Si la imagen no tiene cotas, estima dimensiones industriales razonables
  y decláralas en assumptions.
- Si ves una mesa industrial, usa por defecto: largo 1200 mm, ancho 700 mm,
  alto 850 mm, cubierta 6 mm, tubo 40x40x3 mm, salvo indicación contraria.
- Representa patas, travesaños y diagonales como members entre dos puntos 3D.
- No inventes detalles invisibles sin declararlos como assumptions.
- Si hay incertidumbre alta, baja confidence y agrega missing_data.
- Evita geometrías orgánicas: simplifica todo como perfiles, placas y uniones.
""".strip()


def imagen_a_design_request_estructura(image_path, prompt_usuario=""):
    req = generar_json_desde_imagen(
        system_prompt=SYSTEM_PROMPT_FRAME_VISION,
        image_path=image_path,
        user_prompt=prompt_usuario,
        schema=FRAME_STRUCTURE_SCHEMA
    )

    req["family"] = "frame_structure"
    req.setdefault("intent", "crear_estructura_parametrica")
    req.setdefault("confidence", 0.5)
    req.setdefault("units", "mm")
    req.setdefault("spec", {})
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])
    req["source_image"] = image_path
    return req
