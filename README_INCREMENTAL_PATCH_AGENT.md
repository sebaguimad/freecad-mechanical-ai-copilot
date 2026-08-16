# v0.8 — Incremental Feature Patch Agent

El agente ya no necesita regenerar toda la pieza cada vez que el revisor detecta
un problema localizado.

## Flujo

```text
referencia / prompt
  -> Feature Plan v1
  -> FreeCAD
  -> inspeccion + vistas
  -> IA revisora
  -> IA de patches
       |-> update_feature
       |-> replace_feature
       |-> insert_feature
       |-> delete_feature
       |-> suppress_feature
       |-> unsuppress_feature
  -> Feature Plan v2
  -> rebuild SOLO desde el primer feature afectado
  -> FreeCAD
  -> nueva inspeccion
```

Si el agente no puede identificar una correccion local segura, conserva el
fallback de regeneracion completa.

## Ejemplo

Plan actual:

```text
feat_base       solid_add box
feat_hole       solid_cut cylinder
feat_pattern    linear_pattern
feat_fillet     fillet_all
```

El revisor detecta que el agujero esta demasiado cerca del borde. El agente puede
proponer:

```json
{
  "strategy": "patch",
  "patches": [
    {
      "action": "update_feature",
      "target_feature_id": "feat_hole",
      "changes": {"shape": {"position": [35, 20, -2]}},
      "reason": "Mover el agujero hacia el interior"
    }
  ]
}
```

El motor conserva `feat_base`, elimina/recalcula desde `feat_hole` y vuelve a
ejecutar solamente el sufijo del plan.

## Trazabilidad

Cada plan incluye:

- `plan_version`
- `patch_history`
- patches aplicados
- razon de cada cambio
- indice del primer feature afectado

Así puede reconstruirse la evolucion:

```text
Feature Plan v1
   -> patch 1
Feature Plan v2
   -> patch 2
Feature Plan v3
```

## Seguridad

La IA no modifica OpenCASCADE directamente ni ejecuta Python arbitrario. Solo
puede proponer operaciones de patch declarativas que pasan por
`core/feature_plan_patch.py` antes de ejecutarse.

## Limitacion actual

El rebuild incremental se habilita primero para `family=custom`, que es el dominio
universal de piezas mecanicas. Para `shaft` y `frame_structure`, si el parche no
puede aplicarse de forma segura, se usa la regeneracion completa como fallback.
