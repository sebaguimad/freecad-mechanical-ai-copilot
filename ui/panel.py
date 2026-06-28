# ui/panel.py

import json

try:
    from PySide2 import QtWidgets
except ImportError:
    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets

from core.parser import prompt_a_feature_plan
from core.local_ai_parser import prompt_a_feature_plan_ollama
from core.executor import FeatureExecutor
from core.logger import obtener_ruta_log
from core.exporter import exportar_step_stl, obtener_ruta_outputs


class AIDibujantePanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("AI Dibujante Traceable")

        self.feature_plan = None
        self.executor = None

        layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel("Prompt técnico:")
        layout.addWidget(self.label)

        self.prompt_box = QtWidgets.QTextEdit()
        self.prompt_box.setPlaceholderText(
            "Modo local simple:\n"
            "crea un eje con tramos Ø20x60, Ø30x120 y Ø25x70\n\n"
            "Modo IA local con Ollama:\n"
            "Diseña un eje de 250 mm con extremos delgados y tramo central robusto "
            "para montar una polea. Agrega chavetero central y rosca M20 derecha."
        )
        layout.addWidget(self.prompt_box)

        self.btn_generar_plan = QtWidgets.QPushButton("1. Generar plan CAD local")
        self.btn_generar_plan.clicked.connect(self.generar_plan_local)
        layout.addWidget(self.btn_generar_plan)

        self.btn_generar_plan_ollama = QtWidgets.QPushButton("1B. Generar plan CAD con IA local Ollama")
        self.btn_generar_plan_ollama.clicked.connect(self.generar_plan_ollama)
        layout.addWidget(self.btn_generar_plan_ollama)

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

    def _cargar_plan_en_panel(self, feature_plan, origen):
        self.feature_plan = feature_plan
        self.executor = FeatureExecutor(self.feature_plan)

        self.plan_box.setText(
            json.dumps(self.feature_plan, indent=2, ensure_ascii=False)
        )

        self.result_box.setText(
            f"Plan CAD generado correctamente con {origen}.\n"
            "Ahora puedes ejecutar paso a paso o ejecutar todo."
        )

    def generar_plan_local(self):
        try:
            prompt = self.prompt_box.toPlainText()

            feature_plan = prompt_a_feature_plan(prompt)

            self._cargar_plan_en_panel(
                feature_plan=feature_plan,
                origen="parser local"
            )

        except Exception as e:
            self.result_box.setText(
                "Error al generar plan CAD local:\n"
                f"{str(e)}"
            )

    def generar_plan_ollama(self):
        try:
            prompt = self.prompt_box.toPlainText()

            if not prompt.strip():
                self.result_box.setText(
                    "Debes escribir una instrucción antes de usar IA local."
                )
                return

            self.result_box.setText(
                "Consultando IA local con Ollama...\n"
                "Esto puede tardar algunos segundos."
            )

            QtWidgets.QApplication.processEvents()

            feature_plan = prompt_a_feature_plan_ollama(prompt)

            self._cargar_plan_en_panel(
                feature_plan=feature_plan,
                origen="Ollama local"
            )

        except Exception as e:
            self.result_box.setText(
                "Error al generar plan CAD con Ollama:\n"
                f"{str(e)}"
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
            self.result_box.setText(
                "Error al ejecutar paso:\n"
                f"{str(e)}"
            )

    def ejecutar_todo(self):
        try:
            if self.executor is None:
                self.result_box.setText("Primero debes generar un plan CAD.")
                return

            results = self.executor.execute_all()

            self.result_box.setText(
                json.dumps(results, indent=2, ensure_ascii=False)
            )

        except Exception as e:
            self.result_box.setText(
                "Error al ejecutar todo:\n"
                f"{str(e)}"
            )

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
                    "Primero ejecuta todo el plan CAD o llega hasta la operación de fusión."
                )
                return

            archivos = exportar_step_stl(
                final_obj,
                nombre_base=final_obj.Name
            )

            self.result_box.setText(
                "Modelo exportado correctamente.\n\n"
                f"STEP:\n{archivos['step']}\n\n"
                f"STL:\n{archivos['stl']}\n\n"
                f"Carpeta de salida:\n{obtener_ruta_outputs()}"
            )

        except Exception as e:
            self.result_box.setText(
                "Error al exportar modelo:\n"
                f"{str(e)}"
            )

    def mostrar_log(self):
        try:
            self.result_box.setText(
                f"Los logs se están guardando en:\n{obtener_ruta_log()}"
            )

        except Exception as e:
            self.result_box.setText(
                "Error al mostrar logs:\n"
                f"{str(e)}"
            )

    def accept(self):
        return True

    def reject(self):
        return True