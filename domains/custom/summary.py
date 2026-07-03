# domains/custom/summary.py

_DESCRIPCION_TIPO = {
    "box": "caja",
    "cylinder": "cilindro",
    "cone": "cono",
    "sphere": "esfera",
    "polygon_prism": "perfil extruido",
    "polar_pattern": "patrón polar",
    "fillet_all": "filete",
    "chamfer_all": "chaflán"
}


def _describir_op(op):
    tipo = op["tipo"]
    nombre = op.get("nombre", op["id"])
    modo = op.get("modo")
    accion = ""

    if modo == "agregar":
        accion = "[+] "
    elif modo == "cortar":
        accion = "[-] "

    if tipo == "box":
        detalle = f"{op['largo']:g} x {op['ancho']:g} x {op['alto']:g} mm"
    elif tipo == "cylinder":
        detalle = f"Ø{op['diametro']:g} x {op['altura']:g} mm, eje {op.get('eje', 'Z')}"
    elif tipo == "cone":
        detalle = (f"Ø{op['diametro_inferior']:g}→Ø{op['diametro_superior']:g} "
                   f"x {op['altura']:g} mm")
    elif tipo == "sphere":
        detalle = f"Ø{op['diametro']:g} mm"
    elif tipo == "polygon_prism":
        detalle = f"{len(op['puntos'])} puntos, altura {op['altura']:g} mm"
    elif tipo == "polar_pattern":
        detalle = f"{op['cantidad']}x de '{op['objetivo']}' alrededor de {op['eje']}"
    elif tipo == "fillet_all":
        detalle = f"R{op['radio']:g} mm"
    elif tipo == "chamfer_all":
        detalle = f"{op['distancia']:g} mm"
    else:
        detalle = ""

    return f"{accion}{_DESCRIPCION_TIPO.get(tipo, tipo)} '{nombre}': {detalle}"


def build_summary(corrected_spec, feature_plan, validation_report, design_request=None):
    lines = []
    lines.append(f"Diseño: pieza custom '{corrected_spec.get('nombre_pieza', '?')}'")

    desc = corrected_spec.get("descripcion")
    if desc:
        lines.append(f"- {desc}")

    ops = corrected_spec.get("operaciones", [])
    lines.append(f"- Operaciones: {len(ops)}")

    for op in ops:
        lines.append(f"  {op['id']}: {_describir_op(op)}")

    assumptions = corrected_spec.get("assumptions", [])
    missing = corrected_spec.get("missing_data", [])

    if assumptions:
        lines.append("")
        lines.append("Supuestos:")
        for a in assumptions:
            lines.append(f"- {a}")

    if missing:
        lines.append("")
        lines.append("Datos faltantes (revisar antes de fabricar):")
        for m in missing:
            lines.append(f"- {m}")

    lines.append("")
    lines.append("Validación:")
    lines.append(f"- Estado: {validation_report.get('status', 'unknown')}")

    for label, key in [("Correcciones", "corrections"),
                       ("Advertencias", "warnings"),
                       ("Errores", "errors")]:
        items = validation_report.get(key, [])
        if items:
            lines.append(f"- {label}: {len(items)}")
            for item in items:
                if isinstance(item, dict):
                    lines.append(f"  - {item.get('message', item.get('type', item))}")
                else:
                    lines.append(f"  - {item}")

    return "\n".join(lines)
