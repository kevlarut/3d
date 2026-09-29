"""Generate 3D-printable "used future" table-sign bases (Star Wars-style greebled blocks).

Each base is a low wedge (90 x 40 mm footprint, ~26 mm tall) with a vertical slot
that holds a laminated 4x6" card (or thin acrylic). The slot runs out both ends,
so a 4" wide card can overhang slightly. Both sloped faces carry a recessed
control panel (keypad + two-ring dial), flanked by vents (front) and conduit pipes (back).
Every table uses the same base; the card carries the table number.

Run headless (units are millimetres):
  blender -b --factory-startup -P make_bases.py -- --slot 1.0 --render
Options:
  --slot W       slot width in mm (1.0 = laminated card, 2.3 = up to 2 mm acrylic)
  --out DIR      output folder (default: ./stl next to this script)
  --render       also render preview PNGs to ./previews
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Dimensions (mm) --------------------------------------------------------
L = 90.0           # length along X
HALF_BOTTOM = 20.0 # half depth at the table
HALF_TOP = 11.0    # half depth at the top of the wedge
H = 22.0           # wedge height
RIDGE_HALF = 5.0   # raised spine that deepens the slot
RIDGE_TOP = 26.0
RIDGE_HALF_LEN = 41.0
SLOT_BOTTOM = 10.0 # slot depth = RIDGE_TOP - SLOT_BOTTOM = 16 mm


# ---- Helpers -----------------------------------------------------------------
def to_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def box(name, lo, hi, frame=Matrix.Identity(4)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    size = Vector(hi) - Vector(lo)
    center = (Vector(hi) + Vector(lo)) / 2
    bm.transform(frame @ Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
    return to_object(name, bm)


def prism_x(name, profile_yz, x0, x1):
    """Extrude a YZ polygon (counter-clockwise seen from +X) from x0 to x1."""
    bm = bmesh.new()
    verts = [bm.verts.new((x0, y, z)) for y, z in profile_yz]
    face = bm.faces.new(verts)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(x1 - x0, 0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return to_object(name, bm)


def cylinder(name, radius, z0, z1, frame=Matrix.Identity(4), segments=32):
    """Cylinder along local Z from z0 to z1, placed by `frame`."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                          radius1=radius, radius2=radius, depth=z1 - z0)
    bm.transform(frame @ Matrix.Translation((0, 0, (z0 + z1) / 2)))
    return to_object(name, bm)


def bevel(obj, width):
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = 1
    mod.limit_method = "ANGLE"
    apply_modifiers(obj)


def apply_modifiers(obj):
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def boolean(target, others, operation):
    if not others:
        return
    coll = bpy.data.collections.new(f"ops_{operation}")
    bpy.context.scene.collection.children.link(coll)
    for o in others:
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    mod = target.modifiers.new(operation, "BOOLEAN")
    mod.operation = operation
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    mod.solver = "EXACT"
    apply_modifiers(target)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)


def face_frame(back):
    """Local frame on a sloped face: u along the face, v up the slope, w = outward normal."""
    dy, dz = HALF_BOTTOM - HALF_TOP, H
    n = math.hypot(dy, dz)
    s = 1 if back else -1
    u = Vector((-1, 0, 0)) if back else Vector((1, 0, 0))
    v = Vector((0, -s * dy / n, dz / n))
    w = u.cross(v)
    m = Matrix.Identity(4)
    m.col[0] = (*u, 0)
    m.col[1] = (*v, 0)
    m.col[2] = (*w, 0)
    m.col[3] = (0, s * HALF_BOTTOM, 0, 1)
    return m


def at(frame, u, v, w=0.0):
    return frame @ Matrix.Translation((u, v, w))


# ---- Model -------------------------------------------------------------------
def build_base(slot):
    wedge = prism_x("base", [(-HALF_BOTTOM, 0), (HALF_BOTTOM, 0), (HALF_TOP, H), (-HALF_TOP, H)],
                    -L / 2, L / 2)
    bevel(wedge, 1.0)
    ridge = box("ridge", (-RIDGE_HALF_LEN, -RIDGE_HALF, H - 1), (RIDGE_HALF_LEN, RIDGE_HALF, RIDGE_TOP))
    bevel(ridge, 0.8)
    boolean(wedge, [ridge], "UNION")

    cuts, adds = [], []
    plate_u, plate_v = 15.0, (4.5, 19.5)
    for back in (False, True):
        f = face_frame(back)
        side = "back" if back else "front"
        # Recessed control panel: 2x3 keypad and a two-ring dial
        cuts.append(box(f"plate_{side}", (-plate_u, plate_v[0], -1.2), (plate_u, plate_v[1], 3), f))
        for col, uc in enumerate((-11.3, -7.1, -2.9)):
            for row, vc in enumerate((9.6, 14.4)):
                adds.append(box(f"key_{side}_{col}_{row}", (uc - 1.6, vc - 1.6, -1.5), (uc + 1.6, vc + 1.6, -0.3), f))
        adds.append(cylinder(f"dial_{side}", 4.6, -1.5, -0.4, at(f, 7.5, 12.0), segments=40))
        adds.append(cylinder(f"knob_{side}", 3.0, -0.5, 0.2, at(f, 7.5, 12.0), segments=32))
        for sign in (-1, 1):
            if not back:
                # Heat-sink vents
                for i, vc in enumerate((6, 10, 14, 18)):
                    lo, hi = sorted((sign * 19.0, sign * 40.0))
                    cuts.append(box(f"vent_{sign}_{i}", (lo, vc - 1, -1.2), (hi, vc + 1, 3), f))
                # Rivets
                for vc in (3.5, 20.5):
                    adds.append(cylinder(f"rivet_{sign}_{vc}", 1.1, -0.5, 0.7,
                                         at(f, sign * 42.3, vc), segments=20))
            else:
                # Conduit pipes with clamps and junction boxes
                lo, hi = sorted((sign * 18.0, sign * 41.0))
                for i, vc in enumerate((7.5, 11.5, 15.5)):
                    pipe_frame = at(f, (lo + hi) / 2, vc, 0.4) @ Matrix.Rotation(math.pi / 2, 4, "Y")
                    adds.append(cylinder(f"pipe_{sign}_{i}", 1.5, -(hi - lo) / 2, (hi - lo) / 2,
                                         pipe_frame, segments=24))
                for uc, half in ((sign * 29.5, 1.5), (sign * 18.5, 1.8), (sign * 41.0, 2.2)):
                    adds.append(box(f"clamp_{sign}_{uc}", (uc - half, 5.0, -0.5), (uc + half, 18.0, 2.4), f))

    # End caps: recessed trapezoid panel with hex bolts
    def half_at(z, inset):
        return HALF_BOTTOM - (HALF_BOTTOM - HALF_TOP) * z / H - inset
    panel = [(-half_at(3.5, 3.5), 3.5), (half_at(3.5, 3.5), 3.5),
             (half_at(18.5, 3.5), 18.5), (-half_at(18.5, 3.5), 18.5)]
    for sign in (-1, 1):
        x0, x1 = sorted((sign * (L / 2 - 1.0), sign * (L / 2 + 5)))
        cuts.append(prism_x(f"endpanel_{sign}", panel, x0, x1))
        bolt_axis = Matrix.Rotation(math.pi / 2, 4, "Y")
        for y, z in ((-9, 7), (9, 7), (-6, 15), (6, 15)):
            frame = Matrix.Translation((0, y, z)) @ bolt_axis
            z0, z1 = sorted((sign * (L / 2 - 1.2), sign * (L / 2 + 0.6)))
            adds.append(cylinder(f"bolt_{sign}_{y}_{z}", 2.0, z0, z1, frame, segments=6))

    boolean(wedge, cuts, "DIFFERENCE")
    boolean(wedge, adds, "UNION")

    # Card slot, open at both ends, with a V lead-in on the spine
    half = slot / 2
    slot_cuts = [box("slot", (-L, -half, SLOT_BOTTOM), (L, half, RIDGE_TOP + 5)),
                 prism_x("flare", [(-half, RIDGE_TOP - 0.9), (half, RIDGE_TOP - 0.9),
                                   (half + 1.5, RIDGE_TOP + 0.6), (-half - 1.5, RIDGE_TOP + 0.6)],
                         -RIDGE_HALF_LEN - 1, RIDGE_HALF_LEN + 1)]
    boolean(wedge, slot_cuts, "DIFFERENCE")
    wedge.name = "table_base"
    return wedge


def check(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume() / 1000.0
    bm.free()
    return bad, vol


def export_stl(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0,
                          ascii_format=False, apply_modifiers=True)


# ---- Preview rendering ---------------------------------------------------------
def render_previews(base, out_dir):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "OBJECT"
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.color = (0.08, 0.08, 0.09)
    scene.display.shading.background_type = "WORLD"

    colors = [(0.75, 0.12, 0.10, 1), (0.15, 0.35, 0.75, 1), (0.85, 0.62, 0.12, 1),
              (0.20, 0.55, 0.25, 1), (0.45, 0.25, 0.65, 1)]  # red, blue, gold, green, purple
    bases = [base] + [base.copy() for _ in colors[1:]]
    for i, b in enumerate(bases):
        b.color = colors[i]
        if b is not base:
            scene.collection.objects.link(b)
    base = bases[1]
    for b in bases:
        b.hide_render = b is not base
    card = box("card", (-50.8, -0.25, SLOT_BOTTOM + 0.5), (50.8, 0.25, SLOT_BOTTOM + 0.5 + 152.4))
    card.color = (0.85, 0.83, 0.78, 1)

    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def shoot(name, loc, target, lens, show_card):
        card.hide_render = not show_card
        cam.location = loc
        direction = Vector(target) - Vector(loc)
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        cam_data.lens = lens
        scene.render.filepath = os.path.join(out_dir, name)
        bpy.ops.render.render(write_still=True)

    shoot("front_with_card.png", (-260, -470, 230), (0, 0, 70), 50, True)
    shoot("front_closeup.png", (-95, -150, 90), (0, 0, 10), 50, False)
    shoot("back_closeup.png", (95, 150, 90), (0, 0, 10), 50, False)
    # Colour-coded lineup
    for i, b in enumerate(bases):
        b.hide_render = False
        b.location = ((i - (len(bases) - 1) / 2) * 105, 0, 0)
    shoot("lineup.png", (0, -720, 400), (0, 0, 0), 50, False)
    bpy.data.objects.remove(card)


# ---- Main ----------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--slot", type=float, default=1.0)
    p.add_argument("--out", default=os.path.join(HERE, "stl"))
    p.add_argument("--render", action="store_true")
    a = p.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    out_dir = os.path.join(a.out, f"slot-{a.slot:.1f}mm")
    os.makedirs(out_dir, exist_ok=True)

    base = build_base(a.slot)
    bad, vol = check(base)
    path = os.path.join(out_dir, "table-base.stl")
    export_stl(base, path)
    print(f"[table-sign] {path}: {vol:.1f} cm3, non-manifold edges: {bad}")
    if a.render:
        render_previews(base, os.path.join(HERE, "previews"))


main()
