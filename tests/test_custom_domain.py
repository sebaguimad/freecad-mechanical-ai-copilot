# tests/test_custom_domain.py
"""
Tests del dominio custom (validador + planner).
Se ejecutan sin FreeCAD:  pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domains.custom.validator import validate
from domains.custom.planner import build_plan


def _spec_engranaje():
    """Engranaje recto simplificado m=2, Z=40, b=20, agujero Ø20."""
    return {
        "intent": "crear_pieza_custom",
        "units": "mm",
        "nombre_pieza": "engranaje_recto_z40_m2",
        "operaciones": [
            {"id": "op_001", "tipo": "cylinder", "modo": "agregar",
             "nombre": "cuerpo", "diametro": 75, "altura": 20,
             "posicion": [0, 0, 0], "eje": "Z"},
            {"id": "op_002", "tipo": "polygon_prism", "modo": "agregar",
             "nombre": "diente",
             "puntos": [[36.5, -1.6], [42, -0.7], [42, 0.7], [36.5, 1.6]],
             "altura": 20, "posicion": [0, 0, 0], "eje": "Z"},
            {"id": "op_003", "tipo": "polar_pattern", "objetivo": "op_002",
             "cantidad": 40, "centro": [0, 0, 0], "eje": "Z"},
            {"id": "op_004", "tipo": "cylinder", "modo": "cortar",
             "nombre": "agujero", "diametro": 20, "altura": 24,
             "posicion": [0, 0, -2], "eje": "Z"}
        ],
        "missing_data": [],
        "assumptions": []
    }


def test_engranaje_valido():
    spec, reporte = validate(_spec_engranaje())
    assert reporte["status"] == "ok"
    assert len(spec["operaciones"]) == 4


def test_primera_operacion_cortar_se_fuerza_a_agregar():
    s = _spec_engranaje()
    s["operaciones"][0]["modo"] = "cortar"
    spec, reporte = validate(s)
    assert spec["operaciones"][0]["modo"] == "agregar"
    tipos = [c["type"] for c in reporte["corrections"]]
    assert "first_op_forced_add" in tipos


def test_pattern_con_objetivo_inexistente_es_error():
    s = _spec_engranaje()
    s["operaciones"][2]["objetivo"] = "no_existe"
    spec, reporte = validate(s)
    assert reporte["status"] == "error"


def test_pattern_hacia_adelante_es_error():
    """El patrón no puede apuntar a una operación posterior."""
    s = _spec_engranaje()
    ops = s["operaciones"]
    ops[2]["objetivo"] = "op_004"  # op_004 viene después del patrón
    spec, reporte = validate(s)
    assert reporte["status"] == "error"


def test_ids_duplicados_se_renombran():
    s = _spec_engranaje()
    s["operaciones"][3]["id"] = "op_001"
    spec, reporte = validate(s)
    ids = [op["id"] for op in spec["operaciones"]]
    assert len(ids) == len(set(ids))


def test_dimensiones_absurdas_se_limitan():
    s = _spec_engranaje()
    s["operaciones"][0]["diametro"] = 999999
    spec, reporte = validate(s)
    assert spec["operaciones"][0]["diametro"] <= 10000


def test_poligono_con_2_puntos_es_error():
    s = _spec_engranaje()
    s["operaciones"][1]["puntos"] = [[0, 0], [10, 0]]
    spec, reporte = validate(s)
    assert reporte["status"] == "error"


def test_tipo_desconocido_se_ignora_con_warning():
    s = _spec_engranaje()
    s["operaciones"].append({"id": "op_x", "tipo": "helix_mágica"})
    spec, reporte = validate(s)
    assert reporte["status"] in ("ok", "corrected")
    assert len(spec["operaciones"]) == 4
    assert any("no soportado" in w for w in reporte["warnings"])


def test_sin_operaciones_solidas_es_error():
    s = {"operaciones": [{"id": "op_1", "tipo": "fillet_all", "radio": 1}]}
    spec, reporte = validate(s)
    assert reporte["status"] == "error"


def test_planner_genera_feature_tree_coherente():
    spec, reporte = validate(_spec_engranaje())
    plan = build_plan(spec, validation_report=reporte)

    tree = plan["feature_tree"]
    tipos = [f["type"] for f in tree]

    assert tipos == ["solid_add", "solid_add", "polar_pattern", "solid_cut"]
    # El patrón referencia el feature id mapeado del diente
    patron = tree[2]
    assert patron["pattern_target"] == "feat_op_002"
    assert patron["count"] == 40
    assert plan["final_feature_id"] == "feat_op_004"
    assert plan["family"] == "custom"


def test_planner_shape_specs():
    spec, reporte = validate(_spec_engranaje())
    plan = build_plan(spec, validation_report=reporte)

    base = plan["feature_tree"][0]["shape"]
    assert base["kind"] == "cylinder"
    assert base["diameter"] == 75
    assert base["axis"] == "Z"

    diente = plan["feature_tree"][1]["shape"]
    assert diente["kind"] == "polygon_prism"
    assert len(diente["points"]) == 4
