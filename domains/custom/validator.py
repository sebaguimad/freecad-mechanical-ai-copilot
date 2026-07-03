# domains/custom/validator.py
"""
Validador del dominio custom.

La IA propone operaciones; aquí se garantiza que sean ejecutables:
- ids únicos (se renombran duplicados)
- números positivos y acotados (0 < dim <= 10000 mm)
- la primera operación sólida debe ser modo "agregar"
- polar_pattern apunta a una operación previa existente, cantidad 2..720
- polígonos con >= 3 puntos numéricos
- filetes/chaflanes con valores razonables

Python puro, sin FreeCAD → testeable con pytest.
"""

import copy

MAX_DIM = 10000.0
TIPOS_SOLIDOS = ("box", "cylinder", "cone", "sphere", "polygon_prism")
EJES_VALIDOS = ("X", "Y", "Z")


def _num(op, key, default=None, minimo=1e-6, maximo=MAX_DIM,
         reporte=None, op_id="?"):
    try:
        value = float(op.get(key))
    except Exception:
        value = None

    if value is None or value <= 0:
        if default is None:
            return None
        if reporte is not None:
            reporte["corrections"].append({
                "type": "default_value_applied",
                "message": f"{op_id}: '{key}' inválido; se usó {default:g}."
            })
        value = float(default)

    if value < minimo:
        value = minimo
    if value > maximo:
        if reporte is not None:
            reporte["corrections"].append({
                "type": "value_clamped",
                "message": f"{op_id}: '{key}'={value:g} excede {maximo:g} mm; se limitó."
            })
        value = maximo

    return value


def _point3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return list(default)
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except Exception:
        return list(default)


def _eje(value):
    if isinstance(value, str) and value.upper() in EJES_VALIDOS:
        return value.upper()
    return "Z"


def _validar_solido(op, reporte):
    oid = op["id"]
    tipo = op["tipo"]

    modo = op.get("modo", "agregar")
    if modo not in ("agregar", "cortar"):
        modo = "agregar"
    op["modo"] = modo
    op["nombre"] = str(op.get("nombre", oid))
    op["posicion"] = _point3(op.get("posicion"))

    if tipo == "box":
        op["largo"] = _num(op, "largo", 50.0, reporte=reporte, op_id=oid)
        op["ancho"] = _num(op, "ancho", 50.0, reporte=reporte, op_id=oid)
        op["alto"] = _num(op, "alto", 50.0, reporte=reporte, op_id=oid)

    elif tipo == "cylinder":
        op["diametro"] = _num(op, "diametro", 20.0, reporte=reporte, op_id=oid)
        op["altura"] = _num(op, "altura", 20.0, reporte=reporte, op_id=oid)
        op["eje"] = _eje(op.get("eje"))

    elif tipo == "cone":
        d1 = _num(op, "diametro_inferior", 30.0, reporte=reporte, op_id=oid)
        d2 = _num(op, "diametro_superior", None, minimo=0.0,
                  reporte=reporte, op_id=oid)
        if d2 is None:
            d2 = 0.0
        op["diametro_inferior"] = d1
        op["diametro_superior"] = d2
        op["altura"] = _num(op, "altura", 20.0, reporte=reporte, op_id=oid)
        op["eje"] = _eje(op.get("eje"))

        if abs(d1 - d2) < 1e-9:
            reporte["corrections"].append({
                "type": "cone_degenerated_to_cylinder",
                "message": f"{oid}: cono con d1=d2; se tratará como cilindro."
            })
            op["tipo"] = "cylinder"
            op["diametro"] = d1

    elif tipo == "sphere":
        op["diametro"] = _num(op, "diametro", 20.0, reporte=reporte, op_id=oid)

    elif tipo == "polygon_prism":
        puntos = op.get("puntos")
        puntos_validos = []

        if isinstance(puntos, (list, tuple)):
            for p in puntos:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    try:
                        puntos_validos.append([float(p[0]), float(p[1])])
                    except Exception:
                        pass

        if len(puntos_validos) < 3:
            reporte["errors"].append(
                f"{oid}: polygon_prism necesita al menos 3 puntos válidos."
            )
            return None

        op["puntos"] = puntos_validos
        op["altura"] = _num(op, "altura", 10.0, reporte=reporte, op_id=oid)
        op["eje"] = _eje(op.get("eje"))

    return op


def _validar_polar_pattern(op, ids_solidos_previos, reporte):
    oid = op["id"]

    objetivo = op.get("objetivo")
    if objetivo not in ids_solidos_previos:
        reporte["errors"].append(
            f"{oid}: polar_pattern apunta a '{objetivo}', que no es una "
            "operación sólida previa."
        )
        return None

    try:
        cantidad = int(op.get("cantidad", 0))
    except Exception:
        cantidad = 0

    if cantidad < 2:
        reporte["errors"].append(f"{oid}: polar_pattern necesita cantidad >= 2.")
        return None

    if cantidad > 720:
        reporte["corrections"].append({
            "type": "pattern_count_clamped",
            "message": f"{oid}: cantidad {cantidad} excesiva; se limitó a 720."
        })
        cantidad = 720

    op["cantidad"] = cantidad
    op["centro"] = _point3(op.get("centro"))
    op["eje"] = _eje(op.get("eje"))
    return op


def validate(spec, prompt="", design_request=None):
    reporte = {"status": "ok", "errors": [], "warnings": [], "corrections": []}

    corrected = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    corrected.setdefault("intent", "crear_pieza_custom")
    corrected.setdefault("units", "mm")
    corrected.setdefault("nombre_pieza", "pieza_custom")
    corrected.setdefault("operaciones", [])
    corrected.setdefault("missing_data", [])
    corrected.setdefault("assumptions", [])

    if corrected["units"] != "mm":
        reporte["warnings"].append(
            f"Unidades cambiadas desde {corrected['units']} a mm."
        )
        corrected["units"] = "mm"

    ops_validas = []
    ids_usados = set()
    ids_solidos = set()
    hay_material = False

    for i, op in enumerate(corrected["operaciones"]):
        if not isinstance(op, dict):
            reporte["warnings"].append(f"Operación {i} no es un objeto; se ignoró.")
            continue

        tipo = op.get("tipo")
        oid = str(op.get("id", f"op_{i+1:03d}"))

        if oid in ids_usados:
            nuevo = f"{oid}_{i+1}"
            reporte["corrections"].append({
                "type": "duplicate_id_renamed",
                "message": f"id duplicado '{oid}' renombrado a '{nuevo}'."
            })
            oid = nuevo

        op["id"] = oid

        if tipo in TIPOS_SOLIDOS:
            op = _validar_solido(op, reporte)
            if op is None:
                continue

            # La primera operación sólida debe agregar material.
            if not hay_material and op["modo"] == "cortar":
                reporte["corrections"].append({
                    "type": "first_op_forced_add",
                    "message": (
                        f"{oid}: la primera operación sólida no puede ser un "
                        "corte; se cambió a modo agregar."
                    )
                })
                op["modo"] = "agregar"

            if op["modo"] == "agregar":
                hay_material = True

            ids_solidos.add(oid)

        elif tipo == "polar_pattern":
            op = _validar_polar_pattern(op, ids_solidos, reporte)
            if op is None:
                continue

        elif tipo == "fillet_all":
            radio = _num(op, "radio", 1.0, maximo=100.0, reporte=reporte, op_id=oid)
            op = {"id": oid, "tipo": "fillet_all", "radio": radio}

        elif tipo == "chamfer_all":
            dist = _num(op, "distancia", 1.0, maximo=100.0, reporte=reporte, op_id=oid)
            op = {"id": oid, "tipo": "chamfer_all", "distancia": dist}

        else:
            reporte["warnings"].append(
                f"Operación {i} tiene tipo no soportado '{tipo}'; se ignoró."
            )
            continue

        ids_usados.add(oid)
        ops_validas.append(op)

    corrected["operaciones"] = ops_validas

    if not any(op.get("tipo") in TIPOS_SOLIDOS for op in ops_validas):
        reporte["errors"].append(
            "No hay ninguna operación sólida válida: no se puede generar la pieza."
        )

    if reporte["errors"]:
        reporte["status"] = "error"
    elif reporte["warnings"] or reporte["corrections"]:
        reporte["status"] = "corrected"

    return corrected, reporte
