# zm_foto.py — Zeta Motion
# Frame-level manipulation for stop motion sequences.
# Blender 4.5+ | Linux-only

import bpy
import os
import shutil
import re
from . import zm_worker, zm_convert, zm_movie  # Asume acceso a la lógica de captura

# -----------------------------------------------------------------------------
# Funciones de Propiedades del Strip (LOCALES)
# -----------------------------------------------------------------------------
# Estas funciones son una copia segura de las de zm_properties, pero operan
# localmente para no interferir con el caché global del preview strip.

def _store_movie_strip_properties(strip):
    """
    Crea un snapshot de las propiedades visuales de un strip.
    Devuelve un dict simple, o None si el strip es inválido.
    """
    if not strip:
        return None
    data = {}
    try:
        data["blend_type"] = getattr(strip, "blend_type", "REPLACE")
        data["blend_alpha"] = getattr(strip, "blend_alpha", 1.0)
        data["use_translation"] = getattr(strip, "use_translation", False)
        data["use_crop"] = getattr(strip, "use_crop", False)
        
        transform = getattr(strip, "transform", None)
        if transform:
            data["transform"] = {
                "offset_x": getattr(transform, "offset_x", 0.0),
                "offset_y": getattr(transform, "offset_y", 0.0),
                "scale_x": getattr(transform, "scale_x", 1.0),
                "scale_y": getattr(transform, "scale_y", 1.0),
            }
    except Exception as e:
        print(f"[Zeta Motion] Error storing movie strip properties: {e}")
    return data

def _apply_movie_strip_properties(strip, data):
    """Aplica un dict de propiedades a un strip."""
    if not strip or not data:
        return
    try:
        if "blend_type" in data: strip.blend_type = data["blend_type"]
        if "blend_alpha" in data: strip.blend_alpha = data["blend_alpha"]
        if "use_translation" in data: strip.use_translation = data["use_translation"]
        if "use_crop" in data: strip.use_crop = data["use_crop"]

        t_data = data.get("transform")
        transform = getattr(strip, "transform", None)
        if t_data and transform:
            if "offset_x" in t_data: transform.offset_x = t_data["offset_x"]
            if "offset_y" in t_data: transform.offset_y = t_data["offset_y"]
            if "scale_x" in t_data: transform.scale_x = t_data["scale_x"]
            if "scale_y" in t_data: transform.scale_y = t_data["scale_y"]
    except Exception as e:
        print(f"[Zeta Motion] Error applying movie strip properties: {e}")


# -----------------------------------------------------------------------------
# Funciones Centrales (Helpers)
# -----------------------------------------------------------------------------

def get_active_photo_details(context):
    """
    Identifica la "foto actual" bajo el playhead en el strip de secuencia
    seleccionado.
    """
    scene = context.scene
    if not getattr(scene, 'sequence_editor', None):
        return None

    # 1. Encontrar el strip activo (seleccionado, tipo imagen, bajo playhead)
    active_strip = None
    for strip in scene.sequence_editor.sequences_all:
        if (strip.select and strip.type == 'IMAGE' and
                strip.frame_start <= scene.frame_current < strip.frame_final_end):
            active_strip = strip
            break
    
    if not active_strip:
        print("[Zeta Motion] No active image sequence strip found under playhead.")
        return None

    # 2. Calcular el índice del fichero actual
    frame_relative = scene.frame_current - active_strip.frame_start
    image_index = int(frame_relative + active_strip.frame_offset_start)

    if not (0 <= image_index < len(active_strip.elements)):
        print("[Zeta Motion] Playhead is out of the valid element range for the strip.")
        return None
        
    # 3. Extraer información del fichero
    try:
        proxy_filename = active_strip.elements[image_index].filename
        directory = bpy.path.abspath(active_strip.directory)
        proxy_path = os.path.join(directory, proxy_filename)
        
        # Regex para extraer base_name e índice numérico
        match = re.match(r'^(.*?)_(\d+)\.jpg$', proxy_filename)
        if not match:
             print(f"[Zeta Motion] Filename '{proxy_filename}' does not match expected pattern 'name_index.jpg'.")
             return None

        base_name_proxy = match.group(1) # Nombre base, puede incluir tokens de proxy
        index_str = match.group(2)

        # Normalizar base_name para encontrar el par HD
        tokens = base_name_proxy.split('_')
        if tokens[-1] in ('25', '50', '75'):
            base_name_core = '_'.join(tokens[:-1])
        else:
            base_name_core = base_name_proxy

        hd_path = os.path.join(directory, f"{base_name_core}_HD_{index_str}.jpg")

        return {
            "strip": active_strip,
            "proxy_path": proxy_path if os.path.exists(proxy_path) else None,
            "hd_path": hd_path if os.path.exists(hd_path) else None,
            "base_name_core": base_name_core,
            "index_str": index_str,
            "directory": directory,
        }
    except Exception as e:
        print(f"[Zeta Motion] Error getting photo details: {e}")
        return None

def get_sequence_files(directory, base_name_core, proxy_scale='50'):
    """
    Obtiene una lista ordenada de los archivos proxy de una secuencia.
    """
    pattern = re.compile(f"^{re.escape(base_name_core)}_{proxy_scale}_(\d+)\.jpg$")
    files = []
    for f in os.listdir(directory):
        if pattern.match(f):
            files.append(f)
    return sorted(files)

# -----------------------------------------------------------------------------
# Operaciones de Archivos
# -----------------------------------------------------------------------------

def _exclude_photo(details):
    """
    Excluye la foto actual y recompacta la secuencia.
    """
    if not details: return False
    
    # 1. Excluir por renombrado
    if details["proxy_path"]:
        shutil.move(details["proxy_path"], details["proxy_path"] + ".excluded")
    if details["hd_path"]:
        shutil.move(details["hd_path"], details["hd_path"] + ".excluded")
        
    print(f"[Zeta Motion] Excluded frame {details['index_str']}.")

    # 2. Renombrado masivo para llenar el hueco
    current_index = int(details["index_str"])
    proxy_scale = details["strip"].scene.zm_proxy_scale
    
    all_files = get_sequence_files(details["directory"], details["base_name_core"], proxy_scale)
    
    files_to_rename = []
    for f in all_files:
        match = re.search(r'_(\d+)\.jpg$', f)
        if match and int(match.group(1)) > current_index:
            files_to_rename.append(f)
            
    # Iterar en orden ascendente para no sobrescribir
    for filename in sorted(files_to_rename):
        old_idx = int(re.search(r'_(\d+)\.jpg$', filename).group(1))
        new_idx = old_idx - 1
        
        # Renombrar proxy
        new_proxy_name = f"{details['base_name_core']}_{proxy_scale}_{new_idx:05d}.jpg"
        shutil.move(os.path.join(details["directory"], filename), 
                    os.path.join(details["directory"], new_proxy_name))
        
        # Renombrar HD si existe
        old_hd_name = f"{details['base_name_core']}_HD_{old_idx:05d}.jpg"
        old_hd_path = os.path.join(details["directory"], old_hd_name)
        if os.path.exists(old_hd_path):
            new_hd_name = f"{details['base_name_core']}_HD_{new_idx:05d}.jpg"
            shutil.move(old_hd_path, os.path.join(details["directory"], new_hd_name))
    
    print(f"[Zeta Motion] Re-indexed {len(files_to_rename)} frames.")
    return True

# -----------------------------------------------------------------------------
# Integración con VSE
# -----------------------------------------------------------------------------

def refresh_movie_strip(context, strip_name, directory, base_name_core, proxy_scale='50'):
    """
    Destruye y reconstruye el strip de la película para reflejar los cambios
    en el sistema de archivos.
    """
    scene = context.scene
    seq = scene.sequence_editor
    if not seq:
        print("[Zeta Motion] No sequence editor found for refresh.")
        return
        
    # 1. Encontrar y guardar estado del strip antiguo
    old_strip = next((s for s in seq.sequences if s.name == strip_name), None)
    if not old_strip:
        print(f"[Zeta Motion] Could not find strip '{strip_name}' to refresh.")
        return

    props_snapshot = _store_movie_strip_properties(old_strip)
    channel = old_strip.channel
    frame_start = old_strip.frame_start
    
    # 2. Eliminar strip antiguo
    seq.sequences.remove(old_strip)
    
    # 3. Encontrar la secuencia actualizada en disco
    sequence_files = get_sequence_files(directory, base_name_core, proxy_scale)
    if not sequence_files:
        print("[Zeta Motion] No image files found to rebuild the strip.")
        return

    # 4. Crear nuevo strip
    first_frame_path = os.path.join(directory, sequence_files[0])
    try:
        new_strip = seq.sequences.new_image(
            name=strip_name,
            filepath=first_frame_path,
            channel=channel,
            frame_start=frame_start
        )
        
        # Añadir resto de elementos
        for f in sequence_files[1:]:
            new_strip.elements.append(f)
            
        new_strip.frame_final_duration = len(sequence_files)
        
        # 5. Aplicar propiedades guardadas
        _apply_movie_strip_properties(new_strip, props_snapshot)
        
        print(f"[Zeta Motion] Strip '{strip_name}' refreshed successfully with {len(sequence_files)} frames.")
    except Exception as e:
        print(f"[Zeta Motion] Fatal error rebuilding strip: {e}")

# -----------------------------------------------------------------------------
# Operadores de Blender
# -----------------------------------------------------------------------------

class ZM_OT_ExcludeActivePhoto(bpy.types.Operator):
    """Excluye el fotograma activo y recompacta la secuencia"""
    bl_idname = "zm.exclude_active_photo"
    bl_label = "Delete Frame"

    def execute(self, context):
        details = get_active_photo_details(context)
        if not details:
            self.report({'WARNING'}, "No active frame to delete. Select a strip and place playhead over it.")
            return {'CANCELLED'}
            
        strip_name = details["strip"].name
        directory = details["directory"]
        base_name = details["base_name_core"]
        proxy_scale = context.scene.zm_proxy_scale

        if _exclude_photo(details):
            # Usar un temporizador para asegurar que el VSE se actualice después de las operaciones de archivo
            bpy.app.timers.register(
                lambda: refresh_movie_strip(context, strip_name, directory, base_name, proxy_scale), 
                first_interval=0.1
            )
            self.report({'INFO'}, f"Frame {details['index_str']} excluded and sequence re-indexed.")
        else:
            self.report({'ERROR'}, "Failed to exclude frame.")
            return {'CANCELLED'}
        
        return {'FINISHED'}

# --- NOTA DE IMPLEMENTACIÓN ---
# Los operadores ZM_OT_ReplaceActivePhoto y ZM_OT_InsertActivePhoto requerirían
# una refactorización de la lógica de captura de zm_movie.py para ser reutilizable.
# Su implementación se omite aquí, pero seguirían el patrón de llamar a
# get_active_photo_details(), encolar una tarea en zm_worker y, en el callback,
# ejecutar la manipulación de archivos y el refresco del VSE.

# -----------------------------------------------------------------------------
# Registro
# -----------------------------------------------------------------------------

classes = (
    ZM_OT_ExcludeActivePhoto,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[Zeta Motion] zm_foto registered.")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[Zeta Motion] zm_foto unregistered.")