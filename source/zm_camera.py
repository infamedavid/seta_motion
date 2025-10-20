# zm_camera.py — Camera detection and connection logic
# Blender 4.5+ | Linux-only

import subprocess
from . import state

# -----------------------------------------------------------------------------
# Camera detection
# -----------------------------------------------------------------------------
def detect_cameras():
    """Detect available cameras using gphoto2 and store their info."""
    try:
        result = subprocess.run(
            ["gphoto2", "--auto-detect"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        lines = result.stdout.strip().splitlines()

        cams = []
        for line in lines[2:]:
            if line.strip():
                parts = line.strip().rsplit(None, 1)
                if len(parts) == 2:
                    model, port = parts
                    cams.append({"model": model.strip(), "port": port.strip()})

        state.control_state["camera"]["available"] = cams
        print(f"[Zeta Motion] Cameras detected: {cams}")
        return cams

    except subprocess.TimeoutExpired:
        print("[Zeta Motion] Timeout while detecting cameras.")
        return []
    except FileNotFoundError:
        print("[Zeta Motion] gphoto2 not found. Install it with 'sudo apt install gphoto2'.")
        return []
    except Exception as e:
        print(f"[Zeta Motion] Error detecting cameras: {e}")
        return []

# -----------------------------------------------------------------------------
# Camera connection
# -----------------------------------------------------------------------------
def connect_camera(camera_dict):
    """Connect the selected camera and store its state."""
    if not camera_dict:
        print("[Zeta Motion] No camera selected.")
        return

    state.control_state["camera"]["active_name"] = camera_dict["model"]
    state.control_state["camera"]["active_port"] = camera_dict["port"]
    state.control_state["system"]["connected"] = True
    print(f"[Zeta Motion] Camera connected: {camera_dict['model']} ({camera_dict['port']})")

def get_active_camera():
    """Return the active camera dictionary or None."""
    cams = state.control_state["camera"].get("available", [])
    active = state.control_state["camera"].get("active_name")
    for c in cams:
        if c["model"] == active:
            return c
    return None

# --- Blender registration (minimal: module has register/unregister) ---
def register():
    print("[Zeta Motion] zm_camera registered.")

def unregister():
    print("[Zeta Motion] zm_camera unregistered.")
