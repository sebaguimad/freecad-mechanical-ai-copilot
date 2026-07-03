# domains/shaft/validator.py
"""
Validador y corrector del dominio shaft.

Migrado desde core/plan_validator.py con estas correcciones:

1. La longitud total objetivo viene del campo spec["longitud_total"]
   (declarado por la IA). El regex sobre el prompt es SOLO fallback y
   solo con patrones explícitos — se eliminó el patrón genérico
   r"(\\d+)\\s*mm" que capturaba el primer número con mm del texto
   (p.ej. tomaba "chavetero de 40 mm" como longitud total del eje).

2. Se valida el solape rosca/chavetero en el mismo tramo: la rosca
   simplificada se genera con cut+fuse y rellenaría un chavetero que
   caiga en su zona, así que el conflicto se corrige moviendo o
   recortando la rosca.

3. El filete pasa a ser de hombros (fillet_shoulders), con radio
   limitado de forma más conservadora.

No importa FreeCAD: es Python puro y por lo tanto testeable con pytest.
"""

import copy
import re


# ---------------------------------------------------------------- helpers

def _extraer_longitud_total_desde_prompt(prompt):
    """
    Fallback SOLO con patrones explícitos e inequívocos.
    """
    texto = (prompt or "").lower()

    patrones = [
        r"longitud\s+total\s+(?:de\s+)?(\d+(?:\.\d+)?)\s*mm",
        r"eje\s+de\s+(\d+(?:\.\d+)?)\s*mm\s+(?:de\s+)?(?:largo|longitud)",
        r"eje\s+de\s+(\d+(?:\.\d+)?)\s*mm(?!\s*de\s*di[aá]metro)",
    ]

    for patron in patrones:
        match = re.search(patron, texto)
        if match:
            return float(match.group(1))

    return None


def _es_chavetero_central_solicitado(prompt):
    texto = (prompt or "").lower()
    return "chavetero" in texto and (
        "central" in texto or "tramo central" in texto or "medio" in texto
    )


def _es_rosca_derecha_solicitada(prompt):
    texto = (prompt or "").lower()
    return "rosca" in texto and (
        "derecha" in texto or "extremo derecho" in texto or "lado derecho" in texto
    )


def _tramo_central_index(segmentos):
    if not segmentos:
        return 0
    return len(segmentos) // 2


def _sumar_longitudes(segmentos):
    return sum(float(s["longitud"]) for s in segmentos)


def _inicio_tramo(segmentos, idx):
    return sum(float(s["longitud"]) for s in segmentos[:idx])


# ---------------------------------------------------------------- pasos

def _asegurar_valores_basicos(spec, reporte):
    spec.setdefault("intent", "crear_eje_escalonado")
    spec.setdefault("units", "mm")
    spec.setdefault("longitud_total", None)
    spec.setdefault("segmentos", [])
    spec.setdefault("chaveteros", [])
    spec.setdefault("filetes", [])
    spec.setdefault("roscas", [])
    spec.setdefault("missing_data", [])
    spec.setdefault("assumptions", [])

    if spec["intent"] != "crear_eje_escalonado":
        reporte["warnings"].append(
            f"Intent normalizado desde '{spec['intent']}' a crear_eje_escalonado."
        )
        spec["intent"] = "crear_eje_escalonado"

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
            reporte["errors"].append(f"Segmento {i} tiene valores no numéricos.")
            continue

        if d <= 0 or l <= 0:
            reporte["errors"].append(
                f"Segmento {i} tiene diámetro o longitud no positiva."
            )
            continue

        segmentos_validos.append({"diametro": d, "longitud": l})

    spec["segmentos"] = segmentos_validos

    if not spec["segmentos"]:
        reporte["errors"].append("No existen segmentos válidos para generar el eje.")

    return spec


def _corregir_longitud_total(spec, prompt, reporte):
    segmentos = spec["segmentos"]

    if not segmentos:
        return spec

    longitud_objetivo = None

    try:
        if spec.get("longitud_total") is not None:
            longitud_objetivo = float(spec["longitud_total"])
            if longitud_objetivo <= 0:
                longitud_objetivo = None
    except Exception:
        longitud_objetivo = None

    if longitud_objetivo is None:
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
            "No se pudo corregir la longitud total porque el tramo central "
            "quedaría con longitud no positiva."
        )
        return spec

    segmentos[idx]["longitud"] = nueva_longitud

    reporte["corrections"].append({
        "type": "length_correction",
        "message": (
            f"La suma de longitudes era {suma_actual:g} mm y debía ser "
            f"{longitud_objetivo:g} mm. Se ajustó el tramo central en "
            f"{diferencia:+g} mm."
        ),
        "target_segment": idx,
        "new_length": nueva_longitud
    })

    return spec


def _corregir_chaveteros(spec, prompt, reporte):
    segmentos = spec["segmentos"]
    chaveteros = spec.get("chaveteros", [])

    if not segmentos or not chaveteros:
        return spec

    if _es_chavetero_central_solicitado(prompt):
        idx_central = _tramo_central_index(segmentos)
        chav = chaveteros[0]
        if len(chaveteros) > 1 or chav.get("tramo_index") != idx_central:
            reporte["corrections"].append({
                "type": "keyway_centered",
                "message": (
                    "Se solicitó chavetero central: se conserva un único "
                    f"chavetero en el tramo {idx_central}."
                )
            })
        chav["tramo_index"] = idx_central
        chaveteros = [chav]

    chaveteros_validos = []

    for i, chav in enumerate(chaveteros):
        try:
            idx = int(chav["tramo_index"])
        except Exception:
            idx = 0

        if idx < 0 or idx >= len(segmentos):
            reporte["corrections"].append({
                "type": "keyway_index_fixed",
                "message": f"tramo_index inválido en chavetero {i}; se movió al tramo central."
            })
            idx = _tramo_central_index(segmentos)

        seg = segmentos[idx]

        try:
            ancho = float(chav.get("ancho", 8.0))
            prof = float(chav.get("profundidad", 3.3))
            largo = float(chav.get("longitud", 40.0))
        except Exception:
            ancho, prof, largo = 8.0, 3.3, 40.0
            reporte["corrections"].append({
                "type": "keyway_defaults_applied",
                "message": f"Chavetero {i} tenía valores no numéricos; se aplicaron valores por defecto."
            })

        if ancho <= 0 or prof <= 0 or largo <= 0:
            reporte["errors"].append(f"Chavetero {i} tiene dimensiones no positivas.")
            continue

        # El chavetero debe caber en el tramo
        if largo > seg["longitud"]:
            largo_nuevo = seg["longitud"] * 0.8
            reporte["corrections"].append({
                "type": "keyway_length_reduced",
                "message": (
                    f"Chavetero {i} ({largo:g} mm) no cabía en el tramo {idx} "
                    f"({seg['longitud']:g} mm); se redujo a {largo_nuevo:g} mm."
                )
            })
            largo = largo_nuevo

        # Profundidad razonable: menos del 40% del diámetro
        if prof >= seg["diametro"] * 0.4:
            prof_nueva = seg["diametro"] * 0.16
            reporte["corrections"].append({
                "type": "keyway_depth_reduced",
                "message": (
                    f"Profundidad de chavetero {i} excesiva para Ø{seg['diametro']:g}; "
                    f"se redujo a {prof_nueva:g} mm."
                )
            })
            prof = prof_nueva

        offset = chav.get("offset_desde_inicio")
        if offset is not None:
            try:
                offset = float(offset)
            except Exception:
                offset = None

        if offset is not None:
            if offset < 0 or offset + largo > seg["longitud"]:
                reporte["corrections"].append({
                    "type": "keyway_offset_centered",
                    "message": f"Offset del chavetero {i} fuera de rango; se centró en el tramo."
                })
                offset = None

        chaveteros_validos.append({
            "tramo_index": idx,
            "ancho": ancho,
            "profundidad": prof,
            "longitud": largo,
            "offset_desde_inicio": offset
        })

    spec["chaveteros"] = chaveteros_validos
    return spec


def _corregir_roscas(spec, prompt, reporte):
    segmentos = spec["segmentos"]
    roscas = spec.get("roscas", [])

    if not segmentos or not roscas:
        return spec

    roscas_corregidas = []

    for i, ros in enumerate(roscas):
        try:
            idx = int(ros.get("tramo_index", 0))
        except Exception:
            idx = 0

        lado = ros.get("lado", "derecho")
        if lado not in ("izquierdo", "derecho"):
            lado = "derecho"

        if _es_rosca_derecha_solicitada(prompt):
            lado = "derecho"
            if idx != len(segmentos) - 1:
                reporte["corrections"].append({
                    "type": "thread_moved",
                    "message": f"Rosca {i} derecha movida al último tramo."
                })
                idx = len(segmentos) - 1

        if idx < 0 or idx >= len(segmentos):
            idx = len(segmentos) - 1 if lado == "derecho" else 0
            reporte["corrections"].append({
                "type": "thread_index_fixed",
                "message": f"tramo_index inválido en rosca {i}; se movió al tramo {idx}."
            })

        seg = segmentos[idx]

        try:
            diametro_nominal = float(ros.get("diametro_nominal", seg["diametro"]))
        except Exception:
            diametro_nominal = seg["diametro"]

        try:
            longitud = float(ros.get("longitud", 20.0))
        except Exception:
            longitud = 20.0

        if diametro_nominal <= 0 or longitud <= 0:
            reporte["errors"].append(f"Rosca {i} tiene dimensiones no positivas.")
            continue

        # Una rosca M20 no puede vivir en un tramo de Ø12.
        if diametro_nominal > seg["diametro"]:
            old_d = seg["diametro"]
            seg["diametro"] = diametro_nominal
            reporte["corrections"].append({
                "type": "segment_diameter_increased_for_thread",
                "message": (
                    f"La rosca M{diametro_nominal:g} no era compatible con el "
                    f"tramo Ø{old_d:g}; se aumentó el tramo {idx} a Ø{diametro_nominal:g}."
                ),
                "segment": idx,
                "new_segment_diameter": diametro_nominal
            })

        if longitud > seg["longitud"]:
            longitud = seg["longitud"]
            reporte["corrections"].append({
                "type": "thread_length_reduced",
                "message": f"Longitud de rosca {i} reducida para caber en el tramo {idx}."
            })

        roscas_corregidas.append({
            "tramo_index": idx,
            "diametro_nominal": diametro_nominal,
            "longitud": longitud,
            "lado": lado
        })

    spec["roscas"] = roscas_corregidas
    return spec


def _resolver_conflictos_rosca_chavetero(spec, reporte):
    """
    La rosca simplificada se ejecuta con cut+fuse sobre su zona: si un
    chavetero cae dentro de esa zona X en el mismo tramo, el fuse lo
    rellenaría. Regla: la rosca se recorta para no tocar el chavetero;
    si no queda espacio útil (>= 5 mm), la rosca se elimina con warning.
    """
    segmentos = spec["segmentos"]
    if not segmentos:
        return spec

    roscas_finales = []

    for i, ros in enumerate(spec.get("roscas", [])):
        idx = ros["tramo_index"]
        seg = segmentos[idx]
        seg_ini = _inicio_tramo(segmentos, idx)

        if ros["lado"] == "derecho":
            r_ini = seg_ini + seg["longitud"] - ros["longitud"]
        else:
            r_ini = seg_ini
        r_fin = r_ini + ros["longitud"]

        conflicto = False

        for chav in spec.get("chaveteros", []):
            if chav["tramo_index"] != idx:
                continue

            offset = chav["offset_desde_inicio"]
            if offset is None:
                offset = (seg["longitud"] - chav["longitud"]) / 2.0

            c_ini = seg_ini + offset
            c_fin = c_ini + chav["longitud"]

            if r_ini < c_fin and c_ini < r_fin:
                # Solape: recortar la rosca hasta el borde del chavetero
                if ros["lado"] == "derecho":
                    nueva_long = (seg_ini + seg["longitud"]) - c_fin
                else:
                    nueva_long = c_ini - seg_ini

                if nueva_long >= 5.0:
                    reporte["corrections"].append({
                        "type": "thread_trimmed_keyway_overlap",
                        "message": (
                            f"La rosca {i} se solapaba con un chavetero en el "
                            f"tramo {idx}; se recortó a {nueva_long:g} mm."
                        )
                    })
                    ros["longitud"] = nueva_long
                else:
                    reporte["warnings"].append(
                        f"La rosca {i} se eliminó: no hay espacio en el tramo "
                        f"{idx} sin invadir el chavetero."
                    )
                    conflicto = True
                break

        if not conflicto:
            roscas_finales.append(ros)

    spec["roscas"] = roscas_finales
    return spec


def _corregir_filetes(spec, reporte):
    segmentos = spec["segmentos"]
    filetes = spec.get("filetes", [])

    if not segmentos or not filetes:
        return spec

    d_min = min(seg["diametro"] for seg in segmentos)
    l_min = min(seg["longitud"] for seg in segmentos)
    radio_max = max(0.5, min(d_min * 0.1, l_min * 0.25))

    filetes_validos = []

    for i, fil in enumerate(filetes):
        try:
            radio = float(fil.get("radio", 1.0))
        except Exception:
            radio = 1.0

        if radio <= 0:
            continue

        if radio > radio_max:
            reporte["corrections"].append({
                "type": "fillet_radius_reduced",
                "message": f"Radio de filete {i} reducido de {radio:g} a {radio_max:g} mm."
            })
            radio = radio_max

        filetes_validos.append({"radio": radio})

    # Un solo filete de hombros basta
    spec["filetes"] = filetes_validos[:1]
    return spec


# ---------------------------------------------------------------- API

def validate(spec, prompt="", design_request=None):
    """
    API estándar de dominio: (spec, prompt) -> (corrected_spec, reporte)
    """
    reporte = {"status": "ok", "errors": [], "warnings": [], "corrections": []}

    corrected = copy.deepcopy(spec) if isinstance(spec, dict) else {}

    corrected = _asegurar_valores_basicos(corrected, reporte)

    if not reporte["errors"]:
        corrected = _corregir_longitud_total(corrected, prompt, reporte)
        corrected = _corregir_chaveteros(corrected, prompt, reporte)
        corrected = _corregir_roscas(corrected, prompt, reporte)
        corrected = _resolver_conflictos_rosca_chavetero(corrected, reporte)
        corrected = _corregir_filetes(corrected, reporte)

    if reporte["errors"]:
        reporte["status"] = "error"
    elif reporte["warnings"] or reporte["corrections"]:
        reporte["status"] = "corrected"

    return corrected, reporte


# Compatibilidad con el nombre anterior
def validar_y_corregir_design_spec(spec, prompt):
    corrected, reporte = validate(spec, prompt)
    return corrected, reporte
