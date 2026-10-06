"""Literal replay checks when endpoint-query emptiness differs from family emptiness.

No resource module, external data, or coordinate span beyond four is needed.
The empty final set is an admissible endpoint in one arm; in the other arm the
same cardinality request is infeasible. Source prefixes exist only in the first.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from driftcert import (Contract, Instance, Reject, Segment, check_prefix,
                       check_prefix_shortest, materialize_prefix_witness,
                       produce_prefix, shortest_prefix_bisection)


def run() -> dict:
    cases = active_queries = expanded_witnesses = rejected_empty_markers = 0
    for u in range(1, 5):
        for mask in range(1 << u):
            source = tuple(x for x in range(u) if mask & (1 << x))
            # Single-coordinate pieces also test segments with no source key.
            for slope, intercept, denominator in ((0, 0, 1), (-2, -1, 3)):
                segments = tuple(Segment(x, x, slope, intercept, denominator)
                                 for x in range(u))
                for feasible in (True, False):
                    if not feasible and not source:
                        continue  # Empty source -> empty endpoint always costs zero.
                    budget = len(source) if feasible else len(source) - 1
                    inst = Instance(0, u - 1, source, segments,
                                    Contract(0, len(source), budget, 0, 0))
                    cert, _ = produce_prefix(inst)
                    check_prefix(inst, cert)
                    assert cert["endpoint"]["segments"] == [None] * u
                    values = [[] for _ in segments]
                    if feasible:
                        active = list(source)
                        for step in range(len(source) + 1):
                            for rank, query in enumerate(active):
                                values[query].append(rank - segments[query].predict(query))
                                active_queries += 1
                            if step < len(source):
                                active.remove(source[step])
                    want = [None if not row else [min(row), max(row)] for row in values]
                    got = [None if row is None else [row["lower"], row["upper"]]
                           for row in cert["segments"]]
                    assert got == want, (inst, got, want)
                    for j, row in enumerate(cert["segments"]):
                        if row is None:
                            continue
                        for field, claimed in (("min_witness", row["lower"]),
                                               ("max_witness", row["upper"])):
                            expanded = materialize_prefix_witness(inst, row[field])
                            assert expanded["final_keys"] == []
                            query = expanded["query"]
                            active = list(source)
                            states = [list(active)]
                            for key in source:
                                active.remove(key)
                                states.append(list(active))
                            assert expanded["active_prefix_keys"] in states
                            prefix = expanded["active_prefix_keys"]
                            assert query in prefix
                            assert prefix.index(query) - segments[j].predict(query) == claimed
                            expanded_witnesses += 1
                        mutant = deepcopy(cert)
                        mutant["segments"][j] = None
                        try:
                            check_prefix(inst, mutant)
                        except Reject:
                            rejected_empty_markers += 1
                        else:
                            raise AssertionError("active old query hidden by an empty marker")
                    cases += 1

    # A source-prefix violation can first become reachable at positive endpoint
    # cost when the size band excludes the source. Its predecessor is vacuous.
    growth = Instance(0, 2, (0, 2), (Segment(0, 2, 0, 0),),
                      Contract(1, 0, 1, 3, 3))
    windows = [[1, 1]]
    result = shortest_prefix_bisection(growth, windows)
    check_prefix_shortest(growth, windows, result)
    assert (result["kind"], result["edits"]) == ("violation", 1)
    assert result["previous_certificate"]["segments"] == [None]
    return {"contracts": cases, "active_prefix_queries": active_queries,
            "expanded_empty_final_witnesses": expanded_witnesses,
            "rejected_hidden_active_segments": rejected_empty_markers,
            "growth_minimum_questions": 1, "growth_minimum_edits": result["edits"],
            "mismatches": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must remain enabled")
    result = run()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
