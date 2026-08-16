import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.feature_plan_patch import (
    apply_feature_patches,
    validate_feature_plan_references,
    FeaturePlanPatchError,
)


def _plan():
    return {
        "family": "custom",
        "plan_version": 1,
        "final_feature_id": "feat_hole",
        "feature_tree": [
            {
                "id": "feat_base", "type": "solid_add", "name": "base",
                "shape": {"kind": "box", "length": 100, "width": 60,
                          "height": 10, "position": [0, 0, 0]},
            },
            {
                "id": "feat_hole", "type": "solid_cut", "name": "hole",
                "shape": {"kind": "cylinder", "diameter": 10, "height": 14,
                          "position": [50, 30, -2], "axis": "Z"},
            },
        ],
    }


def test_update_feature_nested_shape():
    plan, report = apply_feature_patches(_plan(), [{
        "action": "update_feature",
        "target_feature_id": "feat_hole",
        "changes": {"shape": {"diameter": 14, "position": [40, 30, -2]}},
        "reason": "Corregir diametro y posicion",
    }])
    hole = plan["feature_tree"][1]
    assert hole["shape"]["diameter"] == 14
    assert hole["shape"]["height"] == 14
    assert hole["shape"]["position"] == [40, 30, -2]
    assert report["affected_index"] == 1
    assert plan["plan_version"] == 2
    assert len(plan["patch_history"]) == 1


def test_insert_feature_after_target():
    plan, report = apply_feature_patches(_plan(), [{
        "action": "insert_feature",
        "target_feature_id": "feat_base",
        "position": "after",
        "feature": {
            "id": "feat_boss", "type": "solid_add", "name": "boss",
            "shape": {"kind": "cylinder", "diameter": 30, "height": 20,
                      "position": [50, 30, 10], "axis": "Z"},
        },
        "reason": "Agregar saliente",
    }])
    assert [f["id"] for f in plan["feature_tree"]] == [
        "feat_base", "feat_boss", "feat_hole"
    ]
    assert report["affected_index"] == 1


def test_suppress_and_unsuppress():
    plan, _ = apply_feature_patches(_plan(), [{
        "action": "suppress_feature",
        "target_feature_id": "feat_hole",
        "reason": "Agujero no existe en referencia",
    }])
    assert plan["feature_tree"][1]["suppressed"] is True
    assert plan["final_feature_id"] == "feat_base"

    plan, _ = apply_feature_patches(plan, [{
        "action": "unsuppress_feature",
        "target_feature_id": "feat_hole",
        "reason": "Restaurar agujero",
    }])
    assert not plan["feature_tree"][1].get("suppressed", False)


def test_invalid_forward_reference_rejected():
    bad = _plan()
    bad["feature_tree"][0]["target"] = "feat_hole"
    try:
        validate_feature_plan_references(bad)
    except FeaturePlanPatchError:
        pass
    else:
        raise AssertionError("Se esperaba FeaturePlanPatchError")
