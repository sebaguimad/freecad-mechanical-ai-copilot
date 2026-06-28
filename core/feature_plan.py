# core/feature_plan.py


def calcular_inicio_tramo(segmentos, tramo_index):
    return sum(seg["longitud"] for seg in segmentos[:tramo_index])


def crear_feature_plan_eje(segmentos, chaveteros=None, filetes=None, roscas=None):
    """
    Crea un plan CAD trazable para un eje escalonado.

    Soporta:
    - cilindros por tramo
    - fusión de tramos
    - chavetero rectangular simplificado
    - rosca simplificada
    - filete global simplificado
    """

    chaveteros = chaveteros or []
    filetes = filetes or []
    roscas = roscas or []

    feature_tree = []
    x = 0.0
    cylinder_ids = []

    # 1. Crear tramos cilíndricos
    for i, seg in enumerate(segmentos, start=1):
        feature_id = f"feat_{i:03d}"

        feature = {
            "id": feature_id,
            "type": "cylinder",
            "name": f"tramo_{i}",
            "diameter": seg["diametro"],
            "length": seg["longitud"],
            "axis": "X",
            "start_x": x
        }

        feature_tree.append(feature)
        cylinder_ids.append(feature_id)

        x += seg["longitud"]

    # 2. Fusionar tramos
    fuse_id = "feat_fuse_001"

    feature_tree.append({
        "id": fuse_id,
        "type": "boolean_fuse",
        "name": "eje_escalonado_final",
        "inputs": cylinder_ids
    })

    current_target = fuse_id

    # 3. Agregar chaveteros
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

    # 4. Agregar roscas simplificadas
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

    # 5. Agregar filetes simplificados
    for i, fil in enumerate(filetes, start=1):
        feature_id = f"feat_fillet_{i:03d}"

        feature_tree.append({
            "id": feature_id,
            "type": "fillet_all",
            "name": f"filete_{i}",
            "target": current_target,
            "radius": fil["radio"]
        })

        current_target = feature_id

    return {
        "intent": "crear_eje_escalonado",
        "units": "mm",
        "total_length": x,
        "final_feature_id": current_target,
        "assumptions": [
            "El eje se genera sobre el eje X.",
            "Las dimensiones están en milímetros.",
            "El chavetero se modela como un corte rectangular simplificado.",
            "La rosca se representa como una zona cilíndrica rebajada, no como rosca helicoidal real.",
            "Los filetes se aplican de forma global simplificada."
        ],
        "missing_data": [],
        "feature_tree": feature_tree
    }