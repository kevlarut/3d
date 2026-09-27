# Medieval Trucker — Game Design Document

> **Working title:** Medieval Trucker
> **Genre:** 3D arcade driving / delivery game
> **Platforms (target):** PC first; controller-friendly for console/Steam Deck later
> **Players:** Single-player (co-op "shotgun rider" mode as a stretch goal)
> **Status:** Concept / pre-production — v0.1

---

## 1. High Concept

It's 1347. The roads are mud, the maps are mostly guesses, and somebody
needs forty live geese, a cathedral bell and a wheel of cheese the size of a
millstone in Hogsbottom **by vespers**. That somebody is paying *you*.

You are a medieval long-haul trucker: a horse-drawn wagon, a team of horses
with opinions, and a reputation that depends on getting absurd cargo to
absurd places on time and (mostly) intact. You'll corner on two wheels past
the abbey, jump a collapsing drawbridge, outrun a bandit gang that insists on
singing its demands, and explain to a very calm duke why his portrait now
has a hoofprint on it.

**Elevator pitch:** *Crazy Taxi* meets *Monty Python and the Holy Grail*.
It's an arcade delivery game where the truck is a wobbly horse-drawn cart,
the freeway is a goat track, and the cargo is always, somehow, a problem.

**Taglines (for the store page / trailer):**
- *"Ye Olde Freight. Ye Olde Deadline."*
- *"Two horses. Four wheels. Usually."*
- *"The cheese must reach Hogsbottom."*
- *"Highway robbery was invented for people like you."*

### Design Pillars

1. **Zany first.** Every system should be able to make something funny
   happen. Physics exaggerates, cargo misbehaves, NPCs overreact, and the
   world plays it completely straight while all of this happens around it.
   If a player has a story to tell a friend after a run, we did it right.
2. **The wagon is a lovable disaster.** Handling is heavy, lurching and
   tippy: momentum you *wrangle*, not a car you point. Every sharp turn is a
   gamble. The wagon rocks up onto two wheels, crates slide, the horses
   scream, and you either save it gloriously or fail gloriously. Both
   should be fun to watch.
3. **The cargo is a character.** Whatever you're hauling is never just
   weight. It squawks, leaks, rolls away, catches fire, gives you directions,
   or tries to escape. Each delivery gets its personality from the cargo.
4. **Risk vs. reward, always.** The fast road is the dangerous road. The
   shortcut through the jousting tournament saves two minutes and might cost
   you a wheel (and some dignity). Payment rewards speed *and* care, and you
   can rarely maximize both.
5. **Weird, but with rules.** The weirdness follows its own consistent
   logic, so players can *plan around* it: geese always chase, cheese always
   rolls downhill, monks always complain. Surprise comes from how these
   systems collide, not from randomness.

### What a run looks like (sample moments)

These are the kinds of stories the systems should create. They're for the
pitch deck and the trailer.

- You take the hairpin above Wettering on two wheels. The beehives shift and
  the wagon slams back down. You arrive on time with a perfect-condition
  bonus and are then chased through town by an extremely angry swarm.
- A bandit gang blocks the bridge. Their leader explains, at length, that
  under the new Brigands' Charter they're entitled to a 15% cut and a
  lunch break. You pay the cut, then run them over during the lunch break.
- Your giant cheese wheel breaks its lashings on a downhill stretch and
  overtakes you. You now have two goals: beat the cheese to the bottom of
  the hill, and don't let the cheese reach the river.
- You are hired to deliver a live bear to the Duke's menagerie. The bear is
  fine. The bear is calm. The bear gets out at the Tollbridge gate, and the
  toll is waived.
- Halfway through a relic delivery, the relic (a saint's finger bone)
  starts *pointing*. It is pointing at a shortcut. The shortcut goes through
  a monastery's dining hall.

---

## 2. Core Gameplay Loop

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │ Pick a job   │ ──► │ Load & plan  │ ──► │ Drive the    │ ──► │ Deliver &    │
 │ at the       │     │ route        │     │ route        │     │ get paid     │
 │ notice board │     │              │     │ (the game)   │     │              │
 └──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
        ▲                                                              │
        └──────────── Upgrade wagon / horses / hire guards ◄───────────┘
```

**Moment-to-moment (seconds):** steer, whip/rein in, lean into turns, brace
cargo, dodge obstacles, fend off attackers.

**Run-level (minutes):** choose route at forks, manage horse stamina vs. the
clock, decide whether to stop and re-tie cargo, decide whether to fight,
flee or pay off bandits.

**Meta (hours):** earn coin and reputation, upgrade/replace your wagon and
team, unlock new settlements and more lucrative (and dangerous) contracts.

---

## 3. The Wagon: Driving & Handling

This is the most important system in the game and should be prototyped first.

### 3.1 Controls (controller / keyboard)

| Action               | Controller          | Keyboard        | Notes |
|----------------------|---------------------|-----------------|-------|
| Steer                | Left stick          | A / D           | Steers the *horses*; the wagon follows through the hitch |
| Urge on / crack whip | Right trigger       | W               | Tap to raise gait; hold to push harder (drains stamina) |
| Rein in / brake      | Left trigger        | S               | Horses slow; hard pull can make them rear |
| Wheel brake (lever)  | A / Cross           | Space           | Locks rear wheels — skids, used for tight "handbrake" turns |
| Lean                 | Right stick L/R     | Q / E           | Driver throws weight to counter a tip |
| Brace cargo          | B / Circle (hold)   | Shift           | Reduces cargo damage while held; can't lean at the same time |
| Horn / shout         | Y / Triangle        | H               | Blows a crumhorn. Scatters livestock and pedestrians; upgradeable to a war horn, a church bell or a bard who screams |
| Look back / aim      | Right stick click   | Mouse           | Used with weapons and to check pursuers |

### 3.2 Gaits (the "gears")

Horses don't have a throttle, they have gaits. Each tap of *urge on* shifts up;
*rein in* shifts down.

| Gait    | Speed    | Stamina       | Turning | Notes |
|---------|----------|---------------|---------|-------|
| Halt    | 0        | Recovers fast | —       | Needed to load/unload and to re-tie cargo |
| Walk    | Slow     | Recovers      | Tight   | Safe over rough ground and bridges |
| Trot    | Medium   | Neutral       | Good    | The "cruising" gait |
| Canter  | Fast     | Drains        | Wide    | Tipping risk begins in sharp turns |
| Gallop  | Very fast| Drains fast   | Very wide | High tip risk; horses can bolt if pushed when exhausted |

Stamina is shown as a lather/sweat meter on the horses themselves (diegetic)
plus a small HUD bar. Push exhausted horses and they get *opinions*: they
stop to eat a hedge, take a scenic detour, or glare at you over their
shoulder until you rein in.

### 3.3 Physics feel — "canting" and tipping

The signature mechanic. The wagon is simulated as a rigid body with a high,
cargo-dependent center of mass, attached to the horse team by a hinged
hitch/tongue.

- **Weight transfer:** In a turn, load shifts to the outside wheels. A
  **cant meter** (a swinging plumb-bob icon, also visible as the wagon's body
  roll) shows how close you are to going over.
- **Two-wheeling:** Past a threshold the inside wheels lift. You can hold it
  for a few seconds — it's actually slightly faster through the corner —
  but the longer you hold it, the more cargo shifts and the harder the
  recovery.
- **Recovery:** Lean into the high side, ease off the gait, or hit a bump at
  the right moment to slam back down (with a satisfying crash and some cargo
  damage).
- **Tipping over:** The wagon rolls in slow motion, cargo spills across the
  road, and the horses stop (or bolt, if spooked). Nearby peasants
  help you heave it upright in a quick button-mash sequence, for a fee, while
  offering unhelpful advice. Spilled cargo must be collected or written
  off. Spectacular crashes are the game's other reward: they get a
  replay and a title card ("THE GREAT TURNIP CALAMITY OF MUCKFORD").
- **Load matters:** Heavy, low cargo (stone, iron ingots) is stable. Tall,
  light cargo (hay, stacked barrels, a bishop's pipe organ) is extremely tippy.
  Cargo loaded badly at the start of the run makes the wagon lean one way.
- **The hitch:** The wagon does not turn where the horses turn — it
  follows. Take a hairpin too tight and the wagon clips the inside rock or
  jackknifes. Good drivers swing wide.

**Tuning target:** it should feel *slightly* out of control at speed, like a
shopping trolley with a heavy load, but never random. A skilled player should
be able to thread a canter-speed S-bend on two wheels on purpose. Physics
should be *exaggerated*: bouncier suspension, bigger air and floppier
cargo than reality, like a cartoon playing out in a realistic-looking world.

### 3.4 Terrain

| Surface       | Speed | Grip  | Cargo shake | Notes |
|---------------|-------|-------|-------------|-------|
| Paved Roman road | High | Good | Low | Rare, straight, often bandit-watched |
| Packed dirt   | Normal| Good  | Medium      | Most roads |
| Mud           | Low   | Poor  | Medium      | Wheels can get stuck — rock back and forth to escape |
| Cobbles (town)| Normal| Medium| High        | Cities are rough on fragile goods |
| Ford / stream | Low   | Poor  | Medium      | Water damages some cargo (flour, books) |
| Bridge        | Normal| Good  | Low         | Some are old; gallop over them and planks give way |
| Snow / ice    | Low   | Very poor | Low     | Mountain region, late game |

Ruts, rocks, potholes and fallen branches act as bumps that jolt cargo and
can launch the wagon briefly airborne (for maximum drama on downhill runs).

### 3.5 Camera

- Default: chase camera behind and above the wagon, lagging slightly so
  sharp turns are *felt* as the wagon swings out of frame.
- Camera rolls a little with the wagon's cant to sell the tipping.
- Optional first-person "driver's bench" view: reins in hand, horse rumps
  ahead, very immersive, very hard.
- Look-back camera for chases.

---

## 4. Cargo & Deliveries

### 4.1 Cargo properties

Each cargo type has a set of properties that shape how the run plays:

| Property     | Effect |
|--------------|--------|
| **Weight**   | Slower acceleration, longer braking, more horse stamina drain |
| **Height / CoM** | Higher = tips more easily |
| **Fragility** | How much damage bumps, impacts and spills do |
| **Perishability** | Value decays over time regardless of damage |
| **Temptation** | How attractive the load is to bandits |
| **Special**  | Unique rules (see below) |

### 4.2 Example cargo

| Cargo | Weight | Fragility | Perishable | Temptation | Special |
|-------|--------|-----------|------------|------------|---------|
| Grain sacks | Heavy | Low | No | Low | Starter cargo; forgiving |
| Wine casks | Heavy | Medium | No | Medium | Leaks if damaged — a trail others can follow |
| Pottery & glassware | Light | Very high | No | Low | Every bump hurts |
| Fresh fish | Medium | Low | **Fast** | Low | Pure time trial; attracts cats and gulls |
| Live chickens / pigs | Medium | Low | No | Low | Escape through damaged crates; can be recaptured |
| Hay bales | Light | Low | No | Very low | Very tall, so extremely tippy; flammable |
| Iron ingots | Very heavy | None | No | Medium | Super stable, super slow |
| Tax silver | Medium | None | No | **Very high** | Every highwayman in the county wants it, and so does the tax collector who hired you |
| Holy relic | Light | High | No | High | A monk rides along and complains about your driving. The relic sometimes points at shortcuts |
| Alchemist's reagents | Light | High | No | Low | Big bumps cause small explosions; very big bumps cause purple ones |
| Passengers (coach) | Medium | "Comfort" | No | Medium | Passengers get sick, scream, or tip for a thrill ride |
| Beehives | Light | Medium | No | None | Damage releases bees that chase *you* |
| Giant cheese wheel | Very heavy | Low | Slowly | Medium | Round. If it breaks free, it rolls, and it's faster than you downhill |
| Forty live geese | Medium | Low | No | Low | Escaped geese don't flee; they *attack*, including the horses |
| A live bear | Very heavy | "Mood" | No | None | Keep it calm (smooth driving) or it starts rocking the wagon itself. Bandits won't touch you |
| Cathedral bell | Extreme | Low | No | Low | Every bump *BONGS*, which alerts bandits for miles. Needs a four-horse team |
| The Duke's portrait | Light | Very high | No | Medium | Must arrive with no damage at all. A tiny hoofprint costs you half the fee |
| Catapult (flat-pack) | Heavy | Medium | No | Medium | Very late game: can be *used* once, at the cost of the delivery bonus |
| A wedding party | Medium | "Comfort" | **Yes** (the ceremony starts at noon) | Low | The bride steers from the back seat. Also, the groom is missing |
| Dragon egg (probably) | Light | Very high | Hatching | Very high | Must be kept warm. Drive through villages with fires or it cools. Do not let it hatch in the wagon |

### 4.3 Cargo damage model

- Cargo is physically simulated as a handful of lashed crates/sacks/barrels
  in the wagon bed (cheap rigid bodies, not full sim).
- Each item has a **condition %**. Impacts above a threshold (scaled by
  fragility) reduce it. Bracing reduces incoming damage by ~50%.
- Lashings can **break** on big impacts; loose cargo slides and can fall off.
  Stop the wagon (Halt) to re-tie — costs time, saves goods.
- Items that fall off stay in the world. You can go back for them, or a
  bandit/peasant/pig may get there first.

### 4.4 Contract types

| Contract | Description |
|----------|-------------|
| **Standard haul** | A to B, generous time limit. Bread and butter. |
| **Express** | Tight deadline, big time bonus, low damage penalty. |
| **Fragile** | Loose deadline, big condition bonus, heavy damage penalty. |
| **Perishable** | Value decays continuously — just go fast. |
| **Escort / convoy** | Stay near an NPC wagon and protect it. |
| **Multi-drop** | Several deliveries on one route; order is up to you. |
| **Pickup en route** | Collect goods from a farm/mine mid-route. |
| **Smuggling** | Illegal cargo; avoid toll gates and town guards as well as bandits. |
| **Rescue / recovery** | Retrieve cargo spilled by another carter before the bandits do. |
| **Royal commission** | Story missions with unique set pieces. |
| **Moving day** | Haul an entire family and their furniture. Grandmother rides on top of the wardrobe and refuses to get down. |
| **Runaway recovery** | Something escaped (a cheese, a pig, a small knight). Herd it into the wagon before it reaches the river. |
| **Getaway driver** | The client is fleeing a witch trial and they are *definitely* not a witch. The mob is on foot, then on horseback, then has a catapult. |

---

## 5. Payment & Scoring

Payment is the core feedback loop — it tells the player *how* they did, not
just *whether*.

```
Payout = Base Fee
       × Condition Multiplier
       × Time Multiplier
       + Bonuses
       − Penalties
```

### 5.1 Time multiplier

Each contract has three times: **Early**, **On Time**, and **Late**.

| Arrival | Multiplier |
|---------|------------|
| Before "Early" | 1.5× (plus "Swift" bonus) |
| Before "On Time" | 1.0× |
| Late | Drops 10% per 30 s late, floor 0.25× |
| Very late (2× limit) | Contract failed; small fee for any undamaged goods |

### 5.2 Condition multiplier

Average condition of all cargo delivered, with lost items counting as 0%.

| Condition | Multiplier |
|-----------|------------|
| 100% (pristine) | 1.25× (plus "Not a Scratch" bonus) |
| 90–99% | 1.0× |
| 50–89% | Scales linearly 0.9× → 0.5× |
| Below 50% | 0.25× and a reputation hit |

The contract's type shifts the weights: *Express* contracts care more about
time; *Fragile* contracts care more about condition.

### 5.3 Bonuses (the "style" layer)

Small, flashy payouts shown as a tally when you arrive — the arcade
dopamine hit.

- **Two-Wheeler** — cornered on two wheels for 3+ seconds without tipping.
- **Close Shave** — passed within a hair of another cart, a tree, or a cow.
- **Big Air** — all four wheels off the ground for 1+ second.
- **Untouched** — no bandit laid a hand on the cargo.
- **Outran 'Em** — escaped a pursuit without fighting.
- **Pacifist Route** — completed a dangerous route without harming anyone.
- **Local Hero** — delivered through a town without hitting any pedestrians/livestock.
- **Tip** — passengers and some clients tip for a thrilling (or smooth) ride.
- **Flying Fowl** — a chicken spent at least 5 seconds airborne.
- **Divine Intervention** — survived a near-tip in the shadow of a church.
- **Sheep Slalom** — drove through a flock without touching a single sheep.
- **Gatecrasher** — entered a town through the gate *as it was closing*.
- **Heir Apparent** — accidentally knocked a jousting knight off his horse.

### 5.4 Penalties

- Damaged property (fences, market stalls, the mayor's prize geese).
- Toll gates run through (fines; bounty if repeated).
- Exhausted/injured horses (vet bill).
- Wagon repairs are paid separately after every run.

### 5.5 Reputation

Each settlement and faction tracks your reputation separately. Good work
unlocks better contracts; bad work means clients lowball you or refuse
service. A global **Carter's Guild rank** (Wagonhand → Journeyman Carter →
Master Carter → Royal Courier) gates regions and wagon types.

---

## 6. Threats: Highwaymen & Other Hazards

### 6.1 Highwaymen

Bandits are the "cops" of this game: a dynamic threat you can avoid, outrun,
outsmart, pay off, or fight.

**Heat / notoriety:** Bandit attention is driven by the cargo's
**Temptation**, time of day, the road's danger rating, and how much loot you
visibly carry. A "Wanted by Bandits" style indicator (a row of little
daggers, 0–5) shows the current threat level.

**Bandit types (initial set):**

| Type | Behavior | Counter |
|------|----------|---------|
| **Footpad** | Jumps out of bushes, tries to climb aboard at low speed | Keep speed above a trot; shake them off with a sharp turn |
| **Roadblock gang** | Fells a tree / drags a cart across the road ahead | Spot the scouts early and take another route, or pay the toll |
| **Mounted raiders** | Chase on horseback, try to cut lashings and grab cargo | Outrun, ram, or use weapons; they tire faster than a team |
| **Archers** | Fire from ridges; arrows damage cargo and horses | Speed and cover; a guard with a shield helps |
| **Rival carters** | Race you for the same contract, shunt you into ditches | Out-drive them; ram back |
| **Kobold swarm** | A dozen tiny thieves clamber aboard like ants and carry off crates one at a time | Shake them off with sharp turns and bumps |
| **The Singing Highwaymen** | Block the road and perform their demands as a full musical number | Pay them, applaud, or drive off mid-chorus (they take this personally) |
| **The Brigands' Guild** | Unionized bandits: cut-rate robberies, strict lunch breaks, lots of paperwork | Know the rules. They can't rob you during a lunch break |
| **Goose gang** | Feral geese that have organized | Nothing. Only running away works |
| **The Gentleman Bandit** (boss) | Recurring charismatic villain with set-piece ambushes; always leaves a thank-you note | Story encounters |

**Encounter resolution options:**

1. **Avoid** — take a different road, travel by day, keep a low profile.
2. **Outrun** — the wagon-chase set piece. Dangerous at high cant.
3. **Pay** — hand over a cut of the cargo or coin. Always an option; never
   a *good* option.
4. **Fight** — hired guards, a crossbow on the bench, caltrops dropped from
   the tailgate, or a well-aimed swing of the wagon itself.
5. **Trick** — upgrades like a false floor or a decoy strongbox.

Combat should stay light: this is a driving game with some fighting, not a
fighting game with some driving. The driver never leaves the bench during
normal play.

### 6.2 Hired guards

Before a run you can hire a guard to ride shotgun (a stretch goal is making
this slot a second local/online player).

| Guard | Cost | Ability |
|-------|------|---------|
| Town militiaman | Cheap | Bats away climbers |
| Crossbowman | Medium | Shoots pursuing riders (auto or player-aimed) |
| Shieldbearer | Medium | Blocks arrows from one side |
| Retired knight | Expensive | Scares off low-level bandits entirely; heavy |
| Hedge wizard | Expensive | Random spells: fog, a speed boost, or accidentally turning the cargo into geese |

### 6.3 Environmental hazards

- **Livestock** on the road — sheep, cows, geese. Hitting them costs money and time.
- **Other traffic** — slow ox-carts, pilgrims, processions, knights who
  will not give way.
- **Weather** — rain turns dirt to mud; fog hides roadblocks; wind makes tall loads tippier.
- **Night** — faster roads (no traffic), far more bandits; lantern upgrades matter.
- **Wildlife** — wolves chase the horses at night in the forest; a bear
  sometimes simply sits in the road.
- **Toll gates & guards** — slow down and pay, or smash through and gain a bounty.
- **Road events (random, weird):**
  - A jousting tournament whose tilt runs straight *across* the road.
  - A religious procession moving at the speed of a funeral, all the way
    to the next town.
  - A trebuchet crew testing its range. Some landing zones are your road.
  - A dancing plague: the villagers will not stop dancing and will not get
    out of the way.
  - A knight errant who challenges your wagon to single combat.
  - A town crier who runs alongside you shouting the news, including news
    about you.

---

## 7. The World

### 7.1 Setting

A fictional, cheerfully ridiculous late-medieval kingdom: muddy, damp,
full of people with very specific jobs and very strong opinions. It's
lightly fantastical (wizards, kobolds, a dragon egg that may or may not be
one), but the joke is that everyone treats medieval freight logistics
with complete seriousness. There are guild regulations for cart widths,
a Ministry of Roads that has never built a road, and a thriving trade in
extremely specific goods ("left-handed turnips").

### 7.2 Structure

The world is a set of **regions**, each a hand-built 3D map (roughly 3–5 km
of drivable road network) connecting 4–6 settlements. Regions unlock as your
guild rank rises.

| Region | Theme | New mechanics |
|--------|-------|---------------|
| **The Vale** (tutorial) | Farmland, gentle hills, friendly villages | Gaits, cant, basic cargo |
| **Blackthorn Forest** | Dense woods, narrow roads, lots of bandits | Ambushes, night runs, wolves |
| **The Fens** | Marsh, fords, rickety causeways | Mud, water damage, fog |
| **Greystone Hills** | Mining country, quarries, switchbacks | Heavy loads, steep descents, brake overheating |
| **The High Pass** | Mountains, snow, sheer drops | Ice, avalanches, the scariest hairpins in the game |
| **The Capital** | A sprawling walled city | Crowds, cobbles, guards, tight alleys |

### 7.3 Settlements

Settlements are hubs: a notice board for contracts, a wheelwright (repairs
and upgrades), a stable (horses), an inn (hire guards, rumors about which
roads are dangerous today), and a market (sell salvage).

Example settlements in The Vale: **Muckford** (home base), **Little
Wettering**, **Abbot's Crossing** (abbey — relic contracts), **Hogsbottom**
(pig farm), and **Tollbridge** (a town that exists purely to charge you).

### 7.4 Roads & routes

- Road networks branch and rejoin so every contract has 2–4 viable routes.
- Before a run, a **route planner** on a parchment map shows distance,
  surface, danger rating and tolls for each option.
- Shortcuts (fields, riverbeds, a farmer's barn with both doors open) are
  discoverable and marked on your map once found.

---

## 8. Progression & Economy

### 8.1 Wagons

| Vehicle | Capacity | Speed | Stability | Notes |
|---------|----------|-------|-----------|-------|
| **Handcart** (pushed by a donkey) | Tiny | Slow | Stable | Tutorial / "you went bankrupt" fallback |
| **Farm cart** (2 wheels) | Small | Medium | Low | Two wheels = tips *forwards/backwards* too; funny and hard |
| **Wagon** (4 wheels) | Medium | Medium | Medium | The workhorse; default vehicle |
| **Freight wain** | Large | Slow | High | For iron and stone; needs 4 horses |
| **Stagecoach** | Passengers | Fast | Low | Suspension helps comfort; very tippy |
| **Armored strongwagon** | Small | Slow | High | Tax silver runs; bandit magnet |
| **Royal courier chariot** | Tiny | Very fast | Very low | Endgame express runs |

### 8.2 Upgrades (at the wheelwright)

- **Wheels:** iron-rimmed (durable), wide (mud), spiked (ice).
- **Suspension:** leather straps → leaf springs; reduces cargo shake.
- **Axles & brakes:** better wheel brake, less overheating on descents.
- **Bed:** cargo nets (fewer spills), padded crates (fragility), low bed
  (lower center of mass), false floor (smuggling).
- **Lantern:** better night visibility, reveals ambushes sooner.
- **Defenses:** side boards (arrows), caltrop box, crossbow mount.
- **Cosmetics:** paint, banners, bells, a little pennant with your carter's mark.
- **Ridiculous upgrades (late game):** a sail for windy downhill stretches, a
  tame goose as a guard animal, a trebuchet that launches you over the river
  (once), and a fake second wagon made of painted canvas to confuse bandits.

### 8.3 Horses

Horses are individuals with names and stats:

- **Speed**, **Stamina**, **Strength** (hauling capacity), **Nerve**
  (resistance to bolting when attacked or near fire/wolves).
- Horses gain experience on routes they know well ("Old Bess knows this
  road").
- Teams of 1, 2 or 4 horses; mismatched teams pull unevenly and drift.
- Injured or exhausted horses need rest days — encourages owning a stable.

### 8.4 Economy

- Coin comes from contracts, tips and salvage.
- Coin goes to repairs, horse care, guards, tolls, upgrades and new wagons.
- Early game is tight: a tipped wagon full of pottery can wipe out a
  day's earnings. That tension is intentional but should never soft-lock
  the player (the donkey handcart is always available).

---

## 9. Game Modes

1. **Career** — the main mode described above, with a light story about
   rising from a debt-ridden wagonhand to Royal Courier and dealing with the
   Gentleman Bandit.
2. **Free Haul** — sandbox: any unlocked region, random contracts, no story.
3. **Time Trials** — fixed routes and cargo, leaderboards for fastest and
   for highest payout.
4. **Daily Contract** — one seeded contract per day, same for everyone,
   one attempt counts for the leaderboard.
5. **Stretch goal: Co-op Shotgun** — player 2 rides as guard, handling
   weapons and bracing cargo while player 1 drives.
6. **Stretch goal: Rival Carters (versus)** — split-screen race for the
   same contract.

---

## 10. HUD & UI

Keep the HUD minimal and period-flavored (inked parchment, wax seals).

- **Top center:** delivery timer, drawn as a burning candle with notches
  for Early / On Time.
- **Bottom left:** gait indicator (horseshoe icons) and horse stamina.
- **Bottom center:** **cant meter** — a plumb bob swinging in an arc; red
  zones on either side.
- **Bottom right:** cargo condition — small icons for each item, cracking
  and reddening as they take damage.
- **Top right:** bandit threat (daggers 0–5) and a compass pointing to the
  destination.
- **World-space cues:** road signs at forks, smoke from destination chimneys,
  bandit scouts glinting on ridges.
- **Delivery screen:** a clerk tallies your payment with an abacus, line by
  line, with bonuses stamped on in wax.

---

## 11. Audio

- **Wagon:** creaking wood, rattling chains, wheel rumble that changes with
  surface, a loud *thunk* when two wheels slam back down.
- **Horses:** hoof rhythm changes with gait (the main speed cue), snorts,
  panicked whinnies near tipping.
- **Cargo:** chickens, clinking glass, sloshing wine — every cargo type
  sounds different, so damage is audible.
- **Music:** high-energy medieval folk (lute, hurdy-gurdy, crumhorn,
  drums), played like a chase-scene soundtrack. It intensifies with speed and
  bandit threat, and a tavern band plays the delivery tally. A near-tip
  cuts the music to a single held note until you land it.
- **Barks:** the driver mutters and swears in medieval curses ("God's
  teeth!"); passengers and monks comment; bandits shout threats and
  complaints about their working conditions. A narrator (a pompous
  royal chronicler) occasionally describes your worst crashes as if they
  were great battles.

---

## 12. Art Direction

- **Style:** stylized-realistic 3D with cartoon timing. The world looks
  grounded and painterly; the *motion* is exaggerated, with squash-and-stretch
  on crashes, cargo that flops and flies, and horses with expressive faces.
  Chunky, readable silhouettes (the wagon and its lean must read clearly at
  a glance) and strong weather and lighting.
- **Illuminated-manuscript flourishes:** UI, title cards, crash replays and
  the map borrow from medieval marginalia, including the famous doodles of
  knights fighting snails and rabbits with swords. Those drawings are the
  game's tonal north star: very medieval and very weird.
- **Palette:** warm earth tones in villages; cold greens and greys in the
  forest; muted blues in the fens; stark white/grey in the mountains.
- **Readability rules:** roads must always be distinguishable from
  off-road; hazards and bandits get a subtle color accent; cargo in the
  wagon bed is always visible from the chase camera.

### 12.1 Reusing assets from this repository

This repo's AI concept → Rodin → Mixamo → Blender pipeline already produces
rigged, animated 3D characters. Several existing models map directly onto
Medieval Trucker roles and can be used as placeholders (or finals) in 3D
rather than rendered to sprite sheets:

| Existing asset | Role in Medieval Trucker |
|----------------|--------------------------|
| `barbarian`, `fighter` | Highwaymen / mounted raiders |
| `cael-underwood` (archer) | Bandit archers on ridges |
| `townguard` | Toll-gate guards, hired militiaman |
| `hero-paladin` | Retired knight guard |
| `wizard` | Hedge wizard guard |
| `peasant-woman`, `worker`, `hobbit-female` | Villagers, pedestrians, clients, passengers |
| `bard` | Tavern musician on the delivery tally screen |
| `cult-searcher` | Smuggling-contract contact / suspicious passenger |
| `wolf`, `bear` | Wildlife hazards |
| `kobold` | Small, cheeky bandits that climb aboard |
| `skeleton`, `ghost` | Night-time / haunted-road event encounters |

New assets needed: horses (with harness and gait animations — idle, walk,
trot, canter, gallop, rear), wagons (modular: bed, wheels, axles,
canopy), cargo props, settlements, and road/terrain kits.

---

## 13. Technical Notes

- **Engine:** Unity 6 with URP, targeting Steam (Windows/macOS/Linux) and
  iOS from one project. Full rationale, platform details and the input
  design for keyboard, gamepad and touch are in [`tech-stack.md`](tech-stack.md).
- **Wagon physics:** rigid-body chassis with raycast wheels (like a
  standard arcade car), plus:
  - Horse team as a kinematic "tractor" steered by the player, attached
    to the wagon by a hinge joint on the tongue.
  - A configurable center-of-mass computed from the loaded cargo.
  - Arcade assists: anti-roll torque that scales down with speed/gait, so
    walking is safe and galloping is dangerous; a small "save window" that
    lets skilled leaning recover from near-tips.
- **Cargo:** a small number of rigid bodies with joints (lashings) that
  break above a force threshold. Damage is computed from impulse magnitude.
- **Performance:** aim for 60 fps on mid-range PCs; horses and bandits
  use LODs, and distant traffic is simulated abstractly.

---

## 14. Prototype Plan

The goal of the first prototype is to answer one question: **is driving the
wagon fun on its own?**

**Milestone 1 — "The Wagon" (graybox)**
- One horse-team + wagon with gaits, hitch steering, cant and tipping.
- A single graybox test track: straights, S-bends, a hairpin, bumps, a
  downhill run.
- Placeholder cargo boxes with condition %.
- Timer and payout screen.

**Milestone 2 — "The Run"**
- One small real map with two settlements and three routes.
- 4 cargo types, 3 contract types.
- Terrain types: dirt, mud, bridge.
- Footpads and mounted raiders with basic AI.

**Milestone 3 — "The Vale" (vertical slice)**
- Full tutorial region with 5 settlements, notice board, wheelwright.
- Upgrades and a second wagon type.
- Art pass using the repo's existing characters; horse models and animations.
- Audio pass on wagon and horses.

---

## 15. Open Questions

- How punishing should tipping be? (Full stop and QTE vs. a quick auto-right
  with a cargo penalty.) Needs playtesting.
- Should the time of day be player-chosen per run or continuous across a
  career "day"?
- How much combat is too much? Keep a dial here and playtest both extremes.
- Is the 2-wheeled farm cart fun or just frustrating?
- Where is the ceiling on weirdness? The current rule is "anything goes, as
  long as it follows consistent rules and the world plays it straight."
  Dragons that actually hatch might be a step too far, or they might be the
  final region.
