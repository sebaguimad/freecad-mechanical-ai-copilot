# Geometria universal avanzada

La reconstruccion aproximada ahora puede elegir operaciones CAD de mayor nivel,
ademas de cajas/cilindros/conos/prismas.

## Operaciones nuevas

- `revolve`: piezas torneadas, poleas, bujes, tapas y cuerpos axisimetricos.
- `sketch_extrude`: soportes, placas, nervios y siluetas 2D.
- `sweep`: tubos curvos, manillas y conductos simples.
- `loft`: transiciones y carcasas simplificadas.
- `linear_pattern`: hileras de agujeros o elementos repetidos.
- `mirror`: simetrias respecto de XY, XZ o YZ.

Se mantienen `polar_pattern`, booleanas, filetes y chaflanes.

## Flujo

```text
foto / plano / texto
 -> Ollama (o agente compatible)
 -> design_request
 -> validator
 -> feature_plan
 -> AdvancedFeatureExecutor
 -> Part.Shape en FreeCAD
```

El parser universal instala `AdvancedFeatureExecutor` como reemplazo compatible
del executor anterior, por lo que los planes antiguos siguen siendo validos.

## Alcance

Esto amplia mucho la variedad de piezas que se pueden aproximar, pero no es
reverse engineering exacto. Una sola foto no contiene dimensiones ocultas,
tolerancias ni geometria interior. Para planos, las cotas visibles se consideran
prioritarias y los datos faltantes se registran como supuestos.

## Ejemplos

**Polea**

`Recrea una polea de dos canales de aproximadamente 140 mm de diametro y 35 mm de ancho, con agujero central de 20 mm. Usa revolucion para el perfil principal.`

**Placa perforada**

`Crea una placa 200x100x8 con una hilera de 5 agujeros de 10 mm separados 35 mm y refleja la hilera para obtener dos filas.`

**Manilla tubular**

`Recrea una manilla curva con seccion cuadrada aproximada de 15 mm mediante sweep siguiendo una trayectoria en U.`

**Desde imagen/plano**

`Recrea esta pieza mecanica aproximadamente. Prioriza cotas visibles. Detecta superficies de revolucion, simetrias y patrones antes de elegir primitivas.`
