# domains/frame_structure/summary.py

import math


def _member_length(member):
    s, e = member["start"], member["end"]
    return math.sqrt((e[0]-s[0])**2 + (e[1]-s[1])**2 + (e[2]-s[2])**2)


def build_summary(corrected_spec, feature_plan, validation_report, design_request=None):
    overall = corrected_spec.get("overall_dimensions", {})
    members = corrected_spec.get("members", [])
    plates = corrected_spec.get("plates", [])
    top = corrected_spec.get("top")
    lines = []
    lines.append("Reconstrucción paramétrica: estructura / mesa industrial")
    lines.append(f"- Tipo detectado: {corrected_spec.get('structure_type', 'unknown')}")
    lines.append(f"- Dimensiones generales: {overall.get('length', '?')} x {overall.get('width', '?')} x {overall.get('height', '?')} mm")
    if top and top.get("enabled"):
        lines.append(f"- Cubierta: {top.get('length')} x {top.get('width')} x {top.get('thickness')} mm")
    lines.append(f"- Miembros/perfiles: {len(members)}")
    lines.append(f"- Placas adicionales: {len(plates)}")
    if members:
        lines.append("")
        lines.append("Lista preliminar de perfiles:")
        for m in members:
            p = m["profile"]
            length = _member_length(m)
            lines.append(f"- {m['id']} ({m.get('role', 'unknown')}): tubo {p['width']:g}x{p['height']:g}x{p['thickness']:g}, L={length:.1f} mm")
    assumptions = corrected_spec.get("assumptions", [])
    missing = corrected_spec.get("missing_data", [])
    if assumptions:
        lines.append("")
        lines.append("Supuestos:")
        for a in assumptions: lines.append(f"- {a}")
    if missing:
        lines.append("")
        lines.append("Datos faltantes:")
        for m in missing: lines.append(f"- {m}")
    lines.append("")
    lines.append("Validación:")
    lines.append(f"- Estado: {validation_report.get('status', 'unknown')}")
    for label, key in [("Correcciones", "corrections"), ("Advertencias", "warnings"), ("Errores", "errors")]:
        items = validation_report.get(key, [])
        if items:
            lines.append(f"- {label}: {len(items)}")
            for item in items:
                if isinstance(item, dict): lines.append(f"  - {item.get('type', item)}")
                else: lines.append(f"  - {item}")
    return "\n".join(lines)
