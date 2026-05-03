"""Brute-force pathing enumerator for a single sub-guide.

The normal pipeline (`guides_generator/routing/`) builds ONE good tour with
greedy + multistart + 2-opt/or-opt/3-opt/Held-Karp. This package does the
opposite: it enumerates every feasible permutation of the sub-guide's stops,
writes each one to a JSONL file, and reports the best rep/distance found.

It is deliberately not an optimisation algorithm — runtime is exponential
in the number of stops, and the user has accepted that. Use it on small
sub-guides only; the existing pipeline remains the practical solver.
"""
from .dataset import SubGuide, list_subguides, load_subguide
from .dfs import enumerate_subguide
from .heldkarp import solve_heldkarp
from .ortools_solver import solve_ortools

__all__ = [
    'SubGuide', 'enumerate_subguide', 'list_subguides', 'load_subguide',
    'solve_heldkarp', 'solve_ortools',
]
