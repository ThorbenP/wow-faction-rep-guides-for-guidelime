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

- **Tour routing**: greedy nearest-feasible build, K=96 randomized
  multistart rebuilds, then a deep refinement chain on the cheapest
  candidate (alternating 2-opt + or-opt to convergence, 3-opt for
  small tours, entry-level Held-Karp for tiny tours, stop-level 2-opt
  and or-opt that can break clusters when shorter routes exist, and a
  final stop-level Held-Karp DP that finds the provably-optimal stop
  ordering for sub-guides up to 30 stops via precedence-pruned sparse
  bitmask DP). All quests' precedence (`pre`, `preg`, `next`) is
  respected. Multistart candidates are evaluated in parallel across
  all available CPU cores; single-faction runs cost a few seconds,
  `--all` takes ~2.5 minutes on a 12-thread host. See
  `_experiments_history.md` for the experiment trail that picked
  this chain.
- **Per-zone sub-guides**: quests are bucketed by their pickup zone, then
  by tier (natural / cleanup) so each zone is a coherent walkthrough.
- **Cross-zone handling**: chains that leave a zone are extracted into a
  "Complex Quests" section at the end of the appropriate sub-guide, so
  the optional cross-zone work is clearly separated from the in-zone path.
- **Race / class filtering**: restrictions are emitted as `[A ...]`
  tags — GuideLime hides non-matching steps at runtime, so the same addon
  serves every race/class on a side.
- **Verb-led step bodies**: each step reads as a player instruction
  (`Pick up [QA<id>]`, `Kill [TAR<a>], [TAR<b>] for [QC<id>]`,
  `Loot for [QC<id>]`, `Turn in [QT<id>] (+rep rep)`, combined
  `Turn in [QT<id1>] (+rep), pick up [QA<id2>]`). Tags carry only the
  ID; GuideLime resolves quest and NPC names at runtime.
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
    │   ├── LICENSE            (GPL-3.0 text, copied from repo root)
    │   └── QUALITY_REPORT.md  (per-addon pathing metrics, written every run)
    ├── Guidelime_ThPi_IronforgeRepGuide/
    │   └── ...
    └── ...                    (30 addons for TBC — all known factions)
_quality_report.md             (slim global summary, written by --all only)
dist/
└── tbc/                       (CurseForge-ready zips, one per addon)
    ├── Guidelime_ThPi_DarnassusRepGuide.zip   (CHANGELOG, README, LICENSE,
    │                                           .toc, .lua — no QUALITY_REPORT)
    └── ...                    (built automatically by --all)
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

[OC]At (26.2, 38.7) in Ashenvale: 2x pickup
[G 26.2,38.7 Ashenvale]Pick up [QA970]
Pick up [QA1010]
[G 31.4,30.7 Ashenvale]Kill [TAR2031], [TAR1984] for [QC970]
[G 32.6,29.5 Ashenvale]Turn in [QT970] (+250 rep), pick up [QA971]
...

[OC]Complex quests: chains that start here and lead to other zones.

[G 86.0,44.1 Ashenvale]Pick up [QA1037]
Kill [TAR4318] for [QC1037]
...
```

Key elements:

- **Title** — `[N min-max <zone> (+<rep> rep)]` so the player sees the
  reward up front when picking which sub-guide to do.
- **Description** — `[D ...]` with quest count, total rep, and any
  complex-quest summary.
- **Cluster header** — emitted only for clusters with two or more stops:
  `[OC]At (x, y) in <zone>: Nx pickup, Ny objective, Nz turnin`.
- **Verb-led step body** — `Pick up [QA<id>]`, `Kill [TAR<a>], [TAR<b>]
  for [QC<id>]`, `Loot for [QC<id>]`, `Turn in [QT<id>] (+rep rep)`,
  or combined `Turn in [QT<id1>] (+rep), pick up [QA<id2>]` when one
  NPC takes a turnin and immediately offers the next pickup.
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

The QA/QT/QC/TAR tags carry **only the ID** in the body — never a
name. GuideLime resolves quest and NPC names from its own DB at
runtime, and putting names inside the tag body triggers a known
`loadStepUseItems` parser bug on short sub-guides. The verb prose
that wraps the tag (`Pick up [QA<id>]`, `Kill [TAR<a>] for [QC<id>]`,
...) is the player-facing instruction; the name appears in-game
because GuideLime expands the tag.

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
7. **Routing** — per sub-guide, run the multistart pipeline:
   K=96 randomized rebuilds, cost-aligned acceptance, ILS escape,
   then the deep refinement chain (2-opt + or-opt + 3-opt + defrag +
   entry-level Held-Karp + stop-level 2-opt + stop-level or-opt +
   stop-level Held-Karp DP) on the winner. The final stop-level
   Held-Karp finds the provably-optimal stop ordering for sub-guides
   up to 30 stops via precedence-pruned sparse bitmask DP — anything
   larger is left to the heuristic chain.
   See `routing/tour.py` for the orchestrator and
   `_experiments_history.md` for the trail that picked the chain.
8. **Emit** — write `<addon>.toc`, `<addon>.lua`, the per-addon
   `CHANGELOG.md`, `README.md` and `LICENSE`.
9. **Zip** (`--all` only) — bundle the addon directory into
   `dist/<expansion>/<addon>.zip` so the run produces ready-to-upload
   archives. `QUALITY_REPORT.md` is excluded from the zip.

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

The greedy build is just the seed. Every sub-guide goes through
**multistart** (`routing/multistart.py`) — K=96 randomized rebuilds
plus an ILS escape — and the cheapest result is then run through
the deep refinement chain (`routing/tour.py:refine_tour`):

- **2-opt** (`routing/two_opt.py`) reverses every (i, j) segment
  that lowers the total cost without breaking precedence.
- **Or-opt** (`routing/or_opt.py`) picks up a contiguous segment of
  1–4 TourEntries and re-inserts it elsewhere. Each candidate uses
  an O(1) incremental cost delta — six boundary edges change at
  most, so the full `_tour_cost` recompute is avoided.
- **3-opt** (`routing/three_opt.py`) for tours with ≤50 entries —
  three-cut reconnection patterns that 2-opt and or-opt cannot
  reach in a single move.
- **Defragmentation** merges same-coord adjacencies into one cluster
  entry. Cosmetic under rep/dist (visit order unchanged), but it
  keeps the emitted Lua tighter.
- **Entry-level Held-Karp DP** (`routing/held_karp.py:held_karp_pass`)
  for tours with ≤12 entries — provably-optimal entry permutation under
  precedence, with clusters kept atomic.
- **Stop-level 2-opt** (`routing/stop_2opt.py`) and **stop-level
  or-opt** (`routing/stop_or_opt.py`) finishers run on the
  flattened stop sequence, then re-cluster. They can pull a single
  stop out of its discovery-time cluster when a different position
  is geometrically cheaper — moves the entry-level passes cannot
  reach because they treat clusters as atomic.
- **Stop-level Held-Karp DP** (`routing/held_karp.py:held_karp_stop_level_pass`)
  for tours whose flattened stop count is ≤ `MAX_STOPS` (30). Same
  bitmask DP as the entry-level pass but applied to the stop sequence
  with a sparse dict over reachable states — precedence pruning keeps
  the state count tractable up to 30 stops in well under a second.
  Final pass: when it fires the result is the provably-optimal stop
  ordering under the cost model, strictly at least as good as anything
  the heuristic chain found.

Each pass unlocks moves the others cannot reach. The cost function
shared by all of them penalises cross-zone jumps with
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
| `THREE_OPT_MAX_ENTRIES` | `routing/tour.py` | 50 | tour-length cap for the 3-opt sweep (O(N³)) |
| `MULTISTART_ITERATIONS` | `routing/multistart.py` | 96 | K, the number of randomized rebuilds per sub-guide |
| `ILS_ROUNDS` | `routing/multistart.py` | 6 | random shake + re-refine rounds on the multistart winner |
| `MAX_ENTRIES` | `routing/held_karp.py` | 12 | entry-level Held-Karp's O(N²·2^N) cap above which the entry-level DP is skipped |
| `MAX_STOPS` | `routing/held_karp.py` | 30 | stop-level Held-Karp's cap; final pass that finds the provably-optimal stop ordering via precedence-pruned sparse DP |
| `JUMP_PENALTY` | `routing/two_opt.py` | 45.0 | cost of one cross-zone jump (in map units), shared across every routing pass |
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
        three_opt.py                   # 3-opt refinement (capped at THREE_OPT_MAX_ENTRIES)
        held_karp.py                   # exact DP for tours <=12 entries
        stop_2opt.py                   # stop-level 2-opt finisher
        stop_or_opt.py                 # stop-level or-opt finisher
        multistart.py                  # K=96 randomized rebuilds + ILS escape
        tour.py                        # route_subguide orchestrator (always-on multistart)
        stats.py                       # compute_tour_stats
    output/                            # GuideLime-Lua emission
        sanitize.py                    # UTF-8 -> safe ASCII subset
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
| `routing` | `route_subguide`, `pick_start_position`, `compute_tour_stats`, `Stop`, `TourEntry` |
| `output` | `generate_guide`, `GuideEmitter` |
| `addon` | `write_addon`, `zip_addon`, `read_changelog`, `addon_name_for_faction`, `guide_title_for_faction` |
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

## License

This project is licensed under the **GNU General Public License v3.0 or
later** (GPL-3.0-or-later). The full license text lives in the
[LICENSE](./LICENSE) file at the repo root, and a copy is dropped into
every generated addon directory by `write_addon`, so each standalone
upload (e.g. on CurseForge) ships GPL-§4-compliant on its own.

GPL-3.0 was chosen so the generated sub-addons stay license-compatible
with **GuideLime** (the parent addon, GPL-2.0-or-later). Anyone
redistributing or modifying this generator or the addons it produces
must keep them under GPL-3.0-or-later and make the corresponding source
available.
