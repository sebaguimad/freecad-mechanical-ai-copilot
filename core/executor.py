# core/executor.py
"""
Executor unificado y trazable.

UN solo executor para los tres dominios (antes había dos: FeatureExecutor
para ejes y frame_direct_executor para estructuras, y el de estructuras
no registraba eventos).

Tipos de feature soportados:

  shaft:   cylinder, boolean_fuse, keyway_cut, thread_zone,
           fillet_shoulders, fillet_all (seguro)
  frame:   box, square_tube_between_points, boolean_fuse, bom_report
  custom:  solid_add, solid_cut, polar_pattern, fillet_all, chamfer_all

Mejoras:
- FreeCADGui se importa de forma protegida: funciona en freecadcmd
  (headless), lo que permite automatizar y testear.
- Toda la ejecución ocurre dentro de una transacción del documento:
  un solo Ctrl+Z revierte la pieza completa.
- Los filetes/chaflanes usan las variantes seguras: si el kernel OCC
  rechaza aristas, se degrada con warning en vez de abortar el plan.
"""

import math

import FreeCAD as App

try:
    import FreeCADGui as Gui
    _HAS_GUI = App.GuiUp
except Exception:
    Gui = None
    _HAS_GUI = False

from generators.primitives import (
    construir_shape,
    construir_box,
    crear_cilindro_x,
    crear_tubo_cuadrado_entre_puntos,
    fusionar_solidos,
    cortar_chavetero,
    aplicar_rosca_simplificada,
    aplicar_filete_seguro,
    aplicar_filete_hombros,
    aplicar_chaflan_seguro,
    patron_polar
)
from core.logger import registrar_evento
from core.metrics import extraer_metricas_objeto


class FeatureExecutor:
    def __init__(self, feature_plan):
        self.feature_plan = feature_plan
        self.feature_tree = feature_plan.get("feature_tree", [])
        self.family = feature_plan.get("family", feature_plan.get("domain", "custom"))
        self.current_index = 0

        self.state = {}          # feature_id -> objeto de documento
        self.tool_shapes = {}    # feature_id -> shape "herramienta" (para patrones)
        self.tool_modes = {}     # feature_id -> "agregar" | "cortar"
        self.current_id = None   # feature_id del sólido en construcción (custom)
        self.final_object = None
        self.bom_text = None
        self._transaction_open = False

        self.doc = App.ActiveDocument
        if self.doc is None:
            self.doc = App.newDocument("AI_Dibujante_Traceable")

    # ------------------------------------------------------------ control

    def has_next(self):
        return self.current_index < len(self.feature_tree)

    def execute_next(self):
        if not self.has_next():
            return {"status": "finished",
                    "message": "No quedan operaciones por ejecutar."}

        feature = self.feature_tree[self.current_index]
        result = self._execute_feature(feature)
        self.current_index += 1
        return result

    def execute_all(self):
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

    def get_final_object(self):
        return self.final_object

    # ------------------------------------------------------------ dispatch

    _HANDLERS = {}

    def _execute_feature(self, feature):
        feature_type = feature.get("type")

        handler = getattr(self, f"_execute_{feature_type}", None)

        try:
            if handler is None:
                raise NotImplementedError(
                    f"Feature no soportada: {feature_type}"
                )
            return handler(feature)

        except Exception as e:
            registrar_evento({
                "feature_id": feature.get("id"),
                "operation": feature_type,
                "parameters": {k: v for k, v in feature.items() if k != "shape"},
                "status": "error",
                "error": str(e)
            })
            return {"status": "error", "feature": feature, "message": str(e)}

    # ------------------------------------------------------------ helpers

    def _commit_shape(self, feature, shape, hide_ids=(), es_resultado=True,
                      mensaje="Operación ejecutada."):
        """
        Registra el shape como objeto del documento, oculta antecesores,
        actualiza estado, métricas y log. Punto único de salida de todos
        los handlers geométricos.
        """
        obj = self.doc.addObject("Part::Feature", feature.get("name", feature["id"]))
        obj.Shape = shape
        self.doc.recompute()

        for hid in hide_ids:
            if hid in self.state:
                self._hide_object(self.state[hid])

        self.state[feature["id"]] = obj

        metricas = None
        if es_resultado:
            self.final_object = obj
            self.current_id = feature["id"]
            try:
                metricas = extraer_metricas_objeto(obj)
            except Exception:
                metricas = None

        evento = {
            "feature_id": feature["id"],
            "operation": feature["type"],
            "parameters": {k: v for k, v in feature.items() if k != "shape"},
            "status": "ok"
        }
        if metricas:
            evento["metrics"] = metricas
        registrar_evento(evento)

        self._fit_view()

        resultado = {"status": "ok", "feature": feature, "message": mensaje}
        if metricas:
            resultado["metrics"] = metricas
        return resultado

    def _require(self, feature_id):
        if feature_id not in self.state:
            raise ValueError(f"No existe el objeto requerido en memoria: {feature_id}")
        return self.state[feature_id]

    def _current_shape(self):
        if self.current_id is None:
            raise ValueError(
                "No existe una pieza en construcción. La primera operación "
                "debe agregar material."
            )
        return self.state[self.current_id].Shape

    # ------------------------------------------------------------ shaft

    def _execute_cylinder(self, feature):
        shape = crear_cilindro_x(
            diametro=feature["diameter"],
            longitud=feature["length"],
            start_x=feature["start_x"]
        )
        return self._commit_shape(
            feature, shape, es_resultado=False,
            mensaje=f"Cilindro creado: {feature.get('name')}"
        )

    def _execute_boolean_fuse(self, feature):
        input_ids = feature["inputs"]
        input_objs = [self._require(i) for i in input_ids]
        fused = fusionar_solidos([o.Shape for o in input_objs])

        return self._commit_shape(
            feature, fused, hide_ids=input_ids,
            mensaje="Sólidos fusionados correctamente."
        )

    def _execute_keyway_cut(self, feature):
        target = self._require(feature["target"])
        start_x = feature["segment_start_x"] + feature["offset_x"]

        shape = cortar_chavetero(
            shape=target.Shape,
            segment_diameter=feature["segment_diameter"],
            start_x=start_x,
            length=feature["length"],
            width=feature["width"],
            depth=feature["depth"]
        )

        return self._commit_shape(
            feature, shape, hide_ids=[feature["target"]],
            mensaje="Chavetero cortado correctamente."
        )

    def _execute_thread_zone(self, feature):
        target = self._require(feature["target"])

        shape = aplicar_rosca_simplificada(
            shape=target.Shape,
            segment_diameter=feature["segment_diameter"],
            nominal_diameter=feature["nominal_diameter"],
            start_x=feature["start_x"],
            length=feature["length"]
        )

        return self._commit_shape(
            feature, shape, hide_ids=[feature["target"]],
            mensaje="Rosca simplificada generada correctamente."
        )

    def _execute_fillet_shoulders(self, feature):
        target = self._require(feature["target"])

        shape, ok, fallidas = aplicar_filete_hombros(
            target.Shape, feature["radius"],
            total_length=feature.get("total_length")
        )

        msg = f"Filete de hombros: {ok} aristas fileteadas"
        if fallidas:
            msg += f", {fallidas} rechazadas por el kernel (se omitieron)"

        return self._commit_shape(
            feature, shape, hide_ids=[feature["target"]], mensaje=msg + "."
        )

    # ------------------------------------------------------------ frame

    def _execute_box(self, feature):
        shape = construir_box(
            length=feature["length"],
            width=feature["width"],
            height=feature["height"],
            position=feature.get("position", [0, 0, 0])
        )
        return self._commit_shape(
            feature, shape, es_resultado=False,
            mensaje=f"Caja creada: {feature.get('name')}"
        )

    def _execute_square_tube_between_points(self, feature):
        shape = crear_tubo_cuadrado_entre_puntos(
            profile=feature.get("profile", {}),
            start=feature["start"],
            end=feature["end"]
        )
        return self._commit_shape(
            feature, shape, es_resultado=False,
            mensaje=f"Perfil creado: {feature.get('name')}"
        )

    def _execute_bom_report(self, feature):
        lines = ["LISTA DE MATERIALES (BOM)", ""]

        top = feature.get("top")
        if top and top.get("enabled"):
            lines.append(
                f"1 x Cubierta: plancha {top['length']:g} x {top['width']:g} "
                f"x {top['thickness']:g} mm"
            )

        perfiles = {}
        for m in feature.get("members", []):
            p = m["profile"]
            s, e = m["start"], m["end"]
            largo = math.sqrt(
                (e[0]-s[0])**2 + (e[1]-s[1])**2 + (e[2]-s[2])**2
            )
            clave = f"tubo {p['width']:g}x{p['height']:g}x{p['thickness']:g}"
            perfiles.setdefault(clave, []).append((m["id"], largo))

        total_por_perfil = {}
        for clave, items in perfiles.items():
            for mid, largo in items:
                lines.append(f"1 x {clave}, L={largo:.1f} mm ({mid})")
            total_por_perfil[clave] = sum(l for _, l in items)

        for plate in feature.get("plates", []):
            lines.append(
                f"1 x Placa {plate.get('role', '')}: {plate['length']:g} x "
                f"{plate['width']:g} x {plate['thickness']:g} mm ({plate['id']})"
            )

        if total_por_perfil:
            lines.append("")
            lines.append("Totales de perfil (agregar % de despunte):")
            for clave, total in total_por_perfil.items():
                lines.append(f"- {clave}: {total/1000.0:.2f} m")

        self.bom_text = "\n".join(lines)

        registrar_evento({
            "feature_id": feature["id"],
            "operation": "bom_report",
            "status": "ok",
            "bom": self.bom_text
        })

        return {"status": "ok", "feature": feature,
                "message": self.bom_text}

    # ------------------------------------------------------------ custom

    def _execute_solid_add(self, feature):
        tool = construir_shape(feature["shape"])
        self.tool_shapes[feature["id"]] = tool
        self.tool_modes[feature["id"]] = "agregar"

        if self.current_id is None:
            shape = tool
            hide = []
        else:
            shape = self._current_shape().fuse(tool)
            hide = [self.current_id]

        return self._commit_shape(
            feature, shape, hide_ids=hide,
            mensaje=f"Material agregado: {feature.get('name')}"
        )

    def _execute_solid_cut(self, feature):
        tool = construir_shape(feature["shape"])
        self.tool_shapes[feature["id"]] = tool
        self.tool_modes[feature["id"]] = "cortar"

        shape = self._current_shape().cut(tool)

        return self._commit_shape(
            feature, shape, hide_ids=[self.current_id],
            mensaje=f"Material cortado: {feature.get('name')}"
        )

    def _execute_polar_pattern(self, feature):
        target_fid = feature.get("pattern_target")

        if target_fid not in self.tool_shapes:
            raise ValueError(
                f"polar_pattern: no existe la herramienta '{target_fid}'."
            )

        base_tool = self.tool_shapes[target_fid]
        modo = self.tool_modes.get(target_fid, "agregar")

        copias = patron_polar(
            base_tool,
            cantidad=feature["count"],
            centro=feature.get("center", [0, 0, 0]),
            eje=feature.get("axis", "Z")
        )

        if not copias:
            raise ValueError("polar_pattern generó 0 copias.")

        conjunto = fusionar_solidos(copias)

        if modo == "agregar":
            shape = self._current_shape().fuse(conjunto)
        else:
            shape = self._current_shape().cut(conjunto)

        return self._commit_shape(
            feature, shape, hide_ids=[self.current_id],
            mensaje=(
                f"Patrón polar: {feature['count']} instancias de "
                f"'{target_fid}' ({modo})."
            )
        )

    def _execute_fillet_all(self, feature):
        # Funciona tanto con target explícito (shaft legado) como con la
        # pieza en construcción (custom).
        target_id = feature.get("target", self.current_id)
        target = self._require(target_id)

        shape, ok, fallidas = aplicar_filete_seguro(
            target.Shape, feature["radius"]
        )

        msg = f"Filete: {ok} aristas fileteadas"
        if fallidas:
            msg += f", {fallidas} rechazadas por el kernel (se omitieron)"

        return self._commit_shape(
            feature, shape, hide_ids=[target_id], mensaje=msg + "."
        )

    def _execute_chamfer_all(self, feature):
        target_id = feature.get("target", self.current_id)
        target = self._require(target_id)

        shape, ok, fallidas = aplicar_chaflan_seguro(
            target.Shape, feature["distance"]
        )

        msg = f"Chaflán: {ok} aristas" if ok else "Chaflán no aplicable; se omitió"

        return self._commit_shape(
            feature, shape, hide_ids=[target_id], mensaje=msg + "."
        )

    # ------------------------------------------------------------ entorno

    def _begin_transaction(self):
        try:
            self.doc.openTransaction("AI Dibujante: generar pieza")
            self._transaction_open = True
        except Exception:
            self._transaction_open = False

    def _commit_transaction(self):
        if self._transaction_open:
            try:
                self.doc.commitTransaction()
            except Exception:
                pass
            self._transaction_open = False

    def _hide_object(self, obj):
        if not _HAS_GUI:
            return
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass

    def _fit_view(self):
        if not _HAS_GUI or Gui is None:
            return
        try:
            if Gui.ActiveDocument is not None:
                Gui.ActiveDocument.ActiveView.fitAll()
        except Exception:
            pass
