import bpy
import os
import numpy as np

# ==========================================
# 1. USER SETTINGS
# ==========================================
output_path = "/home/user/3d/sprites"
directions = 8
res_x = 128
res_y = 128

CAMERA_ZOOM = 4.0
TARGET_HEIGHT = 1.1

SHEET_NAME = "hobbit-female.png"
SHADOW_SHEET_NAME = "hobbit-female-shadow.png"
SHADOW_OPACITY = 0.45  # 0 = invisible, 1 = solid black Diablo shadow
KEEP_INDIVIDUAL_FRAMES = False
TEST_MODE = False

# --- YOUR CUSTOM ANIMATION TIMELINE MAP ---
ANIMATION_ZONES = [
    {"name": "idle", "start": 1, "end": 49, "count": 4},
    {"name": "running", "start": 49, "end": 57, "count": 8},
    {"name": "attack", "start": 57, "end": 105, "count": 8},
    {"name": "hit", "start": 105, "end": 117, "count": 4},
    {"name": "die", "start": 117, "end": 173, "count": 8},
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
bpy.ops.object.select_by_type(type='LIGHT')
bpy.ops.object.delete()

key_data = bpy.data.lights.new(name="KeyLight", type='SUN')
key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
scene.collection.objects.link(key_obj)
# X tilt < 45deg keeps the shadow shorter than the character's height;
# the slight negative Z aims the cast shadow up-and-right in screen space
# for the camera at (8, -8, 6).
key_obj.rotation_euler = (0.6, 0, -0.15)
key_data.energy = 4.0
key_data.color = (1.0, 0.95, 0.9)
key_data.angle = 0.1  # widen the sun disc so shadow edges are soft

fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (0.785, 0, -2.356)
fill_data.energy = 0.8
fill_data.color = (0.7, 0.8, 1.0)
# The fill light was casting the long downward shadow seen in the sprite
# sheet; only the key light should cast onto the shadow catcher.
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
# EEVEE has no native shadow catcher, so we fake one: a ground plane whose
# material is fully transparent where lit and semi-opaque black where shadowed.
old_mat = bpy.data.materials.get("ShadowCatcher")
if old_mat: bpy.data.materials.remove(old_mat)

shadow_mat = bpy.data.materials.new("ShadowCatcher")
shadow_mat.use_nodes = True
shadow_mat.blend_method = 'BLEND'
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
sc_invert = sc_nodes.new('ShaderNodeMath')
sc_invert.operation = 'SUBTRACT'
sc_invert.use_clamp = True
sc_invert.inputs[0].default_value = 1.0
sc_opacity = sc_nodes.new('ShaderNodeMath')
sc_opacity.operation = 'MULTIPLY'
sc_opacity.inputs[1].default_value = SHADOW_OPACITY

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
# 4. CAMERA SETUP
# ==========================================
cam = bpy.data.objects.get('Camera')
if not cam:
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.name = 'Camera'
scene.camera = cam 
cam.data.type = 'ORTHO'
cam.data.ortho_scale = CAMERA_ZOOM
cam.location = (8, -8, 6) 

target = bpy.data.objects.get('CamTarget') or bpy.data.objects.new("CamTarget", None)
if target.name not in scene.collection.objects: scene.collection.objects.link(target)
target.location = (0, 0, TARGET_HEIGHT)

cam.constraints.clear()
track = cam.constraints.new(type='TRACK_TO')
track.target, track.track_axis, track.up_axis = target, 'TRACK_NEGATIVE_Z', 'UP_Y'
bpy.context.view_layer.update()

# ==========================================
# 5. RENDER EXECUTION
# ==========================================
char = bpy.data.objects.get('Armature')
total_columns = sum(zone["count"] for zone in ANIMATION_ZONES)

if not char:
    print("CRITICAL ERROR: No object named 'Armature' found.")
elif not TEST_MODE:
    print("Starting Render...")
    angle_step = 360 / directions
    
    for i in range(directions):
        char.rotation_euler[2] = (angle_step * i) * (3.14159 / 180)
        current_col = 0
        
        for zone in ANIMATION_ZONES:
            zone_length = zone["end"] - zone["start"]
            
            for j in range(zone["count"]):
                # THE FIX: Add 0.5 to 'j' to sample the exact middle of the frame interval
                f = int(zone["start"] + ((j + 0.5) * zone_length / zone["count"]))
                
                scene.frame_set(f)
                bpy.context.view_layer.update()

                # Pass 1: no shadow (as before)
                shadow_plane.hide_render = True
                file_name = f"dir{i}_col{current_col:02d}.png"
                scene.render.filepath = os.path.join(output_path, file_name)
                bpy.ops.render.render(write_still=True)

                # Pass 2: with Diablo-style ground shadow
                shadow_plane.hide_render = False
                file_name = f"dir{i}_col{current_col:02d}_shadow.png"
                scene.render.filepath = os.path.join(output_path, file_name)
                bpy.ops.render.render(write_still=True)
                current_col += 1

    char.rotation_euler[2] = 0
    shadow_plane.hide_render = True

    # ==========================================
    # 6. SPRITE SHEET BUILDER
    # ==========================================
    def build_sheet(sheet_name, suffix):
        print(f"\nStitching frames into Sprite Sheet: {sheet_name}...")
        sheet_width = total_columns * res_x
        sheet_height = directions * res_y
        sheet_pixels = np.zeros((sheet_height, sheet_width, 4), dtype=np.float32)

        for i in range(directions):
            for col in range(total_columns):
                file_name = f"dir{i}_col{col:02d}{suffix}.png"
                img_path = os.path.join(output_path, file_name)

                if os.path.exists(img_path):
                    img = bpy.data.images.load(img_path)
                    img_array = np.array(img.pixels).reshape((res_y, res_x, 4))

                    x_start, x_end = col * res_x, (col + 1) * res_x
                    y_start, y_end = (directions - 1 - i) * res_y, (directions - i) * res_y

                    sheet_pixels[y_start:y_end, x_start:x_end] = img_array

                    bpy.data.images.remove(img)
                    if not KEEP_INDIVIDUAL_FRAMES: os.remove(img_path)

        sheet_img = bpy.data.images.new(sheet_name, width=sheet_width, height=sheet_height, alpha=True)
        sheet_img.pixels = sheet_pixels.flatten()
        sheet_img.filepath_raw = os.path.join(output_path, sheet_name)
        sheet_img.file_format = 'PNG'
        sheet_img.save()
        print(f"Sprite Sheet saved to: {os.path.join(output_path, sheet_name)}")

    build_sheet(SHEET_NAME, "")
    build_sheet(SHADOW_SHEET_NAME, "_shadow")
    print("\n--- SUCCESS ---")