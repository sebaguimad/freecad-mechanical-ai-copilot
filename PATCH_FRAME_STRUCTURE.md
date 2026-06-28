# PATCH_FRAME_STRUCTURE

Este parche conecta `frame_structure` con tu arquitectura modular y agrega la operación clave:

`square_tube_between_points`

---

## 1) Agregar a `core/domain_router.py`

Busca donde están los dominios:

```python
supported = {
    "shaft",
    "plate",
    "flange",
    "bushing",
    "pulley",
    "gear",
    "custom"
}
```

Cámbialo por:

```python
supported = {
    "shaft",
    "plate",
    "flange",
    "bushing",
    "pulley",
    "gear",
    "custom",
    "frame_structure"
}
```

Luego, antes del `else/custom`, agrega:

```python
elif domain == "frame_structure":
    from domains.frame_structure.validator import validate
    from domains.frame_structure.planner import build_plan
    from domains.frame_structure.summary import build_summary
```

También asegúrate de que `route_domain()` no envíe `frame_structure` a custom.

---

## 2) Agregar a `generators/primitives.py`

```python
def crear_prisma_entre_puntos(length, width, start, end):
    import math
    import Part
    import FreeCAD as App

    sx, sy, sz = float(start[0]), float(start[1]), float(start[2])
    ex, ey, ez = float(end[0]), float(end[1]), float(end[2])
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    member_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    if member_length <= 0:
        raise ValueError("El miembro tiene longitud cero.")

    shape = Part.makeBox(
        float(member_length),
        float(width),
        float(length),
        App.Vector(0, -float(width) / 2.0, -float(length) / 2.0)
    )

    direction = App.Vector(dx, dy, dz)
    rotation = App.Rotation(App.Vector(1, 0, 0), direction)
    shape.Placement = App.Placement(App.Vector(sx, sy, sz), rotation)
    return shape


def crear_tubo_cuadrado_entre_puntos(profile, start, end):
    import math
    import Part
    import FreeCAD as App

    outer_w = float(profile.get("width", 40.0))
    outer_h = float(profile.get("height", 40.0))
    t = float(profile.get("thickness", 3.0))

    sx, sy, sz = float(start[0]), float(start[1]), float(start[2])
    ex, ey, ez = float(end[0]), float(end[1]), float(end[2])
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    member_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    if member_length <= 0:
        raise ValueError("El tubo tiene longitud cero.")

    if t <= 0 or t * 2 >= min(outer_w, outer_h):
        return crear_prisma_entre_puntos(outer_h, outer_w, start, end)

    outer = Part.makeBox(
        member_length,
        outer_w,
        outer_h,
        App.Vector(0, -outer_w / 2.0, -outer_h / 2.0)
    )

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
    rotation = App.Rotation(App.Vector(1, 0, 0), direction)
    shape.Placement = App.Placement(App.Vector(sx, sy, sz), rotation)
    return shape
```

---

## 3) Agregar import a `core/executor.py`

```python
from generators.primitives import crear_tubo_cuadrado_entre_puntos
```

---

## 4) Agregar caso en `_execute_feature` de `core/executor.py`

```python
elif feature_type == "square_tube_between_points":
    return self._execute_square_tube_between_points(feature)

elif feature_type == "bom_report":
    return self._execute_bom_report(feature)
```

---

## 5) Agregar métodos a `FeatureExecutor`

```python
def _execute_square_tube_between_points(self, feature):
    shape = crear_tubo_cuadrado_entre_puntos(
        profile=feature.get("profile", {}),
        start=feature["start"],
        end=feature["end"]
    )

    return self._add_shape_object(
        feature_id=feature["id"],
        name=feature.get("name", "square_tube"),
        shape=shape
    )


def _execute_bom_report(self, feature):
    # Operación virtual: no crea geometría.
    self.objects[feature["id"]] = self.final_object
    return self.final_object
```

Si tu `FeatureExecutor` todavía no tiene `_add_shape_object`, agrega:

```python
def _add_shape_object(self, feature_id, name, shape):
    import FreeCAD as App

    obj = App.ActiveDocument.addObject("Part::Feature", name)
    obj.Shape = shape
    App.ActiveDocument.recompute()

    self.objects[feature_id] = obj
    self.final_object = obj
    return obj
```

---

## 6) Prueba desde consola FreeCAD

```python
from ai.vision_reconstruction_parser import imagen_a_design_request_estructura
from core.domain_router import process_design_request
from core.executor import FeatureExecutor

image_path = r"C:\Users\sebag\Desktop\mesa_industrial.png"

req = imagen_a_design_request_estructura(
    image_path,
    "Reconstruye esta imagen como mesa industrial. Si faltan cotas, usa largo 1200, ancho 700, alto 850, tubo 40x40x3 y cubierta de 6 mm."
)

result = process_design_request(req, prompt_usuario="mesa industrial desde imagen")
print(result["summary_text"])

ex = FeatureExecutor(result["feature_plan"])
ex.execute_all()
```
