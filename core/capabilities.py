# core/capabilities.py
"""
Capability Registry.

Define lo que el sistema SABE hacer. Se inyecta en el prompt del
clasificador para que la IA rutee correctamente y declare límites
en vez de inventar.
"""

CAPABILITIES = {
    "supported_families": {
        "shaft": (
            "Ejes escalonados de transmisión: tramos cilíndricos, "
            "chaveteros, roscas simplificadas, filetes de hombro."
        ),
        "frame_structure": (
            "Estructuras de perfiles soldados: mesas industriales, "
            "bastidores, marcos, carros, plataformas. Tubo cuadrado + placas. "
            "Incluye BOM (lista de materiales)."
        ),
        "custom": (
            "Cualquier pieza mecánica construible con operaciones genéricas: "
            "cajas, cilindros, conos, esferas, prismas poligonales extruidos, "
            "cortes booleanos, patrones polares, filetes y chaflanes. "
            "Sirve para engranajes simplificados, bridas, poleas, soportes, "
            "ménsulas, bujes, adaptadores, placas con agujeros, etc."
        )
    },
    "supported_operations": [
        "box", "cylinder", "cone", "sphere", "polygon_prism",
        "polar_pattern", "boolean_add", "boolean_cut",
        "keyway_cut", "thread_zone", "square_tube_between_points",
        "fillet_all", "fillet_shoulders", "chamfer_all", "bom_report"
    ],
    "limitations": [
        "Las roscas se representan como zonas rebajadas, no helicoidales reales.",
        "Los engranajes se generan con dientes simplificados (no involuta exacta).",
        "No se generan superficies orgánicas ni mallas escaneadas.",
        "Unidades siempre en mm."
    ]
}


def capabilities_como_texto():
    lineas = ["FAMILIAS SOPORTADAS:"]
    for fam, desc in CAPABILITIES["supported_families"].items():
        lineas.append(f"- {fam}: {desc}")
    lineas.append("")
    lineas.append("OPERACIONES CAD DISPONIBLES:")
    lineas.append(", ".join(CAPABILITIES["supported_operations"]))
    lineas.append("")
    lineas.append("LIMITACIONES:")
    for lim in CAPABILITIES["limitations"]:
        lineas.append(f"- {lim}")
    return "\n".join(lineas)
