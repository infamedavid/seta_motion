# zm_settings.py — Zeta Motion
# Blender 4.5+ | Linux-only
# Camera settings intelligence: querying, parsing, and constants.

import bpy
from . import zm_worker, state

# --- CORREGIDO: Diccionario de rutas directas para la Canon EOS 4000D ---
PARAM_PATHS = {
    "iso": "/main/imgsettings/iso",
    "aperture": "/main/capturesettings/aperture",
    "shutterspeed": "/main/capturesettings/shutterspeed",
    "imageformat": "/main/imgsettings/imageformat",
}

# --- Mapa de correspondencia para resoluciones (sin cambios) ---
RESOLUTION_MAP = {
    "Large Fine": {"label": "4K+ JPEG", "width": 6000, "height": 4000},
    "Large Normal": {"label": "4K+ JPEG (Normal)", "width": 6000, "height": 4000},
    "Medium Fine": {"label": "2K JPEG", "width": 3984, "height": 2656},
    "Medium Normal": {"label": "2K JPEG (Normal)", "width": 3984, "height": 2656},
    "Small": {"label": "1K JPEG", "width": 2976, "height": 1984},
    "RAW": {"label": "RAW", "width": 6000, "height": 4000},
}

def get_resolution_data(gphoto_format_name):
    for key in sorted(RESOLUTION_MAP.keys(), key=len, reverse=True):
        if key in gphoto_format_name:
            return RESOLUTION_MAP[key]
    return None

def parse_gphoto_output(output):
    current_value = None; choices = []
    if output is None: return None, []
    for line in output.splitlines():
        if line.startswith("Current:"): current_value = line.split(":", 1)[1].strip()
        elif line.startswith("Choice:"):
            parts = line.split(maxsplit=2)
            if len(parts) == 3: choices.append(parts[2])
    return current_value, choices

def get_gphoto_config(param_name, on_result_callback):
    """
    CORREGIDO: Ya no prueba múltiples rutas. Va directamente a la ruta correcta
    y encola una única solicitud de lectura en el worker.
    """
    path = PARAM_PATHS.get(param_name)
    if not path:
        print(f"⚠️ [Zeta Motion Settings] No hay una ruta definida para '{param_name}'.")
        on_result_callback(param_name, None, [])
        return

    command = f"gphoto2 --get-config '{path}'"
    
    def worker_callback(stdout, stderr):
        if stdout:
            current, choices = parse_gphoto_output(stdout)
            if choices:
                on_result_callback(param_name, current, choices)
                return
        
        # Si falló o no devolvió opciones
        print(f"⚠️ [Zeta Motion Settings] La consulta para '{param_name}' falló o no devolvió opciones.")
        on_result_callback(param_name, None, [])

    # Encolamos la única consulta necesaria en el worker
    zm_worker.enqueue_command(command, retries=1, callback=worker_callback)