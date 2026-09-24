"""Separately implemented exact checker.

Shares only typed input parsing with the producer. It does not import certificate,
rank_band, eligible_sizes, overlap_floor, or atoms. Enclosures are checked using
integer linear inequalities, not the producer's floor-and-extremize procedure.
This separation is not independent authorship or a mechanized general proof.
"""
from __future__ import annotations
from dataclasses import replace
from bisect import bisect_left
from .model import Instance


class Reject(ValueError):
    pass


def number(value: object) -> int:
    if type(value) is not int or value.bit_length() > 1024:
        raise Reject('invalid or oversized certificate integer')
    return value


def witness_ok(inst: Instance, w: dict) -> tuple[int, int, int]:
    fields = {'x', 'size', 'rank', 'old_left', 'new_left', 'old_right', 'new_right'}
    if type(w) is not dict or set(w) != fields:
        raise Reject('unexpected witness fields')
    for v in w.values():
        number(v)
    x, m, r = w['x'], w['size'], w['rank']
    if not inst.lo <= x <= inst.hi:
        raise Reject('witness query outside universe')
    n = len(inst.keys)
    at = bisect_left(inst.keys, x)
    s = int(at < n and inst.keys[at] == x)
    capacities = (at, x - inst.lo - at,
                  n - s - at, inst.hi - x - (n - s - at))
    counts = tuple(w[k] for k in ('old_left', 'new_left', 'old_right', 'new_right'))
    if any(v < 0 or v > cap for v, cap in zip(counts, capacities)):
        raise Reject('witness exceeds a category capacity')
    if counts[0] + counts[1] != r or sum(counts) + 1 != m:
        raise Reject('witness rank/cardinality disagreement')
    old_count = counts[0] + counts[2] + s
    d, i = n - old_count, m - old_count
    c = inst.contract
    if not (0 <= d <= c.delete and 0 <= i <= c.insert and d + i <= c.edits
            and c.size_lo <= m <= c.size_hi):
        raise Reject('witness violates trusted update contract')
    return x, r, d + i


def check(inst: Instance, cert: dict) -> dict:
    inst.validate()
    if type(cert) is not dict or set(cert) != {'segments'} or type(cert['segments']) is not list:
        raise Reject('invalid certificate shape')
    rows = cert['segments']
    if len(rows) != len(inst.segments):
        raise Reject('omitted or extra predictor segment')
    n, c = len(inst.keys), inst.contract
    u = inst.hi - inst.lo + 1
    base_low = max(1, c.size_lo, n - c.delete, n - c.edits)
    base_high = min(u, c.size_hi, n + c.insert, n + c.edits)
    inequalities = cells = 0
    for j, (seg, row) in enumerate(zip(inst.segments, rows)):
        if row is not None:
            if type(row) is not dict or set(row) != {'lower', 'upper', 'min_witness', 'max_witness'}:
                raise Reject('unexpected segment certificate fields')
            low, high = number(row['lower']), number(row['upper'])
            if low > high:
                raise Reject('reversed residual enclosure')
            for field, claimed in (('min_witness', low), ('max_witness', high)):
                x, r, _ = witness_ok(inst, row[field])
                if not seg.lo <= x <= seg.hi or r - (seg.a * x + seg.b) // seg.q != claimed:
                    raise Reject('claimed extremum lacks an attaining witness')
        seen = False
        # Independent domain decomposition: cut at each old key and its successor.
        begin = bisect_left(inst.keys, seg.lo)
        end = bisect_left(inst.keys, seg.hi + 1)
        cuts = {seg.lo, seg.hi + 1}
        for x in inst.keys[begin:end]:
            cuts.add(x)
            cuts.add(x + 1)
        ordered = sorted(cuts)
        for a, after in zip(ordered, ordered[1:]):
            b = after - 1
            at = bisect_left(inst.keys, a)
            s = int(at < n and inst.keys[at] == a)
            ml, mh = base_low, base_high
            if not s:
                if c.insert == 0 or n == u:
                    continue
                ml = max(ml, n - c.delete + 1, n - c.edits + 2)
            if ml > mh:
                continue
            seen = True
            if row is None:
                raise Reject('eligible keys hidden by an empty certificate')
            # Recompute required overlap directly from insertion/deletion/edit constraints.
            kl = max(0, n - c.delete, ml - c.insert, -(-(n + ml - c.edits) // 2))
            kh = max(0, n - c.delete, mh - c.insert, -(-(n + mh - c.edits) // 2))
            # Lower rank is max(C, x+offset); upper rank is min(H, x-domain_lo).
            constant_low, offset_low = max(0, at + kl - n), ml - 1 - inst.hi
            constant_high = min(mh - 1, mh - 1 - kh + at + s)
            t_low, t_high = constant_low - offset_low, constant_high + inst.lo
            branches = [
                ('lower', a, min(b, t_low), 0, constant_low),
                ('lower', max(a, t_low + 1), b, 1, offset_low),
                ('upper', a, min(b, t_high), 1, -inst.lo),
                ('upper', max(a, t_high + 1), b, 0, constant_high),
            ]
            for kind, l, h, slope, intercept in branches:
                if l > h:
                    continue
                for x in (l, h):
                    numerator = seg.a * x + seg.b
                    bound = slope * x + intercept
                    if kind == 'lower':
                        # floor(numerator/q) <= bound-low, exactly including strictness.
                        if numerator > seg.q * (bound - low + 1) - 1:
                            raise Reject('lower enclosure fails an integer-linear obligation')
                    else:
                        # floor(numerator/q) >= bound-high.
                        if numerator < seg.q * (bound - high):
                            raise Reject('upper enclosure fails an integer-linear obligation')
                    inequalities += 1
            cells += 1
        if (row is not None) != seen:
            raise Reject('nonempty certificate for a vacuous segment')
    return {'accepted': True, 'eligible_cells': cells, 'linear_inequalities': inequalities}


def check_shortest(inst: Instance, windows: list[list[int]], obj: dict) -> bool:
    inst.validate()
    if type(windows) is not list or len(windows) != len(inst.segments):
        raise Reject('window count mismatch')
    for w in windows:
        if type(w) is not list or len(w) != 2 or number(w[0]) > number(w[1]):
            raise Reject('invalid requested window')
    def safety(cert: dict, target: Instance) -> None:
        check(target, cert)
        for w, row in zip(windows, cert['segments']):
            if row is not None and not (w[0] <= row['lower'] and row['upper'] <= w[1]):
                raise Reject('lower-budget certificate does not establish safety')
    if type(obj) is not dict:
        raise Reject('malformed shortest-witness object')
    if obj.get('kind') == 'safe':
        if set(obj) != {'kind', 'certificate'}:
            raise Reject('unexpected safe result fields')
        safety(obj['certificate'], inst)
        return True
    if set(obj) != {'kind', 'edits', 'segment', 'side', 'witness', 'previous_certificate'} or obj.get('kind') != 'violation':
        raise Reject('invalid violation object')
    b, j = number(obj['edits']), number(obj['segment'])
    if not (0 <= b <= inst.contract.edits and 0 <= j < len(inst.segments)):
        raise Reject('invalid minimum cost or segment')
    target = replace(inst, contract=inst.contract.with_edits(b))
    x, r, actual = witness_ok(target, obj['witness'])
    seg = inst.segments[j]
    if not seg.lo <= x <= seg.hi or actual != b:
        raise Reject('witness does not attain the claimed edit minimum')
    residual = r - (seg.a * x + seg.b) // seg.q
    if obj['side'] == 'below':
        good = residual < windows[j][0]
    elif obj['side'] == 'above':
        good = residual > windows[j][1]
    else:
        good = False
    if not good:
        raise Reject('witness does not violate the requested window')
    if b:
        safety(obj['previous_certificate'], replace(inst, contract=inst.contract.with_edits(b - 1)))
    elif obj['previous_certificate'] is not None:
        raise Reject('zero-cost violation cannot have a negative-budget predecessor')
    return True
