"""Planner del dominio custom universal."""

SOLID_TYPES = {
    "box", "cylinder", "cone", "sphere", "polygon_prism",
    "revolve", "sweep", "loft", "sketch_extrude",
}


def _shape_spec(op):
    t = op["tipo"]
    base = {"kind": t, "position": op.get("posicion", [0, 0, 0])}
    if t == "box":
        base.update(length=op["largo"], width=op["ancho"], height=op["alto"])
    elif t == "cylinder":
        base.update(diameter=op["diametro"], height=op["altura"], axis=op.get("eje", "Z"))
    elif t == "cone":
        base.update(diameter_bottom=op["diametro_inferior"], diameter_top=op["diametro_superior"], height=op["altura"], axis=op.get("eje", "Z"))
    elif t == "sphere":
        base.update(diameter=op["diametro"])
    elif t == "polygon_prism":
        base.update(points=op["puntos"], height=op["altura"], axis=op.get("eje", "Z"))
    elif t == "sketch_extrude":
        base.update(points=op["puntos"], length=op["longitud"], axis=op.get("eje", "Z"))
    elif t == "revolve":
        base.update(profile=op["perfil"], angle=op.get("angulo", 360), axis=op.get("eje", "Z"))
    elif t == "sweep":
        base.update(profile=op["perfil"], path=op["trayectoria"])
    elif t == "loft":
        base.update(sections=op["secciones"])
    return base


def build_plan(corrected_spec, design_request=None, validation_report=None):
    tree, id_map = [], {}
    final_id = None
    for op in corrected_spec.get("operaciones", []):
        t, oid = op["tipo"], op["id"]
        fid = f"feat_{oid}"
        if t in SOLID_TYPES:
            ftype = "solid_add" if op.get("modo", "agregar") == "agregar" else "solid_cut"
            tree.append({"id": fid, "type": ftype, "name": op.get("nombre", oid), "shape": _shape_spec(op)})
            id_map[oid] = fid
            final_id = fid
        elif t == "polar_pattern":
            tree.append({"id": fid, "type": "polar_pattern", "name": f"patron_{oid}", "pattern_target": id_map.get(op["objetivo"]), "count": op["cantidad"], "center": op["centro"], "axis": op["eje"]})
            final_id = fid
        elif t == "linear_pattern":
            tree.append({"id": fid, "type": "linear_pattern", "name": f"patron_lineal_{oid}", "pattern_target": id_map.get(op["objetivo"]), "count": op["cantidad"], "spacing": op["espaciado"], "direction": op["direccion"]})
            final_id = fid
        elif t == "mirror":
            tree.append({"id": fid, "type": "mirror", "name": f"mirror_{oid}", "pattern_target": id_map.get(op["objetivo"]), "plane": op["plano"], "offset": op.get("offset", 0.0)})
            final_id = fid
        elif t == "fillet_all":
            tree.append({"id": fid, "type": "fillet_all", "name": f"filete_{oid}", "radius": op["radio"]})
            final_id = fid
        elif t == "chamfer_all":
            tree.append({"id": fid, "type": "chamfer_all", "name": f"chaflan_{oid}", "distance": op["distancia"]})
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
        "feature_tree": tree,
        "validation_report": validation_report or {},
        "source_design_request": design_request or {},
    }
