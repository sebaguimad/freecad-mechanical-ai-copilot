# core/metrics.py


def _calcular_centro_masa_robusto(shape):
    """
    Calcula centro de masa de forma robusta.
    Algunos objetos tipo Compound no tienen CenterOfMass directamente.
    """

    try:
        cm = shape.CenterOfMass
        return {
            "x": cm.x,
            "y": cm.y,
            "z": cm.z
        }
    except Exception:
        pass

    try:
        solids = list(shape.Solids)

        if solids:
            total_volume = sum(s.Volume for s in solids)

            if total_volume > 0:
                x = sum(s.CenterOfMass.x * s.Volume for s in solids) / total_volume
                y = sum(s.CenterOfMass.y * s.Volume for s in solids) / total_volume
                z = sum(s.CenterOfMass.z * s.Volume for s in solids) / total_volume

                return {
                    "x": x,
                    "y": y,
                    "z": z
                }
    except Exception:
        pass

    bbox = shape.BoundBox

    return {
        "x": (bbox.XMin + bbox.XMax) / 2.0,
        "y": (bbox.YMin + bbox.YMax) / 2.0,
        "z": (bbox.ZMin + bbox.ZMax) / 2.0
    }


def _calcular_volumen_robusto(shape):
    try:
        return shape.Volume
    except Exception:
        pass

    try:
        return sum(s.Volume for s in shape.Solids)
    except Exception:
        return 0.0


def _calcular_area_robusta(shape):
    try:
        return shape.Area
    except Exception:
        pass

    try:
        return sum(s.Area for s in shape.Solids)
    except Exception:
        return 0.0


def extraer_metricas_objeto(obj):
    shape = obj.Shape
    bbox = shape.BoundBox

    return {
        "volume_mm3": _calcular_volumen_robusto(shape),
        "area_mm2": _calcular_area_robusta(shape),
        "center_of_mass": _calcular_centro_masa_robusto(shape),
        "bounding_box": {
            "x_min": bbox.XMin,
            "x_max": bbox.XMax,
            "y_min": bbox.YMin,
            "y_max": bbox.YMax,
            "z_min": bbox.ZMin,
            "z_max": bbox.ZMax
        }
    }