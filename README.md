# Experiments for BCNF Subset-Repair Checking

Code for Sections 4.2–4.4 of the paper *Efficient Subset-Repair Checking for a Relation Schema in BCNF*. It produces Fig. 3 (static scalability), Fig. 4 (effect of the number of functional dependencies), Fig. 5 (local-update performance of incremental maintenance), and the 165.7× speedup reported in the paper. A single command, `powershell -ExecutionPolicy Bypass -File scripts/run_final_pipeline.ps1`, re-runs all experiments and regenerates the figures. Requires Python 3.12 and `pip install -r requirements.txt` (numpy, pandas, matplotlib, Pillow, pytest).

## 1. Repository ↔ paper mapping

| File in this repository | Paper item | Content | Producing script | Data |
|---|---|---|---|---|
| `paper_figures/tif/fig1_static_scalability.tif` | Fig. 3 (§4.2) | Runtime and memory of the three algorithms for \|r\| = 10³–10⁶ | `scripts/run_static.py` | `results/final/static.csv` |
| `paper_figures/tif/fig2_fd_scaling.tif` | Fig. 4 (§4.3) | Index compaction and runtime for 1–15 nontrivial FDs | `scripts/run_sensitivity.py` | `results/final/sensitivity.csv` |
| `paper_figures/tif/fig3_incremental_locality.tif` | Fig. 5 (§4.4) | Incremental maintenance vs. full rebuild; entries in touched conflict blocks vs. elapsed time | `scripts/run_incremental.py` | `results/final/incremental.csv` |
| `paper_figures/tif/fig4_llm_data_quality.tif` | Fig. 6 (§4.5) | Structured QA accuracy of the LLMs | `paper_figures/source/plot_llm_figures.py` | reads `../llm_study/results/final/exp1_summary.csv` |
| `paper_tables/table_fd_prompt.csv`, `table_llm_checker.csv` | Tables 1 and 2 | Conflict-detection precision/recall/F1; effect of defective candidate repairs | `scripts/build_llm_paper_tables.py` | as above (`../llm_study/results/final/`) |

Figure files use the internal names `fig1`–`fig4`, numbered from 1 and therefore offset by two from the paper: `fig1`→Fig. 3, `fig2`→Fig. 4, `fig3`→Fig. 5, `fig4`→Fig. 6.

The QA experiment behind Fig. 6 and Tables 1–2 lives in a separate repository, `llm_study`; this repository only plots and tabulates its results. Clone both repositories under the same parent directory.

## 2. Reproducing the 165.7× speedup

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

The full curve in Fig. 5 uses `--block-distributions uniform zipf_1.2 --workloads d_only swap --batch-sizes 1 10 100 1000`, which is step 5 of `scripts/run_final_pipeline.ps1`.

## 3. Layout

```
algorithms/      BCNF-Index, FD-Hash, Singleton-FullScan, Exhaustive checkers + incremental state
common/          FD utilities, type definitions, metrics, reproducibility helpers
generators/      BCNF schema generation, instance generation, conflict injection (all data is generated here)
scripts/         Experiment entry points: correctness / static / sensitivity / incremental / summarization / tables
paper_figures/   source (plotting scripts), eps, tif, preview
paper_tables/    CSV files for Tables 1 and 2
results/final/   All raw data (CSV) and run configurations (JSON) cited in the paper
tests/           Unit tests, including a 500-case key-cover differential test
dev/             Development-era scripts and an early LLM runner; not needed for reproduction
```

## 4. Environment

Python 3.12:

```bash
pip install -r requirements.txt
python -m pytest tests -q        # all 623 tests should pass
```

Experiment data is not shipped in the repository (it is large) and is generated on the fly by `generators/` from fixed seeds. `results/final/` holds the exact data cited in the paper, provided for verification; there is no need to regenerate it.

## 5. Implementation notes

- **Deterministic results only.** `BCNFRepairChecker` calls `schema.validate_bcnf()` during initialization and raises `ValueError` for a schema that violates BCNF; it never falls back to a general FD-based algorithm.
- **S-repairs are inclusion-maximal, not maximum-cardinality.** A passing check means the candidate satisfies the FDs and cannot be extended further; it does not assert that the retained tuples are the ground truth.
- **Timing scope.** In the incremental experiments the update sequence (`UpdateOp` plan) is generated before the timer starts, and incremental and static modes replay the same updates, so both sides are timed over the same work.
- **Correctness gate.** `results/final/correctness.csv` records, over 2000 random cases, whether Exhaustive / Singleton-FullScan / FD-Hash / BCNF-Index agree.

## 6. Citation

If you use this code, please cite:

> Efficient Subset-Repair Checking for a Relation Schema in BCNF. IEEE International Conference on Data Engineering (ICDE), 2027.

## 7. License

MIT, see [`LICENSE`](LICENSE).
