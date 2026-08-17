"""Parser universal de vision para recreacion CAD mecanica aproximada."""

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
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["family", "intent", "confidence", "units", "spec", "missing_data", "assumptions"],
}

SYSTEM_PROMPT_APPROX_MECHANICAL_IMAGE = r"""
Eres un ingeniero CAD que recrea objetos mecanicos de forma APROXIMADA en
FreeCAD desde fotografias, bocetos y planos. No copies exactamente la imagen,
no hagas fotogrametria ni mallas. Extrae la estructura geometrica principal y
conviertela en un modelo CAD editable y trazable.

Primero decide:
- frame_structure: mesa, bastidor, carro, marco soldado, plataforma/perfiles.
- custom: pieza mecanica general.

Para frame_structure devuelve spec con overall_dimensions, top,
default_profile, members, plates, connections y bom_enabled.

Para custom devuelve:
{
 "family":"custom",
 "intent":"recrear_pieza_mecanica_aproximada",
 "confidence":0.0,
 "units":"mm",
 "spec":{
   "intent":"crear_pieza_custom",
   "units":"mm",
   "nombre_pieza":"nombre_corto",
   "descripcion":"recreacion aproximada desde imagen/plano",
   "operaciones":[],
   "missing_data":[],
   "assumptions":[]
 },
 "missing_data":[],
 "assumptions":[]
}

VOCABULARIO CUSTOM
Basico:
- box(largo,ancho,alto,posicion)
- cylinder(diametro,altura,posicion,eje)
- cone(diametro_inferior,diametro_superior,altura,posicion,eje)
- sphere(diametro,posicion)
- polygon_prism(puntos,altura,posicion,eje)
Avanzado:
- revolve: perfil=[[radio,axial],...], angulo=360, eje, posicion. Usalo para
  poleas, bujes, tapas y piezas torneadas.
- sketch_extrude: puntos=[[x,y],...], longitud, eje, posicion. Usalo para
  siluetas planas, soportes, placas y nervios.
- sweep: perfil=[[x,y],...], trayectoria=[[x,y,z],...]. Usalo para tubos
  curvos, manillas y conductos simples.
- loft: secciones=[{"puntos":[[x,y],...],"z":n}, ...]. Usalo para transiciones
  y carcasas simplificadas.
Transformaciones:
- polar_pattern(objetivo,cantidad,centro,eje)
- linear_pattern(objetivo,cantidad,espaciado,direccion)
- mirror(objetivo,plano="XY|XZ|YZ",offset)
Acabados:
- fillet_all(radio)
- chamfer_all(distancia)

Cada solido lleva modo="agregar" o "cortar". La primera operacion solida debe
agregar material. Los agujeros son cilindros en modo cortar que atraviesan la
pieza.

REGLAS DE INTERPRETACION
1. Si es un PLANO, las cotas visibles tienen prioridad absoluta sobre la escala
   aparente. No inventes tolerancias, roscas o detalles no visibles.
2. Si es una FOTO sin cotas, estima dimensiones industriales razonables y
   declara TODA estimacion en assumptions.
3. Reconoce ejes, simetrias, repeticiones, agujeros, nervios, superficies de
   revolucion y perfiles extruidos antes de elegir primitivas.
4. Prefiere pocas operaciones semanticamente correctas: revolve para una polea,
   pattern para repeticion, mirror para simetria, en vez de docenas de cajas.
5. Simplifica superficies organicas o detalles pequenos y declaralo.
6. Si una zona no es visible, agrega missing_data; no la inventes como certeza.
7. Unidades mm. Responde SOLO JSON valido. /no_think
""".strip()

DEFAULT_USER_PROMPT = (
    "Recrea esta pieza mecanica de forma aproximada en FreeCAD. No busques una "
    "copia exacta. Usa primitivas y operaciones CAD editables; si hay cotas, "
    "priorizalas. Si faltan, asume dimensiones razonables y declara los supuestos. "
    "Mantiene la geometria limpia, parametrica y trazable."
)


def imagen_a_design_request_aproximado(image_path, prompt_usuario=""):
    prompt = prompt_usuario.strip() or DEFAULT_USER_PROMPT
    req = generar_json_desde_imagen(
        system_prompt=SYSTEM_PROMPT_APPROX_MECHANICAL_IMAGE,
        image_path=image_path,
        user_prompt=prompt,
        schema=APPROX_MECHANICAL_IMAGE_SCHEMA,
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
    if family == "custom":
        req["spec"].setdefault("intent", "crear_pieza_custom")
        req["spec"].setdefault("units", "mm")
        req["spec"].setdefault("nombre_pieza", "pieza_recreada_aproximada")
        req["spec"].setdefault("descripcion", "Recreacion aproximada desde imagen/plano")
        req["spec"].setdefault("operaciones", [])
        req["spec"].setdefault("missing_data", req.get("missing_data", []))
        req["spec"].setdefault("assumptions", req.get("assumptions", []))
    return req
