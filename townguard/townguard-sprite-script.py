import bpy
import os
import numpy as np
from mathutils import Vector, Matrix

# ==========================================
# 1. USER SETTINGS
# ==========================================
output_path = "C:/dev/3d/sprites"
directions = int(os.environ.get("TG_DIRS", "8"))
res_x = 128
res_y = 128

CAMERA_ZOOM = 4.0
TARGET_HEIGHT = 1.1

ARMATURE_NAME = "Armature"
SHEET_NAME = os.environ.get("TG_SHEET", "townguard.png")
SHADOW_SHEET_NAME = os.environ.get("TG_SHADOW", "townguard-shadow.png")
SHADOW_OPACITY = 0.45
KEEP_INDIVIDUAL_FRAMES = False
TEST_MODE = False
if os.environ.get("TG_OUT"): output_path = os.environ["TG_OUT"]

# Frame ranges come from the NLA sequence; counts total 32 columns to match the
# existing town-guard sprite sheet.
ANIMATION_ZONES = [
    {"name": "Idle",     "start": 1,   "end": 97,  "count": 4},
    {"name": "Run",      "start": 97,  "end": 113, "count": 8},
    {"name": "Attack",   "start": 113, "end": 153, "count": 8},
    {"name": "Dying",    "start": 153, "end": 249, "count": 8},
    {"name": "Punch",    "start": 249, "end": 321, "count": 4},
]

# ==========================================
# 2. SYSTEM & TEXTURE FIX
# ==========================================
if not os.path.exists(output_path): os.makedirs(output_path)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
scene.render.film_transparent = True
scene.render.engine = 'BLENDER_EEVEE'

for mat in bpy.data.materials:
    if mat.node_tree:
        if hasattr(mat, 'blend_method'): mat.blend_method = 'OPAQUE'
        if hasattr(mat, 'shadow_method'): mat.shadow_method = 'OPAQUE'
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")
        if bsdf and 'Alpha' in bsdf.inputs:
            if bsdf.inputs['Alpha'].is_linked:
                for link in bsdf.inputs['Alpha'].links: links.remove(link)
            bsdf.inputs['Alpha'].default_value = 1.0

# ==========================================
# 3. DARK FANTASY LIGHTING SETUP
# ==========================================
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.select_by_type(type='LIGHT')
bpy.ops.object.delete()

key_data = bpy.data.lights.new(name="KeyLight", type='SUN')
key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
scene.collection.objects.link(key_obj)
key_obj.rotation_euler = (0.6, 0, -0.15)
key_data.energy = 4.0
key_data.color = (1.0, 0.95, 0.9)
key_data.angle = 0.1

fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (0.785, 0, -2.356)
fill_data.energy = 0.8
fill_data.color = (0.7, 0.8, 1.0)
fill_data.use_shadow = False

if not scene.world: scene.world = bpy.data.worlds.new("SpriteWorld")
scene.world.use_nodes = True
bg_node = scene.world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs['Color'].default_value = (0.02, 0.02, 0.02, 1)
    bg_node.inputs['Strength'].default_value = 1.0

# ==========================================
# 3b. DIABLO-STYLE SHADOW CATCHER
# ==========================================
old_mat = bpy.data.materials.get("ShadowCatcher")
if old_mat: bpy.data.materials.remove(old_mat)
shadow_mat = bpy.data.materials.new("ShadowCatcher")
shadow_mat.use_nodes = True
if hasattr(shadow_mat, 'blend_method'): shadow_mat.blend_method = 'BLEND'
if hasattr(shadow_mat, 'shadow_method'): shadow_mat.shadow_method = 'NONE'
sc_nodes = shadow_mat.node_tree.nodes
sc_links = shadow_mat.node_tree.links
sc_nodes.clear()
sc_out = sc_nodes.new('ShaderNodeOutputMaterial')
sc_mix = sc_nodes.new('ShaderNodeMixShader')
sc_transp = sc_nodes.new('ShaderNodeBsdfTransparent')
sc_black = sc_nodes.new('ShaderNodeEmission')
sc_black.inputs['Color'].default_value = (0, 0, 0, 1)
sc_diffuse = sc_nodes.new('ShaderNodeBsdfDiffuse')
sc_diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
sc_to_rgb = sc_nodes.new('ShaderNodeShaderToRGB')
sc_to_bw = sc_nodes.new('ShaderNodeRGBToBW')
sc_invert = sc_nodes.new('ShaderNodeMath'); sc_invert.operation = 'SUBTRACT'; sc_invert.use_clamp = True; sc_invert.inputs[0].default_value = 1.0
sc_opacity = sc_nodes.new('ShaderNodeMath'); sc_opacity.operation = 'MULTIPLY'; sc_opacity.inputs[1].default_value = SHADOW_OPACITY
sc_links.new(sc_diffuse.outputs[0], sc_to_rgb.inputs[0])
sc_links.new(sc_to_rgb.outputs['Color'], sc_to_bw.inputs[0])
sc_links.new(sc_to_bw.outputs[0], sc_invert.inputs[1])
sc_links.new(sc_invert.outputs[0], sc_opacity.inputs[0])
sc_links.new(sc_opacity.outputs[0], sc_mix.inputs['Fac'])
sc_links.new(sc_transp.outputs[0], sc_mix.inputs[1])
sc_links.new(sc_black.outputs[0], sc_mix.inputs[2])
sc_links.new(sc_mix.outputs[0], sc_out.inputs['Surface'])
shadow_plane = bpy.data.objects.get("ShadowCatcher")
if not shadow_plane:
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    shadow_plane = bpy.context.active_object
    shadow_plane.name = "ShadowCatcher"
shadow_plane.data.materials.clear()
shadow_plane.data.materials.append(shadow_mat)
shadow_plane.hide_render = True

# ==========================================
# 4. CAMERA SETUP  (explicit matrix; TRACK_TO does not evaluate headless)
# ==========================================
cam = bpy.data.objects.get('Camera')
if not cam:
    cam_data = bpy.data.cameras.new('Camera'); cam = bpy.data.objects.new('Camera', cam_data)
    scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = CAMERA_ZOOM
cam.constraints.clear()
_aim = Vector((0, 0, TARGET_HEIGHT)); _loc = Vector((8, -8, 6))
_z = (_loc - _aim).normalized(); _up = Vector((0, 0, 1))
_x = _up.cross(_z).normalized(); _y = _z.cross(_x).normalized()
cam.matrix_world = Matrix(((_x.x,_y.x,_z.x,_loc.x),(_x.y,_y.y,_z.y,_loc.y),(_x.z,_y.z,_z.z,_loc.z),(0,0,0,1)))
bpy.context.view_layer.update()

# ==========================================
# 5. RENDER EXECUTION
# ==========================================
char = bpy.data.objects.get(ARMATURE_NAME)
total_columns = sum(z["count"] for z in ANIMATION_ZONES)
if not char:
    print(f"CRITICAL ERROR: No object named '{ARMATURE_NAME}' found.")
elif not TEST_MODE:
    print("Starting Render...")
    angle_step = 360 / directions
    for i in range(directions):
        char.rotation_euler[2] = (angle_step * i) * (3.14159 / 180)
        current_col = 0
        for zone in ANIMATION_ZONES:
            zl = zone["end"] - zone["start"]
            for j in range(zone["count"]):
                f = int(zone["start"] + ((j + 0.5) * zl / zone["count"]))
                scene.frame_set(f); bpy.context.view_layer.update()
                shadow_plane.hide_render = True
                scene.render.filepath = os.path.join(output_path, f"dir{i}_col{current_col:02d}.png")
                bpy.ops.render.render(write_still=True)
                shadow_plane.hide_render = False
                scene.render.filepath = os.path.join(output_path, f"dir{i}_col{current_col:02d}_shadow.png")
                bpy.ops.render.render(write_still=True)
                current_col += 1
    char.rotation_euler[2] = 0
    shadow_plane.hide_render = True

    def build_sheet(sheet_name, suffix):
        print(f"\nStitching {sheet_name} ...")
        W = total_columns * res_x; H = directions * res_y
        px = np.zeros((H, W, 4), dtype=np.float32)
        for i in range(directions):
            for col in range(total_columns):
                p = os.path.join(output_path, f"dir{i}_col{col:02d}{suffix}.png")
                if os.path.exists(p):
                    img = bpy.data.images.load(p)
                    arr = np.array(img.pixels).reshape((res_y, res_x, 4))
                    px[(directions-1-i)*res_y:(directions-i)*res_y, col*res_x:(col+1)*res_x] = arr
                    bpy.data.images.remove(img)
                    if not KEEP_INDIVIDUAL_FRAMES: os.remove(p)
        out = bpy.data.images.new(sheet_name, width=W, height=H, alpha=True)
        out.pixels = px.flatten(); out.filepath_raw = os.path.join(output_path, sheet_name)
        out.file_format = 'PNG'; out.save()
        print("Saved", os.path.join(output_path, sheet_name))
    build_sheet(SHEET_NAME, "")
    build_sheet(SHADOW_SHEET_NAME, "_shadow")
    print("\n--- SUCCESS ---")
