# Routing Experiments — v1.4.0 rep/dist baseline

Authoritative table of every routing experiment branch measured under
the v1.4.0 metric (rep / map unit). Composite-score numbers from
v1.3.x commit messages are no longer comparable.

## Baseline (v1.4.0 main, greedy)

- **Global Rep/Dist**: 16.04 rep / map unit
- **Total Distance**: 40022 map units
- **Total X-Jumps**: 419
- **Bulk runtime**: ~17 s

## Pre-v1.4.0 branches (rebased onto v1.4.0 main)

| Branch | Rep/Dist | Δ | Distance | Δ% | Notes |
|---|---:|---:|---:|---:|---|
| `feat/cluster-defrag` | 16.04 | 0.00 | 40022 | 0% | cosmetic — no distance change |
| `feat/held-karp-small` | 16.11 | +0.07 | 39836 | -0.5% | DP optimum for ≤12-entry sub-guides |
| `feat/three-opt` | 16.08 | +0.04 | 39906 | -0.3% | runtime ≈9× |
| `feat/stop-level-2opt` | 16.05 | +0.01 | 39978 | -0.1% | branch's old score-aligned acceptance fights the new metric |
| `feat/simulated-annealing` | 16.10 | +0.06 | 39862 | -0.4% | small distance gain — visible only under rep/dist |
| `feat/random-insertion` | 15.79 | -0.25 | 40652 | +1.6% | regresses; cheapest-insertion fragments same-coord stops |
| `feat/multistart-routing` (multistart) | 16.55 | +0.51 | 38788 | -3.1% | K=64 randomized rebuilds. Score-aligned acceptance. |

## Post-v1.4.0 experiments

| Branch | Mode | Rep/Dist | Δ vs main | Distance | Δ% | Runtime | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| `feat/multistart-cost-aligned` | multistart | 16.65 | +0.61 | 38550 | -3.7% | 6m36s | cost-aligned beats score-aligned by +0.10. -8 jumps. |
| `feat/double-bridge-ils` | multistart | 16.67 | +0.63 | 38502 | -3.8% | 6m41s | adds Lin-Kernighan-style 4-edge perturbation. +0.02 marginal. |
| `feat/combined-best-v2` | greedy | 16.08 | +0.04 | 39911 | -0.3% | 28s | HK + 3-opt(≤50) + defrag in greedy refinement. |
| `feat/combined-best-v2` | multistart | 16.66 | +0.62 | 38532 | -3.7% | 6m55s | combined chain. +0.01 vs cost-aligned alone. |
| `feat/larger-or-opt` | greedy | 16.03 | -0.01 | 40044 | +0.05% | 16s | k=1..6. Tiny regression — search diverts. |
| `feat/combined-stop-level-finish` | greedy | 16.19 | +0.15 | 39632 | -1.0% | 34s | adds stop-level 2-opt finish. |
| `feat/combined-stop-level-finish` | multistart | 16.74 | +0.70 | 38341 | -4.2% | 7m50s | stop-level 2-opt finds moves 3-opt+HK miss. |
| `feat/stop-level-or-opt-finish` | greedy | 16.26 | +0.22 | 39470 | -1.4% | 38s | adds stop-level or-opt to combined-stop-level. **best greedy** |
| **`feat/stop-level-or-opt-finish`** | **multistart** | **16.78** | **+0.74** | **38251** | **-4.4%** | 8m7s | **OVERALL BEST**. Stop-level or-opt + 2-opt finish on multistart winner. |

## Key findings under rep/dist

1. **Total rep is fixed by the input**, so `rep/dist = const/dist`.
   Maximising rep/dist ≡ minimising `_tour_cost` (distance +
   JUMP_PENALTY × jumps). Score-aligned acceptance schemes carried
   over from v1.3.x optimise the wrong objective and underperform.

2. **Defrag is cosmetic.** The +12 percentage-point absorption it
   produced under v1.3.x score is now correctly worth zero — the
   tour visits the same stops at the same coords, only the cluster
   labelling differs.

3. **Multistart is the dominant lever.** K=64 randomized rebuilds
   with cost-aligned acceptance gives +3.7% distance reduction
   (16.04 → 16.65). Every other technique builds on this.

4. **Stop-level moves outperform entry-level past multistart.**
   3-opt + Held-Karp at the entry level cannot break clusters; once
   multistart finds a good entry-level basin, stop-level 2-opt and
   or-opt reach a strictly smaller-distance optimum (16.66 → 16.78).

5. **Diminishing returns kick in fast.** The ceiling under
   reasonable runtime sits around 16.78 (+4.6% over baseline). Each
   technique past multistart adds 0.02-0.10 rep/dist; each costs ~1
   minute of bulk runtime.

## What did *not* work

- Larger or-opt segments (k=5,6): tiny regression — more candidates
  divert the alternating search.
- Random-insertion construction: regresses by -1.6% distance.
- Pure simulated annealing on top of converged 2-opt: no change.
- Adding 3-opt + HK to the multistart winner *after* cost-aligned
  selection: ≤+0.01 rep/dist — multistart already drives candidates
  close enough to the local optimum.

## Recommended adoption

If you want a single drop-in: **`feat/stop-level-or-opt-finish`**.
- Greedy mode (`--method greedy`, default): +1.4% over baseline,
  ~38s bulk runtime.
- Multistart mode (`--method multistart`): +4.4% over baseline,
  ~8m bulk runtime — appropriate for archive-quality regenerations.

If you want only the free wins without runtime cost:
**`feat/held-karp-small`** alone (+0.4%, no bulk-runtime overhead).

The `_tour_cost`-aligned objective on multistart and ILS finishers
is the prerequisite for everything past that. Score-aligned variants
are obsolete under rep/dist.
