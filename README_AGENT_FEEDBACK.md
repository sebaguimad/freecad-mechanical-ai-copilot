# Agent Mode - feedback visual y autocorreccion

Esta version agrega un bucle de agente CAD:

```text
referencia / prompt
  -> plan CAD
  -> FreeCAD ejecuta
  -> inspeccion OpenCASCADE
  -> capturas iso/frontal/lateral
  -> modelo de vision compara referencia vs resultado
  -> accept | regenerate
  -> nuevo intento con instrucciones de correccion
```

## Dos modos nuevos

### AGENTE: texto + autocorreccion

Genera desde texto, inspecciona el resultado geometrico y reintenta cuando hay:

- error de ejecucion;
- shape invalido;
- volumen nulo;
- ausencia de solidos;
- cuerpos desconectados sospechosos;
- dimensiones/estrategia incoherentes detectadas por el revisor.

### AGENTE: imagen + feedback visual

1. Interpreta la foto/plano original.
2. Construye el modelo en FreeCAD.
3. Captura vistas isometrica, frontal y lateral.
4. Qwen Vision recibe primero la referencia y luego las vistas generadas.
5. Evalua silueta, topologia, agujeros, simetrias, patrones y proporciones.
6. Si detecta errores estructurales, genera instrucciones de correccion y repite.
7. Maximo por defecto: 3 intentos.

El sistema no intenta igualar color, textura, iluminacion ni detalles cosmeticos.

## Archivos principales

- `core/model_feedback.py`: inspeccion geometrica + screenshots.
- `ai/model_critic.py`: revisor IA visual/geometrico.
- `core/self_correcting_agent.py`: bucle de reintentos.
- `ai/ollama_client.py`: ahora soporta varias imagenes en una misma llamada de vision.
- `ui/panel.py`: botones de Agent Mode.

## Uso recomendado

Para una imagen/plano:

> Recrea esta pieza mecanica aproximadamente. Prioriza las cotas visibles. Conserva la topologia, simetrias y patrones principales. Si faltan dimensiones, asume valores razonables y declaralos. Prefiere geometria robusta antes que detalles fragiles.

Luego usa **AGENTE: imagen + feedback visual**.

## Limitaciones

- Una sola foto no revela geometria oculta.
- El revisor visual puede equivocarse; el resultado debe revisarse antes de fabricar.
- `sweep`, `loft`, filetes y booleanas complejas dependen de OpenCASCADE y pueden fallar para perfiles degenerados.
- La autocorreccion busca una recreacion aproximada coherente; no certifica tolerancias ni exactitud metrologica.
