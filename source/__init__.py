# __init__.py — Zeta Motion
# Blender 4.5+ | Linux-only build

bl_info = {
    "name": "Zeta Motion",
    "description": "Stop Motion & Camera Capture System — Integration with gphoto2",
    "author": "infame",
    "version": (0.7, 2), # Versión incrementada para reflejar corrección
    "blender": (4, 5, 0),
    "location": "Properties > Scene > Camera Setup",
    "category": "Animation",
}

import bpy
import sys
import time
import importlib

# --- Linux-only check ---
if sys.platform != "linux":
    raise EnvironmentError("Zeta Motion is only supported on Linux at the moment.")

# --- Import internal modules ---
from . import (
    state, zm_camera, zm_stream, zm_ui, zm_movie,
    zm_preview, zm_convert, zm_movie_source, zm_worker, zm_settings,
    zm_foto # <--- AÑADIR ESTA LÍNEA
)

modules = {
    "state": state, "zm_camera": zm_camera, "zm_stream": zm_stream,
    "zm_ui": zm_ui, "zm_movie": zm_movie, "zm_preview": zm_preview,
    "zm_convert": zm_convert, "zm_movie_source": zm_movie_source,
    "zm_worker": zm_worker, "zm_settings": zm_settings,
    "zm_foto": zm_foto, # <--- AÑADIR ESTA LÍNEA
}

# --- Hot reload for development ---
for name, module in modules.items():
    importlib.reload(module)

# -----------------------------------------------------------------------------
# --- LÓGICA DE PROPIEDADES DE CÁMARA Y SINCRONIZACIÓN ---
# -----------------------------------------------------------------------------

# --- Funciones 'items' para EnumProperty (sin cambios) ---
def get_iso_items(self, context):
    opts = state.control_state["camera"]["settings"]["choices"].get("iso", [])
    return [(opt, opt, "") for opt in opts] if opts else [("NONE", "N/A", "")]
def get_aperture_items(self, context):
    opts = state.control_state["camera"]["settings"]["choices"].get("aperture", [])
    return [(opt, opt, "") for opt in opts] if opts else [("NONE", "N/A", "")]
def get_shutterspeed_items(self, context):
    opts = state.control_state["camera"]["settings"]["choices"].get("shutterspeed", [])
    return [(opt, opt, "") for opt in opts] if opts else [("NONE", "N/A", "")]
def get_imageformat_items(self, context):
    opts = state.control_state["camera"]["settings"]["choices"].get("imageformat", [])
    if not opts: return [("NONE", "N/A", "")]
    items = []
    for opt in opts:
        res_data = zm_settings.get_resolution_data(opt)
        label = res_data["label"] if res_data else opt
        items.append((opt, label, f"Set camera format to {opt}"))
    return items

# --- Funciones 'update' (sin cambios) ---
def _sync_blender_resolution(scene, gphoto_format_name):
    res_data = zm_settings.get_resolution_data(gphoto_format_name)
    if res_data:
        scene.render.resolution_x = res_data["width"]
        scene.render.resolution_y = res_data["height"]
        scene.render.pixel_aspect_x = 1; scene.render.pixel_aspect_y = 1
        print(f"[Zeta Motion] Render resolution set to {res_data['width']}x{res_data['height']}")
def _update_camera_setting(self, context, param_name):
    prop_map = {
        "iso": "zm_iso_setting", "aperture": "zm_aperture_setting",
        "shutterspeed": "zm_shutterspeed_setting", "imageformat": "zm_imageformat_setting",
    }
    new_value = getattr(context.scene, prop_map[param_name])
    with state.state_lock:
        state.control_state["camera"]["settings"]["desired"][param_name] = new_value
    if param_name == "imageformat":
        _sync_blender_resolution(context.scene, new_value)
def _update_iso(self, context): _update_camera_setting(self, context, "iso")
def _update_aperture(self, context): _update_camera_setting(self, context, "aperture")
def _update_shutterspeed(self, context): _update_camera_setting(self, context, "shutterspeed")
def _update_imageformat(self, context): _update_camera_setting(self, context, "imageformat")

# --- Temporizador de Sincronización ---
_last_sync_time = 0.0
def _settings_sync_timer():
    global _last_sync_time
    now = time.time()
    if now - _last_sync_time < 0.5: return 0.5
    with state.state_lock:
        desired = state.control_state["camera"]["settings"]["desired"]
        current = state.control_state["camera"]["settings"]["current"]
        params_to_update = { k: v for k, v in desired.items() if v is not None and v != current.get(k) }
        if params_to_update:
            print(f"[Zeta Motion Sync] Cambios detectados: {params_to_update}")
            for param, value in params_to_update.items():
                # --- CORREGIDO: Usar la nueva estructura de PARAM_PATHS ---
                config_path = zm_settings.PARAM_PATHS.get(param) # Ya no es una lista
                if config_path:
                    command = f"gphoto2 --set-config '{config_path}={value}'"
                    zm_worker.enqueue_command(command)
                    current[param] = value
            _last_sync_time = now
    return 0.5

# --- Register / Unregister ---
def register():
    zm_worker.start_worker()
    if hasattr(zm_camera, "register"): zm_camera.register()
    if hasattr(zm_stream, "register"): zm_stream.register()
    if hasattr(zm_movie, "register"): zm_movie.register()
    if hasattr(zm_preview, "register"): zm_preview.register()
    if hasattr(zm_foto, "register"): zm_foto.register() # <--- AÑADIR ESTA LÍNEA
    if hasattr(zm_ui, "register"): zm_ui.register()

    # --- Propiedades de Escena (sin cambios) ---
    bpy.types.Scene.zm_camera_list = bpy.props.EnumProperty(name="Camera", items=lambda self, context: zm_ui.update_camera_list())
    bpy.types.Scene.zm_preview_path = bpy.props.StringProperty(name="Preview Path", subtype='DIR_PATH', default="")
    bpy.types.Scene.zm_capture_path = bpy.props.StringProperty(name="Capture Path / Base Name", subtype='FILE_PATH', default="")
    bpy.types.Scene.zm_movie_length = bpy.props.IntProperty(name="Strip Length", default=24, min=1)
    bpy.types.Scene.zm_movie_overwrite = bpy.props.BoolProperty(name="Overwrite Existing", default=False)
    bpy.types.Scene.zm_proxy_scale = bpy.props.EnumProperty(name="Proxy Scale", items=[('25', "25%", ""), ('50', "50%", ""), ('75', "75%", "")], default='50')
    bpy.types.Scene.zm_live_blend_enabled = bpy.props.BoolProperty(name="Enable Live Blend", default=False)
    bpy.types.Scene.zm_blend_factor = bpy.props.FloatProperty(name="Blend Factor", default=0.5, min=0.0, max=1.0)
    bpy.types.Scene.zm_iso_setting = bpy.props.EnumProperty(name="ISO", items=get_iso_items, update=_update_iso)
    bpy.types.Scene.zm_aperture_setting = bpy.props.EnumProperty(name="Aperture", items=get_aperture_items, update=_update_aperture)
    bpy.types.Scene.zm_shutterspeed_setting = bpy.props.EnumProperty(name="Shutter Speed", items=get_shutterspeed_items, update=_update_shutterspeed)
    bpy.types.Scene.zm_imageformat_setting = bpy.props.EnumProperty(name="Resolution", items=get_imageformat_items, update=_update_imageformat)

    bpy.app.timers.register(_settings_sync_timer)
    print("[Zeta Motion] Add-on initialized.")

def unregister():
    if bpy.app.timers.is_registered(_settings_sync_timer): bpy.app.timers.unregister(_settings_sync_timer)
    if hasattr(zm_worker, "stop_worker"): zm_worker.stop_worker()
    props_to_remove = (
        "zm_camera_list", "zm_preview_path", "zm_capture_path", "zm_movie_length", 
        "zm_movie_overwrite", "zm_proxy_scale", "zm_live_blend_enabled", "zm_blend_factor", 
        "zm_iso_setting", "zm_aperture_setting", "zm_shutterspeed_setting", "zm_imageformat_setting",
    )
    for prop in props_to_remove:
        if hasattr(bpy.types.Scene, prop):
            try: delattr(bpy.types.Scene, prop)
            except Exception: pass
    if hasattr(zm_ui, "unregister"): zm_ui.unregister()
    if hasattr(zm_foto, "unregister"): zm_foto.unregister() # <--- AÑADIR ESTA LÍNEA
    if hasattr(zm_movie, "unregister"): zm_movie.unregister()
    if hasattr(zm_preview, "unregister"): zm_preview.unregister()
    if hasattr(zm_stream, "unregister"): zm_stream.unregister()
    if hasattr(zm_camera, "unregister"): zm_camera.unregister()
    print("[Zeta Motion] Add-on unloaded cleanly.")

if __name__ == "__main__":
    register()