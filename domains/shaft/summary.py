# domains/shaft/summary.py


def build_summary(corrected_spec, feature_plan, validation_report, design_request=None):
    segmentos = corrected_spec.get("segmentos", [])
    lines = []

    lines.append("Diseño: eje escalonado")
    lines.append(f"- Longitud total: {feature_plan.get('total_length', 0):g} mm")
    lines.append(f"- Tramos: {len(segmentos)}")

    for i, seg in enumerate(segmentos, start=1):
        lines.append(f"  - Tramo {i}: Ø{seg['diametro']:g} x {seg['longitud']:g} mm")

    for i, chav in enumerate(corrected_spec.get("chaveteros", []), start=1):
        lines.append(
            f"- Chavetero {i}: tramo {chav['tramo_index'] + 1}, "
            f"{chav['ancho']:g} x {chav['profundidad']:g} x {chav['longitud']:g} mm"
        )

    for i, ros in enumerate(corrected_spec.get("roscas", []), start=1):
        lines.append(
            f"- Rosca {i}: M{ros['diametro_nominal']:g} x {ros['longitud']:g} mm, "
            f"lado {ros['lado']} (representación simplificada)"
        )

    for i, fil in enumerate(corrected_spec.get("filetes", []), start=1):
        lines.append(f"- Filete de hombros: R{fil['radio']:g} mm")

    assumptions = corrected_spec.get("assumptions", [])
    missing = corrected_spec.get("missing_data", [])

    if assumptions:
        lines.append("")
        lines.append("Supuestos:")
        for a in assumptions:
            lines.append(f"- {a}")

    if missing:
        lines.append("")
        lines.append("Datos faltantes:")
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
