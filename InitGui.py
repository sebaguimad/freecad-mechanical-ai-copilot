# InitGui.py

import os
import sys

import FreeCAD as App
import FreeCADGui as Gui


MODULE_DIR = os.path.join(
    App.getUserAppDataDir(),
    "Mod",
    "AIDibujanteModular"
)

if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


class AIDibujanteModularWorkbench(Gui.Workbench):
    MenuText = "AIDibujanteModular"
    ToolTip = "Workbench modular de dibujo mecánico asistido por IA con trazabilidad CAD"
    Icon = ""

    def Initialize(self):
        import commands

        self.comandos = [
            "AIDibujante_OpenPanel"
        ]

        self.appendToolbar("AI Dibujante Modular", self.comandos)
        self.appendMenu("AI Dibujante Modular", self.comandos)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(AIDibujanteModularWorkbench())