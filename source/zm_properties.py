# zm_properties.py — Zeta Motion 0.5.1
# Almacén temporal de propiedades del strip de preview
# Blender 4.5+ | Linux-only

cached_data = {}

def store_strip_properties(strip):
    """Extrae propiedades visuales y transform del strip para restaurarlas después.
    Devuelve un dict serializable simple con los datos importantes.
    Si strip es None, devuelve None.
    """
    if not strip:
        return None

    data = {}

    # Visual / blending
    try:
        data["blend_type"] = getattr(strip, "blend_type", "ALPHA_OVER")
        data["blend_alpha"] = getattr(strip, "blend_alpha", 0.5)
    except Exception:
        data["blend_type"] = "ALPHA_OVER"
        data["blend_alpha"] = 0.5

    # Flags
    data["use_translation"] = getattr(strip, "use_translation", False)
    data["use_crop"] = getattr(strip, "use_crop", False)
    data["color_multiply"] = getattr(strip, "color_multiply", 1.0)

    # Transform: some strips might not have transform attribute
    t = {}
    try:
        transform = getattr(strip, "transform", None)
        if transform:
            t["offset_x"] = getattr(transform, "offset_x", 0.0)
            t["offset_y"] = getattr(transform, "offset_y", 0.0)
            # size → scale_x / scale_y
            t["scale_x"] = getattr(transform, "scale_x", 1.0)
            t["scale_y"] = getattr(transform, "scale_y", 1.0)
        else:
            t["offset_x"] = 0.0
            t["offset_y"] = 0.0
            t["scale_x"] = 1.0
            t["scale_y"] = 1.0
    except Exception:
        t = {"offset_x": 0.0, "offset_y": 0.0, "scale_x": 1.0, "scale_y": 1.0}

    data["transform"] = t

    # Guardar en cache global temporal
    cached_data["preview"] = data
    return data

def apply_strip_properties(strip, data=None):
    """Aplica un dict de propiedades guardadas a un strip.
    Si data es None, intenta leer cached_data['preview'].
    """
    if not strip:
        return

    if data is None:
        data = cached_data.get("preview")

    if not data:
        return

    # Blending / visual
    try:
        strip.blend_type = data.get("blend_type", "ALPHA_OVER")
    except Exception:
        pass
    try:
        strip.blend_alpha = data.get("blend_alpha", 0.5)
    except Exception:
        pass

    # Flags
    try:
        strip.use_translation = data.get("use_translation", False)
    except Exception:
        pass
    try:
        strip.use_crop = data.get("use_crop", False)
    except Exception:
        pass
    try:
        strip.color_multiply = data.get("color_multiply", 1.0)
    except Exception:
        pass

    # Transform attributes (si existen)
    t = data.get("transform", {})
    transform = getattr(strip, "transform", None)
    if transform:
        try:
            if "offset_x" in t:
                setattr(transform, "offset_x", t.get("offset_x", 0.0))
            if "offset_y" in t:
                setattr(transform, "offset_y", t.get("offset_y", 0.0))
            if "scale_x" in t:
                setattr(transform, "scale_x", t.get("scale_x", 1.0))
            if "scale_y" in t:
                setattr(transform, "scale_y", t.get("scale_y", 1.0))
        except Exception:
            pass
