# FreeCAD RPC Agent Bridge

Este módulo agrega un puente local para que **Ollama, Claude, ChatGPT u otra IA** pueda controlar FreeCAD mediante herramientas CAD seguras.

No reemplaza el Workbench. Lo complementa.

```text
IA externa / agente
        ↓
FreeCAD RPC Client
        ↓
FreeCAD RPC Server dentro de FreeCAD
        ↓
FeatureExecutor + primitivas CAD
        ↓
Modelo FreeCAD
```

## ¿Es MCP?

No todavía. Esta primera versión es un puente **MCP-like** usando XML-RPC de la librería estándar de Python.

La razón es práctica:

- funciona con FreeCAD sin instalar dependencias externas;
- puede ser usado por Ollama local;
- también puede servir como backend para un servidor MCP oficial más adelante;
- evita ejecutar código Python arbitrario generado por IA.

## Herramientas expuestas

El servidor RPC expone herramientas CAD controladas:

- `ping`
- `status`
- `get_objects`
- `clear_document`
- `create_box`
- `create_cylinder`
- `boolean_fuse`
- `cut_cylinder_hole`
- `add_fillet_all`
- `add_chamfer_all`
- `run_feature_plan`
- `run_prompt_universal`
- `save_document`
- `export_step_stl`

## Uso dentro de FreeCAD

Abre FreeCAD y ejecuta desde la consola Python:

```python
from core.freecad_rpc_server import start_rpc_server
start_rpc_server()
```

O usa el botón del panel:

```text
5. Iniciar RPC Server (Ollama / IA externa)
```

Por defecto escucha solo en local:

```text
http://127.0.0.1:8765
```

## Probar desde otro proceso Python

Desde PowerShell, en la carpeta del repo:

```powershell
python - <<'PY'
from core.freecad_rpc_client import FreeCADRPCClient

cad = FreeCADRPCClient()
print(cad.ping())
print(cad.create_box("base", 120, 80, 10, [0, 0, 0]))
print(cad.create_cylinder("boss", 40, 30, [60, 40, 10], "Z"))
print(cad.boolean_fuse("pieza", ["base", "boss"]))
PY
```

## Probar con Ollama

Con FreeCAD abierto y el RPC server iniciado:

```powershell
python agent/ollama_freecad_agent.py "crea una brida circular de diámetro 160 mm, espesor 15 mm, agujero central de 60 mm y 6 agujeros M12 en círculo de pernos de 120 mm"
```

El agente local hace esto:

```text
prompt del usuario
  → Ollama genera tool_calls JSON
  → FreeCADRPCClient ejecuta las llamadas
  → FreeCAD crea/modifica el modelo
```

## Cuándo usar `run_prompt_universal`

Para piezas más complejas, el agente puede llamar directamente al pipeline universal existente:

```json
{
  "tool": "run_prompt_universal",
  "args": {
    "prompt": "Genera un engranaje recto de 40 dientes, módulo 2, ancho 20 mm, agujero Ø20 con chavetero"
  }
}
```

Así no se pierde el trabajo ya hecho en:

- `core/universal_parser.py`
- `domains/custom/`
- `domains/frame_structure/`
- `core/executor.py`

## Seguridad

Esta versión evita exponer `exec()` o `eval()` al agente.

La IA no ejecuta Python arbitrario; solo puede llamar herramientas CAD predefinidas.

Limitaciones:

- Es experimental.
- FreeCAD puede no ser completamente thread-safe bajo RPC; guarda antes de pruebas largas.
- El modelo generado es aproximado y editable, no una copia exacta.
- Para control MCP oficial, este RPC server puede usarse luego como backend de `mcp_server/server.py`.
