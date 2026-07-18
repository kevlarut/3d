# The Automated 3D-to-2D Diablo Sprite Pipeline

This document outlines the complete workflow for generating 8-directional, 32-column sprite sheets for isometric RPGs using AI generation, Mixamo, and an automated Blender Python script.

## Required Tools
* **2D Image Generator:** Midjourney, Scenario.ai, or similar.
* **3D Generator:** [Rodin 1.5](https://hyper3d.ai/rodin/)
* **Rigging & Animation:** [Mixamo](https://www.mixamo.com/) (Free Adobe account required)
* **Renderer:** [Blender](https://www.blender.org/) (Version 4.2+ recommended)

---

## Phase 1: AI Character Generation (2D to 3D)

1.  **Generate the 2D Concept:** Use an AI image generator to create a front-facing, full-body character concept (e.g., Wizard, Orc, Rogue) in a neutral/A-pose. A clean, solid background works best.
2.  **Convert to 3D (Rodin 1.5):** Upload your 2D image to Rodin 1.5 to generate the 3D model.
3.  **Extract the Files:** Download the result. If it's a `.zip`, extract it. 
    * You are looking for the raw geometry file (usually `base.obj`) and the main color texture (usually `texture_diffuse.png` or `base_color.png`).
    * Place the texture file directly into your working directory (e.g., `C:/dev/mystery-of-the-molokites/`).

---

## Phase 2: Rigging and Animation (Mixamo)



1.  **Upload the Mesh:** Go to Mixamo and click "Upload Character". Select **ONLY** the `.obj` file you got from Rodin. 
    > **Note:** The character will appear completely white in Mixamo. This is normal! Mixamo only needs the geometry to rig the skeleton.
2.  **Auto-Rig:** Place the chin, wrist, elbow, knee, and groin markers as instructed.
3.  **Download the "Master" File:** * Search for an **Idle** animation.
    * Click Download. 
    * **Crucial Setting:** Format = `FBX Binary (.fbx)`, Skin = **With Skin**.
4.  **Download the "Actions":**
    * Search for your remaining animations (e.g., Run, Attack, Hit, Die).
    * Click Download for each.
    * **Crucial Setting:** Format = `FBX Binary (.fbx)`, Skin = **Without Skin**.

---

## Phase 3: Blender Timeline Setup



1.  **Import the Master:** Open a new Blender file. Delete the default cube, camera, and light. Go to `File > Import > FBX` and import your Master (Idle) file. It will bring in the skeleton and the mesh.
2.  **"Steal" the Actions:**
    * Go to `File > Import > FBX` and import your next animation (e.g., Run).
    * A new skeleton will appear. **Select it and delete it (Press X).** The animation data is secretly retained in Blender's memory.
    * Repeat this for Attack, Hit, and Die.
3.  **Sequence the NLA Editor:**
    * Switch your bottom workspace panel to the **Non-Linear Animation (NLA) Editor**.
    * Select your Master Character's skeleton in the 3D viewport.
    * In the NLA Editor, click the **Double-Down Arrow** next to the active Idle animation to push it down into a "Strip".
    * Hover over the NLA Editor and press **Shift + A** to add your other animations (Run, Attack, Hit, Die).
    * Press **G** to grab and move the strips so they sit sequentially, end-to-end (like train cars).
4.  **Record the Frame Numbers:** Write down the exact start and end frame for each animation block. You will need these for the script!

---

## Phase 4: Automated Rendering

1.  **Open the Scripting Tab:** In Blender, go to the `Scripting` workspace at the top. Click `New` to create a new text file.
2.  **Paste the Pipeline Script:** Paste the Python code below.
3.  **Update Your Settings:**
    * Check `output_path` matches where your texture lives.
    * Update `CAMERA_ZOOM` and `TARGET_HEIGHT` if your character is too big or small.
    * **Update the `ANIMATION_ZONES`** dictionary with the exact start and end frames you recorded in Phase 3.
4.  **Run It:** Click the "Play" icon (Run Script) in the top right of the text editor. 

The script will automatically fix transparency bugs, apply Diablo-style dark fantasy lighting, render 8 directions from the exact center of your animation frames, and stitch them all into a single `spritesheet.png`.

---

## The Python Automation Script

```python
import bpy
import os
import numpy as np

# ==========================================
# 1. USER SETTINGS
# ==========================================
output_path = "C:/dev/mystery-of-the-molokites/sprites"
directions = 8
res_x = 128
res_y = 128

CAMERA_ZOOM = 4.0
TARGET_HEIGHT = 1.0

SHEET_NAME = "spritesheet.png"
KEEP_INDIVIDUAL_FRAMES = False
TEST_MODE = False 

# --- YOUR CUSTOM ANIMATION TIMELINE MAP ---
# Update "start" and "end" based on your NLA Editor!
ANIMATION_ZONES = [
    {"name": "Idle",   "start": 1,   "end": 201, "count": 4},
    {"name": "Run",    "start": 201, "end": 217, "count": 8},
    {"name": "Attack", "start": 216, "end": 272, "count": 8},
    {"name": "Hit",    "start": 272, "end": 316, "count": 4},
    {"name": "Die",    "start": 316, "end": 421, "count": 8}
]

# ==========================================
# 2. SYSTEM & TEXTURE FIX
# ==========================================
# Ensures destination folder exists
if not os.path.exists(output_path): os.makedirs(output_path)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
scene.render.film_transparent = True
scene.render.engine = 'BLENDER_EEVEE'

# Fixes Mixamo transparency bugs for Eevee Engine
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
key_obj.rotation_euler = (0.785, 0, 0.785)
key_data.energy = 4.0
key_data.color = (1.0, 0.95, 0.9)

fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (0.785, 0, -2.356)
fill_data.energy = 0.8
fill_data.color = (0.7, 0.8, 1.0)

if not scene.world: scene.world = bpy.data.worlds.new("SpriteWorld")
scene.world.use_nodes = True
bg_node = scene.world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs['Color'].default_value = (0.02, 0.02, 0.02, 1)
    bg_node.inputs['Strength'].default_value = 1.0

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
                # Adding 0.5 ensures we sample the exact center of the frame block
                f = int(zone["start"] + ((j + 0.5) * zone_length / zone["count"]))
                
                scene.frame_set(f)
                bpy.context.view_layer.update() 
                
                file_name = f"dir{i}_col{current_col:02d}.png"
                scene.render.filepath = os.path.join(output_path, file_name)
                bpy.ops.render.render(write_still=True)
                current_col += 1
                
    char.rotation_euler[2] = 0

    # ==========================================
    # 6. SPRITE SHEET BUILDER
    # ==========================================
    print("\nStitching frames into Sprite Sheet...")
    sheet_width = total_columns * res_x
    sheet_height = directions * res_y
    sheet_pixels = np.zeros((sheet_height, sheet_width, 4), dtype=np.float32)
    
    for i in range(directions):
        for col in range(total_columns):
            file_name = f"dir{i}_col{col:02d}.png"
            img_path = os.path.join(output_path, file_name)
            
            if os.path.exists(img_path):
                img = bpy.data.images.load(img_path)
                img_array = np.array(img.pixels).reshape((res_y, res_x, 4))
                
                x_start, x_end = col * res_x, (col + 1) * res_x
                y_start, y_end = (directions - 1 - i) * res_y, (directions - i) * res_y
                
                sheet_pixels[y_start:y_end, x_start:x_end] = img_array
                
                bpy.data.images.remove(img)
                if not KEEP_INDIVIDUAL_FRAMES: os.remove(img_path)
    
    sheet_img = bpy.data.images.new(SHEET_NAME, width=sheet_width, height=sheet_height, alpha=True)
    sheet_img.pixels = sheet_pixels.flatten()
    sheet_img.filepath_raw = os.path.join(output_path, SHEET_NAME)
    sheet_img.file_format = 'PNG'
    sheet_img.save()
    print(f"\n--- SUCCESS ---\nSprite Sheet saved to: {os.path.join(output_path, SHEET_NAME)}")