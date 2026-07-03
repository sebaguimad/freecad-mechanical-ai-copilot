# domains/shaft/planner.py
"""
Planner del dominio shaft: spec corregida -> feature tree ejecutable.

Cambio respecto a la versión anterior: el filete ya no es "fillet_all"
(filetear TODAS las aristas rompía el kernel OCC con chaveteros y
roscas presentes) sino "fillet_shoulders": solo las aristas circulares
de los hombros entre tramos, con fallback seguro en el executor.
"""


def calcular_inicio_tramo(segmentos, tramo_index):
    return sum(seg["longitud"] for seg in segmentos[:tramo_index])


def build_plan(corrected_spec, design_request=None, validation_report=None):
    segmentos = corrected_spec["segmentos"]
    chaveteros = corrected_spec.get("chaveteros", [])
    filetes = corrected_spec.get("filetes", [])
    roscas = corrected_spec.get("roscas", [])

    feature_tree = []
    x = 0.0
    cylinder_ids = []

    # 1. Tramos cilíndricos
    for i, seg in enumerate(segmentos, start=1):
        feature_id = f"feat_{i:03d}"
        feature_tree.append({
            "id": feature_id,
            "type": "cylinder",
            "name": f"tramo_{i}",
            "diameter": seg["diametro"],
            "length": seg["longitud"],
            "axis": "X",
            "start_x": x
        })
        cylinder_ids.append(feature_id)
        x += seg["longitud"]

    # 2. Fusión
    fuse_id = "feat_fuse_001"
    feature_tree.append({
        "id": fuse_id,
        "type": "boolean_fuse",
        "name": "eje_escalonado",
        "inputs": cylinder_ids
    })
    current_target = fuse_id

    # 3. Roscas ANTES que chaveteros.
    #    La rosca hace cut+fuse de su zona: si se ejecutara después de un
    #    chavetero solapado lo rellenaría. El validador ya evita solapes,
    #    pero este orden es la segunda línea de defensa.
    for i, ros in enumerate(roscas, start=1):
        idx = ros["tramo_index"]
        seg = segmentos[idx]
        x_inicio_tramo = calcular_inicio_tramo(segmentos, idx)

        if ros["lado"] == "derecho":
            x_rosca = x_inicio_tramo + seg["longitud"] - ros["longitud"]
        else:
            x_rosca = x_inicio_tramo

        feature_id = f"feat_thread_{i:03d}"
        feature_tree.append({
            "id": feature_id,
            "type": "thread_zone",
            "name": f"rosca_simplificada_{i}",
            "target": current_target,
            "segment_index": idx,
            "segment_diameter": seg["diametro"],
            "nominal_diameter": ros["diametro_nominal"],
            "length": ros["longitud"],
            "start_x": x_rosca,
            "side": ros["lado"]
        })
        current_target = feature_id

    # 4. Chaveteros
    for i, chav in enumerate(chaveteros, start=1):
        idx = chav["tramo_index"]
        seg = segmentos[idx]
        x_inicio_tramo = calcular_inicio_tramo(segmentos, idx)

        offset = chav.get("offset_desde_inicio")
        if offset is None:
            offset = (seg["longitud"] - chav["longitud"]) / 2.0

        feature_id = f"feat_keyway_{i:03d}"
        feature_tree.append({
            "id": feature_id,
            "type": "keyway_cut",
            "name": f"chavetero_{i}",
            "target": current_target,
            "segment_index": idx,
            "segment_diameter": seg["diametro"],
            "segment_start_x": x_inicio_tramo,
            "segment_length": seg["longitud"],
            "width": chav["ancho"],
            "depth": chav["profundidad"],
            "length": chav["longitud"],
            "offset_x": offset
        })
        current_target = feature_id

    # 5. Filete de hombros (uno, seguro)
    for i, fil in enumerate(filetes, start=1):
        feature_id = f"feat_fillet_{i:03d}"
        feature_tree.append({
            "id": feature_id,
            "type": "fillet_shoulders",
            "name": f"filete_hombros_{i}",
            "target": current_target,
            "radius": fil["radio"],
            "total_length": x
        })
        current_target = feature_id

    return {
        "intent": "crear_eje_escalonado",
        "family": "shaft",
        "domain": "shaft",
        "units": "mm",
        "total_length": x,
        "final_feature_id": current_target,
        "assumptions": [
            "El eje se genera sobre el eje X.",
            "Las dimensiones están en milímetros.",
            "El chavetero se modela como un corte rectangular simplificado.",
            "La rosca se representa como zona cilíndrica rebajada, no helicoidal real.",
            "El filete se aplica solo a los hombros entre tramos, con fallback seguro."
        ],
        "missing_data": corrected_spec.get("missing_data", []),
        "feature_tree": feature_tree,
        "validation_report": validation_report or {},
        "source_design_request": design_request or {}
    }
