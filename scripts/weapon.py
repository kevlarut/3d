"""Procedural weapons that can be seated in a Mixamo character's hand.

Currently one weapon: a "Sting"-style Elvish short sword with Roman-spatha
proportions (straight, double-edged, tapered blade; short crossguard; leather
grip; round pommel). It is bone-parented to the right-hand bone so it follows
every animation.

Placement is tuned for the standard Mixamo rig (mixamorig:RightHand) and can be
overridden per-run via env vars while dialing it in:
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


def attach_to_hand(bpy, armature, hand_bone="mixamorig:RightHand",
                   loc=None, rot_deg=None):
    """Build the sword and bone-parent it to the right-hand bone."""
    from mathutils import Matrix, Euler

    loc = DEFAULT_LOC if loc is None else loc
    rot_deg = DEFAULT_ROT_DEG if rot_deg is None else rot_deg

    if hand_bone not in armature.data.bones:
        # fall back to any bone whose name ends in RightHand
        cands = [b.name for b in armature.data.bones
                 if b.name.endswith("RightHand")]
        if not cands:
            raise RuntimeError("no right-hand bone found for weapon attach")
        hand_bone = cands[0]

    sword = make_sting(bpy)
    sword.parent = armature
    sword.parent_type = "BONE"
    sword.parent_bone = hand_bone
    sword.matrix_parent_inverse = Matrix.Identity(4)
    sword.location = loc
    sword.rotation_euler = Euler(
        tuple(math.radians(a) for a in rot_deg), "XYZ")
    bpy.context.view_layer.update()
    return sword, hand_bone
