"""Validador del dominio custom universal (Python puro, sin FreeCAD)."""

import copy
import math

MAX_DIM = 10000.0
SOLID_TYPES = {
    "box", "cylinder", "cone", "sphere", "polygon_prism",
    "revolve", "sweep", "loft", "sketch_extrude",
}
PATTERN_TYPES = {"polar_pattern", "linear_pattern", "mirror"}
AXES = {"X", "Y", "Z"}
PLANES = {"XY", "XZ", "YZ"}


def _num(op, key, default=None, minimum=1e-6, maximum=MAX_DIM, report=None, oid="?"):
    try:
        v = float(op.get(key))
    except Exception:
        v = None
    if v is None or v < minimum:
        if default is None:
            return None
        v = float(default)
        if report is not None:
            report["corrections"].append({"type": "default_value_applied", "message": f"{oid}: '{key}' invalido; se uso {v:g}."})
    if v > maximum:
        v = maximum
        if report is not None:
            report["corrections"].append({"type": "value_clamped", "message": f"{oid}: '{key}' limitado a {maximum:g}."})
    return v


def _point3(v, default=(0, 0, 0)):
    try:
        if len(v) >= 3:
            return [float(v[0]), float(v[1]), float(v[2])]
    except Exception:
        pass
    return [float(x) for x in default]


def _points2(values, min_count=3):
    pts = []
    if isinstance(values, (list, tuple)):
        for p in values:
            try:
                if len(p) >= 2:
                    pts.append([float(p[0]), float(p[1])])
            except Exception:
                pass
    return pts if len(pts) >= min_count else None


def _points3(values, min_count=2):
    pts = []
    if isinstance(values, (list, tuple)):
        for p in values:
            try:
                if len(p) >= 3:
                    pts.append([float(p[0]), float(p[1]), float(p[2])])
            except Exception:
                pass
    return pts if len(pts) >= min_count else None


def _axis(v):
    v = str(v or "Z").upper()
    return v if v in AXES else "Z"


def _mode(op):
    return op.get("modo") if op.get("modo") in ("agregar", "cortar") else "agregar"


def _validate_solid(op, report):
    oid, t = op["id"], op["tipo"]
    op["modo"] = _mode(op)
    op["nombre"] = str(op.get("nombre", oid))
    op["posicion"] = _point3(op.get("posicion", [0, 0, 0]))

    if t == "box":
        op["largo"] = _num(op, "largo", 50, report=report, oid=oid)
        op["ancho"] = _num(op, "ancho", 50, report=report, oid=oid)
        op["alto"] = _num(op, "alto", 50, report=report, oid=oid)
    elif t == "cylinder":
        op["diametro"] = _num(op, "diametro", 20, report=report, oid=oid)
        op["altura"] = _num(op, "altura", 20, report=report, oid=oid)
        op["eje"] = _axis(op.get("eje"))
    elif t == "cone":
        op["diametro_inferior"] = _num(op, "diametro_inferior", 30, report=report, oid=oid)
        op["diametro_superior"] = _num(op, "diametro_superior", 1e-6, minimum=0.0, report=report, oid=oid)
        op["altura"] = _num(op, "altura", 20, report=report, oid=oid)
        op["eje"] = _axis(op.get("eje"))
    elif t == "sphere":
        op["diametro"] = _num(op, "diametro", 20, report=report, oid=oid)
    elif t == "polygon_prism":
        pts = _points2(op.get("puntos"))
        if not pts:
            report["errors"].append(f"{oid}: polygon_prism necesita >=3 puntos.")
            return None
        op["puntos"] = pts
        op["altura"] = _num(op, "altura", 10, report=report, oid=oid)
        op["eje"] = _axis(op.get("eje"))
    elif t == "sketch_extrude":
        pts = _points2(op.get("puntos"))
        if not pts:
            report["errors"].append(f"{oid}: sketch_extrude necesita >=3 puntos.")
            return None
        op["puntos"] = pts
        op["longitud"] = _num(op, "longitud", 10, report=report, oid=oid)
        op["eje"] = _axis(op.get("eje"))
    elif t == "revolve":
        pts = _points2(op.get("perfil"))
        if not pts:
            report["errors"].append(f"{oid}: revolve necesita perfil con >=3 puntos [radio,axial].")
            return None
        if any(p[0] < 0 for p in pts):
            report["errors"].append(f"{oid}: revolve no acepta radios negativos.")
            return None
        op["perfil"] = pts
        op["angulo"] = _num(op, "angulo", 360, minimum=0.1, maximum=360, report=report, oid=oid)
        op["eje"] = _axis(op.get("eje"))
    elif t == "sweep":
        prof = _points2(op.get("perfil"))
        path = _points3(op.get("trayectoria"))
        if not prof or not path:
            report["errors"].append(f"{oid}: sweep requiere perfil >=3 puntos y trayectoria >=2 puntos.")
            return None
        op["perfil"] = prof
        op["trayectoria"] = path
    elif t == "loft":
        sections = []
        for s in op.get("secciones", []) if isinstance(op.get("secciones"), list) else []:
            pts = _points2(s.get("puntos")) if isinstance(s, dict) else None
            if pts:
                sections.append({"puntos": pts, "z": float(s.get("z", 0.0))})
        if len(sections) < 2:
            report["errors"].append(f"{oid}: loft necesita >=2 secciones validas.")
            return None
        op["secciones"] = sections
    return op


def _validate_transform(op, previous_solids, report):
    oid = op["id"]
    target = op.get("objetivo")
    if target not in previous_solids:
        report["errors"].append(f"{oid}: objetivo '{target}' no es una operacion solida previa.")
        return None
    if op["tipo"] == "polar_pattern":
        try:
            count = int(op.get("cantidad", 0))
        except Exception:
            count = 0
        if count < 2:
            report["errors"].append(f"{oid}: polar_pattern necesita cantidad >=2.")
            return None
        op["cantidad"] = min(count, 720)
        op["centro"] = _point3(op.get("centro", [0, 0, 0]))
        op["eje"] = _axis(op.get("eje"))
    elif op["tipo"] == "linear_pattern":
        try:
            count = int(op.get("cantidad", 0))
        except Exception:
            count = 0
        if count < 2:
            report["errors"].append(f"{oid}: linear_pattern necesita cantidad >=2.")
            return None
        op["cantidad"] = min(count, 500)
        op["espaciado"] = _num(op, "espaciado", 20, report=report, oid=oid)
        op["direccion"] = _point3(op.get("direccion", [1, 0, 0]), (1, 0, 0))
        if math.sqrt(sum(v*v for v in op["direccion"])) <= 1e-9:
            op["direccion"] = [1.0, 0.0, 0.0]
    elif op["tipo"] == "mirror":
        plane = str(op.get("plano", "YZ")).upper()
        op["plano"] = plane if plane in PLANES else "YZ"
        try:
            op["offset"] = float(op.get("offset", 0.0))
        except Exception:
            op["offset"] = 0.0
    return op


def validate(spec, prompt="", design_request=None):
    report = {"status": "ok", "errors": [], "warnings": [], "corrections": []}
    corrected = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    corrected.setdefault("intent", "crear_pieza_custom")
    corrected.setdefault("units", "mm")
    corrected.setdefault("nombre_pieza", "pieza_custom")
    corrected.setdefault("operaciones", [])
    corrected.setdefault("missing_data", [])
    corrected.setdefault("assumptions", [])
    if corrected["units"] != "mm":
        report["warnings"].append("Unidades normalizadas a mm.")
        corrected["units"] = "mm"

    valid, used, previous_solids = [], set(), set()
    has_material = False
    for i, raw in enumerate(corrected["operaciones"]):
        if not isinstance(raw, dict):
            report["warnings"].append(f"Operacion {i} ignorada: formato invalido.")
            continue
        op = copy.deepcopy(raw)
        oid = str(op.get("id", f"op_{i+1:03d}"))
        if oid in used:
            oid = f"{oid}_{i+1}"
            report["corrections"].append({"type": "duplicate_id_renamed", "message": f"ID duplicado renombrado a {oid}."})
        op["id"] = oid
        t = op.get("tipo")

        if t in SOLID_TYPES:
            op = _validate_solid(op, report)
            if not op:
                continue
            if not has_material and op["modo"] == "cortar":
                op["modo"] = "agregar"
                report["corrections"].append({"type": "first_op_forced_add", "message": f"{oid}: primera operacion forzada a agregar."})
            if op["modo"] == "agregar":
                has_material = True
            previous_solids.add(oid)
        elif t in PATTERN_TYPES:
            op = _validate_transform(op, previous_solids, report)
            if not op:
                continue
        elif t == "fillet_all":
            op = {"id": oid, "tipo": t, "radio": _num(op, "radio", 1, maximum=100, report=report, oid=oid)}
        elif t == "chamfer_all":
            op = {"id": oid, "tipo": t, "distancia": _num(op, "distancia", 1, maximum=100, report=report, oid=oid)}
        else:
            report["warnings"].append(f"Operacion {i} no soportada: '{t}'.")
            continue

        used.add(oid)
        valid.append(op)

    corrected["operaciones"] = valid
    if not any(op.get("tipo") in SOLID_TYPES for op in valid):
        report["errors"].append("No hay ninguna operacion solida valida.")
    if report["errors"]:
        report["status"] = "error"
    elif report["warnings"] or report["corrections"]:
        report["status"] = "corrected"
    return corrected, report
