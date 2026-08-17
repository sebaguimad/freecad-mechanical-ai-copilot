# core/model_feedback.py
"""Inspeccion geometrica y captura visual del resultado para feedback de IA."""

import os
import tempfile

import FreeCAD as App

try:
    import FreeCADGui as Gui
    _HAS_GUI = App.GuiUp
except Exception:
    Gui = None
    _HAS_GUI = False


def _bbox(shape):
    b = shape.BoundBox
    return {
        "xmin": float(b.XMin), "xmax": float(b.XMax),
        "ymin": float(b.YMin), "ymax": float(b.YMax),
        "zmin": float(b.ZMin), "zmax": float(b.ZMax),
        "xlen": float(b.XLength), "ylen": float(b.YLength), "zlen": float(b.ZLength),
    }


def inspect_object(obj):
    if obj is None or not hasattr(obj, "Shape"):
        return {"valid": False, "errors": ["No existe un objeto final con Shape."]}

    shape = obj.Shape
    errors = []
    warnings = []

    try:
        valid = bool(shape.isValid())
    except Exception:
        valid = False
        warnings.append("OpenCASCADE no pudo confirmar isValid().")

    try:
        solids = len(shape.Solids)
    except Exception:
        solids = 0
    try:
        faces = len(shape.Faces)
    except Exception:
        faces = 0
    try:
        edges = len(shape.Edges)
    except Exception:
        edges = 0
    try:
        volume = float(shape.Volume)
    except Exception:
        volume = 0.0

    if not valid:
        errors.append("El shape final no es valido segun OpenCASCADE.")
    if solids == 0:
        errors.append("El resultado no contiene ningun solido.")
    if volume <= 1e-9:
        errors.append("El volumen final es nulo o casi nulo.")
    if solids > 1:
        warnings.append(f"El resultado contiene {solids} solidos desconectados.")

    try:
        bbox = _bbox(shape)
    except Exception:
        bbox = None
        errors.append("No se pudo calcular el bounding box.")

    return {
        "valid": len(errors) == 0,
        "shape_valid": valid,
        "errors": errors,
        "warnings": warnings,
        "solids": solids,
        "faces": faces,
        "edges": edges,
        "volume": volume,
        "bbox": bbox,
        "object_name": getattr(obj, "Name", None),
        "object_label": getattr(obj, "Label", None),
    }


def capture_object_views(obj=None, output_dir=None, prefix="ai_feedback"):
    """Guarda vistas isometrica, frontal y lateral del documento activo."""
    if not _HAS_GUI or Gui is None or Gui.ActiveDocument is None:
        return []

    output_dir = output_dir or tempfile.mkdtemp(prefix="freecad_ai_feedback_")
    os.makedirs(output_dir, exist_ok=True)

    if obj is not None:
        for other in App.ActiveDocument.Objects:
            try:
                other.ViewObject.Visibility = (other.Name == obj.Name)
            except Exception:
                pass

    view = Gui.ActiveDocument.ActiveView
    paths = []
    configurations = [
        ("iso", view.viewAxonometric),
        ("front", view.viewFront),
        ("right", view.viewRight),
    ]
    for suffix, setter in configurations:
        try:
            setter()
            view.fitAll()
            path = os.path.join(output_dir, f"{prefix}_{suffix}.png")
            view.saveImage(path, 900, 700, "White")
            paths.append(path)
        except Exception:
            continue

    try:
        view.viewAxonometric()
        view.fitAll()
    except Exception:
        pass
    return paths


def compare_bbox(reference_bbox, actual_bbox, tolerance_ratio=0.35):
    """Compara proporciones si existe una referencia dimensional conocida."""
    if not reference_bbox or not actual_bbox:
        return {"available": False, "mismatches": []}

    mismatches = []
    for key in ("xlen", "ylen", "zlen"):
        try:
            ref = float(reference_bbox[key])
            actual = float(actual_bbox[key])
        except Exception:
            continue
        if ref <= 1e-9:
            continue
        ratio = abs(actual - ref) / ref
        if ratio > tolerance_ratio:
            mismatches.append({"axis": key, "expected": ref, "actual": actual, "relative_error": ratio})
    return {"available": True, "mismatches": mismatches}
