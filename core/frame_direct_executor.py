# core/frame_direct_executor.py

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part


def _get_doc():
    doc = App.ActiveDocument

    if doc is None:
        doc = App.newDocument("AI_Frame_Reconstruction")

    return doc


def _add_shape(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    doc.recompute()
    return obj


def _make_box(length, width, height, position):
    x, y, z = position

    return Part.makeBox(
        float(length),
        float(width),
        float(height),
        App.Vector(float(x), float(y), float(z))
    )


def _make_square_tube_between_points(profile, start, end):
    outer_w = float(profile.get("width", 40.0))
    outer_h = float(profile.get("height", 40.0))
    t = float(profile.get("thickness", 3.0))

    sx, sy, sz = float(start[0]), float(start[1]), float(start[2])
    ex, ey, ez = float(end[0]), float(end[1]), float(end[2])

    dx = ex - sx
    dy = ey - sy
    dz = ez - sz

    member_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    if member_length <= 0:
        raise ValueError("El tubo tiene longitud cero.")

    outer = Part.makeBox(
        member_length,
        outer_w,
        outer_h,
        App.Vector(0, -outer_w / 2.0, -outer_h / 2.0)
    )

    if t <= 0 or 2.0 * t >= min(outer_w, outer_h):
        shape = outer
    else:
        inner_w = outer_w - 2.0 * t
        inner_h = outer_h - 2.0 * t

        inner = Part.makeBox(
            member_length + 2.0,
            inner_w,
            inner_h,
            App.Vector(-1.0, -inner_w / 2.0, -inner_h / 2.0)
        )

        shape = outer.cut(inner)

    direction = App.Vector(dx, dy, dz)
    base = App.Vector(1, 0, 0)

    rotation = App.Rotation(base, direction)

    shape.Placement = App.Placement(
        App.Vector(sx, sy, sz),
        rotation
    )

    return shape


def _fuse_objects(doc, objects, name="estructura_fusionada"):
    if not objects:
        return None

    shape = objects[0].Shape.copy()

    for obj in objects[1:]:
        shape = shape.fuse(obj.Shape)

    fused = _add_shape(doc, name, shape)

    for obj in objects:
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass

    return fused


def execute_frame_plan(feature_plan):
    doc = _get_doc()

    objects_by_id = {}
    created_objects = []
    final_object = None

    for feature in feature_plan.get("feature_tree", []):
        ftype = feature.get("type")
        fid = feature.get("id")
        name = feature.get("name", fid)

        print("Ejecutando:", fid, ftype, name)

        if ftype == "box":
            shape = _make_box(
                length=feature["length"],
                width=feature["width"],
                height=feature["height"],
                position=feature.get("position", [0, 0, 0])
            )

            obj = _add_shape(doc, name, shape)
            objects_by_id[fid] = obj
            created_objects.append(obj)
            final_object = obj

        elif ftype == "square_tube_between_points":
            shape = _make_square_tube_between_points(
                profile=feature.get("profile", {}),
                start=feature["start"],
                end=feature["end"]
            )

            obj = _add_shape(doc, name, shape)
            objects_by_id[fid] = obj
            created_objects.append(obj)
            final_object = obj

        elif ftype == "boolean_fuse":
            input_ids = feature.get("inputs", [])
            input_objects = [
                objects_by_id[i]
                for i in input_ids
                if i in objects_by_id
            ]

            fused = _fuse_objects(
                doc=doc,
                objects=input_objects,
                name=name
            )

            if fused is not None:
                objects_by_id[fid] = fused
                final_object = fused

        elif ftype == "bom_report":
            objects_by_id[fid] = final_object

        else:
            print(f"Operación no soportada: {ftype}")

    doc.recompute()

    try:
        Gui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass

    print("Ejecución frame_structure finalizada.")
    print("Objetos creados:", len(created_objects))
    print([obj.Label for obj in created_objects])

    return {
        "objects_by_id": objects_by_id,
        "created_objects": created_objects,
        "final_object": final_object
    }