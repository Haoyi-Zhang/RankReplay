"""Extremum producer and shortest net-edit witnesses.

The verifier is in checker.py and does not call the extremum producer.
"""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import replace
from .model import Instance, Contract, atoms, eligible_sizes, overlap_floor


def count_witness(inst: Instance, x: int, size: int, rank: int,
                  left: int | None = None, old: int | None = None) -> dict:
    n = len(inst.keys)
    if left is None:
        left = bisect_left(inst.keys, x)
    if old is None:
        old = int(left < n and inst.keys[left] == x)
    ol = min(left, rank)
    oright = min(n - old - left, size - 1 - rank)
    return {'x': x, 'size': size, 'rank': rank,
            'old_left': ol, 'new_left': rank - ol,
            'old_right': oright, 'new_right': size - 1 - rank - oright}


def produce(inst: Instance) -> tuple[dict, dict]:
    inst.validate()
    c, n = inst.contract, len(inst.keys)
    sizes = {s: eligible_sizes(inst, bool(s)) for s in (0, 1)}
    thresholds = {}
    for old, interval in sizes.items():
        if interval is not None:
            ml, mh = interval
            thresholds[old] = (ml, mh, overlap_floor(n, ml, c), overlap_floor(n, mh, c))
    rows: list[dict | None] = [None] * len(inst.segments)
    evaluations = cell_count = 0
    for j, a, b, left, old in atoms(inst):
        cell_count += 1
        if sizes[old] is None:
            continue
        ml, mh, kl, kh = thresholds[old]
        low_const = max(0, left + kl - n)
        high_const = min(mh - 1, mh - 1 - kh + left + old)
        # Within a gap the rank bounds each have one integer hinge.
        low_hinge = inst.hi - ml + 1 + low_const
        high_hinge = inst.lo + high_const
        candidates = sorted({a, b, max(a, min(b, low_hinge)), max(a, min(b, high_hinge))})
        s = inst.segments[j]
        for x in candidates:
            lower = max(low_const, ml - 1 - inst.hi + x)
            upper = min(high_const, x - inst.lo)
            pred = s.predict(x)
            lo, hi = lower - pred, upper - pred
            row = rows[j]
            if row is None:
                rows[j] = {'lower': lo, 'upper': hi,
                           'min_witness': count_witness(inst, x, ml, lower, left, old),
                           'max_witness': count_witness(inst, x, mh, upper, left, old)}
            else:
                if lo < row['lower']:
                    row['lower'], row['min_witness'] = lo, count_witness(inst, x, ml, lower, left, old)
                if hi > row['upper']:
                    row['upper'], row['max_witness'] = hi, count_witness(inst, x, mh, upper, left, old)
            evaluations += 1
    return {'segments': rows}, {'atoms': cell_count, 'candidate_evaluations': evaluations}


def contained(cert: dict, windows: list[list[int]]) -> bool:
    return all(row is None or (w[0] <= row['lower'] and row['upper'] <= w[1])
               for row, w in zip(cert['segments'], windows))


def _window_check(inst: Instance, windows: list[list[int]]) -> None:
    if type(windows) is not list or len(windows) != len(inst.segments):
        raise ValueError('one window is required per predictor segment')
    for w in windows:
        if type(w) is not list or len(w) != 2 or any(type(x) is not int or x.bit_length() > 1024 for x in w) or w[0] > w[1]:
            raise ValueError('invalid closed residual window')


def shortest_bisection(inst: Instance, windows: list[list[int]], metrics: dict | None = None) -> dict:
    """A replayable optimum: a witness at b and an exact safety certificate at b-1."""
    inst.validate()
    _window_check(inst, windows)
    if metrics is not None:
        metrics.update(envelope_calls=0, envelope_candidates=0)
    def envelope(target: Instance):
        result, measured = produce(target)
        if metrics is not None:
            metrics['envelope_calls'] += 1
            metrics['envelope_candidates'] += measured['candidate_evaluations']
        return result, measured
    top, _ = envelope(inst)
    if contained(top, windows):
        return {'kind': 'safe', 'certificate': top}
    lo, hi = 0, inst.contract.edits
    calls = 1
    while lo < hi:
        mid = (lo + hi) // 2
        candidate = replace(inst, contract=inst.contract.with_edits(mid))
        cert, _ = envelope(candidate)
        calls += 1
        if contained(cert, windows):
            lo = mid + 1
        else:
            hi = mid
    current = replace(inst, contract=inst.contract.with_edits(lo))
    cert, _ = envelope(current)
    for j, (row, w) in enumerate(zip(cert['segments'], windows)):
        if row is not None and row['lower'] < w[0]:
            side, witness = 'below', row['min_witness']
            break
        if row is not None and row['upper'] > w[1]:
            side, witness = 'above', row['max_witness']
            break
    else:
        raise AssertionError('bisection lost its violating upper endpoint')
    previous = None
    if lo:
        previnst = replace(inst, contract=inst.contract.with_edits(lo - 1))
        previous, _ = envelope(previnst)
    return {'kind': 'violation', 'edits': lo, 'segment': j, 'side': side,
            'witness': witness, 'previous_certificate': previous}


def materialize_witness(inst: Instance, witness: dict, limit: int = 100000) -> dict:
    """Expand a count witness only when its final set and edit trace are small.

    Large proofs remain valid compact count witnesses; no huge domain is scanned.
    """
    from .checker import witness_ok
    witness_ok(inst, witness)
    x, m = witness['x'], witness['size']
    if m + len(inst.keys) > limit:
        raise ValueError('literal witness expansion exceeds the explicit output limit')
    left = bisect_left(inst.keys, x)
    old = left < len(inst.keys) and inst.keys[left] == x
    keep = list(inst.keys[:witness['old_left']])
    right_start = left + int(old)
    keep += list(inst.keys[right_start:right_start + witness['old_right']])
    keep.append(x)

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
                raise ValueError('count witness exceeds hole capacity')
            p, k = next_old + 1, k + 1
        return chosen

    keep += holes(inst.lo, x - 1, witness['new_left'])
    keep += holes(x + 1, inst.hi, witness['new_right'])
    final = sorted(keep)
    if len(final) != m or len(set(final)) != m:
        raise ValueError('invalid witness expansion')
    s, t = set(inst.keys), set(final)
    delete, insert = sorted(s - t), sorted(t - s)
    return {'final_keys': final, 'delete_ascending': delete, 'insert_ascending': insert,
            'net_edits': len(delete) + len(insert)}


def _comparison_candidates(a: int, b: int, integer_lines: list[tuple[int, int]],
                           numerator: tuple[int, int, int], shift: int) -> list[int]:
    """Endpoints of cells with fixed weak ordering of seven integer lines and
    one floor-affine function. There are at most 114 candidate points per side and atom.

    Both <= orientations are included so equality plateaus are separate cells.
    The bit lengths, not the magnitude of the coordinate interval, determine the
    cost of division. This is not floating-point line intersection.
    """
    aa, bb, qq = numerator
    cuts = {a, b + 1}

    def add_cut(d: int, e: int) -> None:
        # Truth of d*x <= e changes at one integer cut, or is constant.
        if d > 0:
            t = e // d + 1
        elif d < 0:
            t = -((-e) // d)
        else:
            return
        if a < t <= b:
            cuts.add(t)

    for i, (s, t) in enumerate(integer_lines):
        for v, w in integer_lines[i + 1:]:
            add_cut(s - v, w - t)
            add_cut(v - s, t - w)
        # floor((aa*x+bb)/qq)+shift <= s*x+t
        add_cut(aa - qq * s, qq * (t - shift + 1) - 1 - bb)
        # s*x+t <= floor((aa*x+bb)/qq)+shift
        add_cut(qq * s - aa, bb - qq * (t - shift))
    ordered = sorted(cuts)
    return sorted({x for l, h in zip(ordered, ordered[1:]) for x in (l, h - 1)})


def direct_minimum(inst: Instance, windows: list[list[int]]) -> tuple[dict | None, dict]:
    """Minimize net edits with I,D and the cardinality band fixed, ignoring B.

    The caller compares the returned minimum against B. Every positive result
    can be checked using the independently constructed safety proof at cost b-1.
    No dynamic program or enumeration over cardinalities or budgets is used.
    """
    inst.validate()
    _window_check(inst, windows)
    n, c = len(inst.keys), inst.contract
    relaxed = replace(c, edits=c.insert + c.delete)
    sizes = {s: eligible_sizes(inst, bool(s), relaxed) for s in (0, 1)}
    thresholds = {}
    for old, interval in sizes.items():
        if interval is not None:
            ml, mh = interval
            thresholds[old] = (ml, mh, overlap_floor(n, ml, relaxed), overlap_floor(n, mh, relaxed))
    best = None
    evaluations = atoms_seen = 0
    for j, a, b, left, old in atoms(inst):
        atoms_seen += 1
        if sizes[old] is None:
            continue
        ml, mh, kl, kh = thresholds[old]
        low_constant = max(0, left + kl - n)
        low_offset = ml - 1 - inst.hi
        high_constant = min(mh - 1, mh - 1 - kh + left + old)
        reserve = 1 - old
        seg = inst.segments[j]
        # The cost changes slope only at r=L and at these two translated
        # cardinality endpoints. Include them in the ordering arrangement.
        lines = [(0, low_constant), (1, low_offset),
                 (0, high_constant), (1, -inst.lo), (0, left),
                 (0, left + c.size_lo - n - reserve),
                 (0, left + c.size_hi - n - reserve)]
        for side, shift in (('below', windows[j][0] - 1), ('above', windows[j][1] + 1)):
            points = _comparison_candidates(a, b, lines, (seg.a, seg.b, seg.q), shift)
            for x in points:
                evaluations += 1
                lower = max(low_constant, x + low_offset)
                upper = min(high_constant, x - inst.lo)
                threshold = seg.predict(x) + shift
                if side == 'below':
                    upper = min(upper, threshold)
                else:
                    lower = max(lower, threshold)
                if lower > upper:
                    continue
                rank = max(lower, min(upper, left))
                undisturbed_size = n + reserve + rank - left
                size = max(c.size_lo, min(c.size_hi, undisturbed_size))
                cost = reserve + abs(rank - left) + abs(size - undisturbed_size)
                if best is None or cost < best['edits']:
                    best = {'edits': cost, 'segment': j, 'side': side,
                            'witness': count_witness(inst, x, size, rank, left, old)}
    return best, {'atoms': atoms_seen, 'candidate_evaluations': evaluations}


def shortest(inst: Instance, windows: list[list[int]], metrics: dict | None = None) -> dict:
    """Single atom sweep for the minimum, plus a predecessor-budget certificate.

    Producer cost is O(n+p) exact-integer operations: a fixed-size comparison
    arrangement per atom, followed by at most one envelope construction. The
    independent checker remains comparison-based and is not claimed linear.
    """
    best, measured = direct_minimum(inst, windows)
    if metrics is not None:
        metrics.update(measured, envelope_calls=0, envelope_candidates=0)
    if best is None or best['edits'] > inst.contract.edits:
        cert, measured = produce(inst)
        if metrics is not None:
            metrics.update(envelope_calls=1, envelope_candidates=measured['candidate_evaluations'])
        return {'kind': 'safe', 'certificate': cert}
    b = best['edits']
    previous = None
    if b:
        previous, measured = produce(replace(inst, contract=inst.contract.with_edits(b - 1)))
        if metrics is not None:
            metrics.update(envelope_calls=1, envelope_candidates=measured['candidate_evaluations'])
    return {'kind': 'violation', **best, 'previous_certificate': previous}
