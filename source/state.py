# state.py — Zeta Motion 0.5.0
# Blender 4.5+ | Linux-only
# Global control state for cameras and system

control_state = {
    "camera": {
        "available": [],       # dtected cameras [{"model": "...", "port": "..."}]
        "active_name": None,   # camera to send commands
        "active_port": None,   # active camera port
    },
    "system": {
        "connected": False,    # conecction state
    },

    # Stream state: only this key is required to know if a stream is active
    "stream": {
        "method": "none",      # "none", "ffplay", "vse"
        "paused_method": "none", # relaunch the  running method
    },
}