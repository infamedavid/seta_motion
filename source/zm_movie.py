# zm_movie.py — Zeta Motion 0.5.5
# Blender 4.5+ | Linux-only
# Movie sequence creation and management with placeholders and VSE strip.

import bpy
import time
import subprocess
import threading
import os

# Pillow es una dependencia externa. Se asume que está instalada.
try:
    from PIL import Image
except ImportError:
    Image = None

# Módulos internos
from . import state
from . import zm_stream

# --- Estado global para la comunicación entre el operador y el temporizador ---
timer_state = {
    "is_running": False,
    "target_path": None,
    "context": None,
    "base_name": None,
    "directory": None,
}

# -----------------------------------------------------------------------------
# Lógica de Placeholders y VSE Strip
# -----------------------------------------------------------------------------

def _get_image_resolution(image_path):
    """Usa Pillow para obtener las dimensiones de la imagen de referencia."""
    if not Image:
        print("❌ Error: La librería Pillow no está instalada. No se pueden generar placeholders.")
        return None
    try:
        with Image.open(image_path) as img:
            return img.size  # Retorna (ancho, alto)
    except Exception as e:
        print(f"❌ Error al leer la resolución de la imagen de referencia: {e}")
        return None

def _generate_placeholders(directory, base_name, length, resolution, overwrite):
    """Genera imágenes JPEG en blanco como placeholders para la secuencia."""
    if not Image:
        return
        
    width, height = resolution
    color = (255, 255, 255)  # Blanco puro
    
    print(f"[Zeta Motion] Generando {length - 1} placeholders con resolución {width}x{height}...")

    # Creamos placeholders desde el frame 2 hasta el final
    for i in range(2, length + 1):
        filename = f"{base_name}_{i:05d}.jpg"
        filepath = os.path.join(directory, filename)

        # Respetamos la bandera 'overwrite'
        if not overwrite and os.path.exists(filepath):
            continue

        try:
            placeholder_img = Image.new('RGB', (width, height), color)
            placeholder_img.save(filepath, 'JPEG', quality=95)
        except Exception as e:
            print(f"❌ Error al crear el placeholder {filepath}: {e}")
    print("[Zeta Motion] Placeholders generados.")


def _find_available_vse_channel(scene):
    """Encuentra el canal de video más bajo disponible en el VSE."""
    if not scene.sequence_editor:
        return 1
    
    used_channels = {s.channel for s in scene.sequence_editor.sequences}
    channel = 1
    while channel in used_channels:
        channel += 1
    return channel

# --- INICIO DE LA SOLUCIÓN IMPLEMENTADA ---
def _create_vse_strip(context, directory, base_name, length):
    """Crea un strip de secuencia de imágenes (no imagen única) en el VSE."""
    scene = context.scene

    # Asegurar que el editor de secuencias esté disponible
    if not scene.sequence_editor:
        scene.sequence_editor_create()

    # Evitar duplicados
    for s in scene.sequence_editor.sequences:
        if s.name == base_name:
            print(f"[Zeta Motion] ⚠️  El strip '{base_name}' ya existe en el VSE. No se creará uno nuevo.")
            return

    # Buscar canal libre
    channel = _find_available_vse_channel(scene)
    frame_start = scene.frame_current

    # Buscar archivos válidos (JPG numerados)
    image_files = [
        f for f in sorted(os.listdir(directory))
        if f.startswith(base_name + "_") and f.endswith(".jpg")
    ]

    if not image_files:
        print(f"❌ No se encontraron imágenes con prefijo '{base_name}_' en {directory}")
        return

    # Crear strip base con el primer frame
    first_frame_path = os.path.join(directory, image_files[0])
    try:
        strip = scene.sequence_editor.sequences.new_image(
            name=base_name,
            filepath=first_frame_path,
            channel=channel,
            frame_start=frame_start
        )
    except Exception as e:
        print(f"❌ Error al crear el strip base: {e}")
        return

    # Añadir el resto de los frames a la secuencia
    added_count = 1
    for img_name in image_files[1:]:
        filepath = os.path.join(directory, img_name)
        if os.path.exists(filepath):
            try:
                strip.elements.append(filepath)
                added_count += 1
            except Exception as e:
                print(f"❌ Error al añadir {img_name}: {e}")

    # Ajustar duración final del strip
    strip.frame_final_duration = added_count
    print(f"[Zeta Motion] ✅ Strip '{base_name}' creado correctamente en canal {channel} con {added_count} imágenes.")

    # Configurar comportamiento visual estándar
    #strip.use_translation = False
    #strip.use_crop = False
    #strip.use_proxy = False
    strip.animation_offset_start = 0
    strip.animation_offset_end = 0
    strip.frame_still_start = 0
    strip.frame_still_end = 0

    # Mantener el cursor en el primer frame real
    scene.frame_current = frame_start

    print(f"[Zeta Motion] 🎬 Secuencia '{base_name}' añadida al VSE ({added_count} frames).")
# --- FIN DE LA SOLUCIÓN IMPLEMENTADA ---

# -----------------------------------------------------------------------------
# Lógica del Temporizador para Espera Asíncrona
# -----------------------------------------------------------------------------

def _timer_callback():
    """Función llamada por el temporizador de Blender para esperar el archivo."""
    if not timer_state["is_running"]:
        return None

    target_path = timer_state["target_path"]
    
    if os.path.exists(target_path):
        print(f"✅ Imagen de referencia encontrada: {target_path}")
        
        context = timer_state["context"]
        scene = context.scene
        
        resolution = _get_image_resolution(target_path)
        
        if resolution:
            _generate_placeholders(
                directory=timer_state["directory"],
                base_name=timer_state["base_name"],
                length=scene.zm_movie_length,
                resolution=resolution,
                overwrite=scene.zm_movie_overwrite
            )
            
            _create_vse_strip(
                context=context,
                directory=timer_state["directory"],
                base_name=timer_state["base_name"],
                length=scene.zm_movie_length
            )

        _resume_paused_stream(context)
        
        print("\n" + "="*50)
        print("[Zeta Motion] PROCESO DE CREACIÓN DE SECUENCIA FINALIZADO")
        print("="*50)

        timer_state["is_running"] = False
        return None
    
    return 0.5

# -----------------------------------------------------------------------------
# Lógica de Captura (sin cambios)
# -----------------------------------------------------------------------------
def _find_camera_image_folder():
    """Encuentra dinámicamente la carpeta completa de imágenes en la cámara."""
    print("[Zeta Motion Capture] Buscando carpeta de imágenes en la cámara...")
    try:
        result = subprocess.run(["gphoto2", "--list-folders"], capture_output=True, text=True, check=True, timeout=10)
        for line in result.stdout.splitlines():
            if "store" in line and "DCIM" in line:
                folder = line.strip().split()[-1]
                print(f"[Zeta Motion Capture] Carpeta completa encontrada: {folder}")
                return folder
        print("❌ Error: No se encontró una ruta absoluta que contenga 'DCIM'.")
        return None
    except Exception as e:
        print(f"❌ Error al listar carpetas de la cámara: {e}")
        return None

def _capture_task(save_path):
    """Tarea de captura ejecutada en un hilo para no bloquear Blender."""
    try:
        print("[Zeta Motion Capture] 1/4 - Disparando obturador...")
        subprocess.run(["gphoto2", "--set-config", "eosremoterelease=5"], check=True, timeout=5)
        time.sleep(2)

        print("[Zeta Motion Capture] 2/4 - Listando archivos en la cámara...")
        result = subprocess.run(["gphoto2", "--list-files"], capture_output=True, text=True, check=True, timeout=10)
        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("#")]
        if not lines:
            print("❌ Error: No se encontraron archivos en la cámara."); return
        last_file_num = lines[-1].split()[0].replace("#", "").strip()
        print(f"[Zeta Motion Capture] Último archivo detectado: #{last_file_num}")

        print("[Zeta Motion Capture] 3/4 - Detectando ruta de la imagen...")
        folder_path = _find_camera_image_folder()
        if not folder_path: return
        
        folder_path = folder_path.strip(" .'\"")
        if not folder_path.startswith("/store_"): folder_path = "/store_00020001/DCIM"

        print(f"[Zeta Motion Capture] 4/4 - Descargando archivo a: {save_path}")
        subprocess.run(
            ["gphoto2", "--folder", folder_path, "--get-file", last_file_num, "--filename", save_path],
            check=True, timeout=20
        )
        if not os.path.exists(save_path):
            print(f"❌ Error: El comando de descarga finalizó, pero el archivo no se encontró.")
    except Exception as e:
        print(f"❌ Error durante la captura en segundo plano: {e}")

# -----------------------------------------------------------------------------
# Funciones Auxiliares de Pausa y Reanudación (sin cambios)
# -----------------------------------------------------------------------------
def _pause_active_stream():
    current_method = state.control_state["stream"]["method"]
    if current_method != "none":
        print(f"[Zeta Motion] Stream activo detectado: '{current_method}'. Pausando...")
        state.control_state["stream"]["paused_method"] = current_method
        zm_stream.stop_all_streams()
        time.sleep(1.5)
        print("[Zeta Motion] Stream pausado.")
        return True
    return False

def _resume_paused_stream(context):
    paused_method = state.control_state["stream"]["paused_method"]
    if paused_method != "none":
        print(f"[Zeta Motion] Reanudando stream pausado: '{paused_method}'...")
        if paused_method == "ffplay": zm_stream.start_live_view(context)
        elif paused_method == "vse": zm_stream.start_vse_preview(context)
        state.control_state["stream"]["paused_method"] = "none"
        print("[Zeta Motion] Stream reanudado.")

# -----------------------------------------------------------------------------
# Operador Principal (sin cambios)
# -----------------------------------------------------------------------------
class ZM_OT_CreateMovieSequence(bpy.types.Operator):
    bl_idname = "zm.create_movie_sequence"
    bl_label = "Create Movie Sequence"
    bl_description = "Generates a stop motion image sequence"

    def execute(self, context):
        scene = context.scene
        
        if timer_state["is_running"]:
            self.report({'WARNING'}, "Un proceso de creación de secuencia ya está en curso.")
            return {'CANCELLED'}
            
        capture_path_full = bpy.path.abspath(scene.zm_capture_path)
        directory = os.path.dirname(capture_path_full)
        base_name = os.path.basename(capture_path_full)
        if not base_name or "." in base_name:
            base_name = "zm_movie"; directory = capture_path_full
        if not os.path.isdir(directory):
            self.report({'ERROR'}, f"El directorio de captura no existe: {directory}")
            return {'CANCELLED'}

        first_frame_filename = f"{base_name}_00001.jpg"
        first_frame_path = os.path.join(directory, first_frame_filename)

        print("\n" + "="*50)
        print("[Zeta Motion] INICIANDO PROCESO DE CREACIÓN DE SECUENCIA")
        print(f"Ruta de referencia: {first_frame_path}")
        print("="*50)

        _pause_active_stream()

        self.report({'INFO'}, f"Capturando {first_frame_filename} en segundo plano...")
        capture_thread = threading.Thread(target=_capture_task, args=(first_frame_path,))
        capture_thread.daemon = True
        capture_thread.start()

        timer_state.update({
            "is_running": True,
            "target_path": first_frame_path,
            "context": context,
            "base_name": base_name,
            "directory": directory,
        })
        bpy.app.timers.register(_timer_callback, first_interval=0.5)

        return {'FINISHED'}

# -----------------------------------------------------------------------------
# Registro (sin cambios)
# -----------------------------------------------------------------------------
classes = (ZM_OT_CreateMovieSequence,)
def register():
    if timer_state["is_running"]:
        bpy.app.timers.unregister(_timer_callback)
        timer_state["is_running"] = False

    for cls in classes:
        bpy.utils.register_class(cls)
    print("[Zeta Motion] zm_movie registered.")

def unregister():
    if timer_state["is_running"]:
        bpy.app.timers.unregister(_timer_callback)
        timer_state["is_running"] = False
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[Zeta Motion] zm_movie unregistered.")