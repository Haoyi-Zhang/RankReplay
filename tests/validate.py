"""Deterministic validation against actual finite sets, never the envelope formula.

Each --universe chunk is resumable as a separate output. Production and checker
paths do not import this oracle. Running a command successfully is not a general
formal proof; the proof is supplied in proofs/theorems.md and in the paper.
"""
from __future__ import annotations
import sys, os, time, resource, json, argparse, itertools, random, copy
from pathlib import Path
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from driftcert import Instance, Segment, Contract, produce, shortest, shortest_bisection, check, check_shortest, materialize_witness, Reject
from driftcert.model import rank_band


def all_sets(u: int, offset: int = 0):
    return [tuple(offset + j for j in range(u) if mask >> j & 1) for mask in range(1 << u)]


def final_states(inst: Instance):
    c, s = inst.contract, set(inst.keys)
    for t in all_sets(inst.hi - inst.lo + 1, inst.lo):
        ss = set(t)
        i, d = len(ss - s), len(s - ss)
        if i <= c.insert and d <= c.delete and i + d <= c.edits and c.size_lo <= len(t) <= c.size_hi:
            yield t, i + d


def actual_envelope(inst: Instance):
    rows = [None] * len(inst.segments)
    count = 0
    for t, _ in final_states(inst):
        j = 0
        for r, x in enumerate(t):
            while x > inst.segments[j].hi:
                j += 1
            err = r - inst.segments[j].predict(x)
            if rows[j] is None:
                rows[j] = [err, err]
            else:
                rows[j] = [min(rows[j][0], err), max(rows[j][1], err)]
            count += 1
    return rows, count


def actual_minimum(inst: Instance, windows):
    best = None
    for t, cost in final_states(inst):
        if best is not None and cost >= best:
            continue
        j = 0
        for r, x in enumerate(t):
            while x > inst.segments[j].hi:
                j += 1
            err = r - inst.segments[j].predict(x)
            if not windows[j][0] <= err <= windows[j][1]:
                best = cost
                break
    return best


def overlap(u: int) -> dict:
    offset = -u // 2
    sets = all_sets(u, offset)
    checks = states = 0
    for s in sets:
        old = set(s)
        for m in range(u + 1):
            for k in range(min(len(s), m) + 1):
                matches = [t for t in sets if len(t) == m and len(old.intersection(t)) >= k]
                states += len(matches)
                inst = Instance(offset, offset + u - 1, s, (Segment(offset, offset + u - 1, 0, 0),),
                                Contract(m - k, len(s) - k, len(s) + m - 2 * k, m, m))
                for x in range(offset, offset + u):
                    rr = sorted({t.index(x) for t in matches if x in t})
                    actual = rank_band(inst, x)
                    assert bool(rr) == (actual is not None)
                    if rr:
                        assert rr == list(range(actual[0], actual[1] + 1)), (inst, x, rr, actual)
                    checks += 1
    return {'rank_queries': checks, 'admissible_set_occurrences': states,
            'all_intermediate_ranks_checked': True, 'mismatches': 0}


def budgets(u: int, start_set: int = 0, stop_set: int | None = None) -> dict:
    offset = -u // 2
    sets = all_sets(u, offset)
    contracts = queries = states = 0
    for s in sets[start_set:stop_set]:
        old = set(s)
        annotated = [(t, len(set(t) - old), len(old - set(t))) for t in sets]
        for i in range(u + 1):
            for d in range(u + 1):
                for b in range(2 * u + 1):
                    possible = [(t, ii, dd) for t, ii, dd in annotated if ii <= i and dd <= d and ii + dd <= b]
                    # All inclusive final-cardinality intervals, including empty final states.
                    for ml in range(u + 1):
                        for mh in range(ml, u + 1):
                            lo, hi = [None] * u, [None] * u
                            for t, _, _ in possible:
                                if not ml <= len(t) <= mh:
                                    continue
                                states += 1
                                for r, x in enumerate(t):
                                    p = x - offset
                                    lo[p] = r if lo[p] is None else min(lo[p], r)
                                    hi[p] = r if hi[p] is None else max(hi[p], r)
                            inst = Instance(offset, offset + u - 1, s, (Segment(offset, offset + u - 1, 0, 0),),
                                            Contract(i, d, b, ml, mh))
                            for x in range(offset, offset + u):
                                rr = rank_band(inst, x)
                                p = x - offset
                                assert (rr is None) == (lo[p] is None), (inst, x, rr, lo)
                                if rr is not None:
                                    assert rr[:2] == (lo[p], hi[p]), (inst, x, rr, lo[p], hi[p])
                                queries += 1
                            contracts += 1
    return {'contracts': contracts, 'rank_queries': queries,
            'admissible_set_occurrences': states, 'mismatches': 0}


def integration(u: int) -> dict:
    offset = -u // 2
    rng = random.Random(104729 + u)
    cases = queries = checked = witness_checks = mutation_rejections = 0
    slopes = [(-3, -2, 2), (0, 0, 1), (1, -1, 3), (1, 0, 1), (5, 2, 2)]
    for s in all_sets(u, offset):
        for rep in range(8):
            ml = rng.randrange(u + 1)
            mh = rng.randrange(ml, u + 1)
            c = Contract(rng.randrange(u + 1), rng.randrange(u + 1), rng.randrange(2 * u + 1), ml, mh)
            cuts = sorted({offset, offset + u, *(offset + rng.randrange(u + 1) for _ in range(3))})
            segments = []
            for a, b in zip(cuts, cuts[1:]):
                aa, bb, qq = slopes[(rep + a) % len(slopes)]
                segments.append(Segment(a, b - 1, aa, bb, qq))
            inst = Instance(offset, offset + u - 1, s, tuple(segments), c)
            cert, _ = produce(inst)
            check(inst, cert)
            actual, cnt = actual_envelope(inst)
            queries += cnt
            assert [None if row is None else [row['lower'], row['upper']] for row in cert['segments']] == actual
            checked += 1
            windows = [[0, 0] for _ in segments]
            for j, seg in enumerate(segments):
                residuals = [r - seg.predict(x) for r, x in enumerate(s) if seg.lo <= x <= seg.hi]
                if residuals:
                    windows[j] = [min(residuals), max(residuals)]
            # Both a source-valid window and a deliberately narrow arbitrary window.
            for w in (windows, [[-1, 1] for _ in segments]):
                result = shortest(inst, w)
                check_shortest(inst, w, result)
                binary = shortest_bisection(inst, w)
                check_shortest(inst, w, binary)
                assert (binary['kind'], binary.get('edits')) == (result['kind'], result.get('edits'))
                exact = actual_minimum(inst, w)
                assert (result['kind'] == 'safe') == (exact is None)
                if exact is not None:
                    assert result['edits'] == exact
                    literal = materialize_witness(inst, result['witness'])
                    assert literal['net_edits'] == exact
                    assert literal['final_keys'].index(result['witness']['x']) == result['witness']['rank']
                witness_checks += 1
            # Tightness is part of this certificate type: widening is rejected too.
            for j, row in enumerate(cert['segments']):
                if row is not None:
                    for field, delta in [('lower', 1), ('lower', -1), ('upper', 1), ('upper', -1)]:
                        mutant = copy.deepcopy(cert)
                        mutant['segments'][j][field] += delta
                        try:
                            check(inst, mutant)
                        except Reject:
                            mutation_rejections += 1
                        else:
                            raise AssertionError('changed exact endpoint was accepted')
                    break
            cases += 1
    return {'instances': cases, 'actual_present_key_queries': queries,
            'certificates_checked': checked, 'shortest_results_checked': witness_checks,
            'endpoint_mutants_rejected': mutation_rejections, 'mismatches': 0,
            'seed': 104729 + u}


def regression() -> dict:
    inst = Instance(0, 10, (0, 10), (Segment(0, 10, 1, 0, 2),), Contract(3, 1, 4, 4, 4))
    cert, stats = produce(inst)
    check(inst, cert)
    assert (cert['segments'][0]['lower'], cert['segments'][0]['upper']) == (-3, 2)
    endpoints = []
    for x in (0, 1, 9, 10):
        band = rank_band(inst, x)
        endpoints.append([band[0] - inst.segments[0].predict(x), band[1] - inst.segments[0].predict(x)])
    assert min(x[0] for x in endpoints) == -2 and max(x[1] for x in endpoints) == 1
    windows = [[-4, 0]]
    opt = shortest(inst, windows)
    check_shortest(inst, windows, opt)
    assert opt['edits'] == 2
    rejected = []
    mutations = {}
    m = copy.deepcopy(cert); m['segments'] = []; mutations['missing_segment'] = m
    m = copy.deepcopy(cert); m['segments'][0] = None; mutations['hidden_gap'] = m
    for name, field in [('forged_query','x'),('forged_size','size'),('forged_rank','rank'),('forged_old_count','old_left'),('forged_new_count','new_right')]:
        m = copy.deepcopy(cert); m['segments'][0]['max_witness'][field] += 100; mutations[name] = m
    m = copy.deepcopy(cert); m['segments'][0]['upper'] = True; mutations['boolean_endpoint'] = m
    m = copy.deepcopy(cert); m['segments'][0]['upper'] = 1.5; mutations['float_endpoint'] = m
    m = copy.deepcopy(cert); m['contract'] = {}; mutations['input_substitution_field'] = m
    m = copy.deepcopy(cert); m['segments'][0]['min_witness']['old_left'] = -1; mutations['negative_count'] = m
    m = copy.deepcopy(cert); m['segments'][0]['upper'] = 1; m['segments'][0]['max_witness'] = {'x': 1,'size':4,'rank':1,'old_left':1,'new_left':0,'old_right':1,'new_right':1}; mutations['endpoint_only_enclosure'] = m
    for name, m in mutations.items():
        try: check(inst, m)
        except Reject: rejected.append(name)
        else: raise AssertionError(name)
    shortest_mutants = []
    for field in ('edits', 'segment'):
        m = copy.deepcopy(opt); m[field] += 1; shortest_mutants.append(m)
    m = copy.deepcopy(opt); m['previous_certificate'] = cert; shortest_mutants.append(m)
    m = copy.deepcopy(opt); m['side'] = 'below'; shortest_mutants.append(m)
    m = copy.deepcopy(opt); m['witness']['new_left'] += 1; shortest_mutants.append(m)
    for m in shortest_mutants:
        try: check_shortest(inst, windows, m)
        except Reject: pass
        else: raise AssertionError('shortest-certificate mutation accepted')
    # Exact arithmetic at and above unsigned 64-bit endpoints, without scanning the domain.
    huge = Instance(-(1 << 63), (1 << 64) - 1,
                    (-(1 << 63), 0, (1 << 64) - 1),
                    (Segment(-(1 << 63), -1, -7, -(1 << 65), 3),
                     Segment(0, (1 << 64) - 1, 9, -11, 5)),
                    Contract(5, 3, 7, 1, 8))
    huge_cert, _ = produce(huge); check(huge, huge_cert)
    return {'regression_families': len(rejected) + len(shortest_mutants) + 2,
            'malformed_certificate_mutants_rejected': rejected,
            'shortest_mutants_rejected': len(shortest_mutants),
            'interior_hinge_negative_control': {'exact': [-3,2], 'endpoints_only': [-2,1]},
            'wide_integer_case': 'passed', 'mismatches': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['overlap','budgets','integration','regression'], required=True)
    p.add_argument('--universe', type=int, default=5)
    p.add_argument('--output', required=True)
    p.add_argument('--start-set', type=int, default=0)
    p.add_argument('--stop-set', type=int)
    args = p.parse_args()
    if not 1 <= args.universe <= 9:
        p.error('universe must be between 1 and 9')
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (3758096384,3758096384))
    start, cpu = time.monotonic(), time.process_time()
    if args.mode == 'budgets':
        stop = (1 << args.universe) if args.stop_set is None else args.stop_set
        if not 0 <= args.start_set < stop <= (1 << args.universe):
            p.error('invalid initial-set shard')
        result = budgets(args.universe, args.start_set, stop)
        result.update(initial_set_start=args.start_set, initial_set_stop=stop)
    else:
        result = regression() if args.mode == 'regression' else globals()[args.mode](args.universe)
    result.update(mode=args.mode, universe=args.universe, workers=1,
                  wall_seconds=time.monotonic()-start, cpu_seconds=time.process_time()-cpu,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
