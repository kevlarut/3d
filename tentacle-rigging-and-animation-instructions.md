### Phase 1: Mesh Cleanup (The "Normalization")

1. **Reset Transforms:** Select tentacle. Press **Ctrl + A** > **All Transforms**.
2. **Fix Normals:** Press **Tab** (Edit Mode). Press **A** (Select All). Press **Shift + N**.
3. **Merge Vertices:** Still in Edit Mode, press **M** > **By Distance**.
4. **Exit Edit Mode:** Press **Tab** (Object Mode).

### Phase 2: Rigging (Skeleton)

1. **Add Armature:** Press **Shift + A** > **Armature** > **Single Bone**.
2. **Extrude Chain:** * Press **Tab** (Edit Mode).
* Click the **tip** of the bone.
* Press **E** and drag upward. Repeat 5–8 times.
* Press **Tab** (Object Mode).



### Phase 3: Parenting (The "Glue")

1. **Order:** Click **Mesh** first. Hold **Shift** and click **Bones** second.
2. **The Command:** Press **Ctrl + P**.
3. **The Method:** Choose **With Automatic Weights**.

### Phase 4: Animation (The Slam)

1. **Setup:** Select bones. Change top-left dropdown to **Pose Mode**.
2. **Auto-Puppet:** Press **N** (Sidebar) > **Tool** tab > **Options** > **Auto IK**.
3. **Record:** Click the **Circle icon** (Auto Keying) on the timeline.
4. **Keyframing:**
* **Frame 1:** Move bone slightly to set start.
* **Frame 15 (Wind-up):** Move tip bone (**G**) back and high.
* **Frame 20 (Slam):** Move tip bone (**G**) down to the floor.
* **Manual Key:** Press **I** > **Location, Rotation & Scale**.



### Phase 5: The Cut (Boolean)

1. **Cutter:** **Shift + A** > **Mesh** > **Cube**. Place over the bottom.
2. **Modifier:** Select **Tentacle** > **Blue Wrench** > **Add Boolean**.
3. **Settings:** Eyedropper the **Cube**. Set Solver to **Manifold**.
4. **Stack:** Drag the Boolean to the **TOP** of the modifier stack.
5. **Hide:** In the Outliner, click the **Camera Icon** on the Cube.

---

### Windows vs. Mac Shortcut Comparison

| Action | Windows Shortcut | Mac Shortcut |
| --- | --- | --- |
| **Apply / Menu** | **Ctrl + [Key]** | **Command + [Key]** |
| **Clear Parent** | **Alt + P** | **Option + P** |
| **Search Menu** | **F3** | **F3** (or Spacebar) |
| **Hide Object** | **H** | **H** |
| **Unhide All** | **Alt + H** | **Option + H** |