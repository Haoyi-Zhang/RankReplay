# Owned native rank replay

This C++17 compact-vector consumer is not PGM, Shift-Table, a database engine,
or a native certificate producer/checker. The latter computations remain Python.

## Contract and comparators

`workflow.py` takes every nonoverlapping four-replacement horizon in the eight
retained traces (128 source/endpoint pairs), plus one declared replacement for
each of the 24 retained scale sources. Each pair replays independently: source,
ascending net deletions, ascending net insertions. It is not the original
potentially cancelling operational history. All active keys are queried at each
prefix. Final cardinality bounds do not constrain prefix cardinalities.

Exact replay and ordinary transport receive the same trusted source, predictor,
universe and caps without the endpoint during preparation. Both guarantee
containment without fallback; only exact replay additionally supplies tightness
and attainment. Ordinary transport uses source rank plus completed insertions
minus completed deletions. Proposition 25 proves containment for any minimal
edit order, not repeated histories or concurrency. This is not a new algorithm.
Stored windows with fallback and full binary search are correct-answer controls.
Full binary search transfers one dummy domain piece and skips model routing and
prediction. None is a reproduction of a third-party index implementation.

## Arithmetic and consumer

Keys are signed 64-bit integers; parser magnitudes are below 2^120; source,
target and piece counts are at most 100000. Multiplication/addition reject
overflow; negative nonintegral division is adjusted to mathematical floor.
This does not implement every admitted 256-bit Python input. Vector erase and
insert actually execute. Each lookup is checked against its active compact
rank. Prefix aggregates and an unsigned rolling checksum are conformance
diagnostics, not cryptographic authentication. Existing project license applies.

Use an existing C++17 compiler with `__int128` and overflow builtins. Example
flags are `-std=c++17 -O3 -DNDEBUG` and `-std=c++17 -O0 -g -ftrapv`. No global
installation is needed. Measured dependencies and build costs are recorded in
`results/native-replay/environment.json`. Use absolute binary paths and fresh
outputs outside retained results:

```sh
python -B native/workflow.py --binary /absolute/release \
  --check-binary /absolute/checked --output /fresh/output --repeats 3
python -B tests/transport_native.py --binary /absolute/release \
  --binary /absolute/checked --output /fresh/transport.json
python -B -O tests/transport_native.py --binary /absolute/release \
  --binary /absolute/checked --output /fresh/transport-O.json
python -B tests/native_report_controls.py
python -B -O tests/native_report_controls.py
python -B native/report.py --figures ../paper/figures --scratch /fresh/scratch --check
```

The public results retain actual inputs, all samples, checked-build hashes,
actual environment, and a compressed archive of all 6082 raw files. The report
consumer requires exact raw membership, source/input/output bindings, complete
case/arm/repeat scope, typed counts, successful queries and release/checked
equality before generating the every-case CSV, table and vector PDF. Controls
run in normal and optimized Python. Rendering additionally uses the documented
Matplotlib/FontTools/Libertine dependencies, outside the timed interval.

## Cost and negatives

The measured interval includes batch validation, preparation and exact checking,
encoding, input write/close, startup/read, vector construction and updates,
routing/prediction, queries, output serialization, parent parse and literal-input
binding. Common frozen-model/fixture generation, reference construction, builds,
warmup, logs and summaries are excluded equally. This is a hybrid complete-call
cost, not complete system lifecycle or steady-state service latency. No fsync,
physical allocated bytes, RSS, energy, counters, cross-host or third-party
deployment is measured.

There are 152 cases, 1824 timed calls, 608 warmup outputs and 608 additional
checked outputs. Each arm executes 816 edits and 634178 queries counting each
batch once. Exact replay has 4433401 probes, transport 6064074, stored fallback
3612119 (231952 fallbacks), and full binary search 7653823. All queries succeed.
Exact case-median time exceeds transport in 151/152 cases; the median of ratios
is 1.181, range 0.996--3.024. It also exceeds full binary search in 151 cases.
Three repetitions are descriptive: no significance, uniform performance
advantage, deployment benefit or algorithmic novelty follows.

Original Linux measurements and original inputs/results remain unchanged.
Separate `results/current-windows/` runs compare all 64 chunks' deterministic
science, not identical timings or POSIX resource enforcement.
