# Supplemental static, locality, and benchmark experiments

These are the measurements behind Fig. 2 (Sections 4.2 and 4.3), Fig. 3 and
Fig. 4 (Section 4.4), and Fig. 5 (Section 4.5). They are kept apart from
`results/final/` on purpose.

## Why this directory exists

`results/final/static.csv` was collected with `tracemalloc` running inside the
timing region. The numbers in this directory were collected afterwards with
allocation tracking in a **separate** run, so the two sets are not comparable
and must not be mixed. The paper reports the numbers below, not the ones in
`results/final/static.csv`.

Both sets are shipped so the difference is auditable rather than hidden.

## What can be reproduced without re-running anything

Everything. All raw observations are included.

```bash
# Recompute every table in data/ from the raw records, and redraw the
# supplemental static figure.
python code/summarize_static.py

# Redraw the five result figures of the paper (Figs. 2-6) from data/.
python figures/plot_results.py
```

`summarize_static.py` reads `data/static_raw.jsonl` (360 timing observations,
14 jobs, 3 seeds x 3 repetitions per cell after one untimed warmup) and rewrites
`data/static_summary.csv`, `data/static_paired_speedups.csv`,
`data/static_separate_allocation.csv`, and `data/static_skipped.csv`. Running it
on the shipped records reproduces those four files byte for byte.

`plot_results.py` writes the figures to `fig/`. The generated `fig2.pdf` through
`fig5.pdf` are byte-identical in size to the files used in the submission.

## Values quoted in the paper

| Where | Quantity | Value | Source file |
|---|---|---|---|
| Sec. 4.3 | legacy 1,000,000 tuples, FD-Hash / FD-Hash-Cover / BCNF-Index | 5.220131 / 2.123948 / 1.208682 s | `data/static_summary.csv` |
| Sec. 4.3 | median paired speedup over raw FD hashing | 4.3505x | `data/static_paired_speedups.csv` |
| Sec. 4.3 | median paired speedup over the equivalent cover | 1.7572x | `data/static_paired_speedups.csv` |
| Sec. 4.3 | peak allocation at 100,000 tuples | 64.91 / 24.73 / 15.58 MiB | `data/static_separate_allocation.csv` |
| Sec. 4.4 | 250,000 tuples, q=1 -> q=8, cover baseline | 0.6456 -> 2.4377 s | `data/static_summary.csv` |
| Sec. 4.4 | 250,000 tuples, q=1 -> q=8, BCNF-Index | 0.2716 -> 1.2875 s | `data/static_summary.csv` |
| Sec. 4.4 | median paired gains at 1,000,000 tuples, q=1,2 | 2.098x, 1.889x | `data/static_paired_speedups.csv` |

## Layout

```
code/
  supplement.py               equivalent_cover(), synthetic key-control schemas,
                              definition oracle, and the evaluation harness
  run_static_supplement.py    produces data/static_raw.jsonl
  summarize_static.py         raw -> tables and figure
  run_hot_incremental.py      locality experiment (810 hot-group batches)
  summarize_hot.py            -> data/hot_summary.csv
  run_tpch_supplement.py      native-SQL benchmark
  summarize_tpch.py           -> data/tpch_summary.csv
data/                         raw records, protocols, and every summary table
reports/                      per-experiment protocol and result reports
figures/plot_results.py       redraws Figs. 2-6 from data/
```

## The equivalent-cover baseline

`equivalent_cover()` in `code/supplement.py` decomposes right-hand sides,
removes extraneous determinant attributes and redundant dependencies, and
regroups identical left-hand sides. It then asserts implication equivalence in
both directions, so the cover is a valid rewriting of the input FD set, not a
weaker or stronger constraint set. It is one equivalent reduced cover, not a
claim of a unique or globally minimum representation.

## Re-running the experiments

Re-running is only necessary if you change the protocol. It takes about 20
minutes for the static part at the shipped sizes and needs `psutil`.

```bash
python code/run_static_supplement.py --jobs data/jobs.json
```

The script timestamps every observation and refuses to time anything while
`tracemalloc` is active; allocation is measured in a separate pass. It records
the git HEAD, the Python build, and SHA-256 of every algorithm source file into
`data/static_protocol.json`.

The TPC-H benchmark additionally needs `duckdb`. Its generated database files
(`tpch_sf*.duckdb`, about 33 MB) are not shipped; `run_tpch_supplement.py`
regenerates them from the TPC-H generator.

`pilot_v1_*` records are an earlier protocol run. They are retained for audit
and are excluded from every summary and figure.
