# ui/panel.py
"""
Panel principal del Workbench.

Tres caminos de entrada que convergen en el MISMO pipeline y executor:

  1. IA universal (texto): clasifica → shaft | frame_structure | custom
  2. Parser simple sin IA: "Ø20x60, Ø30x120, Ø25x70"
  3. Imagen (visión): reconstrucción paramétrica aproximada

Luego: ejecutar paso a paso o todo, exportar STEP/STL, ver logs.
"""

import json

try:
    from PySide2 import QtWidgets
except ImportError:
    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets

from core.parser import prompt_a_feature_plan
from core.universal_parser import prompt_a_resultado_universal
from core.domain_router import process_design_request
from core.executor import FeatureExecutor
from core.logger import obtener_ruta_log
from core.exporter import exportar_step_stl, obtener_ruta_outputs


class AIDibujantePanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("AI Dibujante Traceable")

        self.feature_plan = None
        self.executor = None
        self.summary = None

        layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel("Prompt técnico:")
        layout.addWidget(self.label)

        self.prompt_box = QtWidgets.QTextEdit()
        self.prompt_box.setPlaceholderText(
            "Ejemplos (IA universal):\n"
            "- Diseña un eje de 250 mm con extremos delgados y tramo central "
            "robusto. Chavetero central y rosca M20 derecha.\n"
            "- Genera un engranaje recto de 40 dientes, módulo 2, ancho 20 mm, "
            "agujero Ø20 con chavetero.\n"
            "- Brida circular Ø160, espesor 15, agujero central Ø60, "
            "6 pernos M12 en círculo Ø120.\n"
            "- Mesa industrial de 1500x750x900 con tubo 40x40x3.\n\n"
            "Modo simple sin IA:\n"
            "crea un eje con tramos Ø20x60, Ø30x120 y Ø25x70"
        )
        layout.addWidget(self.prompt_box)

        self.btn_universal = QtWidgets.QPushButton(
            "1. Generar plan con IA universal (texto)"
        )
        self.btn_universal.clicked.connect(self.generar_plan_universal)
        layout.addWidget(self.btn_universal)

        fila = QtWidgets.QHBoxLayout()

        self.btn_simple = QtWidgets.QPushButton("1B. Parser simple (sin IA)")
        self.btn_simple.clicked.connect(self.generar_plan_simple)
        fila.addWidget(self.btn_simple)

        self.btn_imagen = QtWidgets.QPushButton("1C. Desde imagen (visión)")
        self.btn_imagen.clicked.connect(self.generar_desde_imagen)
        fila.addWidget(self.btn_imagen)

        layout.addLayout(fila)

        self.plan_box = QtWidgets.QTextEdit()
        self.plan_box.setReadOnly(True)
        layout.addWidget(self.plan_box)

        self.btn_paso = QtWidgets.QPushButton("2. Ejecutar siguiente paso")
        self.btn_paso.clicked.connect(self.ejecutar_paso)
        layout.addWidget(self.btn_paso)

        self.btn_todo = QtWidgets.QPushButton("3. Ejecutar todo")
        self.btn_todo.clicked.connect(self.ejecutar_todo)
        layout.addWidget(self.btn_todo)

        self.btn_exportar = QtWidgets.QPushButton("4. Exportar STEP/STL")
        self.btn_exportar.clicked.connect(self.exportar_modelo)
        layout.addWidget(self.btn_exportar)

        self.result_box = QtWidgets.QTextEdit()
        self.result_box.setReadOnly(True)
        layout.addWidget(self.result_box)

        self.btn_log = QtWidgets.QPushButton("Ver ruta de logs")
        self.btn_log.clicked.connect(self.mostrar_log)
        layout.addWidget(self.btn_log)

        self.form.setLayout(layout)

    # ------------------------------------------------------------ carga

    def _cargar_resultado(self, resultado, origen):
        self.feature_plan = resultado["feature_plan"]
        self.summary = resultado.get("summary", "")
        self.executor = FeatureExecutor(self.feature_plan)

        texto = ""
        if self.summary:
            texto += self.summary + "\n\n"
        texto += "PLAN CAD (JSON):\n"
        texto += json.dumps(self.feature_plan, indent=2, ensure_ascii=False)

        self.plan_box.setText(texto)

        clasificacion = resultado.get("classification")
        extra = ""
        if clasificacion:
            extra = (
                f"\nFamilia detectada: {clasificacion['family']} "
                f"(confianza {clasificacion.get('confidence', 0):.2f})"
            )

        self.result_box.setText(
            f"Plan CAD generado correctamente con {origen}.{extra}\n"
            "Revisa el resumen y las correcciones; luego ejecuta paso a paso "
            "o ejecuta todo."
        )

    def _cargar_plan_directo(self, feature_plan, origen):
        self.feature_plan = feature_plan
        self.summary = None
        self.executor = FeatureExecutor(self.feature_plan)

        self.plan_box.setText(
            json.dumps(self.feature_plan, indent=2, ensure_ascii=False)
        )
        self.result_box.setText(
            f"Plan CAD generado correctamente con {origen}.\n"
            "Ahora puedes ejecutar paso a paso o ejecutar todo."
        )

    # ------------------------------------------------------------ acciones

    def generar_plan_universal(self):
        try:
            prompt = self.prompt_box.toPlainText()

            if not prompt.strip():
                self.result_box.setText(
                    "Debes escribir una instrucción antes de usar la IA."
                )
                return

            self.result_box.setText(
                "Clasificando y consultando IA local (Ollama)...\n"
                "Esto puede tardar algunos segundos."
            )
            QtWidgets.QApplication.processEvents()

            resultado = prompt_a_resultado_universal(prompt)
            self._cargar_resultado(resultado, origen="IA universal")

        except Exception as e:
            self.result_box.setText(
                f"Error al generar plan con IA universal:\n{str(e)}"
            )

    def generar_plan_simple(self):
        try:
            prompt = self.prompt_box.toPlainText()
            feature_plan = prompt_a_feature_plan(prompt)
            self._cargar_plan_directo(feature_plan, origen="parser simple")

        except Exception as e:
            self.result_box.setText(
                f"Error al generar plan CAD local:\n{str(e)}"
            )

    def generar_desde_imagen(self):
        try:
            ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.form,
                "Seleccionar imagen de referencia",
                "",
                "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
            )

            if not ruta:
                return

            self.result_box.setText(
                "Analizando imagen con IA de visión local...\n"
                "Esto puede tardar hasta un par de minutos."
            )
            QtWidgets.QApplication.processEvents()

            from ai.vision_reconstruction_parser import (
                imagen_a_design_request_estructura
            )

            prompt = self.prompt_box.toPlainText()
            design_request = imagen_a_design_request_estructura(
                ruta, prompt_usuario=prompt
            )

            resultado = process_design_request(design_request, prompt)
            self._cargar_resultado(resultado, origen="reconstrucción desde imagen")

        except Exception as e:
            self.result_box.setText(
                f"Error al reconstruir desde imagen:\n{str(e)}"
            )

    def ejecutar_paso(self):
        try:
            if self.executor is None:
                self.result_box.setText("Primero debes generar un plan CAD.")
                return

            result = self.executor.execute_next()
            self.result_box.setText(
                json.dumps(result, indent=2, ensure_ascii=False)
            )

        except Exception as e:
            self.result_box.setText(f"Error al ejecutar paso:\n{str(e)}")

    def ejecutar_todo(self):
        try:
            if self.executor is None:
                self.result_box.setText("Primero debes generar un plan CAD.")
                return

            results = self.executor.execute_all()

            errores = [r for r in results if r.get("status") == "error"]
            resumen = f"Operaciones ejecutadas: {len(results)}"
            if errores:
                resumen += f" ({len(errores)} con error)"

            if self.executor.bom_text:
                resumen += "\n\n" + self.executor.bom_text

            self.result_box.setText(
                resumen + "\n\n" +
                json.dumps(results, indent=2, ensure_ascii=False)
            )

        except Exception as e:
            self.result_box.setText(f"Error al ejecutar todo:\n{str(e)}")

    def exportar_modelo(self):
        try:
            if self.executor is None:
                self.result_box.setText(
                    "Primero debes generar y ejecutar un modelo."
                )
                return

            final_obj = self.executor.get_final_object()

            if final_obj is None:
                self.result_box.setText(
                    "Todavía no existe un objeto final para exportar.\n"
                    "Primero ejecuta el plan CAD."
                )
                return

            nombre = self.feature_plan.get("nombre_pieza") if self.feature_plan else None
            nombre = nombre or final_obj.Name

            archivos = exportar_step_stl(final_obj, nombre_base=nombre)

            self.result_box.setText(
                "Modelo exportado correctamente.\n\n"
                f"STEP:\n{archivos['step']}\n\n"
                f"STL:\n{archivos['stl']}\n\n"
                f"Carpeta de salida:\n{obtener_ruta_outputs()}"
            )

        except Exception as e:
            self.result_box.setText(f"Error al exportar modelo:\n{str(e)}")

    def mostrar_log(self):
        try:
            self.result_box.setText(
                f"Los logs se están guardando en:\n{obtener_ruta_log()}"
            )
        except Exception as e:
            self.result_box.setText(f"Error al mostrar logs:\n{str(e)}")

    # ------------------------------------------------------------ diálogo

    def accept(self):
        return True

    def reject(self):
        return True
