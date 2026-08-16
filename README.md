# AI Dibujante Modular — v0.7 Agent Mode

Copiloto CAD local para FreeCAD con Ollama. Convierte texto, fotografías y planos
en recreaciones mecánicas paramétricas aproximadas, ejecuta el modelo en FreeCAD
y ahora puede inspeccionar lo generado y realizar hasta 3 intentos de corrección.

## Flujo principal

```text
texto / foto / plano
      ↓
Ollama / Qwen Vision
      ↓
design_request + assumptions
      ↓
validator + feature_plan
      ↓
AdvancedFeatureExecutor
      ↓
FreeCAD / OpenCASCADE
      ↓
inspección geométrica + capturas
      ↓
IA revisora
      ↓
ACCEPT ───────────────→ modelo final
  │
  └─ REGENERATE → instrucciones de corrección → nuevo intento
```

El objetivo es **recreación aproximada**, no fotogrametría ni ingeniería inversa
metrológica exacta.

## Agent Mode

El panel incorpora dos acciones nuevas:

- **AGENTE: texto + autocorrección**: genera, inspecciona el shape, revisa errores
de ejecución/topología y reintenta si el resultado no es coherente.
- **AGENTE: imagen + feedback visual**: además captura vistas isométrica, frontal
y lateral del resultado y las compara con la imagen/plano de referencia mediante
el modelo de visión.

El revisor considera silueta, topología, agujeros, salientes, patrones, simetrías
y proporciones generales. No intenta igualar color, textura o iluminación.

Más detalles: [`README_AGENT_FEEDBACK.md`](README_AGENT_FEEDBACK.md).

## Geometría universal

Operaciones básicas:

`box, cylinder, cone, sphere, polygon_prism, polar_pattern, fillet_all, chamfer_all`

Operaciones avanzadas:

`sketch_extrude, revolve, sweep, loft, linear_pattern, mirror`

Esto permite aproximar, entre otras cosas:

- ejes, bujes y piezas torneadas;
- bridas y placas perforadas;
- poleas y cuerpos de revolución;
- engranajes simplificados;
- soportes, ménsulas y nervios;
- mesas, bastidores y estructuras soldadas;
- tubos/manillas simples mediante sweep;
- transiciones y carcasas simplificadas mediante loft;
- geometrías repetitivas y simétricas.

## Imagen y planos

Prompt recomendado:

> Recrea esta pieza mecánica aproximadamente en FreeCAD. Prioriza las cotas visibles. Conserva la topología, simetrías y patrones principales. Si faltan dimensiones, asume valores razonables y decláralos. Prefiere geometría CAD robusta antes que detalles frágiles.

Para obtener el mejor resultado utiliza **AGENTE: imagen + feedback visual**.

## RPC para cualquier IA

FreeCAD también puede funcionar como backend local para Ollama, Claude, ChatGPT
o cualquier agente capaz de llamar el cliente RPC.

```text
IA externa
   ↓
FreeCADRPCClient
   ↓
RPC local 127.0.0.1:8765
   ↓
FreeCAD
```

El objetivo es exponer herramientas CAD controladas en vez de ejecutar Python
arbitrario generado por el modelo.

Desde FreeCAD:

```python
from core.freecad_rpc_server import start_rpc_server
start_rpc_server()
```

Más detalles: [`README_RPC_AGENT.md`](README_RPC_AGENT.md).

## Instalación

1. Copiar el proyecto a `%APPDATA%/FreeCAD/Mod/AIDibujanteModular`.
2. Instalar Ollama.
3. Descargar los modelos recomendados:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5vl:7b
```

4. Abrir FreeCAD y seleccionar `AIDibujanteModular`.

## Archivos clave

```text
ai/
  ollama_client.py              texto + visión + multi-imagen
  approx_mechanical_vision_parser.py
  model_critic.py               revisor IA

core/
  universal_parser.py
  universal_image_to_cad.py
  executor.py
  executor_advanced.py
  model_feedback.py             inspección OCC + screenshots
  self_correcting_agent.py      generate -> inspect -> critique -> retry
  freecad_rpc_server.py
  freecad_rpc_client.py

generators/
  primitives.py
  advanced_primitives.py

domains/
  shaft/
  frame_structure/
  custom/

ui/panel.py
```

## Seguridad y trazabilidad

- Los planes se validan antes de ejecutar.
- Los supuestos y datos faltantes se conservan en el `design_request`/plan.
- Las operaciones se registran en logs.
- Los reintentos eliminan los objetos creados por el intento descartado.
- El RPC escucha en localhost por defecto.
- El modo normal no ejecuta Python arbitrario producido por la IA.

## Limitaciones

- Una sola foto no revela dimensiones o geometría oculta.
- El feedback visual puede equivocarse: siempre revisar antes de fabricar.
- `loft`, `sweep`, filetes y booleanas complejas pueden fallar para geometrías
degeneradas de OpenCASCADE.
- Los engranajes universales usan dientes aproximados, no involuta certificada.
- Roscas pueden representarse de forma simplificada.
- No se garantizan tolerancias, GD&T, material ni manufacturabilidad.

## Estado

**v0.7 experimental / research prototype.**

La meta es evolucionar desde un generador de CAD hacia un agente CAD que pueda
observar el resultado de FreeCAD, detectar problemas y corregir su estrategia de
modelado de forma iterativa y trazable.
