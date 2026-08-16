# core/self_correcting_agent.py
"""Bucle generar -> inspeccionar -> criticar -> corregir para FreeCAD."""

from __future__ import annotations

import copy

import FreeCAD as App

from ai.model_critic import criticar_con_referencia, criticar_sin_referencia
from core.executor_advanced import AdvancedFeatureExecutor
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
        f"Este es el intento de correccion numero {attempt}. El intento anterior fue revisado.\n"
        f"Problemas detectados: {problems}.\n"
        f"Instrucciones de correccion: {instructions}.\n"
        "Conserva lo que estaba bien. Corrige solo los errores estructurales y de proporcion. "
        "Prefiere una geometria simple y robusta antes que detalles fragiles."
    )


def _execute_result(resultado):
    executor = AdvancedFeatureExecutor(resultado["feature_plan"])
    execution = executor.execute_all()
    final_object = executor.get_final_object()
    return executor, execution, final_object


def generar_autocorregido_desde_imagen(image_path, prompt_usuario="", max_attempts=MAX_ATTEMPTS_DEFAULT):
    """Reconstruccion desde imagen con feedback visual automatico."""
    original_prompt = prompt_usuario or (
        "Recrea esta pieza mecanica de forma aproximada en FreeCAD. "
        "No busques una copia exacta. Usa geometria CAD editable, limpia y trazable."
    )
    retry_prompt = original_prompt
    history = []
    before_all = _snapshot_names()

    for attempt in range(1, int(max_attempts) + 1):
        before_attempt = _snapshot_names()
        resultado = reconstruir_imagen_aproximada(image_path, retry_prompt)
        executor, execution, final_object = _execute_result(resultado)
        inspection = inspect_object(final_object)
        screenshots = capture_object_views(final_object, prefix=f"attempt_{attempt}")

        if _execution_has_error(execution) or not inspection.get("valid"):
            critic = {
                "decision": "regenerate",
                "score": 0.0,
                "summary": "FreeCAD detecto un error geometrico o de ejecucion.",
                "problems": inspection.get("errors", []) + [
                    r.get("message", "error") for r in execution if r.get("status") == "error"
                ],
                "correction_instructions": "Simplifica la estrategia CAD y evita la operacion que fallo.",
            }
        elif screenshots:
            critic = criticar_con_referencia(
                reference_image=image_path,
                generated_images=screenshots,
                prompt_usuario=retry_prompt,
                inspection=inspection,
                feature_plan=resultado["feature_plan"],
            )
        else:
            critic = criticar_sin_referencia(
                prompt_usuario=retry_prompt,
                inspection=inspection,
                feature_plan=resultado["feature_plan"],
                execution=execution,
            )

        item = {
            "attempt": attempt,
            "prompt": retry_prompt,
            "inspection": inspection,
            "critic": critic,
            "execution": execution,
            "screenshots": screenshots,
        }
        history.append(item)

        registrar_evento({
            "stage": "self_correction",
            "attempt": attempt,
            "decision": critic.get("decision"),
            "score": critic.get("score"),
            "problems": critic.get("problems", []),
        })

        if critic.get("decision") == "accept" or attempt >= int(max_attempts):
            resultado["self_correction"] = {
                "attempts": attempt,
                "accepted": critic.get("decision") == "accept",
                "critic": critic,
                "history": history,
            }
            resultado["execution"] = execution
            resultado["final_object"] = final_object
            resultado["executor"] = executor
            return resultado

        _remove_new_objects(before_attempt)
        retry_prompt = _compose_retry_prompt(original_prompt, critic, attempt + 1)

    _remove_new_objects(before_all)
    raise RuntimeError("No se pudo completar la reconstruccion autocorregida.")


def generar_autocorregido_desde_texto(prompt_usuario, max_attempts=MAX_ATTEMPTS_DEFAULT):
    """Generacion por texto con validacion geometrica y reintentos."""
    original_prompt = prompt_usuario.strip()
    retry_prompt = original_prompt
    history = []

    for attempt in range(1, int(max_attempts) + 1):
        before_attempt = _snapshot_names()
        resultado = prompt_a_resultado_universal(retry_prompt)
        executor, execution, final_object = _execute_result(resultado)
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

        history.append({
            "attempt": attempt,
            "prompt": retry_prompt,
            "inspection": inspection,
            "critic": copy.deepcopy(critic),
            "execution": execution,
        })

        if critic.get("decision") == "accept" or attempt >= int(max_attempts):
            resultado["self_correction"] = {
                "attempts": attempt,
                "accepted": critic.get("decision") == "accept",
                "critic": critic,
                "history": history,
            }
            resultado["execution"] = execution
            resultado["final_object"] = final_object
            resultado["executor"] = executor
            return resultado

        _remove_new_objects(before_attempt)
        retry_prompt = _compose_retry_prompt(original_prompt, critic, attempt + 1)

    raise RuntimeError("No se pudo completar la generacion autocorregida.")
