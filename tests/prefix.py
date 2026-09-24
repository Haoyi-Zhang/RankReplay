"""Exact oracle checks for canonical ordered-replay envelopes and minima.

The bounded oracle enumerates complete final sets and every active replay prefix, including the empty edit prefix at the source state.
It is deliberately independent of the producer formulas.  Universe size is
capped at four and runs are shardable by the initial-set mask.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import resource
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftcert import (Contract, Instance, Reject, Segment, check_prefix,
                       check_prefix_shortest, produce, produce_prefix,
                       shortest, shortest_prefix_bisection)


def all_sets(u: int) -> list[tuple[int, ...]]:
    return [tuple(x for x in range(u) if mask & (1 << x)) for mask in range(1 << u)]


def predictors(u: int) -> list[tuple[Segment, ...]]:
    result = [(Segment(0, u - 1, -2, 1, 3),)]
    if u >= 2:
        cut = (u - 1) // 2
        result.append((Segment(0, cut, 3, -2, 2),
                       Segment(cut + 1, u - 1, -1, 2 * u, 2)))
    else:
        result.append((Segment(0, 0, 1, -1, 2),))
    return result


def admissible(inst: Instance, final: tuple[int, ...]) -> bool:
    source = set(inst.keys)
    target = set(final)
    deletes = len(source - target)
    inserts = len(target - source)
    c = inst.contract
    return (deletes <= c.delete and inserts <= c.insert
            and deletes + inserts <= c.edits
            and c.size_lo <= len(target) <= c.size_hi)


def replay_states(source: tuple[int, ...], final: tuple[int, ...]) -> list[tuple[int, ...]]:
    s, t = set(source), set(final)
    state = set(source)
    states = [tuple(sorted(state))]
    for x in sorted(s - t):
        state.remove(x)
        states.append(tuple(sorted(state)))
    for x in sorted(t - s):
        state.add(x)
        states.append(tuple(sorted(state)))
    return states


def oracle(inst: Instance, finals: list[tuple[int, ...]]) -> tuple[list[tuple[int, int] | None], dict]:
    values: list[list[int]] = [[] for _ in inst.segments]
    traces = prefixes = queries = 0
    for final in finals:
        if not admissible(inst, final):
            continue
        traces += 1
        states = replay_states(inst.keys, final)
        prefixes += len(states)
        for state in states:
            for rank, x in enumerate(state):
                for j, segment in enumerate(inst.segments):
                    if segment.lo <= x <= segment.hi:
                        values[j].append(rank - segment.predict(x))
                        queries += 1
                        break
    envelope = [None if not row else (min(row), max(row)) for row in values]
    return envelope, {"traces": traces, "prefixes": prefixes, "active_queries": queries}


def envelope_campaign(u: int, start: int, stop: int) -> dict:
    finals = all_sets(u)
    cases = traces = prefixes = queries = 0
    strict_contracts = strict_segments = 0
    mismatches = 0
    bands = [(m, m) for m in range(u + 1)] + [(0, u)]
    for mask in range(start, stop):
        source = finals[mask]
        for segments in predictors(u):
            for insert in range(u + 1):
                for delete in range(u + 1):
                    for edits in range(u + 1):
                        for size_lo, size_hi in bands:
                            inst = Instance(0, u - 1, source, segments,
                                            Contract(insert, delete, edits, size_lo, size_hi))
                            cert, _ = produce_prefix(inst)
                            check_prefix(inst, cert)
                            got = [None if row is None else (row["lower"], row["upper"])
                                   for row in cert["segments"]]
                            terminal = cert["endpoint"]["segments"]
                            enlarged = 0
                            for terminal_row, replay_row in zip(terminal, cert["segments"]):
                                if replay_row is not None and (terminal_row is None
                                   or replay_row["lower"] < terminal_row["lower"]
                                   or replay_row["upper"] > terminal_row["upper"]):
                                    enlarged += 1
                            strict_segments += enlarged
                            strict_contracts += int(enlarged > 0)
                            want, stats = oracle(inst, finals)
                            if got != want:
                                mismatches += 1
                                raise AssertionError((inst.to_dict(), got, want))
                            cases += 1
                            traces += stats["traces"]
                            prefixes += stats["prefixes"]
                            queries += stats["active_queries"]
    return {
        "mode": "envelope",
        "universe": u,
        "initial_set_start": start,
        "initial_set_stop": stop,
        "contracts": cases,
        "admissible_final_sets_counted_with_multiplicity": traces,
        "replay_prefixes": prefixes,
        "active_prefix_queries": queries,
        "contracts_with_strict_prefix_enlargement": strict_contracts,
        "strict_segment_enlargements": strict_segments,
        "mismatches": mismatches,
    }


def violates(inst: Instance, windows: list[list[int]], finals: list[tuple[int, ...]]) -> bool:
    envelope, _ = oracle(inst, finals)
    return any(row is not None and not (window[0] <= row[0] and row[1] <= window[1])
               for row, window in zip(envelope, windows))


def minimum_campaign(u: int, start: int, stop: int) -> dict:
    finals = all_sets(u)
    cases = safe = violations = 0
    mismatches = 0
    step = max(1, u // 2)
    for mask in range(start, stop):
        source = finals[mask]
        segments = (Segment(0, u - 1, 2, -1, 3),)
        source_residuals = [rank - segments[0].predict(x) for rank, x in enumerate(source)]
        windows = [[[-1, 1]], [[0, 0]]]
        if source_residuals:
            low, high = min(source_residuals), max(source_residuals)
            windows += [[[low, high]], [[low - 1, high]], [[low, high + 1]]]
        for insert in range(0, u + 1, step):
            for delete in range(0, u + 1, step):
                for edits in range(u + 1):
                    for size_lo, size_hi in ((0, u), (len(source), len(source))):
                        inst = Instance(0, u - 1, source, segments,
                                        Contract(insert, delete, edits, size_lo, size_hi))
                        for window in windows:
                            expected = None
                            for budget in range(edits + 1):
                                target = replace(inst, contract=inst.contract.with_edits(budget))
                                if violates(target, window, finals):
                                    expected = budget
                                    break
                            result = shortest_prefix_bisection(inst, window)
                            check_prefix_shortest(inst, window, result)
                            actual = None if result["kind"] == "safe" else result["edits"]
                            if actual != expected:
                                mismatches += 1
                                raise AssertionError((inst.to_dict(), window, actual, expected))
                            cases += 1
                            if actual is None:
                                safe += 1
                            else:
                                violations += 1
    return {
        "mode": "minimum",
        "universe": u,
        "initial_set_start": start,
        "initial_set_stop": stop,
        "minimum_queries": cases,
        "safe_results": safe,
        "violating_results": violations,
        "mismatches": mismatches,
    }


def regression() -> dict:
    inst = Instance(
        0, 2, (0, 2),
        (Segment(0, 1, 0, 0, 1), Segment(2, 2, 0, 0, 1)),
        Contract(1, 1, 2, 2, 2),
    )
    endpoint, _ = produce(inst)
    prefix, _ = produce_prefix(inst)
    check_prefix(inst, prefix)
    windows = [[-10, 10], [1, 1]]
    endpoint_result = shortest(inst, windows)
    prefix_result = shortest_prefix_bisection(inst, windows)
    check_prefix_shortest(inst, windows, prefix_result)
    if endpoint_result["kind"] != "safe" or prefix_result.get("edits") != 2:
        raise AssertionError("terminal-state/prefix separation example failed")
    if prefix["segments"][1]["lower"] != 0 or prefix["segments"][1]["upper"] != 1:
        raise AssertionError("unexpected separation envelope")

    mutants: dict[str, dict] = {}
    m = copy.deepcopy(prefix); m["schedule"] = "insert-first"; mutants["schedule"] = m
    m = copy.deepcopy(prefix); m["segments"][1]["lower"] -= 1; mutants["forged_lower"] = m
    m = copy.deepcopy(prefix); m["segments"][1] = None; mutants["hidden_old_key"] = m
    m = copy.deepcopy(prefix); m["endpoint"]["segments"] = []; mutants["endpoint_omission"] = m
    for name, field in (("rank", "rank"), ("old_left", "old_left"),
                        ("size", "size"), ("overlap", "overlap")):
        m = copy.deepcopy(prefix)
        wrapped = m["segments"][1]["min_witness"]
        wrapped["witness"][field] += 1
        mutants["forged_" + name] = m
    m = copy.deepcopy(prefix)
    m["segments"][1]["min_witness"]["phase"] = "initial"
    mutants["phase_swap"] = m
    rejected = []
    for name, mutant in mutants.items():
        try:
            check_prefix(inst, mutant)
        except Reject:
            rejected.append(name)
        else:
            raise AssertionError("accepted replay-certificate mutant: " + name)

    shortest_mutants = []
    m = copy.deepcopy(prefix_result); m["edits"] = 1; shortest_mutants.append(m)
    m = copy.deepcopy(prefix_result); m["side"] = "above"; shortest_mutants.append(m)
    m = copy.deepcopy(prefix_result); m["previous_certificate"] = prefix; shortest_mutants.append(m)
    m = copy.deepcopy(prefix_result)
    m["witness"]["witness"]["old_left"] += 1
    shortest_mutants.append(m)
    for mutant in shortest_mutants:
        try:
            check_prefix_shortest(inst, windows, mutant)
        except Reject:
            pass
        else:
            raise AssertionError("accepted replay-minimum mutant")

    return {
        "mode": "regression",
        "terminal_certificate": [
            [row["lower"], row["upper"]] if row is not None else None
            for row in endpoint["segments"]
        ],
        "prefix_certificate": [
            [row["lower"], row["upper"]] if row is not None else None
            for row in prefix["segments"]
        ],
        "terminal_result": endpoint_result["kind"],
        "prefix_minimum_edits": prefix_result["edits"],
        "certificate_mutants_rejected": rejected,
        "minimum_mutants_rejected": len(shortest_mutants),
        "mismatches": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["envelope", "minimum", "regression"], required=True)
    parser.add_argument("--universe", type=int, default=4)
    parser.add_argument("--start-set", type=int, default=0)
    parser.add_argument("--stop-set", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 1 <= args.universe <= 4:
        parser.error("universe must be between 1 and 4")
    total = 1 << args.universe
    stop = total if args.stop_set is None else args.stop_set
    if not 0 <= args.start_set < stop <= total:
        parser.error("invalid initial-set shard")
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (3758096384, 3758096384))
    wall = time.monotonic()
    cpu = time.process_time()
    if args.mode == "regression":
        result = regression()
    elif args.mode == "envelope":
        result = envelope_campaign(args.universe, args.start_set, stop)
    else:
        result = minimum_campaign(args.universe, args.start_set, stop)
    result.update(
        workers=1,
        cpu_seconds=time.process_time() - cpu,
        wall_seconds=time.monotonic() - wall,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
