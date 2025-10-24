import bpy
import os
import re
import shutil
from . import zm_movie_source, zm_worker

# =========================================================
# HELPERS
# =========================================================

def get_active_photo_details(context):
    strip = zm_movie_source._find_active_strip(context)
    if not strip or not strip.elements:
        return None

    frame_idx = context.scene.frame_current - strip.frame_start
    frame_idx = max(0, min(frame_idx, len(strip.elements) - 1))

    element = strip.elements[frame_idx]
    proxy_path = bpy.path.abspath(element.filename)
    directory = os.path.dirname(proxy_path)
    base_name_match = re.match(r"(.+?)_(\d+)\.jpg$", os.path.basename(proxy_path))
    if not base_name_match:
        return None

    base_name = base_name_match.group(1)
    index_str = base_name_match.group(2)

    hd_path = None
    hd_candidate = os.path.join(directory, f"{base_name}_HD_{index_str}.jpg")
    if os.path.exists(hd_candidate):
        hd_path = hd_candidate

    return {
        "proxy_path": proxy_path,
        "hd_path": hd_path,
        "base_name": base_name,
        "index_str": index_str,
        "directory": directory
    }


def get_sequence_files(directory, base_name):
    pattern = re.compile(rf"{base_name}_(\d+)\.jpg$")
    matches = []
    for f in os.listdir(directory):
        if m := pattern.match(f):
            matches.append((int(m.group(1)), os.path.join(directory, f)))
    matches.sort(key=lambda x: x[0])
    return [p for _, p in matches]


# =========================================================
# OPERACIONES DE ARCHIVOS
# =========================================================

def _replace_photo(new_photo_path, active_details):
    shutil.copy2(new_photo_path, active_details["proxy_path"])
    if active_details["hd_path"]:
        hd_candidate = new_photo_path.replace(".jpg", "_HD.jpg")
        if os.path.exists(hd_candidate):
            shutil.copy2(hd_candidate, active_details["hd_path"])


def _insert_photo(new_photo_path, active_details):
    base = active_details["base_name"]
    directory = active_details["directory"]
    files = get_sequence_files(directory, base)

    current_idx = int(active_details["index_str"])
    for idx, path in sorted([(int(re.search(r"_(\d+)\.jpg$", f).group(1)), f) for f in files], reverse=True):
        if idx >= current_idx:
            new_idx = idx + 1
            new_name = os.path.join(directory, f"{base}_{new_idx:04d}.jpg")
            os.rename(path, new_name)

    new_target = os.path.join(directory, f"{base}_{current_idx + 1:04d}.jpg")
    shutil.copy2(new_photo_path, new_target)


def _exclude_photo(active_details):
    proxy_path = active_details["proxy_path"]
    directory = active_details["directory"]
    base = active_details["base_name"]
    idx = int(active_details["index_str"])

    excluded_path = proxy_path + ".excluded"
    os.rename(proxy_path, excluded_path)
    if active_details["hd_path"] and os.path.exists(active_details["hd_path"]):
        os.rename(active_details["hd_path"], active_details["hd_path"] + ".excluded")

    files = get_sequence_files(directory, base)
    for f in files:
        m = re.search(r"_(\d+)\.jpg$", f)
        if m and int(m.group(1)) > idx:
            new_idx = int(m.group(1)) - 1
            new_name = os.path.join(directory, f"{base}_{new_idx:04d}.jpg")
            os.rename(f, new_name)


# =========================================================
# INTEGRACIÓN CON VSE
# =========================================================

def refresh_movie_strip(context, strip_name, directory):
    scene = context.scene
    seq = scene.sequence_editor
    strip = seq.sequences.get(strip_name)
    if not strip:
        return

    props = {
        "frame_start": strip.frame_start,
        "channel": strip.channel,
        "blend_type": strip.blend_type,
        "transform": (strip.transform.offset_x, strip.transform.offset_y),
    }

    seq.sequences.remove(strip)

    base_name = None
    for f in os.listdir(directory):
        if f.endswith(".jpg"):
            base_name = f.split("_")[0]
            break
    if not base_name:
        return

    image_files = get_sequence_files(directory, base_name)
    new_strip = seq.sequences.new_image(
        strip_name,
        image_files[0],
        channel=props["channel"],
        frame_start=props["frame_start"]
    )

    for img in image_files[1:]:
        new_strip.elements.append(img)

    new_strip.blend_type = props["blend_type"]
    new_strip.transform.offset_x, new_strip.transform.offset_y = props["transform"]


# =========================================================
# OPERADORES BLENDER
# =========================================================

class ZM_OT_ReplaceActivePhoto(bpy.types.Operator):
    bl_idname = "zm.replace_active_photo"
    bl_label = "Reemplazar Foto Activa"
    bl_description = "Captura una nueva foto y reemplaza la actual"

    def execute(self, context):
        details = get_active_photo_details(context)
        if not details:
            self.report({'ERROR'}, "No hay foto activa.")
            return {'CANCELLED'}

        def capture_and_replace():
            from .zm_movie import capture_single_photo
            def on_done(photo_path):
                _replace_photo(photo_path, details)
                refresh_movie_strip(context, details["base_name"], details["directory"])
            capture_single_photo(callback=on_done, tag="foto_capture")

        zm_worker.enqueue(capture_and_replace, tag="foto_capture")
        return {'FINISHED'}


class ZM_OT_InsertActivePhoto(bpy.types.Operator):
    bl_idname = "zm.insert_active_photo"
    bl_label = "Insertar Foto"
    bl_description = "Captura una nueva foto e inserta después de la actual"

    def execute(self, context):
        details = get_active_photo_details(context)
        if not details:
            self.report({'ERROR'}, "No hay foto activa.")
            return {'CANCELLED'}

        def capture_and_insert():
            from .zm_movie import capture_single_photo
            def on_done(photo_path):
                _insert_photo(photo_path, details)
                refresh_movie_strip(context, details["base_name"], details["directory"])
            capture_single_photo(callback=on_done, tag="foto_capture")

        zm_worker.enqueue(capture_and_insert, tag="foto_capture")
        return {'FINISHED'}


class ZM_OT_ExcludeActivePhoto(bpy.types.Operator):
    bl_idname = "zm.exclude_active_photo"
    bl_label = "Excluir Foto"
    bl_description = "Excluye la foto actual y recompacta la secuencia"

    def execute(self, context):
        details = get_active_photo_details(context)
        if not details:
            self.report({'ERROR'}, "No hay foto activa.")
            return {'CANCELLED'}

        _exclude_photo(details)
        refresh_movie_strip(context, details["base_name"], details["directory"])
        return {'FINISHED'}


classes = (
    ZM_OT_ReplaceActivePhoto,
    ZM_OT_InsertActivePhoto,
    ZM_OT_ExcludeActivePhoto,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
