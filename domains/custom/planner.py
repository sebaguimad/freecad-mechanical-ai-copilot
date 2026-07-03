# domains/custom/planner.py
"""
Planner del dominio custom: convierte la lista de operaciones validadas
en el feature tree unificado que entiende core/executor.py.

Tipos emitidos:
  solid_add / solid_cut  (con sub-spec "shape")
  polar_pattern
  fillet_all / chamfer_all
"""

TIPOS_SOLIDOS = ("box", "cylinder", "cone", "sphere", "polygon_prism")


def _shape_spec(op):
    tipo = op["tipo"]
    base = {"kind": tipo, "position": op.get("posicion", [0, 0, 0])}

    if tipo == "box":
        base.update({
            "length": op["largo"], "width": op["ancho"], "height": op["alto"]
        })
    elif tipo == "cylinder":
        base.update({
            "diameter": op["diametro"], "height": op["altura"],
            "axis": op.get("eje", "Z")
        })
    elif tipo == "cone":
        base.update({
            "diameter_bottom": op["diametro_inferior"],
            "diameter_top": op["diametro_superior"],
            "height": op["altura"], "axis": op.get("eje", "Z")
        })
    elif tipo == "sphere":
        base.update({"diameter": op["diametro"]})
    elif tipo == "polygon_prism":
        base.update({
            "points": op["puntos"], "height": op["altura"],
            "axis": op.get("eje", "Z")
        })

    return base


def build_plan(corrected_spec, design_request=None, validation_report=None):
    feature_tree = []
    id_map = {}  # id de operación → id de feature
    final_id = None

    for op in corrected_spec.get("operaciones", []):
        tipo = op["tipo"]
        oid = op["id"]
        fid = f"feat_{oid}"

        if tipo in TIPOS_SOLIDOS:
            ftype = "solid_add" if op.get("modo", "agregar") == "agregar" else "solid_cut"
            feature_tree.append({
                "id": fid,
                "type": ftype,
                "name": op.get("nombre", oid),
                "shape": _shape_spec(op)
            })
            id_map[oid] = fid
            final_id = fid

        elif tipo == "polar_pattern":
            feature_tree.append({
                "id": fid,
                "type": "polar_pattern",
                "name": f"patron_{oid}",
                "pattern_target": id_map.get(op["objetivo"]),
                "count": op["cantidad"],
                "center": op["centro"],
                "axis": op["eje"]
            })
            final_id = fid

        elif tipo == "fillet_all":
            feature_tree.append({
                "id": fid, "type": "fillet_all",
                "name": f"filete_{oid}", "radius": op["radio"]
            })
            final_id = fid

        elif tipo == "chamfer_all":
            feature_tree.append({
                "id": fid, "type": "chamfer_all",
                "name": f"chaflan_{oid}", "distance": op["distancia"]
            })
            final_id = fid

    return {
        "intent": "crear_pieza_custom",
        "family": "custom",
        "domain": "custom",
        "units": "mm",
        "nombre_pieza": corrected_spec.get("nombre_pieza", "pieza_custom"),
        "final_feature_id": final_id,
        "assumptions": corrected_spec.get("assumptions", []),
        "missing_data": corrected_spec.get("missing_data", []),
        "feature_tree": feature_tree,
        "validation_report": validation_report or {},
        "source_design_request": design_request or {}
    }
