# core/universal_image_to_cad.py
"""
Pipeline universal de imagen -> CAD aproximado.

Este módulo conecta el parser de visión aproximada con el router estándar:

  imagen
    -> ai.approx_mechanical_vision_parser.imagen_a_design_request_aproximado
    -> core.domain_router.process_design_request
    -> feature_plan trazable
    -> core.executor.FeatureExecutor

No promete copia exacta. Promete recreación paramétrica aproximada con supuestos.
"""

from ai.approx_mechanical_vision_parser import imagen_a_design_request_aproximado
from core.domain_router import process_design_request
from core.logger import registrar_evento


DEFAULT_APPROX_PROMPT = """
Recrea esta pieza mecánica de forma aproximada en FreeCAD. No busques una copia
exacta. Usa primitivas CAD editables y asume dimensiones razonables si no hay
cotas. Mantén la geometría limpia, paramétrica y trazable.
""".strip()


def reconstruir_imagen_aproximada(image_path, prompt_usuario=""):
    """
    Punto de entrada recomendado para imagen -> modelo CAD aproximado.

    Retorna el mismo tipo de resultado que core.universal_parser:
    {
      "domain", "feature_plan", "summary", "corrected_spec",
      "validation_report", "design_request", "classification"
    }
    """
    prompt = prompt_usuario.strip() or DEFAULT_APPROX_PROMPT

    design_request = imagen_a_design_request_aproximado(
        image_path=image_path,
        prompt_usuario=prompt
    )

    registrar_evento({
        "stage": "image_classification",
        "family": design_request.get("family"),
        "confidence": design_request.get("confidence"),
        "source_image": image_path,
        "intent": design_request.get("intent")
    })

    resultado = process_design_request(design_request, prompt)

    resultado["classification"] = {
        "family": design_request.get("family", "custom"),
        "confidence": float(design_request.get("confidence", 0.0)),
        "motivo": "clasificación desde imagen para recreación CAD aproximada"
    }

    return resultado


def imagen_a_feature_plan_aproximado(image_path, prompt_usuario=""):
    """
    Compatibilidad: devuelve solo el feature_plan.
    """
    return reconstruir_imagen_aproximada(image_path, prompt_usuario)["feature_plan"]
