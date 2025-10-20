# zm_preview.py — Zeta Motion 0.5.1
# Gestión del Preview Strip y sincronización con VSE (solo manejo de strip)
# Compatible con Blender 4.5+ (Linux-only)

import bpy
import os
from . import state
from . import zm_properties

# ------------------------------------------------------------
# CONSTANTES
# ------------------------------------------------------------
PREVIEW_STRIP_NAME = "ZM_Preview"
PREVIEW_CHANNEL = 20  # Canal reservado para preview
PREVIEW_FILENAME = "preview.jpg"

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------
def get_preview_path(scene):
    """Devuelve la ruta absoluta al archivo preview.jpg.
    Prioriza scene.zm_preview_snapshot (si existe) y luego scene.zm_preview_path.
    Retorna None si no hay ruta válida.
    """
    # Prefer snapshot full path if present
    path_candidate = None
    if hasattr(scene, "zm_preview_snapshot") and scene.zm_preview_snapshot:
        path_candidate = bpy.path.abspath(scene.zm_preview_snapshot)
    else:
        path_candidate = bpy.path.abspath(getattr(scene, "zm_preview_path", "//"))

    if not path_candidate:
        return None

    if os.path.isfile(path_candidate):
        base_dir = os.path.dirname(path_candidate)
    else:
        base_dir = path_candidate

    if not os.path.isdir(base_dir):
        return None

    return os.path.join(base_dir, PREVIEW_FILENAME)

def find_existing_preview_strip(scene):
    """Busca el strip existente de preview:
    - Primero por escena.zm_preview_strip_name
    - Luego por nombre PREVIEW_STRIP_NAME en PREVIEW_CHANNEL
    Retorna strip o None.
    """
    seq = getattr(scene, "sequence_editor", None)
    if not seq:
        return None
    seq_all = getattr(seq, "sequences_all", None)
    if not seq_all:
        return None

    stored = getattr(scene, "zm_preview_strip_name", "")
    if stored:
        for s in seq_all:
            if s.name == stored:
                return s

    # fallback: search by canonical name + channel
    for s in seq_all:
        if s.name == PREVIEW_STRIP_NAME and getattr(s, "channel", None) == PREVIEW_CHANNEL:
            return s
    return None

# ------------------------------------------------------------
# CREACIÓN / DESTRUCCIÓN
# ------------------------------------------------------------
def _create_image_strip(scene, filepath, channel=None, frame_start=None, frame_duration=1, props_data=None):
    """Crea un strip de imagen apuntando a `filepath`.
    Aplica props_data si se proporciona (pasado a zm_properties.apply_strip_properties).
    Guarda scene.zm_preview_strip_name con el nombre del strip creado.
    """
    if not filepath:
        print("[Zeta Motion] _create_image_strip: no filepath provided")
        return None

    # Crear sequence editor si falta (en main thread)
    if not getattr(scene, "sequence_editor", None):
        try:
            scene.sequence_editor_create()
        except Exception as e:
            print("[Zeta Motion] _create_image_strip: cannot create sequence editor:", e)
            return None

    # channel / frame defaults
    ch = PREVIEW_CHANNEL if channel is None else int(channel)
    start = int(scene.frame_current) if frame_start is None else int(frame_start)
    duration = int(frame_duration) if frame_duration else 1

    try:
        strip = scene.sequence_editor.sequences.new_image(
            name=PREVIEW_STRIP_NAME,
            filepath=filepath,
            channel=ch,
            frame_start=start,
        )
    except Exception as e:
        print("[Zeta Motion] Error creating image strip:", e)
        # fallback: try with just name and minimal params
        try:
            strip = scene.sequence_editor.sequences.new_image(
                name=PREVIEW_STRIP_NAME,
                filepath=filepath,
                channel=ch,
                frame_start=start
            )
        except Exception as e2:
            print("[Zeta Motion] Fatal: cannot create preview strip:", e2)
            return None

    # frame/duration and default visuals
    try:
        strip.frame_final_duration = duration
    except Exception:
        pass
    try:
        strip.blend_type = 'ALPHA_OVER'
        strip.blend_alpha = 0.5
    except Exception:
        pass

    # assign elements filename as basename to avoid absolute path caching issues
    try:
        strip.elements[0].filename = os.path.basename(filepath)
    except Exception:
        pass

    # apply saved properties if any
    if props_data:
        try:
            zm_properties.apply_strip_properties(strip, props_data)
        except Exception as e:
            print("[Zeta Motion] Warning: apply_strip_properties failed:", e)

    # persist name
    scene.zm_preview_strip_name = strip.name
    print(f"[Zeta Motion] Created preview strip '{strip.name}' -> {filepath}")
    return strip

def _destroy_strip(scene, strip):
    """Elimina únicamente el strip proporcionado si existe."""
    if not strip:
        return False
    try:
        seq = scene.sequence_editor
        if seq:
            # remove by reference
            seq.sequences.remove(strip)
            print(f"[Zeta Motion] Destroyed preview strip '{getattr(strip, 'name', '<unknown>')}'")
            return True
    except Exception as e:
        print("[Zeta Motion] Error removing preview strip:", e)
    return False

# ------------------------------------------------------------
# API pública
# ------------------------------------------------------------
def ensure_preview_strip(scene):
    """Asegura que exista un preview strip válido.
    - Si existe y path es válido, actualiza filename y retorna strip.
    - Si no existe, intenta crear usando cached props o defaults.
    """
    path = get_preview_path(scene)
    if not path:
        print("[Zeta Motion] ensure_preview_strip: invalid preview path.")
        return None

    strip = find_existing_preview_strip(scene)
    if strip and os.path.exists(path):
        # Update element filename in case Blender lost reference
        try:
            strip.elements[0].filename = os.path.basename(path)
        except Exception:
            pass
        scene.zm_preview_strip_name = strip.name
        return strip

    # Create new strip, try using cached properties if available
    props = zm_properties.cached_data.get("preview", None)
    new_strip = _create_image_strip(scene, path, props_data=props)
    return new_strip

def refresh_preview_strip(context):
    """Forzar refresco del preview strip destruyéndolo y recreándolo.
    - Mantiene channel, frame_start y frame_final_duration del strip anterior si existía.
    - Restaura propiedades guardadas mediante zm_properties.
    - Actualiza scene.zm_preview_strip_name con el nuevo nombre.
    """
    scene = context.scene
    path = get_preview_path(scene)
    if not path:
        print("[Zeta Motion] refresh_preview_strip: invalid preview path.")
        return None

    # Ensure sequence editor exists
    if not getattr(scene, "sequence_editor", None):
        try:
            scene.sequence_editor_create()
        except Exception as e:
            print("[Zeta Motion] refresh_preview_strip: cannot create sequence editor:", e)
            return None

    # old strip snapshot
    old_strip = find_existing_preview_strip(scene)
    props_snapshot = None
    channel = PREVIEW_CHANNEL
    frame_start = scene.frame_current
    frame_duration = 1

    if old_strip:
        try:
            props_snapshot = zm_properties.store_strip_properties(old_strip)
        except Exception as e:
            print("[Zeta Motion] Warning: store_strip_properties failed:", e)
            props_snapshot = None

        try:
            channel = int(getattr(old_strip, "channel", PREVIEW_CHANNEL))
        except Exception:
            channel = PREVIEW_CHANNEL
        try:
            frame_start = int(getattr(old_strip, "frame_start", scene.frame_current))
        except Exception:
            frame_start = scene.frame_current
        try:
            frame_duration = int(getattr(old_strip, "frame_final_duration", 1))
        except Exception:
            frame_duration = 1

        # destroy old strip (mandatory)
        _destroy_strip(scene, old_strip)

    # Create new strip with same parameters
    new_strip = _create_image_strip(scene, path, channel=channel, frame_start=frame_start, frame_duration=frame_duration, props_data=props_snapshot)

    # If creation failed with props, try without props
    if not new_strip:
        new_strip = _create_image_strip(scene, path, channel=channel, frame_start=frame_start, frame_duration=frame_duration, props_data=None)

    if new_strip:
        scene.zm_preview_strip_name = new_strip.name
    else:
        print("[Zeta Motion] Failed to create preview strip during refresh.")

    return new_strip

def destroy_preview_strip(scene):
    """Destruye el strip identificado en scene.zm_preview_strip_name si existe."""
    strip = find_existing_preview_strip(scene)
    if not strip:
        return False
    ok = _destroy_strip(scene, strip)
    if ok:
        # clear stored name
        try:
            scene.zm_preview_strip_name = ""
        except Exception:
            pass
    return ok

# ------------------------------------------------------------
# registro mínimo
# ------------------------------------------------------------
def register():
    # propiedad para persistir nombre del strip
    bpy.types.Scene.zm_preview_strip_name = bpy.props.StringProperty(
        name="Preview Strip Name",
        description="Identificador del strip de preview activo"
    )
    print("[Zeta Motion] zm_preview registered.")

def unregister():
    if hasattr(bpy.types.Scene, "zm_preview_strip_name"):
        try:
            delattr(bpy.types.Scene, "zm_preview_strip_name")
        except Exception:
            pass
    print("[Zeta Motion] zm_preview unregistered.")
