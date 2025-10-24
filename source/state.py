# state.py — Zeta Motion
# Blender 4.5+ | Linux-only
# Global control state for cameras and system

import threading

# --- REFUERZO: Lock para proteger escrituras al estado desde hilos ---
state_lock = threading.Lock()

control_state = {
    "camera": {
        "available": [],       # dtected cameras [{"model": "...", "port": "..."}]
        "active_name": None,   # camera to send commands
        "active_port": None,   # active camera port
        
        # --- NUEVO: Estructura para gestionar los ajustes de la cámara ---
        "settings": {
            # Opciones disponibles leídas de la cámara (ej: ['100','200','400'])
            "choices": {
                "iso": [],
                "aperture": [],
                "shutterspeed": [],
                "imageformat": [],
            },
            # Valor deseado por el usuario desde la UI
            "desired": {
                "iso": None,
                "aperture": None,
                "shutterspeed": None,
                "imageformat": None,
            },
            # Último valor confirmado/enviado a la cámara
            "current": {
                "iso": None,
                "aperture": None,
                "shutterspeed": None,
                "imageformat": None,
            }
        }
    },
    "system": {
        "connected": False,    # conecction state
    },

    # Stream state: only this key is required to know if a stream is active
    "stream": {
        "method": "none",      # "none", "ffplay", "vse", "live_blend"
        "paused_method": "none", # relaunch the  running method
    },
}