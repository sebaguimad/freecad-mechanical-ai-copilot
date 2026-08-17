# ui/panel.py
"""Panel principal del Workbench con generacion, vision, RPC y autocorreccion."""

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
from core.executor_advanced import AdvancedFeatureExecutor
from core.logger import obtener_ruta_log
from core.exporter import exportar_step_stl, obtener_ruta_outputs


PROMPT_IMAGEN_APROX_DEFAULT = (
    "Recrea esta pieza mecanica de forma aproximada en FreeCAD. "
    "No busques una copia exacta. Prioriza las cotas visibles, superficies de "
    "revolucion, simetrias y patrones. Usa geometria CAD editable y asume "
    "dimensiones razonables si faltan datos. Mantiene la geometria limpia, "
    "parametrica y trazable."
)


class AIDibujantePanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("AI Dibujante Traceable - Agent Mode")

        self.feature_plan = None
        self.executor = None
        self.summary = None
        self.last_image_path = None

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Prompt tecnico:"))

        self.prompt_box = QtWidgets.QTextEdit()
        self.prompt_box.setPlaceholderText(
            "Ejemplos:\n"
            "- Genera una polea de dos canales con agujero central.\n"
            "- Recrea esta pieza mecanica aproximadamente y respeta las cotas visibles.\n"
            "- Genera una brida Ø160, espesor 15, agujero central Ø60 y 6 agujeros."
        )
        layout.addWidget(self.prompt_box)

        self.btn_universal = QtWidgets.QPushButton("1. Generar plan con IA universal (texto)")
        self.btn_universal.clicked.connect(self.generar_plan_universal)
        layout.addWidget(self.btn_universal)

        fila = QtWidgets.QHBoxLayout()
        self.btn_simple = QtWidgets.QPushButton("1B. Parser simple")
        self.btn_simple.clicked.connect(self.generar_plan_simple)
        fila.addWidget(self.btn_simple)
        self.btn_imagen = QtWidgets.QPushButton("1C. Recrear desde imagen (aprox.)")
        self.btn_imagen.clicked.connect(self.generar_desde_imagen)
        fila.addWidget(self.btn_imagen)
        layout.addLayout(fila)

        fila_agent = QtWidgets.QHBoxLayout()
        self.btn_agent_text = QtWidgets.QPushButton("AGENTE: texto + autocorreccion")
        self.btn_agent_text.clicked.connect(self.generar_texto_autocorregido)
        fila_agent.addWidget(self.btn_agent_text)
        self.btn_agent_image = QtWidgets.QPushButton("AGENTE: imagen + feedback visual")
        self.btn_agent_image.clicked.connect(self.generar_imagen_autocorregida)
        fila_agent.addWidget(self.btn_agent_image)
        layout.addLayout(fila_agent)

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
        self.btn_rpc = QtWidgets.QPushButton("5. Iniciar RPC Server (Ollama / IA externa)")
        self.btn_rpc.clicked.connect(self.iniciar_rpc_server)
        layout.addWidget(self.btn_rpc)

        self.result_box = QtWidgets.QTextEdit()
        self.result_box.setReadOnly(True)
        layout.addWidget(self.result_box)

        self.btn_log = QtWidgets.QPushButton("Ver ruta de logs")
        self.btn_log.clicked.connect(self.mostrar_log)
        layout.addWidget(self.btn_log)
        self.form.setLayout(layout)

    def _cargar_resultado(self, resultado, origen, executor=None):
        self.feature_plan = resultado["feature_plan"]
        self.summary = resultado.get("summary", "")
        self.executor = executor or AdvancedFeatureExecutor(self.feature_plan)
        texto = ""
        if self.summary:
            texto += self.summary + "\n\n"
        texto += "PLAN CAD (JSON):\n" + json.dumps(self.feature_plan, indent=2, ensure_ascii=False)
        self.plan_box.setText(texto)

        correction = resultado.get("self_correction")
        extra = ""
        if correction:
            extra = (
                f"\nIntentos automaticos: {correction.get('attempts')}"
                f"\nAceptado por revisor: {correction.get('accepted')}"
                f"\nScore: {correction.get('critic', {}).get('score')}"
                f"\nRevision: {correction.get('critic', {}).get('summary', '')}"
            )
        self.result_box.setText(f"Resultado generado con {origen}.{extra}")

    def _cargar_plan_directo(self, feature_plan, origen):
        self.feature_plan = feature_plan
        self.summary = None
        self.executor = AdvancedFeatureExecutor(feature_plan)
        self.plan_box.setText(json.dumps(feature_plan, indent=2, ensure_ascii=False))
        self.result_box.setText(f"Plan CAD generado con {origen}.")

    def _seleccionar_imagen(self):
        ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.form, "Seleccionar imagen o plano", "",
            "Imagenes (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if ruta:
            self.last_image_path = ruta
        return ruta

    def generar_plan_universal(self):
        try:
            prompt = self.prompt_box.toPlainText().strip()
            if not prompt:
                self.result_box.setText("Debes escribir una instruccion.")
                return
            self.result_box.setText("Consultando IA local...")
            QtWidgets.QApplication.processEvents()
            self._cargar_resultado(prompt_a_resultado_universal(prompt), "IA universal")
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def generar_plan_simple(self):
        try:
            self._cargar_plan_directo(
                prompt_a_feature_plan(self.prompt_box.toPlainText()), "parser simple"
            )
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def generar_desde_imagen(self):
        try:
            ruta = self._seleccionar_imagen()
            if not ruta:
                return
            prompt = self.prompt_box.toPlainText().strip() or PROMPT_IMAGEN_APROX_DEFAULT
            self.result_box.setText("Analizando referencia visual...")
            QtWidgets.QApplication.processEvents()
            from core.universal_image_to_cad import reconstruir_imagen_aproximada
            self._cargar_resultado(
                reconstruir_imagen_aproximada(ruta, prompt), "recreacion desde imagen"
            )
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def generar_texto_autocorregido(self):
        try:
            prompt = self.prompt_box.toPlainText().strip()
            if not prompt:
                self.result_box.setText("Debes escribir una instruccion.")
                return
            self.result_box.setText(
                "AGENTE activo: generando, inspeccionando y corrigiendo automaticamente..."
            )
            QtWidgets.QApplication.processEvents()
            from core.self_correcting_agent import generar_autocorregido_desde_texto
            result = generar_autocorregido_desde_texto(prompt, max_attempts=3)
            self._cargar_resultado(result, "agente autocorrectivo", executor=result.get("executor"))
        except Exception as e:
            self.result_box.setText(f"Error del agente:\n{e}")

    def generar_imagen_autocorregida(self):
        try:
            ruta = self._seleccionar_imagen()
            if not ruta:
                return
            prompt = self.prompt_box.toPlainText().strip() or PROMPT_IMAGEN_APROX_DEFAULT
            self.result_box.setText(
                "AGENTE VISUAL activo:\n"
                "1) interpreta la referencia\n2) genera FreeCAD\n3) captura vistas\n"
                "4) compara con la referencia\n5) corrige si es necesario (max. 3 intentos)"
            )
            QtWidgets.QApplication.processEvents()
            from core.self_correcting_agent import generar_autocorregido_desde_imagen
            result = generar_autocorregido_desde_imagen(ruta, prompt, max_attempts=3)
            self._cargar_resultado(result, "agente visual autocorrectivo", executor=result.get("executor"))
        except Exception as e:
            self.result_box.setText(f"Error del agente visual:\n{e}")

    def ejecutar_paso(self):
        try:
            if self.executor is None:
                self.result_box.setText("Primero genera un plan CAD.")
                return
            self.result_box.setText(json.dumps(self.executor.execute_next(), indent=2, ensure_ascii=False))
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def ejecutar_todo(self):
        try:
            if self.executor is None:
                self.result_box.setText("Primero genera un plan CAD.")
                return
            results = self.executor.execute_all()
            self.result_box.setText(json.dumps(results, indent=2, ensure_ascii=False))
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def exportar_modelo(self):
        try:
            if self.executor is None or self.executor.get_final_object() is None:
                self.result_box.setText("Primero genera y ejecuta un modelo.")
                return
            obj = self.executor.get_final_object()
            name = (self.feature_plan or {}).get("nombre_pieza") or obj.Name
            files = exportar_step_stl(obj, nombre_base=name)
            self.result_box.setText(
                f"Modelo exportado.\nSTEP: {files['step']}\nSTL: {files['stl']}\n"
                f"Carpeta: {obtener_ruta_outputs()}"
            )
        except Exception as e:
            self.result_box.setText(f"Error:\n{e}")

    def iniciar_rpc_server(self):
        try:
            from core.freecad_rpc_server import start_rpc_server
            status = start_rpc_server()
            self.result_box.setText(
                "RPC server activo en http://127.0.0.1:8765\n" +
                json.dumps(status, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            self.result_box.setText(f"Error RPC:\n{e}")

    def mostrar_log(self):
        self.result_box.setText(f"Logs:\n{obtener_ruta_log()}")

    def accept(self):
        return True

    def reject(self):
        return True
