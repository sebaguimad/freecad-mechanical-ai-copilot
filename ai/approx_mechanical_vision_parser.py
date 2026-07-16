# ai/approx_mechanical_vision_parser.py
"""
Parser universal de visión para recreación CAD aproximada.

Convierte una imagen de referencia en un design_request compatible con el
router actual:
  - frame_structure si la imagen parece bastidor/mesa/estructura de perfiles
  - custom si parece pieza mecánica general

La intención NO es fotogrametría ni copia exacta. El objetivo es recrear una
geometría CAD paramétrica, limpia, editable y trazable con supuestos explícitos.
"""

from ai.ollama_client import generar_json_desde_imagen


APPROX_MECHANICAL_IMAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "family": {"type": "string", "enum": ["frame_structure", "custom"]},
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


SYSTEM_PROMPT_APPROX_MECHANICAL_IMAGE = """
Eres un asistente CAD mecánico para FreeCAD especializado en recreación
paramétrica aproximada desde imágenes.

TU OBJETIVO:
Recrear la pieza u objeto de forma aproximada en FreeCAD. NO busques una copia
exacta, NO hagas fotogrametría, NO generes mallas. Interpreta las formas
principales y conviértelas en operaciones CAD editables, limpias y trazables.

Debes elegir UNA de estas familias:

1) family = "frame_structure"
   Úsala si la imagen muestra una mesa industrial, bastidor, estructura soldada,
   carro metálico, banco de trabajo, marco de perfiles o plataforma.

2) family = "custom"
   Úsala si la imagen muestra una pieza mecánica general: engranaje, brida,
   polea, soporte, ménsula, placa, bloque, buje, adaptador, pieza torneada simple
   o geometría aproximable con primitivas.

FORMATO PARA family = "frame_structure":
{
  "family": "frame_structure",
  "intent": "recrear_estructura_aproximada",
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
    "plates": [],
    "connections": [],
    "bom_enabled": true
  },
  "missing_data": [],
  "assumptions": []
}

FORMATO PARA family = "custom":
{
  "family": "custom",
  "intent": "recrear_pieza_mecanica_aproximada",
  "confidence": 0.0,
  "units": "mm",
  "spec": {
    "intent": "crear_pieza_custom",
    "units": "mm",
    "nombre_pieza": "nombre_corto",
    "descripcion": "recreación aproximada desde imagen",
    "operaciones": [
      {"id": "op_001", "tipo": "cylinder", "modo": "agregar", "nombre": "cuerpo_base", "diametro": 100, "altura": 20, "posicion": [0,0,0], "eje": "Z"}
    ],
    "missing_data": [],
    "assumptions": []
  },
  "missing_data": [],
  "assumptions": []
}

OPERACIONES DISPONIBLES PARA custom:
- box: {"id","tipo":"box","modo":"agregar|cortar","nombre","largo","ancho","alto","posicion":[x,y,z]}
- cylinder: {"id","tipo":"cylinder","modo":"agregar|cortar","nombre","diametro","altura","posicion":[x,y,z],"eje":"X|Y|Z"}
- cone: {"id","tipo":"cone","modo":"agregar|cortar","nombre","diametro_inferior","diametro_superior","altura","posicion":[x,y,z],"eje":"X|Y|Z"}
- sphere: {"id","tipo":"sphere","modo":"agregar|cortar","nombre","diametro","posicion":[x,y,z]}
- polygon_prism: {"id","tipo":"polygon_prism","modo":"agregar|cortar","nombre","puntos":[[x,y],...],"altura","posicion":[x,y,z],"eje":"X|Y|Z"}
- polar_pattern: {"id","tipo":"polar_pattern","objetivo":"id_operacion_previa","cantidad":N,"centro":[x,y,z],"eje":"X|Y|Z"}
- fillet_all: {"id","tipo":"fillet_all","radio":r}
- chamfer_all: {"id","tipo":"chamfer_all","distancia":d}

REGLAS GENERALES:
- Responde SOLO JSON válido.
- Unidades siempre en mm.
- Mantén el modelo simple, editable y robusto.
- Usa cajas, cilindros, conos, prismas, cortes y patrones. Evita detalles orgánicos.
- La primera operación custom debe ser un sólido con modo "agregar".
- Los agujeros son cilindros con modo "cortar" que atraviesan la pieza.
- Si no hay cotas visibles, asume medidas industriales razonables y decláralas.
- Declara TODO supuesto en assumptions.
- Declara datos no visibles o inciertos en missing_data.
- Baja confidence si la imagen es ambigua.

HEURÍSTICAS ÚTILES:
- Engranaje aproximado: cilindro base + un diente trapezoidal polygon_prism + polar_pattern + agujero central.
- Brida: cilindro base + agujero central + un agujero de perno + polar_pattern.
- Polea: cilindro/conos aproximados + agujero central. El canal puede aproximarse con corte cónico/cilíndrico si es simple.
- Soporte en L: dos boxes fusionados + agujeros cilíndricos + nervios polygon_prism.
- Placa perforada: box + cilindros de corte + patrones si corresponde.
- Pieza torneada: combinación de cilindros/conos coaxiales y cortes.

/no_think
""".strip()


DEFAULT_USER_PROMPT = """
Recrea esta pieza mecánica de forma aproximada en FreeCAD. No busques una copia
exacta. Usa primitivas CAD editables y asume dimensiones razonables si no hay
cotas. Mantén la geometría limpia, paramétrica y trazable.
""".strip()


def imagen_a_design_request_aproximado(image_path, prompt_usuario=""):
    """
    Imagen -> design_request universal aproximado.

    El resultado se puede pasar directamente a core.domain_router.process_design_request.
    """
    prompt = prompt_usuario.strip() or DEFAULT_USER_PROMPT

    req = generar_json_desde_imagen(
        system_prompt=SYSTEM_PROMPT_APPROX_MECHANICAL_IMAGE,
        image_path=image_path,
        user_prompt=prompt,
        schema=APPROX_MECHANICAL_IMAGE_SCHEMA
    )

    family = req.get("family", "custom")
    if family not in ("frame_structure", "custom"):
        family = "custom"

    req["family"] = family
    req.setdefault("intent", "recrear_modelo_cad_aproximado")
    req.setdefault("confidence", 0.5)
    req.setdefault("units", "mm")
    req.setdefault("spec", {})
    req.setdefault("missing_data", [])
    req.setdefault("assumptions", [])
    req["source_image"] = image_path

    # Sincronizar assumptions/missing_data internos para el dominio custom.
    if family == "custom":
        req["spec"].setdefault("intent", "crear_pieza_custom")
        req["spec"].setdefault("units", "mm")
        req["spec"].setdefault("nombre_pieza", "pieza_recreada_aproximada")
        req["spec"].setdefault("descripcion", "Recreación aproximada desde imagen")
        req["spec"].setdefault("operaciones", [])
        req["spec"].setdefault("missing_data", req.get("missing_data", []))
        req["spec"].setdefault("assumptions", req.get("assumptions", []))

    return req
