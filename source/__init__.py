# __init__.py — Zeta Motion 0.5.0
# Blender 4.5+ | Linux-only build

bl_info = {
    "name": "Zeta Motion",
    "description": "Stop Motion & Camera Capture System — Integration with gphoto2",
    "author": "infame",
    "version": (0, 5, 0),
    "blender": (4, 5, 0),
    "location": "Properties > Scene > Camera Setup",
    "category": "Animation",
}

import bpy
import sys
import importlib

# --- Linux-only check ---
if sys.platform != "linux":
    raise EnvironmentError("Zeta Motion is only supported on Linux at the moment.")

# --- Import internal modules ---
from . import (
    state,
    zm_camera,
    zm_stream,
    zm_ui,
    zm_movie,
    zm_preview,
    zm_convert,
    zm_movie_source,
)

modules = {
    "state": state,
    "zm_camera": zm_camera,
    "zm_stream": zm_stream,
    "zm_ui": zm_ui,
    "zm_movie": zm_movie,
    "zm_preview": zm_preview,
    "zm_convert": zm_convert,
    "zm_movie_source": zm_movie_source
}

# --- Hot reload for development: reload modules to pick up edits ---
for name, module in modules.items():
    importlib.reload(module)

# --- Register / Unregister ---
def register():
    # Register backend modules
    if hasattr(zm_camera, "register"):
        zm_camera.register()
    if hasattr(zm_stream, "register"):
        zm_stream.register()
    if hasattr(zm_movie, "register"): # Registramos el nuevo módulo de película
        zm_movie.register()
    if hasattr(zm_preview, "register"):
        zm_preview.register()
    
    
    # UI must be registered last
    if hasattr(zm_ui, "register"):
        zm_ui.register()

    # Scene properties (used by UI)
    bpy.types.Scene.zm_camera_list = bpy.props.EnumProperty(
        name="Camera",
        description="Available cameras detected via gphoto2",
        items=lambda self, context: zm_ui.update_camera_list(),
    )
    bpy.types.Scene.zm_preview_path = bpy.props.StringProperty(
        name="Preview Path",
        description="Folder where temporary preview images will be stored (use an existing folder).",
        subtype='DIR_PATH',
        default=""
    )
    # MODIFICADO: para aceptar nombre base de archivo
    bpy.types.Scene.zm_capture_path = bpy.props.StringProperty(
        name="Capture Path / Base Name",
        description="Folder for final captures, or a full path with a base name (e.g., /path/to/my_movie)",
        subtype='FILE_PATH', # CAMBIO a FILE_PATH
        default=""
    )

    # NUEVO: Propiedades para el panel de Stop Motion Movie
    bpy.types.Scene.zm_movie_length = bpy.props.IntProperty(
        name="Strip Length",
        description="Total number of frames for the stop motion sequence",
        default=24,
        min=1,
    )
    bpy.types.Scene.zm_movie_overwrite = bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="If enabled, overwrites existing frames from the beginning. If disabled, extends the sequence",
        default=False,
    )

    # NEW: proxy scale preference used by conversion/swap (25/50/75)
    bpy.types.Scene.zm_proxy_scale = bpy.props.EnumProperty(
        name="Proxy Scale",
        description="Scale to generate proxies (percentage)",
        items=[
            ('25', "25%", "Generate 25% proxy"),
            ('50', "50%", "Generate 50% proxy"),
            ('75', "75%", "Generate 75% proxy"),
        ],
        default='50'
    )

    bpy.types.Scene.zm_live_blend_enabled = bpy.props.BoolProperty(
        name="Enable Live Blend",
        description="Enable Onion Skinning by blending the live feed over the current frame in the VSE",
        default=False,
    )
    bpy.types.Scene.zm_blend_factor = bpy.props.FloatProperty(
        name="Blend Factor",
        description="Opacity of the live camera feed over the still image",
        default=0.5,
        min=0.0,
        max=1.0,
    )

    print("[Zeta Motion] Add-on initialized (Blender 4.5+ / Linux).")

def unregister():
    # Remove scene properties
    props_to_remove = (
        "zm_camera_list", "zm_preview_path", "zm_capture_path",
        "zm_movie_length", "zm_movie_overwrite", "zm_proxy_scale",
        "zm_live_blend_enabled", "zm_blend_factor"
    )
    
    for prop in props_to_remove:
        if hasattr(bpy.types.Scene, prop):
            try:
                delattr(bpy.types.Scene, prop)
            except Exception:
                pass

    # Unregister in reverse order
    if hasattr(zm_ui, "unregister"):
        zm_ui.unregister()
    if hasattr(zm_movie, "unregister"): # Des-registramos el nuevo módulo
        zm_movie.unregister()
    if hasattr(zm_preview, "unregister"):
        zm_preview.unregister()

    if hasattr(zm_stream, "unregister"):
        zm_stream.unregister()
    if hasattr(zm_camera, "unregister"):
        zm_camera.unregister()

    print("[Zeta Motion] Add-on unloaded cleanly.")

if __name__ == "__main__":
    register()
