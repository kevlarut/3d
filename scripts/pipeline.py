"""
Automated Mixamo-FBX -> Diablo sprite-sheet pipeline (the Blender side).

Runs either under a real Blender:
    blender --background --factory-startup --python scripts/pipeline.py -- --folder <dir> --root <repo>
or under the `bpy` pip module:
    python scripts/pipeline.py --folder <dir> --root <repo>

It performs, for one character folder, the manual steps from
workflow-instructions.md Phases 3-4:
  1. New empty file (also deletes the default cube/camera/light).
  2. Import the idle FBX (brings in the armature + mesh).
  3. Import each action FBX (run, attack, hit, die), keep its action, delete
     its imported skeleton/mesh.
  4. Lay the actions end-to-end in an NLA track, in order.
  5. Read back each strip's start/end frames -> ANIMATION_ZONES.
  6. Wire <folder>/rodin/shaded.png into the mesh material's Base Color.
  7. Write <folder>/<folder>-sprite-script.py (a copy of the repo's
     blender-script.py with output name + detected zones baked in).
  8. Save <folder>/<folder>.blend, then render + stitch the sprite sheets into
     sprites/<folder>.png and sprites/<folder>-shadow.png.
"""

import bpy
import os
import re
import sys
import json
import numpy as np

# ==========================================================================
# 0. ARGUMENTS & CONFIG
# ==========================================================================

def parse_args():
    argv = list(sys.argv)
    # Under `blender --python x.py -- a b`, real args follow the first "--".
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]  # bpy-module mode: everything after the script name
    out = {"folder": None, "root": None}
    it = iter(argv)
    for tok in it:
        if tok == "--folder":
            out["folder"] = next(it, None)
        elif tok == "--root":
            out["root"] = next(it, None)
    if not out["folder"]:
        raise SystemExit("pipeline.py: --folder <dir> is required")
    out["folder"] = os.path.abspath(out["folder"])
    if not out["root"]:
        out["root"] = os.path.abspath(os.path.join(out["folder"], ".."))
    out["root"] = os.path.abspath(out["root"])
    return out

ARGS = parse_args()
FOLDER = ARGS["folder"]
ROOT = ARGS["root"]
FOLDER_NAME = os.path.basename(FOLDER.rstrip("/"))

# Render config. Defaults match the repo's other sprite scripts; env vars let a
# CI / low-power run trade quality for speed without editing this file.
DIRECTIONS = int(os.environ.get("SPRITE_DIRECTIONS", "8"))
RES = int(os.environ.get("SPRITE_RES", "128"))
SAMPLES = os.environ.get("SPRITE_SAMPLES")  # None -> leave EEVEE default
CAMERA_ZOOM_ENV = os.environ.get("SPRITE_ZOOM")      # override auto-fit
TARGET_HEIGHT_ENV = os.environ.get("SPRITE_TARGET")  # override auto-fit
SHADOW_OPACITY = float(os.environ.get("SPRITE_SHADOW_OPACITY", "0.45"))

SPRITES_DIR = os.path.join(ROOT, "sprites")
SHEET_NAME = f"{FOLDER_NAME}.png"
SHADOW_SHEET_NAME = f"{FOLDER_NAME}-shadow.png"

# The five roles, in the required NLA order, with default column counts (from
# the workflow-instructions.md template: 4/8/8/4/8 == 32 columns).
ROLES = [
    ("idle",    4),
    ("running", 8),
    ("attack",  8),
    ("hit",     4),
    ("die",     8),
]

# Keyword patterns to recognise a Mixamo file name for each role. Checked in
# this order; the first unused file that matches wins. Tuned so a dedicated
# "attack"/"slash" clip is not stolen by the "hit" bucket, and vice-versa.
ROLE_KEYWORDS = {
    "idle":    [r"idle"],
    "running": [r"\brun\b", r"run", r"jog", r"sprint"],
    "attack":  [r"attack", r"slash", r"magic", r"cast", r"shoot", r"aim",
                r"melee", r"swing", r"stab"],
    "hit":     [r"impact", r"\bhit\b", r"react", r"damage", r"taking",
                r"recoil", r"stagger", r"punch"],
    "die":     [r"death", r"dying", r"\bdie\b", r"dead", r"falling"],
}


def log(msg):
    print(f"[pipeline] {msg}", flush=True)


# ==========================================================================
# 1. RESOLVE WHICH FBX IS WHICH ROLE
# ==========================================================================

def resolve_roles():
    """Return an ordered list of (role, count, filepath) for roles present."""
    fbx_files = [f for f in os.listdir(FOLDER) if f.lower().endswith(".fbx")]

    # Explicit override file wins: { "idle": "Idle.fbx", "running": "...", ... }
    override = {}
    cfg = os.path.join(FOLDER, "actions.json")
    if os.path.exists(cfg):
        with open(cfg) as fh:
            override = {k.lower(): v for k, v in json.load(fh).items()}
        log(f"found actions.json override: {override}")

    used = set()
    mapping = []
    for role, count in ROLES:
        chosen = None
        if role in override and override[role]:
            chosen = override[role]
        else:
            for pat in ROLE_KEYWORDS[role]:
                for f in fbx_files:
                    if f in used:
                        continue
                    if re.search(pat, f, re.IGNORECASE):
                        chosen = f
                        break
                if chosen:
                    break
        if chosen:
            used.add(chosen)
            mapping.append((role, count, os.path.join(FOLDER, chosen)))
            log(f"  {role:8s} -> {chosen}")
        else:
            log(f"  {role:8s} -> (none found, skipping)")

    if not mapping or mapping[0][0] != "idle":
        raise SystemExit(
            "pipeline.py: could not find an idle FBX (needed as the base mesh). "
            "Add an actions.json with an \"idle\" entry.")
    return mapping


# ==========================================================================
# 2. FBX IMPORT HELPERS
# ==========================================================================

def ensure_fbx_addon():
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")
    except Exception:
        pass  # already built in / enabled


def import_fbx(path):
    """Import an FBX; return (new_objects, new_actions)."""
    before_objs = set(bpy.data.objects)
    before_acts = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path)
    new_objs = [o for o in bpy.data.objects if o not in before_objs]
    new_acts = [a for a in bpy.data.actions if a not in before_acts]
    return new_objs, new_acts


def longest_action(actions):
    if not actions:
        return None
    return max(actions, key=lambda a: a.frame_range[1] - a.frame_range[0])


def delete_objects(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        try:
            o.select_set(True)
        except Exception:
            pass
    bpy.ops.object.delete()


# ==========================================================================
# 3. BUILD THE SCENE (import + NLA + texture)  -> returns ANIMATION_ZONES
# ==========================================================================

def build_scene(mapping):
    # 1. New empty file: no default cube / camera / light.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ensure_fbx_addon()

    # 2. Import idle -> keep its armature + mesh(es).
    idle_role, idle_count, idle_path = mapping[0]
    log(f"importing idle: {os.path.basename(idle_path)}")
    idle_objs, idle_acts = import_fbx(idle_path)

    armature = next((o for o in idle_objs if o.type == "ARMATURE"), None)
    meshes = [o for o in idle_objs if o.type == "MESH"]
    if not armature:
        raise SystemExit("pipeline.py: idle FBX did not contain an armature")
    armature.name = "Armature"  # what the render step looks for
    armature.rotation_euler = (0, 0, 0)

    idle_action = longest_action(idle_acts)
    if idle_action:
        idle_action.use_fake_user = True
        idle_action.name = "idle"

    captured = [(idle_role, idle_count, idle_action)]

    # 3. Import each remaining action, steal its action, delete its skeleton.
    for role, count, path in mapping[1:]:
        log(f"importing {role}: {os.path.basename(path)}")
        new_objs, new_acts = import_fbx(path)
        act = longest_action(new_acts)
        if act:
            act.use_fake_user = True
            act.name = role
            captured.append((role, count, act))
        else:
            log(f"  warning: no action found in {os.path.basename(path)}")
        delete_objects(new_objs)

    # 4. Lay the actions end-to-end in one NLA track.
    ad = armature.animation_data_create()
    ad.action = None  # NLA drives the pose, not an active action
    track = ad.nla_tracks.new()
    track.name = "Sprite_Sequence"

    zones = []
    cursor = 1
    for role, count, act in captured:
        if act is None:
            continue
        strip = track.strips.new(role, int(cursor), act)
        start = int(round(strip.frame_start))
        end = int(round(strip.frame_end))
        zones.append({"name": role, "start": start, "end": end, "count": count})
        log(f"  NLA strip {role:8s} frames {start}-{end}")
        cursor = end  # next strip begins where this one ends

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(cursor)

    # 6. Wire the shaded texture into Base Color.
    apply_shaded_texture(meshes)

    return zones, armature, meshes


def apply_shaded_texture(meshes):
    shaded = None
    for sub in ("rodin", "rodin-obj"):
        cand = os.path.join(FOLDER, sub, "shaded.png")
        if os.path.exists(cand):
            shaded = cand
            break
    if not shaded:
        log("no rodin/shaded.png found; leaving imported materials as-is")
        return
    log(f"applying base color texture: {os.path.relpath(shaded, ROOT)}")
    img = bpy.data.images.load(shaded, check_existing=True)

    for mesh in meshes:
        if not mesh.data.materials:
            mat = bpy.data.materials.new(f"{mesh.name}_mat")
            mat.use_nodes = True
            mesh.data.materials.append(mat)
        for slot in mesh.material_slots:
            mat = slot.material
            if not mat:
                continue
            mat.use_nodes = True
            nt = mat.node_tree
            bsdf = nt.nodes.get("Principled BSDF") or next(
                (n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not bsdf:
                continue
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.location = (bsdf.location.x - 400, bsdf.location.y)
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])


# ==========================================================================
# 4. AUTO-FRAME  (measure the character so any rig size is well composed)
# ==========================================================================

def measure_character(meshes):
    """World-space height + vertical centre of the mesh at a mid-idle frame."""
    scene = bpy.context.scene
    scene.frame_set(int((scene.frame_start + scene.frame_end) / 4) or 1)
    bpy.context.view_layer.update()
    zs = []
    for mesh in meshes:
        mw = mesh.matrix_world
        for corner in mesh.bound_box:
            zs.append((mw @ __import__("mathutils").Vector(corner)).z)
    if not zs:
        return 1.8, 0.9
    height = max(zs) - min(zs)
    centre = (max(zs) + min(zs)) / 2.0
    return max(height, 0.1), centre


# ==========================================================================
# 5. WRITE THE PER-FOLDER GENERATION SCRIPT  (faithful copy w/ edited header)
# ==========================================================================

def write_folder_script(zones):
    src = os.path.join(ROOT, "blender-script.py")
    if not os.path.exists(src):
        log("blender-script.py not found at repo root; skipping per-folder copy")
        return
    with open(src) as fh:
        text = fh.read()

    posix_out = SPRITES_DIR.replace("\\", "/")
    text = re.sub(r'output_path\s*=\s*".*?"',
                  f'output_path = "{posix_out}"', text, count=1)
    text = re.sub(r'SHEET_NAME\s*=\s*".*?"',
                  f'SHEET_NAME = "{SHEET_NAME}"', text, count=1)
    text = re.sub(r'SHADOW_SHEET_NAME\s*=\s*".*?"',
                  f'SHADOW_SHEET_NAME = "{SHADOW_SHEET_NAME}"', text, count=1)

    zones_src = "ANIMATION_ZONES = [\n" + "".join(
        f'    {{"name": "{z["name"]}", "start": {z["start"]}, '
        f'"end": {z["end"]}, "count": {z["count"]}}},\n' for z in zones
    ) + "]"
    text = re.sub(r'ANIMATION_ZONES\s*=\s*\[.*?\]', zones_src, text,
                  count=1, flags=re.DOTALL)

    dst = os.path.join(FOLDER, f"{FOLDER_NAME}-sprite-script.py")
    with open(dst, "w") as fh:
        fh.write(text)
    log(f"wrote {os.path.relpath(dst, ROOT)}")


# ==========================================================================
# 6. RENDER + STITCH  (lifted from blender-script.py, parameterised)
# ==========================================================================

def render_and_stitch(zones, armature, meshes):
    from mathutils import Vector

    if not os.path.exists(SPRITES_DIR):
        os.makedirs(SPRITES_DIR)
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = RES
    scene.render.film_transparent = True
    # EEVEE engine name changed in 4.2 (BLENDER_EEVEE -> BLENDER_EEVEE_NEXT).
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except Exception:
            continue
    if SAMPLES and hasattr(scene, "eevee"):
        try:
            scene.eevee.taa_render_samples = int(SAMPLES)
        except Exception:
            pass

    # Mixamo transparency fix for EEVEE.
    for mat in bpy.data.materials:
        if mat.node_tree:
            if hasattr(mat, "blend_method"):
                mat.blend_method = "OPAQUE"
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            bsdf = nodes.get("Principled BSDF")
            if bsdf and "Alpha" in bsdf.inputs:
                for link in list(bsdf.inputs["Alpha"].links):
                    links.remove(link)
                bsdf.inputs["Alpha"].default_value = 1.0

    # Lighting
    bpy.ops.object.select_by_type(type="LIGHT")
    bpy.ops.object.delete()
    key_data = bpy.data.lights.new("KeyLight", type="SUN")
    key_obj = bpy.data.objects.new("KeyLight", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (0.6, 0, -0.15)
    key_data.energy, key_data.color, key_data.angle = 4.0, (1.0, 0.95, 0.9), 0.1
    fill_data = bpy.data.lights.new("FillLight", type="SUN")
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (0.785, 0, -2.356)
    fill_data.energy, fill_data.color = 0.8, (0.7, 0.8, 1.0)
    fill_data.use_shadow = False
    if not scene.world:
        scene.world = bpy.data.worlds.new("SpriteWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
        bg.inputs["Strength"].default_value = 1.0

    # Diablo-style shadow catcher
    shadow_plane = build_shadow_catcher(scene)

    # Auto-frame the character.
    height, centre = measure_character(meshes)
    zoom = float(CAMERA_ZOOM_ENV) if CAMERA_ZOOM_ENV else round(height * 2.3, 3)
    target_h = float(TARGET_HEIGHT_ENV) if TARGET_HEIGHT_ENV else round(centre, 3)
    log(f"character height ~{height:.2f}m -> ortho_scale={zoom}, target={target_h}")

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = zoom
    cam.location = (8, -8, 6)
    target = bpy.data.objects.new("CamTarget", None)
    scene.collection.objects.link(target)
    target.location = (0, 0, target_h)
    track = cam.constraints.new(type="TRACK_TO")
    track.target, track.track_axis, track.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    bpy.context.view_layer.update()
    # TRACK_TO does not always evaluate in --background; bake the aim into a
    # fixed camera matrix (as townguard/wolf scripts do).
    bpy.context.view_layer.update()
    direction = (target.location - Vector(cam.location))
    rot = direction.to_track_quat("-Z", "Y").to_euler()
    cam.constraints.clear()
    cam.rotation_euler = rot
    bpy.context.view_layer.update()

    total_columns = sum(z["count"] for z in zones)
    angle_step = 360 / DIRECTIONS
    log(f"rendering {DIRECTIONS} dirs x {total_columns} cols x2 passes "
        f"= {DIRECTIONS * total_columns * 2} frames")

    for i in range(DIRECTIONS):
        armature.rotation_euler[2] = (angle_step * i) * (3.14159 / 180)
        current_col = 0
        for zone in zones:
            zlen = zone["end"] - zone["start"]
            for j in range(zone["count"]):
                f = int(zone["start"] + ((j + 0.5) * zlen / zone["count"]))
                scene.frame_set(f)
                bpy.context.view_layer.update()
                shadow_plane.hide_render = True
                scene.render.filepath = os.path.join(
                    SPRITES_DIR, f"dir{i}_col{current_col:02d}.png")
                bpy.ops.render.render(write_still=True)
                shadow_plane.hide_render = False
                scene.render.filepath = os.path.join(
                    SPRITES_DIR, f"dir{i}_col{current_col:02d}_shadow.png")
                bpy.ops.render.render(write_still=True)
                current_col += 1
    armature.rotation_euler[2] = 0
    shadow_plane.hide_render = True

    build_sheet(SHEET_NAME, "", total_columns)
    build_sheet(SHADOW_SHEET_NAME, "_shadow", total_columns)
    log("SUCCESS")


def build_shadow_catcher(scene):
    old = bpy.data.materials.get("ShadowCatcher")
    if old:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new("ShadowCatcher")
    m.use_nodes = True
    m.blend_method = "BLEND"
    n, l = m.node_tree.nodes, m.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    mix = n.new("ShaderNodeMixShader")
    transp = n.new("ShaderNodeBsdfTransparent")
    black = n.new("ShaderNodeEmission")
    black.inputs["Color"].default_value = (0, 0, 0, 1)
    diff = n.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    to_rgb = n.new("ShaderNodeShaderToRGB")
    to_bw = n.new("ShaderNodeRGBToBW")
    inv = n.new("ShaderNodeMath")
    inv.operation, inv.use_clamp, inv.inputs[0].default_value = "SUBTRACT", True, 1.0
    opac = n.new("ShaderNodeMath")
    opac.operation, opac.inputs[1].default_value = "MULTIPLY", SHADOW_OPACITY
    l.new(diff.outputs[0], to_rgb.inputs[0])
    l.new(to_rgb.outputs["Color"], to_bw.inputs[0])
    l.new(to_bw.outputs[0], inv.inputs[1])
    l.new(inv.outputs[0], opac.inputs[0])
    l.new(opac.outputs[0], mix.inputs["Fac"])
    l.new(transp.outputs[0], mix.inputs[1])
    l.new(black.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "ShadowCatcher"
    plane.data.materials.clear()
    plane.data.materials.append(m)
    plane.hide_render = True
    return plane


def build_sheet(sheet_name, suffix, total_columns):
    log(f"stitching {sheet_name}")
    w, h = total_columns * RES, DIRECTIONS * RES
    pixels = np.zeros((h, w, 4), dtype=np.float32)
    for i in range(DIRECTIONS):
        for col in range(total_columns):
            p = os.path.join(SPRITES_DIR, f"dir{i}_col{col:02d}{suffix}.png")
            if os.path.exists(p):
                img = bpy.data.images.load(p)
                arr = np.array(img.pixels).reshape((RES, RES, 4))
                xs, xe = col * RES, (col + 1) * RES
                ys, ye = (DIRECTIONS - 1 - i) * RES, (DIRECTIONS - i) * RES
                pixels[ys:ye, xs:xe] = arr
                bpy.data.images.remove(img)
                os.remove(p)
    out = bpy.data.images.new(sheet_name, width=w, height=h, alpha=True)
    out.pixels = pixels.flatten()
    out.filepath_raw = os.path.join(SPRITES_DIR, sheet_name)
    out.file_format = "PNG"
    out.save()
    log(f"saved {os.path.join('sprites', sheet_name)}")


# ==========================================================================
# 7. MAIN
# ==========================================================================

def main():
    log(f"folder: {FOLDER}")
    mapping = resolve_roles()
    zones, armature, meshes = build_scene(mapping)

    write_folder_script(zones)

    blend_path = os.path.join(FOLDER, f"{FOLDER_NAME}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log(f"saved {os.path.relpath(blend_path, ROOT)}")

    if os.environ.get("SPRITE_NO_RENDER") == "1":
        log("SPRITE_NO_RENDER=1 set; skipping render")
        print("ZONES_JSON=" + json.dumps(zones))
        return
    render_and_stitch(zones, armature, meshes)


if __name__ == "__main__":
    main()
