# core/self_correcting_agent.py
"""Agente CAD: generar -> inspeccionar -> criticar -> PATCH -> reconstruir sufijo."""

from __future__ import annotations

import copy

import FreeCAD as App

from ai.model_critic import criticar_con_referencia, criticar_sin_referencia
from ai.feature_patch_critic import proponer_patches
from core.executor_advanced import AdvancedFeatureExecutor
from core.feature_plan_patch import apply_feature_patches, FeaturePlanPatchError
from core.model_feedback import inspect_object, capture_object_views
from core.universal_parser import prompt_a_resultado_universal
from core.universal_image_to_cad import reconstruir_imagen_aproximada
from core.logger import registrar_evento


MAX_ATTEMPTS_DEFAULT = 3


def _snapshot_names():
    doc = App.ActiveDocument
    if doc is None:
        return set()
    return {o.Name for o in doc.Objects}


def _remove_new_objects(before_names):
    doc = App.ActiveDocument
    if doc is None:
        return
    for obj in list(doc.Objects):
        if obj.Name not in before_names:
            try:
                doc.removeObject(obj.Name)
            except Exception:
                pass
    doc.recompute()


def _execution_has_error(results):
    return any(r.get("status") == "error" for r in (results or []))


def _compose_retry_prompt(original_prompt, critic, attempt):
    problems = critic.get("problems", [])
    instructions = critic.get("correction_instructions", "")
    return (
        f"{original_prompt.strip()}\n\n"
        f"Intento de correccion {attempt}. El modelo anterior fue revisado.\n"
        f"Problemas detectados: {problems}.\n"
        f"Instrucciones: {instructions}.\n"
        "Conserva lo correcto y corrige los errores estructurales/proporcionales. "
        "Prefiere geometria CAD robusta."
    )


def _execute_result(resultado):
    executor = AdvancedFeatureExecutor(resultado["feature_plan"])
    execution = executor.execute_all()
    final_object = executor.get_final_object()
    return executor, execution, final_object


def _build_failure_critic(execution, inspection):
    return {
        "decision": "regenerate",
        "score": 0.0,
        "summary": "FreeCAD detecto un error geometrico o de ejecucion.",
        "problems": inspection.get("errors", []) + [
            r.get("message", "error") for r in execution if r.get("status") == "error"
        ],
        "correction_instructions": (
            "Corrige la operacion responsable. Si es posible conserva el resto del feature plan."
        ),
    }


def _try_incremental_patch(resultado, executor, critic, inspection, prompt_usuario):
    """Intenta corregir el plan actual sin borrar el prefijo ya construido."""
    plan = resultado.get("feature_plan") or {}
    if plan.get("family", plan.get("domain")) != "custom":
        return None

    proposal = proponer_patches(
        feature_plan=plan,
        critic=critic,
        inspection=inspection,
        prompt_usuario=prompt_usuario,
    )
    if proposal.get("strategy") != "patch" or not proposal.get("patches"):
        return None

    try:
        new_plan, patch_report = apply_feature_patches(
            plan,
            proposal["patches"],
            source="self_correcting_agent",
        )
        execution = executor.rebuild_from_index(
            new_plan,
            patch_report["affected_index"],
        )
    except (FeaturePlanPatchError, ValueError, KeyError) as exc:
        registrar_evento({
            "stage": "incremental_patch",
            "status": "fallback",
            "error": str(exc),
            "proposal": proposal,
        })
        return None

    resultado = dict(resultado)
    resultado["feature_plan"] = new_plan
    resultado["execution"] = execution
    resultado["executor"] = executor
    resultado["final_object"] = executor.get_final_object()
    resultado["last_patch"] = {
        "proposal": proposal,
        "report": patch_report,
    }

    registrar_evento({
        "stage": "incremental_patch",
        "status": "ok",
        "plan_version": new_plan.get("plan_version"),
        "affected_index": patch_report.get("affected_index"),
        "patches": proposal.get("patches", []),
    })
    return resultado


def _critic_for_image(image_path, prompt, resultado, execution, final_object, attempt):
    inspection = inspect_object(final_object)
    screenshots = capture_object_views(final_object, prefix=f"attempt_{attempt}")

    if _execution_has_error(execution) or not inspection.get("valid"):
        critic = _build_failure_critic(execution, inspection)
    elif screenshots:
        critic = criticar_con_referencia(
            reference_image=image_path,
            generated_images=screenshots,
            prompt_usuario=prompt,
            inspection=inspection,
            feature_plan=resultado["feature_plan"],
        )
    else:
        critic = criticar_sin_referencia(
            prompt_usuario=prompt,
            inspection=inspection,
            feature_plan=resultado["feature_plan"],
            execution=execution,
        )
    return critic, inspection, screenshots


def generar_autocorregido_desde_imagen(image_path, prompt_usuario="", max_attempts=MAX_ATTEMPTS_DEFAULT):
    """Imagen -> CAD con patches puntuales y regeneracion completa como fallback."""
    original_prompt = prompt_usuario or (
        "Recrea esta pieza mecanica aproximadamente en FreeCAD. "
        "Usa geometria CAD editable, limpia y trazable."
    )
    retry_prompt = original_prompt
    history = []
    before_all = _snapshot_names()

    # Primer modelo completo.
    resultado = reconstruir_imagen_aproximada(image_path, retry_prompt)
    executor, execution, final_object = _execute_result(resultado)

    for attempt in range(1, int(max_attempts) + 1):
        critic, inspection, screenshots = _critic_for_image(
            image_path, retry_prompt, resultado, execution, final_object, attempt
        )

        history_item = {
            "attempt": attempt,
            "prompt": retry_prompt,
            "plan_version": resultado["feature_plan"].get("plan_version", 1),
            "inspection": inspection,
            "critic": copy.deepcopy(critic),
            "execution": execution,
            "screenshots": screenshots,
            "correction_mode": "none",
        }

        if critic.get("decision") == "accept" or attempt >= int(max_attempts):
            history.append(history_item)
            resultado["self_correction"] = {
                "attempts": attempt,
                "accepted": critic.get("decision") == "accept",
                "critic": critic,
                "history": history,
                "plan_version": resultado["feature_plan"].get("plan_version", 1),
                "patch_history": resultado["feature_plan"].get("patch_history", []),
            }
            resultado["execution"] = execution
            resultado["final_object"] = final_object
            resultado["executor"] = executor
            return resultado

        # Primero intentar PATCH puntual.
        patched = _try_incremental_patch(
            resultado, executor, critic, inspection, retry_prompt
        )
        if patched is not None:
            history_item["correction_mode"] = "incremental_patch"
            history_item["patch"] = patched.get("last_patch")
            history.append(history_item)
            resultado = patched
            execution = patched["execution"]
            executor = patched["executor"]
            final_object = patched["final_object"]
            retry_prompt = original_prompt
            continue

        # Fallback: solo cuando el plan no puede parchearse de forma segura.
        history_item["correction_mode"] = "full_regeneration_fallback"
        history.append(history_item)
        _remove_new_objects(before_all)
        retry_prompt = _compose_retry_prompt(original_prompt, critic, attempt + 1)
        resultado = reconstruir_imagen_aproximada(image_path, retry_prompt)
        executor, execution, final_object = _execute_result(resultado)

    raise RuntimeError("No se pudo completar la reconstruccion autocorregida.")


def generar_autocorregido_desde_texto(prompt_usuario, max_attempts=MAX_ATTEMPTS_DEFAULT):
    """Texto -> CAD con patch incremental y fallback de regeneracion."""
    original_prompt = prompt_usuario.strip()
    if not original_prompt:
        raise ValueError("prompt_usuario no puede estar vacio.")

    retry_prompt = original_prompt
    history = []
    before_all = _snapshot_names()
    resultado = prompt_a_resultado_universal(retry_prompt)
    executor, execution, final_object = _execute_result(resultado)

    for attempt in range(1, int(max_attempts) + 1):
        inspection = inspect_object(final_object)
        critic = criticar_sin_referencia(
            prompt_usuario=retry_prompt,
            inspection=inspection,
            feature_plan=resultado["feature_plan"],
            execution=execution,
        )
        if _execution_has_error(execution) or not inspection.get("valid"):
            critic["decision"] = "regenerate"
            critic["score"] = min(float(critic.get("score", 0.0)), 0.25)

        item = {
            "attempt": attempt,
            "prompt": retry_prompt,
            "plan_version": resultado["feature_plan"].get("plan_version", 1),
            "inspection": inspection,
            "critic": copy.deepcopy(critic),
            "execution": execution,
            "correction_mode": "none",
        }

        if critic.get("decision") == "accept" or attempt >= int(max_attempts):
            history.append(item)
            resultado["self_correction"] = {
                "attempts": attempt,
                "accepted": critic.get("decision") == "accept",
                "critic": critic,
                "history": history,
                "plan_version": resultado["feature_plan"].get("plan_version", 1),
                "patch_history": resultado["feature_plan"].get("patch_history", []),
            }
            resultado["execution"] = execution
            resultado["final_object"] = final_object
            resultado["executor"] = executor
            return resultado

        patched = _try_incremental_patch(
            resultado, executor, critic, inspection, retry_prompt
        )
        if patched is not None:
            item["correction_mode"] = "incremental_patch"
            item["patch"] = patched.get("last_patch")
            history.append(item)
            resultado = patched
            execution = patched["execution"]
            executor = patched["executor"]
            final_object = patched["final_object"]
            retry_prompt = original_prompt
            continue

        item["correction_mode"] = "full_regeneration_fallback"
        history.append(item)
        _remove_new_objects(before_all)
        retry_prompt = _compose_retry_prompt(original_prompt, critic, attempt + 1)
        resultado = prompt_a_resultado_universal(retry_prompt)
        executor, execution, final_object = _execute_result(resultado)

    raise RuntimeError("No se pudo completar la generacion autocorregida.")
