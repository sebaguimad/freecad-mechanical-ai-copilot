# core/domain_router.py
"""
Router de dominios (corregido).

Antes importaba domains.shaft y domains.plate que no existían y rompía
en runtime. Ahora:
  - solo rutea a dominios implementados: shaft, frame_structure, custom
  - cualquier familia desconocida cae a custom (el dominio universal)
  - devuelve un resultado uniforme: feature_plan + summary + reporte
"""

from core.logger import registrar_evento


DOMINIOS_SOPORTADOS = ("shaft", "frame_structure", "custom")


def normalizar_design_request(design_request):
    if not isinstance(design_request, dict):
        raise ValueError("design_request debe ser un diccionario.")

    spec = design_request.get("spec", {})

    if not isinstance(spec, dict):
        raise ValueError("design_request['spec'] debe ser un diccionario.")

    try:
        confidence = float(design_request.get("confidence", 0.0))
    except Exception:
        confidence = 0.0

    return {
        "family": design_request.get("family", "custom"),
        "intent": design_request.get("intent", ""),
        "confidence": confidence,
        "units": design_request.get("units", "mm"),
        "spec": spec,
        "missing_data": design_request.get("missing_data", []),
        "assumptions": design_request.get("assumptions", []),
        "source_image": design_request.get("source_image")
    }


def route_domain(design_request):
    family = design_request.get("family", "custom")
    if family not in DOMINIOS_SOPORTADOS:
        return "custom"
    return family


def _cargar_dominio(domain):
    if domain == "shaft":
        from domains.shaft.validator import validate
        from domains.shaft.planner import build_plan
        from domains.shaft.summary import build_summary
    elif domain == "frame_structure":
        from domains.frame_structure.validator import validate
        from domains.frame_structure.planner import build_plan
        from domains.frame_structure.summary import build_summary
    else:
        from domains.custom.validator import validate
        from domains.custom.planner import build_plan
        from domains.custom.summary import build_summary

    return validate, build_plan, build_summary


def process_design_request(design_request, prompt_usuario=""):
    """
    design_request → dominio → validar → plan → resumen.

    Devuelve:
    {
      "domain", "feature_plan", "summary",
      "corrected_spec", "validation_report", "design_request"
    }

    Lanza ValueError con mensaje legible si la validación termina en error.
    """
    req = normalizar_design_request(design_request)
    domain = route_domain(req)

    validate, build_plan, build_summary = _cargar_dominio(domain)

    corrected_spec, reporte = validate(
        req["spec"],
        prompt=prompt_usuario,
        design_request=req
    )

    registrar_evento({
        "stage": "validation",
        "domain": domain,
        "status": reporte.get("status"),
        "errors": reporte.get("errors", []),
        "warnings": reporte.get("warnings", []),
        "corrections": reporte.get("corrections", [])
    })

    if reporte.get("status") == "error":
        detalles = "\n".join(f"- {e}" for e in reporte.get("errors", []))
        raise ValueError(
            f"La validación del dominio '{domain}' encontró errores:\n{detalles}"
        )

    feature_plan = build_plan(
        corrected_spec,
        design_request=req,
        validation_report=reporte
    )

    summary = build_summary(corrected_spec, feature_plan, reporte, design_request=req)

    registrar_evento({
        "stage": "planning",
        "domain": domain,
        "features": len(feature_plan.get("feature_tree", [])),
        "status": "ok"
    })

    return {
        "domain": domain,
        "feature_plan": feature_plan,
        "summary": summary,
        "corrected_spec": corrected_spec,
        "validation_report": reporte,
        "design_request": req
    }
