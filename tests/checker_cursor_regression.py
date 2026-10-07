"""Untimed, portable literal-set/replay regression; optional original-source comparison.

No closed-form oracle helpers, private paths, resource substitutions or subprocesses.
The default command needs only the current artifact and Python's standard library.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import driftcert as current

BEFORE = None
COUNTS = {'instances': 0, 'literal_final_sets': 0, 'literal_replay_states': 0,
          'observations': 0, 'original_comparisons': 0}

def outcome(fn, *args):
    try:
        return ('return', fn(*args))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return ('error', type(exc).__name__, str(exc))

def observe(name, inst, packet, windows=None):
    args = (inst, packet) if windows is None else (inst, windows, packet)
    value = outcome(getattr(current, name), *args)
    COUNTS['observations'] += 1
    if BEFORE is not None:
        old_inst = BEFORE.Instance(inst.lo, inst.hi, inst.keys,
            tuple(BEFORE.Segment(s.lo, s.hi, s.a, s.b, s.q) for s in inst.segments),
            BEFORE.Contract(inst.contract.insert, inst.contract.delete, inst.contract.edits,
                            inst.contract.size_lo, inst.contract.size_hi))
        old_args = (old_inst, packet) if windows is None else (old_inst, windows, packet)
        assert value == outcome(getattr(BEFORE, name), *old_args), (name, inst, packet, value)
        COUNTS['original_comparisons'] += 1
    return value

def literal(inst):
    """Enumerate actual sets, then perform the declared deletions and insertions."""
    width = inst.hi - inst.lo + 1
    assert width <= 6
    source, c = set(inst.keys), inst.contract
    final_rows = [[] for _ in inst.segments]
    replay_rows = [[] for _ in inst.segments]
    for mask in range(1 << width):
        target = {inst.lo + k for k in range(width) if mask & (1 << k)}
        i, d = len(target - source), len(source - target)
        if not (i <= c.insert and d <= c.delete and i+d <= c.edits
                and c.size_lo <= len(target) <= c.size_hi):
            continue
        COUNTS['literal_final_sets'] += 1
        states, active = [set(source)], set(source)
        for x in sorted(source - target):
            active.remove(x); states.append(set(active))
        for x in sorted(target - source):
            active.add(x); states.append(set(active))
        COUNTS['literal_replay_states'] += len(states)
        for rows, sets in ((final_rows, [target]), (replay_rows, states)):
            for state in sets:
                for rank, x in enumerate(sorted(state)):
                    j = next(j for j, seg in enumerate(inst.segments) if seg.lo <= x <= seg.hi)
                    seg = inst.segments[j]
                    rows[j].append(rank - (seg.a*x + seg.b)//seg.q)
    return [[None if not xs else (min(xs), max(xs)) for xs in rows]
            for rows in (final_rows, replay_rows)]

def mutations(packet):
    yield {}
    p = copy.deepcopy(packet); p['extra'] = 0; yield p
    if 'schedule' in packet:
        p = copy.deepcopy(packet); p['schedule'] = 'insert-first'; yield p
    for j, row in enumerate(packet['segments']):
        if row is None:
            continue
        p = copy.deepcopy(packet); p['segments'][j] = None; yield p
        for field in ('lower', 'upper'):
            for value in (True, 0.5, 1 << 1024):
                p = copy.deepcopy(packet); p['segments'][j][field] = value; yield p
        p = copy.deepcopy(packet); p['segments'][j]['lower'] -= 1; yield p
        p = copy.deepcopy(packet); p['segments'][j]['upper'] += 1; yield p

class CursorTests(unittest.TestCase):
    def test_literal_boundaries_parity_vacuity_and_replay(self):
        for width in range(1, 6):
            lo, hi = -3, width - 4
            for mask in range(1 << width):
                keys = tuple(lo+k for k in range(width) if mask & (1 << k))
                n = len(keys)
                segments = (current.Segment(lo, hi, -1, 2, 2),) if width == 1 else (
                    current.Segment(lo, lo, 0, 0, 1), current.Segment(lo+1, hi, 3, -2, 2))
                bands = ((0, width), (0, 0), (n, n))
                for insert, delete, edits in ((0, 0, 0), (0, width, width),
                                               (1, 1, 1), (1, 1, 2)):
                    for size_lo, size_hi in bands:
                        inst = current.Instance(lo, hi, keys, segments,
                            current.Contract(insert, delete, edits, size_lo, size_hi))
                        expected = literal(inst)
                        COUNTS['instances'] += 1
                        for producer, checker, rows in ((current.produce, 'check', expected[0]),
                                                       (current.produce_prefix, 'check_prefix', expected[1])):
                            packet, _ = producer(inst)
                            actual = [None if r is None else (r['lower'], r['upper'])
                                      for r in packet['segments']]
                            self.assertEqual(actual, rows)
                            self.assertEqual(observe(checker, inst, packet)[0], 'return')
                            for mutant in mutations(packet):
                                self.assertEqual(observe(checker, inst, mutant)[0], 'error')
                        windows = [[-1, 1] for _ in segments]
                        for producer, checker in ((current.shortest, 'check_shortest'),
                                                  (current.shortest_bisection, 'check_shortest'),
                                                  (current.shortest_prefix_bisection, 'check_prefix_shortest')):
                            packet = producer(inst, windows)
                            self.assertEqual(observe(checker, inst, packet, windows)[0], 'return')

    def test_large_coordinates_and_invalid_admission(self):
        inst = current.Instance(-(1 << 63), (1 << 64)-1, (-(1 << 63), 0, (1 << 64)-1),
            (current.Segment(-(1 << 63), (1 << 64)-1, -1, 1 << 100, 3),),
            current.Contract(1, 1, 2, 2, 4))
        for producer, checker in ((current.produce, 'check'), (current.produce_prefix, 'check_prefix')):
            packet, _ = producer(inst)
            self.assertEqual(observe(checker, inst, packet)[0], 'return')
        for keys in ((0, 0), (1, 0), (inst.lo-1,), (True,)):
            bad = current.Instance(inst.lo, inst.hi, keys, inst.segments, inst.contract)
            self.assertEqual(observe('check', bad, {})[0], 'error')

    def test_no_cell_start_binary_search(self):
        import driftcert.checker as checker
        inst = current.Instance(0, 127, tuple(range(0, 128, 2)),
            (current.Segment(0, 127, 0, 0, 1),), current.Contract(0, 0, 0, 64, 64))
        packet, _ = current.produce(inst)
        original, calls = checker.bisect_left, []
        def counted(*args):
            calls.append(args[1]); return original(*args)
        checker.bisect_left = counted
        try:
            result = current.check(inst, packet)
        finally:
            checker.bisect_left = original
        self.assertEqual(len(calls), 4)  # Two witnesses plus two segment boundaries.
        self.assertEqual(result['eligible_cells'], 64)
        self.assertEqual(observe('check', inst, packet), ('return', result))

if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Assertions must be enabled; do not use -O')
    parser = argparse.ArgumentParser()
    parser.add_argument('--before-artifact', type=Path, help='Optional original artifact root for exact differential')
    args = parser.parse_args()
    if args.before_artifact:
        package = args.before_artifact.resolve() / 'src' / 'driftcert'
        spec = importlib.util.spec_from_file_location('cursor_original', package / '__init__.py',
                                                     submodule_search_locations=[str(package)])
        BEFORE = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = BEFORE
        spec.loader.exec_module(BEFORE)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CursorTests))
    print(json.dumps(COUNTS, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
