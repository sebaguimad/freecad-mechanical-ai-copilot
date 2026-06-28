# generators/primitives.py

import FreeCAD as App
import Part


def crear_cilindro_x(diametro, longitud, start_x):
    radio = diametro / 2.0

    cilindro = Part.makeCylinder(
        radio,
        longitud,
        App.Vector(start_x, 0, 0),
        App.Vector(1, 0, 0)
    )

    return cilindro


def fusionar_solidos(solidos):
    if not solidos:
        raise ValueError("No hay sólidos para fusionar.")

    resultado = solidos[0]

    for solido in solidos[1:]:
        resultado = resultado.fuse(solido)

    return resultado


def cortar_chavetero(shape, segment_diameter, start_x, length, width, depth):
    """
    Corta un chavetero rectangular simplificado en la parte superior del eje.
    El eje está orientado sobre X.
    """

    radio = segment_diameter / 2.0

    x = start_x
    y = -width / 2.0
    z = radio - depth

    cutter = Part.makeBox(
        length,
        width,
        depth + 2.0,
        App.Vector(x, y, z)
    )

    return shape.cut(cutter)


def aplicar_rosca_simplificada(shape, segment_diameter, nominal_diameter, start_x, length):
    """
    Representa una rosca como una zona cilíndrica rebajada.
    No es una rosca helicoidal real.
    """

    diametro_rebaje = min(
        nominal_diameter * 0.96,
        segment_diameter * 0.98
    )

    cilindro_original = Part.makeCylinder(
        segment_diameter / 2.0,
        length,
        App.Vector(start_x, 0, 0),
        App.Vector(1, 0, 0)
    )

    cilindro_rebajado = Part.makeCylinder(
        diametro_rebaje / 2.0,
        length,
        App.Vector(start_x, 0, 0),
        App.Vector(1, 0, 0)
    )

    return shape.cut(cilindro_original).fuse(cilindro_rebajado)


def aplicar_filete_global(shape, radio):
    """
    Aplica filete a todas las aristas del sólido.
    Es una simplificación para el MVP.
    """

    return shape.makeFillet(radio, shape.Edges)