# domains/custom/spec.py
"""
Dominio CUSTOM: el dominio universal.

En vez de pedirle a la IA código Python (frágil con modelos locales de 8B),
se le pide una LISTA ORDENADA DE OPERACIONES sobre un sólido en construcción.
Con este vocabulario se puede aproximar la gran mayoría de piezas mecánicas
de taller: engranajes simplificados, bridas, poleas, soportes, bujes,
ménsulas, placas con agujeros, adaptadores, etc.

Operaciones disponibles:
  box            caja           (largo, ancho, alto, posicion)
  cylinder       cilindro       (diametro, altura, posicion, eje)
  cone           cono/tronco    (diametro_inferior, diametro_superior, altura, posicion, eje)
  sphere         esfera         (diametro, posicion)
  polygon_prism  perfil 2D extruido (puntos [[x,y],...], altura, posicion, eje)
  polar_pattern  repite una operación previa alrededor de un eje
  fillet_all     filete seguro a todas las aristas que lo acepten
  chamfer_all    chaflán seguro

Cada operación sólida tiene "modo": "agregar" (fusiona con la pieza) o
"cortar" (resta de la pieza). La pieza se construye secuencialmente.
"""

from ai.ollama_client import generar_json


# Schema deliberadamente permisivo en los parámetros de cada operación
# (additionalProperties: true): el validador Python es la red de seguridad
# real y así el modelo local no pelea contra una gramática rígida.
CUSTOM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string"},
        "units": {"type": "string"},
        "nombre_pieza": {"type": "string"},
        "descripcion": {"type": "string"},
        "operaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "id": {"type": "string"},
                    "tipo": {
                        "type": "string",
                        "enum": ["box", "cylinder", "cone", "sphere",
                                 "polygon_prism", "polar_pattern",
                                 "fillet_all", "chamfer_all"]
                    },
                    "modo": {"type": "string", "enum": ["agregar", "cortar"]},
                    "nombre": {"type": "string"}
                },
                "required": ["id", "tipo"]
            }
        },
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["intent", "units", "nombre_pieza", "operaciones",
                 "missing_data", "assumptions"]
}


SYSTEM_PROMPT_CUSTOM = """
Eres un asistente CAD mecánico local para FreeCAD.

Convierte la instrucción del usuario en una LISTA ORDENADA de operaciones
CAD que construyen la pieza paso a paso. La pieza se construye fusionando
(modo "agregar") o restando (modo "cortar") sólidos en orden.

Responde SOLO JSON válido. Unidades: mm. intent: crear_pieza_custom.

OPERACIONES DISPONIBLES (campo "tipo") y sus parámetros:

1. box: {"id","tipo":"box","modo","nombre","largo","ancho","alto","posicion":[x,y,z]}
   La posición es la esquina de menor x,y,z.

2. cylinder: {"id","tipo":"cylinder","modo","nombre","diametro","altura","posicion":[x,y,z],"eje":"X"|"Y"|"Z"}
   La posición es el centro de la cara inicial; el cilindro crece según el eje.

3. cone: {"id","tipo":"cone","modo","nombre","diametro_inferior","diametro_superior","altura","posicion":[x,y,z],"eje":"X"|"Y"|"Z"}

4. sphere: {"id","tipo":"sphere","modo","nombre","diametro","posicion":[x,y,z]}

5. polygon_prism: {"id","tipo":"polygon_prism","modo","nombre","puntos":[[x,y],...],"altura","posicion":[x,y,z],"eje":"X"|"Y"|"Z"}
   puntos define un polígono cerrado en el plano perpendicular al eje
   (coordenadas locales, se cierra solo). Se extruye "altura" a lo largo del eje.
   Útil para dientes de engranaje, perfiles, nervios, ménsulas.

6. polar_pattern: {"id","tipo":"polar_pattern","objetivo":"id_de_operacion_previa","cantidad":N,"centro":[x,y,z],"eje":"X"|"Y"|"Z"}
   Repite la operación "objetivo" N veces en total, equiespaciadas 360°
   alrededor del eje que pasa por "centro". Hereda el modo del objetivo.

7. fillet_all: {"id","tipo":"fillet_all","radio":r}
8. chamfer_all: {"id","tipo":"chamfer_all","distancia":d}

REGLAS:
- La PRIMERA operación debe ser un sólido con modo "agregar" (es el cuerpo base).
- ids únicos y cortos: op_001, op_002, ...
- Los agujeros son cilindros con modo "cortar", con altura mayor que el
  espesor a atravesar y posición que sobresalga (ej: empezar 1 mm antes).
- ENGRANAJE RECTO simplificado (módulo m, Z dientes, ancho b):
  diámetro primitivo dp = m*Z, exterior de = m*(Z+2), raíz dr = m*(Z-2.5).
  1) cylinder base: diametro=dr, altura=b, eje Z.
  2) polygon_prism de UN diente en modo agregar: trapecio desde radio
     dr/2 - 1 hasta de/2, ancho en la raíz ≈ 1.6*m, en la punta ≈ 0.7*m,
     apuntando en +X desde el centro. Ejemplo m=2: puntos=[[dr/2-1,-1.6],[de/2,-0.7],[de/2,0.7],[dr/2-1,1.6]].
  3) polar_pattern del diente con cantidad=Z, eje Z, centro=[0,0,0].
  4) cylinder modo cortar para el agujero central.
  5) box modo cortar para el chavetero del agujero si se pide.
  Declara en assumptions que el perfil de diente es trapezoidal aproximado.
- BRIDA: cilindro base + cilindro cortar central + UN agujero de perno
  cortar + polar_pattern de ese agujero.
- Si el usuario no da medidas, usa proporciones industriales razonables y
  decláralas en assumptions.
- Lo que no puedas representar con estas operaciones, decláralo en missing_data.
/no_think
""".strip()


def generar_design_request(prompt_usuario):
    spec = generar_json(
        system_prompt=SYSTEM_PROMPT_CUSTOM,
        user_prompt=prompt_usuario,
        schema=CUSTOM_SCHEMA
    )

    return {
        "family": "custom",
        "intent": spec.get("intent", "crear_pieza_custom"),
        "confidence": 0.75,
        "units": "mm",
        "spec": spec,
        "missing_data": spec.get("missing_data", []),
        "assumptions": spec.get("assumptions", [])
    }
