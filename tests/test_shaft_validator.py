# tests/test_shaft_validator.py
"""
Tests del validador del dominio shaft.
Se ejecutan sin FreeCAD:  pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domains.shaft.validator import validate


def _spec_base():
    return {
        "intent": "crear_eje_escalonado",
        "units": "mm",
        "longitud_total": None,
        "segmentos": [
            {"diametro": 20, "longitud": 60},
            {"diametro": 30, "longitud": 120},
            {"diametro": 25, "longitud": 70}
        ],
        "chaveteros": [],
        "filetes": [],
        "roscas": [],
        "missing_data": [],
        "assumptions": []
    }


def test_eje_valido_pasa_sin_correcciones():
    spec, reporte = validate(_spec_base(), prompt="")
    assert reporte["status"] == "ok"
    assert len(spec["segmentos"]) == 3


def test_longitud_total_se_corrige_desde_campo_spec():
    s = _spec_base()
    s["longitud_total"] = 300  # la suma real es 250
    spec, reporte = validate(s, prompt="")
    assert reporte["status"] == "corrected"
    assert abs(sum(x["longitud"] for x in spec["segmentos"]) - 300) < 1e-6
    # Se ajusta el tramo central
    assert abs(spec["segmentos"][1]["longitud"] - 170) < 1e-6


def test_regex_generico_eliminado_no_toma_numero_equivocado():
    """
    Bug histórico: 'chavetero de 40 mm' era capturado como longitud
    total del eje por el patrón genérico (\\d+)mm. Ya no debe pasar.
    """
    s = _spec_base()  # suma 250, sin longitud_total declarada
    spec, reporte = validate(
        s, prompt="eje con chavetero de 40 mm en el tramo central"
    )
    tipos = [c["type"] for c in reporte["corrections"]]
    assert "length_correction" not in tipos
    assert abs(sum(x["longitud"] for x in spec["segmentos"]) - 250) < 1e-6


def test_fallback_regex_explicito_si_funciona():
    s = _spec_base()
    spec, reporte = validate(
        s, prompt="Diseña un eje con longitud total de 300 mm"
    )
    assert abs(sum(x["longitud"] for x in spec["segmentos"]) - 300) < 1e-6


def test_rosca_m20_en_tramo_delgado_aumenta_diametro():
    s = _spec_base()
    s["segmentos"][2]["diametro"] = 12
    s["roscas"] = [{"tramo_index": 2, "diametro_nominal": 20,
                    "longitud": 20, "lado": "derecho"}]
    spec, reporte = validate(s, prompt="")
    assert spec["segmentos"][2]["diametro"] == 20
    tipos = [c["type"] for c in reporte["corrections"]]
    assert "segment_diameter_increased_for_thread" in tipos


def test_chavetero_central_unico():
    s = _spec_base()
    s["chaveteros"] = [
        {"tramo_index": 0, "ancho": 8, "profundidad": 3.3,
         "longitud": 40, "offset_desde_inicio": None},
        {"tramo_index": 2, "ancho": 8, "profundidad": 3.3,
         "longitud": 40, "offset_desde_inicio": None}
    ]
    spec, reporte = validate(s, prompt="eje con chavetero central")
    assert len(spec["chaveteros"]) == 1
    assert spec["chaveteros"][0]["tramo_index"] == 1


def test_chavetero_mas_largo_que_tramo_se_reduce():
    s = _spec_base()
    s["chaveteros"] = [{"tramo_index": 0, "ancho": 8, "profundidad": 3.3,
                        "longitud": 200, "offset_desde_inicio": None}]
    spec, reporte = validate(s, prompt="")
    assert spec["chaveteros"][0]["longitud"] <= 60


def test_conflicto_rosca_chavetero_recorta_rosca():
    """
    Chavetero centrado en el último tramo (70 mm): ocupa x local 15..55.
    Rosca derecha de 40 mm ocuparía x local 30..70 → solape.
    Debe recortarse a 70-55 = 15 mm.
    """
    s = _spec_base()
    s["chaveteros"] = [{"tramo_index": 2, "ancho": 8, "profundidad": 3.3,
                        "longitud": 40, "offset_desde_inicio": None}]
    s["roscas"] = [{"tramo_index": 2, "diametro_nominal": 20,
                    "longitud": 40, "lado": "derecho"}]
    spec, reporte = validate(s, prompt="")
    assert len(spec["roscas"]) == 1
    assert abs(spec["roscas"][0]["longitud"] - 15) < 1e-6
    tipos = [c["type"] for c in reporte["corrections"]]
    assert "thread_trimmed_keyway_overlap" in tipos


def test_sin_segmentos_es_error():
    s = _spec_base()
    s["segmentos"] = []
    spec, reporte = validate(s, prompt="")
    assert reporte["status"] == "error"


def test_filete_excesivo_se_limita():
    s = _spec_base()
    s["filetes"] = [{"radio": 50}]
    spec, reporte = validate(s, prompt="")
    assert spec["filetes"][0]["radio"] <= 2.0  # 10% del Ø mínimo (20)
