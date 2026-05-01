"""Quest-chain detection and topological sort over pre/preg/next edges."""
from __future__ import annotations

from collections import defaultdict


def topo_sort(quests: list[dict]) -> list[dict]:
    """Order quests so that prerequisites come before their successors.

    Pre-sorted by level (then id) to make the topological traversal stable —
    shorter chains and lower-level quests appear first when there are no
    dependencies between them.
    """
    by_id = {q['id']: q for q in quests}
    visited: set[int] = set()
    out: list[dict] = []

    def visit(q: dict) -> None:
        if q['id'] in visited:
            return
        for fld in ('pre', 'preg'):
            pre = q.get(fld)
            if not pre:
                continue
            pre_list = (
                [pre] if isinstance(pre, int)
                else list(pre.values()) if isinstance(pre, dict)
                else pre
            )
            for pid in pre_list:
                if pid in by_id:
                    visit(by_id[pid])
        visited.add(q['id'])
        out.append(q)

    for q in sorted(quests, key=lambda x: (x.get('level') or 99, x['id'])):
        visit(q)
    return out


def find_chains(quests: list[dict]) -> tuple[list[list[dict]], list[dict]]:
    """Group quests into connected components via pre/preg/next edges.

    Operates only on quests in the given list — quests whose chain neighbours
    are outside the list are treated as singletons. Returns (chains,
    singletons) where every chain is topologically sorted.
    """
    by_id = {q['id']: q for q in quests}
    if not by_id:
        return [], []

    adj: dict[int, set[int]] = defaultdict(set)
    for q in quests:
        qid = q['id']
        for fld in ('pre', 'preg'):
            pre = q.get(fld) or []
            if isinstance(pre, int):
                pre = [pre]
            elif isinstance(pre, dict):
                pre = list(pre.values())
            for pid in pre:
                if pid in by_id:
                    adj[qid].add(pid)
                    adj[pid].add(qid)
        nxt = q.get('next')
        if nxt and nxt in by_id:
            adj[qid].add(nxt)
            adj[nxt].add(qid)

    seen: set[int] = set()
    chains: list[list[dict]] = []
    singletons: list[dict] = []

    for q in quests:
        qid = q['id']
        if qid in seen:
            continue
        if not adj[qid]:
            seen.add(qid)
            singletons.append(q)
            continue
        comp_ids: list[int] = []
        queue = [qid]
        while queue:
            cur = queue.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp_ids.append(cur)
            for n in adj[cur]:
                if n not in seen:
                    queue.append(n)
        if len(comp_ids) <= 1:
            singletons.append(by_id[comp_ids[0]])
        else:
            chains.append(topo_sort([by_id[i] for i in comp_ids]))

    return chains, singletons
