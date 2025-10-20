# zm_stream.py
# -----------------------------------------------
# Zeta Motion - Stream management module
# Controla los procesos Live View y VSE Preview
# usando gphoto2 + ffmpeg/ffplay
# -----------------------------------------------

import bpy
import subprocess
import os
import signal
from . import state, zm_camera

# Procesos activos en runtime (gphoto2 + ffplay/ffmpeg corren en el mismo pgid)
stream_processes = {
    "live_view": None,
    "vse_preview": None,
}

# ----------------------------------------------------------------
# FUNCIONES DE CONTROL DE STREAM
# ----------------------------------------------------------------

def stop_all_streams():
    """Detiene todos los procesos activos de stream (ffplay, ffmpeg, gphoto2)."""
    for key, proc in stream_processes.items():
        if proc and proc.poll() is None:
            try:
                # Matar grupo de procesos para incluir gphoto2 y ffplay/ffmpeg
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                print(f"[Zeta Motion] {key} stream detenido.")
            except Exception as e:
                print(f"[Zeta Motion] Error deteniendo {key}: {e}")
        stream_processes[key] = None

    state.control_state["stream"]["method"] = "none"
    print("[Zeta Motion] All streams stopped.")

# ----------------------------------------------------------------
# Live View (ffplay) - visible, no files
# ----------------------------------------------------------------
def start_live_view(context):
    """Inicia el Live View: muestra la imagen en tiempo real (ventana visible)."""
    # Si ya está corriendo el mismo modo, no hacemos nada
    if state.control_state["stream"].get("method") == "ffplay":
        print("[Zeta Motion] Live View already active.")
        return

    # Si otro modo está activo, detenlo primero
    stop_all_streams()

    # Verificar cámara activa
    cam = zm_camera.get_active_camera()
    if not cam:
        print("[Zeta Motion] No active camera. Please detect and connect a camera first.")
        return

    # Comando que abre ffplay en ventana visible y consume stdout de gphoto2
    cmd = [
        "bash", "-c",
        "gphoto2 --set-config viewfinder=1 --capture-movie --stdout | ffplay -window_title 'Zeta Live View' -f mjpeg -"
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            preexec_fn=os.setsid,  # crea nuevo grupo
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        stream_processes["live_view"] = proc
        state.control_state["stream"]["method"] = "ffplay"
        print("[Zeta Motion] Live View started (ffplay window).")
    except Exception as e:
        print(f"[Zeta Motion] Error starting Live View: {e}")

# ----------------------------------------------------------------
# VSE Preview (ffmpeg) - silent, writes preview.jpg continuously
# ----------------------------------------------------------------
def start_vse_preview(context):
    """Inicia el stream continuo para el VSE Preview. Sobrescribe preview.jpg continuamente."""
    # Si ya está corriendo el mismo modo, no hacemos nada
    if state.control_state["stream"].get("method") == "vse":
        print("[Zeta Motion] VSE Preview already active.")
        return

    # Si otro modo está activo, detenlo primero
    stop_all_streams()

    # Verificar cámara activa
    cam = zm_camera.get_active_camera()
    if not cam:
        print("[Zeta Motion] No active camera. Please detect and connect a camera first.")
        return

    # Obtener ruta de carpeta desde la escena
    scene = context.scene
    dir_path = bpy.path.abspath(getattr(scene, "zm_preview_path", "//"))
    if not dir_path:
        print(f"[Zeta Motion] Error: preview path not set.")
        return
    # Si la propiedad apunta a un archivo en vez de carpeta, tomar su carpeta
    if os.path.isfile(dir_path):
        dir_path = os.path.dirname(dir_path)

    # Debe existir la carpeta (no la creamos arbitrariamente; avisamos al usuario)
    if not os.path.isdir(dir_path):
        print(f"[Zeta Motion] Error: preview folder does not exist: {dir_path}")
        return

    output_path = os.path.join(dir_path, "preview.jpg")

    cmd = [
        "bash", "-c",
        f"gphoto2 --set-config viewfinder=1 --capture-movie --stdout | "
        f"ffmpeg -y -f mjpeg -i - -vf fps=1 -update 1 '{output_path}'"
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        stream_processes["vse_preview"] = proc
        state.control_state["stream"]["method"] = "vse"
        print(f"[Zeta Motion] VSE Preview started (writing: {output_path}).")
    except Exception as e:
        print(f"[Zeta Motion] Error starting VSE Preview: {e}")

# ----------------------------------------------------------------
# OPERADORES
# ----------------------------------------------------------------

class ZM_OT_StartLiveView(bpy.types.Operator):
    """Start Live View (ffplay)"""
    bl_idname = "zm.start_live_view"
    bl_label = "Live View"

    def execute(self, context):
        start_live_view(context)
        return {'FINISHED'}


class ZM_OT_StartVSEPreview(bpy.types.Operator):
    """Start VSE Preview (ffmpeg -> preview.jpg)"""
    bl_idname = "zm.start_vse_preview"
    bl_label = "VSE Preview"

    def execute(self, context):
        # Inicia el stream VSE (zm_stream maneja ffmpeg/gphoto2)
        start_vse_preview(context)

        # Fuerza inmediatamente la creación o refresco del strip de preview
        # Importamos aquí para evitar dependencias circulares
        try:
            from . import zm_preview
            zm_preview.refresh_preview_strip(context)
        except Exception as e:
            print("[Zeta Motion] Warning: zm_preview.refresh_preview_strip failed:", e)

        return {'FINISHED'}


class ZM_OT_StopStreams(bpy.types.Operator):
    """Stop all streams"""
    bl_idname = "zm.stop_streams"
    bl_label = "Stop Streams"

    def execute(self, context):
        stop_all_streams()
        return {'FINISHED'}


# ----------------------------------------------------------------
# REGISTRO
# ----------------------------------------------------------------

classes = (
    ZM_OT_StartLiveView,
    ZM_OT_StartVSEPreview,
    ZM_OT_StopStreams,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[Zeta Motion] zm_stream registered.")


def unregister():
    # Ensure processes are killed
    stop_all_streams()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[Zeta Motion] zm_stream unregistered.")
