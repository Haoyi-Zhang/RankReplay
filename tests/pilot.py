"""Exhaustive pilot: overlap reduction and exact rank attainability."""
from __future__ import annotations
import sys, json, time, resource, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from driftcert.model import Instance, Segment, Contract, rank_band


def main() -> None:
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (3758096384, 3758096384))
    start, cpu = time.monotonic(), time.process_time()
    checks = states = 0
    for u in range(1, 7):
        allsets = [tuple(i for i in range(u) if mask >> i & 1) for mask in range(1 << u)]
        for keys in allsets:
            n, sk = len(keys), set(keys)
            # This oracle enumerates actual final sets, not transport formulae.
            for m in range(u + 1):
                for k in range(min(n, m) + 1):
                    final = [t for t in allsets if len(t) == m and len(sk.intersection(t)) >= k]
                    states += len(final)
                    inst = Instance(0, u - 1, keys, (Segment(0, u - 1, 1, 0),),
                                    Contract(m - k, n - k, n + m - 2 * k, m, m))
                    inst.validate()
                    for x in range(u):
                        ranks = sorted({t.index(x) for t in final if x in t})
                        band = rank_band(inst, x)
                        assert (band is None) == (not ranks), (inst, x, ranks, band)
                        if ranks:
                            assert ranks == list(range(band[0], band[1] + 1)), (inst, x, ranks, band)
                        checks += 1
    # Negative controls: a future key consumes an insertion; keeping size costs a deletion too.
    inst = Instance(0, 4, (1, 3), (Segment(0, 4, 0, 0),), Contract(1, 1, 1, 2, 2))
    assert rank_band(inst, 2) is None
    inst2 = Instance(0, 4, (1, 3), (Segment(0, 4, 0, 0),), Contract(1, 1, 2, 2, 2))
    assert rank_band(inst2, 2)[:2] == (0, 1)
    result = {'test': 'pilot_exact_overlap', 'universe_sizes': [1, 2, 3, 4, 5, 6],
              'rank_queries_checked': checks, 'admissible_set_occurrences': states,
              'mismatches': 0, 'negative_controls': 2, 'negative_controls_passed': 2,
              'wall_seconds': time.monotonic() - start, 'cpu_seconds': time.process_time() - cpu,
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'workers': 1}
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('results/pilot.json')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
