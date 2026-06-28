# core/exporter.py

from pathlib import Path


OUTPUT_DIR = Path.home() / "AIDibujanteOutputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def exportar_step_stl(obj, nombre_base="eje_escalonado_final"):
    """
    Exporta el objeto final de FreeCAD a STEP y STL.
    """

    if obj is None:
        raise ValueError("No hay objeto final para exportar.")

    step_path = OUTPUT_DIR / f"{nombre_base}.step"
    stl_path = OUTPUT_DIR / f"{nombre_base}.stl"

    obj.Shape.exportStep(str(step_path))
    obj.Shape.exportStl(str(stl_path))

    return {
        "step": str(step_path),
        "stl": str(stl_path)
    }


def obtener_ruta_outputs():
    return str(OUTPUT_DIR)