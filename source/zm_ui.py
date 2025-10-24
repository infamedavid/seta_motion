# zm_ui.py — Zeta Motion
# Blender 4.5+ | Linux-only

import bpy
from . import zm_camera, state, zm_settings, zm_stream, zm_movie_source

# -----------------------------------------------------------------------------
# Handler persistente
# -----------------------------------------------------------------------------
def update_camera_list(dummy=None):
    cams = state.control_state["camera"].get("available", [])
    return [(c["model"], f"{c['model']} ({c['port']})", "") for c in cams]

# -----------------------------------------------------------------------------
# Operadores
# -----------------------------------------------------------------------------
class ZM_OT_DetectCameras(bpy.types.Operator):
    bl_idname = "zm.detect_cameras"
    bl_label = "Detect Cameras"
    def execute(self, context): zm_camera.detect_cameras(); return {'FINISHED'}

class ZM_OT_ConnectCamera(bpy.types.Operator):
    bl_idname = "zm.connect_camera"
    bl_label = "Connect Camera"
    def execute(self, context):
        cams = state.control_state["camera"]["available"]
        selected = next((c for c in cams if c["model"] == context.scene.zm_camera_list), None)
        if selected: zm_camera.connect_camera(selected)
        return {'FINISHED'}

class ZM_OT_RefreshSettings(bpy.types.Operator):
    bl_idname = "zm.refresh_settings"
    bl_label = "Refresh Camera Settings"
    def execute(self, context):
        active_cam = zm_camera.get_active_camera()
        if active_cam: zm_camera.connect_camera(active_cam)
        return {'FINISHED'}

class ZM_OT_MatchCameraToScene(bpy.types.Operator):
    bl_idname = "zm.match_camera_to_scene"
    bl_label = "Match Camera to Scene Resolution"
    bl_description = "Find the camera image format that best matches the scene's render resolution"
    def execute(self, context):
        scene = context.scene
        scene_res_x = scene.render.resolution_x; scene_res_y = scene.render.resolution_y
        scene_area = scene_res_x * scene_res_y
        available_formats = state.control_state["camera"]["settings"]["choices"].get("imageformat", [])
        if not available_formats:
            self.report({'WARNING'}, "No image formats available.")
            return {'CANCELLED'}
        best_match = None; smallest_diff = float('inf')
        for fmt in available_formats:
            res_data = zm_settings.get_resolution_data(fmt)
            if res_data:
                diff = abs(scene_area - (res_data["width"] * res_data["height"]))
                if diff < smallest_diff:
                    smallest_diff = diff
                    best_match = fmt
        if best_match:
            self.report({'INFO'}, f"Best match: {best_match}. Setting format.")
            scene.zm_imageformat_setting = best_match
        else:
            self.report({'WARNING'}, "Could not find a suitable resolution match.")
        return {'FINISHED'}

class ZM_OT_StartLiveView(bpy.types.Operator):
    bl_idname = "zm.start_live_view"
    bl_label = "Live View / Blend"
    bl_description = "Start a live camera preview. If Live Blend is enabled, overlays on the current VSE frame"
    def execute(self, context):
        scene = context.scene
        image_path = None
        if scene.zm_live_blend_enabled:
            image_path = zm_movie_source.get_active_frame_path(context)
            if not image_path:
                self.report({'WARNING'}, "Live Blend enabled, but no active frame found.")
        zm_stream.start_live_stream(context, image_path, scene.zm_blend_factor)
        return {'FINISHED'}

class ZM_OT_SwapHDProxy(bpy.types.Operator):
    bl_idname = "zm.swap_hd_proxy"
    bl_label = "Toggle HD / Proxy"
    bl_description = "Swap between High-Definition and Proxy versions of the movie strip"
    use_proxy: bpy.props.BoolProperty()
    def execute(self, context):
        print(f"Swapping to {'proxy' if self.use_proxy else 'HD'}")
        return {'FINISHED'}

# -----------------------------------------------------------------------------
# Paneles de UI
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
        is_connected = state.control_state["system"]["connected"]
        
        # --- Sección de Conexión ---
        box = layout.box()
        box.label(text="Camera Connection", icon="CAMERA_DATA")
        row = box.row(align=True)
        row.operator("zm.detect_cameras", icon="FILE_REFRESH")
        if is_connected and state.control_state["camera"]["active_name"]:
             row.label(text=f"Active: {state.control_state['camera']['active_name']}", icon="CHECKMARK")
        if state.control_state["camera"]["available"]:
            box.prop(scene, "zm_camera_list", text="")
            box.operator("zm.connect_camera", icon="LINKED")
        else:
            box.label(text="No cameras detected.", icon="ERROR")
        layout.separator()

        # --- Sección de Ajustes de Cámara ---
        settings_box = layout.box()
        header_row = settings_box.row()
        header_row.label(text="Camera Settings", icon="SETTINGS")
        header_row.operator("zm.refresh_settings", text="", icon="FILE_REFRESH")
        settings_box.enabled = is_connected
        col = settings_box.column(align=True)
        col.prop(scene, "zm_imageformat_setting", text="Resolution")
        col.operator("zm.match_camera_to_scene", icon="SCREEN_BACK")
        col.separator()
        col.prop(scene, "zm_iso_setting")
        col.prop(scene, "zm_aperture_setting")
        col.prop(scene, "zm_shutterspeed_setting")
        layout.separator()

        # --- CÓDIGO RESTAURADO: Sección de Paths ---
        paths_box = layout.box()
        paths_box.label(text="File Paths", icon="FILE_FOLDER")
        paths_box.prop(scene, "zm_preview_path", text="Preview")
        paths_box.prop(scene, "zm_capture_path", text="Capture")
        layout.separator()

        # --- CÓDIGO RESTAURADO: Sección de Streams ---
        stream_box = layout.box()
        stream_box.label(text="Live Preview", icon="CAMERA_DATA")
        col_stream = stream_box.column(align=True)
        col_stream.operator("zm.start_live_view", icon="PLAY")
        col_stream.operator("zm.start_vse_preview", icon="PREVIEW_RANGE")
        col_stream.operator("zm.stop_streams", icon="PAUSE")
        blend_box = stream_box.box()
        blend_box.prop(scene, "zm_live_blend_enabled", text="Enable Live Blend")
        blend_row = blend_box.row()
        blend_row.enabled = scene.zm_live_blend_enabled
        blend_row.prop(scene, "zm_blend_factor", text="Opacity")

class ZM_PT_MoviePanel(bpy.types.Panel):
    bl_label = "Stop Motion Sequence"
    bl_idname = "ZM_PT_movie_panel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Zeta Motion"
    bl_parent_id = "ZM_PT_camera_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        box.label(text="Capture & Sequence Settings", icon="FILE_MOVIE")
        box.prop(scene, "zm_capture_path", text="")
        row = box.row(align=True)
        row.prop(scene, "zm_movie_length", text="Frames")
        row.prop(scene, "zm_movie_overwrite", text="Overwrite")
        box.prop(scene, "zm_proxy_scale")
        layout.separator()
        layout.operator("zm.create_movie_sequence", text="Create Sequence", icon="ADD")
        row = layout.row(align=True)
        row.operator("zm.swap_hd_proxy", text="Use HD").use_proxy = False
        row.operator("zm.swap_hd_proxy", text="Use Proxy").use_proxy = True

# -----------------------------------------------------------------------------
# Registro
# -----------------------------------------------------------------------------
classes = (
    ZM_OT_DetectCameras,
    ZM_OT_ConnectCamera,
    ZM_OT_RefreshSettings,
    ZM_OT_MatchCameraToScene,
    ZM_OT_StartLiveView,
    ZM_OT_SwapHDProxy,
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