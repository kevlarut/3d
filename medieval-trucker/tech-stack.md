# Medieval Trucker — Tech Stack

> Companion to [`game-design-document.md`](game-design-document.md).
> **Targets:** Steam (Windows, macOS, Linux) and iPhone/iPad (App Store), from one codebase.
> **Status:** proposal, v0.1

---

## 1. Summary of decisions

| Area | Decision | Why |
|------|----------|-----|
| Engine | **Unity 6 (LTS)**, Universal Render Pipeline (URP) | Strongest iOS support of the 3D engines, mature vehicle physics, one project exports to every target, and it imports the FBX files this repo already produces |
| Language | C# | Unity's native language; good tooling; one language for gameplay, tools and tests |
| Physics | Unity PhysX with a custom raycast-wheel wagon controller | Arcade feel needs hand-tuned wheel code, not the stock `WheelCollider` |
| Animation | Blender → FBX → Unity Animator (Mecanim), humanoid retargeting for people, generic rigs for horses and wagon | Reuses the Rodin → Mixamo → Blender pipeline in this repo |
| Input | Unity **Input System** package with action maps; touch UI overlay on mobile | One set of gameplay actions, per-platform bindings, automatic control scheme switching |
| Steam | Steamworks.NET (Facepunch.Steamworks as alternative) | Achievements, leaderboards, cloud saves, Steam Input |
| iOS | Metal via URP, Xcode project export, Game Center for leaderboards | Standard Unity iOS path |
| Builds / CI | GitHub Actions with GameCI for PC builds; macOS runner (or a Mac mini) for iOS; TestFlight for iOS testing | Automated builds from day one |
| Version control | Git + Git LFS for binary assets | This repo already uses Git; LFS keeps .fbx/.png/.blend from bloating history |
| Saves | JSON save files, versioned; Steam Cloud on PC, iCloud key-value/Documents on iOS | Simple and debuggable; cross-platform sync is a later feature |
| Analytics / crashes | Unity Cloud Diagnostics or Sentry | Know what crashes on which iPhone |

**Alternative:** Godot 4 is a good fit if you want to avoid Unity's licensing.
See §11 before choosing.

---

## 2. Engine choice: why Unity

The game needs, in order of importance:

1. **A single project that ships to Steam and iOS** with different quality
   settings and controls. Unity does this with build targets and quality
   tiers; no code forks.
2. **Full 3D characters with skeletal animation** from the existing
   FBX/Mixamo pipeline. Unity's Mecanim humanoid system retargets Mixamo
   animations across every human character in this repo automatically.
3. **Vehicle-style physics with an arcade feel.** PhysX plus a custom
   wheel controller is a well-trodden path (many arcade racers ship this
   way).
4. **Mobile performance.** URP is built for phones: forward rendering,
   scalable shadows, SRP Batcher, GPU instancing for grass/crowds.
5. **Store integrations.** Steamworks.NET and Unity's iOS/Game Center
   support are both mature.

Unreal is the other candidate. It has excellent vehicle physics (Chaos
Vehicles) and looks better out of the box, but iOS builds are large and
harder to keep performant, and C++/Blueprint iteration is slower for a small
team. For a stylized game at 60 fps on a phone, Unity is the safer bet.

---

## 3. Project structure

```
MedievalTrucker/               (Unity project; new repo or a subfolder of this one)
├── Assets/
│   ├── _Game/                  Everything we author
│   │   ├── Scripts/
│   │   │   ├── Core/           Bootstrap, scene loading, save system, platform services
│   │   │   ├── Vehicle/        Wagon controller, hitch, horses, cant/tip logic
│   │   │   ├── Cargo/          Cargo items, lashings, damage, special behaviors
│   │   │   ├── Contracts/      Notice board, contract generation, payout
│   │   │   ├── AI/             Bandits, traffic, livestock, geese
│   │   │   ├── Input/          Control schemes, touch controls, tilt
│   │   │   ├── UI/             HUD, menus, delivery tally
│   │   │   └── Platform/       ISteam / IGameCenter / IStore adapters
│   │   ├── Art/                Models, materials, textures (LFS)
│   │   ├── Animation/          Controllers, clips, avatars
│   │   ├── Audio/
│   │   ├── Prefabs/
│   │   ├── ScriptableObjects/  Cargo types, contracts, wagon stats, horse stats
│   │   └── Scenes/
│   ├── Settings/               URP assets, quality tiers, input actions
│   └── Plugins/                Steamworks.NET, etc.
├── Packages/
├── ProjectSettings/
└── ci/                         Build scripts
```

**Data-driven design:** cargo types, contracts, wagons, horses and bandit
types are all `ScriptableObject` assets. Designers tune the game without
touching code, and the zany special behaviors are small components attached
to a cargo prefab (`RollsAwayWhenLoose`, `AttractsBees`, `BongsOnBump`).

**Platform abstraction:** gameplay never calls Steam or Game Center
directly. It calls `IPlatformServices` (achievements, leaderboards, cloud
save, rich presence). There's a Steam implementation, an iOS implementation
and a null implementation for the editor.

---

## 4. Rendering and performance

**Pipeline:** URP, forward+ on PC, forward on iOS. Same shaders and
materials everywhere; quality tiers change the settings, not the assets.

| Setting | PC (Steam) | iPhone (recent) | iPhone (older, e.g. iPhone 11) |
|---------|-----------|-----------------|------------------------------|
| Target frame rate | 60–144 | 60 | 30 |
| Render scale | 1.0 | 0.8–1.0 | 0.7 |
| Shadows | Cascaded, 4 cascades | 1–2 cascades, short distance | Main light only, short |
| Post-processing | Bloom, color grading, motion blur, vignette | Bloom, color grading | Color grading only |
| Draw distance | Far | Medium | Near, with fog to hide it |
| Grass / crowds | Full | Reduced density | Minimal |

**Asset budgets (per frame, iOS target):**
- Under ~300k triangles on screen, under ~150 draw calls after batching.
- Wagon + team: ~15k tris. Character: ~5–8k tris with 2 LOD levels. Horse: ~10k tris with LODs.
- Textures: 2048 max for hero assets, 1024 for characters, 512 for props. ASTC compression on iOS, BC7 on PC.
- One texture atlas per character (the Rodin output already gives one diffuse per model).

**Tricks that keep it zany *and* cheap:**
- Distant traffic, livestock and bandits are simulated abstractly (position
  on a spline) and only get physics/animation within ~60 m.
- Crowds (dancing plague, processions) use GPU-instanced animated meshes
  (vertex animation textures), not skinned meshes.
- The cargo bed simulates at most ~12 rigid bodies. Forty geese are one
  cage until it breaks, then up to 8 real geese and a flock particle effect.

**Thermal:** iPhones throttle after a few minutes at full load. Run
sustained 60 fps in a 10-minute session, cap the frame rate at 60 (never
120) on mobile, and expose a "battery saver" 30 fps option.

---

## 5. Physics: the wagon

The stock `WheelCollider` is tuned for cars and fights against an arcade
tipping feel. Use a custom **raycast wheel** controller (each wheel is a
spring-damper raycast applying forces to the chassis rigidbody) — the
standard approach for arcade racers.

**Setup:**
- **Wagon chassis:** one `Rigidbody`, mass 400–1500 kg depending on wagon
  type. Center of mass is set each run from the loaded cargo (`Rigidbody.centerOfMass`).
- **Wheels:** 4 raycast wheels (2 on a farm cart). Rear wheels can lock
  (wheel brake). Side friction is reduced at high slip for the drift.
- **Horse team:** a kinematic "tractor" object moved along the steering
  input with gait-based speed and turn-rate curves. It connects to the
  wagon by a `HingeJoint` (or `ConfigurableJoint`) at the tongue. The
  wagon *follows*; that's what makes hairpins scary.
- **Anti-roll assist:** a torque that resists roll, scaled from strong at
  walking gait to weak at gallop. This is the main tuning knob for "safe at
  low speed, dangerous at high speed."
- **Cant meter:** read roll angle and roll velocity; the HUD shows both.
  Two-wheeling is a state (inside wheels off ground for > 0.2 s) with a
  save window where lean input applies a counter-torque.
- **Cargo:** rigid bodies in the bed with `FixedJoint`s as lashings and a
  `breakForce`. Damage = impulse magnitude above a fragility threshold,
  computed in `OnCollisionEnter`.
- **Fixed timestep:** 50 Hz (0.02 s) on PC, 50 Hz on iOS too if the CPU
  budget allows, else 30 Hz with interpolation. Never let physics tick rate
  differ between platforms in a way that changes handling; the handling
  must feel the same on both so leaderboards are fair.

**Horses' animation** is driven by gait state, not physics: the horse rigs
play walk/trot/canter/gallop cycles at a speed matched to the tractor
velocity, plus rear/stumble/bolt one-shots.

---

## 6. Animation pipeline

The repo's pipeline already produces exactly what Unity wants.

```
Midjourney concept → Rodin (mesh + texture) → Mixamo (rig + clips) → Blender (cleanup) → FBX → Unity
```

**Humans (villagers, bandits, guards, passengers):**
1. Import the Mixamo FBX with the Rig set to **Humanoid**. Unity builds an
   Avatar from the Mixamo skeleton automatically.
2. Import animation clips as separate FBX files (Mixamo "without skin"),
   also Humanoid. Every clip then plays on every human character.
3. One shared `AnimatorController` for all humans (idle, walk, run, react,
   die, climb-aboard, cheer, dance), with overrides for special NPCs.
4. `blender-script.py` and `scripts/pipeline.py` stay useful for 2D
   marketing/UI sprites and for the map screen.

**Horses, wolves, bears, geese:** Rig set to **Generic**. Mixamo doesn't rig
quadrupeds, so these need either purchased rigged animals (Unity Asset Store
has good horse packs with harness-ready rigs) or a Blender rig (Rigify has a
horse metarig). Horse clips needed: idle, walk, trot, canter, gallop, rear,
stumble, stop, eat hedge, glare.

**Wagon:** not skinned. Wheels, axles, tongue and canopy are separate
transforms driven by the physics controller. Flapping canvas and swinging
lanterns use simple spring scripts.

**Cargo:** props with a `Cargo` component. Animated cargo (bear, geese,
bride) is a skinned mesh parented to the cargo rigid body.

**Faces:** blend shapes on horses and hero NPCs for the cartoon expressions
(wide eyes on a near-tip). Rodin output doesn't include these; add them in
Blender for the few characters that need them.

---

## 7. Input: one action map, three control schemes

Use the **Unity Input System** package. Define gameplay *actions* once and
bind them per control scheme. The game reads actions, never devices.

**Actions:** `Steer` (axis), `UrgeOn`, `ReinIn`, `WheelBrake`, `Lean`
(axis), `Brace`, `Horn`, `LookBack`, `Pause`, plus menu navigation.

### 7.1 Control schemes

| Scheme | Steer | Gait | Brake | Lean | Brace | Where |
|--------|-------|------|-------|------|-------|-------|
| **Keyboard + mouse** | A/D | W/S | Space | Q/E | Shift | Steam |
| **Gamepad** | Left stick | RT/LT | A | Right stick | B (hold) | Steam, iOS (MFi/PS/Xbox controllers) |
| **Touch** | Tilt (default) or left-thumb virtual wheel | Right-side up/down buttons, or auto-gait | Brake button | Swipe or second thumb | Hold on cargo icon | iOS |

**Auto-switching:** the Input System raises a control-scheme-changed event
when the player touches a different device. The HUD swaps prompts (glyphs
vs. touch buttons) and the touch overlay hides itself when a controller is
connected to an iPhone. On Steam, use **Steam Input** glyphs so Steam Deck and
odd controllers show the right buttons.

### 7.2 Touch design (this decides whether the iOS version is any good)

Phones can't do 8 simultaneous inputs, so the mobile mode simplifies
without making the game easier:

- **Tilt steering** with a dead zone and a calibrate button; virtual wheel
  as an alternative.
- **Auto-gait:** the horses hold the highest gait that's safe for the
  current road, and the player holds a "push" button to override into
  danger. This replaces the four-gait tap system on mobile.
- **Lean = tilt further.** When the wagon starts to two-wheel, tilting
  *against* it leans. This makes the signature mechanic physical on a phone.
- **Brace** is a large hold button at the bottom right.
- **Horn/Look-back** share a corner button; tap vs. hold.
- Runs are 3–8 minutes and pauseable at any time, which suits mobile
  sessions.

Prototype the touch scheme by Milestone 1 (see the GDD), not after PC is
done. If tilt-to-lean isn't fun, the whole mobile version needs rethinking
early.

### 7.3 Platform feature flags

```csharp
public static class Platform {
    public static bool IsMobile => Application.isMobilePlatform;
    public static bool HasSteam  => SteamManager.Initialized;   // false on iOS
    public static bool TouchOverlayVisible => IsMobile && !Gamepad.current?.enabled ?? IsMobile;
}
```

Scripting defines (`UNITY_IOS`, `UNITY_STANDALONE`, `STEAMWORKS`) are used
only inside the `Platform/` adapters, never in gameplay code.

---

## 8. Steam

- **SDK:** [Steamworks.NET](https://steamworks.github.io/) (thin C# wrapper)
  or [Facepunch.Steamworks](https://github.com/Facepunch/Facepunch.Steamworks)
  (friendlier API). Either is fine; Facepunch is faster to work with.
- **Features:** achievements (the style bonuses map straight onto them),
  leaderboards for Time Trials and the Daily Contract, Steam Cloud saves,
  rich presence ("Hauling 40 geese to Hogsbottom"), Steam Input, Steam Deck
  verification (it's a big audience for this kind of game).
- **Builds:** Windows x64, macOS (Universal), Linux x64. Steam Deck runs the
  Linux build (or Windows via Proton). Test on Deck early; the "canter on two
  wheels on a handheld" pitch is natural there.
- **Upload:** SteamPipe (`steamcmd`) from CI on tagged releases.

---

## 9. iOS

- **Rendering:** Metal (only option). URP forward, ASTC textures, 60 fps
  cap, no 120 Hz.
- **Minimum target:** iOS 16, A13 (iPhone 11) and up. Set the "older"
  quality tier for A13/A14, "recent" for A15+.
- **Build:** Unity exports an Xcode project; CI archives it and uploads to
  TestFlight with `xcodebuild` + `altool`/`notarytool` or Fastlane. This
  needs a macOS machine (GitHub-hosted macOS runner or a Mac mini).
- **Game Center:** leaderboards and achievements through Unity's Apple
  plugins (`Apple.GameKit`) behind the same `IPlatformServices` interface.
- **iCloud:** save file in the app's iCloud Documents container so a new
  phone keeps progress. Cross-platform sync with Steam is not in scope for
  v1.
- **App Store rules to plan for:** Sign in with Apple isn't needed if there's
  no account. Premium price (one purchase, no IAP) is simplest and matches
  the Steam build; if IAP for cosmetics is added later, it must use StoreKit.
  Provide a privacy manifest; keep third-party SDKs to a minimum.
- **Binary size:** aim under 500 MB download; strip unused shader variants,
  use addressables for late-game regions.
- **Input:** MFi/PS/Xbox controllers work through the Input System with no
  extra code; the touch overlay hides when one connects.

---

## 10. Tooling, CI and workflow

- **Unity version:** pin one Unity 6 LTS version in `ProjectSettings/ProjectVersion.txt`; everyone uses it via Unity Hub.
- **Git:** `.gitattributes` with LFS for `*.fbx *.blend *.png *.psd *.wav *.ogg *.glb`; Unity's YAML serialization with `UnityYAMLMerge` for scene/prefab merges.
- **CI (GitHub Actions):**
  - Every PR: compile check + EditMode/PlayMode tests (GameCI `unity-test-runner`).
  - Main branch: Windows/Linux/macOS builds (GameCI `unity-builder`), artifacts attached.
  - Tag `v*`: upload to Steam (SteamPipe) and to TestFlight (macOS runner + Fastlane).
- **Tests:** physics handling regression tests run the wagon through a
  scripted track and assert time and roll angle ranges, so a tuning change
  on one platform can't silently change handling. Unit tests cover payout
  math and contract generation.
- **Addressables** for regions, so the first download stays small and
  regions can be patched independently.
- **Profiling:** Unity Profiler and Frame Debugger; Xcode Instruments and
  Metal frame capture on device. Profile on a real, older iPhone weekly.
- **Localization:** Unity Localization package from the start; string
  tables, not hardcoded text, because the game's humor lives in its text.

---

## 11. Alternative: Godot 4

If you'd rather avoid Unity (licensing, closed source), **Godot 4.3+** can
also hit both targets:

| | Unity | Godot 4 |
|---|---|---|
| iOS export | Mature; huge install base | Works (Metal renderer since 4.4); fewer shipped 3D titles |
| Language | C# | GDScript or C#; C# on iOS is newer and less proven |
| Vehicle/arcade physics | PhysX + custom wheels; many references | Jolt physics + custom wheels; fewer references |
| Animation retargeting | Humanoid avatar system, very smooth for Mixamo | Works with `SkeletonProfileHumanoid`, more manual |
| Steam | Steamworks.NET / Facepunch | GodotSteam (GDExtension), solid |
| Asset store | Large (horse rigs, VFX, etc.) | Smaller |
| Cost | Free under revenue threshold; per-install fees dropped in 2024; Pro at scale | Free, MIT |
| Editor iteration | Good | Excellent (fast startup, small) |

**Recommendation:** Unity, because the two hardest technical risks here
(smooth iOS 3D performance and a large volume of retargeted humanoid
animation) are the areas where Unity has the most proven ground. Godot
would be a fine choice for a PC-first game; the iOS target tips it.

---

## 11a. Licensing and cost (as of mid-2026; verify before committing)

| | Unity 6 | Godot 4 | Unreal 5 |
|---|---|---|---|
| License | Proprietary | MIT (open source) | Proprietary |
| Cost to start | Free (Personal) | Free | Free |
| Cost at scale | Pro seat subscription once company revenue/funding exceeds $200K in trailing 12 months (~$2,200/seat/yr at last pricing). No per-install Runtime Fee (cancelled before Unity 6) | None. No royalties, thresholds or seat fees | 5% royalty on gross revenue above $1M lifetime per product |
| Logo / splash required | No, on Unity 6+ (all tiers). Required on Personal for 2022 and earlier | No | No |
| Source access | Read-only reference source; can't ship a modified engine without a separate license | Full; you can modify and ship the engine | Full source; can modify and ship |
| Console ports later | Direct support | Through third parties (e.g. W4 Games) | Direct support |

**Bottom line:** all three are free to build and ship this game. Godot is
the only one that stays free at any revenue. Unity's splash requirement is
gone on Unity 6. Unreal's royalty only matters after $1M per product.

---

## 12. Risks

| Risk | Mitigation |
|------|-----------|
| Touch controls make the tipping mechanic frustrating on phones | Prototype tilt-to-lean in Milestone 1; ship auto-gait; allow controllers |
| Handling differs between PC and iOS (physics tick, frame rate) | Same fixed timestep; automated handling regression tests; frame-rate-independent controller |
| Phone thermals kill 60 fps mid-run | Quality tiers, 30 fps mode, budget for older devices, profile on device weekly |
| Mixamo has no quadruped rigs | Buy or build horse rigs early; the horse is on screen 100% of the time |
| Binary size on iOS with many regions | Addressables, texture compression, strip shader variants |
| Steam Deck controls/perf | Test on Deck from Milestone 2; use Steam Input glyphs |

---

## 13. First steps

1. Create the Unity 6 project with URP and the Input System, Test
   Framework, Addressables and Localization packages. Commit with LFS.
2. Build the graybox test track and the raycast-wheel wagon with the hitch
   and cant model (GDD Milestone 1).
3. Add the three control schemes and a touch overlay; get the same build
   running on a PC with a gamepad and on an iPhone via TestFlight within
   the first two weeks.
4. Import one human character from this repo (`townguard`) as Humanoid and
   confirm Mixamo clips retarget.
5. Set up GitHub Actions for test + PC builds; add the iOS lane once an
   Apple developer account and a Mac runner exist.
