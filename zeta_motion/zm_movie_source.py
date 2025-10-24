# zm_movie_source.py — Zeta Motion
# Lógica para detectar el frame de video activo bajo el playhead en el VSE.
# Blender 4.5+ | Linux-only

import bpy
import os

def _find_active_strip(scene):
    """Encuentra el primer strip de imagen seleccionado bajo el playhead."""
    if not getattr(scene, 'sequence_editor', None):
        return None

    current_frame = scene.frame_current
    
    for strip in scene.sequence_editor.sequences_all:
        # Condición 1: Debe estar seleccionado
        if not getattr(strip, 'select', False):
            continue
        
        # Condición 2: Debe ser un strip de imagen
        if strip.type != 'IMAGE':
            continue

        # Condición 3: El playhead debe estar dentro de su rango visible
        frame_start = strip.frame_start
        frame_end = strip.frame_final_end
        if not (frame_start <= current_frame < frame_end):
            continue
        
        # Si cumple todo, es nuestro candidato
        return strip
    
    return None

def _resolve_proxy_path(strip, frame_index):
    """
    Dada una ruta de archivo, intenta encontrar la mejor versión disponible
    (proxy de alta resolución o el original).
    Prioridad: 75% > 50% > 25% > HD > Original.
    """
    try:
        base_filename = strip.elements[frame_index].filename
    except IndexError:
        return None # Índice fuera de rango

    directory = bpy.path.abspath(strip.directory)
    name, ext = os.path.splitext(base_filename)
    
    # Extraer nombre base e índice numérico (ej: 'mi_peli_HD_00123' -> 'mi_peli', '00123')
    tokens = name.split('_')
    
    if not tokens:
        return os.path.join(directory, base_filename) # Fallback

    numeric_index = ""
    base_name_parts = []
    
    if tokens[-1].isdigit():
        numeric_index = tokens[-1]
        # Ignorar sufijos de proxy/HD para obtener el nombre real
        for part in tokens[:-1]:
            if part not in ('HD', '75', '50', '25'):
                base_name_parts.append(part)
    else:
        # No se pudo encontrar un índice numérico, usar el nombre tal cual
        return os.path.join(directory, base_filename)

    base_name = "_".join(base_name_parts)

    # Lista de sufijos a buscar, en orden de prioridad
    suffixes_to_check = ['75', '50', '25', 'HD']
    
    for suffix in suffixes_to_check:
        candidate_name = f"{base_name}_{suffix}_{numeric_index}{ext}"
        candidate_path = os.path.join(directory, candidate_name)
        if os.path.exists(candidate_path):
            print(f"[Zeta Motion] Proxy/HD found for blend: {candidate_path}")
            return candidate_path

    # Si no se encuentra ningún proxy o HD, devolver la ruta original que está en el strip
    original_path = os.path.join(directory, base_filename)
    if os.path.exists(original_path):
        return original_path

    return None

def get_active_frame_path(context):
    """
    Función principal. Devuelve la ruta absoluta al archivo de imagen bajo el
    playhead en el VSE, o None si no se cumplen las condiciones.
    """
    scene = context.scene
    
    strip = _find_active_strip(scene)
    if not strip:
        return None

    # Calcular el índice del frame dentro de la secuencia de imágenes
    frame_relative = scene.frame_current - strip.frame_start
    image_index = int(frame_relative + strip.frame_offset_start)
    
    # Verificar que el índice sea válido
    if not (0 <= image_index < len(strip.elements)):
        return None

    # Resolver la mejor ruta (proxy o HD)
    return _resolve_proxy_path(strip, image_index)