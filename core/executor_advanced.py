"""Extension del FeatureExecutor con operaciones CAD avanzadas y rebuild incremental."""

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

    def __init__(self, feature_plan):
        # Los features suprimidos permanecen en el plan para trazabilidad, pero
        # no participan en la reconstruccion geometrica.
        clean_plan = dict(feature_plan)
        clean_plan["feature_tree"] = [
            f for f in feature_plan.get("feature_tree", [])
            if not f.get("suppressed", False)
        ]
        super().__init__(clean_plan)
        self.original_feature_plan = feature_plan

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

    # ------------------------------------------------------------------
    # Rebuild incremental para el agente de correccion

    def _is_custom_result_feature(self, feature):
        return feature.get("type") in {
            "solid_add", "solid_cut", "polar_pattern", "linear_pattern",
            "mirror", "fillet_all", "chamfer_all"
        }

    def rebuild_from_index(self, new_feature_plan, affected_index):
        """Reutiliza el prefijo ya ejecutado y recalcula solo el sufijo afectado.

        Diseñado para family=custom. Si la estructura del prefijo cambia o no
        existe estado reutilizable, el llamador debe caer a regeneracion completa.
        """
        if self.family != "custom":
            raise ValueError("El rebuild incremental actualmente solo soporta family=custom.")

        new_tree_all = new_feature_plan.get("feature_tree", [])
        new_tree = [f for f in new_tree_all if not f.get("suppressed", False)]
        affected_index = max(0, min(int(affected_index), len(new_tree)))

        # Verificar que el prefijo conserva exactamente los mismos ids.
        old_prefix_ids = [f.get("id") for f in self.feature_tree[:affected_index]]
        new_prefix_ids = [f.get("id") for f in new_tree[:affected_index]]
        if old_prefix_ids != new_prefix_ids:
            raise ValueError("El prefijo del plan cambio; no se puede reutilizar de forma segura.")

        # Borrar objetos/document-state solo desde el primer feature afectado.
        suffix_ids = {f.get("id") for f in self.feature_tree[affected_index:]}
        for fid in list(suffix_ids):
            obj = self.state.pop(fid, None)
            if obj is not None:
                try:
                    self.doc.removeObject(obj.Name)
                except Exception:
                    pass
            self.tool_shapes.pop(fid, None)
            self.tool_modes.pop(fid, None)

        self.doc.recompute()

        # El ultimo feature geometrico previo pasa a ser el current_id reutilizado.
        self.current_id = None
        self.final_object = None
        for feature in new_tree[:affected_index]:
            fid = feature.get("id")
            if self._is_custom_result_feature(feature) and fid in self.state:
                self.current_id = fid
                self.final_object = self.state[fid]

        # Herramientas de operaciones previas deben seguir disponibles para
        # patterns posteriores. Si alguna se perdio, reconstruir su tool shape sin
        # modificar el documento.
        for feature in new_tree[:affected_index]:
            fid = feature.get("id")
            ftype = feature.get("type")
            if ftype in ("solid_add", "solid_cut") and fid not in self.tool_shapes:
                self.tool_shapes[fid] = self._build_tool_shape(feature["shape"])
                self.tool_modes[fid] = "agregar" if ftype == "solid_add" else "cortar"

        self.original_feature_plan = new_feature_plan
        self.feature_plan = dict(new_feature_plan)
        self.feature_tree = new_tree
        self.current_index = affected_index

        results = []
        self._begin_transaction()
        try:
            while self.has_next():
                result = self.execute_next()
                results.append(result)
                if result.get("status") == "error":
                    break
        finally:
            self._commit_transaction()

        return results


FeatureExecutorAdvanced = AdvancedFeatureExecutor
