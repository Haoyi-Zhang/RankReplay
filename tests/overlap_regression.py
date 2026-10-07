"""Standalone untimed finite conformance, separate from the 64-file campaign.

The test-local oracle enumerates literal final sets and canonical edit prefixes.
It imports no overlap/rank/atom/envelope helpers or historical implementation.
No private paths, resource substitutions, files written, subprocesses or timers.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from driftcert import (Contract, Instance, Segment, check, check_prefix,
                       check_prefix_shortest, check_shortest, direct_minimum,
                       materialize_prefix_witness, materialize_witness, produce,
                       produce_prefix, shortest, shortest_bisection,
                       shortest_prefix_bisection)

COUNTS = {}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def count(name, amount=1):
    COUNTS[name] = COUNTS.get(name, 0) + amount


def subsets(values):
    for mask in range(1 << len(values)):
        yield tuple(x for j, x in enumerate(values) if mask & (1 << j))


def trace(source, final):
    active, target = set(source), set(final)
    states = [tuple(sorted(active))]
    for x in sorted(active - target):
        active.remove(x)
        states.append(tuple(sorted(active)))
    for x in sorted(target - active):
        active.add(x)
        states.append(tuple(sorted(active)))
    return states


def literal(inst, windows):
    """Original inequalities only; cost minima are obtained from actual sets."""
    width = inst.hi - inst.lo + 1
    require(width <= 11, "literal oracle admission is at most eleven coordinates")
    c, source = inst.contract, set(inst.keys)
    endpoint, replay = [None] * len(inst.segments), [None] * len(inst.segments)
    minimum, prefix_minimum = None, None
    finals = states_count = queries = prefix_queries = 0

    def visit(active, rows):
        bad = False
        for rank, x in enumerate(active):
            j = next(j for j, seg in enumerate(inst.segments) if seg.lo <= x <= seg.hi)
            seg = inst.segments[j]
            value = rank - (seg.a * x + seg.b) // seg.q
            rows[j] = [value, value] if rows[j] is None else [min(rows[j][0], value), max(rows[j][1], value)]
            bad |= not windows[j][0] <= value <= windows[j][1]
        return bad

    for final in subsets(tuple(range(inst.lo, inst.hi + 1))):
        target = set(final)
        inserted, deleted = len(target - source), len(source - target)
        cost = inserted + deleted
        if (inserted > c.insert or deleted > c.delete or cost > c.edits
                or not c.size_lo <= len(final) <= c.size_hi):
            continue
        finals += 1
        queries += len(final)
        if visit(final, endpoint):
            minimum = cost if minimum is None else min(cost, minimum)
        for active in trace(inst.keys, final):
            states_count += 1
            prefix_queries += len(active)
            if visit(active, replay):
                prefix_minimum = cost if prefix_minimum is None else min(cost, prefix_minimum)
    return endpoint, replay, minimum, prefix_minimum, (finals, states_count, queries, prefix_queries)


def cases():
    for u in range(1, 5):
        lo, hi = -u // 2, -u // 2 + u - 1
        for source in subsets(tuple(range(lo, hi + 1))):
            n = len(source)
            bands = sorted({(0, 0), (n, n), (u, u), (0, u), (n + 1, n + 1)})
            budgets = sorted({(0, 0, 0), (1, 1, 1), (1, 1, 2), (u, u, 2 * u), (1, 0, 1), (0, u, u)})
            predictors = [(Segment(lo, hi, -2, -1, 3),), (Segment(lo, hi, 3, -2, 2),)]
            if u > 1:
                cut = lo + u // 2 - 1
                predictors.append((Segment(lo, cut, 0, -1), Segment(cut + 1, hi, -3, 2, 2)))
            for segments, (insert, delete, edits), (ml, mh) in product(predictors, budgets, bands):
                yield Instance(lo, hi, source, segments, Contract(insert, delete, edits, ml, mh))


def endpoints(cert):
    return [None if row is None else [row["lower"], row["upper"]] for row in cert["segments"]]


def verify_expansion(inst, wrapped, residual):
    expanded = materialize_prefix_witness(inst, wrapped)
    final = tuple(expanded["final_keys"])
    source, target, c = set(inst.keys), set(final), inst.contract
    cost = len(source - target) + len(target - source)
    require(tuple(sorted(target)) == final, "expanded final is not a sorted set")
    require(len(target - source) <= c.insert and len(source - target) <= c.delete
            and cost <= c.edits and c.size_lo <= len(final) <= c.size_hi, "expanded contract mismatch")
    require(expanded["net_edits"] == cost and expanded["delete_ascending"] == sorted(source - target)
            and expanded["insert_ascending"] == sorted(target - source), "expanded edit order mismatch")
    states = trace(inst.keys, final)
    witness = wrapped["witness"]
    query = witness["x"]
    if wrapped["kind"] == "endpoint":
        active = final
    elif wrapped["phase"] == "initial":
        active = states[0]
    else:
        # The last prefix before the query disappears, or end of deletion.
        deletions = sorted(source - target)
        step = deletions.index(query) if query in deletions else len(deletions)
        active = states[step]
    require(query in active and active.index(query) == witness["rank"], "expanded active rank mismatch")
    seg = next(seg for seg in inst.segments if seg.lo <= query <= seg.hi)
    require(active.index(query) - (seg.a * query + seg.b) // seg.q == residual, "expanded residual mismatch")
    if wrapped["kind"] == "prefix":
        require(expanded["active_prefix_keys"] == list(active), "expanded phase mismatch")
    count("expanded_witnesses")
    return expanded


def observe(inst, windows):
    """Full records used unchanged by the private actual-snapshot comparator."""
    original = copy.deepcopy((inst.to_dict(), windows))
    expected, expected_prefix, minimum, replay_minimum, visits = literal(inst, windows)
    cert, stats = produce(inst)
    prefix, prefix_stats = produce_prefix(inst)
    require(endpoints(cert) == expected and endpoints(prefix) == expected_prefix, "literal envelope mismatch")
    checked, prefix_checked = check(inst, cert), check_prefix(inst, prefix)
    expansions = []
    for row in prefix["segments"]:
        if row is not None:
            for field, key in (("min_witness", "lower"), ("max_witness", "upper")):
                expansions.append(verify_expansion(inst, row[field], row[key]))
    relaxed = replace(inst, contract=replace(inst.contract, edits=inst.contract.insert + inst.contract.delete))
    relaxed_minimum = literal(relaxed, windows)[2]
    best, direct_stats = direct_minimum(inst, windows)
    require((None if best is None else best["edits"]) == relaxed_minimum, "relaxed direct minimum mismatch")
    packets = []
    for fn, validator, expected_minimum in (
            (shortest, check_shortest, minimum),
            (shortest_bisection, check_shortest, minimum),
            (shortest_prefix_bisection, check_prefix_shortest, replay_minimum)):
        measured = {}
        packet = fn(inst, windows, measured)
        accepted = validator(inst, windows, packet)
        require((None if packet["kind"] == "safe" else packet["edits"]) == expected_minimum, "minimum mismatch")
        if packet["kind"] == "violation":
            target = replace(inst, contract=inst.contract.with_edits(packet["edits"]))
            wrapped = packet["witness"] if fn is shortest_prefix_bisection else {"kind": "endpoint", "witness": packet["witness"]}
            witness = wrapped["witness"]
            seg = target.segments[packet["segment"]]
            residual = witness["rank"] - (seg.a * witness["x"] + seg.b) // seg.q
            expansions.append(verify_expansion(target, wrapped, residual))
        packets.append((packet, measured, accepted))
    require((inst.to_dict(), windows) == original, "trusted input/window mutated")
    count("instances")
    for label, value in zip(("literal_finals", "literal_prefixes", "literal_final_queries", "literal_prefix_queries"), visits):
        count(label, value)
    return cert, stats, checked, prefix, prefix_stats, prefix_checked, best, direct_stats, packets, expansions


def bad_inputs():
    base = Instance(0, 2, (0, 2), (Segment(0, 2, 1, -1, 2),), Contract(1, 1, 2, 2, 2))
    for field, value in (("lo", True), ("hi", 1 << 256), ("lo", 3),
                         ("keys", (0, 0)), ("keys", (2, 0)), ("keys", (-1,)),
                         ("keys", tuple(range(100001))), ("segments", ()),
                         ("segments", (Segment(0, 1, 1, 0),)),
                         ("segments", (Segment(0, 2, 1, 0, 0),)),
                         ("segments", (Segment(0, 2, True, 0),)),
                         ("segments", (base.segments[0],) * 100001),
                         ("contract", Contract(-1, 0, 0, 0, 2)),
                         ("contract", Contract(1, 1, True, 0, 2)),
                         ("contract", Contract(1, 1, 2, 2, 1))):
        yield replace(base, **{field: value})
    yield replace(base, lo=True, keys=(0, 0), contract=Contract(-1, 0, 0, 0, 2))


def bad_windows():
    return (None, (), [], [[0]], [[1, 0]], [[False, 1]], [[0, 1.5]], [[0, 1 << 1024]], [[0, 1, 2]])


def mutants(packet):
    for field in packet:
        obj = copy.deepcopy(packet)
        del obj[field]
        yield "missing-" + field, obj
    obj = copy.deepcopy(packet); obj["extra"] = 1
    yield "extra", obj
    if "segments" in packet:
        obj = copy.deepcopy(packet); obj["segments"] = []
        yield "missing-segments", obj
        for j, row in enumerate(packet["segments"]):
            if row is None:
                continue
            for field in row:
                obj = copy.deepcopy(packet); del obj["segments"][j][field]
                yield f"missing-row-{j}-{field}", obj
            for field in ("lower", "upper"):
                for value in (True, 1.5, 1 << 1024, row[field] + 1, row[field] - 1):
                    obj = copy.deepcopy(packet); obj["segments"][j][field] = value
                    yield f"bad-row-{j}-{field}-{value}", obj
    if "schedule" in packet:
        obj = copy.deepcopy(packet); obj["schedule"] = "insert-first"
        yield "changed-schedule", obj
    if packet.get("kind") == "violation":
        for field, value in (("edits", True), ("edits", packet["edits"] + 1),
                             ("side", "invalid"), ("segment", -1), ("witness", {}),
                             ("previous_certificate", {})):
            obj = copy.deepcopy(packet); obj[field] = value
            yield "bad-" + field, obj


class OverlapRegression(unittest.TestCase):
    def test_literal_sets_replays_minima_and_local_metrics(self):
        for inst in cases():
            observe(inst, [[-1, 1] for _ in inst.segments])

    def test_targeted_contracts_and_returned_witnesses(self):
        hinge = Instance(0, 10, (0, 10), (Segment(0, 10, 1, 0, 2),), Contract(3, 1, 4, 4, 4))
        observe(hinge, [[-4, 0]])
        separation = Instance(0, 2, (0, 2), (Segment(0, 1, 0, 0), Segment(2, 2, 0, 0)), Contract(1, 1, 2, 2, 2))
        record = observe(separation, [[-10, 10], [1, 1]])
        self.assertEqual(record[8][0][0]["kind"], "safe")
        self.assertEqual(record[8][2][0]["edits"], 2)
        growth = Instance(0, 2, (0, 2), (Segment(0, 2, 0, 0),), Contract(1, 0, 1, 3, 3))
        observe(growth, [[1, 1]])
        # Reuse one direct-API instance with mutable lists between calls: no
        # retained context may hide the changed source, pieces or contract.
        keys, segments = [0, 2], [Segment(0, 2, -2, -1, 3)]
        direct = Instance(0, 2, keys, segments, Contract(1, 1, 2, 0, 3))
        observe(direct, [[-1, 1]])
        keys[:] = [1]; segments[:] = [Segment(0, 2, 3, -2, 2)]
        observe(direct, [[0, 0]])
        for budget in (0, 1, 2, 1, 0, 3):
            observe(replace(direct, contract=direct.contract.with_edits(budget)), [[-1, 1]])

    def test_admission_windows_and_packet_mutants(self):
        for inst in bad_inputs():
            for fn, args in ((produce, (inst,)), (direct_minimum, (inst, [])), (shortest, (inst, []))):
                with self.assertRaises(ValueError):
                    fn(*args)
                count("invalid_input_rejections")
        inst = Instance(0, 2, (0, 2), (Segment(0, 2, 0, 0),), Contract(1, 1, 2, 2, 2))
        for window in bad_windows():
            for fn in (direct_minimum, shortest, shortest_bisection, shortest_prefix_bisection):
                with self.assertRaises(ValueError):
                    fn(inst, window)
                count("invalid_window_rejections")
        for fn, validator, args in ((produce, check, ()), (produce_prefix, check_prefix, ()),
                                   (shortest, check_shortest, ([[0, 0]],)),
                                   (shortest_prefix_bisection, check_prefix_shortest, ([[0, 0]],))):
            result = fn(inst, *args)
            packet = result[0] if isinstance(result, tuple) else result
            for label, damaged in mutants(packet):
                with self.subTest(label=label), self.assertRaises(ValueError):
                    validator(inst, *args, damaged)
                count("packet_mutants")
        huge = Instance(-(1 << 63), (1 << 64) - 1, (-(1 << 63), 0, (1 << 64) - 1),
                        (Segment(-(1 << 63), -1, -7, -(1 << 65), 3), Segment(0, (1 << 64) - 1, 9, -11, 5)),
                        Contract(5, 3, 7, 1, 8))
        cert, _ = produce(huge)
        self.assertTrue(check(huge, cert)["accepted"])
        for fn, validator in ((shortest, check_shortest), (shortest_prefix_bisection, check_prefix_shortest)):
            windows = [[-1, 1], [-1, 1]]
            self.assertTrue(validator(huge, windows, fn(huge, windows)))
        with self.assertRaisesRegex(ValueError, "output limit"):
            materialize_witness(inst, produce(inst)[0]["segments"][0]["min_witness"], limit=0)
        count("wide_and_expansion_cap_groups")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OverlapRegression))
    print(json.dumps({"successful": result.wasSuccessful(), "groups": result.testsRun, "counts": COUNTS}, sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
