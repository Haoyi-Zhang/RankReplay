"""Exact envelopes for a canonical ordered replay.

The replay first deletes ``S \\ T`` in ascending key order and then inserts
``T \\ S`` in ascending key order.  Queries range over every key present at
each prefix, not only keys in the final set.  The independent checker lives in
:mod:`driftcert.prefix_checker`.
"""
from __future__ import annotations

from bisect import bisect_left
from copy import deepcopy
from dataclasses import replace

from .certificate import _window_check, contained, materialize_witness, produce
from .model import Contract, Instance

SCHEDULE = "source-prefix-delete-ascending-insert-ascending"


def family_size_band(inst: Instance, contract: Contract | None = None) -> tuple[int, int] | None:
    """All final cardinalities for which at least one contracted final set exists."""
    c = contract or inst.contract
    n = len(inst.keys)
    u = inst.hi - inst.lo + 1
    lo = max(c.size_lo, 0, n - c.delete, n - c.edits)
    hi = min(c.size_hi, u, n + c.insert, n + c.edits)
    return (lo, hi) if lo <= hi else None


def minimum_family_overlap(inst: Instance, contract: Contract | None = None) -> tuple[int, int] | None:
    """Return the smallest feasible final size and its minimum old-key overlap.

    The overlap lower bound is monotone in final size, so the smallest feasible
    size also minimizes overlap over the entire family.
    """
    c = contract or inst.contract
    band = family_size_band(inst, c)
    if band is None:
        return None
    n = len(inst.keys)
    u = inst.hi - inst.lo + 1
    m = band[0]
    h = max(0, n - c.delete, m - c.insert,
            (n + m - c.edits + 1) // 2,
            m - (u - n))
    if h > min(n, m):
        raise AssertionError("derived family band contains an infeasible size")
    return m, h


def _prefix_count_witness(inst: Instance, x: int, size: int, overlap: int,
                          phase: str, *, left: int, old_left: int,
                          old_self: int, old_right: int, new_left: int,
                          new_right: int) -> dict:
    """Construct a compact old-key prefix witness from scan-local counts.

    ``produce_prefix`` already knows the source rank ``left`` and the five
    category counts while scanning the sorted source.  Passing them here avoids
    a binary search for every strict endpoint update and keeps witness creation
    in the same linear scan as the replay obligations.
    """
    n = len(inst.keys)
    if not 0 <= left < n or inst.keys[left] != x:
        raise ValueError("prefix-only witness requires the scanned old key")
    left_holes = x - inst.lo - left
    right_holes = inst.hi - x - (n - left - 1)
    capacities = (left, 1, n - left - 1, left_holes, right_holes)
    counts = (old_left, old_self, old_right, new_left, new_right)
    if old_self not in {0, 1} or any(v < 0 or v > cap for v, cap in zip(counts, capacities)):
        raise AssertionError("derived replay witness exceeds a category capacity")
    if old_left + old_self + old_right != overlap:
        raise AssertionError("derived replay witness has the wrong overlap")
    if overlap + new_left + new_right != size:
        raise AssertionError("derived replay witness has the wrong final size")
    if phase == "initial":
        rank = left
    elif phase == "deletion-min":
        rank = old_left
    else:
        raise ValueError("unknown replay phase")
    return {
        "x": x,
        "size": size,
        "overlap": overlap,
        "rank": rank,
        "old_left": old_left,
        "old_self": old_self,
        "old_right": old_right,
        "new_left": new_left,
        "new_right": new_right,
    }


def produce_prefix(inst: Instance) -> tuple[dict, dict]:
    """Produce exact segment envelopes over all active canonical-replay prefixes."""
    inst.validate()
    endpoint, endpoint_metrics = produce(inst)
    rows: list[dict | None] = []
    for row in endpoint["segments"]:
        if row is None:
            rows.append(None)
        else:
            rows.append({
                "lower": row["lower"],
                "upper": row["upper"],
                "min_witness": {"kind": "endpoint", "witness": deepcopy(row["min_witness"])},
                "max_witness": {"kind": "endpoint", "witness": deepcopy(row["max_witness"])},
            })

    minimum = minimum_family_overlap(inst)
    old_evaluations = witness_constructions = 0
    if minimum is not None:
        size, overlap = minimum
        n = len(inst.keys)
        segment = 0
        for left, x in enumerate(inst.keys):
            while x > inst.segments[segment].hi:
                segment += 1
            pred = inst.segments[segment].predict(x)
            old_left = max(0, overlap - (n - left))
            outside_left = overlap - old_left
            old_self = int(outside_left > 0)
            old_right = outside_left - old_self
            new_total = size - overlap
            left_holes = x - inst.lo - left
            new_left = min(left_holes, new_total)
            new_right = new_total - new_left
            low = old_left - pred
            high = left - pred
            row = rows[segment]
            if row is None:
                min_witness = _prefix_count_witness(
                    inst, x, size, overlap, "deletion-min", left=left,
                    old_left=old_left, old_self=old_self, old_right=old_right,
                    new_left=new_left, new_right=new_right,
                )
                max_witness = _prefix_count_witness(
                    inst, x, size, overlap, "initial", left=left,
                    old_left=old_left, old_self=old_self, old_right=old_right,
                    new_left=new_left, new_right=new_right,
                )
                witness_constructions += 2
                rows[segment] = {
                    "lower": low,
                    "upper": high,
                    "min_witness": {
                        "kind": "prefix", "phase": "deletion-min",
                        "witness": min_witness,
                    },
                    "max_witness": {
                        "kind": "prefix", "phase": "initial",
                        "witness": max_witness,
                    },
                }
            else:
                if low < row["lower"]:
                    witness = _prefix_count_witness(
                        inst, x, size, overlap, "deletion-min", left=left,
                        old_left=old_left, old_self=old_self, old_right=old_right,
                        new_left=new_left, new_right=new_right,
                    )
                    witness_constructions += 1
                    row["lower"] = low
                    row["min_witness"] = {
                        "kind": "prefix", "phase": "deletion-min",
                        "witness": witness,
                    }
                if high > row["upper"]:
                    witness = _prefix_count_witness(
                        inst, x, size, overlap, "initial", left=left,
                        old_left=old_left, old_self=old_self, old_right=old_right,
                        new_left=new_left, new_right=new_right,
                    )
                    witness_constructions += 1
                    row["upper"] = high
                    row["max_witness"] = {
                        "kind": "prefix", "phase": "initial",
                        "witness": witness,
                    }
            old_evaluations += 1

    return {
        "schedule": SCHEDULE,
        "endpoint": endpoint,
        "segments": rows,
    }, {
        "endpoint_atoms": endpoint_metrics["atoms"],
        "endpoint_candidate_evaluations": endpoint_metrics["candidate_evaluations"],
        "old_key_evaluations": old_evaluations,
        "witness_constructions": witness_constructions,
    }


def contained_prefix(cert: dict, windows: list[list[int]]) -> bool:
    return contained({"segments": cert["segments"]}, windows)


def shortest_prefix_bisection(inst: Instance, windows: list[list[int]],
                              metrics: dict | None = None) -> dict:
    """Smallest total-edit budget whose canonical replay leaves ``windows``."""
    inst.validate()
    _window_check(inst, windows)
    if metrics is not None:
        metrics.update(prefix_envelope_calls=0, prefix_candidate_evaluations=0,
                       prefix_old_key_evaluations=0,
                       prefix_witness_constructions=0)

    def envelope(target: Instance) -> dict:
        result, measured = produce_prefix(target)
        if metrics is not None:
            metrics["prefix_envelope_calls"] += 1
            metrics["prefix_candidate_evaluations"] += measured["endpoint_candidate_evaluations"]
            metrics["prefix_old_key_evaluations"] += measured["old_key_evaluations"]
            metrics["prefix_witness_constructions"] += measured["witness_constructions"]
        return result

    top = envelope(inst)
    if contained_prefix(top, windows):
        return {"kind": "safe", "schedule": SCHEDULE, "certificate": top}
    lo, hi = 0, inst.contract.edits
    while lo < hi:
        mid = (lo + hi) // 2
        cert = envelope(replace(inst, contract=inst.contract.with_edits(mid)))
        if contained_prefix(cert, windows):
            lo = mid + 1
        else:
            hi = mid
    target = replace(inst, contract=inst.contract.with_edits(lo))
    cert = envelope(target)
    for j, (row, window) in enumerate(zip(cert["segments"], windows)):
        if row is not None and row["lower"] < window[0]:
            side, witness = "below", row["min_witness"]
            break
        if row is not None and row["upper"] > window[1]:
            side, witness = "above", row["max_witness"]
            break
    else:
        raise AssertionError("prefix bisection lost its violating endpoint")
    previous = None
    if lo:
        previous = envelope(replace(inst, contract=inst.contract.with_edits(lo - 1)))
    return {
        "kind": "violation",
        "schedule": SCHEDULE,
        "edits": lo,
        "segment": j,
        "side": side,
        "witness": witness,
        "previous_certificate": previous,
    }


def materialize_prefix_witness(inst: Instance, wrapped: dict,
                               limit: int = 100000) -> dict:
    """Expand an endpoint or replay-prefix count witness into explicit keys."""
    if type(wrapped) is not dict or wrapped.get("kind") not in {"endpoint", "prefix"}:
        raise ValueError("invalid wrapped replay witness")
    if wrapped["kind"] == "endpoint":
        if set(wrapped) != {"kind", "witness"}:
            raise ValueError("unexpected endpoint wrapper fields")
        result = materialize_witness(inst, wrapped["witness"], limit)
        result["phase"] = "final"
        return result

    if set(wrapped) != {"kind", "phase", "witness"}:
        raise ValueError("unexpected prefix wrapper fields")

    from .prefix_checker import prefix_witness_ok
    phase = wrapped.get("phase")
    witness = wrapped.get("witness")
    prefix_witness_ok(inst, phase, witness)
    x = witness["x"]
    left = bisect_left(inst.keys, x)
    if witness["size"] + len(inst.keys) > limit:
        raise ValueError("literal replay witness expansion exceeds the explicit output limit")

    keep = list(inst.keys[:witness["old_left"]])
    if witness["old_self"]:
        keep.append(x)
    right_start = left + 1
    keep += list(inst.keys[right_start:right_start + witness["old_right"]])

    def holes(lo: int, hi: int, count: int) -> list[int]:
        chosen: list[int] = []
        p = lo
        k = bisect_left(inst.keys, lo)
        while len(chosen) < count:
            next_old = inst.keys[k] if k < len(inst.keys) else hi + 1
            end = min(hi, next_old - 1)
            take = min(count - len(chosen), max(0, end - p + 1))
            chosen.extend(range(p, p + take))
            p += take
            if len(chosen) == count:
                break
            if next_old > hi:
                raise ValueError("prefix count witness exceeds hole capacity")
            p, k = next_old + 1, k + 1
        return chosen

    keep += holes(inst.lo, x - 1, witness["new_left"])
    keep += holes(x + 1, inst.hi, witness["new_right"])
    final = sorted(keep)
    source = set(inst.keys)
    target = set(final)
    deletes = sorted(source - target)
    inserts = sorted(target - source)
    if phase == "initial":
        active = list(inst.keys)
    elif witness["old_self"]:
        active = sorted(source - set(deletes))
    else:
        removed = {k for k in deletes if k < x}
        active = sorted(source - removed)
    rank = bisect_left(active, x)
    if x not in active or rank != witness["rank"]:
        raise AssertionError("materialized replay prefix does not attain the witness rank")
    return {
        "phase": phase,
        "active_prefix_keys": active,
        "query": x,
        "rank": rank,
        "final_keys": final,
        "delete_ascending": deletes,
        "insert_ascending": inserts,
        "net_edits": len(deletes) + len(inserts),
    }
