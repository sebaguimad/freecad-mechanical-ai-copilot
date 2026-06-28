# AIDibujante v0.5-alpha: Vision Reconstruction + Frame Structure

Este scaffold agrega la base para que el Workbench haga lo que buscas:

**imagen de una estructura / mesa industrial**
→ **reconstrucción paramétrica aproximada**
→ **spec editable**
→ **validador**
→ **assembly/feature plan**
→ **FreeCAD genera modelo editable**

No busca copiar exacto desde una foto. Busca generar una hipótesis CAD paramétrica, trazable y editable.

## Módulos incluidos

```text
ai/
└─ vision_reconstruction_parser.py

domains/
└─ frame_structure/
   ├─ __init__.py
   ├─ profile_library.py
   ├─ validator.py
   ├─ planner.py
   └─ summary.py

knowledge/
└─ frame_structure/
   └─ rules.md

PATCH_FRAME_STRUCTURE.md
```

## Flujo

```text
Imagen
↓
ai/vision_reconstruction_parser.py
↓
design_request JSON
↓
domains/frame_structure/validator.py
↓
domains/frame_structure/planner.py
↓
feature_plan
↓
core/executor.py
↓
FreeCAD
```

## Prueba esperada

```python
from ai.vision_reconstruction_parser import imagen_a_design_request_estructura
from core.domain_router import process_design_request
from core.executor import FeatureExecutor

image_path = r"C:\Users\sebag\Desktop\mesa_industrial.png"

req = imagen_a_design_request_estructura(
    image_path,
    "Reconstruye esta imagen como una mesa industrial paramétrica. Si faltan cotas, usa supuestos razonables."
)

result = process_design_request(req, prompt_usuario="mesa industrial desde imagen")
print(result["summary_text"])

ex = FeatureExecutor(result["feature_plan"])
ex.execute_all()
```

Antes de probar, aplica los parches indicados en `PATCH_FRAME_STRUCTURE.md`.
