# Caveats and design notes

Recurring pitfalls collected from real bugs, plus the rationale for the
non-obvious choices. Organised by topic, not by version (see `changelog/`
for "what changed when"). Worth a read before touching the output path
or the routing.

---

## 1. GuideLime tag renderer is UTF-8 fragile

GuideLime parses tag bodies byte-oriented. Multibyte UTF-8 punctuation
inside an `[OC]` comment or any `[X ...]` tag produces mojibake or empty
checkboxes. German umlauts (`ä ö ü Ä Ö Ü ß`) round-trip fine.

### Confirmed offenders

| Character | Codepoint | Symptom |
|---|---|---|
| `×` | U+00D7 | `[OC]----- ... 1× ... -----` rendered as an empty checkbox |
| `→` | U+2192 | chain index `Lord Grayson -> ...` rendered as a mojibake block |
| `—` | U+2014 | em-dash inside `[D ...]` corrupted the description |
| `–` | U+2013 | en-dash, same as above |
| `…` | U+2026 | horizontal ellipsis, same |
| `‘ ’ “ ”` | U+2018-201D | smart quotes, replaced defensively |

### Defence

`output/sanitize.py` exposes `safe_text()` and `safe_tag_content()`,
applied to every dynamically composed string in the output: tag bodies
of `[QA]/[QT]/[QC]/[TAR]`, the `*Name*:` italic prefix on QC steps,
cluster headers, the chain index, and `[N]/[D]` titles.
`_PUNCT_REPLACEMENTS` maps the known offenders to ASCII; everything else
outside ASCII (other than the umlaut whitelist `_ALLOWED_UTF8`) is
dropped silently. When you add a new output site, channel the dynamic
value through one of those helpers — never inline a raw `q['name']`
straight into a Lua string.

### Pre-commit check

```sh
grep -P "[^\x00-\x7FäöüÄÖÜß]" addons/Guidelime_*/Guidelime_*.lua
```

Hits = bug. Expected: nothing.

---

## 2. Square brackets in NPC and quest names

The Questie database contains test/dev entries whose names start with
`[PH]`, `[DND]`, `[DNT]`, `[OLD]`, `[Not Used]`. If such a name lands
inside a tag body — `[TAR<id> [PH] Foo]` — the inner `]` closes the tag
prematurely, and the rest becomes plain text. The visible result is an
empty checkbox or a broken render.

### Defence

- **Quest names**: quests whose name starts with `[OLD]` / `[DEP]` /
  `[UNUSED]` are dropped at the source in `quests/builder.py:build_quest_dict`
  (constant `DEPRECATED_PREFIXES`).
- **NPC names**: kept in the DB (filtering them by name is fragile) but
  passed through `safe_tag_content` (`output/sanitize.py`), which
  replaces `[` with `(` and `]` with `)` before they enter a TAR tag.

When pulling text from a new source (a future Questie patch, a different
DB), do not assume names are tag-safe. Always go through the sanitiser.

---

## 3. Lua long-bracket and apostrophes in strings

The guide body sits inside `[[ ... ]]` (Lua long-bracket). Anything is
allowed inside except the closing `]]`. The category, however, is the
second argument: `registerGuide([[...]], "ThPi's ... Rep Guide")`. If
the category were single-quoted, `ThPi's` would end the string early.

### Defence

- The category is emitted with double quotes: `f']], "{category}"'`. Do
  not switch to single quotes without first solving the apostrophe case.
- No quest name with `]]` has been seen in any DB so far, but it would
  break the long-bracket. `_safe_text` does not currently strip `]]`;
  add that if a future DB triggers it.

---

## 4. Quests without `pickup_coords` (item-drop bridges)

Some bridge quests are auto-started when an item enters the player's
inventory — there is no NPC pickup, just an item drop. Example: Q6981
"The Glowing Shard" (bridge for Q3370 "In Nightmares" in the Barrens).

### Symptoms when not handled

1. The bridge falls out of bucketing if `zoneOrSort` is also missing
   (`assign_primary_zone` returns 0, the quest is dropped).
2. Dependent rep-quests are then hidden by GuideLime because their
   prerequisite is not present in the same sub-guide.
3. `is_feasible(QT)` blocks forever — historically it required
   `'QA' in completed`, but with no pickup there is no QA stop, so the
   QT lands in the "unreachable stops" orphan section.

### Defence

- `zones.py:assign_primary_zone` cascades pickup -> turnin -> zoneOrSort
  so item-drop bridges fall back to their turnin zone.
- `routing/feasibility.py:is_feasible` skips the QA check when
  `pickup_coords` is missing — the QC and QT are then directly feasible
  (the pickup is implicit).
- `coords/resolve.py:get_npc_coords` falls back to a dungeon entrance
  when an NPC has no world coords but its zone or NPC id is in
  `DUNGEON_ENTRANCES` / `DUNGEON_BOSS_NPCS`. Used when the source item
  drops from a dungeon boss (Mutanus -> Wailing Caverns, etc.).

### When the item itself has no source

About 1 in 13 item-drop bridges in the TBC data set has empty
`npcDrops`, `objectDrops` and `vendors` — a real data gap, no code fix
possible. Example: Q9550 "Weathered Treasure Map" (Exodar). The bridge
gets bucketed via the turnin-zone fallback, but no pickup hint can be
emitted.

---

## 5. Cross-bucket prerequisites within one zone

`group_by_zone_and_tier` buckets each quest into either `natural` (level
matches the zone's tier) or `cleanup` (level outside tier ± tolerance).
A quest chain can cross that boundary: Q2741 "The Super Egg-O-Matic"
(level 47) lands in natural Tanaris, while its follow-up egg quests
Q2747-2750 (level 60) end up in the cleanup bucket.

### Symptom

The cleanup sub-guide shows its title but is otherwise empty in WoW —
GuideLime hides every step whose prerequisite is not part of the same
sub-guide.

### Defence

`zones.py:_coalesce_chain_buckets` runs as a final pass: any quest whose
`pre`/`preg` predecessor sits in the same zone but a different bucket
moves to the prerequisite's bucket. Iterates until no further move is
possible. Keep this pass when refactoring bucketing — it is the only
thing preventing the egg-quest case from breaking.

---

## 6. Cross-zone quests (pickup and turnin in different zones)

Three cases:

| Case | Routing |
|---|---|
| Solo cross-zone (no chain partners) | -> complex section of the pickup zone |
| Chain with a cross-zone tail (rest of the chain stays in one zone) | stays in the chain (visual integrity > strict separation) |
| Cross-zone bridge chain (bridges spanning zones) | -> complex section of the entry pickup zone |

### Defence

- `quests/classify.py:drop_unreachable_bridge_chains` ->
  `_extract_in_zone_subset` + `_identify_solo_cross_zone`.
- `quests/classify.py:attribute_complex_to_zones` assigns each complex
  component to the pickup zone of its entry quest.
- `output/sub_guide.py:_emit_complex_section` appends the complex tour
  at the end of the matching zone's sub-guide.

### Consistency check after filter changes

`kept + complex == total` for every faction. If the diff is non-zero,
quests are leaking somewhere; that identity is the canonical test.

---

## 7. Tag-in-tag with race_class_tag

`[QA<id>]<annotations>[A Druid]` — the class restriction `[A Druid]`
sits AFTER the closing `]` of the QA tag, not inside it. A tag inside
a tag would be ambiguous to the parser.

### Defence

The `GuideEmitter` (`output/emitter.py`) always emits the
`race_class_tag` (`output/tags.py`) after the closing `]` of the
QA/QT/QC tag, never inside it.

---

## 8. Empty steps / checkboxes without label

A step body that ends up empty (or only contains an `[OC]` with no
text) renders as an empty checkbox in some GuideLime versions.

### Observed cases

- Earlier the generator emitted a stray `[GT ON]` tag when turnin was
  at the same position as pickup — that rendered as an empty checkbox.
  The tag has since been removed.
- `[OC]----- ... -----` (the old cluster-header format) led to a
  checkbox in some versions because of the leading dashes. The format
  was changed to `[OC]At (x, y) ...` — plain ASCII, no leading
  punctuation.

### Defence

- Never emit an `[OC]` line whose first character after `[OC]` is a
  non-letter (dashes, arrows, punctuation).
- Never emit a step with an empty body. If `_emit_with_location` is
  called with no body content, drop the line entirely.

### Pre-commit check

```sh
grep -nE '^\[OC\][^A-Za-z]' addons/Guidelime_*/Guidelime_*.lua
grep -nE '^\[Q[ATC]\d+\]\s*$' addons/Guidelime_*/Guidelime_*.lua
```

Both should return nothing.

---

## 9. `(repeatable)` and other plain-text annotations

Annotations after a step (`(repeatable)`, `(needs Honored)`, etc.) are
**plain text in round parentheses**. Earlier they were `[repeatable]` —
GuideLime interpreted that as a tag and crashed.

### Defence

`GuideEmitter._quest_annotations` (`output/emitter.py`) only uses
round parentheses. Square brackets are reserved for GuideLime tag
syntax — never use them for human-readable annotations.

---

## 10. Battleground zones outside ZONE_MAP

Quests in Alterac Valley (zone 2597), Arathi Basin and similar
battleground sub-zones currently get `assign_primary_zone == 0` and are
dropped. They are not relevant for normal rep farming. If anyone wants
to add Stormpike Guard / Frostwolf Clan factions, `ZONE_MAP` needs to
be extended; otherwise the quests are invisible to the generator.

---

## 11. Sage-style tags: no name in the tag body

GuideLime's tag parser stumbles on `[QA<id> <name>]` for small
sub-guides — `attempt to index local 'step' (a nil value)` errors in
`loadStepUseItems`. The format with names worked for large sub-guides
but failed for sub-guides with only 1-2 quests (Dun Morogh, Loch Modan,
Thousand Needles cleanup).

### Defence

Tags carry only the ID:
- `[QA<id>]`, `[QT<id>]`, `[QC<id>]`, `[TAR<id>]`

The quest name is rendered as a `*Name*:` italic prefix in front of the
tag:
- Solo: `*Name*: [QA<id>]`
- Combined QT+QA: `*Name1 -> Name2*: [QT<id1>] (+rep)[QA<id2>]`

GuideLime resolves quest and NPC names from its own DB at runtime. The
italic prefix keeps the source readable.

### Pre-commit check

```sh
grep -nE '\[Q[ATC]\d+\s+\w' addons/Guidelime_*/Guidelime_*.lua
grep -nE '\[TAR\d+\s+\w' addons/Guidelime_*/Guidelime_*.lua
```

Both must return zero hits — any hit means a tag carries a name in its
body again.

---

## 12. Empty sub-guides in WoW are usually completed-quest-hiding

A small sub-guide (Barrens, Hinterlands, Thousand Needles cleanup,
Ashenvale cleanup, etc.) sometimes appears empty in-game.

### Diagnosis

The addon's own `QUALITY_REPORT.md` (next to its `.lua`) shows whether
steps were actually emitted. If the report has `>0` steps but the
sub-guide is empty in-game:

- Quest already completed by the character — GuideLime hides finished
  quests.
- Race/class restriction hides the steps for that character.
- Prerequisite not satisfied — GuideLime hides steps whose start cannot
  yet happen.

This is GuideLime behaviour, not a generator bug. The quality report is
the ground truth for "what we emitted".

---

## 13. Pathing efficiency tracking

`_quality_report.md` (slim global, written by `--all`) ships the same
headline KPIs in its `## Snapshot` section that previous releases
had. For larger routing or bucketing changes:

1. Save a copy of the current `_quality_report.md` as a baseline.
2. Make the change, run `python3 create.py --all`.
3. Compare the headline KPIs of the new report with the baseline. The
   diff snippet below extracts them.

For a single-faction iteration (e.g. `--faction sporeggar`), the
addon's own `QUALITY_REPORT.md` carries the same KPIs scoped to that
one faction — the same diff trick works, just point it at the
addon-specific file.

The KPIs that matter most: `Global ø Score`, `Global Efficiency`,
`Total Distance`, `X-Jumps`, `Absorption Rate`. The cluster constants
mostly affect absorption — actual distance reductions come from the
alternating 2-opt + or-opt refinement passes (`routing/two_opt.py`
and `routing/or_opt.py`, alternated by `routing/tour.py`).

### Diff snippet

```python
import re

def extract(path):
    """Works for both the slim global (`Global ø Score`, `Total
    Distance`, etc.) and per-addon files (`ø Score`, `Distance`, ...) —
    the optional `Global ` / `Total ` prefixes make the regex match
    either layout."""
    out = {}
    for line in open(path, encoding='utf-8'):
        for k, pat in [
            ('Score', r'- \*\*(?:Global )?ø Score\*\*: ([\d.]+)'),
            ('Eff',   r'- \*\*(?:Global )?Efficiency\*\*: ([\d.]+)'),
            ('Dist',  r'- \*\*(?:Total )?Distance \(Normal\)\*\*: ([\d.]+)'),
            ('Jumps', r'- \*\*(?:Total )?X-Jumps \(Normal\)\*\*: (\d+)'),
            ('Absorp', r'- \*\*Absorption Rate \(Normal\)\*\*: ([\d.]+)%'),
            ('Lost',  r'- \*\*Lost Quests\*\*: (\d+)'),
        ]:
            m = re.match(pat, line)
            if m:
                out[k] = float(m.group(1))
    return out

b = extract('/tmp/baseline.md')
t = extract('_quality_report.md')
for k in b:
    print(f'{k:<7} {b[k]:>10.2f} -> {t[k]:>10.2f}  diff={t[k]-b[k]:+.2f}')
```

### Constants sensitivity (from earlier experiments)

- `CLUSTER_RADIUS` (default in `routing/tour.py`, override per zone via
  `ZONE_CLUSTER_RADIUS`): mostly changes absorption rate. Tests at 5/8/12
  yielded scores 68.4/69.3/70.4. R=12 is the sweet spot for dense zones;
  larger values mix city and field stops.
- `ZONE_CLUSTER_RADIUS`: only useful for sparse zones (raise it). Going
  below the default for dense zones makes things worse — only tune up.
- `DETOUR_THRESHOLD`: **dead knob** — sweep 4/6/8/10/12 produces
  identical KPIs (cluster discovery already absorbs anything closer
  than `CLUSTER_RADIUS=12`, and the absorption corridor is too narrow
  beyond that for the threshold to matter). Leave at 6.
- `JUMP_PENALTY` (`routing/two_opt.py`): tuning is a real trade-off,
  not a free win. JP=30 lowers distance by ~3.7% but raises X-Jumps by
  ~10%, which is more painful for the player than the score reflects.
  JP=60+ flips the trade the other way and converges by 75. JP=45
  remains the production value.
- Path distance `N-Dist` does not move much for cluster/detour tuning —
  the stops are the stops, just labelled differently. Real distance
  reductions need an algorithmic change like the 2-opt + or-opt
  refinement loop.

### Per-zone radius from data

Snippet to derive `ZONE_CLUSTER_RADIUS` empirically when a new faction
or zone is added:

```python
import math
from collections import defaultdict

# zone_stops: dict[zone_id, list[(x, y)]]
for zid, pts in zone_stops.items():
    if len(pts) < 2:
        continue
    nn = []
    for i, p in enumerate(pts):
        d_min = min(
            math.hypot(p[0]-q[0], p[1]-q[1])
            for j, q in enumerate(pts) if i != j
        )
        nn.append(d_min)
    nn.sort()
    p75 = nn[3 * len(nn) // 4]
    radius = max(12, min(25, p75 * 1.5))  # only use values > 12
    print(f'{zid}: {radius:.1f}')
```

Add the result to `ZONE_CLUSTER_RADIUS` only for zones where the
recommended radius is above 12.

---

## 14. Pathing experiments

The current production path is "greedy + alternating 2-opt/or-opt with
spawn-anchored start, JP=45". Several other ideas were tried; some
landed, several were dropped. Read this before re-implementing one of
the dropped ones.

### What landed

| Change | Score delta | Notes |
|---|---:|---|
| Spawn anchor (lowest-level quest's pickup) for natural-tier sub-guides only | +0.2 | v1.2.0; cleanup buckets stay unanchored — anchoring them regressed dense-cluster sub-guides like Argent Dawn |
| Or-opt refinement (segments of length 1..4) alternated with 2-opt | +0.5 | v1.3.0; the two heuristics unlock each other's moves |
| Convergence-based early exit on the alternation loop | 0 effect on quality, ~30% runtime saved | v1.3.0; bails as soon as a full round leaves cost unchanged |
| Two-phase sub-guide layout — natural-tier first, then cleanup | 0 effect on score (same content), UX clarity | v1.3.1; cleanup buckets stop being interleaved by quest level into the natural-tour sequence |

### What was dropped

| Change | Solo effect | Verdict |
|---|---:|---|
| smart-start-stop (centroid / highest-degree) | -0.2 / -0.1 | The default first-feasible already starts well |
| cluster-lookahead (tie-break by unlocked successors) | 0.0 | Too few ties for it to matter |
| adaptive cluster-type radius (NPC vs mob) | 0.0 | NPC-vs-mob differentiation does not move the score |
| complex-reclassify (promote short complex chains back to normal) | -0.5 | Promoted quests in battleground zones get lost; +50 % jumps |
| spawn-anchor for **all** sub-guides incl. cleanup | -0.0 globally, but Argent Dawn fell from 91 to 84 | Cleanup is not a "first arrival" — kept anchor for natural only |
| followup-aware absorption (extra detour budget if quest's next stop is near target) | -0.0 to -1.0 depending on knobs | Absorption corridor too narrow for the signal to help; aggressive bonuses fragmented clusters |
| `JUMP_PENALTY` tuning | -0.0 to +0.1 | Distance gain at low JP comes at the cost of more X-Jumps; not a clear win |
| or-opt segment length k=5 | -0.0 (regresses vs k=4) | Longer segments are too rigid for precedence-bound chains |
| unlocking-power tie-break (prefer candidates whose quest unlocks more downstream work) | 0.0 score, +0.5% distance, -2.1% jumps | Mixed; the precedence check already prevents bad orderings, the tie-break only shifts equally-valid picks |
| multi-restart (build tour from 2-3 anchor candidates, keep cheapest) | -0.1 score, -1.2% distance, +50% runtime | Distance win is small and the runtime hit is real |

If you have a new heuristic, by all means test it — but do the
comparison properly with the diff snippet above, and check Argent Dawn
specifically: extremely dense clusters expose anchor and absorption
trade-offs the global aggregate hides.

---

## 15. General defence strategy

1. **Sanitise at the output edge, not at the input edge.** Leave the
   raw quest names untouched in the DB; channel them through
   `_safe_text` / `_safe_tag_content` only when emitted.
2. **Before each release, run the regex sweeps** from sections 1, 2, 8
   and 11 over `addons/*/Guidelime_*.lua`.
3. **When adding a new emit site, never interpolate `q[...]` straight**
   into a Lua string — go through one of the helpers.
4. **Prefer a small consistency-check pass over clever logic.** The
   chain coalescing in `zones.py` is the textbook example: a simple
   fixpoint loop is more robust than trying to bucket "correctly" the
   first time.
