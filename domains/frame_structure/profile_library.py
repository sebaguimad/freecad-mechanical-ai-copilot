# domains/frame_structure/profile_library.py

DEFAULT_SQUARE_TUBE = {"section": "square_tube", "width": 40.0, "height": 40.0, "thickness": 3.0}
DEFAULT_LIGHT_TUBE = {"section": "square_tube", "width": 30.0, "height": 30.0, "thickness": 2.0}


def normalize_profile(profile=None):
    if not isinstance(profile, dict):
        profile = {}
    section = profile.get("section", "square_tube")
    if section != "square_tube":
        section = "square_tube"

    def num(key, default):
        try:
            value = float(profile.get(key, default))
            if value <= 0:
                return default
            return value
        except Exception:
            return default

    width = num("width", 40.0)
    height = num("height", 40.0)
    thickness = num("thickness", 3.0)
    max_t = min(width, height) * 0.45
    if thickness > max_t:
        thickness = max_t
    return {"section": section, "width": width, "height": height, "thickness": thickness}
