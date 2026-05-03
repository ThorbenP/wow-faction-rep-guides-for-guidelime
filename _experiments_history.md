# Routing Experiments — History

This file is the documentation trail of the routing experiments run
against the v1.4.0 rep/dist baseline. **The optimisations the
production pipeline now uses by default were promoted to `main` in
v1.5.0**; the experiment branches stay on GitHub as historical
artefacts but their measurements are the ones you read off this
table.

## What v1.5.x ships by default

> v1.5.0 introduced the chain below. v1.5.1 parallelised the K
> candidates via `multiprocessing.Pool` and bumped K from 64 to 96
> (compensates for a small parallel tie-breaking variance). The
> chain itself and the rep/dist headline are unchanged at 16.78–16.79;
> only the bulk wallclock dropped from ~7 min to ~2.5 min.

The production routing chain (always-on, no flags) is:

  1. Greedy build with cluster discovery + on-the-way absorption.
  2. K=64 randomized multistart rebuilds with cost-aligned acceptance.
  3. ILS escape (segment-reverse + Lin-Kernighan-style double-bridge).
  4. Deep refinement on the multistart winner: 2-opt + or-opt
     convergence, 3-opt for tours with ≤50 entries, defrag, Held-Karp
     DP for tours with ≤12 entries, stop-level 2-opt finisher,
     stop-level or-opt finisher.

This combines every productive technique from the table below.
Everything labelled "tried, dropped" or "marginal" is **not** in the
production code; the GitHub branches remain for context but are not
maintained.

## Baseline (pre-v1.5.0 main, greedy + 2-opt + or-opt only)

- **Global Rep/Dist**: 16.04 rep / map unit
- **Total Distance**: 40022 map units
- **Total X-Jumps**: 419
- **Bulk runtime**: ~17 s

## Pre-v1.4.0 branches (rebased onto v1.4.0 main, then re-measured)

| Branch | Rep/Dist | Δ | Distance | Δ% | Notes |
|---|---:|---:|---:|---:|---|
| `feat/cluster-defrag` | 16.04 | 0.00 | 40022 | 0% | cosmetic — no distance change |
| `feat/held-karp-small` | 16.11 | +0.07 | 39836 | -0.5% | DP optimum for ≤12-entry sub-guides; **adopted in v1.5.0** |
| `feat/three-opt` | 16.08 | +0.04 | 39906 | -0.3% | runtime ≈9× standalone, but **adopted in v1.5.0** under a 50-entry cap where it pays |
| `feat/stop-level-2opt` | 16.05 | +0.01 | 39978 | -0.1% | branch's score-aligned acceptance fights the new metric — replaced by cost-aligned variant in v1.5.0 |
| `feat/simulated-annealing` | 16.10 | +0.06 | 39862 | -0.4% | small distance gain visible only under rep/dist; **dropped** — adds runtime without pulling its weight once multistart is in |
| `feat/random-insertion` | 15.79 | -0.25 | 40652 | +1.6% | **dropped** — regresses; cheapest-insertion fragments same-coord stops |
| `feat/multistart-routing` (multistart) | 16.55 | +0.51 | 38788 | -3.1% | K=64 randomized rebuilds; score-aligned acceptance. Superseded by cost-aligned multistart in v1.5.0. |

## Post-v1.4.0 experiments

| Branch | Mode | Rep/Dist | Δ vs main | Distance | Δ% | Runtime | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| `feat/multistart-cost-aligned` | multistart | 16.65 | +0.61 | 38550 | -3.7% | 6m36s | cost-aligned beats score-aligned by +0.10. **adopted in v1.5.0** |
| `feat/double-bridge-ils` | multistart | 16.67 | +0.63 | 38502 | -3.8% | 6m41s | Lin-Kernighan-style 4-edge perturbation. **adopted in v1.5.0** |
| `feat/combined-best-v2` | multistart | 16.66 | +0.62 | 38532 | -3.7% | 6m55s | combined chain — folded into v1.5.0 |
| `feat/larger-or-opt` | greedy | 16.03 | -0.01 | 40044 | +0.05% | 16s | k=1..6. **dropped** — tiny regression; the alternating search diverts |
| `feat/combined-stop-level-finish` | multistart | 16.74 | +0.70 | 38341 | -4.2% | 7m50s | stop-level 2-opt finds moves 3-opt+HK miss. **adopted in v1.5.0** |
| **`feat/stop-level-or-opt-finish`** | **multistart** | **16.78** | **+0.74** | **38251** | **-4.4%** | 8m7s | **promoted to main in v1.5.0** |

## Post-v1.6.x experiments

| Change | Rep/Dist | Notes |
|---|---:|---|
| stop-level Held-Karp DP for sub-guides ≤30 stops, plus `compute_tour_stats` `start_pos` reporting fix | 16.63 | adopted on `main`. The DP rebuilds the optimal stop ordering via precedence-pruned sparse bitmask states (typically a few hundred to a few thousand reachable states even at the cap). The reporting fix counts the spawn-to-first-stop edge that the previous `compute_tour_stats(tour)` call dropped — this *lowers* the reported global rep/dist by ~0.15 because all the previous numbers were missing one edge per sub-guide, while the DP raises it by recovering the true optimum on every bucket up to 30 stops. Net 16.78 → 16.63. The number is smaller; the underlying tours are at least as short and provably-optimal where the cap fires. |
| **multi-anchor start (try all min-level pickups, keep cheapest tour)** | **16.90** | adopted on `main`. `pick_start_position` previously broke level ties by quest ID — that often lands on an interior NPC. Building a tour for each distinct min-level pickup coord (capped at 4 candidates) and keeping the cheapest under `compute_tour_stats(tour, start_pos)` reveals that an "outlier" starter is worth +14 to +18% rep/dist on dense city sub-guides (Stormwind City: 18.91 → 21.63, Dustwallow Marsh: 17.20 → 20.32). Most sub-guides have 1-2 candidates and land on the same tour, so the global gain is +1.6% (16.63 → 16.90), front-loaded into a handful of city + outdoor-hub buckets. Runtime cost is k× the multistart pipeline for the candidate sub-guides — ~2-3× total `--all` runtime (`--all` now ~10-12 min vs ~8 min). Cleanup-tier sub-guides skip the search since they have no spawn anchor by design. |
| **multi-anchor start: widen pool to `min_level + 2`, raise cap to 6 (v1.7.2)** | **17.08** | adopted on `main`. The strict-min-level filter blocked level+1 and level+2 pickups that were sometimes the better spawn anchor — geographically outlying quests whose visit-first amortises the trip across the whole cluster. Widening to `LEVEL_TOLERANCE = 2` and bumping `MAX_START_CANDIDATES` from 4 to 6 surfaces those candidates without runtime regression. Global gain: 16.90 → 17.08 (+1.1 %). No faction regresses — 7 of 30 factions improve >0.5%, biggest are Darnassus +3.4%, Exodar +2.5%, Lower City +2.3%, Stormwind +2.0%. Total normal distance 37969 → 37582 (-1.0 %), x-jumps unchanged at 414 → 417. |
| quest-sharing detection (off-tree experiment) | n/a | hypothesis: when two QC stops share mob/object objectives, the player completes both with one trip — but today's solver counts them as separate stops. Surveyed every faction × sub-guide for QC-stop pairs with overlapping `obj_creatures` AND distinct objective centroids (`0 < dist < 5`). Found **zero candidates**: when two quests share an objective creature, `compute_objective_centroid` deterministically resolves them to the same coord, which the cluster discovery already merges into a single zero-distance entry. Quest-sharing is therefore already implicitly handled by the centroid model — no production change needed. |
| OR-Tools CP-SAT refinement (off-tree experiment) | n/a | external solver gave +1–4% on sub-guides >30 stops via a hint = existing tour, but only as `FEASIBLE` within a 20-min time budget per bucket. Not worth the extra dependency + ~17h `--all` runtime for the small marginal gain — the heuristic chain is already close to the bound. Kept as a documented option, not in production. |
| stop-level Held-Karp cap raised 30 → 35 | 16.91 (+0.01) | tried, **dropped**. Sub-guides between 31 and 35 stops are rare and the heuristic chain already lands close to the optimum — the global gain is within rounding. Not worth the larger reachable-state set or the runtime variance at the new cap. |
| `JUMP_PENALTY` lowered 45 → 30 | 18.12 (looks +7.2 %) | tried, **dropped — metric artefact**. Reported global rep/dist jumps from 16.90 to 18.12, but only because the report counts cross-zone edges as zero distance. Total distance shrinks 37969 → 35424 (-6.7 %) at the cost of 414 → 487 jumps (+18 %). Real-world cost (`dist + 45 × jumps`, with the production penalty) is 56599 → 57339, **1.3 % worse** than baseline. The "improvement" is the solver buying cheap zero-cost report distance with extra flightpath time the player actually pays. JP=45 is the right operating point, the empirical calibration in `routing/two_opt.py` stands. |

## Key findings under rep/dist

1. **Total rep is fixed by the input**, so `rep/dist = const/dist`.
   Maximising rep/dist ≡ minimising `_tour_cost` (distance +
   JUMP_PENALTY × jumps). Score-aligned acceptance schemes carried
   over from v1.3.x optimise the wrong objective and underperform.

2. **Defrag is cosmetic.** The +12 percentage-point absorption it
   produced under v1.3.x score is now correctly worth zero — the
   tour visits the same stops at the same coords, only the cluster
   labelling differs. (v1.5.0 still runs defrag because the tighter
   Lua emission is nice; the headline metric is unaffected.)

3. **Multistart is the dominant lever.** K=64 randomized rebuilds
   with cost-aligned acceptance gives +3.7% distance reduction
   (16.04 → 16.65). Every other technique builds on this.

4. **Stop-level moves outperform entry-level past multistart.**
   3-opt + Held-Karp at the entry level cannot break clusters; once
   multistart finds a good entry-level basin, stop-level 2-opt and
   or-opt reach a strictly smaller-distance optimum (16.66 → 16.78).

5. **Diminishing returns kick in fast.** The ceiling under
   reasonable runtime sits around 16.78 (+4.6% over baseline). Each
   technique past multistart adds 0.02-0.10 rep/dist.

## What did *not* work and was dropped

- **Larger or-opt segments** (k=5,6): tiny regression — more
  candidates divert the alternating 2-opt/or-opt search into
  slightly worse local optima.
- **Random-insertion construction**: regresses by -1.6% distance.
  Cheapest-insertion places same-coord stops at different cheapest
  positions; refinement cannot recover the cluster grouping greedy
  produces for free.
- **Pure simulated annealing** on top of converged 2-opt with the
  segment-reverse kernel: zero change. The convergent 2-opt has
  already explored every reachable reversal, so a temperature-driven
  random-walk over the same move space cannot escape.
- **Adding 3-opt + HK to the multistart winner *only*** (without the
  stop-level finishers): ≤+0.01 rep/dist on top of multistart alone
  — the candidate already lands close enough to the local optimum
  that 3-opt cannot improve it. 3-opt earns its keep further upstream
  in the chain (small standalone win on the deterministic baseline,
  picked up by v1.5.0 under the ≤50-entry cap).

## Reproducing measurements

Each branch is checkout-and-run-able. The pre-v1.4.0 ones were
merged with `main` so they land on the v1.4.0 score formula; the
post-v1.4.0 ones were forked from v1.4.0 main to begin with:

```
git checkout feat/<name>
python3 create.py --all          # bench (some branches need --method, see commit msg)
grep "Global Rep/Dist" _quality_report.md
```

The v1.5.0 production code on `main` reproduces 16.78 rep/dist with
no flags — the same number as `feat/stop-level-or-opt-finish` with
`--method multistart`.
