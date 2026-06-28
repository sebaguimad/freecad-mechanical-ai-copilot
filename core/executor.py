# core/executor.py

import FreeCAD as App
import FreeCADGui as Gui

from generators.primitives import (
    crear_cilindro_x,
    fusionar_solidos,
    cortar_chavetero,
    aplicar_rosca_simplificada,
    aplicar_filete_global
)
from core.logger import registrar_evento
from core.metrics import extraer_metricas_objeto


class FeatureExecutor:
    def __init__(self, feature_plan):
        self.feature_plan = feature_plan
        self.feature_tree = feature_plan["feature_tree"]
        self.current_index = 0
        self.state = {}
        self.final_object = None
        self.doc = App.ActiveDocument

        if self.doc is None:
            self.doc = App.newDocument("AI_Dibujante_Traceable")

    def has_next(self):
        return self.current_index < len(self.feature_tree)

    def execute_next(self):
        if not self.has_next():
            return {
                "status": "finished",
                "message": "No quedan operaciones por ejecutar."
            }

        feature = self.feature_tree[self.current_index]
        result = self._execute_feature(feature)

        self.current_index += 1

        return result

    def execute_all(self):
        results = []

        while self.has_next():
            result = self.execute_next()
            results.append(result)

            if result.get("status") == "error":
                break

        return results

    def _execute_feature(self, feature):
        feature_type = feature["type"]

        try:
            if feature_type == "cylinder":
                return self._execute_cylinder(feature)

            if feature_type == "boolean_fuse":
                return self._execute_boolean_fuse(feature)

            if feature_type == "keyway_cut":
                return self._execute_keyway_cut(feature)

            if feature_type == "thread_zone":
                return self._execute_thread_zone(feature)

            if feature_type == "fillet_all":
                return self._execute_fillet_all(feature)

            raise NotImplementedError(
                f"Feature no soportada: {feature_type}"
            )

        except Exception as e:
            registrar_evento({
                "feature_id": feature.get("id"),
                "operation": feature_type,
                "parameters": feature,
                "status": "error",
                "error": str(e)
            })

            return {
                "status": "error",
                "feature": feature,
                "message": str(e)
            }

    def _execute_cylinder(self, feature):
        shape = crear_cilindro_x(
            diametro=feature["diameter"],
            longitud=feature["length"],
            start_x=feature["start_x"]
        )

        obj = self.doc.addObject("Part::Feature", feature["name"])
        obj.Shape = shape

        self.doc.recompute()

        self.state[feature["id"]] = obj

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "cylinder",
            "parameters": feature,
            "status": "ok"
        })

        self._fit_view()

        return {
            "status": "ok",
            "feature": feature,
            "message": f"Cilindro creado: {feature['name']}"
        }

    def _execute_boolean_fuse(self, feature):
        input_ids = feature["inputs"]

        input_objs = []

        for input_id in input_ids:
            if input_id not in self.state:
                raise ValueError(
                    f"No existe el objeto requerido en memoria: {input_id}"
                )

            input_objs.append(self.state[input_id])

        input_shapes = [obj.Shape for obj in input_objs]

        fused_shape = fusionar_solidos(input_shapes)

        obj = self.doc.addObject("Part::Feature", feature["name"])
        obj.Shape = fused_shape

        self.doc.recompute()

        for input_obj in input_objs:
            self._hide_object(input_obj)

        self.state[feature["id"]] = obj
        self.final_object = obj

        metricas = extraer_metricas_objeto(obj)

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "boolean_fuse",
            "inputs": input_ids,
            "status": "ok",
            "metrics": metricas
        })

        self._fit_view()

        return {
            "status": "ok",
            "feature": feature,
            "metrics": metricas,
            "message": "Sólidos fusionados correctamente."
        }

    def _execute_keyway_cut(self, feature):
        target_id = feature["target"]

        if target_id not in self.state:
            raise ValueError(f"No existe el target requerido: {target_id}")

        target_obj = self.state[target_id]

        start_x = feature["segment_start_x"] + feature["offset_x"]

        result_shape = cortar_chavetero(
            shape=target_obj.Shape,
            segment_diameter=feature["segment_diameter"],
            start_x=start_x,
            length=feature["length"],
            width=feature["width"],
            depth=feature["depth"]
        )

        obj = self.doc.addObject("Part::Feature", feature["name"])
        obj.Shape = result_shape

        self.doc.recompute()

        self._hide_object(target_obj)

        self.state[feature["id"]] = obj
        self.final_object = obj

        metricas = extraer_metricas_objeto(obj)

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "keyway_cut",
            "parameters": feature,
            "status": "ok",
            "metrics": metricas
        })

        self._fit_view()

        return {
            "status": "ok",
            "feature": feature,
            "metrics": metricas,
            "message": "Chavetero cortado correctamente."
        }

    def _execute_thread_zone(self, feature):
        target_id = feature["target"]

        if target_id not in self.state:
            raise ValueError(f"No existe el target requerido: {target_id}")

        target_obj = self.state[target_id]

        result_shape = aplicar_rosca_simplificada(
            shape=target_obj.Shape,
            segment_diameter=feature["segment_diameter"],
            nominal_diameter=feature["nominal_diameter"],
            start_x=feature["start_x"],
            length=feature["length"]
        )

        obj = self.doc.addObject("Part::Feature", feature["name"])
        obj.Shape = result_shape

        self.doc.recompute()

        self._hide_object(target_obj)

        self.state[feature["id"]] = obj
        self.final_object = obj

        metricas = extraer_metricas_objeto(obj)

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "thread_zone",
            "parameters": feature,
            "status": "ok",
            "metrics": metricas
        })

        self._fit_view()

        return {
            "status": "ok",
            "feature": feature,
            "metrics": metricas,
            "message": "Rosca simplificada generada correctamente."
        }

    def _execute_fillet_all(self, feature):
        target_id = feature["target"]

        if target_id not in self.state:
            raise ValueError(f"No existe el target requerido: {target_id}")

        target_obj = self.state[target_id]

        result_shape = aplicar_filete_global(
            shape=target_obj.Shape,
            radio=feature["radius"]
        )

        obj = self.doc.addObject("Part::Feature", feature["name"])
        obj.Shape = result_shape

        self.doc.recompute()

        self._hide_object(target_obj)

        self.state[feature["id"]] = obj
        self.final_object = obj

        metricas = extraer_metricas_objeto(obj)

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "fillet_all",
            "parameters": feature,
            "status": "ok",
            "metrics": metricas
        })

        self._fit_view()

        return {
            "status": "ok",
            "feature": feature,
            "metrics": metricas,
            "message": "Filete aplicado correctamente."
        }

    def get_final_object(self):
        return self.final_object

    def _hide_object(self, obj):
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass

    def _fit_view(self):
        try:
            if Gui.ActiveDocument is not None:
                Gui.ActiveDocument.ActiveView.fitAll()
        except Exception:
            pass