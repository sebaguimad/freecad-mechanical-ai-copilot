# agent/ollama_freecad_agent.py
"""
Agente local Ollama -> FreeCAD RPC.

Este archivo demuestra que el conector no depende de Claude. Cualquier IA que
pueda producir JSON de llamadas a herramientas puede controlar FreeCAD mediante
core/freecad_rpc_server.py.

Flujo:
1. FreeCAD abierto: iniciar RPC server.
2. Este script llama a Ollama para convertir un prompt en tool_calls.
3. El cliente RPC ejecuta esas herramientas en FreeCAD.

Uso desde PowerShell en la carpeta del repo:

    python agent/ollama_freecad_agent.py "crea una brida circular Ø160..."

Requisito: el servidor RPC debe estar activo dentro de FreeCAD:

    from core.freecad_rpc_server import start_rpc_server
    start_rpc_server()
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Permite ejecutar este archivo directamente desde la carpeta del repo.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.ollama_client import generar_json
from core.freecad_rpc_client import FreeCADRPCClient


TOOL_CALL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": [
                            "ping", "get_objects", "clear_document",
                            "create_box", "create_cylinder", "boolean_fuse",
                            "cut_cylinder_hole", "add_fillet_all", "add_chamfer_all",
                            "run_prompt_universal", "save_document", "export_step_stl"
                        ]
                    },
                    "args": {"type": "object", "additionalProperties": True}
                },
                "required": ["tool", "args"]
            }
        }
    },
    "required": ["intent", "assumptions", "missing_data", "tool_calls"]
}


SYSTEM_PROMPT_TOOL_AGENT = """
Eres un agente CAD mecánico que controla FreeCAD mediante herramientas RPC.

Tu tarea es convertir la instrucción del usuario en una secuencia ordenada de
llamadas a herramientas. NO generes Python libre. Usa SOLO las herramientas
permitidas y argumentos JSON.

Herramientas disponibles:

1. ping: {}
2. get_objects: {}
3. clear_document: {}

4. create_box:
   {"name": str, "length": mm, "width": mm, "height": mm, "position": [x,y,z]}
   Crea una caja. position es la esquina mínima.

5. create_cylinder:
   {"name": str, "diameter": mm, "height": mm, "position": [x,y,z], "axis": "X"|"Y"|"Z"}
   position es el centro de la cara inicial. El cilindro crece en el eje.

6. boolean_fuse:
   {"name": str, "object_names": [str, ...]}

7. cut_cylinder_hole:
   {"name": str, "target": str, "diameter": mm, "height": mm, "position": [x,y,z], "axis": "X"|"Y"|"Z"}
   Para agujeros, usa altura mayor que el espesor y empieza 1 mm antes.

8. add_fillet_all:
   {"name": str, "target": str, "radius": mm}

9. add_chamfer_all:
   {"name": str, "target": str, "distance": mm}

10. run_prompt_universal:
   {"prompt": str}
   Úsalo cuando la pieza sea compleja y convenga delegar al pipeline universal
   del Workbench. Ej: engranaje, brida con patrón circular, polea, soporte.

11. save_document:
   {"path": str}

12. export_step_stl:
   {"name_base": str}

Reglas:
- Si el usuario pide algo complejo, usa run_prompt_universal en vez de muchas
  herramientas manuales.
- Si no hay cotas, asume dimensiones razonables y escríbelas en assumptions.
- Mantén modelos simples, paramétricos y editables.
- No prometas exactitud ni fabricación directa.
- Para recreación aproximada, prioriza volumen principal, agujeros, salientes,
  simetría y proporciones generales.
- Devuelve SOLO JSON.
/no_think
""".strip()


class OllamaFreeCADAgent:
    def __init__(self, rpc_url=None):
        self.rpc_url = rpc_url or os.environ.get("AI_CAD_RPC_URL", "http://127.0.0.1:8765")
        self.cad = FreeCADRPCClient(self.rpc_url)

    def plan(self, prompt_usuario):
        return generar_json(
            system_prompt=SYSTEM_PROMPT_TOOL_AGENT,
            user_prompt=prompt_usuario,
            schema=TOOL_CALL_SCHEMA,
            temperature=0.1,
        )

    def execute_call(self, call):
        tool = call["tool"]
        args = call.get("args", {}) or {}

        if tool == "ping":
            return self.cad.ping()
        if tool == "get_objects":
            return self.cad.get_objects()
        if tool == "clear_document":
            return self.cad.clear_document()
        if tool == "create_box":
            return self.cad.create_box(
                args.get("name", "box"),
                args.get("length", 50),
                args.get("width", 50),
                args.get("height", 50),
                args.get("position", [0, 0, 0]),
            )
        if tool == "create_cylinder":
            return self.cad.create_cylinder(
                args.get("name", "cylinder"),
                args.get("diameter", 20),
                args.get("height", 20),
                args.get("position", [0, 0, 0]),
                args.get("axis", "Z"),
            )
        if tool == "boolean_fuse":
            return self.cad.boolean_fuse(
                args.get("name", "fusion"),
                args.get("object_names", []),
            )
        if tool == "cut_cylinder_hole":
            return self.cad.cut_cylinder_hole(
                args.get("name", "hole_cut"),
                args.get("target", ""),
                args.get("diameter", 10),
                args.get("height", 20),
                args.get("position", [0, 0, 0]),
                args.get("axis", "Z"),
            )
        if tool == "add_fillet_all":
            return self.cad.add_fillet_all(
                args.get("name", "fillet"),
                args.get("target"),
                args.get("radius", 1),
            )
        if tool == "add_chamfer_all":
            return self.cad.add_chamfer_all(
                args.get("name", "chamfer"),
                args.get("target"),
                args.get("distance", 1),
            )
        if tool == "run_prompt_universal":
            return self.cad.run_prompt_universal(args.get("prompt", ""))
        if tool == "save_document":
            return self.cad.save_document(args.get("path", ""))
        if tool == "export_step_stl":
            return self.cad.export_step_stl(args.get("name_base", ""))

        return {"status": "error", "message": f"Tool no soportada: {tool}"}

    def run(self, prompt_usuario):
        plan = self.plan(prompt_usuario)
        results = []
        for call in plan.get("tool_calls", []):
            result = self.execute_call(call)
            results.append({"call": call, "result": result})
        return {"plan": plan, "results": results}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Uso: python agent/ollama_freecad_agent.py \"prompt CAD\"")
        return 2

    prompt = " ".join(argv)
    agent = OllamaFreeCADAgent()
    output = agent.run(prompt)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
