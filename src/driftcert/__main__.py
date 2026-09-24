"""Bounded JSON command-line interface. See README.md for complete commands."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from . import (Instance, produce, shortest, check, check_shortest, materialize_witness,
               produce_prefix, shortest_prefix_bisection, check_prefix,
               check_prefix_shortest, materialize_prefix_witness)


def load(path: str) -> object:
    p = Path(path)
    if p.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('input JSON exceeds 32 MiB')
    return json.loads(p.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['certify', 'check', 'shortest', 'check-shortest', 'expand',
                                'certify-prefix', 'check-prefix', 'shortest-prefix',
                                'check-shortest-prefix', 'expand-prefix'])
    parser.add_argument('instance')
    parser.add_argument('--certificate')
    parser.add_argument('--windows')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        inst = Instance.from_dict(load(args.instance))
        if args.action == 'certify':
            obj, _ = produce(inst)
        elif args.action == 'check':
            obj = check(inst, load(args.certificate))
        elif args.action == 'shortest':
            obj = shortest(inst, load(args.windows))
        elif args.action == 'check-shortest':
            obj = {'accepted': check_shortest(inst, load(args.windows), load(args.certificate))}
        elif args.action == 'expand':
            raw = load(args.certificate)
            obj = materialize_witness(inst, raw.get('witness', raw))
        elif args.action == 'certify-prefix':
            obj, _ = produce_prefix(inst)
        elif args.action == 'check-prefix':
            obj = check_prefix(inst, load(args.certificate))
        elif args.action == 'shortest-prefix':
            obj = shortest_prefix_bisection(inst, load(args.windows))
        elif args.action == 'check-shortest-prefix':
            obj = {'accepted': check_prefix_shortest(inst, load(args.windows), load(args.certificate))}
        else:
            raw = load(args.certificate)
            obj = materialize_prefix_witness(inst, raw.get('witness', raw))
        text = json.dumps(obj, indent=2) + '\n'
        if args.output:
            Path(args.output).write_text(text)
        else:
            print(text, end='')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'rejected: {exc}', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
