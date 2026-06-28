# core/plan_validator.py

import copy
import re


def _extraer_longitud_total_desde_prompt(prompt):
    """
    Busca patrones como:
    - eje de 250 mm
    - longitud total 250 mm
    - 250mm
    """

    texto = prompt.lower()

    patrones = [
        r"eje\s+de\s+(\d+(?:\.\d+)?)\s*mm",
        r"longitud\s+total\s+de\s+(\d+(?:\.\d+)?)\s*mm",
        r"longitud\s+total\s+(\d+(?:\.\d+)?)\s*mm",
        r"(\d+(?:\.\d+)?)\s*mm"
    ]

    for patron in patrones:
        match = re.search(patron, texto)
        if match:
            return float(match.group(1))

    return None


def _es_chavetero_central_solicitado(prompt):
    texto = prompt.lower()
    return "chavetero" in texto and ("central" in texto or "tramo central" in texto or "medio" in texto)


def _es_rosca_derecha_solicitada(prompt):
    texto = prompt.lower()
    return "rosca" in texto and ("derecha" in texto or "extremo derecho" in texto or "lado derecho" in texto)


def _tramo_central_index(segmentos):
    if not segmentos:
        return 0
    return len(segmentos) // 2


def _sumar_longitudes(segmentos):
    return sum(float(s["longitud"]) for s in segmentos)


def _asegurar_valores_basicos(spec, reporte):
    """
    Asegura estructura mínima y valores positivos.
    """

    spec.setdefault("intent", "crear_eje_escalonado")
    spec.setdefault("units", "mm")
    spec.setdefault("segmentos", [])
    spec.setdefault("chaveteros", [])
    spec.setdefault("filetes", [])
    spec.setdefault("roscas", [])
    spec.setdefault("missing_data", [])
    spec.setdefault("assumptions", [])

    if spec["intent"] != "crear_eje_escalonado":
        reporte["errors"].append(
            f"Intent no soportado: {spec['intent']}"
        )

    if spec["units"] != "mm":
        reporte["warnings"].append(
            f"Unidades cambiadas desde {spec['units']} a mm."
        )
        spec["units"] = "mm"

    segmentos_validos = []

    for i, seg in enumerate(spec["segmentos"]):
        try:
            d = float(seg["diametro"])
            l = float(seg["longitud"])
        except Exception:
            reporte["errors"].append(
                f"Segmento {i} tiene valores no numéricos."
            )
            continue

        if d <= 0 or l <= 0:
            reporte["errors"].append(
                f"Segmento {i} tiene diámetro o longitud no positiva."
            )
            continue

        segmentos_validos.append({
            "diametro": d,
            "longitud": l
        })

    spec["segmentos"] = segmentos_validos

    if not spec["segmentos"]:
        reporte["errors"].append(
            "No existen segmentos válidos para generar el eje."
        )

    return spec


def _corregir_longitud_total(spec, prompt, reporte):
    """
    Si el prompt indica una longitud total y la suma no coincide,
    ajusta el tramo central para cerrar la longitud total.
    """

    segmentos = spec["segmentos"]

    if not segmentos:
        return spec

    longitud_objetivo = _extraer_longitud_total_desde_prompt(prompt)

    if longitud_objetivo is None:
        return spec

    suma_actual = _sumar_longitudes(segmentos)
    diferencia = longitud_objetivo - suma_actual

    if abs(diferencia) < 1e-6:
        return spec

    idx = _tramo_central_index(segmentos)

    nueva_longitud = segmentos[idx]["longitud"] + diferencia

    if nueva_longitud <= 0:
        reporte["errors"].append(
            "No se pudo corregir la longitud total porque el tramo central quedaría con longitud no positiva."
        )
        return spec

    segmentos[idx]["longitud"] = nueva_longitud

    reporte["corrections"].append({
        "type": "length_correction",
        "message": (
            f"La suma de longitudes era {suma_actual} mm y debía ser {longitud_objetivo} mm. "
            f"Se ajustó la longitud del tramo central en {diferencia} mm."
        ),
        "target_segment": idx,
        "new_length": nueva_longitud
    })

    return spec


def _corregir_chaveteros(spec, prompt, reporte):
    """
    Corrige chaveteros:
    - si el usuario pidió chavetero central, deja solo uno en el tramo central;
    - valida dimensiones;
    - centra el offset si está fuera de rango o si corresponde.
    """

    segmentos = spec["segmentos"]
    chaveteros = spec.get("chaveteros", [])

    if not segmentos:
        return spec

    if not chaveteros:
        return spec

    if _es_chavetero_central_solicitado(prompt):
        idx_central = _tramo_central_index(segmentos)

        # Mantener solo un chavetero central.
        chav = None

        for c in chaveteros:
            if int(c.get("tramo_index", -1)) == idx_central:
                chav = c
                break

        if chav is None:
            chav = chaveteros[0]

        chav["tramo_index"] = idx_central

        spec["chaveteros"] = [chav]

        if len(chaveteros) > 1:
            reporte["corrections"].append({
                "type": "duplicate_keyway_removed",
                "message": (
                    "El usuario pidió chavetero central. "
                    "Se eliminaron chaveteros adicionales y se mantuvo uno en el tramo central."
                ),
                "kept_segment": idx_central
            })

    chaveteros_corregidos = []

    for i, chav in enumerate(spec.get("chaveteros", [])):
        idx = int(chav.get("tramo_index", _tramo_central_index(segmentos)))

        if idx < 0 or idx >= len(segmentos):
            idx_original = idx
            idx = _tramo_central_index(segmentos)
            reporte["corrections"].append({
                "type": "keyway_segment_index_correction",
                "message": f"tramo_index inválido en chavetero {i}. Se movió al tramo central.",
                "old_index": idx_original,
                "new_index": idx
            })

        seg = segmentos[idx]

        ancho = float(chav.get("ancho", 8.0))
        profundidad = float(chav.get("profundidad", 3.3))
        longitud = float(chav.get("longitud", 40.0))

        # Evitar chavetero más largo que el tramo.
        if longitud > seg["longitud"]:
            old = longitud
            longitud = seg["longitud"] * 0.6
            reporte["corrections"].append({
                "type": "keyway_length_correction",
                "message": f"Longitud de chavetero reducida para caber dentro del tramo {idx}.",
                "old_length": old,
                "new_length": longitud
            })

        # Evitar profundidad excesiva.
        max_depth = seg["diametro"] * 0.35
        if profundidad > max_depth:
            old = profundidad
            profundidad = max_depth
            reporte["corrections"].append({
                "type": "keyway_depth_correction",
                "message": f"Profundidad de chavetero reducida para no exceder el diámetro del tramo {idx}.",
                "old_depth": old,
                "new_depth": profundidad
            })

        # Evitar ancho mayor que diámetro.
        max_width = seg["diametro"] * 0.8
        if ancho > max_width:
            old = ancho
            ancho = max_width
            reporte["corrections"].append({
                "type": "keyway_width_correction",
                "message": f"Ancho de chavetero reducido para ser compatible con el diámetro del tramo {idx}.",
                "old_width": old,
                "new_width": ancho
            })

        offset = chav.get("offset_desde_inicio", None)

        # Muy importante:
        # Si el prompt dice central, se centra automáticamente.
        if _es_chavetero_central_solicitado(prompt):
            offset = None

        if offset is not None:
            try:
                offset = float(offset)
            except Exception:
                offset = None

        if offset is not None:
            max_offset = seg["longitud"] - longitud

            if offset < 0 or offset > max_offset:
                old = offset
                offset = None
                reporte["corrections"].append({
                    "type": "keyway_offset_correction",
                    "message": (
                        f"Offset de chavetero fuera del tramo {idx}. "
                        "Se reemplazó por centrado automático."
                    ),
                    "old_offset": old,
                    "new_offset": None
                })

        chaveteros_corregidos.append({
            "tramo_index": idx,
            "ancho": ancho,
            "profundidad": profundidad,
            "longitud": longitud,
            "offset_desde_inicio": offset
        })

    spec["chaveteros"] = chaveteros_corregidos

    return spec


def _corregir_roscas(spec, prompt, reporte):
    """
    Corrige roscas:
    - si es rosca derecha, la mueve al último tramo;
    - si el diámetro nominal supera el diámetro del tramo, aumenta el diámetro del tramo;
    - limita la longitud de rosca para que quepa en el tramo.
    """

    segmentos = spec["segmentos"]
    roscas = spec.get("roscas", [])

    if not segmentos or not roscas:
        return spec

    roscas_corregidas = []

    for i, ros in enumerate(roscas):
        idx = int(ros.get("tramo_index", len(segmentos) - 1))

        if _es_rosca_derecha_solicitada(prompt):
            idx = len(segmentos) - 1

        if idx < 0 or idx >= len(segmentos):
            idx_original = idx
            idx = len(segmentos) - 1
            reporte["corrections"].append({
                "type": "thread_segment_index_correction",
                "message": f"tramo_index inválido en rosca {i}. Se movió al último tramo.",
                "old_index": idx_original,
                "new_index": idx
            })

        seg = segmentos[idx]

        diametro_nominal = float(ros.get("diametro_nominal", seg["diametro"]))
        longitud = float(ros.get("longitud", 20.0))
        lado = ros.get("lado", "derecho")

        # Corrección mecánica básica:
        # una rosca M20 no puede estar sobre un tramo de Ø12.
        if diametro_nominal > seg["diametro"]:
            old_d = seg["diametro"]
            seg["diametro"] = diametro_nominal

            reporte["corrections"].append({
                "type": "thread_diameter_correction",
                "message": (
                    f"La rosca M{diametro_nominal} no era compatible con el tramo Ø{old_d}. "
                    f"Se aumentó el diámetro del tramo {idx} a Ø{diametro_nominal}."
                ),
                "segment_index": idx,
                "old_segment_diameter": old_d,
                "new_segment_diameter": diametro_nominal
            })

        if longitud > seg["longitud"]:
            old_l = longitud
            longitud = seg["longitud"] * 0.5

            reporte["corrections"].append({
                "type": "thread_length_correction",
                "message": f"Longitud de rosca reducida para caber en el tramo {idx}.",
                "old_thread_length": old_l,
                "new_thread_length": longitud
            })

        roscas_corregidas.append({
            "tramo_index": idx,
            "diametro_nominal": diametro_nominal,
            "longitud": longitud,
            "lado": lado
        })

    spec["roscas"] = roscas_corregidas

    return spec


def _corregir_filetes(spec, reporte):
    segmentos = spec["segmentos"]
    filetes = spec.get("filetes", [])

    if not segmentos or not filetes:
        return spec

    d_min = min(seg["diametro"] for seg in segmentos)
    radio_max = d_min * 0.15

    filetes_corregidos = []

    for fil in filetes:
        radio = float(fil.get("radio", 1.0))

        if radio <= 0:
            radio = 1.0

        if radio > radio_max:
            old = radio
            radio = radio_max

            reporte["corrections"].append({
                "type": "fillet_radius_correction",
                "message": "Radio de filete reducido por compatibilidad geométrica.",
                "old_radius": old,
                "new_radius": radio
            })

        filetes_corregidos.append({
            "radio": radio
        })

    spec["filetes"] = filetes_corregidos

    return spec


def validar_y_corregir_design_spec(spec, prompt):
    """
    Valida y corrige la especificación generada por IA antes de convertirla a feature_plan.

    Devuelve:
    - corrected_spec
    - validation_report
    """

    reporte = {
        "status": "ok",
        "errors": [],
        "warnings": [],
        "corrections": []
    }

    corrected = copy.deepcopy(spec)

    corrected = _asegurar_valores_basicos(corrected, reporte)

    if reporte["errors"]:
        reporte["status"] = "error"
        return corrected, reporte

    corrected = _corregir_longitud_total(corrected, prompt, reporte)
    corrected = _corregir_chaveteros(corrected, prompt, reporte)
    corrected = _corregir_roscas(corrected, prompt, reporte)
    corrected = _corregir_filetes(corrected, reporte)

    if reporte["errors"]:
        reporte["status"] = "error"
    elif reporte["corrections"] or reporte["warnings"]:
        reporte["status"] = "corrected"
    else:
        reporte["status"] = "ok"

    return corrected, reporte