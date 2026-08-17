# ai/json_repair.py
"""Saneo tolerante de JSON generado por modelos locales.

No intenta reinterpretar el diseño CAD. Solo corrige errores sintacticos comunes:
- fences ```json
- texto antes/despues del objeto
- comas finales
- claves sin comillas simples
- comas omitidas entre propiedades/elementos

Si no puede repararlo, entrega un error con contexto util para depuracion.
"""

from __future__ import annotations

import json
import re


_SMART_QUOTES = {
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
}


def _strip_fences(texto):
    texto = texto.strip().lstrip("\ufeff")
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def _replace_smart_quotes(texto):
    for old, new in _SMART_QUOTES.items():
        texto = texto.replace(old, new)
    return texto


def _extract_balanced_json(texto):
    """Extrae el primer objeto/array balanceado respetando strings JSON."""
    starts = [(texto.find("{"), "{"), (texto.find("["), "[")]
    starts = [(i, ch) for i, ch in starts if i >= 0]
    if not starts:
        return None

    start, opener = min(starts, key=lambda x: x[0])
    closer = "}" if opener == "{" else "]"
    stack = []
    in_string = False
    escaped = False

    pairs = {"{": "}", "[": "]"}

    for i in range(start, len(texto)):
        ch = texto[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch in "{[":
            stack.append(pairs[ch])
        elif ch in "}]":
            if not stack:
                continue
            expected = stack.pop()
            if ch != expected:
                # Estructura cruzada: dejamos que json.loads entregue el detalle.
                return texto[start:i + 1]
            if not stack:
                return texto[start:i + 1]

    # Si quedo truncado, usar hasta el ultimo cierre disponible para mejorar el error.
    last = max(texto.rfind("}"), texto.rfind("]"))
    if last >= start:
        return texto[start:last + 1]
    return texto[start:]


def _remove_trailing_commas(texto):
    # Repetir por estructuras anidadas con espacios/saltos de linea.
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = re.sub(r",\s*([}\]])", r"\1", texto)
    return texto


def _quote_simple_unquoted_keys(texto):
    """Corrige {foo: 1} -> {"foo": 1}; no toca claves complejas."""
    return re.sub(
        r'([\{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)',
        r'\1"\2"\3',
        texto,
    )


def _prev_nonspace(texto, pos):
    i = pos - 1
    while i >= 0 and texto[i].isspace():
        i -= 1
    return i, (texto[i] if i >= 0 else "")


def _looks_like_new_json_value(texto, pos):
    if pos < 0 or pos >= len(texto):
        return False
    ch = texto[pos]
    if ch in '"{[':
        return True
    if ch == "-" or ch.isdigit():
        return True
    return texto.startswith("true", pos) or texto.startswith("false", pos) or texto.startswith("null", pos)


def _repair_missing_commas(texto, max_fixes=32):
    """Usa la posicion exacta del JSONDecodeError para insertar comas omitidas."""
    current = texto

    for _ in range(max_fixes):
        try:
            return json.loads(current), current
        except json.JSONDecodeError as exc:
            if "Expecting ',' delimiter" not in exc.msg:
                raise

            pos = exc.pos
            # json normalmente apunta al comienzo del siguiente key/value.
            while pos < len(current) and current[pos].isspace():
                pos += 1

            prev_i, prev = _prev_nonspace(current, pos)
            if prev_i < 0:
                raise

            can_end_value = prev in ('"', '}', ']') or prev.isdigit() or prev in ("e", "l")
            if not can_end_value or not _looks_like_new_json_value(current, pos):
                raise

            current = current[:pos] + "," + current[pos:]

    raise json.JSONDecodeError("Demasiadas reparaciones de comas", current, 0)


def _error_context(texto, exc, radius=180):
    pos = getattr(exc, "pos", None)
    if pos is None:
        return texto[:360]
    ini = max(0, int(pos) - radius)
    fin = min(len(texto), int(pos) + radius)
    fragmento = texto[ini:fin]
    pointer = " " * (int(pos) - ini) + "^"
    return fragmento + "\n" + pointer


def limpiar_json_respuesta(texto):
    """Devuelve dict/list desde una respuesta potencialmente sucia de la IA."""
    if texto is None:
        raise ValueError("Respuesta vacia: no hay texto para parsear.")

    texto = _replace_smart_quotes(_strip_fences(str(texto)))

    # Camino rapido: salida estructurada correcta.
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    candidate = _extract_balanced_json(texto)
    if not candidate:
        raise ValueError(
            "No se encontro ningun objeto/array JSON en la respuesta de la IA.\n"
            f"Inicio de respuesta:\n{texto[:700]}"
        )

    variants = []
    variants.append(candidate)
    variants.append(_remove_trailing_commas(candidate))
    variants.append(_quote_simple_unquoted_keys(_remove_trailing_commas(candidate)))

    last_exc = None
    for variant in variants:
        try:
            return json.loads(variant)
        except json.JSONDecodeError as exc:
            last_exc = exc
            try:
                parsed, _ = _repair_missing_commas(variant)
                return parsed
            except json.JSONDecodeError as repair_exc:
                last_exc = repair_exc

    contexto = _error_context(candidate, last_exc) if last_exc else candidate[:500]
    raise ValueError(
        "La IA devolvio JSON malformado y no pudo repararse automaticamente.\n"
        f"Detalle: {last_exc}\n\nContexto cerca del error:\n{contexto}"
    )
