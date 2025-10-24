# zm_camera.py — Camera detection and connection logic
# Blender 4.5+ | Linux-only

import subprocess
from . import state, zm_stream, zm_settings

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

        with state.state_lock:
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

def connect_camera(camera_dict):
    """
    Conecta la cámara seleccionada, detiene streams activos, y lanza la consulta
    asíncrona y serializada de todos sus ajustes.
    """
    if not camera_dict:
        print("[Zeta Motion] No camera selected to connect.")
        return
        
    print(f"[Zeta Motion] Conectando a {camera_dict['model']}...")
    zm_stream.stop_all_streams()

    with state.state_lock:
        state.control_state["camera"]["active_name"] = camera_dict["model"]
        state.control_state["camera"]["active_port"] = camera_dict["port"]
        state.control_state["system"]["connected"] = True
    
    print(f"[Zeta Motion] Cámara conectada. Iniciando consulta de ajustes...")

    params_to_query = list(state.control_state["camera"]["settings"]["choices"].keys())
    
    def _query_chain_callback(param_name, current_value, choices_list):
        """Callback que se ejecuta al recibir un resultado y lanza la siguiente consulta."""
        print(f"↳ Recibido resultado para '{param_name}': Current='{current_value}', Choices={len(choices_list)}")
        with state.state_lock:
            state.control_state["camera"]["settings"]["choices"][param_name] = choices_list
            state.control_state["camera"]["settings"]["current"][param_name] = current_value
            state.control_state["camera"]["settings"]["desired"][param_name] = current_value
        
        if params_to_query:
            next_param = params_to_query.pop(0)
            print(f"→ Solicitando configuración para '{next_param}'...")
            zm_settings.get_gphoto_config(next_param, _query_chain_callback)
        else:
            print("[Zeta Motion] Consulta de todos los ajustes finalizada.")

    # Iniciar la cadena de consultas con el primer parámetro
    if params_to_query:
        first_param = params_to_query.pop(0)
        print(f"→ Solicitando configuración para '{first_param}'...")
        zm_settings.get_gphoto_config(first_param, _query_chain_callback)

def get_active_camera():
    """Return the active camera dictionary or None."""
    cams = state.control_state["camera"].get("available", [])
    active = state.control_state["camera"].get("active_name")
    for c in cams:
        if c["model"] == active:
            return c
    return None

def register():
    print("[Zeta Motion] zm_camera registered.")

def unregister():
    print("[Zeta Motion] zm_camera unregistered.")