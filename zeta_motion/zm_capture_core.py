# zm_capture_core.py
import bpy
import subprocess
import os
import datetime
from .state import control_state

def capture_image(output_path, camera_device=None):
    """
    Captura una imagen desde gphoto2 y la guarda en output_path.
    Devuelve True si la captura fue exitosa, False si hubo error.
    """
    try:
        cmd = ["gphoto2", "--capture-image-and-download", "--filename", output_path]
        if camera_device:
            cmd.extend(["--camera", camera_device])
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ZETA MOTION] Error al capturar imagen: {e.stderr.decode('utf-8').strip()}")
        return False


def register_snapshot(scene, filepath):
    """
    Actualiza el snapshot global y la referencia en la escena.
    """
    control_state["preview"]["last_filename"] = filepath
    scene.zm_preview_snapshot = filepath


def build_output_path(scene, prefix="frame"):
    """
    Genera un nombre de archivo con timestamp dentro del directorio de salida de Zeta Motion.
    """
    directory = bpy.path.abspath(scene.zm_output_dir)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.jpg"

    return os.path.join(directory, filename)
