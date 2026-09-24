"""Independent checker for canonical ordered-replay certificates."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import replace

from .checker import Reject, check, number, witness_ok
from .model import Instance
from .prefix import SCHEDULE


def prefix_witness_ok(inst: Instance, phase: object, w: object) -> tuple[int, int, int]:
    fields = {"x", "size", "overlap", "rank", "old_left", "old_self",
              "old_right", "new_left", "new_right"}
    if phase not in {"initial", "deletion-min"}:
        raise Reject("unknown replay witness phase")
    if type(w) is not dict or set(w) != fields:
        raise Reject("unexpected replay witness fields")
    for value in w.values():
        number(value)
    x = w["x"]
    if not inst.lo <= x <= inst.hi:
        raise Reject("replay witness query outside universe")
    n = len(inst.keys)
    left = bisect_left(inst.keys, x)
    if left >= n or inst.keys[left] != x:
        raise Reject("replay-only witness query is not an old key")
    left_holes = x - inst.lo - left
    right_holes = inst.hi - x - (n - left - 1)
    capacities = (left, 1, n - left - 1, left_holes, right_holes)
    counts = (w["old_left"], w["old_self"], w["old_right"],
              w["new_left"], w["new_right"])
    if w["old_self"] not in {0, 1}:
        raise Reject("old-self indicator is not Boolean")
    if any(value < 0 or value > cap for value, cap in zip(counts, capacities)):
        raise Reject("replay witness exceeds a category capacity")
    overlap = w["old_left"] + w["old_self"] + w["old_right"]
    size = overlap + w["new_left"] + w["new_right"]
    if overlap != w["overlap"] or size != w["size"]:
        raise Reject("replay witness size or overlap disagreement")
    expected_rank = left if phase == "initial" else w["old_left"]
    if w["rank"] != expected_rank:
        raise Reject("replay witness rank disagrees with its phase")
    c = inst.contract
    deletes = n - overlap
    inserts = size - overlap
    if not (deletes <= c.delete and inserts <= c.insert and deletes + inserts <= c.edits
            and c.size_lo <= size <= c.size_hi):
        raise Reject("replay witness violates trusted update contract")
    return x, w["rank"], deletes + inserts


def _wrapped_witness_ok(inst: Instance, wrapped: object, segment: int,
                        claimed: int) -> tuple[int, int]:
    if type(wrapped) is not dict or wrapped.get("kind") not in {"endpoint", "prefix"}:
        raise Reject("invalid replay extremum witness wrapper")
    if wrapped["kind"] == "endpoint":
        if set(wrapped) != {"kind", "witness"}:
            raise Reject("unexpected endpoint wrapper fields")
        x, rank, edits = witness_ok(inst, wrapped["witness"])
    else:
        if set(wrapped) != {"kind", "phase", "witness"}:
            raise Reject("unexpected prefix wrapper fields")
        x, rank, edits = prefix_witness_ok(inst, wrapped["phase"], wrapped["witness"])
    seg = inst.segments[segment]
    if not seg.lo <= x <= seg.hi or rank - seg.predict(x) != claimed:
        raise Reject("replay extremum witness does not attain the claimed residual")
    return x, edits


def check_prefix(inst: Instance, cert: object) -> dict:
    inst.validate()
    if type(cert) is not dict or set(cert) != {"schedule", "endpoint", "segments"}:
        raise Reject("invalid replay certificate shape")
    if cert["schedule"] != SCHEDULE:
        raise Reject("unsupported replay schedule")
    endpoint_stats = check(inst, cert["endpoint"])
    rows = cert["segments"]
    if type(rows) is not list or len(rows) != len(inst.segments):
        raise Reject("replay certificate segment count mismatch")

    n = len(inst.keys)
    u = inst.hi - inst.lo + 1
    c = inst.contract
    size_lo = max(c.size_lo, 0, n - c.delete, n - c.edits)
    size_hi = min(c.size_hi, u, n + c.insert, n + c.edits)
    expected: list[list[int] | None] = []
    for row in cert["endpoint"]["segments"]:
        expected.append(None if row is None else [row["lower"], row["upper"]])

    old_checks = 0
    if size_lo <= size_hi:
        overlap = max(0, n - c.delete, size_lo - c.insert,
                      (n + size_lo - c.edits + 1) // 2,
                      size_lo - (u - n))
        if overlap > min(n, size_lo):
            raise Reject("replay family feasibility arithmetic is inconsistent")
        segment = 0
        for left, x in enumerate(inst.keys):
            while x > inst.segments[segment].hi:
                segment += 1
            prediction = inst.segments[segment].predict(x)
            low = max(0, overlap - (n - left)) - prediction
            high = left - prediction
            if expected[segment] is None:
                expected[segment] = [low, high]
            else:
                expected[segment][0] = min(expected[segment][0], low)
                expected[segment][1] = max(expected[segment][1], high)
            old_checks += 1

    for j, (row, want) in enumerate(zip(rows, expected)):
        if want is None:
            if row is not None:
                raise Reject("nonempty replay segment for a vacuous trace family")
            continue
        if type(row) is not dict or set(row) != {"lower", "upper", "min_witness", "max_witness"}:
            raise Reject("unexpected replay segment fields")
        lower, upper = number(row["lower"]), number(row["upper"])
        if [lower, upper] != want:
            raise Reject("replay enclosure is not the exact independently derived envelope")
        _wrapped_witness_ok(inst, row["min_witness"], j, lower)
        _wrapped_witness_ok(inst, row["max_witness"], j, upper)
    return {
        "accepted": True,
        "endpoint_eligible_cells": endpoint_stats["eligible_cells"],
        "endpoint_linear_inequalities": endpoint_stats["linear_inequalities"],
        "old_key_obligations": old_checks,
    }


def _window_check(inst: Instance, windows: object) -> list[list[int]]:
    if type(windows) is not list or len(windows) != len(inst.segments):
        raise Reject("window count mismatch")
    for window in windows:
        if type(window) is not list or len(window) != 2:
            raise Reject("invalid replay window")
        if number(window[0]) > number(window[1]):
            raise Reject("reversed replay window")
    return windows


def check_prefix_shortest(inst: Instance, windows: object, obj: object) -> bool:
    inst.validate()
    windows = _window_check(inst, windows)

    def safety(cert: object, target: Instance) -> None:
        check_prefix(target, cert)
        for window, row in zip(windows, cert["segments"]):
            if row is not None and not (window[0] <= row["lower"] and row["upper"] <= window[1]):
                raise Reject("predecessor replay certificate does not establish safety")

    if type(obj) is not dict:
        raise Reject("malformed replay minimum object")
    if obj.get("kind") == "safe":
        if set(obj) != {"kind", "certificate"}:
            raise Reject("unexpected safe replay result fields")
        safety(obj["certificate"], inst)
        return True
    required = {"kind", "edits", "segment", "side", "witness", "previous_certificate"}
    if set(obj) != required or obj.get("kind") != "violation":
        raise Reject("invalid replay violation object")
    budget, segment = number(obj["edits"]), number(obj["segment"])
    if not (0 <= budget <= inst.contract.edits and 0 <= segment < len(inst.segments)):
        raise Reject("invalid replay minimum budget or segment")
    target = replace(inst, contract=inst.contract.with_edits(budget))
    # Validate the complete exact target certificate implicitly through the witness and predecessor.
    wrapped = obj["witness"]
    if type(wrapped) is not dict or wrapped.get("kind") not in {"endpoint", "prefix"}:
        raise Reject("invalid replay violating witness")
    if wrapped["kind"] == "endpoint":
        x, rank, actual = witness_ok(target, wrapped.get("witness"))
    else:
        x, rank, actual = prefix_witness_ok(target, wrapped.get("phase"), wrapped.get("witness"))
    if actual != budget:
        raise Reject("replay witness does not attain the claimed minimum budget")
    seg = target.segments[segment]
    if not seg.lo <= x <= seg.hi:
        raise Reject("replay witness routed to the wrong segment")
    residual = rank - seg.predict(x)
    if obj["side"] == "below":
        violating = residual < windows[segment][0]
    elif obj["side"] == "above":
        violating = residual > windows[segment][1]
    else:
        violating = False
    if not violating:
        raise Reject("replay witness does not violate the requested window")
    if budget:
        safety(obj["previous_certificate"], replace(inst, contract=inst.contract.with_edits(budget - 1)))
    elif obj["previous_certificate"] is not None:
        raise Reject("zero-budget replay violation cannot have a predecessor")
    return True
