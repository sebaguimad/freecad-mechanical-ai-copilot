# core/domain_router.py

def normalizar_design_request(design_request):
    if not isinstance(design_request, dict):
        raise ValueError("design_request debe ser un diccionario.")

    family = design_request.get("family", "custom")
    intent = design_request.get("intent", "")
    units = design_request.get("units", "mm")
    confidence = float(design_request.get("confidence", 0.0))
    spec = design_request.get("spec", {})

    if not isinstance(spec, dict):
        raise ValueError("design_request['spec'] debe ser un diccionario.")

    return {
        "family": family,
        "intent": intent,
        "confidence": confidence,
        "units": units,
        "spec": spec,
        "missing_data": design_request.get("missing_data", []),
        "assumptions": design_request.get("assumptions", []),
        "source_image": design_request.get("source_image")
    }


def route_domain(design_request):
    family = design_request.get("family", "custom")

    supported = {
        "shaft",
        "plate",
        "custom",
        "frame_structure"
    }

    if family not in supported:
        return "custom"

    return family


def process_design_request(design_request, prompt_usuario=""):
    req = normalizar_design_request(design_request)
    domain = route_domain(req)

    if domain == "shaft":
        from domains.shaft.validator import validate
        from domains.shaft.planner import build_plan
        from domains.shaft.summary import build_summary

    elif domain == "plate":
        from domains.plate.validator import validate
        from domains.plate.planner import build_plan
        from domains.plate.summary import build_summary

    elif domain == "frame_structure":
        from domains.frame_structure.validator import validate
        from domains.frame_structure.planner import build_plan
        from domains.frame_structure.summary import build_summary

    else:
        from domains.custom.validator import validate
        from domains.custom.planner import build_plan
        from domains.custom.summary import build_summary

    corrected_spec, validation_report = validate(
        spec=req["spec"],
        prompt=prompt_usuario,
        design_request=req
    )

    feature_plan = build_plan(
        corrected_spec=corrected_spec,
        design_request=req,
        validation_report=validation_report
    )

    summary_text = build_summary(
        corrected_spec=corrected_spec,
        feature_plan=feature_plan,
        validation_report=validation_report,
        design_request=req
    )

    return {
        "domain": domain,
        "design_request": req,
        "corrected_spec": corrected_spec,
        "validation_report": validation_report,
        "feature_plan": feature_plan,
        "summary_text": summary_text
    }