"""Dominio custom: vocabulario CAD universal controlado para Ollama/otras IA."""

from ai.ollama_client import generar_json

OP_TYPES = [
    "box", "cylinder", "cone", "sphere", "polygon_prism",
    "revolve", "sweep", "loft", "sketch_extrude",
    "polar_pattern", "linear_pattern", "mirror",
    "fillet_all", "chamfer_all",
]

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
                    "tipo": {"type": "string", "enum": OP_TYPES},
                    "modo": {"type": "string", "enum": ["agregar", "cortar"]},
                    "nombre": {"type": "string"},
                },
                "required": ["id", "tipo"],
            },
        },
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "units", "nombre_pieza", "operaciones", "missing_data", "assumptions"],
}

SYSTEM_PROMPT_CUSTOM = r"""
Eres un planificador CAD mecanico para FreeCAD. Convierte la peticion del
usuario en una LISTA ORDENADA de operaciones, no en codigo Python. El resultado
debe ser aproximado, limpio, editable y trazable. Responde SOLO JSON. Usa mm.

SOLIDOS BASICOS
- box: {id,tipo:"box",modo,nombre,largo,ancho,alto,posicion:[x,y,z]}
- cylinder: {id,tipo:"cylinder",modo,nombre,diametro,altura,posicion:[x,y,z],eje:"X|Y|Z"}
- cone: {id,tipo:"cone",modo,nombre,diametro_inferior,diametro_superior,altura,posicion,eje}
- sphere: {id,tipo:"sphere",modo,nombre,diametro,posicion}
- polygon_prism: {id,tipo:"polygon_prism",modo,nombre,puntos:[[x,y],...],altura,posicion,eje}

OPERACIONES AVANZADAS
- revolve: {id,tipo:"revolve",modo,nombre,perfil:[[radio,axial],...],angulo:360,eje:"X|Y|Z",posicion:[x,y,z]}
  Ideal para poleas, bujes, tapas, piezas torneadas y cuerpos de revolucion.
- sketch_extrude: {id,tipo:"sketch_extrude",modo,nombre,puntos:[[x,y],...],longitud,eje,posicion}
  Ideal para soportes, placas, nervios y perfiles 2D extruidos.
- sweep: {id,tipo:"sweep",modo,nombre,perfil:[[x,y],...],trayectoria:[[x,y,z],...]}
  Ideal para tubos curvos, manillas y conductos simples.
- loft: {id,tipo:"loft",modo,nombre,secciones:[{puntos:[[x,y],...],z:n}, ...]}
  Ideal para transiciones y carcasas simplificadas.

TRANSFORMACIONES
- polar_pattern: {id,tipo:"polar_pattern",objetivo:"op_previa",cantidad:N,centro:[x,y,z],eje:"X|Y|Z"}
- linear_pattern: {id,tipo:"linear_pattern",objetivo:"op_previa",cantidad:N,espaciado:n,direccion:[dx,dy,dz]}
- mirror: {id,tipo:"mirror",objetivo:"op_previa",plano:"XY|XZ|YZ",offset:n}
- fillet_all: {id,tipo:"fillet_all",radio:r}
- chamfer_all: {id,tipo:"chamfer_all",distancia:d}

REGLAS
1. La primera operacion que crea solido debe tener modo="agregar".
2. Agujeros = cilindros modo="cortar" atravesando completamente el material.
3. Usa revolve antes que una pila de cilindros si la pieza es claramente torneada.
4. Usa sketch_extrude para siluetas planas reconocibles.
5. Usa linear_pattern para hileras y polar_pattern para repeticiones circulares.
6. Usa mirror para simetrias evidentes.
7. Si faltan cotas, estima dimensiones industriales razonables y registra cada
   estimacion en assumptions. No inventes tolerancias.
8. Si una geometria no puede representarse razonablemente, simplificala y
   registrala en assumptions/missing_data.
9. Para un plano tecnico, prioriza las cotas visibles sobre proporciones visuales.
10. Evita detalles pequenos que no cambien la forma mecanica principal.

EJEMPLOS DE ESTRATEGIA
- Polea: revolve del perfil axial completo + agujero central.
- Brida: cylinder/revolve + agujero central + agujero de perno + polar_pattern.
- Soporte: sketch_extrude/box + agujeros + mirror si es simetrico.
- Engranaje aproximado: cylinder base + diente polygon_prism + polar_pattern.
- Manilla tubular: sweep.
/no_think
""".strip()


def generar_design_request(prompt_usuario):
    spec = generar_json(
        system_prompt=SYSTEM_PROMPT_CUSTOM,
        user_prompt=prompt_usuario,
        schema=CUSTOM_SCHEMA,
    )
    return {
        "family": "custom",
        "intent": spec.get("intent", "crear_pieza_custom"),
        "confidence": 0.75,
        "units": "mm",
        "spec": spec,
        "missing_data": spec.get("missing_data", []),
        "assumptions": spec.get("assumptions", []),
    }
