"""Deterministic endpoint-versus-replay comparison on the frozen scale matrix."""
from __future__ import annotations
from pathlib import Path
import argparse, json, os, resource, statistics, sys, time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from driftcert import check, check_prefix, produce, produce_prefix
from fixtures import FAMILIES, scale_instance

SIZES = [32, 128, 512, 2048, 8192, 32768]


def width(row: dict | None) -> int | None:
    return None if row is None else row["upper"] - row["lower"] + 1


def run() -> dict:
    cases = []
    total_segments = enlarged = total_witness_constructions = 0
    for n in SIZES:
        for family in FAMILIES:
            inst = scale_instance(n, family)
            endpoint, _ = produce(inst)
            replay, stats = produce_prefix(inst)
            check(inst, endpoint)
            checked = check_prefix(inst, replay)
            endpoint_widths, replay_widths, increments = [], [], []
            changed = 0
            for e, p in zip(endpoint["segments"], replay["segments"]):
                ew, pw = width(e), width(p)
                if ew is None or pw is None:
                    if ew != pw:
                        raise AssertionError("vacuity disagreement")
                    continue
                if pw < ew or p["lower"] > e["lower"] or p["upper"] < e["upper"]:
                    raise AssertionError("replay envelope must contain endpoint envelope")
                endpoint_widths.append(ew)
                replay_widths.append(pw)
                increments.append(pw - ew)
                changed += int(pw > ew)
            total_segments += len(endpoint_widths)
            enlarged += changed
            total_witness_constructions += stats["witness_constructions"]
            cases.append({
                "n": n,
                "family": family,
                "segments": len(endpoint_widths),
                "enlarged_segments": changed,
                "mean_endpoint_width": statistics.mean(endpoint_widths),
                "mean_replay_width": statistics.mean(replay_widths),
                "mean_width_increment": statistics.mean(increments),
                "maximum_width_increment": max(increments, default=0),
                "old_key_obligations": checked["old_key_obligations"],
                "producer_old_key_scans": stats["old_key_evaluations"],
                "producer_witness_constructions": stats["witness_constructions"],
                "certificate_json_bytes": len(json.dumps(replay, separators=(",", ":")).encode()),
            })
    return {
        "mode": "prefix_scaling",
        "cases": cases,
        "case_count": len(cases),
        "segments_compared": total_segments,
        "enlarged_segments": enlarged,
        "cases_with_enlargement": sum(c["enlarged_segments"] > 0 for c in cases),
        "producer_witness_constructions": total_witness_constructions,
        "mismatches": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (3758096384, 3758096384))
    wall, cpu = time.monotonic(), time.process_time()
    result = run()
    result.update(
        cpu_seconds=time.process_time() - cpu,
        wall_seconds=time.monotonic() - wall,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        workers=1,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["case_count", "segments_compared", "enlarged_segments", "cases_with_enlargement", "cpu_seconds", "peak_rss_kib"]}, indent=2))


if __name__ == "__main__":
    main()
