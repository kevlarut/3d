# 3D → 2D Sprite Sheet Pipeline

Tools for turning AI-generated 3D characters into 8-directional, Diablo-style
sprite sheets for isometric games.

The full manual workflow (AI concept → Rodin 3D → Mixamo rigging → Blender
render) is documented in [`workflow-instructions.md`](workflow-instructions.md).
The canonical Blender render script is [`blender-script.py`](blender-script.py).

## `npm run generate` — one-command sprite sheets

`npm run generate` automates the Blender half of the workflow (Phases 3–4 of
`workflow-instructions.md`): it builds the scene from a folder of Mixamo FBX
exports and renders the finished sheets, with no manual Blender work.

```bash
cd hobbit-female
npm run generate                 # uses the folder you're in
npm run generate -- --scale 0.7  # scale a short character down (see below)
```

You can also name the folder explicitly from the repo root:

```bash
npm run generate -- hobbit-female --scale 0.7
```

### What it does

For the target folder it runs, in order:

1. Opens a new empty Blender file (no default cube/camera/light).
2. Imports the **idle** FBX (brings in the armature + mesh).
3. Imports each action FBX (**running, attacking, hit, dying**), keeps its
   animation, and deletes the imported skeleton — the "steal the action" trick.
4. Lays the actions end-to-end in an NLA track, in that order.
5. Reads each strip's start/end frames to build the `ANIMATION_ZONES` map.
6. Resets the tiny Mixamo import to a usable scale (see `--scale`) and stands
   the character on the ground.
7. Wires `rodin/shaded.png` (or `rodin-obj/shaded.png`) into the material's
   Base Color.
8. Writes `<folder>/<folder>-sprite-script.py` — a copy of `blender-script.py`
   with the output name and detected frames baked in — saves
   `<folder>/<folder>.blend`, then renders and stitches the sheets to
   `sprites/<folder>.png` and `sprites/<folder>-shadow.png`.

### Which FBX is which action?

FBX role detection is by keyword on the file names (Mixamo names vary a lot),
checked in order idle → running → attack → hit → die. To override a bad guess,
drop an `actions.json` in the folder mapping roles to file names:

```json
{
  "idle": "Neutral Idle.fbx",
  "running": "Running.fbx",
  "attack": "Standing 1H Magic Attack 01.fbx",
  "hit": "Taking Punch.fbx",
  "die": "Dying.fbx"
}
```

Any subset is allowed — a folder that only has idle/run/attack simply produces a
narrower sheet (missing roles are skipped, not fatal).

### Character scale

Mixamo geometry is authored at roughly human height (~1.8 m) at scale `1.0`, the
default. The camera framing is **fixed** (matching the other sprite scripts), so
scaling a character changes how big it renders relative to the others. Short
characters take a value below `1.0`:

```bash
npm run generate -- hobbit-female --scale 0.7
```

### Weapons

Optionally place a weapon in the character's right hand with `--weapon`:

```bash
npm run generate -- hobbit-female --scale 0.7 --weapon sword
```

`sword` builds a procedural "Sting"-style Elvish short sword (straight,
double-edged, tapered blade with Roman-spatha proportions; short crossguard;
leather grip; round pommel) and bone-parents it to `mixamorig:RightHand`, so it
follows every animation. Placement is tuned for the standard Mixamo rig and can
be nudged with `SPRITE_W_LOC` / `SPRITE_W_ROT` / `SPRITE_W_LEN`. See
`scripts/weapon.py`.

### Requirements

- **Blender 4.2+** — found via the `BLENDER` env var, then your `PATH`, then the
  macOS default (`/Applications/Blender.app/Contents/MacOS/Blender`).
- **Node.js** — to run `npm run generate`.

Headless / no-Blender-app fallback: set `SPRITE_PYTHON` to a Python that has the
[`bpy`](https://pypi.org/project/bpy/) module installed (`pip install bpy`) and
the generator will use it instead of a Blender binary.

### Options

| Setting | How | Default |
| --- | --- | --- |
| Character scale | `--scale N` / `SPRITE_SCALE` | `1.0` |
| Right-hand weapon | `--weapon sword` / `SPRITE_WEAPON` | none |
| Weapon placement | `SPRITE_W_LOC` / `SPRITE_W_ROT` / `SPRITE_W_LEN` | tuned defaults |
| FBX role mapping | `actions.json` in the folder | keyword auto-detect |
| Blender binary | `BLENDER` | PATH / macOS app |
| bpy fallback | `SPRITE_PYTHON` | — |
| Directions | `SPRITE_DIRECTIONS` | `8` |
| Resolution | `SPRITE_RES` | `128` |
| EEVEE samples | `SPRITE_SAMPLES` | Blender default |
| Camera zoom / aim | `SPRITE_ZOOM` / `SPRITE_TARGET` | `4.0` / `1.1` |
| Shadow opacity | `SPRITE_SHADOW_OPACITY` | `0.45` |
