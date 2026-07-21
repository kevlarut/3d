import bpy
import os
import numpy as np

# ==========================================
# 1. USER SETTINGS
# ==========================================
output_path = "C:/dev/3d/sprites"
directions = 8
res_x = 128
res_y = 128

CAMERA_ZOOM = 4.0
TARGET_HEIGHT = 1.1

SHEET_NAME = "ghost.png"
SHADOW_SHEET_NAME = "ghost-shadow.png"
SHADOW_OPACITY = 0.45  # 0 = invisible, 1 = solid black Diablo shadow
SWIM_HEIGHT_OFFSET = 0.35  # Lifts the horizontal swimming rig to match vertical floating height
KEEP_INDIVIDUAL_FRAMES = False
TEST_MODE = False

# --- YOUR CUSTOM ANIMATION TIMELINE MAP ---
# NOTE: Attack / Take Damage / Die all reuse the floating frames (1-57). The
# motion is the same floating loop; the *state* differences (glow burst, red
# flash, fade-out) are driven per-column by set_ghost_state() in Section 5.
# When you record dedicated attack/hit/death clips later, just repoint the
# start/end frames below and everything else keeps working.
ANIMATION_ZONES = [
    {"name": "Idle (Floating)",        "start": 1,   "end": 57,  "count": 8},
    {"name": "Walking (Swimming)",     "start": 57,  "end": 129, "count": 8},
    {"name": "Attack (Floating)",      "start": 1,   "end": 57,  "count": 8},
    {"name": "Take Damage (Floating)", "start": 1,   "end": 57,  "count": 4},
    {"name": "Die (Floating)",         "start": 1,   "end": 57,  "count": 8}
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
# 4b. SPECTRAL GHOST MATERIAL
# ==========================================
# Semi-transparent blue-green spectral look. Uses the EEVEE-only Shader-to-RGB
# node to read real scene lighting, so lit areas render more opaque/white and
# shadowed areas render more transparent/teal. A Fresnel rim gives the white
# outline. Four named Value/RGB nodes are left exposed so the render loop can
# drive per-state effects (glow burst, red hit flash, death fade).
BASE_GLOW    = 2.0
GLOW_COLOR   = (0.05, 0.85, 0.75)   # blue-green core / shadow tint
HIGHLIGHT    = (0.85, 1.00, 0.97)   # near-white in lit areas
RIM_COLOR    = (0.90, 1.00, 1.00)   # white outline
SHADOW_ALPHA = 0.03                 # LOWERED: almost completely see-through in shadows
HILITE_ALPHA = 0.40                 # LOWERED: glassy and spectral even in bright highlights
RIM_STRENGTH = 3.0

# --- VERTICAL TAIL GRADIENT SETTINGS ---
TAIL_FADE_MIN = 0.00                # Body transparency at the very tip of the tail
TAIL_FADE_MAX = 1.00                # Body transparency multiplier at upper chest/head
TAIL_FADE_TOP = 0.70                # Height (0.0 to 1.0) where full opacity begins

def build_ghost_material():
    old = bpy.data.materials.get("GhostSpectral")
    if old: bpy.data.materials.remove(old)
    mat = bpy.data.materials.new("GhostSpectral")
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear(); L = nt.links
    def nd(t, x, y):
        node = nt.nodes.new(t); node.location = (x, y); return node

    # sample real scene lighting (EEVEE-only Shader to RGB)
    diffuse = nd('ShaderNodeBsdfDiffuse', -1300, 300)
    diffuse.inputs['Color'].default_value = (0.8, 0.9, 1.0, 1.0)
    s2rgb = nd('ShaderNodeShaderToRGB', -1100, 300)
    lum   = nd('ShaderNodeRGBToBW', -920, 300)
    L.new(diffuse.outputs['BSDF'], s2rgb.inputs['Shader'])
    L.new(s2rgb.outputs['Color'], lum.inputs['Color'])

    # alpha from shading: bright = opaque, dark = transparent
    arange = nd('ShaderNodeMapRange', -720, 320)
    arange.inputs['To Min'].default_value = SHADOW_ALPHA
    arange.inputs['To Max'].default_value = HILITE_ALPHA
    L.new(lum.outputs['Val'], arange.inputs['Value'])

    # --- VERTICAL GRADIENT TO FADE OUT THE BODY TOWARDS THE TAIL ---
    tex_coord = nd('ShaderNodeTexCoord', -1100, 500)
    sep_xyz = nd('ShaderNodeSeparateXYZ', -920, 500)
    z_range = nd('ShaderNodeMapRange', -720, 500)
    z_range.inputs['From Min'].default_value = 0.0
    z_range.inputs['From Max'].default_value = TAIL_FADE_TOP
    z_range.inputs['To Min'].default_value = TAIL_FADE_MIN
    z_range.inputs['To Max'].default_value = TAIL_FADE_MAX
    L.new(tex_coord.outputs['Generated'], sep_xyz.inputs['Vector'])
    L.new(sep_xyz.outputs['Z'], z_range.inputs['Value'])

    body_grad_mult = nd('ShaderNodeMath', -500, 320); body_grad_mult.operation = 'MULTIPLY'
    L.new(arange.outputs['Result'], body_grad_mult.inputs[0])
    L.new(z_range.outputs['Result'], body_grad_mult.inputs[1])

    # body color: teal in shadow -> white in light
    colmix = nd('ShaderNodeMix', -720, 120); colmix.data_type = 'RGBA'
    colmix.inputs[6].default_value = (*GLOW_COLOR, 1.0)
    colmix.inputs[7].default_value = (*HIGHLIGHT, 1.0)
    L.new(lum.outputs['Val'], colmix.inputs[0])

    # per-state color override (red flash on hit, etc.)
    state_color = nd('ShaderNodeRGB', -720, -120); state_color.name = "StateColor"
    state_color.outputs[0].default_value = (1.0, 0.05, 0.05, 1.0)
    state_mix = nd('ShaderNodeValue', -720, -300); state_mix.name = "StateMix"
    state_mix.outputs[0].default_value = 0.0
    tint = nd('ShaderNodeMix', -500, 120); tint.data_type = 'RGBA'
    L.new(state_mix.outputs[0], tint.inputs[0])
    L.new(colmix.outputs[2], tint.inputs[6])
    L.new(state_color.outputs[0], tint.inputs[7])

    # animatable glow
    glow = nd('ShaderNodeValue', -500, -80); glow.name = "GlowStrength"
    glow.outputs[0].default_value = BASE_GLOW
    body_emit = nd('ShaderNodeEmission', -300, 120)
    L.new(tint.outputs[2], body_emit.inputs['Color'])
    L.new(glow.outputs[0], body_emit.inputs['Strength'])

    # white Fresnel outline
    lw = nd('ShaderNodeLayerWeight', -1100, -200); lw.inputs['Blend'].default_value = 0.35
    rim_ramp = nd('ShaderNodeValToRGB', -920, -200)
    rim_ramp.color_ramp.elements[0].position = 0.55
    rim_ramp.color_ramp.elements[1].position = 0.90
    L.new(lw.outputs['Facing'], rim_ramp.inputs['Fac'])
    rim_amt = nd('ShaderNodeValue', -920, -400); rim_amt.name = "RimStrength"
    rim_amt.outputs[0].default_value = RIM_STRENGTH
    rim_str = nd('ShaderNodeMath', -700, -300); rim_str.operation = 'MULTIPLY'
    L.new(rim_ramp.outputs['Color'], rim_str.inputs[0])
    L.new(rim_amt.outputs[0], rim_str.inputs[1])
    rim_emit = nd('ShaderNodeEmission', -300, -120)
    rim_emit.inputs['Color'].default_value = (*RIM_COLOR, 1.0)
    L.new(rim_str.outputs[0], rim_emit.inputs['Strength'])

    add = nd('ShaderNodeAddShader', -80, 0)
    L.new(body_emit.outputs['Emission'], add.inputs[0])
    L.new(rim_emit.outputs['Emission'], add.inputs[1])

    # final alpha = max(body * tail_gradient, rim) * AlphaMult
    amax = nd('ShaderNodeMath', -300, 320); amax.operation = 'MAXIMUM'
    L.new(body_grad_mult.outputs[0], amax.inputs[0])
    L.new(rim_ramp.outputs['Color'], amax.inputs[1])
    alpha_mult = nd('ShaderNodeValue', -300, 480); alpha_mult.name = "AlphaMult"
    alpha_mult.outputs[0].default_value = 1.0
    afinal = nd('ShaderNodeMath', -80, 360); afinal.operation = 'MULTIPLY'
    L.new(amax.outputs[0], afinal.inputs[0])
    L.new(alpha_mult.outputs[0], afinal.inputs[1])

    transp = nd('ShaderNodeBsdfTransparent', -80, -200)
    mix = nd('ShaderNodeMixShader', 160, 120)
    L.new(afinal.outputs[0], mix.inputs[0])
    L.new(transp.outputs[0], mix.inputs[1])   # alpha 0 -> see-through
    L.new(add.outputs[0], mix.inputs[2])      # alpha 1 -> glowing
    out = nd('ShaderNodeOutputMaterial', 380, 120)
    L.new(mix.outputs[0], out.inputs['Surface'])

    if hasattr(mat, 'surface_render_method'): mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    for a in ('use_transparent_shadow', 'use_transparency_overlap'):
        if hasattr(mat, a): setattr(mat, a, True)

    return mat, {"glow": glow, "alpha": alpha_mult,
                 "state_mix": state_mix, "state_color": state_color}

ghost_mat, GHOST = build_ghost_material()

# assign to every ghost mesh (all meshes except the shadow catcher)
for ob in bpy.data.objects:
    if ob.type == 'MESH' and ob.name != 'ShadowCatcher':
        ob.data.materials.clear(); ob.data.materials.append(ghost_mat)

# ---- per-state material driver: t is 0->1 progress through the zone --------
def set_ghost_state(name, t):
    n = name.lower()
    glow, amult, smix = BASE_GLOW, 1.0, 0.0
    scol = (1.0, 0.05, 0.05, 1.0)
    rise = 0.0
    if "attack" in n:
        # --- NEW BELL-CURVE SURGE ---
        # Rapidly ramps up to peak at t=0.35 (strike), then smoothly fades back to normal by t=1.0
        if t < 0.35:
            intensity = (t / 0.35) ** 1.5          # Fast wind-up
        else:
            intensity = ((1.0 - t) / 0.65) ** 1.5  # Smooth fade back to Idle baseline

        glow = BASE_GLOW + intensity * 18.0        # Huge emission spike during strike
        amult = 1.0 + intensity * 1.5              # Solidifies body opacity with power
        smix = intensity * 0.8                     # Overrides tint with electric attack energy
        scol = (0.7, 1.0, 0.95, 1.0)               # Searing white-cyan flash
        rise = intensity * 0.4                     # Lunges upward at the peak of the strike
    elif "walking" in n or "swimming" in n or "walk" in n or "swim" in n:
        rise = SWIM_HEIGHT_OFFSET                  # lift swimming animation to match floating height
    elif "damage" in n or "hit" in n:
        flash = 1.0 - t                            # red on impact, recovers
        smix, glow = flash, BASE_GLOW + flash * 3.0
    elif "die" in n or "death" in n:
        fade = 1.0 - t                             # dissolve to invisible
        amult, glow = fade, BASE_GLOW * fade
    GHOST["glow"].outputs[0].default_value = glow
    GHOST["alpha"].outputs[0].default_value = amult
    GHOST["state_mix"].outputs[0].default_value = smix
    GHOST["state_color"].outputs[0].default_value = scol
    return rise

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

                # drive the spectral material for this state + position in the zone
                count = zone["count"]
                t = j / (count - 1) if count > 1 else 0.0
                char.delta_location.z = set_ghost_state(zone["name"], t)

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
    char.delta_location.z = 0
    set_ghost_state("Idle", 0.0)   # leave the .blend in a clean baseline state
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

        # Clean up generated sheet image block from Blender memory
        if sheet_img.name in bpy.data.images:
            bpy.data.images.remove(sheet_img)

    build_sheet(SHEET_NAME, "")
    build_sheet(SHADOW_SHEET_NAME, "_shadow")

    # ==========================================
    # 7. CLEANUP
    # ==========================================
    print("\nCleaning up temporary shadow platform and data blocks...")
    if shadow_plane and shadow_plane.name in bpy.data.objects:
        mesh_data = shadow_plane.data
        bpy.data.objects.remove(shadow_plane, do_unlink=True)
        if mesh_data and mesh_data.name in bpy.data.meshes:
            bpy.data.meshes.remove(mesh_data)

    if shadow_mat and shadow_mat.name in bpy.data.materials:
        bpy.data.materials.remove(shadow_mat)

    print("\n--- SUCCESS ---")