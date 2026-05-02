# Routing Experiments — History

This file is the documentation trail of the routing experiments run
against the v1.4.0 rep/dist baseline. **The optimisations the
production pipeline now uses by default were promoted to `main` in
v1.5.0**; the experiment branches stay on GitHub as historical
artefacts but their measurements are the ones you read off this
table.

## What v1.5.0 ships by default

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
