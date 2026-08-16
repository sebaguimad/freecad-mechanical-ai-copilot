"""Extension del FeatureExecutor con operaciones CAD avanzadas."""

from core.executor import FeatureExecutor
from generators.primitives import construir_shape, fusionar_solidos
from generators.advanced_primitives import (
    sketch_extrude,
    revolve_profile,
    sweep_polygon,
    loft_polygons,
    linear_pattern,
    mirror_shape,
)


class AdvancedFeatureExecutor(FeatureExecutor):
    """FeatureExecutor compatible con planes antiguos y geometria avanzada."""

    def _build_tool_shape(self, shape_spec):
        kind = shape_spec.get("kind")
        if kind == "sketch_extrude":
            return sketch_extrude(
                shape_spec["points"],
                shape_spec["length"],
                position=shape_spec.get("position", [0, 0, 0]),
                axis=shape_spec.get("axis", "Z"),
            )
        if kind == "revolve":
            return revolve_profile(
                shape_spec["profile"],
                angle=shape_spec.get("angle", 360),
                axis=shape_spec.get("axis", "Z"),
                position=shape_spec.get("position", [0, 0, 0]),
            )
        if kind == "sweep":
            return sweep_polygon(shape_spec["profile"], shape_spec["path"])
        if kind == "loft":
            return loft_polygons(shape_spec["sections"], solid=True)
        return construir_shape(shape_spec)

    def _execute_solid_add(self, feature):
        tool = self._build_tool_shape(feature["shape"])
        self.tool_shapes[feature["id"]] = tool
        self.tool_modes[feature["id"]] = "agregar"
        if self.current_id is None:
            shape, hide = tool, []
        else:
            shape, hide = self._current_shape().fuse(tool), [self.current_id]
        return self._commit_shape(
            feature, shape, hide_ids=hide,
            mensaje=f"Material agregado: {feature.get('name')}"
        )

    def _execute_solid_cut(self, feature):
        tool = self._build_tool_shape(feature["shape"])
        self.tool_shapes[feature["id"]] = tool
        self.tool_modes[feature["id"]] = "cortar"
        shape = self._current_shape().cut(tool)
        return self._commit_shape(
            feature, shape, hide_ids=[self.current_id],
            mensaje=f"Material cortado: {feature.get('name')}"
        )

    def _execute_linear_pattern(self, feature):
        target_fid = feature.get("pattern_target")
        if target_fid not in self.tool_shapes:
            raise ValueError(f"linear_pattern: herramienta inexistente '{target_fid}'.")
        base_tool = self.tool_shapes[target_fid]
        mode = self.tool_modes.get(target_fid, "agregar")
        copies = linear_pattern(
            base_tool,
            count=feature["count"],
            spacing=feature["spacing"],
            direction=feature.get("direction", [1, 0, 0]),
        )
        if not copies:
            raise ValueError("linear_pattern genero 0 copias.")
        group = fusionar_solidos(copies)
        shape = self._current_shape().fuse(group) if mode == "agregar" else self._current_shape().cut(group)
        return self._commit_shape(
            feature, shape, hide_ids=[self.current_id],
            mensaje=f"Patron lineal: {feature['count']} instancias ({mode})."
        )

    def _execute_mirror(self, feature):
        target_fid = feature.get("pattern_target")
        if target_fid not in self.tool_shapes:
            raise ValueError(f"mirror: herramienta inexistente '{target_fid}'.")
        base_tool = self.tool_shapes[target_fid]
        mode = self.tool_modes.get(target_fid, "agregar")
        mirrored = mirror_shape(
            base_tool,
            plane=feature.get("plane", "YZ"),
            offset=feature.get("offset", 0.0),
        )
        shape = self._current_shape().fuse(mirrored) if mode == "agregar" else self._current_shape().cut(mirrored)
        return self._commit_shape(
            feature, shape, hide_ids=[self.current_id],
            mensaje=f"Simetria respecto de {feature.get('plane', 'YZ')} ({mode})."
        )


# Alias para poder reemplazar el executor sin cambiar APIs externas.
FeatureExecutorAdvanced = AdvancedFeatureExecutor
