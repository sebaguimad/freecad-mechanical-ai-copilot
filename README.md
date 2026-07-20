# AI Dibujante Modular — v0.5 (IA externa + RPC local)

Copiloto CAD local para FreeCAD. Genera piezas mecánicas paramétricas desde
texto o imágenes usando IA local (Ollama), con validación trazable,
correcciones automáticas registradas y exportación STEP/STL.

## Qué hay de nuevo en esta versión

### 1. Pipeline universal (texto)

Un solo botón: el sistema clasifica el pedido y lo rutea al dominio correcto.

```text
prompt → clasificador → shaft | frame_structure | custom
       → schema JSON de esa familia (Ollama, salida estructurada)
       → validador del dominio (corrige y registra)
       → planner → feature tree
       → executor unificado → geometría FreeCAD
```

### 2. Recreación aproximada desde imagen

Nuevo flujo para imágenes:

```text
imagen + prompt opcional
  → modelo de visión local
  → design_request aproximado
  → frame_structure | custom
  → validador
  → feature_plan trazable
  → executor unificado
  → modelo FreeCAD editable
```

El objetivo NO es copiar exactamente la foto ni hacer fotogrametría. El objetivo
es recrear una pieza o estructura de forma aproximada usando primitivas CAD
editables y supuestos declarados.

Prompt recomendado:

> Recrea esta pieza mecánica de forma aproximada en FreeCAD. No busques una copia exacta. Usa primitivas CAD editables y asume dimensiones razonables si no hay cotas. Mantén la geometría limpia, paramétrica y trazable.

Este modo puede elegir:

- `frame_structure`: mesas industriales, bastidores, carros, marcos soldados.
- `custom`: piezas mecánicas aproximables con cajas, cilindros, conos, prismas,
  cortes, patrones, filetes y chaflanes.

### 3. RPC local para Ollama, Claude, ChatGPT u otra IA

Además del panel interno, ahora FreeCAD puede actuar como servidor local de
herramientas CAD.

```text
Ollama / Claude / ChatGPT / agente externo
        ↓
FreeCADRPCClient
        ↓
FreeCAD RPC Server dentro de FreeCAD
        ↓
FeatureExecutor + generators/primitives.py
        ↓
Modelo FreeCAD editable
```

Esto permite un flujo parecido a un conector MCP:

- la IA razona fuera de FreeCAD;
- llama herramientas controladas;
- FreeCAD crea cajas, cilindros, agujeros, filetes, chaflanes o ejecuta un
  `feature_plan` completo;
- no se ejecuta Python arbitrario generado por IA.

Herramientas RPC iniciales:

`ping, status, get_objects, clear_document, create_box, create_cylinder, boolean_fuse, cut_cylinder_hole, add_fillet_all, add_chamfer_all, run_feature_plan, run_prompt_universal, save_document, export_step_stl`

Para iniciar el servidor desde FreeCAD:

```python
from core.freecad_rpc_server import start_rpc_server
start_rpc_server()
```

O desde el panel:

```text
5. Iniciar RPC Server (Ollama / IA externa)
```

Luego, desde PowerShell:

```powershell
python agent/ollama_freecad_agent.py "crea una brida circular Ø160, espesor 15, agujero central Ø60 y 6 agujeros M12 en círculo Ø120"
```

Más detalles en [`README_RPC_AGENT.md`](README_RPC_AGENT.md).

### 4. Dominio `custom` (el universal)

En vez de código Python libre (frágil con modelos locales de 8B), la IA devuelve
una lista ordenada de operaciones genéricas:

`box, cylinder, cone, sphere, polygon_prism, polar_pattern, fillet_all, chamfer_all`

con modo `agregar` / `cortar`. Con ese vocabulario se aproximan engranajes
simplificados, bridas, poleas, soportes, bujes, ménsulas, placas con agujeros,
adaptadores, etc. Ejemplos:

- "Genera un engranaje recto de 40 dientes, módulo 2, ancho 20, agujero Ø20 con chavetero"
- "Brida circular Ø160, espesor 15, agujero central Ø60, 6 pernos M12 en círculo Ø120"
- Imagen de una pieza mecánica + prompt de recreación aproximada.

### 5. Correcciones de bugs de la versión anterior

- **Router roto**: `domain_router` importaba `domains/shaft` y `domains/plate`
  inexistentes (ImportError en runtime). Ahora `shaft` existe como dominio
  formal y cualquier familia desconocida cae a `custom`.
- **Regex peligroso**: el validador capturaba el primer número con "mm" del
  prompt como longitud total (p.ej. "chavetero de 40 mm" redimensionaba el
  eje). Ahora la longitud total viene como campo `longitud_total` del JSON de
  la IA; el regex quedó solo como fallback con patrones explícitos.
- **Filete que reventaba**: `makeFillet` sobre TODAS las aristas fallaba en OCC
  con chaveteros/roscas. Ahora: `fillet_shoulders` y `aplicar_filete_seguro`.
- **Rosca que rellenaba chaveteros**: la rosca simplificada (cut+fuse) destruía
  un chavetero solapado. El validador recorta o elimina la rosca en conflicto,
  y el planner además ejecuta roscas antes que chaveteros.
- **Dos executors**: `FeatureExecutor` y `frame_direct_executor`. Ahora hay UN
  executor trazable para todo, con BOM integrado y transacción de documento.
- **Headless**: `FreeCADGui` se importa protegido; el pipeline corre en
  `freecadcmd`.
- **Código triplicado de Ollama**: unificado en `ai/ollama_client.py`.
- **package.xml** agregado (Addon Manager).

### 6. Tests (sin FreeCAD)

Los validadores, planners y el router son Python puro:

```powershell
pip install pytest
pytest tests/ -v
```

## Instalación

1. Copiar esta carpeta a `<UserAppData>/FreeCAD/Mod/AIDibujanteModular`
   (en Windows: `%APPDATA%/FreeCAD/Mod/AIDibujanteModular`).
2. Instalar Ollama y los modelos:
   ```powershell
   ollama pull qwen3:8b
   ollama pull qwen2.5vl:7b
   ```
3. Abrir FreeCAD → workbench "AIDibujanteModular" → Abrir asistente.

Variables de entorno opcionales:
`AI_CAD_OLLAMA_URL`, `AI_CAD_OLLAMA_MODEL`, `AI_CAD_OLLAMA_VISION_MODEL`,
`AI_CAD_RPC_URL`, `AI_CAD_RPC_PORT`.

## Uso

| Botón | Qué hace |
|---|---|
| 1. IA universal (texto) | Clasifica y genera el plan del dominio correcto |
| 1B. Parser simple | `Ø20x60, Ø30x120, Ø25x70` sin IA |
| 1C. Recrear desde imagen (aprox.) | Recreación paramétrica aproximada desde imagen |
| 2 / 3 | Ejecutar paso a paso o todo (trazable, con métricas) |
| 4 | Exportar STEP + STL a `~/AIDibujanteOutputs` |
| 5 | Iniciar RPC Server para Ollama / IA externa |

Logs JSONL de cada operación en `~/AIDibujanteLogs`.

## Filosofía Texto vs Imagen vs Agente externo

- **Texto** → diseñar desde cero o reconstruir aproximadamente por descripción.
- **Imagen** → recrear aproximadamente algo existente.
- **Agente externo** → conversación paso a paso: crear, modificar, consultar,
  exportar y guardar desde herramientas CAD controladas.

Todos convergen en el mismo motor: `design_request` / `feature_plan` → validador
→ executor → FreeCAD.

## Estructura

```text
ai/            cliente Ollama unificado, visión, saneo JSON, config modelos
agent/         agente Ollama -> FreeCAD RPC
core/          clasificador, parser universal, router, executor, logger,
               métricas, exportador, RPC server/client, pipeline imagen universal
domains/
  shaft/           eje escalonado (spec + validador + planner + summary)
  frame_structure/ estructuras de perfiles (con BOM)
  custom/          dominio universal por operaciones genéricas
generators/    primitivas geométricas (único módulo que toca Part)
ui/            panel Qt
tests/         tests de validadores, planners y router (sin FreeCAD)
```

## Limitaciones declaradas

- La reconstrucción desde imagen es aproximada; no es copia exacta ni
  fotogrametría.
- Si no hay cotas visibles, se asumen dimensiones razonables y se registran en
  `assumptions`.
- El servidor RPC es experimental y escucha solo en `127.0.0.1` por defecto.
- FreeCAD puede no ser completamente thread-safe bajo RPC; guarda antes de
  pruebas largas.
- Roscas representadas como zona rebajada (no helicoidales reales).
- Dientes de engranaje trapezoidales aproximados (no involuta exacta); para
  engranajes de precisión, futuro dominio `gear` delegando en
  `InvoluteGearFeature` de FreeCAD.
- Unidades siempre mm.

## Roadmap sugerido

1. Servidor MCP oficial encima del RPC local.
2. Dominio `gear` formal (involuta vía Part Design).
3. Dominio `plate` (placas con patrones de agujeros y cortes).
4. Mejorar visión para piezas torneadas desde foto/plano.
5. Modo macro experimental (IA genera Python, usuario aprueba) como último
   recurso, con transacción + revisión previa.
