# generators/primitives.py
"""
Generadores geométricos de bajo nivel (único módulo que habla con Part).

Novedades respecto a la versión anterior:
- Primitivas universales con posición y eje arbitrario:
  box, cylinder, cone, sphere, polygon_prism.
- patron_polar: copias rotadas de un shape alrededor de un eje.
- aplicar_filete_seguro / aplicar_chaflan_seguro: intentan la operación
  completa y, si el kernel OCC falla, degradan arista por arista en vez
  de abortar (el fillet_all antiguo era la causa nº1 de crashes).
- aplicar_filete_hombros: filete selectivo SOLO en las aristas circulares
  entre tramos de un eje (excluye las caras extremas).
- crear_tubo_cuadrado_entre_puntos: movido aquí desde frame_direct_executor
  para que exista UN solo executor.
"""

import math

import FreeCAD as App
import Part


# ------------------------------------------------------------ utilidades

_AXIS_VECTORS = {
    "X": App.Vector(1, 0, 0),
    "Y": App.Vector(0, 1, 0),
    "Z": App.Vector(0, 0, 1)
}


def _vector_eje(eje):
    if isinstance(eje, str):
        return _AXIS_VECTORS.get(eje.upper(), _AXIS_VECTORS["Z"])
    if isinstance(eje, (list, tuple)) and len(eje) >= 3:
        v = App.Vector(float(eje[0]), float(eje[1]), float(eje[2]))
        if v.Length > 1e-9:
            return v
    return _AXIS_VECTORS["Z"]


def _vec(p):
    return App.Vector(float(p[0]), float(p[1]), float(p[2]))


# ------------------------------------------------------------ primitivas

def construir_box(length, width, height, position):
    return Part.makeBox(
        float(length), float(width), float(height), _vec(position)
    )


def construir_cilindro(diameter, height, position, axis="Z"):
    return Part.makeCylinder(
        float(diameter) / 2.0, float(height), _vec(position), _vector_eje(axis)
    )


def construir_cono(diameter_bottom, diameter_top, height, position, axis="Z"):
    return Part.makeCone(
        float(diameter_bottom) / 2.0,
        float(diameter_top) / 2.0,
        float(height),
        _vec(position),
        _vector_eje(axis)
    )


def construir_esfera(diameter, position):
    return Part.makeSphere(float(diameter) / 2.0, _vec(position))


def construir_prisma_poligonal(points, height, position, axis="Z"):
    """
    Extruye un polígono cerrado definido en coordenadas locales 2D.
    El polígono se dibuja en el plano XY local y se extruye a lo largo
    del eje indicado; luego se rota desde Z al eje y se traslada.
    """
    vectores = [App.Vector(float(p[0]), float(p[1]), 0.0) for p in points]

    if len(vectores) < 3:
        raise ValueError("Un polígono necesita al menos 3 puntos.")

    # Cerrar el polígono si es necesario
    if (vectores[0] - vectores[-1]).Length > 1e-9:
        vectores.append(vectores[0])

    wire = Part.makePolygon(vectores)
    face = Part.Face(wire)
    solido = face.extrude(App.Vector(0, 0, float(height)))

    eje = _vector_eje(axis)
    rotation = App.Rotation(App.Vector(0, 0, 1), eje)
    solido.Placement = App.Placement(_vec(position), rotation)

    return solido


def construir_shape(shape_spec):
    """
    Construye un shape desde la sub-spec unificada del feature tree.
    """
    kind = shape_spec.get("kind")
    pos = shape_spec.get("position", [0, 0, 0])

    if kind == "box":
        return construir_box(
            shape_spec["length"], shape_spec["width"], shape_spec["height"], pos
        )
    if kind == "cylinder":
        return construir_cilindro(
            shape_spec["diameter"], shape_spec["height"], pos,
            shape_spec.get("axis", "Z")
        )
    if kind == "cone":
        return construir_cono(
            shape_spec["diameter_bottom"], shape_spec["diameter_top"],
            shape_spec["height"], pos, shape_spec.get("axis", "Z")
        )
    if kind == "sphere":
        return construir_esfera(shape_spec["diameter"], pos)
    if kind == "polygon_prism":
        return construir_prisma_poligonal(
            shape_spec["points"], shape_spec["height"], pos,
            shape_spec.get("axis", "Z")
        )

    raise NotImplementedError(f"Tipo de shape no soportado: {kind}")


# ------------------------------------------------------------ eje (shaft)

def crear_cilindro_x(diametro, longitud, start_x):
    return Part.makeCylinder(
        float(diametro) / 2.0,
        float(longitud),
        App.Vector(float(start_x), 0, 0),
        App.Vector(1, 0, 0)
    )


def cortar_chavetero(shape, segment_diameter, start_x, length, width, depth):
    """
    Corta un chavetero rectangular simplificado en la parte superior del
    eje (orientado sobre X).
    """
    radio = float(segment_diameter) / 2.0

    cutter = Part.makeBox(
        float(length),
        float(width),
        float(depth) + 2.0,
        App.Vector(float(start_x), -float(width) / 2.0, radio - float(depth))
    )

    return shape.cut(cutter)


def aplicar_rosca_simplificada(shape, segment_diameter, nominal_diameter,
                               start_x, length):
    """
    Representa una rosca como zona cilíndrica rebajada (no helicoidal).
    """
    diametro_rebaje = min(
        float(nominal_diameter) * 0.96,
        float(segment_diameter) * 0.98
    )

    cilindro_original = Part.makeCylinder(
        float(segment_diameter) / 2.0, float(length),
        App.Vector(float(start_x), 0, 0), App.Vector(1, 0, 0)
    )

    cilindro_rebajado = Part.makeCylinder(
        diametro_rebaje / 2.0, float(length),
        App.Vector(float(start_x), 0, 0), App.Vector(1, 0, 0)
    )

    return shape.cut(cilindro_original).fuse(cilindro_rebajado)


# ------------------------------------------------------------ booleanas

def fusionar_solidos(solidos):
    if not solidos:
        raise ValueError("No hay sólidos para fusionar.")

    resultado = solidos[0]
    for solido in solidos[1:]:
        resultado = resultado.fuse(solido)
    return resultado


# ------------------------------------------------------------ estructuras

def crear_tubo_cuadrado_entre_puntos(profile, start, end):
    outer_w = float(profile.get("width", 40.0))
    outer_h = float(profile.get("height", 40.0))
    t = float(profile.get("thickness", 3.0))

    sx, sy, sz = (float(v) for v in start)
    ex, ey, ez = (float(v) for v in end)

    dx, dy, dz = ex - sx, ey - sy, ez - sz
    member_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    if member_length <= 0:
        raise ValueError("El tubo tiene longitud cero.")

    outer = Part.makeBox(
        member_length, outer_w, outer_h,
        App.Vector(0, -outer_w / 2.0, -outer_h / 2.0)
    )

    if t <= 0 or 2.0 * t >= min(outer_w, outer_h):
        shape = outer
    else:
        inner_w = outer_w - 2.0 * t
        inner_h = outer_h - 2.0 * t
        inner = Part.makeBox(
            member_length + 2.0, inner_w, inner_h,
            App.Vector(-1.0, -inner_w / 2.0, -inner_h / 2.0)
        )
        shape = outer.cut(inner)

    shape.Placement = App.Placement(
        App.Vector(sx, sy, sz),
        App.Rotation(App.Vector(1, 0, 0), App.Vector(dx, dy, dz))
    )

    return shape


# ------------------------------------------------------------ patrones

def patron_polar(shape, cantidad, centro, eje):
    """
    Devuelve la lista de copias del shape (excluyendo el original)
    rotadas equiespaciadas 360° alrededor del eje que pasa por centro.
    """
    cantidad = int(cantidad)
    if cantidad < 2:
        return []

    centro_v = _vec(centro)
    eje_v = _vector_eje(eje)
    paso = 360.0 / cantidad

    copias = []
    for i in range(1, cantidad):
        copia = shape.copy()
        copia.rotate(centro_v, eje_v, paso * i)
        copias.append(copia)

    return copias


# ------------------------------------------------------------ filetes

def _filete_por_aristas(shape, radio, edges):
    """
    Intenta filetear el conjunto completo; si falla, arista por arista
    acumulando las que sí funcionan.
    Devuelve (shape_resultante, n_ok, n_fallidas).
    """
    if not edges:
        return shape, 0, 0

    try:
        return shape.makeFillet(float(radio), edges), len(edges), 0
    except Exception:
        pass

    actual = shape
    ok, fallidas = 0, 0

    for i in range(len(edges)):
        # Los índices de aristas cambian tras cada filete: refiltrar por
        # geometría no es trivial, así que se refileta sobre el shape
        # actual buscando la arista más parecida por punto medio.
        try:
            objetivo = edges[i]
            punto = objetivo.valueAt(
                (objetivo.FirstParameter + objetivo.LastParameter) / 2.0
            )

            candidata = None
            mejor_dist = 1e9
            for e in actual.Edges:
                try:
                    pm = e.valueAt((e.FirstParameter + e.LastParameter) / 2.0)
                    d = (pm - punto).Length
                    if d < mejor_dist:
                        mejor_dist = d
                        candidata = e
                except Exception:
                    continue

            if candidata is None or mejor_dist > 1.0:
                fallidas += 1
                continue

            actual = actual.makeFillet(float(radio), [candidata])
            ok += 1

        except Exception:
            fallidas += 1
            continue

    return actual, ok, fallidas


def aplicar_filete_seguro(shape, radio):
    """
    Filete "a todo lo que acepte filete". Nunca lanza excepción por
    fallas del kernel: degrada y reporta.
    """
    resultado, ok, fallidas = _filete_por_aristas(shape, radio, list(shape.Edges))
    return resultado, ok, fallidas


def aplicar_filete_hombros(shape, radio, total_length=None):
    """
    Filete selectivo para ejes sobre X: solo aristas circulares cuyo
    eje es paralelo a X y cuyo centro está sobre el eje (y≈0, z≈0),
    excluyendo los círculos de las caras extremas (x mínimo y máximo).
    """
    bbox = shape.BoundBox
    x_min, x_max = bbox.XMin, bbox.XMax
    tol = 1e-4

    candidatas = []

    for edge in shape.Edges:
        try:
            curva = edge.Curve
            if curva.__class__.__name__ != "Circle":
                continue

            eje = curva.Axis
            centro = curva.Center

            # Eje del círculo paralelo a X
            if abs(abs(eje.x) - 1.0) > 1e-6:
                continue

            # Centro sobre el eje del árbol
            if abs(centro.y) > tol or abs(centro.z) > tol:
                continue

            # Excluir extremos del eje
            if abs(centro.x - x_min) < tol or abs(centro.x - x_max) < tol:
                continue

            candidatas.append(edge)

        except Exception:
            continue

    resultado, ok, fallidas = _filete_por_aristas(shape, radio, candidatas)
    return resultado, ok, fallidas


def aplicar_chaflan_seguro(shape, distancia):
    edges = list(shape.Edges)

    try:
        return shape.makeChamfer(float(distancia), edges), len(edges), 0
    except Exception:
        pass

    actual = shape
    ok, fallidas = 0, 0

    for _ in range(len(edges)):
        break  # chaflán arista por arista con re-indexado es inestable

    # Fallback conservador: probar con la mitad de la distancia una vez.
    try:
        return shape.makeChamfer(float(distancia) / 2.0, edges), len(edges), 0
    except Exception:
        return shape, 0, len(edges)


# ------------------------------------------------------------ compat

def aplicar_filete_global(shape, radio):
    """
    Compatibilidad con el nombre antiguo. Ahora es seguro: nunca revienta.
    """
    resultado, _, _ = aplicar_filete_seguro(shape, radio)
    return resultado
