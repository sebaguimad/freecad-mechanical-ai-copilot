"""Tests Python puros para operaciones custom avanzadas."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domains.custom.validator import validate
from domains.custom.planner import build_plan


def test_revolve_plan():
    raw = {
        "nombre_pieza": "polea",
        "operaciones": [
            {"id": "op_1", "tipo": "revolve", "modo": "agregar",
             "perfil": [[10, 0], [50, 0], [50, 20], [10, 20]],
             "angulo": 360, "eje": "Z", "posicion": [0, 0, 0]},
            {"id": "op_2", "tipo": "cylinder", "modo": "cortar",
             "diametro": 20, "altura": 24, "eje": "Z", "posicion": [0, 0, -2]},
        ],
    }
    spec, report = validate(raw)
    assert report["status"] in ("ok", "corrected")
    plan = build_plan(spec, validation_report=report)
    assert plan["feature_tree"][0]["shape"]["kind"] == "revolve"
    assert plan["feature_tree"][0]["shape"]["angle"] == 360


def test_linear_pattern_and_mirror_plan():
    raw = {
        "operaciones": [
            {"id": "base", "tipo": "box", "modo": "agregar", "largo": 100, "ancho": 60, "alto": 8},
            {"id": "hole", "tipo": "cylinder", "modo": "cortar", "diametro": 8, "altura": 12,
             "posicion": [15, 15, -2], "eje": "Z"},
            {"id": "row", "tipo": "linear_pattern", "objetivo": "hole", "cantidad": 4,
             "espaciado": 20, "direccion": [1, 0, 0]},
            {"id": "sym", "tipo": "mirror", "objetivo": "hole", "plano": "XZ", "offset": 30},
        ]
    }
    spec, report = validate(raw)
    assert report["status"] in ("ok", "corrected")
    plan = build_plan(spec, validation_report=report)
    types = [f["type"] for f in plan["feature_tree"]]
    assert types == ["solid_add", "solid_cut", "linear_pattern", "mirror"]


def test_sweep_requires_path():
    raw = {"operaciones": [{"id": "s", "tipo": "sweep", "modo": "agregar", "perfil": [[0,0],[5,0],[5,5]]}]}
    _, report = validate(raw)
    assert report["status"] == "error"


def test_loft_requires_two_sections():
    raw = {"operaciones": [{"id": "l", "tipo": "loft", "modo": "agregar",
                             "secciones": [{"puntos": [[0,0],[10,0],[10,10],[0,10]], "z": 0}]}]}
    _, report = validate(raw)
    assert report["status"] == "error"
