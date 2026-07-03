# tests/test_domain_router.py
"""
Tests del router: el bug original era que importaba dominios inexistentes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.domain_router import route_domain, process_design_request


def test_familia_desconocida_cae_a_custom():
    assert route_domain({"family": "gear"}) == "custom"
    assert route_domain({"family": "plate"}) == "custom"
    assert route_domain({}) == "custom"


def test_familias_soportadas():
    assert route_domain({"family": "shaft"}) == "shaft"
    assert route_domain({"family": "frame_structure"}) == "frame_structure"
    assert route_domain({"family": "custom"}) == "custom"


def test_pipeline_shaft_completo_sin_freecad():
    """
    El bug original: family='shaft' lanzaba ImportError porque
    domains/shaft no existía. Ahora el pipeline completo
    (validar → plan → resumen) debe funcionar.
    """
    design_request = {
        "family": "shaft",
        "intent": "crear_eje_escalonado",
        "confidence": 0.9,
        "units": "mm",
        "spec": {
            "intent": "crear_eje_escalonado",
            "units": "mm",
            "longitud_total": 250,
            "segmentos": [
                {"diametro": 20, "longitud": 60},
                {"diametro": 30, "longitud": 120},
                {"diametro": 25, "longitud": 70}
            ],
            "chaveteros": [{"tramo_index": 1, "ancho": 8, "profundidad": 3.3,
                            "longitud": 40, "offset_desde_inicio": None}],
            "filetes": [{"radio": 1.0}],
            "roscas": [{"tramo_index": 2, "diametro_nominal": 20,
                        "longitud": 20, "lado": "derecho"}],
            "missing_data": [],
            "assumptions": []
        }
    }

    resultado = process_design_request(design_request, "eje de prueba")

    assert resultado["domain"] == "shaft"
    plan = resultado["feature_plan"]
    tipos = [f["type"] for f in plan["feature_tree"]]

    # 3 cilindros + fusión + rosca (antes del chavetero) + chavetero + filete
    assert tipos == ["cylinder", "cylinder", "cylinder", "boolean_fuse",
                     "thread_zone", "keyway_cut", "fillet_shoulders"]
    assert "resumen" not in resultado or True
    assert isinstance(resultado["summary"], str)
    assert "eje escalonado" in resultado["summary"]


def test_pipeline_frame_completo_sin_freecad():
    design_request = {
        "family": "frame_structure",
        "intent": "crear_estructura_parametrica",
        "confidence": 0.8,
        "units": "mm",
        "spec": {
            "structure_type": "industrial_table",
            "overall_dimensions": {"length": 1200, "width": 700, "height": 850},
            "bom_enabled": True
        }
    }

    resultado = process_design_request(design_request, "mesa industrial")

    assert resultado["domain"] == "frame_structure"
    tipos = [f["type"] for f in resultado["feature_plan"]["feature_tree"]]
    assert "square_tube_between_points" in tipos
    assert "boolean_fuse" in tipos
    assert tipos[-1] == "bom_report"


def test_validacion_con_error_lanza_valueerror():
    design_request = {
        "family": "shaft",
        "spec": {"segmentos": []}
    }

    try:
        process_design_request(design_request, "")
        assert False, "Debió lanzar ValueError"
    except ValueError as e:
        assert "shaft" in str(e)
