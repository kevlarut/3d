"""Photoreal Cycles mockups of the table signs: printed base + laminated card on a game table.

  blender -b --factory-startup -P make_mockups.py -- --tables 11 [--samples 512]

Uses the STLs from make_bases.py and the card JPGs from make_cards.py, so run those first.
Writes mockups/table-NN-name.png.
"""
import argparse
import ast
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
HDRI = os.path.join(bpy.utils.system_resource("DATAFILES"), "studiolights", "world", "interior.exr")

CARD_W, CARD_H, CARD_T = 0.1016, 0.1524, 0.0006   # 4x6" laminated card, metres
CARD_BOTTOM = 0.0105                              # resting 0.5 mm above the slot floor
BASE_COLOR = (0.007, 0.007, 0.008, 1.0)            # black PLA, linear RGB


def load_tables():
    """Read the TABLES list from make_cards.py (single source of names and colours)."""
    tree = ast.parse(open(os.path.join(HERE, "make_cards.py"), encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TABLES":
            return ast.literal_eval(node.value)
    raise RuntimeError("TABLES not found in make_cards.py")


def srgb_to_linear(hex_color):
    rgb = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb) + (1.0,)


# ---- Setup ---------------------------------------------------------------------
def enable_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            bpy.context.scene.cycles.device = "GPU"
            return kind
    return "CPU"


def setup_render(samples, res):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    print("[mockup] device:", enable_gpu())


def world():
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value[2] = math.radians(140)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 0.18
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])


def area_light(name, loc, target, size, power, color):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "DISK"
    data.size = size
    data.energy = power
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


# ---- Materials -------------------------------------------------------------------
def principled(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat, mat.node_tree, mat.node_tree.nodes["Principled BSDF"]


def wood_material():
    mat, nt, bsdf = principled("wood")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 14.0, 1.0)  # stretch grain along X
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 4.0
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 4.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.015, 0.006, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.075, 0.03, 1)
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[2].default_value = 0.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], mix.inputs[0])
    nt.links.new(noise.outputs["Fac"], mix.inputs[1])
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.5
    bsdf.inputs["Coat Weight"].default_value = 0.15
    bsdf.inputs["Coat Roughness"].default_value = 0.2
    return mat


def pla_material(color):
    """Matte PLA with 0.2 mm layer lines and a thin dark wash settled into the recesses."""
    mat, nt, bsdf = principled("pla")
    N, L = nt.nodes, nt.links
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.002
    ao.only_local = True
    wash = N.new("ShaderNodeMix")
    wash.data_type = "RGBA"
    wash.inputs["A"].default_value = [c * 0.3 for c in color[:3]] + [1]
    wash.inputs["B"].default_value = color
    L.new(ao.outputs["AO"], wash.inputs["Factor"])
    L.new(wash.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.38
    # Layer lines: a sine on Z with a 0.2 mm period
    coord = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    mul = N.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 2 * math.pi / 0.0002
    sine = N.new("ShaderNodeMath")
    sine.operation = "SINE"
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.1
    bump.inputs["Distance"].default_value = 0.00002
    L.new(coord.outputs["Object"], sep.inputs["Vector"])
    L.new(sep.outputs["Z"], mul.inputs[0])
    L.new(mul.outputs[0], sine.inputs[0])
    L.new(sine.outputs[0], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def laminated(name, image_path=None, color=(0.8, 0.8, 0.78, 1)):
    """Paper under a matte laminate film."""
    mat, nt, bsdf = principled(name)
    if image_path:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image_path)
        tex.interpolation = "Cubic"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Coat Weight"].default_value = 0.8
    bsdf.inputs["Coat Roughness"].default_value = 0.18
    bsdf.inputs["Coat IOR"].default_value = 1.5
    return mat


def dice_material(color):
    mat, nt, bsdf = principled("dice")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Subsurface Weight"].default_value = 0.3
    bsdf.inputs["Subsurface Radius"].default_value = (0.002, 0.002, 0.002)
    return mat


# ---- Objects ---------------------------------------------------------------------
def link(name, bm, mats):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for m in mats:
        mesh.materials.append(m)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def card(front_mat, back_mat, edge_mat):
    """Box with the card image UV-mapped on the -Y face."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new()
    x0, x1 = -CARD_W / 2, CARD_W / 2
    y0, y1 = -CARD_T / 2, CARD_T / 2
    z0, z1 = CARD_BOTTOM, CARD_BOTTOM + CARD_H
    v = {(i, j, k): bm.verts.new((x, y, z))
         for i, x in enumerate((x0, x1)) for j, y in enumerate((y0, y1)) for k, z in enumerate((z0, z1))}
    faces = [  # (verts, material index)
        ((v[0, 0, 0], v[1, 0, 0], v[1, 0, 1], v[0, 0, 1]), 0),  # front (-Y)
        ((v[1, 1, 0], v[0, 1, 0], v[0, 1, 1], v[1, 1, 1]), 1),  # back
        ((v[0, 1, 0], v[0, 0, 0], v[0, 0, 1], v[0, 1, 1]), 2),
        ((v[1, 0, 0], v[1, 1, 0], v[1, 1, 1], v[1, 0, 1]), 2),
        ((v[0, 0, 1], v[1, 0, 1], v[1, 1, 1], v[0, 1, 1]), 2),
        ((v[0, 1, 0], v[1, 1, 0], v[1, 0, 0], v[0, 0, 0]), 2),
    ]
    for verts, mi in faces:
        f = bm.faces.new(verts)
        f.material_index = mi
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = ((co.x - x0) / CARD_W, (co.z - z0) / CARD_H)
    return link("card", bm, [front_mat, back_mat, edge_mat])


def base(stl_path, mat):
    bpy.ops.wm.stl_import(filepath=stl_path, global_scale=0.001)
    obj = bpy.context.selected_objects[0]
    print("[mockup] imported base scale:", tuple(obj.scale))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # textures work in metres
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(35))
    obj.data.materials.append(mat)
    return obj


def die(kind, radius, loc, yaw, mat):
    bm = bmesh.new()
    if kind == "d20":
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    else:
        bmesh.ops.create_cube(bm, size=radius * 2)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=radius * 0.18, segments=4, affect="EDGES")
    # Rest the die on its lowest face
    bm.normal_update()
    down = min(bm.faces, key=lambda f: f.normal.z).normal
    rot = down.rotation_difference(Vector((0, 0, -1))).to_matrix().to_4x4()
    bm.transform(rot)
    lowest = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -lowest))
    obj = link(kind, bm, [mat])
    obj.location = loc
    obj.rotation_euler[2] = yaw
    for p in obj.data.polygons:
        p.use_smooth = kind != "d20"
    return obj


def camera(loc, target, lens, fstop):
    data = bpy.data.cameras.new("cam")
    data.lens = lens
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new("cam", data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    data.dof.focus_distance = direction.length
    bpy.context.scene.camera = cam


# ---- Scene -----------------------------------------------------------------------
def render_table(number, name, samples, res, out_dir, closeup):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(samples, res)
    world()

    slug = name.lower().replace(" ", "-")
    card_jpg = os.path.join(HERE, "cards", "jpg", f"table-{number:02d}-{slug}.jpg")
    stl = os.path.join(HERE, "stl", "slot-1.0mm", "table-base.stl")

    bpy.ops.mesh.primitive_plane_add(size=1.6)
    bpy.context.object.data.materials.append(wood_material())

    base(stl, pla_material(BASE_COLOR))
    card(laminated("card_front", card_jpg), laminated("card_back"), laminated("card_edge"))

    rng = random.Random(number)
    die("d20", 0.0115, (0.105, 0.075, 0), rng.uniform(0, 6.28), dice_material((0.55, 0.02, 0.02, 1)))
    die("d6", 0.008, (0.135, 0.02, 0), rng.uniform(0, 6.28), dice_material((0.02, 0.12, 0.45, 1)))
    die("d6", 0.008, (-0.125, -0.035, 0), rng.uniform(0, 6.28), dice_material((0.85, 0.85, 0.82, 1)))

    area_light("key", (-0.6, -0.12, 0.55), (0, 0, 0.07), 0.6, 55, (1.0, 0.95, 0.88))
    area_light("rim", (0.35, 0.45, 0.35), (0, 0, 0.08), 0.35, 30, (0.85, 0.92, 1.0))
    area_light("fill", (0.5, -0.4, 0.15), (0, 0, 0.07), 0.5, 8, (1.0, 1.0, 1.0))

    camera((-0.21, -0.47, 0.16), (0.004, 0, 0.078), 70, 4.0)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"table-{number:02d}-{slug}.png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[mockup] wrote", path)

    if not closeup:
        return
    # Close-up of the base (identical for every table, so only rendered once)
    bpy.data.objects.remove(bpy.context.scene.camera)
    camera((-0.075, -0.155, 0.05), (0.002, -0.012, 0.013), 90, 11)
    res_x, res_y = bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = res_y, res_x
    path = os.path.join(out_dir, f"table-{number:02d}-{slug}-closeup.png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[mockup] wrote", path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--tables", default="all", help="comma-separated table numbers, or 'all'")
    p.add_argument("--samples", type=int, default=512)
    p.add_argument("--res", type=int, nargs=2, default=(1600, 2000))
    p.add_argument("--out", default=os.path.join(HERE, "mockups"))
    p.add_argument("--no-closeup", action="store_true", help="skip the base close-up for the first table")
    a = p.parse_args(argv)

    tables = load_tables()
    wanted = range(1, len(tables) + 1) if a.tables == "all" else [int(t) for t in a.tables.split(",")]
    for i, n in enumerate(wanted):
        name, _accent, _style = tables[n - 1]
        render_table(n, name, a.samples, tuple(a.res), a.out, closeup=i == 0 and not a.no_closeup)


main()
