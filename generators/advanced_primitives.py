"""Primitivas CAD avanzadas para reconstruccion mecanica aproximada.

Mantiene toda la geometria avanzada en una capa controlada; la IA nunca ejecuta
Python arbitrario. Las funciones devuelven Part.Shape para que el executor pueda
registrarlas de forma trazable.
"""

import FreeCAD as App
import Part


def _vec(p):
    return App.Vector(float(p[0]), float(p[1]), float(p[2]))


def _axis_vector(axis):
    return {
        "X": App.Vector(1, 0, 0),
        "Y": App.Vector(0, 1, 0),
        "Z": App.Vector(0, 0, 1),
    }.get(str(axis).upper(), App.Vector(0, 0, 1))


def _polygon_face_xy(points):
    pts = [App.Vector(float(x), float(y), 0) for x, y in points]
    if len(pts) < 3:
        raise ValueError("Se requieren al menos 3 puntos.")
    if (pts[0] - pts[-1]).Length > 1e-9:
        pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts))


def sketch_extrude(points, length, position=(0, 0, 0), axis="Z"):
    """Extruye un croquis poligonal 2D sobre X-Y y lo orienta al eje pedido."""
    face = _polygon_face_xy(points)
    shape = face.extrude(App.Vector(0, 0, float(length)))
    rot = App.Rotation(App.Vector(0, 0, 1), _axis_vector(axis))
    shape.Placement = App.Placement(_vec(position), rot)
    return shape


def revolve_profile(profile, angle=360.0, axis="Z", position=(0, 0, 0)):
    """Revoluciona un perfil [radio, axial] alrededor del eje local Z.

    El perfil se construye en el plano XZ: (x=radio, z=axial). Debe cerrar una
    region valida. Para X/Y se rota el resultado desde Z al eje solicitado.
    """
    pts = [App.Vector(float(r), 0, float(a)) for r, a in profile]
    if len(pts) < 3:
        raise ValueError("revolve necesita al menos 3 puntos de perfil.")
    if (pts[0] - pts[-1]).Length > 1e-9:
        pts.append(pts[0])
    face = Part.Face(Part.makePolygon(pts))
    shape = face.revolve(App.Vector(0, 0, 0), App.Vector(0, 0, 1), float(angle))
    rot = App.Rotation(App.Vector(0, 0, 1), _axis_vector(axis))
    shape.Placement = App.Placement(_vec(position), rot)
    return shape


def sweep_polygon(profile_points, path_points):
    """Barre un perfil poligonal por una trayectoria 3D aproximada."""
    if len(path_points) < 2:
        raise ValueError("sweep necesita al menos 2 puntos de trayectoria.")
    face = _polygon_face_xy(profile_points)
    profile_wire = face.OuterWire
    path = Part.makePolygon([_vec(p) for p in path_points])
    return Part.Wire(path.Edges).makePipeShell([profile_wire], True, False)


def loft_polygons(sections, solid=True):
    """Crea loft entre secciones: [{points:[[x,y],...], z:...}, ...]."""
    wires = []
    if len(sections) < 2:
        raise ValueError("loft necesita al menos 2 secciones.")
    for section in sections:
        z = float(section.get("z", 0.0))
        pts = [App.Vector(float(x), float(y), z) for x, y in section["points"]]
        if len(pts) < 3:
            raise ValueError("Cada seccion del loft necesita >=3 puntos.")
        if (pts[0] - pts[-1]).Length > 1e-9:
            pts.append(pts[0])
        wires.append(Part.Wire(Part.makePolygon(pts).Edges))
    return Part.makeLoft(wires, bool(solid), False)


def linear_pattern(shape, count, spacing, direction=(1, 0, 0)):
    count = int(count)
    if count < 2:
        return []
    d = _vec(direction)
    if d.Length <= 1e-9:
        raise ValueError("Direccion de patron lineal invalida.")
    d.normalize()
    copies = []
    for i in range(1, count):
        c = shape.copy()
        c.translate(d * (float(spacing) * i))
        copies.append(c)
    return copies


def mirror_shape(shape, plane="YZ", offset=0.0):
    """Refleja un shape respecto de XY, XZ o YZ, con offset opcional."""
    plane = str(plane).upper()
    sx, sy, sz = 1.0, 1.0, 1.0
    tx = ty = tz = 0.0
    off = float(offset)
    if plane == "YZ":
        sx, tx = -1.0, 2.0 * off
    elif plane == "XZ":
        sy, ty = -1.0, 2.0 * off
    elif plane == "XY":
        sz, tz = -1.0, 2.0 * off
    else:
        raise ValueError("Plano de mirror debe ser XY, XZ o YZ.")

    m = App.Matrix()
    m.A11, m.A22, m.A33 = sx, sy, sz
    m.A14, m.A24, m.A34 = tx, ty, tz
    return shape.transformGeometry(m)
