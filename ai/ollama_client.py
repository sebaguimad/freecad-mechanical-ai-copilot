# ai/ollama_client.py
"""Cliente unificado para Ollama (texto, vision y comparacion multi-imagen)."""

import base64
import json
import urllib.request
import urllib.error

from ai.model_config import OLLAMA_URL, TEXT_MODEL, VISION_MODEL, TEXT_TIMEOUT, VISION_TIMEOUT
from ai.json_repair import limpiar_json_respuesta


def _post_ollama(payload, timeout, model_hint):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Error HTTP llamando a Ollama (modelo {model_hint}). Codigo: {e.code}.\nDetalle:\n{detail}"
        )
    except urllib.error.URLError as e:
        raise RuntimeError(
            "No se pudo conectar con Ollama.\n\n"
            "Verifica que Ollama este instalado y ejecutandose.\n"
            f"Prueba en una terminal:\n  ollama run {model_hint}\n\n"
            f"Detalle:\n{str(e)}"
        )

    if "error" in data:
        raise RuntimeError(f"Ollama respondio con error:\n{data['error']}")

    respuesta = data.get("response", "").strip()
    if not respuesta:
        raise RuntimeError(
            "Ollama no devolvio contenido en el campo response.\n"
            f"Respuesta completa:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        )
    return respuesta


def generar_json(system_prompt, user_prompt, schema, model=None,
                 temperature=0.1, timeout=None):
    model = (model or TEXT_MODEL).strip()
    timeout = timeout or TEXT_TIMEOUT
    prompt = (
        f"{system_prompt.strip()}\n\n"
        f"Instruccion del usuario:\n{user_prompt.strip()}\n\n"
        "Devuelve SOLO JSON valido."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": temperature, "top_p": 0.9},
    }
    respuesta = _post_ollama(payload, timeout=timeout, model_hint=model)
    return limpiar_json_respuesta(respuesta)


def _encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generar_json_desde_imagen(system_prompt, image_path, user_prompt="",
                              schema=None, model=None, temperature=0.1,
                              timeout=None):
    return generar_json_desde_imagenes(
        system_prompt=system_prompt,
        image_paths=[image_path],
        user_prompt=user_prompt,
        schema=schema,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )


def generar_json_desde_imagenes(system_prompt, image_paths, user_prompt="",
                                schema=None, model=None, temperature=0.1,
                                timeout=None):
    """Vision con una o varias imagenes en orden conocido por el prompt."""
    model = (model or VISION_MODEL).strip()
    timeout = timeout or VISION_TIMEOUT

    image_paths = [p for p in (image_paths or []) if p]
    if not image_paths:
        raise ValueError("image_paths debe contener al menos una imagen.")

    images_b64 = [_encode_image(path) for path in image_paths]
    prompt = (
        f"{system_prompt.strip()}\n\n"
        f"Instruccion adicional del usuario:\n{user_prompt.strip()}\n\n"
        "Devuelve SOLO JSON valido."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "images": images_b64,
        "options": {"temperature": temperature, "top_p": 0.9},
    }
    if schema is not None:
        payload["format"] = schema

    respuesta = _post_ollama(payload, timeout=timeout, model_hint=model)
    return limpiar_json_respuesta(respuesta)
