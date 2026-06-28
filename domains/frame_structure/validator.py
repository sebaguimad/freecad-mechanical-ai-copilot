# domains/frame_structure/validator.py

from domains.frame_structure.profile_library import normalize_profile


def _num(value, default):
    try:
        if value is None:
            return default

        value = float(value)

        if value <= 0:
            return default

        return value

    except Exception:
        return default


def _point(value, default):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return list(default)

    try:
        return [float(value[0]), float(value[1]), float(value[2])]

    except Exception:
        return list(default)


def _member_length(member):
    s = member["start"]
    e = member["end"]

    return (
        (e[0] - s[0]) ** 2 +
        (e[1] - s[1]) ** 2 +
        (e[2] - s[2]) ** 2
    ) ** 0.5


def _build_default_industrial_table(length, width, height, profile):
    """
    Reconstrucción paramétrica estable de una mesa industrial.

    Sistema de coordenadas:
    - X = largo
    - Y = ancho
    - Z = altura
    - origen en una esquina inferior de la mesa
    """

    rail_z_low = 120.0
    rail_z_top = max(height - 80.0, height * 0.85)

    members = []

    # Patas verticales
    leg_positions = [
        (0.0, 0.0),
        (length, 0.0),
        (length, width),
        (0.0, width)
    ]

    for i, (x, y) in enumerate(leg_positions, start=1):
        members.append({
            "id": f"leg_{i}",
            "role": "leg",
            "profile": profile,
            "start": [x, y, 0.0],
            "end": [x, y, height]
        })

    # Travesaños inferiores
    members.extend([
        {
            "id": "lower_front_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, 0.0, rail_z_low],
            "end": [length, 0.0, rail_z_low]
        },
        {
            "id": "lower_back_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, width, rail_z_low],
            "end": [length, width, rail_z_low]
        },
        {
            "id": "lower_left_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, 0.0, rail_z_low],
            "end": [0.0, width, rail_z_low]
        },
        {
            "id": "lower_right_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [length, 0.0, rail_z_low],
            "end": [length, width, rail_z_low]
        }
    ])

    # Travesaños superiores bajo cubierta
    members.extend([
        {
            "id": "upper_front_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, 0.0, rail_z_top],
            "end": [length, 0.0, rail_z_top]
        },
        {
            "id": "upper_back_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, width, rail_z_top],
            "end": [length, width, rail_z_top]
        },
        {
            "id": "upper_left_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [0.0, 0.0, rail_z_top],
            "end": [0.0, width, rail_z_top]
        },
        {
            "id": "upper_right_rail",
            "role": "cross_member",
            "profile": profile,
            "start": [length, 0.0, rail_z_top],
            "end": [length, width, rail_z_top]
        }
    ])

    return members


def _should_rebuild_as_table(spec, corrected_members, length, width, height):
    """
    Decide si conviene ignorar los members de la IA y reconstruir una mesa estable.
    Esto evita que la IA genere patas cortas o coordenadas inconsistentes.
    """

    structure_type = spec.get("structure_type", "industrial_table")

    if structure_type == "industrial_table":
        return True

    if not corrected_members:
        return True

    leg_members = [
        m for m in corrected_members
        if m.get("role") == "leg"
    ]

    if len(leg_members) < 4:
        return True

    # Si las patas son demasiado cortas, reconstruir.
    for leg in leg_members:
        if _member_length(leg) < height * 0.7:
            return True

    return False


def validate(spec, prompt="", design_request=None):
    """
    Validador robusto para estructuras paramétricas tipo mesa/bastidor.

    Objetivo:
    - La IA vision interpreta la imagen.
    - Este validador convierte esa interpretación en una estructura coherente.
    - Si la IA entrega coordenadas malas, se reconstruye una mesa paramétrica estable.
    """

    errors = []
    warnings = []
    corrections = []

    overall = spec.get("overall_dimensions", {})

    length = _num(overall.get("length"), 1200.0)
    width = _num(overall.get("width"), 700.0)
    height = _num(overall.get("height"), 850.0)

    if "overall_dimensions" not in spec:
        corrections.append({
            "type": "default_overall_dimensions_added",
            "value": [length, width, height]
        })

    default_profile = normalize_profile(
        spec.get(
            "default_profile",
            {
                "section": "square_tube",
                "width": 40,
                "height": 40,
                "thickness": 3
            }
        )
    )

    assumptions = []
    missing_data = []

    if design_request:
        assumptions.extend(design_request.get("assumptions", []))
        missing_data.extend(design_request.get("missing_data", []))

    corrected = {
        "structure_type": spec.get("structure_type", "industrial_table"),
        "overall_dimensions": {
            "length": length,
            "width": width,
            "height": height
        },
        "top": {
            "enabled": True,
            "type": "plate",
            "length": length,
            "width": width,
            "thickness": _num(
                spec.get("top", {}).get("thickness", 6.0)
                if isinstance(spec.get("top", {}), dict)
                else 6.0,
                6.0
            ),
            "position": [0.0, 0.0, height]
        },
        "default_profile": default_profile,
        "members": [],
        "plates": [],
        "connections": spec.get("connections", []),
        "bom_enabled": bool(spec.get("bom_enabled", True)),
        "missing_data": missing_data,
        "assumptions": assumptions
    }

    # Leer members propuestos por la IA, por si son razonables
    proposed_members = spec.get("members", [])

    used_ids = set()

    for i, member in enumerate(proposed_members):
        mid = str(member.get("id", f"member_{i+1}"))

        if mid in used_ids:
            old = mid
            mid = f"{mid}_{i+1}"
            corrections.append({
                "type": "duplicate_member_id_renamed",
                "old": old,
                "new": mid
            })

        used_ids.add(mid)

        start = _point(member.get("start"), [0.0, 0.0, 0.0])
        end = _point(member.get("end"), [0.0, 0.0, height])

        if start == end:
            warnings.append(f"Member {mid} tiene start=end. Se ignoró.")
            continue

        corrected["members"].append({
            "id": mid,
            "role": member.get("role", "unknown"),
            "profile": normalize_profile(member.get("profile", default_profile)),
            "start": start,
            "end": end
        })

    # Si parece mesa industrial, reconstruir de forma canónica.
    if _should_rebuild_as_table(spec, corrected["members"], length, width, height):
        old_count = len(corrected["members"])

        corrected["members"] = _build_default_industrial_table(
            length=length,
            width=width,
            height=height,
            profile=default_profile
        )

        corrections.append({
            "type": "frame_rebuilt_as_parametric_industrial_table",
            "old_member_count": old_count,
            "new_member_count": len(corrected["members"])
        })

        warnings.append(
            "La geometría visual fue normalizada a una mesa industrial paramétrica editable."
        )

    # Placas adicionales: por ahora no duplicar la cubierta
    for i, plate in enumerate(spec.get("plates", [])):
        role = plate.get("role", "unknown")

        if role == "top":
            corrections.append({
                "type": "duplicate_top_plate_removed",
                "plate_id": plate.get("id", f"plate_{i+1}")
            })
            continue

        if role == "base_plate":
            # Por ahora ignoramos base_plate gigante si viene de la IA
            # porque muchas veces confunde la cubierta con base.
            corrections.append({
                "type": "base_plate_from_vision_ignored_in_mvp",
                "plate_id": plate.get("id", f"plate_{i+1}")
            })
            continue

        corrected["plates"].append({
            "id": str(plate.get("id", f"plate_{i+1}")),
            "role": role,
            "length": _num(plate.get("length"), 80.0),
            "width": _num(plate.get("width"), 80.0),
            "thickness": _num(plate.get("thickness"), 6.0),
            "position": _point(plate.get("position"), [0.0, 0.0, 0.0])
        })

    if design_request and design_request.get("confidence", 1.0) < 0.65:
        warnings.append(
            "La confianza de reconstrucción visual es baja. Revisar medidas antes de fabricar."
        )

    status = "ok"

    if errors:
        status = "error"
    elif warnings or corrections:
        status = "corrected"

    return corrected, {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "corrections": corrections
    }