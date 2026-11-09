# Experiments for BCNF Subset-Repair Checking

Code for Sections 4.2–4.5 of the paper *Efficient Subset-Repair Checking for a Relation Schema in BCNF*. It produces Fig. 2 (static scalability and the key-count control), Fig. 3 (incremental maintenance), Fig. 4 (update locality), Fig. 5 (the SQL baseline), and the 165.7× speedup reported in Section 4.4. A single command, `powershell -ExecutionPolicy Bypass -File scripts/run_final_pipeline.ps1`, re-runs the algorithmic experiments and regenerates the figures. Requires Python 3.12 and `pip install -r requirements.txt`.

## 1. Repository ↔ paper mapping

| Paper item | Content | Produced by | Data |
|---|---|---|---|
| Fig. 1 (§3) | Framework overview | external drawing | — |
| Fig. 2 (§4.2, §4.3) | Runtime and memory over \|r\| = 10³–10⁶; key-count control with 250,000 retained tuples and 16 input FDs | `supplement/figures/plot_results.py` | `supplement/data/static_summary.csv`, `static_separate_allocation.csv` |
| Fig. 3 (§4.4) | Incremental maintenance vs. full rebuild | `supplement/figures/plot_results.py` | `supplement/data/fig4_incremental_summary.csv`, `fig4_swap_records.csv`, `fig4_locality_bins.csv` |
| Fig. 4 (§4.4) | Hot-group locality: entries in touched conflict blocks vs. elapsed time | `supplement/figures/plot_results.py` | `supplement/data/hot_summary.csv`, `hot_raw.jsonl` |
| Fig. 5 (§4.5) | Benchmark-derived relations with a native SQL baseline | `supplement/figures/plot_results.py` | `supplement/data/tpch_summary.csv` |
| Fig. 6 (§4.6), Tables 1–2 | Structured QA accuracy of the two LLM backends | `paper_figures/source/plot_llm_figures.py`, `scripts/build_llm_paper_tables.py` | `../llm_study/results/final/` |

Figure files are named after their paper number: `fig2.pdf` is Fig. 2 and so on. `paper_figures/tif/` holds the exports used for the journal version of this work and uses an older numbering (`fig1`–`fig4`); ignore it when reproducing the conference paper.

The QA experiment behind Fig. 6 and Tables 1–2 lives in a separate repository, `llm_study`. Clone both repositories under the same parent directory; this repository only plots and tabulates its results.

## 2. Two static datasets, and why

`results/final/static.csv` and `supplement/data/static_raw.jsonl` both contain static timings, but they were collected under different timing boundaries:

- `results/final/static.csv` was measured with `tracemalloc` active inside the timing region.
- `supplement/data/static_raw.jsonl` was measured with allocation tracking in a **separate** run, so ordinary timings carry no instrumentation overhead.

**The paper reports the second set.** The first is kept because it is the source of the earlier journal version and because the difference is worth being able to audit; do not mix the two. See `supplement/README.md`.

## 3. Reproducing the 165.7× speedup

The speedup reported in §4.4 corresponds to `swap` updates, batch size 1000, and `uniform` conflict-block distribution, over 5 random seeds × 100 update batches (500 independent runs). The reported figure is the median of the per-batch speedups, which evaluates to 165.66 on the data included here.

```powershell
# Re-run this configuration (about 5-10 minutes on one machine)
python scripts/run_incremental.py --n 1000000 --seeds 1 2 3 4 5 `
  --block-distributions uniform --workloads swap --batch-sizes 1000 `
  --batches-per-config 100 --out results/final/incremental.csv `
  --config-out results/final/incremental_config.json

# Recompute the number (median of per-batch speedups)
python -c "import pandas as pd; d=pd.read_csv('results/final/incremental.csv'); s=d[(d.workload=='swap')&(d.batch_size==1000)&(d.block_distribution=='uniform')]; print((s.static_total_time/s.incremental_total_time).median())"
```

Fixed conditions: `--n 1000000` (that is, \|r\|), `--conflict-ratio 0.1`, `--key-width 1`, `--fd-count 4`, seeds `1 2 3 4 5`, and 100 batches per configuration. Randomness is driven entirely by `--seeds`; `common/reproducibility.py::set_global_seed()` sets the global seed, so no extra environment variables are needed.

The full curve in Fig. 3 uses `--block-distributions uniform zipf_1.2 --workloads d_only swap --batch-sizes 1 10 100 1000`, which is step 5 of `scripts/run_final_pipeline.ps1`.

## 4. Layout

```
algorithms/      BCNF-Index, FD-Hash, Singleton-FullScan, Exhaustive checkers + incremental state
common/          FD utilities, type definitions, metrics, reproducibility helpers
generators/      BCNF schema generation, instance generation, conflict injection (all data is generated here)
scripts/         Experiment entry points: correctness / static / sensitivity / incremental / summarization / tables
supplement/      Timings and summaries behind Figs. 2-5, collected with allocation tracking separated
paper_figures/   source (plotting scripts), eps, tif, preview
paper_tables/    CSV files for Tables 1 and 2
results/final/   Raw data (CSV) and run configurations (JSON) of the algorithmic experiments
tests/           Unit tests, including a 500-case key-cover differential test
dev/             Development-era scripts and an early LLM runner; not needed for reproduction
```

## 5. Environment

Python 3.12:

```bash
pip install -r requirements.txt
python -m pytest tests -q        # all 623 tests should pass
```

Experiment data is not shipped in `results/final/` for the large generated tables: `generators/` rebuilds them from fixed seeds. `results/final/` and `supplement/data/` hold the exact data cited in the paper, provided for verification; there is no need to regenerate it.

To redraw every result figure from the shipped data:

```bash
python supplement/figures/plot_results.py    # writes supplement/fig/fig2.pdf ... fig6.pdf
python supplement/code/summarize_static.py   # recomputes supplement/data/*.csv first, if you want to verify
```

## 6. Implementation notes

- **Deterministic results only.** `BCNFRepairChecker` calls `schema.validate_bcnf()` during initialization and raises `ValueError` for a schema that violates BCNF; it never falls back to a general FD-based algorithm.
- **S-repairs are inclusion-maximal, not maximum-cardinality.** A passing check means the candidate satisfies the FDs and cannot be extended further; it does not assert that the retained tuples are the ground truth.
- **Timing scope.** In the incremental experiments the update sequence (`UpdateOp` plan) is generated before the timer starts, and incremental and static modes replay the same updates, so both sides are timed over the same work.
- **Correctness gate.** `results/final/correctness.csv` records, over 2000 random cases, whether Exhaustive / Singleton-FullScan / FD-Hash / BCNF-Index agree.
- **Equivalent-cover baseline.** `supplement/code/supplement.py` implements the cover used as a baseline in §4.3 and asserts implication equivalence in both directions before timing.

## 7. Citation

If you use this code, please cite:

> Efficient Subset-Repair Checking for a Relation Schema in BCNF. IEEE International Conference on Data Engineering (ICDE), 2027.

## 8. License

MIT, see [`LICENSE`](LICENSE).
