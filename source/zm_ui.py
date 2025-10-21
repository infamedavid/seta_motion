# zm_ui.py — Zeta Motion 0.5.0
# Blender 4.5+ | Linux-only
# UI in English, comments in Spanish

import bpy
from bpy.app.handlers import persistent
from . import zm_camera, state, zm_preview

# -----------------------------------------------------------------------------
# Handler persistente: actualizar lista de cámaras tras detección
# -----------------------------------------------------------------------------
@persistent
def update_camera_list(dummy=None):
    cams = state.control_state["camera"].get("available", [])
    return [(c["model"], f"{c['model']} ({c['port']})", "") for c in cams]

# -----------------------------------------------------------------------------
# Operadores
# -----------------------------------------------------------------------------
class ZM_OT_DetectCameras(bpy.types.Operator):
    bl_idname = "zm.detect_cameras"
    bl_label = "Detect Cameras"
    bl_description = "Detect connected cameras using gphoto2 (Linux only)"

    def execute(self, context):
        zm_camera.detect_cameras()
        return {'FINISHED'}


class ZM_OT_ConnectCamera(bpy.types.Operator):
    bl_idname = "zm.connect_camera"
    bl_label = "Connect Camera"
    bl_description = "Connect the selected camera via gphoto2"

    def execute(self, context):
        scene = context.scene
        cams = state.control_state["camera"].get("available", [])
        selected = next((c for c in cams if c["model"] == getattr(scene, "zm_camera_list", "")), None)
        if selected:
            zm_camera.connect_camera(selected)
        else:
            self.report({'WARNING'}, "Failed to connect the selected camera.")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# NEW: Swap operator between HD and Proxy
# -----------------------------------------------------------------------------
class ZM_OT_SwapHDProxy(bpy.types.Operator):
    """Swap the selected strip between HD and Proxy (if proxy exists)"""
    bl_idname = "zm.swap_hd_proxy"
    bl_label = "Swap HD/Proxy"

    strip_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        scene = context.scene
        # try strip name from selection if not provided
        name = self.strip_name or getattr(scene, 'zm_preview_strip_name', '')
        if not name:
            # try active sequence
            seq = getattr(scene, 'sequence_editor', None)
            if seq and seq.sequences_all:
                sel = next((s for s in seq.sequences_all if getattr(s, 'select', False)), None)
                if sel:
                    name = sel.name
        if not name:
            self.report({'WARNING'}, 'No strip selected to swap')
            return {'CANCELLED'}

        # determine scale label from scene property
        scale = getattr(scene, 'zm_proxy_scale', '50')
        try:
            from . import zm_convert
            zm_convert.swap_strip_resolution(context, strip_name=name, use_proxy=True, scale_label=scale)
            self.report({'INFO'}, 'Swap attempted')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Swap failed: {e}")
            return {'CANCELLED'}


# -----------------------------------------------------------------------------
# Panel principal en el N-panel del VSE
# -----------------------------------------------------------------------------
class ZM_PT_CameraPanel(bpy.types.Panel):
    bl_label = "Zeta Motion"
    bl_idname = "ZM_PT_camera_panel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Zeta Motion"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        cams = state.control_state["camera"].get("available", [])
        connected = state.control_state["system"].get("connected", False)

        # --- Camera detection box ---
        box = layout.box()
        box.label(text="Camera Detection", icon="CAMERA_DATA")
        box.operator("zm.detect_cameras", icon="FILE_REFRESH")

        if cams:
            if not hasattr(scene, "zm_camera_list") or scene.zm_camera_list == "":
                scene.zm_camera_list = cams[0]["model"]
            box.prop(scene, "zm_camera_list", text="Select Camera")
            box.operator("zm.connect_camera", icon="CHECKMARK")

            active = zm_camera.get_active_camera()
            if connected and active:
                box.label(text=f"Connected: {active['model']}", icon="CHECKMARK")
                box.label(text=f"Port: {active['port']}")
        else:
            box.label(text="No cameras detected.", icon="ERROR")

        layout.separator()

        # --- Output paths box ---
        box2 = layout.box()
        box2.label(text="Output Paths", icon="FILE_FOLDER")
        box2.prop(scene, "zm_preview_path") # texto por defecto
        box2.prop(scene, "zm_capture_path") # texto por defecto

        layout.separator()

        # --- Streams controls ---
        col = layout.column(align=True)
        col.label(text="Camera Streams")
        row = col.row(align=True)
        row.operator("zm.start_live_view", text="Live View", icon='CAMERA_DATA')
        row.operator("zm.start_vse_preview", text="VSE Preview", icon='IMAGE_DATA')
        col.separator()
        col.operator("zm.stop_streams", text="Stop Streams", icon='CANCEL')


# -----------------------------------------------------------------------------
# NUEVO PANEL: Stop Motion Movie
# -----------------------------------------------------------------------------
class ZM_PT_MoviePanel(bpy.types.Panel):
    bl_label = "Stop Motion Movie"
    bl_idname = "ZM_PT_movie_panel"
    bl_space_type = "SEQUENCE_EDITOR"  # Mismo espacio que el panel de cámara
    bl_region_type = "UI"
    bl_category = "Zeta Motion"        # Misma categoría para agruparlos

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="Sequence Creation", icon="SEQUENCE")

        # Vinculamos las propiedades creadas en __init__.py
        row = box.row()
        row.prop(scene, "zm_movie_length")
        row.prop(scene, "zm_movie_overwrite")

        row = box.row()
        row.label(text="Proxy Scale:")
        row.prop(scene, 'zm_proxy_scale', text='')

        box.operator("zm.create_movie_sequence", text="Create / Extend Sequence", icon="ADD")
        box.operator("zm.swap_hd_proxy", text="Swap HD/Proxy", icon='FILE_REFRESH')

# -----------------------------------------------------------------------------
# Registro
# -----------------------------------------------------------------------------
classes = (
    ZM_OT_DetectCameras,
    ZM_OT_ConnectCamera,
    ZM_OT_SwapHDProxy,  # <-- ADDED
    ZM_PT_CameraPanel,
    ZM_PT_MoviePanel, 
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[Zeta Motion] zm_ui registered.")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[Zeta Motion] zm_ui unregistered.")
