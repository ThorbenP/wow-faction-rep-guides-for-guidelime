# guides_generator — GuideLime reputation farm guide generator

Generates a standalone [GuideLime](https://github.com/borick/Guidelime) sub-addon
for every reputation faction in WoW Classic Era and Burning Crusade. Each
addon contains a routed, level-bucketed walkthrough of all rep-granting
quests for one faction, together with the prerequisite chain quests needed
to unlock them.

The data comes entirely from the [Questie](https://github.com/Questie/Questie)
database — no manual curation, no hand-written guides.

## Support the project

If these guides save you time and you'd like to say thanks, you can buy me a
coffee — entirely optional, all guides stay free either way.

- ☕ **Buy me a coffee**: <https://buymeacoffee.com/thpi>

## Quick start

```bash
pip install slpp
python3 create.py            # interactive: pick a faction and an expansion
python3 create.py --faction darnassus
python3 create.py --faction 69
python3 create.py --all      # all 30 factions in one run, default TBC
```

Generated addons are written to `./addons/<expansion>/`
(e.g. `./addons/tbc/` for TBC Anniversary / Burning Crusade Classic).
Copy each folder you want to use into your WoW `Interface/AddOns/`
directory; the addons declare `## Dependencies: Guidelime`, so they
group under the main GuideLime addon in the in-game addon manager.

Each `.toc` carries the matching `## Interface` version
(`20504` for TBC, `11403` for Classic Era).

## Features

- **Tour routing**: greedy nearest-feasible cluster discovery with
  on-the-way absorption, then alternating **2-opt** (segment reversal)
  and **or-opt** (segment relocation) refinement passes until both
  converge. Typical sub-guide paths are within a few percent of optimal
  while respecting quest precedence (`pre`, `preg`, `next`).
- **Per-zone sub-guides**: quests are bucketed by their pickup zone, then
  by tier (natural / cleanup) so each zone is a coherent walkthrough.
- **Cross-zone handling**: chains that leave a zone are extracted into a
  "Complex Quests" section at the end of the appropriate sub-guide, so
  the optional cross-zone work is clearly separated from the in-zone path.
- **Race / class filtering**: restrictions are emitted as `[A ...]`
  tags — GuideLime hides non-matching steps at runtime, so the same addon
  serves every race/class on a side.
- **Sage-style tags**: only the quest/NPC ID is in the tag body; the name
  is rendered as an italic `*Name*:` prefix. GuideLime resolves names
  itself at runtime.
- **Quality reports**: every run writes a per-addon `QUALITY_REPORT.md`
  (snapshot, sub-guide breakdown, dropped quests) into the addon's own
  directory — so a single-faction `--faction` run produces the same
  artefact you would get from a full bulk pass. `--all` additionally
  writes the slim `_quality_report.md` at the repo root, with the
  global snapshot, faction comparison, and top/bottom-20 sub-guide
  ranking. Useful as a baseline when iterating on routing.

## Output layout

```
addons/
└── tbc/                       (one subdirectory per generated expansion)
    ├── Guidelime_ThPi_DarnassusRepGuide/
    │   ├── Guidelime_ThPi_DarnassusRepGuide.toc
    │   ├── Guidelime_ThPi_DarnassusRepGuide.lua
    │   ├── CHANGELOG.md
    │   ├── README.md          (faction- and expansion-specific player readme)
    │   └── QUALITY_REPORT.md  (per-addon pathing metrics, written every run)
    ├── Guidelime_ThPi_IronforgeRepGuide/
    │   └── ...
    └── ...                    (30 addons for TBC — all known factions)
_quality_report.md             (slim global summary, written by --all only)
```

The folder prefix `Guidelime_<AUTHOR>_` matches GuideLime's sub-addon
convention (e.g. `Guidelime_Sage`); it groups all your generated addons
together in the addon list. The author tag is `guides_generator.constants.AUTHOR`.

## Generated guide structure

Each addon registers one `Guidelime.registerGuide([[...]], "category")`
block per zone bucket. A typical sub-guide looks like this:

```
[N 18-30 Ashenvale (+10350 rep)]
[D 42 quests in *Ashenvale*. \\ ~9375 rep for *Darnassus*.
   \\ + 10 complex quests (chain leading to other zones, +475 rep).]
[GA Alliance]

[OC]Quest chains in this zone:
[OC]  Chain 1: The Tower of Althalaxx -> Supplies to Auberdine
[OC]  Chain 2: Raene's Cleansing -> An Aggressive Defense
[OC]  ...

[OC]At (26.2, 38.7) in Ashenvale: 2x pickup
[G 26.2,38.7 Ashenvale]*The Tower of Althalaxx (Pt. 1)*: [QA970] *Chain 1 1/5*
*Bathran's Hair*: [QA1010] *Chain 5 1/5*
[G 31.4,30.7 Ashenvale]*The Tower of Althalaxx (Pt. 1)*: [QC970] *Chain 1 1/5*
...

[OC]Complex quests: chains that start here and lead to other zones.

[OC]Complex chains:
[OC]  Chain 1: Velinde Starsong -> Velinde's Effects -> The Barrens Port -> ...

[G 86.0,44.1 Ashenvale]*Velinde Starsong*: [QA1037] *Chain 1 1/8*
...
```

Key elements:

- **Title** — `[N min-max <zone> (+<rep> rep)]` so the player sees the
  reward up front when picking which sub-guide to do.
- **Description** — `[D ...]` with quest count, total rep, and any
  complex-quest summary.
- **Chain index** — opening `[OC]` block listing every quest chain in
  the sub-guide, so the player sees the structure up front.
- **Cluster header** — emitted only for clusters with two or more stops:
  `[OC]At (x, y) in <zone>: Nx pickup, Ny objective, Nz turnin`.
- **Inline chain markers** — `*Chain 3 2/4*` on each chain step, with a
  combined `*Chain 3 2->3/4*` form when a turnin and the next pickup
  share a single emitted line.
- **Location sharing** — the `[G x,y zone]` hint is omitted while
  consecutive steps share a position (within 1.5 map units).

## Tag reference

| Tag | Meaning |
|---|---|
| `[N min-max <name>]` | Sub-guide title and level range |
| `[D <text>]` | Sub-guide description (`\\` is a line break) |
| `[GA Alliance]` / `[GA Horde]` | Restricts the sub-guide to one side |
| `[G x,y <zone>]` | Map marker / waypoint for the next step |
| `[QA<id>]` | Pick up the quest |
| `[QC<id>]` | Mark the objective complete (progress comes from the quest log) |
| `[QT<id>]` | Turn in the quest |
| `[TAR<id>]` | Click-to-target macro for an NPC |
| `[A <race/class,...>]` | Step is only shown for the listed race/class |
| `[OC]<text>` | Optional comment line, no checkbox |

The QA/QT/QC/TAR tags carry **only the ID** in the body; the human-
readable name is the `*Name*:` italic prefix in front of the tag. This
matches the Sage convention and avoids a known GuideLime parser bug
where names inside the tag body trigger `loadStepUseItems` errors on
short sub-guides.

Plain-text annotations after a QA tag (round parentheses, not square
brackets — those would parse as another tag):

| Annotation | Meaning |
|---|---|
| `(repeatable)` | Quest is repeatable (`specialFlags` bit 0) |
| `(needs Honored)`, `(needs Revered)`, ... | Required minimum standing (`requiredMinRep`) |
| `(needs Cooking 50)`, ... | Required profession skill (`requiredSkill`) |

## Pipeline

1. **Load Questie DB** — quest, NPC, object, and item tables (cached on disk).
2. **Filter by faction** — keep quests with `reputationReward` for the
   chosen faction.
3. **Bridge expansion** — pull in `pre`/`preg` quests transitively, even
   if they grant no rep, so chains are acceptable in-game.
4. **Resolve coordinates** — pickup, turnin and objective coords via
   NPC -> object -> item-drop cascades. Item-drop bridges whose source is
   a dungeon boss fall back to the dungeon entrance (see
   `constants.DUNGEON_ENTRANCES`).
5. **Cross-zone classification** — chains that span zones are split: the
   self-contained sub-tree stays in its zone, the rest goes to a
   "Complex" section attributed to the chain's entry zone.
6. **Bucketing** — each kept quest goes into a `(zone, natural|cleanup)`
   bucket. Chain-coalescing then merges buckets within a zone if a
   prerequisite ends up in the other bucket, otherwise GuideLime would
   hide the dependent step.
7. **Routing** — per sub-guide, build a tour: cluster discovery,
   on-the-way absorption, then alternate 2-opt and or-opt refinement
   passes until convergence.
8. **Emit** — write `<addon>.toc`, `<addon>.lua`, the per-addon
   `CHANGELOG.md`, and `README.md`.

## Routing in detail

For each sub-guide the routing produces a sequence of *cluster* and
*travel* entries:

- **Cluster**: stops within `CLUSTER_RADIUS` map units of the current
  position, visited in order without an inter-step travel hop. Picking a
  stop moves the cluster centre, so a cluster grows incrementally.
- **Travel**: a single stop reached after travel. While travelling to a
  far stop, intermediate stops are absorbed if their detour is below
  `DETOUR_THRESHOLD` and they are not already inside the destination's
  cluster.

`CLUSTER_RADIUS` defaults to 12 map units. WoW map coordinates are
normalised 0-100 per zone, but the actual zone size differs hugely
(Tanaris is huge, Stormwind is small), so sparse zones get an override
in `constants.ZONE_CLUSTER_RADIUS` (up to 25). City- and medium-density
zones use the default — empirically a smaller radius makes them worse.

After the greedy tour, two refinement heuristics alternate until both
converge (or `MAX_REFINE_ROUNDS = 8` is hit; most sub-guides finish in
2–4 rounds):

- **2-opt** (`routing/two_opt.py`) reverses every (i, j) segment that
  lowers the total cost without breaking precedence.
- **Or-opt** (`routing/or_opt.py`) picks up a contiguous segment of 1–4
  TourEntries and re-inserts it elsewhere, again without breaking
  precedence. Each candidate is evaluated by an O(1) incremental cost
  delta — six boundary edges change at most, so the full
  `_tour_cost` recompute is avoided.

Each pass unlocks moves the other cannot reach in a single iteration;
alternating squeezes more distance out than running either pass harder.
The cost function shared by both penalises cross-zone jumps with
`JUMP_PENALTY = 45.0` so the refinement does not "shorten" intra-zone
distance by adding extra flightpath hops.

Precedence is enforced by `routing.feasibility.is_feasible`: a stop is
only considered if all its prerequisites are already in the `completed`
set. Quests without `pickup_coords` (item-drop bridges) treat the QA as
implicitly satisfied — their QC and QT do not wait for a non-existent
pickup stop.

## Configuration

Tuning constants live under `guides_generator/constants/` (split by domain;
all symbols are re-exported from the package root):

| Constant | Lives in | Purpose |
|---|---|---|
| `AUTHOR` | `constants/paths.py` | Author tag in folder names, .toc Title, Author field |
| `REPO_URL` | `constants/paths.py` | GitHub repo, embedded in every per-addon README |
| `DEFAULT_CLUSTER_RADIUS` | `constants/zones.py` | Default routing cluster radius (12.0) |
| `ZONE_CLUSTER_RADIUS` | `constants/zones.py` | Per-zone overrides for sparse zones |
| `ZONE_LEVEL_TIER` | `constants/zones.py` | Natural level range per zone (used for bucketing) |
| `ZONE_MAP` | `constants/zones.py` | Numeric zone id -> human-readable name |
| `CITY_ZONES` | `constants/zones.py` | Capital cities — no tier filter applied |
| `DUNGEON_ENTRANCES` | `constants/dungeons.py` | Instance-zone-id -> (parent zone, x, y) entrance fallback |
| `DUNGEON_BOSS_NPCS` | `constants/dungeons.py` | Override map for NPCs with `zone=0` that live in a known dungeon |
| `FACTION_NAMES`, `FACTION_GROUPS` | `constants/factions.py` | Faction registry |

Routing constants are scattered across `guides_generator/routing/`:

| Constant | Lives in | Default | Purpose |
|---|---|---:|---|
| `CLUSTER_RADIUS` | `routing/tour.py` | 12.0 | per-zone overridable via `ZONE_CLUSTER_RADIUS` |
| `DETOUR_THRESHOLD` | `routing/tour.py` | 6.0 | maximum extra distance for on-the-way absorption |
| `MAX_REFINE_ROUNDS` | `routing/tour.py` | 8 | upper bound on alternating 2-opt/or-opt rounds (early-exits on convergence) |
| `JUMP_PENALTY` | `routing/two_opt.py` | 45.0 | cost of one cross-zone jump (in map units), used by both 2-opt and or-opt |
| `MAX_PASSES` | `routing/two_opt.py` | 3 | max improving 2-opt swaps per outer round |
| `MAX_PASSES` | `routing/or_opt.py` | 3 | max improving or-opt relocations per outer round |
| `DIFFERENT_ZONE_PENALTY` | `routing/distance.py` | 1e6 | synthetic distance for cross-zone neighbours |

## Versioning and changelog

Each new release is one Markdown file under `changelog/` named
`vX.Y.Z[_<slug>].md`. On generation:

1. The highest version (semver-sorted) is written to every `.toc`'s
   `## Version` field.
2. All entries are concatenated in reverse-chronological order (newest
   on top, separated by `---`) and written as `CHANGELOG.md` into every
   addon directory.
3. If `changelog/` is empty, the version falls back to `0.0.0`.

So every distributed addon ships with a complete, identical history.

Alongside `CHANGELOG.md`, `write_addon` also drops a `README.md` into every
addon directory. It is templated per faction + expansion (faction name,
interface version, install path) and carries the GitHub repo link from
`REPO_URL` plus the hardcoded Buy-me-a-coffee URL.

## Project layout

```
create.py                              # entry point (re-exports cli.main)
caveats.md                             # recurring pitfalls and design rationale
readme.md                              # this file
changelog/                             # versioned release notes
guides_generator/
    cli.py                             # argument parsing + dispatch
    chains.py                          # connected-component detection, topo sort
    zones.py                           # zone assignment and bucketing
    prompts.py                         # interactive faction + expansion selection
    constants/                         # static reference data, split by domain
        paths.py        factions.py    races_classes.py
        zones.py        dungeons.py    databases.py
    questie/                           # Questie DB I/O
        fetch.py                       # downloader + on-disk cache
        lua.py                         # slpp wrapper, table iteration helpers
        spawns.py                      # NPC/object spawn-list extraction
        quest_db.py     npc_db.py      object_db.py    item_db.py
    quests/                            # quest-level processing
        builder.py                     # filter + lift Questie array into quest dict
        bridges.py                     # pull in pre/preg prerequisite chains
        classify.py                    # split into kept vs complex (cross-zone)
        decode.py                      # race / class bitmask decoders
    coords/                            # coordinate resolution
        geometry.py                    # Coord type, clustering, centroid
        resolve.py                     # NPC/object/item lookup, attach_coords
        objectives.py                  # objective spawn centroid
    routing/                           # tour builder
        types.py                       # Stop, TourEntry
        feasibility.py                 # predecessor map, is_feasible
        distance.py                    # zone-aware distance helper
        cluster.py                     # cluster discovery + on-the-way absorption
        start.py                       # spawn-anchor heuristic for natural tier
        two_opt.py                     # 2-opt refinement pass
        or_opt.py                      # or-opt refinement pass (incremental cost)
        tour.py                        # route_subguide orchestrator (alternates 2-opt + or-opt)
        stats.py                       # compute_tour_stats
    output/                            # GuideLime-Lua emission
        sanitize.py                    # UTF-8 -> safe ASCII subset
        chain_index.py                 # chain detection, name disambiguation
        tags.py                        # [A race/class] tag construction
        emitter.py                     # GuideEmitter (stateful tag-line renderer)
        header.py                      # file-top comment block
        sub_guide.py                   # one Guidelime.registerGuide(...) block
        guide.py                       # generate_guide orchestrator
    addon/                             # write addon directory
        names.py                       # addon folder + .toc Title naming
        expansions.py                  # per-expansion display labels
        toc.py          changelog.py   readme.py        writer.py
    pipeline/                          # CLI orchestration
        loader.py                      # shared DB loaders + build-and-write
        single.py                      # interactive / --faction
        bulk.py                        # --all
        console.py                     # progress + summary printing
    report/                            # quality report
        aggregate.py    sections.py    writer.py
addons/<expansion>/                    # generated addon directories
                                       # each addon also has QUALITY_REPORT.md
cache/<expansion>/                     # cached Questie DB files
_quality_report.md                     # slim global summary, --all only
```

Public entry points per package:

| Package | Main symbols |
|---|---|
| `questie` | `fetch_or_load`, `parse_quest_db`, `parse_npc_db`, `parse_object_db`, `parse_item_db` |
| `quests` | `filter_quests_by_faction`, `expand_with_prereq_bridges`, `drop_unreachable_bridge_chains`, `attribute_complex_to_zones`, `decode_races`, `decode_classes` |
| `coords` | `attach_coords`, `compute_objective_centroid`, `get_npc_coords` |
| `zones` | `assign_primary_zone`, `is_self_contained`, `group_by_zone_and_tier`, `get_zone_tier` |
| `chains` | `find_chains`, `topo_sort` |
| `routing` | `route_subguide`, `pick_start_position`, `compute_tour_stats`, `Stop`, `TourEntry` |
| `output` | `generate_guide`, `GuideEmitter` |
| `addon` | `write_addon`, `read_changelog`, `addon_name_for_faction`, `guide_title_for_faction` |
| `pipeline` | `run_single`, `run_all` |
| `report` | `write_addon_report`, `write_global_report` |
| `prompts` | `prompt_faction`, `prompt_expansion` |
| `cli` | `main` |

## Data sources

All from [Questie](https://github.com/Questie/Questie):

| File | Content |
|---|---|
| `Database/<expansion>/<prefix>QuestDB.lua` | quest data: rep rewards, race/class bitmasks, prerequisites, objectives |
| `Database/<expansion>/<prefix>NpcDB.lua` | NPC spawns and names |
| `Database/<expansion>/<prefix>ObjectDB.lua` | world object spawns |
| `Database/<expansion>/<prefix>ItemDB.lua` | items with their drop sources (npcDrops, objectDrops, vendors) |

`<expansion>` is `Classic` or `TBC`; `<prefix>` is `classic` or `tbc`.
Files are downloaded on first use into `./cache/<expansion>/` so different
game versions never collide on the same filename.

## Quality report

Two complementary files are emitted:

- `<addon_dir>/QUALITY_REPORT.md` — one per addon. Self-contained
  faction snapshot, sub-guide table, dropped-quest list, glossary.
  Single-faction (`--faction`) and bulk (`--all`) runs both write it,
  so a per-faction tuning loop can diff this file directly.
- `_quality_report.md` at the repo root — slim global summary across
  every faction (bulk runs only). Snapshot, faction comparison,
  global top/bottom-20 sub-guides.

The headline metric is **N-Rep/Dist** — rep delivered per map unit
walked. Higher is better, with no upper target. There is no
normalised 0-100 score: a routing change is an improvement if
`Global Rep/Dist` (in the slim global) or the per-faction
`Rep/Dist` (in the addon report) goes up. Distance, x-jumps and
absorption are kept as diagnostics but do not feed a composite.

The report is intended for the maintainer; it is not part of the
distributed addons.

## Coverage

Measured on the Darnassus faction (TBC, ~280 rep quests):

| Field | Coverage |
|---|---|
| Pickup coords | ~97% |
| Turnin coords | ~99% |
| Objective coords | ~40% |

Quests without coords are still emitted, just without a `[G ...]` hint
on the affected step.

## Caveats

`caveats.md` documents recurring pitfalls (UTF-8 punctuation in
GuideLime tags, item-drop bridges with no pickup coords, cross-bucket
prerequisites, test NPCs named `[PH] ...`, etc.) and the rationale for
non-obvious choices. Worth a read before changing anything in the
output path or routing.

## Limitations

- The router is greedy + alternating 2-opt/or-opt, not an exact TSP
  solver. It is robust and fast — a full bulk run takes ~15s once the
  Questie DBs are cached.
- Quest chains spanning multiple sub-guides are tracked as singletons
  inside each sub-guide. The chain index lists each part separately.
- Battleground and a few other zones are not in `ZONE_MAP`; quests
  living only there are dropped (the report calls these out as "Lost").
- Era and TBC are supported. Wrath could be added analogously by adding
  a `Database/Wotlk/...` entry to `DB_FILES`.
