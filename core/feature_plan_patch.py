# core/feature_plan_patch.py
"""Edicion trazable del Feature Plan sin regenerar toda la pieza.

Este modulo es Python puro: no importa FreeCAD y puede probarse con pytest.
La IA nunca edita objetos OCC directamente; propone patches sobre el feature tree.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone


PATCH_ACTIONS = {
    "update_feature",
    "replace_feature",
    "insert_feature",
    "delete_feature",
    "suppress_feature",
    "unsuppress_feature",
}

REFERENCE_FIELDS = ("target", "pattern_target")


class FeaturePlanPatchError(ValueError):
    pass


def _deep_merge(base, changes):
    out = copy.deepcopy(base)
    for key, value in (changes or {}).items():
        if key == "id":
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _index_by_id(tree, feature_id):
    for i, feature in enumerate(tree):
        if feature.get("id") == feature_id:
            return i
    raise FeaturePlanPatchError(f"No existe feature '{feature_id}'.")


def _active_feature_ids(tree):
    return [f.get("id") for f in tree if f.get("id") and not f.get("suppressed", False)]


def validate_feature_plan_references(feature_plan):
    """Valida ids y dependencias principales en orden topologico simple."""
    tree = feature_plan.get("feature_tree", [])
    seen = set()
    all_ids = [f.get("id") for f in tree]

    if any(not fid for fid in all_ids):
        raise FeaturePlanPatchError("Todos los features deben tener id.")
    if len(all_ids) != len(set(all_ids)):
        raise FeaturePlanPatchError("El feature plan contiene ids duplicados.")

    suppressed = {f.get("id") for f in tree if f.get("suppressed", False)}

    for feature in tree:
        fid = feature["id"]
        if feature.get("suppressed", False):
            seen.add(fid)
            continue

        refs = []
        for key in REFERENCE_FIELDS:
            ref = feature.get(key)
            if ref:
                refs.append((key, ref))
        for ref in feature.get("inputs", []) or []:
            refs.append(("inputs", ref))

        for field, ref in refs:
            if ref not in seen:
                raise FeaturePlanPatchError(
                    f"{fid}: referencia '{ref}' en {field} no existe antes del feature."
                )
            if ref in suppressed:
                raise FeaturePlanPatchError(
                    f"{fid}: referencia '{ref}' esta suprimida."
                )
        seen.add(fid)

    return True


def _normalize_patch(patch):
    if not isinstance(patch, dict):
        raise FeaturePlanPatchError("Cada patch debe ser un objeto JSON.")
    action = str(patch.get("action", "")).strip()
    if action not in PATCH_ACTIONS:
        raise FeaturePlanPatchError(f"Accion de patch no soportada: {action!r}")
    out = copy.deepcopy(patch)
    out["action"] = action
    return out


def apply_feature_patches(feature_plan, patches, source="ai_feedback"):
    """Aplica patches y devuelve (nuevo_plan, reporte).

    El reporte incluye el indice mas temprano afectado; el executor incremental
    puede reutilizar todo el prefijo anterior a ese indice.
    """
    plan = copy.deepcopy(feature_plan or {})
    tree = plan.setdefault("feature_tree", [])
    normalized = [_normalize_patch(p) for p in (patches or [])]
    if not normalized:
        raise FeaturePlanPatchError("No se recibieron patches para aplicar.")

    old_version = int(plan.get("plan_version", 1))
    affected = len(tree)
    applied = []

    for patch in normalized:
        action = patch["action"]
        target = patch.get("target_feature_id")

        if action == "update_feature":
            idx = _index_by_id(tree, target)
            changes = patch.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise FeaturePlanPatchError(f"{target}: update_feature necesita changes.")
            tree[idx] = _deep_merge(tree[idx], changes)
            tree[idx]["id"] = target
            affected = min(affected, idx)

        elif action == "replace_feature":
            idx = _index_by_id(tree, target)
            replacement = copy.deepcopy(patch.get("feature") or {})
            if not isinstance(replacement, dict) or not replacement:
                raise FeaturePlanPatchError(f"{target}: replace_feature necesita feature.")
            replacement["id"] = target
            tree[idx] = replacement
            affected = min(affected, idx)

        elif action == "insert_feature":
            feature = copy.deepcopy(patch.get("feature") or {})
            if not isinstance(feature, dict) or not feature.get("id"):
                raise FeaturePlanPatchError("insert_feature necesita feature con id.")
            if feature["id"] in {f.get("id") for f in tree}:
                raise FeaturePlanPatchError(f"El id insertado '{feature['id']}' ya existe.")

            if target:
                target_idx = _index_by_id(tree, target)
                position = str(patch.get("position", "after")).lower()
                if position not in ("before", "after"):
                    raise FeaturePlanPatchError("position debe ser before o after.")
                idx = target_idx if position == "before" else target_idx + 1
            else:
                idx = len(tree)
            tree.insert(idx, feature)
            affected = min(affected, idx)

        elif action == "delete_feature":
            idx = _index_by_id(tree, target)
            del tree[idx]
            affected = min(affected, idx)

        elif action == "suppress_feature":
            idx = _index_by_id(tree, target)
            tree[idx]["suppressed"] = True
            affected = min(affected, idx)

        elif action == "unsuppress_feature":
            idx = _index_by_id(tree, target)
            tree[idx].pop("suppressed", None)
            affected = min(affected, idx)

        applied.append({
            "action": action,
            "target_feature_id": target,
            "reason": patch.get("reason", ""),
        })

    validate_feature_plan_references(plan)

    active_ids = _active_feature_ids(tree)
    if not active_ids:
        raise FeaturePlanPatchError("El patch dejaria el plan sin features activos.")

    if plan.get("final_feature_id") not in active_ids:
        plan["final_feature_id"] = active_ids[-1]

    new_version = old_version + 1
    plan["plan_version"] = new_version
    history = plan.setdefault("patch_history", [])
    history.append({
        "from_version": old_version,
        "to_version": new_version,
        "source": str(source),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "patches": copy.deepcopy(normalized),
    })

    return plan, {
        "status": "ok",
        "from_version": old_version,
        "to_version": new_version,
        "affected_index": 0 if affected == len(tree) and not tree else affected,
        "applied": applied,
    }
