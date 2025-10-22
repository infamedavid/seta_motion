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
    "live_blend": None,
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
# Función de Stream Unificada (Normal y Blend)
# ----------------------------------------------------------------
def start_live_stream(context, image_path=None, blend_factor=0.5):
    """
    Inicia el stream de la cámara.
    - Si image_path es None, inicia el Live View estándar.
    - Si image_path se proporciona, inicia el modo Live Blend.
    """
    stop_all_streams()

    cam = zm_camera.get_active_camera()
    if not cam:
        print("[Zeta Motion] No active camera for stream.")
        return

    # Lógica para modo Blend
    if image_path and os.path.exists(image_path):
        print(f"[Zeta Motion] Live Blend started (Overlaying: {os.path.basename(image_path)}).")
        stream_key = "live_blend"
        state.control_state["stream"]["method"] = "live_blend"
        
        cmd_str_core = (
            f"gphoto2 --set-config viewfinder=1 --capture-movie --stdout | "
            f"ffmpeg -f mjpeg -i - -loop 1 -i '{image_path}' "
            f"-filter_complex \"[1:v]format=yuv420p[bg];[0:v]format=yuv420p[cam];[bg][cam]scale2ref[bg_scaled][cam_ref];[cam_ref][bg_scaled]blend=all_mode=overlay:all_opacity={blend_factor}\" "
            f"-f mjpeg - | ffplay -window_title 'Zeta Live Blend' -"
        )
    # Lógica para modo Normal (fallback)
    else:
        print("[Zeta Motion] Live View started (ffplay window).")
        stream_key = "live_view"
        state.control_state["stream"]["method"] = "ffplay"
        cmd_str_core = "gphoto2 --set-config viewfinder=1 --capture-movie --stdout | ffplay -window_title 'Zeta Live View' -f mjpeg -"

    # Ejecución del comando
    cmd = ["bash", "-c", "set -m; exec " + cmd_str_core]
    try:
        proc = subprocess.Popen(
            cmd,
            preexec_fn=os.setsid,
            stdout=None,
            stderr=None
        )
        stream_processes[stream_key] = proc
    except Exception as e:
        print(f"[Zeta Motion] Error starting stream: {e}")


# ----------------------------------------------------------------
# VSE Preview (ffmpeg) - silent, writes preview.jpg continuously
# ----------------------------------------------------------------
def start_vse_preview(context):
    """Inicia el stream continuo para el VSE Preview. Sobrescribe preview.jpg continuamente."""
    if state.control_state["stream"].get("method") == "vse":
        print("[Zeta Motion] VSE Preview already active.")
        return

    stop_all_streams()

    cam = zm_camera.get_active_camera()
    if not cam:
        print("[Zeta Motion] No active camera. Please detect and connect a camera first.")
        return

    scene = context.scene
    dir_path = bpy.path.abspath(getattr(scene, "zm_preview_path", "//"))
    if not dir_path or not os.path.isdir(os.path.dirname(bpy.path.abspath(dir_path))):
        print(f"[Zeta Motion] Error: preview path is not a valid directory.")
        return

    if os.path.isfile(dir_path):
        dir_path = os.path.dirname(dir_path)

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
            cmd, preexec_fn=os.setsid, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        stream_processes["vse_preview"] = proc
        state.control_state["stream"]["method"] = "vse"
        print(f"[Zeta Motion] VSE Preview started (writing: {output_path}).")
    except Exception as e:
        print(f"[Zeta Motion] Error starting VSE Preview: {e}")

# ----------------------------------------------------------------
# OPERADORES
# ----------------------------------------------------------------

class ZM_OT_StartVSEPreview(bpy.types.Operator):
    bl_idname = "zm.start_vse_preview"
    bl_label = "VSE Preview"

    def execute(self, context):
        start_vse_preview(context)
        try:
            from . import zm_preview
            zm_preview.refresh_preview_strip(context)
        except Exception as e:
            print("[Zeta Motion] Warning: zm_preview.refresh_preview_strip failed:", e)
        return {'FINISHED'}


class ZM_OT_StopStreams(bpy.types.Operator):
    bl_idname = "zm.stop_streams"
    bl_label = "Stop Streams"

    def execute(self, context):
        stop_all_streams()
        return {'FINISHED'}

# ----------------------------------------------------------------
# REGISTRO
# ----------------------------------------------------------------

classes = (
    ZM_OT_StartVSEPreview,
    ZM_OT_StopStreams,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[Zeta Motion] zm_stream registered.")

def unregister():
    stop_all_streams()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[Zeta Motion] zm_stream unregistered.")