# core/freecad_rpc_client.py
"""
Cliente RPC para controlar FreeCAD desde un proceso externo.

Este módulo no requiere FreeCAD. Sirve para que Ollama, Claude, ChatGPT u otro
agente pueda llamar herramientas CAD expuestas por core/freecad_rpc_server.py.

Ejemplo:

    from core.freecad_rpc_client import FreeCADRPCClient

    cad = FreeCADRPCClient()
    print(cad.ping())
    cad.create_box("base", 120, 80, 10, [0, 0, 0])
    cad.create_cylinder("boss", 40, 30, [60, 40, 10], "Z")
    cad.boolean_fuse("pieza", ["base", "boss"])
"""

from __future__ import annotations

import json
from xmlrpc.client import ServerProxy


class FreeCADRPCClient:
    def __init__(self, url="http://127.0.0.1:8765"):
        self.url = url.rstrip("/")
        self.proxy = ServerProxy(self.url, allow_none=True)

    def ping(self):
        return self.proxy.ping()

    def status(self):
        return self.proxy.status()

    def get_objects(self):
        return self.proxy.get_objects()

    def clear_document(self):
        return self.proxy.clear_document()

    def create_box(self, name, length, width, height, position=None):
        return self.proxy.create_box(
            str(name), float(length), float(width), float(height), position or [0, 0, 0]
        )

    def create_cylinder(self, name, diameter, height, position=None, axis="Z"):
        return self.proxy.create_cylinder(
            str(name), float(diameter), float(height), position or [0, 0, 0], axis
        )

    def boolean_fuse(self, name, object_names):
        return self.proxy.boolean_fuse(str(name), list(object_names))

    def cut_cylinder_hole(self, name, target, diameter, height, position=None, axis="Z"):
        return self.proxy.cut_cylinder_hole(
            str(name), str(target), float(diameter), float(height), position or [0, 0, 0], axis
        )

    def add_fillet_all(self, name, target=None, radius=1.0):
        return self.proxy.add_fillet_all(str(name), target, float(radius))

    def add_chamfer_all(self, name, target=None, distance=1.0):
        return self.proxy.add_chamfer_all(str(name), target, float(distance))

    def run_feature_plan(self, feature_plan):
        payload = feature_plan if isinstance(feature_plan, str) else json.dumps(feature_plan)
        return self.proxy.run_feature_plan(payload)

    def run_prompt_universal(self, prompt):
        return self.proxy.run_prompt_universal(str(prompt))

    def save_document(self, path=""):
        return self.proxy.save_document(str(path or ""))

    def export_step_stl(self, name_base=""):
        return self.proxy.export_step_stl(str(name_base or ""))


def get_client(url="http://127.0.0.1:8765"):
    return FreeCADRPCClient(url=url)
