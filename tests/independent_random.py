"""Independent random actual-state oracle for final and canonical-replay certificates.

This test enumerates literal final sets and literal replay states.  It deliberately
does not call the implementation's overlap, rank-band, atom, envelope, or
minimum-cost helpers.  The only imported project functions are the public
producer/checker interfaces being tested and the input dataclasses.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import replace
from pathlib import Path

from driftcert import (
    Contract, Instance, Segment,
    check, check_prefix, check_prefix_shortest, check_shortest,
    produce, produce_prefix, shortest, shortest_bisection,
    shortest_prefix_bisection,
)


def powerset(values: tuple[int, ...]):
    for mask in range(1 << len(values)):
        yield tuple(values[i] for i in range(len(values)) if mask & (1 << i))


def segment_index(inst: Instance, x: int) -> int:
    for j, seg in enumerate(inst.segments):
        if seg.lo <= x <= seg.hi:
            return j
    raise AssertionError("query outside predictor partition")


def admissible(inst: Instance, final: tuple[int, ...]) -> bool:
    source = set(inst.keys)
    target = set(final)
    inserts = len(target - source)
    deletes = len(source - target)
    c = inst.contract
    return (inserts <= c.insert and deletes <= c.delete and
            inserts + deletes <= c.edits and
            c.size_lo <= len(final) <= c.size_hi)


def update(rows: list[list[int] | None], inst: Instance,
           active: tuple[int, ...]) -> int:
    count = 0
    for rank, x in enumerate(active):
        j = segment_index(inst, x)
        residual = rank - inst.segments[j].predict(x)
        if rows[j] is None:
            rows[j] = [residual, residual]
        else:
            rows[j][0] = min(rows[j][0], residual)
            rows[j][1] = max(rows[j][1], residual)
        count += 1
    return count


def brute_final(inst: Instance):
    universe = tuple(range(inst.lo, inst.hi + 1))
    rows: list[list[int] | None] = [None] * len(inst.segments)
    sets = queries = 0
    for final in powerset(universe):
        if admissible(inst, final):
            sets += 1
            queries += update(rows, inst, final)
    return rows, {"final_sets": sets, "final_queries": queries}


def brute_prefix(inst: Instance):
    universe = tuple(range(inst.lo, inst.hi + 1))
    source = set(inst.keys)
    rows: list[list[int] | None] = [None] * len(inst.segments)
    sets = states = queries = 0
    for final_tuple in powerset(universe):
        if not admissible(inst, final_tuple):
            continue
        sets += 1
        final = set(final_tuple)
        active = set(source)
        queries += update(rows, inst, tuple(sorted(active))); states += 1
        for x in sorted(source - final):
            active.remove(x)
            queries += update(rows, inst, tuple(sorted(active))); states += 1
        for x in sorted(final - source):
            active.add(x)
            queries += update(rows, inst, tuple(sorted(active))); states += 1
        assert active == final
    return rows, {"replay_final_sets": sets, "replay_states": states,
                  "replay_queries": queries}


def endpoints(cert: dict):
    return [None if row is None else [row["lower"], row["upper"]]
            for row in cert["segments"]]


def safe(rows, windows):
    return all(row is None or (w[0] <= row[0] and row[1] <= w[1])
               for row, w in zip(rows, windows))


def brute_minimum(inst: Instance, windows, replay: bool):
    for edits in range(inst.contract.edits + 1):
        target = replace(inst, contract=inst.contract.with_edits(edits))
        rows, _ = brute_prefix(target) if replay else brute_final(target)
        if not safe(rows, windows):
            return edits
    return None


def make_instance(rng: random.Random, maximum: int) -> Instance:
    width = rng.randint(1, maximum)
    lo = rng.randint(-5, 5); hi = lo + width - 1
    universe = list(range(lo, hi + 1))
    keys = tuple(x for x in universe if rng.random() < 0.5)
    pieces = rng.randint(1, min(4, width))
    cuts = sorted(rng.sample(range(lo + 1, hi + 1), pieces - 1))
    starts = [lo] + cuts; ends = [x - 1 for x in cuts] + [hi]
    segments = tuple(Segment(a, b, rng.randint(-5, 5),
                             rng.randint(-9, 9), rng.randint(1, 5))
                     for a, b in zip(starts, ends))
    insert = rng.randint(0, width)
    delete = rng.randint(0, width)
    edits = rng.randint(0, 2 * width)
    size_lo, size_hi = sorted((rng.randint(0, width), rng.randint(0, width)))
    return Instance(lo, hi, keys, segments,
                    Contract(insert, delete, edits, size_lo, size_hi))


def make_windows(rng: random.Random, inst: Instance):
    source_rows: list[list[int] | None] = [None] * len(inst.segments)
    update(source_rows, inst, inst.keys)
    result = []
    for row in source_rows:
        if row is None or rng.random() < 0.35:
            center = rng.randint(-8, 8); radius = rng.randint(0, 4)
            result.append([center - radius, center + radius])
        else:
            result.append([row[0] - rng.randint(0, 3),
                           row[1] + rng.randint(0, 3)])
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=2500)
    ap.add_argument("--max-universe", type=int, default=9)
    ap.add_argument("--seed", type=int, default=8675309)
    ap.add_argument("--output", default="results/independent-random.json")
    args = ap.parse_args()
    if args.cases < 1 or not 1 <= args.max_universe <= 12:
        ap.error("cases must be positive and max-universe must be in 1..12")

    rng = random.Random(args.seed)
    started = time.process_time()
    totals = dict(instances=0, final_sets=0, final_queries=0,
                  replay_final_sets=0, replay_states=0, replay_queries=0,
                  minimum_questions=0, checker_acceptances=0, mismatches=0)
    failures = []
    for case in range(args.cases):
        inst = make_instance(rng, args.max_universe)
        windows = make_windows(rng, inst)
        final_oracle, counts = brute_final(inst)
        replay_oracle, replay_counts = brute_prefix(inst)
        totals["instances"] += 1
        for k, v in {**counts, **replay_counts}.items(): totals[k] += v

        final_cert, _ = produce(inst); replay_cert, _ = produce_prefix(inst)
        try:
            check(inst, final_cert); check_prefix(inst, replay_cert)
            totals["checker_acceptances"] += 2
        except Exception as exc:
            failures.append({"case": case, "stage": "checker", "error": repr(exc),
                             "instance": inst.to_dict()})
        if endpoints(final_cert) != final_oracle:
            failures.append({"case": case, "stage": "final-envelope",
                             "instance": inst.to_dict(),
                             "producer": endpoints(final_cert), "oracle": final_oracle})
        if endpoints(replay_cert) != replay_oracle:
            failures.append({"case": case, "stage": "replay-envelope",
                             "instance": inst.to_dict(),
                             "producer": endpoints(replay_cert), "oracle": replay_oracle})

        final_min = brute_minimum(inst, windows, False)
        replay_min = brute_minimum(inst, windows, True)
        direct = shortest(inst, windows)
        binary = shortest_bisection(inst, windows)
        prefix = shortest_prefix_bisection(inst, windows)
        totals["minimum_questions"] += 3
        try:
            check_shortest(inst, windows, direct)
            check_shortest(inst, windows, binary)
            check_prefix_shortest(inst, windows, prefix)
            totals["checker_acceptances"] += 3
        except Exception as exc:
            failures.append({"case": case, "stage": "minimum-checker",
                             "error": repr(exc), "instance": inst.to_dict(),
                             "windows": windows})
        got_direct = None if direct["kind"] == "safe" else direct["edits"]
        got_binary = None if binary["kind"] == "safe" else binary["edits"]
        got_prefix = None if prefix["kind"] == "safe" else prefix["edits"]
        if (got_direct, got_binary) != (final_min, final_min):
            failures.append({"case": case, "stage": "final-minimum",
                             "instance": inst.to_dict(), "windows": windows,
                             "direct": got_direct, "binary": got_binary,
                             "oracle": final_min})
        if got_prefix != replay_min:
            failures.append({"case": case, "stage": "replay-minimum",
                             "instance": inst.to_dict(), "windows": windows,
                             "producer": got_prefix, "oracle": replay_min})
        if failures:
            break

    totals["mismatches"] = len(failures)
    result = {"seed": args.seed, "requested_cases": args.cases,
              "max_universe": args.max_universe, **totals,
              "cpu_seconds": time.process_time() - started,
              "failures": failures}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if failures: raise SystemExit(1)


if __name__ == "__main__":
    main()
