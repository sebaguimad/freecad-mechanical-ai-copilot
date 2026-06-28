# commands.py

import FreeCADGui as Gui


class OpenPanelCommand:
    def GetResources(self):
        return {
            "MenuText": "Abrir asistente",
            "ToolTip": "Abrir AI Dibujante Traceable",
            "Pixmap": ""
        }

    def Activated(self):
        from ui.panel import AIDibujantePanel
        panel = AIDibujantePanel()
        Gui.Control.showDialog(panel)

    def IsActive(self):
        return True


Gui.addCommand("AIDibujante_OpenPanel", OpenPanelCommand())