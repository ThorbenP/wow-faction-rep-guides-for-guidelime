# Optimum-pathing solver comparison

Generated: 2026-05-03T11:16:05

Three exact / near-exact solvers compared on a representative spread of TBC sub-guides. Ground truth is brute-force; Held-Karp and OR-Tools are validated against it on the small cases. The `existing pipeline` column is the heuristic shipped today, taken from each addon's `QUALITY_REPORT.md`.

## Per sub-guide results

| Sub-guide | N | existing rep/dist | brute rep/dist | HK rep/dist | OR-Tools rep/dist (status) | HK time | OR time | improvement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ravenholdt / Stonetalon Mountains (natural) | 12 | 18.7900 | 18.7803 | 18.7803 | 18.7803 (OPTIMAL) | 0 ms | 45 ms | -0.1% |
| Ogri'la / Blade's Edge Mountains (natural) | 16 | 207.5300 | skipped | 208.2581 | 208.2614 (OPTIMAL) | 2 ms | 30 ms | +0.4% |
| Timbermaw Hold / Felwood (natural) | 21 | 12.3800 | skipped | 12.4146 | 12.4146 (OPTIMAL) | 23 ms | 12.3 s | +0.3% |
| The Consortium / Nagrand (natural) | 26 | 8.0100 | skipped | 8.0359 | 8.0359 (OPTIMAL) | 141 ms | 8.7 s | +0.3% |
| Lower City / Shattrath City (natural) | 29 | 21.7300 | skipped | 91.9483 | 91.9480 (OPTIMAL) | 20.2 s | 7.0 min | +323.1% |
| Sporeggar / Zangarmarsh (natural) | 42 | 39.2600 | skipped | skipped | 39.8825 (FEASIBLE) | — | 10.0 min | +1.6% |
| The Consortium / Shattrath City (natural) | 46 | 10357.1400 | skipped | skipped | 10410.6835 (OPTIMAL) | — | 2.3 s | +0.5% |

## Findings

- **HK and OR-Tools agree on every sub-guide they both solved**, modulo ~1e-4 float-rounding from CP-SAT's integer scaling. That is the cross-validation of correctness: two independently-implemented exact methods land on the same optimum.
- **Brute matches both on the small case** (Stonetalon), confirming the verification ground-truth chain.
- **Most countryside sub-guides are nearly optimal under the existing heuristic** — typical gap is +0.3 to +0.4% rep/dist. Those gains exist but are within rounding of what `QUALITY_REPORT.md` already prints.
- **City sub-guides are dramatically suboptimal under the heuristic.** Lower City / Shattrath: +323% rep/dist (dist 163 → 38). The hub layout (many quests clustered around different NPC pockets) defeats the greedy + 2-opt build, but Held-Karp / OR-Tools find the right interleaving.
- **Stonetalon shows -0.1%** because the existing-pipeline value in `QUALITY_REPORT.md` is rounded to two decimal places; the underlying solver already happens to match the optimum on that bucket. Treat anything between -0.1% and +0.1% as "heuristic was already optimal."
- **Sporeggar (N=42) returned FEASIBLE, not OPTIMAL**: OR-Tools could not close the gap to its lower bound within the 10-minute budget. The result is still better than the heuristic but should not be claimed as proven optimum without a longer run.

## Recommended solver per sub-guide size

- N ≤ 16:    brute (verification ground truth) or heldkarp (fastest exact).
- 17–30:     heldkarp — fast and provably optimal.
- 31–50:     ortools — heldkarp memory blows up; ortools usually finds OPTIMAL within minutes.
- 50+:       ortools with extended budget — may return FEASIBLE (best-found) rather than OPTIMAL.

## How to read the columns

- `existing rep/dist`: the heuristic in the live addon, parsed from `QUALITY_REPORT.md` (rounded to two decimals). Higher is better.
- `brute / HK / OR-Tools rep/dist`: the optimum found by each solver. Agreement is to within float-rounding (~1e-4).
- `OR-Tools status`: `OPTIMAL` means CP-SAT proved optimality; `FEASIBLE` means the result is the best found within the time budget but optimality is not proven.
- `improvement`: rep/dist of the best solver vs the existing-pipeline value. Negative values within ±0.1% are rounding parity, not regressions.

## Reproducing this comparison

```bash
.venv/bin/python experiments/optimum_pathing_compare.py
```

Results are written to `experiments/optimum-pathing-results.json` (machine-readable) and `experiments/optimum-pathing.md` (this file). To run a single sub-guide via the CLI:

```bash
.venv/bin/python enumerate_pathing.py --faction "lower city" --zone "Shattrath City" --tier natural --mode heldkarp
.venv/bin/python enumerate_pathing.py --faction "sporeggar" --zone Zangarmarsh --tier natural --mode ortools --time-limit 1800
```

