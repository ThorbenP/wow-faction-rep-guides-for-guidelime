# Routing Experiments — v1.4.0 rep/dist baseline

Snapshot of the seven feature-experiment branches re-benchmarked
under the v1.4.0 metric (rep / map unit). The composite-score numbers
recorded earlier on each branch are no longer directly comparable;
this file is the authoritative table for "what does this branch buy
us, on the metric we now care about?".

## Baseline (v1.4.0 main, greedy)

- **Global Rep/Dist**: 16.04 rep / map unit
- **Total Distance (Normal)**: 40022 map units
- **Total X-Jumps (Normal)**: 419
- **Absorption Rate (Normal)**: 67.5%
- **Bulk-run runtime**: ~17 s

## Per-branch results

| Branch | Rep/Dist | Δ rep/dist | Distance | Δ% dist | Jumps | Absorp | Runtime | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `feat/cluster-defrag` | 16.04 | 0.00 | 40022 | 0% | 419 | 79.8% | ~17s | **cosmetic** — no distance change, only re-labels travels as cluster members |
| `feat/held-karp-small` | 16.11 | +0.07 | 39836 | -0.5% | 420 | 67.5% | ~17s | small win on tiny sub-guides; provably-optimal where it applies (≤12 entries) |
| `feat/three-opt` | 16.08 | +0.04 | 39906 | -0.3% | 414 | 67.5% | 2m38s | marginal, expensive (≈9× runtime) |
| `feat/stop-level-2opt` | 16.05 | +0.01 | 39978 | -0.1% | 419 | 70.5% | 20s | almost null; branch's score-aligned acceptance fights the new metric |
| `feat/simulated-annealing` | 16.10 | +0.06 | 39862 | -0.4% | 419 | 67.5% | 33s | small but real distance gain — invisible under v1.3.x score because the composite did not reflect 0.4% distance |
| `feat/random-insertion` | 15.79 | -0.25 | 40652 | +1.6% | 413 | 57.8% | 35s | regresses; cheapest-insertion fragments same-coord stops |
| `feat/multistart-routing` (greedy mode) | 16.04 | 0.00 | 40022 | 0% | 419 | 76.5% | 20s | greedy mode of branch ≡ greedy + defrag; cosmetic only |
| `feat/multistart-routing` (multistart) | **16.55** | **+0.51** | **38788** | **-3.1%** | 428 | 81.9% | 7m9s | **largest single-branch win**; K=64 randomized rebuilds beat the greedy local optimum |

## Insights from the new metric

1. **Total rep is fixed by the input.** `rep / dist` therefore
   collapses to `constant / dist` per sub-guide — minimising
   distance is the *only* lever the routing has on the headline KPI.
   Score-aligned acceptance schemes added on the v1.3.x branches
   (multistart, stop-level-2opt) optimise something else and may
   *underperform* a simple `_tour_cost` (`distance + JUMP_PENALTY ×
   jumps`) acceptance against rep/dist.
2. **Defrag had no impact.** v1.3.x's composite gave it +1.6 score
   because absorption carried 15% weight. Under rep/dist there is no
   such weight. Keeping defrag is a *presentation* choice, not a
   routing improvement.
3. **3-opt and Held-Karp matter more than expected.** Small but real
   distance reductions (-0.3% / -0.5%) directly translate to rep/dist
   gains. They are honest contributions.
4. **Multistart is the dominant lever.** -3.1% distance, +3.2% on the
   headline. The runtime cost is steep but for an archive-quality
   regeneration it is acceptable.
5. **Ranking under rep/dist (best -> worst on the headline metric):**
   multistart >> SA ≈ HK > 3-opt > stop-level ≈ defrag (no effect) >
   random-insertion (regresses).

## Implications for next round of experiments

- Re-run multistart with raw `_tour_cost` acceptance instead of
  score-aligned: the new metric may favour pure distance-min, and
  the score-aligned variant could be leaving distance on the table.
- Add a *double-bridge* move to ILS: classic escape from 2-opt local
  optima that pure segment-reversal cannot leave.
- Re-assemble a "combined-best" branch under v1.4.0:
  HK + 3-opt-cap + multistart-cost-aligned, see how the wins
  compose.

These follow up as `feat/multistart-cost-aligned`,
`feat/double-bridge-ils`, `feat/combined-best-v2`.
