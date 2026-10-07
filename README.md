# Drift-complete safety certificates

This standalone reference repository accompanies **Exact Rank-Drift
Certificates for Final States and Ordered Replays of Frozen Rank Predictors**.
It implements and checks the paper's finite-domain final-state and declared
ordered-replay certificates. It is a research implementation, not a database,
and it needs neither the paper directory, a network connection, a model
service, nor a third-party Python package.

## Scope and exact semantics

The trusted input consists of:

- a finite consecutive integer universe and a sorted unique source set;
- a frozen piecewise floor-affine predictor evaluated with mathematical floor;
- insertion, deletion, total net-edit, and final-cardinality bounds; and
- per-segment requested compact-rank residual windows.

A final-state query is a key present in the final compact sorted array. The
producer computes tight residual endpoints and count witnesses for every
admissible final set. A separately implemented checker verifies universal
enclosure and endpoint attainment. A minimum-failure packet contains an
explicit violating witness and, except at budget zero, an exact safety
certificate for the predecessor budget.

The replay extension fixes one protocol. For a chosen final set `T`, the
**canonical replay** contains the length-zero source prefix, deletes `S \\ T`
in ascending key order, and then inserts `T \\ S` in ascending key order. A
query is checked at a prefix exactly when its key is active at that prefix. The
trusted bounds constrain the final set; no separate cardinality bound is
silently imposed on intermediate prefixes. `certify-prefix` computes the exact
envelope over all active queries at all such prefixes and
`shortest-prefix` finds the first total-edit budget at which that envelope can
leave a requested window.

The written general arguments are in `proofs/theorems.md`. Executable finite
checks complement those arguments; they are not proof-assistant proofs or
independent human verification.

No claim is made for absent-key/predecessor semantics, multisets, arbitrary
interleavings, atomic multi-key operations, physical addresses in gapped
layouts, weighted edits, concurrent readers/writers, crashes, adaptive
retraining or resegmentation, multidimensional indexes, or production
throughput. A mathematically tight window may still be too wide to be useful.

## Requirements

Use CPython 3.11 or later on Linux for the resource-limited runner. The core
library uses only the standard library. The runner uses Linux CPU affinity and
POSIX resource limits. Do not run tests with Python `-O`, which would remove
their assertions. Inputs are capped at 32 MiB; source/piece counts at 100,000;
input integers at 256 bits; and materialized source-plus-final sets at 100,000.
These are engineering admission bounds, not theorem assumptions.

## Command-line examples

Work from this repository root. The commands below create new outputs and do
not overwrite the retained reference campaign.

### Final-state certificate

```sh
mkdir -p results/demo
PYTHONPATH=src python -m driftcert certify \
  data/example.json --output results/demo/final-certificate.json
PYTHONPATH=src python -m driftcert check \
  data/example.json --certificate results/demo/final-certificate.json
PYTHONPATH=src python -m driftcert shortest \
  data/example.json --windows data/windows.json \
  --output results/demo/final-shortest.json
PYTHONPATH=src python -m driftcert check-shortest \
  data/example.json --windows data/windows.json \
  --certificate results/demo/final-shortest.json
PYTHONPATH=src python -m driftcert expand \
  data/example.json --certificate results/demo/final-shortest.json \
  --output results/demo/final-witness.json
```

The example has universe `0..10`, source set `{0,10}`, predictor
`floor(x/2)`, `I=3`, `D=1`, `B=4`, and final size four. Its exact final-state
residual interval is `[-3,2]`. Against requested window `[-4,0]`, the minimum
failure costs two net edits.

### Canonical-replay certificate

```sh
PYTHONPATH=src python -m driftcert certify-prefix \
  data/example.json --output results/demo/replay-certificate.json
PYTHONPATH=src python -m driftcert check-prefix \
  data/example.json --certificate results/demo/replay-certificate.json
PYTHONPATH=src python -m driftcert shortest-prefix \
  data/example.json --windows data/windows.json \
  --output results/demo/replay-shortest.json
PYTHONPATH=src python -m driftcert check-shortest-prefix \
  data/example.json --windows data/windows.json \
  --certificate results/demo/replay-shortest.json
PYTHONPATH=src python -m driftcert expand-prefix \
  data/example.json --certificate results/demo/replay-shortest.json \
  --output results/demo/replay-witness.json
```

Invalid inputs and rejected packets exit nonzero.

## Complete reproduction

The final-state checker advances a segment-local old-key cursor through its own
sorted cuts, including ineligible cells, instead of binary-searching each cell
start. Witness and segment-boundary searches remain unchanged. The portable
`python -B tests/checker_cursor_regression.py` checks literal final sets and
canonical replays; optionally add `--before-artifact /path/to/original/artifact`
for exact returned counters and rejection-message comparison with an original
source tree. This is an untimed conformance check, not a campaign rerun or a
runtime-gain claim; the conservative sorting-based checker bound is unchanged.

The additional untimed local arithmetic regression is
`python -B tests/overlap_regression.py` (also usable by absolute path from any
working directory). It compares final sets, canonical prefixes, minimum packets
and witness expansions with a test-local literal oracle. The producer reuses
old/new-class overlap thresholds only within each validated call; direct minimum
uses its own relaxed contract. Both checkers, candidate counts and packet fields
are unchanged. This standalone check is not a rerun of the retained campaign and
does not establish a runtime gain. The existing scientific CI workflow runs it
explicitly before the campaign; remote workflow success is not asserted here.

```sh
python reproduce.py --group all
python tools/compare_results.py
python tests/reproduction_compare.py
PYTHONPATH=src python tests/independent_random.py \
  --cases 2500 --max-universe 9 --output results/independent-random.json
python tools/summarize.py \
  --source results/reproduced --output results/reproduced-summary
python tools/paper_assets.py \
  --source results/reproduced-summary --output results/reproduced-assets
```

A targeted replay-vacuity regression runs separately from the retained 64-file
campaign and needs no Linux resource module:

```sh
python -B tests/replay_vacuity.py --output results/demo/replay-vacuity.json
```

It distinguishes an admissible empty final set (whose replay may contain old
queries) from an empty admissible family (which has no replay). It also checks a
positive-cost first source-prefix failure with a vacuous predecessor.

The controller's complete-log and fail-fast regression uses synthetic child
outcomes, not a claim of POSIX resource-limit enforcement:

```sh
python -B tests/reproduction_logs.py --output results/demo/log-regression
```

The prepared `scientific-checks.yml` workflow runs these checks, the complete
finite campaign, deterministic-result comparison, and the fixed-seed literal
oracle on Ubuntu 24.04, with a whole-run timeout and raw uploads even on failure.
A local run does not establish that this remote workflow has passed.

These scientific commands are self-contained and do not read a sibling paper
directory.  When this repository is embedded in the complete project, the
manuscript citation graph can be audited separately and explicitly:

```sh
python tools/audit_bibliography.py --paper ../paper
```

For a differently located manuscript, pass its directory to `--paper`.  The
tool has no implicit `../paper` default, so omitting the manuscript is never
mistaken for a complete standalone reproduction.

`reproduce.py` starts one child at a time, pins one available CPU, sets a
3.5-GiB address-space limit in each child, and enforces a 35-second wall limit
per child. It records cumulative child CPU including interpreter startup. A
failed child stops that invocation. Complete child stdout and stderr, including
output captured before a timeout, are retained under the selected output's
`logs/` directory. The complete command contains many bounded
children, so an outer shell with a short command limit may interrupt the
controller even though every scientific child is within its own limit. The
following disjoint invocations populate the same **64 scientific result files**:

```sh
python reproduce.py --group exact --match overlap
python reproduce.py --group exact --match budgets_u1
python reproduce.py --group exact --match budgets_u2
python reproduce.py --group exact --match budgets_u3
python reproduce.py --group exact --match budgets_u4
python reproduce.py --group exact --match budgets_u5
python reproduce.py --group exact --match budgets_u6
python reproduce.py --group exact --match integration
python reproduce.py --group exact --match regression
python reproduce.py --group prefix
python reproduce.py --group arrangement
python reproduce.py --group scaling --size 32
python reproduce.py --group scaling --size 128
python reproduce.py --group scaling --size 512
python reproduce.py --group scaling --size 2048
python reproduce.py --group scaling --size 8192
python reproduce.py --group scaling --size 32768 --match uniform
python reproduce.py --group scaling --size 32768 --match alternating
python reproduce.py --group scaling --size 32768 --match increasing
python reproduce.py --group scaling --size 32768 --match clustered
python reproduce.py --group trace
python reproduce.py --group sensitivity
python tools/compare_results.py
python tests/reproduction_compare.py
```

On a slower machine, report a timeout rather than reducing coverage. Rerunning
a case regenerates that case; it does not change the test universe. The
comparator requires all 64 files, zero mismatch fields, and equality of every
explicit deterministic field. Five early unsharded reference budget files lack
source-set range metadata later added for six-key sharding. Only for those five
known files, the comparator verifies the complete expected contract count and
supplies the frozen range `[0,2^v)` for comparison; it never alters the retained
reference file or relaxes candidate scope. CPU time, wall time, peak RSS, and
maintenance CPU are the only generally excluded fields. Comparator controls
verify that changed counts, changed ranges, and missing files are rejected,
while a measurement-only change is accepted.

## Retained evidence

The retained campaign and clean reproduction establish the following finite
facts within the declared model:

- final-state exhaustive budget checks: 1,471,728 contracts and 8,424,696 rank
  queries, with zero mismatches;
- integrated final-state checks: 4,080 instances, 8,160 minimum-result
  comparisons, and 12,276 rejected endpoint mutants;
- replay-envelope checks: 30,080 contracts, 61,000 admissible final-set
  occurrences, 144,664 prefixes, and 259,288 active-prefix queries, with zero
  mismatches;
- replay-minimum checks: 12,696 questions, comprising 7,665 safe and 5,031
  violating results, with zero mismatches;
- replay witness expansion: 57,035 compact extrema or minimum-failure witnesses
  expanded and independently replayed edit by edit, with 57,035 active-query,
  rank, and budget assertions; this includes source-initial, deletion-minimum,
  final-endpoint, retained-old, deleted-old, new-query, empty-final, and
  zero-budget cases;
- replay mutation controls: nine certificate mutants and twelve
  minimum-packet/schema mutants rejected;
- 24 scale cases and 5,460 compared segments, of which eight segments in four
  cases are strictly wider under replay; maximum observed widening is 929
  ranks; and
- all 64 scientific result files match in the clean semantic comparison; and
- a separate fixed-seed literal-set oracle covers 2,500 random instances,
  76,650 admissible final-set occurrences, 349,239 replay states, 1,216,188
  active replay queries, 7,500 minimum-budget questions, and 9,582 independently
  replayed compact witnesses with zero mismatch.

The independent-random script does not import the closed-form rank, overlap,
atom, envelope, or minimum-cost helpers. It does share the public input and
predictor types, and it was developed in the same research process; it is a
stronger common-mode check, not independent human validation.

The scale campaign retains unfavorable and null results. Direct/bisection
median CPU ratios range from 0.904 to 15.224, so no uniform speedup is claimed.
The largest clustered instance fails at two net edits and has mean unclipped
residual width about `3.433e10`. The total-cap ablation is null in the planned
fixed-cardinality scale cases. In generated traces the certified policy has no
window misses but uses more measured CPU than both safe rebuilding policies.

Reference results are in `results/campaign/`; clean reruns are in
`results/reproduced/`; summaries are in `results/summary/` and
`results/reproduced-summary/`; and the semantic comparison is in
`results/reproduction-check.json`. A successful command or finite check is not
by itself a proof of the general theorem.

Replay scaling measurements are intentionally kept as two run-local records:
`results/campaign/prefix/scaling.json` reports 3.069421701 CPU seconds and
104,364 KiB peak RSS, while `results/reproduced/prefix/scaling.json` reports
2.88467512 seconds and 104,456 KiB.  Both report the same deterministic result:
8 of 5,460 segments widen, by at most 929 ranks.  The resource ledger points to
those exact files and does not substitute a peak from another run.

## Repository map and trust boundary

- `src/driftcert/model.py`: trusted JSON parsing and predictor semantics.
- `src/driftcert/certificate.py`: final-state envelope and minimum producers.
- `src/driftcert/checker.py`: independently structured final-state checker.
- `src/driftcert/prefix.py`: canonical-replay envelope and minimum producer.
- `src/driftcert/prefix_checker.py`: replay checker, including schedule and
  old-key obligations reconstructed independently of the producer.
- `tests/validate.py`: final-state exhaustive and mutation checks.
- `tests/prefix.py`: replay exhaustive and mutation checks.
- `tests/independent_random.py`: fixed-seed literal-set and literal-replay oracle
  that avoids the implementation's closed-form helpers.
- `tests/prefix_scaling.py`: endpoint/replay scale comparison.
- `tests/arrangement.py`, `tests/scaling.py`, `tests/trace.py`, and
  `tests/sensitivity.py`: targeted finite and measured studies.
- `claim_evidence_ledger.csv`: claim-to-proof/test/result mapping.
- `external_resources.csv`: provenance and integration boundaries.
- `sources/calibration-matrix.csv`: 22 nominated works, comprising 21 retained
  historical complete-paper reading records and one identity-only range-filter
  record whose former author/source pairing was wrong. These are not fresh
  external full-text verification; the exception is excluded from established
  complete-paper calibration.
- `sources/reading-boundaries.md`: separates complete calibration reading from
  narrower claim-specific source review and states the novelty limits.
- `tools/audit_bibliography.py` plus `sources/bibliography-audit.*`: local
  structural audit of all cited references and stable identifiers.
- `data/PROVENANCE.md`: exact public-input and generated-fixture provenance.

Producer and checker share typed input parsing but not their envelope or
optimizer implementations. They were created in one research process and do
not constitute independent human validation. The caller remains responsible
for the trusted instance, the mapping from compact ranks to an operational
index, and any deployment-specific synchronization or address invariant.

## Current reproduction

The retained Linux reproduction below predates the checker cursor change; its
outputs are preserved, not relabeled as a new run of that change.

The current Linux/Python 3.12 run completes all 64 scientific chunks with no
nonzero child exit. Its deterministic results agree with the retained campaign
after completing the declared source-set ranges for five unsharded budget
files; original reference files are unchanged. The controller records
204.462509 child CPU seconds, 0.170494458 parent CPU seconds and 204.773650880
elapsed seconds, using one worker and a 35-second per-chunk wall limit.
The separate 2,500-instance literal-set oracle has zero mismatches. The 112
empty-final regressions expand 196 witnesses and reject 98 hidden active
segments. `results/measurements/` retains current accounting, comparisons and
regression outputs; the timing tables remain labeled historical measurements.

## License and external use

Repository code is covered by `LICENSE`; the bundled UCI Wine numeric fixture
retains attribution under `licenses/wine-attribution.txt`. Scholarly PDFs are
not redistributed.
