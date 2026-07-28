"""Weapons that can be seated in a Mixamo character's hand.

Two sources for the "Sting"-style Elvish short sword, in priority order:

1. A modelled `sting-sword.obj` sitting in the character folder. This is the
   preferred one — it is a real sculpt in four parts (Manche/Lame/Pommeau/Garde
   — grip/blade/pommel/guard). Its placement in the hand is baked in below as a
   bone-local transform, measured from the pose it was hand-fitted to.
2. Otherwise, a procedural fallback: a straight, double-edged, tapered blade
   with Roman-spatha proportions, a short crossguard, leather grip and round
   pommel, built from primitives.

Either way the result is bone-parented to the right-hand bone so it follows
every animation.

Placement is tuned for the standard Mixamo rig (mixamorig:RightHand). The
procedural fallback can be overridden per-run via env vars while dialing it in:
  SPRITE_W_LOC="x,y,z"      local offset from the hand bone (metres)
  SPRITE_W_ROT="rx,ry,rz"   local rotation (degrees)
  SPRITE_W_LEN=0.36         blade half-length (metres)
"""
import os
import math


def _env_vec(name, default):
    v = os.environ.get(name)
    if not v:
        return default
    return tuple(float(x) for x in v.split(","))


# Defaults dialed in visually for the hobbit-female sword-and-shield rig.
DEFAULT_LOC = _env_vec("SPRITE_W_LOC", (0.0, 0.0, 0.0))
DEFAULT_ROT_DEG = _env_vec("SPRITE_W_ROT", (-40.0, 0.0, 0.0))
BLADE_HALF_LEN = float(os.environ.get("SPRITE_W_LEN", "0.46"))

# --- modelled sword -------------------------------------------------------
# File looked for in the character folder, and how it sits relative to the
# right-hand bone. These numbers were read back out of hobbit-female.blend after
# the sword was positioned by hand in the palm on an idle frame, so re-running
# the generator puts it back exactly where it was fitted.
#
# The transform is bone-local, so it rides the armature's own scale: a character
# built at a different --scale gets a proportionally sized sword for free.
# The scale is uniformly negative because the sword was mirrored into the right
# hand; the blade is symmetric, so this only flips handedness, not the look.
OBJ_FILENAME = "sting-sword.obj"
OBJ_LOC = (0.281728, 0.099366, -0.027595)
OBJ_ROT_RAD = (1.778652, -0.347320, 1.871459)
OBJ_SCALE = (-0.017186, -0.017186, -0.017186)


def _material(bpy, name, color, metallic, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    return m


def make_sting(bpy):
    """Build the sword mesh. Grip runs along local +Y; guard sits at the
    origin; blade points +Y, pommel at -Y. Returns the joined object."""
    import bmesh

    steel = _material(bpy, "Sting_Steel", (0.70, 0.77, 0.86), 1.0, 0.15)
    gold = _material(bpy, "Sting_Guard", (0.80, 0.62, 0.22), 1.0, 0.30)
    leather = _material(bpy, "Sting_Grip", (0.14, 0.09, 0.06), 0.0, 0.70)

    parts = []
    # Blade: a flattened cube, tapered to a point at the +Y tip.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.05 + BLADE_HALF_LEN, 0))
    blade = bpy.context.active_object
    blade.name = "Blade"
    blade.scale = (0.075, BLADE_HALF_LEN, 0.016)  # width, length, thickness
    bpy.ops.object.transform_apply(scale=True)
    me = blade.data
    bm = bmesh.new()
    bm.from_mesh(me)
    ymax = max(v.co.y for v in bm.verts)
    y0 = 0.05
    for v in bm.verts:
        if abs(v.co.y - ymax) < 1e-4:
            v.co.x = 0.0
            v.co.z = 0.0                      # collapse tip to a point
        else:
            t = max(0.0, min(1.0, (v.co.y - y0) / (ymax - y0)))
            v.co.x *= (1.0 - 0.45 * t)        # gentle edge taper
    bm.to_mesh(me)
    bm.free()
    blade.data.materials.append(steel)
    parts.append(blade)

    # Crossguard: slim bar across local X.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.05, 0))
    guard = bpy.context.active_object
    guard.name = "Guard"
    guard.scale = (0.20, 0.026, 0.030)
    bpy.ops.object.transform_apply(scale=True)
    guard.data.materials.append(gold)
    parts.append(guard)

    # Grip: cylinder below the guard (-Y).
    bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=0.12, location=(0, 0, 0))
    grip = bpy.context.active_object
    grip.name = "Grip"
    grip.rotation_euler = (math.radians(90), 0, 0)  # align cylinder axis to Y
    bpy.ops.object.transform_apply(rotation=True)
    grip.location = (0, -0.005, 0)
    grip.data.materials.append(leather)
    parts.append(grip)

    # Pommel: small sphere at the grip end.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.030, location=(0, -0.075, 0))
    pom = bpy.context.active_object
    pom.name = "Pommel"
    pom.data.materials.append(gold)
    parts.append(pom)

    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = blade
    bpy.ops.object.join()
    blade.name = "StingSword"
    return blade


def import_sting_obj(bpy, path):
    """Import the modelled sword, returning its freshly added mesh objects."""
    before = {o.name for o in bpy.data.objects}
    if hasattr(bpy.ops.wm, "obj_import"):        # Blender 3.3+
        bpy.ops.wm.obj_import(filepath=path)
    else:                                        # legacy Python importer
        bpy.ops.import_scene.obj(filepath=path)
    return [o for o in bpy.data.objects
            if o.name not in before and o.type == "MESH"]


def _bone_parent(bpy, obj, armature, hand_bone, loc, rot_rad, scale=None):
    """Parent obj to a bone and place it with a bone-local transform."""
    from mathutils import Matrix, Euler

    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = hand_bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = loc
    obj.rotation_euler = Euler(rot_rad, "XYZ")
    if scale is not None:
        obj.scale = scale


def resolve_hand_bone(armature, hand_bone="mixamorig:RightHand"):
    if hand_bone in armature.data.bones:
        return hand_bone
    # fall back to any bone whose name ends in RightHand
    cands = [b.name for b in armature.data.bones
             if b.name.endswith("RightHand")]
    if not cands:
        raise RuntimeError("no right-hand bone found for weapon attach")
    return cands[0]


def attach_to_hand(bpy, armature, hand_bone="mixamorig:RightHand",
                   loc=None, rot_deg=None, folder=None):
    """Seat the sword in the right hand and bone-parent it there.

    Uses the modelled `sting-sword.obj` from `folder` when present, otherwise
    falls back to the procedural build. Returns (object, bone_name); for the
    modelled sword the object returned is the blade, the piece the other parts
    are grouped with.
    """
    hand_bone = resolve_hand_bone(armature, hand_bone)

    obj_path = os.path.join(folder, OBJ_FILENAME) if folder else None
    if obj_path and os.path.exists(obj_path):
        parts = import_sting_obj(bpy, obj_path)
        if not parts:
            raise RuntimeError(f"{OBJ_FILENAME} imported no meshes")
        for part in parts:
            _bone_parent(bpy, part, armature, hand_bone,
                         OBJ_LOC, OBJ_ROT_RAD, OBJ_SCALE)
        bpy.context.view_layer.update()
        blade = next((p for p in parts if p.name.startswith("Lame")), parts[0])
        return blade, hand_bone

    loc = DEFAULT_LOC if loc is None else loc
    rot_deg = DEFAULT_ROT_DEG if rot_deg is None else rot_deg

    sword = make_sting(bpy)
    _bone_parent(bpy, sword, armature, hand_bone, loc,
                 tuple(math.radians(a) for a in rot_deg))
    bpy.context.view_layer.update()
    return sword, hand_bone
