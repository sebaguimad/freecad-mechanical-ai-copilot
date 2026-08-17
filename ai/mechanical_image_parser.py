# ai/mechanical_image_parser.py
"""
Parser de visión para recreación aproximada de piezas mecánicas.

Este módulo NO intenta fotogrametría ni copia exacta. Convierte una imagen
referencial en un design_request del dominio custom usando primitivas CAD
editables: box, cylinder, cone, sphere, polygon_prism, polar_pattern,
fillet_all y chamfer_all.
"""

from ai.ollama_client import generar_json_desde_imagen


MECHANICAL_IMAGE_SCHEMA = {
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
    "required": [
        "family", "intent", "confidence", "units", "spec",
        "missing_data", "assumptions"
    ]
}


SYSTEM_PROMPT_MECHANICAL_IMAGE = """
Eres un asistente CAD mecánico para FreeCAD especializado en RECREACIÓN
APROXIMADA desde imágenes de referencia.

Tu tarea NO es copiar exactamente la foto, NO es fotogrametría y NO es generar
una malla. Tu tarea es interpretar la pieza y crear un modelo CAD paramétrico
aproximado, limpio, editable y trazable usando primitivas simples.

Debes analizar imágenes de piezas mecánicas como: soportes, bridas, poleas,
engranajes simplificados, bujes, ejes, ménsulas, placas, adaptadores, bloques
con agujeros, piezas soldadas pequeñas y componentes industriales simples.

Devuelve SOLO JSON válido con este formato:

{
  "family": "custom",
  "intent": "crear_pieza_custom",
  "confidence": 0.0,
  "units": "mm",
  "spec": {
    "intent": "crear_pieza_custom",
    "units": "mm",
    "nombre_pieza": "nombre_corto",
    "descripcion": "recreación aproximada de la pieza observada",
    "operaciones": [
      {"id":"op_001", "tipo":"cylinder", "modo":"agregar", "nombre":"cuerpo_base", "diametro":100, "altura":20, "posicion":[0,0,0], "eje":"Z"}
    ],
    "missing_data": [],
    "assumptions": []
  },
  "missing_data": [],
  "assumptions": []
}

OPERACIONES DISPONIBLES:

1. box:
   {"id","tipo":"box","modo":"agregar|cortar","nombre","largo","ancho","alto","posicion":[x,y,z]}
   La posición es la esquina de menor x,y,z.

2. cylinder:
   {"id","tipo":"cylinder","modo":"agregar|cortar","nombre","diametro","altura","posicion":[x,y,z],"eje":"X|Y|Z"}
   La posición es el centro de la cara inicial; el cilindro crece según el eje.

3. cone:
   {"id","tipo":"cone","modo":"agregar|cortar","nombre","diametro_inferior","diametro_superior","altura","posicion":[x,y,z],"eje":"X|Y|Z"}

4. sphere:
   {"id","tipo":"sphere","modo":"agregar|cortar","nombre","diametro","posicion":[x,y,z]}

5. polygon_prism:
   {"id","tipo":"polygon_prism","modo":"agregar|cortar","nombre","puntos":[[x,y],...],"altura","posicion":[x,y,z],"eje":"X|Y|Z"}
   Útil para dientes trapezoidales, nervios triangulares, ménsulas y refuerzos.

6. polar_pattern:
   {"id","tipo":"polar_pattern","objetivo":"id_de_operacion_previa","cantidad":N,"centro":[x,y,z],"eje":"X|Y|Z"}
   Repite una operación previa alrededor del eje indicado. Hereda agregar/cortar.

7. fillet_all:
   {"id","tipo":"fillet_all","radio":r}

8. chamfer_all:
   {"id","tipo":"chamfer_all","distancia":d}

REGLAS DE RECONSTRUCCIÓN APROXIMADA:
- La primera operación debe ser un sólido con modo "agregar".
- Usa ids únicos: op_001, op_002, op_003...
- Usa mm.
- Si no hay cotas visibles, asume dimensiones razonables y escríbelas en assumptions.
- Mantén la geometría limpia: pocas operaciones, simetría, patrones, sólidos simples.
- Prioriza formas principales sobre detalles pequeños.
- Declara como missing_data lo que no pueda verse: espesor oculto, profundidad,
  agujeros traseros, tolerancias, material, radios reales, roscas reales.
- Los agujeros se hacen con cylinder en modo "cortar" y altura mayor que la pieza.
- Las ranuras/chaveteros se pueden hacer con box en modo "cortar".
- Los patrones de agujeros o dientes se hacen creando UNO y luego polar_pattern.
- Si ves un engranaje y no hay datos: usa engranaje recto simplificado con dientes
  trapezoidales aproximados. Declara que NO es involuta real.
- Si ves una polea: usa cilindro/conos/cortes para representar canal aproximado.
- Si ves una brida: usa cilindro base + agujero central + un agujero de perno + patrón polar.
- Si ves una ménsula/escuadra: usa cajas para placas, cilindros de corte para agujeros y
  polygon_prism para nervios triangulares.
- No generes código Python. No generes texto fuera del JSON.
/no_think
""".strip()


def imagen_a_design_request_pieza_mecanica(image_path, prompt_usuario=""):
    """
    Imagen + instrucción opcional → design_request del dominio custom.

    El resultado se puede pasar directamente a:
        core.domain_router.process_design_request(...)
    """
    req = generar_json_desde_imagen(
        system_prompt=SYSTEM_PROMPT_MECHANICAL_IMAGE,
        image_path=image_path,
        user_prompt=prompt_usuario,
        schema=MECHANICAL_IMAGE_SCHEMA
    )

    req["family"] = "custom"
    req.setdefault("intent", "crear_pieza_custom")
    req.setdefault("confidence", 0.5)
    req.setdefault("units", "mm")
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])

    spec = req.setdefault("spec", {})
    spec.setdefault("intent", "crear_pieza_custom")
    spec.setdefault("units", "mm")
    spec.setdefault("nombre_pieza", "pieza_mecanica_aproximada")
    spec.setdefault("descripcion", "Recreación mecánica aproximada desde imagen.")
    spec.setdefault("operaciones", [])
    spec.setdefault("missing_data", req.get("missing_data", []))
    spec.setdefault("assumptions", req.get("assumptions", []))

    req["source_image"] = image_path
    return req
