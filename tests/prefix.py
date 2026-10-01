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
                       materialize_prefix_witness, shortest,
                       shortest_prefix_bisection)
import driftcert.prefix as prefix_impl


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


def empty_witness_stats() -> dict[str, int]:
    return {
        "expanded_witnesses": 0,
        "expanded_endpoint_wrappers": 0,
        "expanded_prefix_wrappers": 0,
        "expanded_initial_phase": 0,
        "expanded_deletion_min_phase": 0,
        "expanded_final_phase": 0,
        "expanded_old_query_retained": 0,
        "expanded_old_query_deleted": 0,
        "expanded_new_query": 0,
        "expanded_empty_final": 0,
        "expanded_zero_budget": 0,
        "edit_steps_replayed": 0,
        "active_query_assertions": 0,
        "rank_assertions": 0,
        "budget_assertions": 0,
    }


def add_stats(total: dict[str, int], item: dict[str, int]) -> None:
    for key, value in item.items():
        total[key] += value


def expand_and_replay_witness(inst: Instance, wrapped: dict, claimed_residual: int) -> dict[str, int]:
    """Expand one compact witness, then replay every edit without producer helpers."""
    expanded = materialize_prefix_witness(inst, wrapped)
    final = tuple(expanded["final_keys"])
    if tuple(sorted(set(final))) != final:
        raise AssertionError("expanded final keys are not a sorted set")
    if not admissible(inst, final):
        raise AssertionError("expanded witness final set violates the contract")

    source = set(inst.keys)
    target = set(final)
    deletes = sorted(source - target)
    inserts = sorted(target - source)
    if expanded["delete_ascending"] != deletes or expanded["insert_ascending"] != inserts:
        raise AssertionError("expanded witness does not expose the canonical edit order")
    if expanded["net_edits"] != len(deletes) + len(inserts):
        raise AssertionError("expanded witness net-edit count is inconsistent")

    if wrapped["kind"] == "endpoint":
        witness = wrapped["witness"]
        phase = "final"
    else:
        witness = wrapped["witness"]
        phase = wrapped["phase"]
    query, expected_rank = witness["x"], witness["rank"]

    active = set(inst.keys)
    captured: tuple[int, ...] | None = tuple(sorted(active)) if phase == "initial" else None
    for key in deletes:
        if key not in active:
            raise AssertionError("canonical replay deletes an inactive key")
        if (phase == "deletion-min" and not witness["old_self"]
                and key == query and captured is None):
            captured = tuple(sorted(active))
        active.remove(key)
    if phase == "deletion-min" and witness["old_self"]:
        captured = tuple(sorted(active))
    for key in inserts:
        if key in active:
            raise AssertionError("canonical replay inserts an active key")
        active.add(key)
    if active != target:
        raise AssertionError("canonical replay does not end at the expanded final set")
    if phase == "final":
        captured = tuple(sorted(active))
    if captured is None or query not in captured:
        raise AssertionError("claimed query is not active at the declared replay phase")
    rank = captured.index(query)
    if rank != expected_rank:
        raise AssertionError("independent replay rank disagrees with the compact witness")
    segment = next(seg for seg in inst.segments if seg.lo <= query <= seg.hi)
    if rank - segment.predict(query) != claimed_residual:
        raise AssertionError("independent replay does not attain the claimed residual")
    if wrapped["kind"] == "prefix":
        if expanded["active_prefix_keys"] != list(captured):
            raise AssertionError("expander and independent replay disagree on the active prefix")
        if expanded["query"] != query or expanded["rank"] != rank:
            raise AssertionError("expander reports the wrong active query or rank")

    stats = empty_witness_stats()
    stats["expanded_witnesses"] = 1
    stats["expanded_endpoint_wrappers" if wrapped["kind"] == "endpoint"
          else "expanded_prefix_wrappers"] = 1
    stats[f"expanded_{phase.replace('-', '_')}_phase"] = 1
    if query in source:
        stats["expanded_old_query_retained" if query in target
              else "expanded_old_query_deleted"] = 1
    else:
        stats["expanded_new_query"] = 1
    stats["expanded_empty_final"] = int(not final)
    stats["expanded_zero_budget"] = int(not deletes and not inserts)
    stats["edit_steps_replayed"] = len(deletes) + len(inserts)
    stats["active_query_assertions"] = 1
    stats["rank_assertions"] = 1
    stats["budget_assertions"] = 1
    return stats


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
    witness_stats = empty_witness_stats()
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
                            for row in cert["segments"]:
                                if row is None:
                                    continue
                                add_stats(witness_stats, expand_and_replay_witness(
                                    inst, row["min_witness"], row["lower"]))
                                add_stats(witness_stats, expand_and_replay_witness(
                                    inst, row["max_witness"], row["upper"]))
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
        "predictors": [
            "one-piece floor((-2*x+1)/3)",
            "two-piece floor((3*x-2)/2) then floor((-x+2*u)/2); u=1 uses floor((x-1)/2)",
        ],
        "insert_delete_caps": "all integers 0..u",
        "total_edit_caps": "all integers 0..u",
        "final_size_bands": "all fixed bands [m,m] for m=0..u plus [0,u]",
        **witness_stats,
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
    witness_stats = empty_witness_stats()
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
                                target = replace(inst, contract=inst.contract.with_edits(actual))
                                wrapped = result["witness"]
                                if wrapped["kind"] == "endpoint":
                                    witness = wrapped["witness"]
                                else:
                                    witness = wrapped["witness"]
                                segment = target.segments[result["segment"]]
                                claimed = witness["rank"] - segment.predict(witness["x"])
                                add_stats(witness_stats, expand_and_replay_witness(
                                    target, wrapped, claimed))
    return {
        "mode": "minimum",
        "universe": u,
        "initial_set_start": start,
        "initial_set_stop": stop,
        "minimum_queries": cases,
        "safe_results": safe,
        "violating_results": violations,
        "predictor": "one-piece floor((2*x-1)/3)",
        "insert_delete_step": step,
        "insert_delete_caps": list(range(0, u + 1, step)),
        "total_edit_caps": "all integers 0..u",
        "final_size_bands": ["[0,u]", "[|S|,|S|]"],
        **witness_stats,
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
    if prefix_result.get("schedule") != prefix_impl.SCHEDULE:
        raise AssertionError("replay minimum packet omitted its schedule binding")
    if prefix["segments"][1]["lower"] != 0 or prefix["segments"][1]["upper"] != 1:
        raise AssertionError("unexpected separation envelope")

    # Bounded hot-path regression: dense old keys, empty final state, and every
    # strict upper update needs a witness.  Production must reuse the scan rank
    # rather than perform a fresh bisect_left for each construction.
    dense_n = 64
    dense = Instance(
        0, dense_n - 1, tuple(range(dense_n)),
        (Segment(0, dense_n - 1, 0, 0, 1),),
        Contract(0, dense_n, dense_n, 0, 0),
    )
    bisect_calls = 0
    original_bisect = prefix_impl.bisect_left

    def counted_bisect(values, value, lo=0, hi=None):
        nonlocal bisect_calls
        bisect_calls += 1
        return (original_bisect(values, value, lo) if hi is None
                else original_bisect(values, value, lo, hi))

    prefix_impl.bisect_left = counted_bisect
    try:
        dense_cert, dense_metrics = produce_prefix(dense)
    finally:
        prefix_impl.bisect_left = original_bisect
    check_prefix(dense, dense_cert)
    if bisect_calls != 0:
        raise AssertionError("produce_prefix repeated bisect_left during witness construction")
    if dense_metrics["old_key_evaluations"] != dense_n:
        raise AssertionError("dense hot-path scan count is wrong")
    if dense_metrics["witness_constructions"] != dense_n + 1:
        raise AssertionError("dense hot-path witness count is wrong")

    # Literal expansion and independent edit-by-edit replay cover both temporal
    # phases, an empty final state, retained and deleted old queries, and a final
    # endpoint witness.
    regression_witness_stats = empty_witness_stats()
    for row in dense_cert["segments"]:
        if row is not None:
            add_stats(regression_witness_stats, expand_and_replay_witness(
                dense, row["min_witness"], row["lower"]))
            add_stats(regression_witness_stats, expand_and_replay_witness(
                dense, row["max_witness"], row["upper"]))
    add_stats(regression_witness_stats, expand_and_replay_witness(
        inst, prefix["segments"][1]["min_witness"], prefix["segments"][1]["lower"]))

    # A zero-budget source-prefix failure must still be a schedule-bound packet.
    zero = Instance(0, 0, (0,), (Segment(0, 0, 0, 0, 1),),
                    Contract(0, 0, 0, 1, 1))
    zero_windows = [[1, 1]]
    zero_result = shortest_prefix_bisection(zero, zero_windows)
    check_prefix_shortest(zero, zero_windows, zero_result)
    if (zero_result.get("kind"), zero_result.get("edits"),
            zero_result.get("schedule"), zero_result.get("previous_certificate")) != (
            "violation", 0, prefix_impl.SCHEDULE, None):
        raise AssertionError("zero-budget replay failure packet is malformed")
    zero_wrapped = zero_result["witness"]
    zero_witness = zero_wrapped["witness"]
    zero_residual = zero_witness["rank"] - zero.segments[0].predict(zero_witness["x"])
    add_stats(regression_witness_stats, expand_and_replay_witness(
        zero, zero_wrapped, zero_residual))
    safe_result = shortest_prefix_bisection(zero, [[-1, 1]])
    check_prefix_shortest(zero, [[-1, 1]], safe_result)
    if safe_result.get("kind") != "safe" or safe_result.get("schedule") != prefix_impl.SCHEDULE:
        raise AssertionError("safe replay minimum packet is not schedule bound")

    for required in ("expanded_initial_phase", "expanded_deletion_min_phase",
                     "expanded_final_phase", "expanded_endpoint_wrappers",
                     "expanded_prefix_wrappers", "expanded_old_query_retained",
                     "expanded_old_query_deleted", "expanded_empty_final",
                     "expanded_zero_budget"):
        if regression_witness_stats[required] == 0:
            raise AssertionError("missing targeted replay-witness coverage: " + required)

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

    minimum_mutants: dict[str, tuple[Instance, list[list[int]], dict]] = {}
    m = copy.deepcopy(prefix_result); m["edits"] = 1
    minimum_mutants["forged_budget"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m["side"] = "above"
    minimum_mutants["forged_side"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m["previous_certificate"] = prefix
    minimum_mutants["forged_predecessor"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m["witness"]["witness"]["old_left"] += 1
    minimum_mutants["forged_prefix_count"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m.pop("schedule")
    minimum_mutants["missing_schedule"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m["schedule"] = "insert-first"
    minimum_mutants["modified_schedule"] = (inst, windows, m)
    m = copy.deepcopy(prefix_result); m["witness"]["extra"] = 1
    minimum_mutants["extra_prefix_wrapper_field"] = (inst, windows, m)
    m = copy.deepcopy(zero_result); m["witness"]["extra"] = 1
    minimum_mutants["extra_endpoint_wrapper_field"] = (zero, zero_windows, m)
    m = copy.deepcopy(zero_result); m.pop("schedule")
    minimum_mutants["zero_budget_missing_schedule"] = (zero, zero_windows, m)
    m = copy.deepcopy(zero_result); m["schedule"] = "insert-first"
    minimum_mutants["zero_budget_modified_schedule"] = (zero, zero_windows, m)
    m = copy.deepcopy(safe_result); m.pop("schedule")
    minimum_mutants["safe_missing_schedule"] = (zero, [[-1, 1]], m)
    m = copy.deepcopy(safe_result); m["unexpected"] = 1
    minimum_mutants["safe_extra_packet_field"] = (zero, [[-1, 1]], m)

    minimum_rejected = []
    for name, (target, target_windows, mutant) in minimum_mutants.items():
        try:
            check_prefix_shortest(target, target_windows, mutant)
        except Reject:
            minimum_rejected.append(name)
        else:
            raise AssertionError("accepted replay-minimum mutant: " + name)

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
        "zero_budget_failure": {
            "schedule": zero_result["schedule"],
            "edits": zero_result["edits"],
            "side": zero_result["side"],
            "previous_certificate": zero_result["previous_certificate"],
        },
        "hot_path": {
            "n": dense_n,
            "bisect_left_calls": bisect_calls,
            "old_key_evaluations": dense_metrics["old_key_evaluations"],
            "witness_constructions": dense_metrics["witness_constructions"],
        },
        "targeted_witness_expansion": regression_witness_stats,
        "certificate_mutants_rejected": rejected,
        "minimum_mutants_rejected": minimum_rejected,
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
