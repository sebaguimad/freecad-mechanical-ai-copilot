# domains/frame_structure/planner.py

def build_plan(corrected_spec, design_request=None, validation_report=None):
    feature_tree = []
    current_targets = []
    counter = 1
    top = corrected_spec.get("top")
    if top and top.get("enabled"):
        top_id = "feat_frame_top_plate"
        feature_tree.append({"id": top_id, "type": "box", "name": "cubierta_superior", "length": top["length"], "width": top["width"], "height": top["thickness"], "position": top.get("position", [0,0,0])})
        current_targets.append(top_id)

    for member in corrected_spec.get("members", []):
        op_id = f"feat_frame_member_{counter:03d}"
        counter += 1
        feature_tree.append({"id": op_id, "type": "square_tube_between_points", "name": member["id"], "role": member.get("role", "unknown"), "profile": member["profile"], "start": member["start"], "end": member["end"]})
        current_targets.append(op_id)

    for plate in corrected_spec.get("plates", []):
        op_id = f"feat_frame_plate_{counter:03d}"
        counter += 1
        feature_tree.append({"id": op_id, "type": "box", "name": plate["id"], "length": plate["length"], "width": plate["width"], "height": plate["thickness"], "position": plate["position"]})
        current_targets.append(op_id)

    final_id = None
    if len(current_targets) == 1:
        final_id = current_targets[0]
    elif len(current_targets) > 1:
        final_id = "feat_frame_fuse_all"
        feature_tree.append({"id": final_id, "type": "boolean_fuse", "name": "estructura_fusionada", "inputs": current_targets})

    if corrected_spec.get("bom_enabled", True):
        feature_tree.append({"id": "feat_frame_bom", "type": "bom_report", "name": "lista_materiales", "members": corrected_spec.get("members", []), "plates": corrected_spec.get("plates", []), "top": corrected_spec.get("top")})

    return {"intent": "crear_estructura_parametrica", "family": "frame_structure", "domain": "frame_structure", "units": "mm", "final_feature_id": final_id, "feature_tree": feature_tree, "validation_report": validation_report or {}, "source_design_request": design_request or {}}
