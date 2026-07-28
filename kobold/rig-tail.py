"""
Give the kobold a real tail: bones, weights, and animation.

Mixamo's auto-rigger stops at the pelvis, so the kobold's ~0.9 m tail came out
of `npm run generate` with every one of its vertices weighted to
`mixamorig:LeftUpLeg` — the left thigh. The tail therefore kicked with the left
leg, which is why the run cycle in particular read as broken.

This script, run against `kobold/kobold.blend`, does three things:

  1. Traces the tail's centreline through the rest-pose mesh and adds a chain of
     `mixamorig:Tail1..N` bones along it, parented to `mixamorig:Hips`.
  2. Re-skins the tail vertices onto that chain, smoothly handing back to the
     hips at the base and taking the stolen weight off the thigh.
  3. Bakes tail motion into all five Mixamo actions by simulating the chain as a
     damped spring pendulum driven by the animated pelvis, so the tail lags,
     swings and overshoots in step with whatever the body is already doing.

Usage:
    blender --background kobold/kobold.blend --python kobold/rig-tail.py
    blender --background kobold/kobold.blend --python kobold/rig-tail.py -- --probe

`--probe` prints the traced centreline without touching the file. Without it
the .blend is saved in place.

This expects a .blend straight out of `npm run generate` — it blends the tail's
new weights against whatever skinning it finds, so running it twice over would
compound the transition band. It refuses to run on a file that already has the
chain; regenerate the .blend first. Note that `npm run generate -- kobold`
rebuilds kobold.blend from the Mixamo FBX and knows nothing about the tail, so
this has to be re-run afterwards.
"""

import bpy
import math
import sys

from mathutils import Vector, Quaternion, Matrix

# ==========================================================================
# CONFIG
# ==========================================================================

ARMATURE = "Armature"
MESH = "model"
HIPS = "mixamorig:Hips"

BONE_COUNT = 6
BONE_PREFIX = "mixamorig:Tail"

# Vertices the Mixamo rig parked on a thigh; the tail's weight is taken back
# from these and handed to the hips wherever the tail chain doesn't claim it.
LEG_GROUPS = (
    "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg",
    "mixamorig:LeftLeg", "mixamorig:RightLeg",
)

# --- centreline tracing (world space: +X = character's left, +Y = behind,
# +Z = up; the kobold faces -Y) -------------------------------------------
SEED_BAND = (0.30, 0.35)   # a Y slice that is unambiguously tail, not body
TRACE_STEP = 0.035         # march length per station
TRACE_RADIUS = 0.16        # how far off-axis to look for tail cross-section
TRACE_MIN_VERTS = 6        # below this the trace has run off the end
# Behind y=0.18 the tail is a clean tube; in front of it the geometry merges
# into the pelvis and a cross-section centroid just climbs the character's
# back. So stop the backward march there and extrapolate the tail's own axis
# into the body to find a plausible sacral pivot.
BASE_STOP_Y = 0.18
ROOT_EXTEND = 0.14

# --- skinning -------------------------------------------------------------
# Tail authority ramps in over this much arc length, so the base blends into
# the pelvis instead of creasing.
CLAIM_START = 0.08
CLAIM_FULL = 0.32
# Alongside a fat tail the distance-to-centreline curve is nearly flat, so a
# plain nearest-point search hands neighbouring vertices arc lengths several
# centimetres apart and the skin tears there. Average arc length over every
# segment within SOFTMIN_SIGMA of the nearest one instead.
SOFTMIN_SIGMA = 0.04
# Radial falloff, as multiples of the traced cross-section radius: full tail
# authority inside CLAIM_R_IN, fading to none at CLAIM_R_OUT.
CLAIM_R_IN = 1.5
CLAIM_R_OUT = 2.4
CLAIM_R_PAD = 0.05
CLAIM_R_MAX = 0.22
# Where along the tail the thigh loses its say entirely. Mixamo's weights here
# swing by 0.2 between neighbouring vertices; that was invisible while the
# whole region rode the same thigh, but once the tail moves on its own those
# leftovers rip the skin open. So the transition is driven purely by arc length
# — a smooth field — and the thigh is gone by the time the tail leaves the body.
REDIRECT_START = 0.10
REDIRECT_FULL = 0.34

# Laplacian smoothing of the finished weights over the re-skinned region.
SMOOTH_ITERS = 20
SMOOTH_FACTOR = 0.5

# --- simulation -----------------------------------------------------------
SUBSTEPS = 4
CONSTRAINT_ITERS = 6
MAX_BEND = math.radians(42)   # per joint, stops the tail folding through itself
FLOOR_Z = 0.03                # tail thickness above the ground plane
LOOP_PREROLL = 6              # cycles run before recording a looping clip
ONESHOT_SETTLE = 24           # frames held on the first pose before a one-shot

DEG = math.radians


def _sway(amp_deg, cycles, phase=0.0):
    """Per-joint sine drive, `cycles` full swings across the clip."""
    a = DEG(amp_deg)
    return lambda t: a * math.sin(2 * math.pi * (cycles * t + phase))


def _const(deg):
    a = DEG(deg)
    return lambda t: a


def ZERO(t):
    return 0.0

# Per-action bake settings, keyed by the NLA strip's role. `stiffness` is how
# hard the tail is held in its rest shape (1.0 = rigid with the pelvis, 0.0 =
# limp), `damping` how quickly a swing dies out, `yaw`/`pitch` are the
# character's own muscle input on top of the physics — per joint, so the tip
# gets BONE_COUNT times the listed angle.
CLIPS = {
    # Loose, unhurried S-curve; the tail is idling too.
    "idle": dict(
        loop=True, stiffness=0.30, damping=0.90, gravity=3.0,
        yaw=_sway(4.5, 1.0), pitch=_sway(1.6, 2.0, 0.25),
    ),
    # Streamed out behind and counter-swinging against the stride: one full
    # sway per gait cycle, with a twice-per-cycle lift on the footfalls.
    "running": dict(
        loop=True, stiffness=0.38, damping=0.86, gravity=4.0,
        yaw=lambda t: DEG(7.0) + DEG(6.0) * math.sin(2 * math.pi * t),
        pitch=lambda t: DEG(3.5) + DEG(2.2) * math.sin(2 * math.pi * (2 * t + 0.15)),
    ),
    # Braced during the wind-up, lashing after the swing lands.
    "attack": dict(
        loop=False, stiffness=0.42, damping=0.84, gravity=4.0,
        yaw=_sway(5.0, 1.0, -0.1), pitch=_const(2.0),
    ),
    # Limp: the impact travels down the tail and whips the tip.
    "hit": dict(
        loop=False, stiffness=0.20, damping=0.86, gravity=5.0,
        yaw=ZERO, pitch=ZERO,
    ),
    # Goes slack as the kobold drops, then lies on the ground.
    "die": dict(
        loop=False, stiffness=0.28, damping=0.82,
        gravity=9.8, slacken=True, yaw=ZERO, pitch=ZERO,
    ),
}


# ==========================================================================
# SMALL HELPERS
# ==========================================================================

def log(msg):
    print(f"[tail] {msg}", flush=True)


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smoothstep(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


# ==========================================================================
# 1. TRACE THE TAIL CENTRELINE THROUGH THE REST MESH
# ==========================================================================

def trace_centreline(mesh_obj):
    """March along the tail, returning [(point, cross-section radius), ...].

    Starts from a Y slice that can only be tail, then walks to the tip and back
    to the pelvis, re-centring on the local cross-section at every step. This
    follows the tail's sideways sweep and its upward hook, which a naive
    slice-by-Y would smear out.
    """
    mw = mesh_obj.matrix_world
    pts = [mw @ v.co for v in mesh_obj.data.vertices if (mw @ v.co).y > 0.0]
    log(f"tracing over {len(pts)} candidate vertices behind the hips")

    def section(p, d):
        """Vertices in a thin disc at p facing d -> (centroid, radius, count)."""
        hits = []
        for q in pts:
            r = q - p
            along = r.dot(d)
            if abs(along) > TRACE_STEP * 0.6:
                continue
            perp = (r - d * along).length
            if perp > TRACE_RADIUS:
                continue
            hits.append((q, perp))
        if not hits:
            return None, 0.0, 0
        c = Vector((0, 0, 0))
        for q, _ in hits:
            c += q
        c /= len(hits)
        rad = sorted(p for _, p in hits)[int(len(hits) * 0.9)]
        return c, rad, len(hits)

    seed_pts = [q for q in pts if SEED_BAND[0] <= q.y < SEED_BAND[1]]
    if not seed_pts:
        raise SystemExit("rig-tail: no vertices in the seed band; is this the kobold?")
    seed = Vector((0, 0, 0))
    for q in seed_pts:
        seed += q
    seed /= len(seed_pts)

    # Initial direction: toward the tip, i.e. further behind the character.
    ahead = [q for q in pts if SEED_BAND[1] <= q.y < SEED_BAND[1] + 0.05]
    tip_dir = Vector((0, 0, 0))
    for q in ahead:
        tip_dir += q
    tip_dir = (tip_dir / len(ahead) - seed).normalized()

    def march(start, d0, stop_y=None):
        out = []
        p, d = start.copy(), d0.copy()
        for _ in range(80):
            guess = p + d * TRACE_STEP
            c, rad, n = section(guess, d)
            if n < TRACE_MIN_VERTS:
                break
            step = c - p
            if step.length < 1e-5:
                break
            nd = step.normalized()
            # Where the tail dissolves into the pelvis the cross-section is
            # really the body, and its centroid can throw the march back the
            # way it came. Treat that as the end of the tail.
            if nd.dot(d) < 0.3:
                break
            if stop_y is not None and c.y < stop_y:
                break
            d = (d.lerp(nd, 0.6)).normalized()
            p = c
            out.append((p.copy(), rad))
        return out

    to_tip = march(seed, tip_dir)
    to_base = march(seed, -tip_dir, stop_y=BASE_STOP_Y)

    line = list(reversed(to_base)) + [(seed, section(seed, tip_dir)[1])] + to_tip

    # Carry the tail's own axis on into the pelvis to give the first bone a
    # pivot. Averaged over a few stations so one noisy centroid can't aim it.
    if len(line) >= 4:
        d = (line[0][0] - line[3][0]).normalized()
        line.insert(0, (line[0][0] + d * ROOT_EXTEND, line[0][1]))
    return line


def resample(line, count):
    """Split the traced polyline into `count` equal-arc-length bone stations."""
    pts = [p for p, _ in line]
    seglen = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seglen)
    cum = [0.0]
    for L in seglen:
        cum.append(cum[-1] + L)

    stations = []
    for i in range(count + 1):
        target = total * i / count
        j = 0
        while j < len(seglen) and cum[j + 1] < target:
            j += 1
        j = min(j, len(seglen) - 1)
        f = (target - cum[j]) / seglen[j] if seglen[j] > 1e-9 else 0.0
        stations.append(pts[j].lerp(pts[j + 1], f))
    return stations, total


def arc_lengths(line):
    pts = [p for p, _ in line]
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + (pts[i + 1] - pts[i]).length)
    return cum


def closest_on_line(line, cum, q):
    """(arc length, perpendicular distance, radius there) of q on the polyline.

    The arc length is a soft minimum: every segment whose closest point is
    within SOFTMIN_SIGMA of the nearest one gets a say, weighted by how close
    it is. Along a thick tail the distance curve is almost flat, and picking
    the single nearest segment makes arc length jump between neighbouring
    vertices — which shows up as a torn skin once the tail moves.
    """
    pts = [p for p, _ in line]
    hits = []
    nearest = 1e9
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ab = b - a
        L2 = ab.length_squared
        t = 0.0 if L2 < 1e-12 else clamp((q - a).dot(ab) / L2)
        dist = (q - (a + ab * t)).length
        hits.append((dist,
                     cum[i] + (cum[i + 1] - cum[i]) * t,
                     lerp(line[i][1], line[i + 1][1], t)))
        nearest = min(nearest, dist)

    tot = s = rad = 0.0
    for dist, si, ri in hits:
        w = math.exp(-((dist - nearest) / SOFTMIN_SIGMA) ** 2)
        tot += w
        s += w * si
        rad += w * ri
    return s / tot, nearest, rad / tot


# ==========================================================================
# 2. BUILD THE BONE CHAIN
# ==========================================================================

def build_bones(arm_obj, stations):
    names = [f"{BONE_PREFIX}{i + 1}" for i in range(len(stations) - 1)]
    to_local = arm_obj.matrix_world.inverted()

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_obj.data.edit_bones

    for n in names:                      # idempotent: rebuild from scratch
        if n in eb:
            eb.remove(eb[n])

    parent = eb[HIPS]
    for i, n in enumerate(names):
        b = eb.new(n)
        b.head = to_local @ stations[i]
        b.tail = to_local @ stations[i + 1]
        b.parent = parent
        b.use_connect = i > 0
        b.use_deform = True
        b.align_roll(to_local.to_3x3() @ Vector((0, 0, 1)))
        parent = b

    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"added {len(names)} tail bones under {HIPS}")
    return names


# ==========================================================================
# 3. RE-SKIN THE TAIL
# ==========================================================================

def skin(mesh_obj, names, line):
    cum = arc_lengths(line)
    total = cum[-1]

    # Arc length of each bone's midpoint, for tent-shaped blending between
    # neighbouring bones.
    edges = [total * i / len(names) for i in range(len(names) + 1)]
    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(names))]

    def tent(s):
        w = [0.0] * len(names)
        if s <= mids[0]:
            w[0] = 1.0
        elif s >= mids[-1]:
            w[-1] = 1.0
        else:
            for i in range(len(mids) - 1):
                if mids[i] <= s <= mids[i + 1]:
                    f = (s - mids[i]) / (mids[i + 1] - mids[i])
                    w[i], w[i + 1] = 1 - f, f
                    break
        return w

    vgs = mesh_obj.vertex_groups
    for n in names:
        if n not in vgs:
            vgs.new(name=n)
    if HIPS not in vgs:
        vgs.new(name=HIPS)
    gname = {g.index: g.name for g in vgs}

    mw = mesh_obj.matrix_world
    weights = {}          # vertex index -> {group name: weight}
    strength = {}         # vertex index -> how much smoothing it may take
    for v in mesh_obj.data.vertices:
        q = mw @ v.co
        if q.y <= 0.0:
            continue
        s, dist, rad = closest_on_line(line, cum, q)
        r_in = min(rad * CLAIM_R_IN, CLAIM_R_MAX)
        r_out = min(rad * CLAIM_R_OUT + CLAIM_R_PAD, CLAIM_R_MAX)
        if dist >= r_out:
            continue
        # Full authority along the tail's core, fading out sideways and at the
        # base so nothing in the pelvis snaps between the two.
        radial = 1.0 - smoothstep((dist - r_in) / max(r_out - r_in, 1e-6))
        m = radial * smoothstep((s - CLAIM_START) / (CLAIM_FULL - CLAIM_START))
        # How much of the thigh's weight to hand to the pelvis instead. Also
        # scaled by the radial falloff, so it too fades out rather than
        # stopping dead at the edge of the claimed region.
        redirect = radial * smoothstep(
            (s - REDIRECT_START) / (REDIRECT_FULL - REDIRECT_START))
        if m <= 0.001 and redirect <= 0.001:
            continue

        old = {gname[g.group]: g.weight for g in v.groups}

        new = {}
        for name, w in old.items():
            keep = w * (1 - m)
            if name in LEG_GROUPS and redirect > 0:
                new[HIPS] = new.get(HIPS, 0.0) + keep * redirect
                keep *= 1 - redirect
            if keep > 0:
                new[name] = new.get(name, 0.0) + keep
        for i, w in enumerate(tent(s)):
            if w > 0:
                new[names[i]] = new.get(names[i], 0.0) + m * w

        tot = sum(new.values())
        if tot > 1e-6:
            weights[v.index] = {n: w / tot for n, w in new.items()}
            # How hard this vertex may be smoothed. Tapering with the same
            # field that decides how much we changed it keeps the smoothing
            # from carving a fresh step at the edge of the patch.
            strength[v.index] = clamp(max(m, redirect) / 0.5)

    smooth_weights(mesh_obj, weights, strength, gname)

    for idx, w in weights.items():
        for name, val in w.items():
            if val >= 1e-4:
                vgs[name].add([idx], val, "REPLACE")
        for g in list(mesh_obj.data.vertices[idx].groups):
            name = gname[g.group]
            if w.get(name, 0.0) < 1e-4:
                vgs[name].remove([idx])

    log(f"re-skinned {len(weights)} tail vertices onto the chain")
    return len(weights)


def smooth_weights(mesh_obj, weights, strength, gname):
    """Laplacian-smooth the re-skinned weights across the mesh's own edges.

    Irons out steps between neighbouring vertices — Mixamo's weights around
    the pelvis swing by 0.2 from one vertex to the next, which tears once the
    tail starts moving independently of the legs. Each vertex is smoothed only
    as hard as `strength` allows, so the effect fades out where the patch does
    instead of pushing the discontinuity one ring further out.
    """
    core = set(weights)
    adj = {}
    for e in mesh_obj.data.edges:
        a, b = e.vertices
        if a in core or b in core:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)

    # Vertices just outside the patch take part as sources (strength 0), so
    # weight can flow across the seam without them being rewritten.
    field = {}
    for idx in adj:
        if idx in weights:
            field[idx] = dict(weights[idx])
        else:
            v = mesh_obj.data.vertices[idx]
            field[idx] = {gname[g.group]: g.weight for g in v.groups}

    for _ in range(SMOOTH_ITERS):
        nxt = {}
        for idx, w in field.items():
            f = SMOOTH_FACTOR * strength.get(idx, 0.0)
            ns = adj.get(idx, ())
            if f <= 0.0 or not ns:
                nxt[idx] = w
                continue
            avg = {}
            for n in ns:
                for name, val in field.get(n, {}).items():
                    avg[name] = avg.get(name, 0.0) + val
            blended = {}
            for name in set(w) | set(avg):
                blended[name] = ((1 - f) * w.get(name, 0.0)
                                 + f * avg.get(name, 0.0) / len(ns))
            tot = sum(blended.values())
            nxt[idx] = {n: v / tot for n, v in blended.items()} if tot > 1e-6 else w
        field = nxt

    weights.clear()
    weights.update({i: w for i, w in field.items() if strength.get(i, 0.0) > 0.0})


# ==========================================================================
# 4. SIMULATE + BAKE THE TAIL INTO EVERY ACTION
# ==========================================================================

def rest_offsets(arm_obj, names):
    """Each joint's rest position expressed in the hips bone's own space."""
    bones = arm_obj.data.bones
    hips_inv = bones[HIPS].matrix_local.inverted()
    joints = [bones[n].head_local for n in names] + [bones[names[-1]].tail_local]
    return [hips_inv @ p for p in joints]


def targets_at(arm_obj, offsets, yaw, pitch):
    """Where the joints would be if the tail were rigid with the pelvis.

    `yaw` / `pitch` bend that rigid shape by the character's own muscle input,
    applied per joint so the bend accumulates smoothly toward the tip.
    """
    m = arm_obj.matrix_world @ arm_obj.pose.bones[HIPS].matrix
    pts = [m @ o for o in offsets]
    if abs(yaw) < 1e-6 and abs(pitch) < 1e-6:
        return pts
    rot = (Quaternion(Vector((0, 0, 1)), yaw)
           @ Quaternion(Vector((1, 0, 0)), pitch)).to_matrix()
    out = [pts[0]]
    acc = Matrix.Identity(3)
    for i in range(1, len(pts)):
        acc = acc @ rot
        out.append(out[-1] + acc @ (pts[i] - pts[i - 1]))
    return out


def simulate(arm_obj, names, cfg, frames, fps):
    """Run the chain over `frames`, returning {frame: [joint positions]}."""
    offsets = rest_offsets(arm_obj, names)
    n = len(names)
    stiff = [cfg["stiffness"] * lerp(1.0, 0.35, i / max(n - 1, 1)) for i in range(n)]
    damp = cfg["damping"]
    grav = Vector((0, 0, -cfg["gravity"]))
    slacken = cfg.get("slacken", False)
    scene = bpy.context.scene

    dt = 1.0 / (fps * SUBSTEPS)
    damp_sub = damp ** (1.0 / SUBSTEPS)

    # Frame -> muscle-bent targets, evaluated once so the sim can sub-step
    # between them and be re-run for pre-roll without re-evaluating the rig.
    span = max(len(frames) - 1, 1)
    target_cache = []
    for k, f in enumerate(frames):
        scene.frame_set(int(f))
        bpy.context.view_layer.update()
        t = k / span
        target_cache.append(targets_at(arm_obj, offsets, cfg["yaw"](t), cfg["pitch"](t)))
    lengths = [(target_cache[0][i + 1] - target_cache[0][i]).length for i in range(n)]

    pos = [p.copy() for p in target_cache[0]]
    prev = [p.copy() for p in pos]

    def step(T_from, T_to, slack=1.0):
        for sub in range(SUBSTEPS):
            a = (sub + 1) / SUBSTEPS
            T = [T_from[i].lerp(T_to[i], a) for i in range(n + 1)]
            pos[0] = T[0]
            prev[0] = T[0]
            for i in range(1, n + 1):
                v = (pos[i] - prev[i]) * damp_sub
                nxt = pos[i] + v + grav * (dt * dt)
                k = clamp(stiff[i - 1] * slack)
                nxt = nxt.lerp(T[i], k)
                if nxt.z < FLOOR_Z:
                    nxt.z = FLOOR_Z
                prev[i] = pos[i]
                pos[i] = nxt
            for _ in range(CONSTRAINT_ITERS):
                for i in range(1, n + 1):
                    d = pos[i] - pos[i - 1]
                    L = d.length
                    if L < 1e-7:
                        d = Vector((0, 1, 0))
                        L = 1.0
                    pos[i] = pos[i - 1] + d * (lengths[i - 1] / L)
                    if i >= 2:                       # limit the bend
                        a_dir = (pos[i - 1] - pos[i - 2]).normalized()
                        b_dir = (pos[i] - pos[i - 1]).normalized()
                        ang = a_dir.angle(b_dir, 0.0)
                        if ang > MAX_BEND:
                            axis = a_dir.cross(b_dir)
                            if axis.length > 1e-7:
                                fix = Quaternion(axis.normalized(), MAX_BEND - ang)
                                pos[i] = pos[i - 1] + fix @ (pos[i] - pos[i - 1])
                    if pos[i].z < FLOOR_Z:
                        pos[i].z = FLOOR_Z

    if cfg["loop"]:
        for _ in range(LOOP_PREROLL):
            for k in range(len(frames) - 1):
                step(target_cache[k], target_cache[k + 1])
    else:
        for _ in range(ONESHOT_SETTLE):
            step(target_cache[0], target_cache[0])

    baked = {frames[0]: [p.copy() for p in pos]}
    for k in range(len(frames) - 1):
        slack = 1.0
        if slacken:
            # The tail goes limp as the kobold dies, then just lies there.
            slack = lerp(1.0, 0.12, smoothstep((k / span - 0.05) / 0.45))
        step(target_cache[k], target_cache[k + 1], slack)
        baked[frames[k + 1]] = [p.copy() for p in pos]

    if cfg["loop"]:
        baked[frames[-1]] = [p.copy() for p in baked[frames[0]]]
    return baked


def bake(arm_obj, names, baked, frames):
    """Turn simulated joint positions into keyed bone rotations."""
    bones = arm_obj.data.bones
    pbs = [arm_obj.pose.bones[n] for n in names]
    for pb in pbs:
        pb.rotation_mode = "QUATERNION"

    w_inv = arm_obj.matrix_world.to_3x3().inverted()
    scene = bpy.context.scene

    # Bone rest transforms relative to their parent, so the chain can be posed
    # without asking the depsgraph to re-evaluate between bones.
    rel = []
    for i, n in enumerate(names):
        parent = bones[names[i - 1]] if i else bones[HIPS]
        rel.append(parent.matrix_local.inverted() @ bones[n].matrix_local)

    for f in frames:
        scene.frame_set(int(f))
        bpy.context.view_layer.update()
        pts = baked[f]
        P = arm_obj.pose.bones[HIPS].matrix
        for i, pb in enumerate(pbs):
            M0 = P @ rel[i]
            want = w_inv @ (pts[i + 1] - pts[i])
            local = M0.to_3x3().inverted() @ want
            if local.length < 1e-9:
                continue
            q = Vector((0, 1, 0)).rotation_difference(local.normalized())
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=int(f))
            P = M0 @ q.to_matrix().to_4x4()


def bake_all(arm_obj, names):
    ad = arm_obj.animation_data
    strips = [s for t in ad.nla_tracks for s in t.strips if s.action]
    fps = bpy.context.scene.render.fps

    prev_action, prev_slot = ad.action, getattr(ad, "action_slot", None)
    ad.use_nla = False
    try:
        for idx, strip in enumerate(strips):
            # pipeline.py names its strips after the role; this .blend was
            # built before that and still carries Mixamo's own names, so fall
            # back to the fixed idle/run/attack/hit/die order.
            role = strip.name if strip.name in CLIPS else (
                list(CLIPS)[idx] if idx < len(CLIPS) else None)
            cfg = CLIPS.get(role)
            if not cfg:
                log(f"no settings for strip {strip.name}; skipping")
                continue
            act = strip.action
            ad.action = act
            slot = getattr(strip, "action_slot", None)
            if slot is not None:
                ad.action_slot = slot
            f0, f1 = (int(round(v)) for v in act.frame_range)
            frames = list(range(f0, f1 + 1))
            log(f"baking {role:8s} <- {act.name} frames {f0}-{f1} "
                f"({'loop' if cfg['loop'] else 'one-shot'})")
            baked = simulate(arm_obj, names, cfg, frames, fps)
            bake(arm_obj, names, baked, frames)
    finally:
        ad.action = prev_action
        if prev_slot is not None:
            try:
                ad.action_slot = prev_slot
            except Exception:
                pass
        ad.use_nla = True
    for pb in (arm_obj.pose.bones[n] for n in names):
        pb.rotation_quaternion = (1, 0, 0, 0)


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    probe = "--probe" in argv

    arm = bpy.data.objects[ARMATURE]
    mesh = bpy.data.objects[MESH]

    line = trace_centreline(mesh)
    stations, total = resample(line, BONE_COUNT)
    log(f"traced {len(line)} stations, tail arc length {total:.3f} m")
    if probe:
        for p, rad in line:
            log(f"   trace ({p.x:6.3f},{p.y:6.3f},{p.z:6.3f}) r={rad:.3f}")
        for i, p in enumerate(stations):
            log(f"   station {i}: ({p.x:6.3f},{p.y:6.3f},{p.z:6.3f})")
        return

    # The skinning step blends against the weights already on the mesh, so a
    # second pass over its own output would compound the transition band.
    if any(b.name.startswith(BONE_PREFIX) for b in arm.data.bones):
        raise SystemExit(
            f"rig-tail: {bpy.data.filepath} already has a {BONE_PREFIX} chain. "
            "Rebuild the .blend with `npm run generate -- kobold` first, then "
            "run this against the fresh file.")

    names = build_bones(arm, stations)
    skin(mesh, names, line)
    bake_all(arm, names)

    bpy.ops.wm.save_mainfile()
    log(f"saved {bpy.data.filepath}")


if __name__ == "__main__":
    main()
