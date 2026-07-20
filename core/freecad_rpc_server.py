# core/freecad_rpc_server.py
"""
Servidor RPC local para controlar FreeCAD desde una IA externa.

Objetivo:
- Mantener FreeCAD como motor CAD.
- Permitir que Ollama, Claude, ChatGPT u otro agente llame herramientas CAD.
- Evitar ejecutar Python arbitrario generado por IA: se exponen herramientas
  controladas y trazables.

Uso dentro de FreeCAD:

    from core.freecad_rpc_server import start_rpc_server
    start_rpc_server()

Luego, desde otro proceso Python:

    from core.freecad_rpc_client import FreeCADRPCClient
    c = FreeCADRPCClient()
    c.ping()

Notas:
- Es un puente RPC local tipo "MCP-like", no un servidor MCP oficial.
- Por seguridad escucha por defecto solo en 127.0.0.1.
- Las operaciones son experimentales; guarda el documento antes de pruebas largas.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from socketserver import ThreadingMixIn
from xmlrpc.server import SimpleXMLRPCServer

import FreeCAD as App
import Part

try:
    import FreeCADGui as Gui
    _HAS_GUI = App.GuiUp
except Exception:  # pragma: no cover - headless/freecadcmd
    Gui = None
    _HAS_GUI = False

from core.executor import FeatureExecutor
from core.exporter import exportar_step_stl
from generators.primitives import (
    aplicar_chaflan_seguro,
    aplicar_filete_seguro,
    construir_box,
    construir_cilindro,
)


_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = int(os.environ.get("AI_CAD_RPC_PORT", "8765"))

_SERVER = None
_SERVER_THREAD = None
_SERVER_LOCK = threading.RLock()
_SERVER_STARTED_AT = None


class _ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Helpers


def _ok(**data):
    data.setdefault("status", "ok")
    return data


def _err(message, **data):
    data.setdefault("status", "error")
    data["message"] = str(message)
    return data


def _safe_call(fn):
    def wrapper(*args, **kwargs):
        try:
            with _SERVER_LOCK:
                return fn(*args, **kwargs)
        except Exception as exc:
            return _err(
                exc,
                traceback=traceback.format_exc(limit=8),
                function=getattr(fn, "__name__", "unknown"),
            )
    return wrapper


def _doc():
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("AI_FreeCAD_RPC")
    return doc


def _fit_view():
    if not _HAS_GUI or Gui is None:
        return
    try:
        if Gui.ActiveDocument is not None:
            Gui.ActiveDocument.ActiveView.fitAll()
    except Exception:
        pass


def _vec3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        value = default
    return [float(value[0]), float(value[1]), float(value[2])]


def _find_object(identifier):
    doc = _doc()
    if not identifier:
        if not doc.Objects:
            raise ValueError("No hay objetos en el documento.")
        return doc.Objects[-1]

    for obj in doc.Objects:
        if obj.Name == identifier or obj.Label == identifier:
            return obj

    raise ValueError(f"No se encontró objeto: {identifier}")


def _add_shape(name, shape):
    doc = _doc()
    obj = doc.addObject("Part::Feature", str(name or "AI_RPC_Object"))
    obj.Shape = shape
    doc.recompute()
    _fit_view()
    return obj


def _bbox(obj):
    try:
        b = obj.Shape.BoundBox
        return {
            "xmin": float(b.XMin), "xmax": float(b.XMax),
            "ymin": float(b.YMin), "ymax": float(b.YMax),
            "zmin": float(b.ZMin), "zmax": float(b.ZMax),
            "xlen": float(b.XLength), "ylen": float(b.YLength),
            "zlen": float(b.ZLength),
        }
    except Exception:
        return None


def _object_info(obj):
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": getattr(obj, "TypeId", ""),
        "bbox": _bbox(obj),
    }


# ---------------------------------------------------------------------------
# Herramientas RPC expuestas


@_safe_call
def rpc_ping():
    return _ok(
        message="FreeCAD RPC server activo.",
        freecad_version=".".join(str(x) for x in App.Version()[:3]),
        document=_doc().Name,
        objects=len(_doc().Objects),
    )


@_safe_call
def rpc_status():
    return _ok(
        host=_DEFAULT_HOST,
        port=_DEFAULT_PORT,
        started_at=_SERVER_STARTED_AT,
        uptime_s=(time.time() - _SERVER_STARTED_AT) if _SERVER_STARTED_AT else None,
        document=_doc().Name,
        objects=len(_doc().Objects),
    )


@_safe_call
def rpc_get_objects():
    doc = _doc()
    return _ok(objects=[_object_info(o) for o in doc.Objects])


@_safe_call
def rpc_clear_document():
    doc = _doc()
    names = [o.Name for o in doc.Objects]
    for name in names:
        doc.removeObject(name)
    doc.recompute()
    return _ok(message="Documento limpiado.", removed=len(names))


@_safe_call
def rpc_create_box(name, length, width, height, position=None):
    shape = construir_box(
        length=float(length),
        width=float(width),
        height=float(height),
        position=_vec3(position),
    )
    obj = _add_shape(name or "box", shape)
    return _ok(message="Caja creada.", object=_object_info(obj))


@_safe_call
def rpc_create_cylinder(name, diameter, height, position=None, axis="Z"):
    shape = construir_cilindro(
        diameter=float(diameter),
        height=float(height),
        position=_vec3(position),
        axis=str(axis or "Z").upper(),
    )
    obj = _add_shape(name or "cylinder", shape)
    return _ok(message="Cilindro creado.", object=_object_info(obj))


@_safe_call
def rpc_boolean_fuse(name, object_names):
    if not isinstance(object_names, (list, tuple)) or not object_names:
        raise ValueError("object_names debe ser una lista no vacía.")

    objs = [_find_object(n) for n in object_names]
    shape = objs[0].Shape.copy()
    for obj in objs[1:]:
        shape = shape.fuse(obj.Shape)

    out = _add_shape(name or "fusion", shape)
    for obj in objs:
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass
    return _ok(message="Sólidos fusionados.", object=_object_info(out))


@_safe_call
def rpc_cut_cylinder_hole(name, target, diameter, height, position=None, axis="Z"):
    target_obj = _find_object(target)
    cutter = construir_cilindro(
        diameter=float(diameter),
        height=float(height),
        position=_vec3(position),
        axis=str(axis or "Z").upper(),
    )
    shape = target_obj.Shape.cut(cutter)
    out = _add_shape(name or f"{target_obj.Label}_hole_cut", shape)
    try:
        target_obj.ViewObject.Visibility = False
    except Exception:
        pass
    return _ok(message="Agujero cilíndrico cortado.", object=_object_info(out))


@_safe_call
def rpc_add_fillet_all(name, target=None, radius=1.0):
    target_obj = _find_object(target)
    shape, ok, failed = aplicar_filete_seguro(target_obj.Shape, float(radius))
    out = _add_shape(name or f"{target_obj.Label}_fillet", shape)
    try:
        target_obj.ViewObject.Visibility = False
    except Exception:
        pass
    return _ok(
        message=f"Filete aplicado: {ok} aristas, {failed} omitidas.",
        object=_object_info(out),
        edges_ok=ok,
        edges_failed=failed,
    )


@_safe_call
def rpc_add_chamfer_all(name, target=None, distance=1.0):
    target_obj = _find_object(target)
    shape, ok, failed = aplicar_chaflan_seguro(target_obj.Shape, float(distance))
    out = _add_shape(name or f"{target_obj.Label}_chamfer", shape)
    try:
        target_obj.ViewObject.Visibility = False
    except Exception:
        pass
    return _ok(
        message=f"Chaflán aplicado: {ok} aristas, {failed} omitidas.",
        object=_object_info(out),
        edges_ok=ok,
        edges_failed=failed,
    )


@_safe_call
def rpc_run_feature_plan(feature_plan_json):
    if isinstance(feature_plan_json, str):
        feature_plan = json.loads(feature_plan_json)
    elif isinstance(feature_plan_json, dict):
        feature_plan = feature_plan_json
    else:
        raise ValueError("feature_plan_json debe ser str JSON o dict.")

    ex = FeatureExecutor(feature_plan)
    results = ex.execute_all()
    final = ex.get_final_object()
    return _ok(
        message="Feature plan ejecutado.",
        operations=len(results),
        results=results,
        final_object=_object_info(final) if final else None,
        bom_text=getattr(ex, "bom_text", None),
    )


@_safe_call
def rpc_run_prompt_universal(prompt):
    """
    Ejecuta el pipeline universal dentro de FreeCAD.

    Útil para clientes externos simples. Para agentes avanzados se recomienda
    razonar fuera de FreeCAD y llamar herramientas individuales o enviar un
    feature_plan validado.
    """
    from core.universal_parser import prompt_a_resultado_universal

    resultado = prompt_a_resultado_universal(str(prompt))
    ex = FeatureExecutor(resultado["feature_plan"])
    execution = ex.execute_all()
    final = ex.get_final_object()
    return _ok(
        message="Prompt universal ejecutado.",
        summary=resultado.get("summary", ""),
        classification=resultado.get("classification"),
        feature_plan=resultado.get("feature_plan"),
        execution=execution,
        final_object=_object_info(final) if final else None,
    )


@_safe_call
def rpc_save_document(path=""):
    doc = _doc()
    if path:
        doc.saveAs(str(path))
    else:
        if not doc.FileName:
            default_path = os.path.join(os.path.expanduser("~"), "AI_FreeCAD_RPC.FCStd")
            doc.saveAs(default_path)
        else:
            doc.save()
    return _ok(message="Documento guardado.", path=doc.FileName)


@_safe_call
def rpc_export_step_stl(name_base=""):
    doc = _doc()
    if not doc.Objects:
        raise ValueError("No hay objetos para exportar.")
    obj = doc.Objects[-1]
    archivos = exportar_step_stl(obj, nombre_base=name_base or obj.Label)
    return _ok(message="Modelo exportado.", files=archivos, object=_object_info(obj))


# ---------------------------------------------------------------------------
# Control del servidor


def _register_functions(server):
    server.register_function(rpc_ping, "ping")
    server.register_function(rpc_status, "status")
    server.register_function(rpc_get_objects, "get_objects")
    server.register_function(rpc_clear_document, "clear_document")
    server.register_function(rpc_create_box, "create_box")
    server.register_function(rpc_create_cylinder, "create_cylinder")
    server.register_function(rpc_boolean_fuse, "boolean_fuse")
    server.register_function(rpc_cut_cylinder_hole, "cut_cylinder_hole")
    server.register_function(rpc_add_fillet_all, "add_fillet_all")
    server.register_function(rpc_add_chamfer_all, "add_chamfer_all")
    server.register_function(rpc_run_feature_plan, "run_feature_plan")
    server.register_function(rpc_run_prompt_universal, "run_prompt_universal")
    server.register_function(rpc_save_document, "save_document")
    server.register_function(rpc_export_step_stl, "export_step_stl")


def start_rpc_server(host=_DEFAULT_HOST, port=_DEFAULT_PORT):
    """Inicia el servidor RPC local en segundo plano."""
    global _SERVER, _SERVER_THREAD, _SERVER_STARTED_AT

    if _SERVER is not None:
        return rpc_status()

    server = _ThreadedXMLRPCServer(
        (str(host), int(port)),
        allow_none=True,
        logRequests=False,
    )
    _register_functions(server)

    thread = threading.Thread(
        target=server.serve_forever,
        name="FreeCAD-AI-RPC-Server",
        daemon=True,
    )
    thread.start()

    _SERVER = server
    _SERVER_THREAD = thread
    _SERVER_STARTED_AT = time.time()

    return _ok(
        message="FreeCAD RPC server iniciado.",
        host=str(host),
        port=int(port),
        url=f"http://{host}:{int(port)}",
    )


def stop_rpc_server():
    """Detiene el servidor RPC si está activo."""
    global _SERVER, _SERVER_THREAD, _SERVER_STARTED_AT

    if _SERVER is None:
        return _ok(message="RPC server no estaba activo.")

    server = _SERVER
    _SERVER = None
    _SERVER_THREAD = None
    _SERVER_STARTED_AT = None

    server.shutdown()
    server.server_close()
    return _ok(message="FreeCAD RPC server detenido.")


def get_rpc_server_status():
    if _SERVER is None:
        return _ok(active=False, message="RPC server no iniciado.")
    status = rpc_status()
    status["active"] = True
    return status
