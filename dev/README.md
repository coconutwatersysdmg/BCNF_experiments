# dev — development-era scripts

This directory is not part of the paper's experimental pipeline, and nothing here is needed to reproduce the reported results. It is kept only to document diagnostics and earlier implementations from the development period.

| File | Description |
|---|---|
| `run_diagnostics.py` | Development-time diagnostics: cross-checks of certificate overhead and of the incremental timing scope |
| `run_incremental_stress.py` | Mixed-update stress test of the incremental state |
| `run_formal.py`, `run_formal_pipeline.ps1` | Early experiment orchestration, superseded by `scripts/run_final_pipeline.ps1` |
| `plot_results_legacy.py` | Early plotting script (Fig_A/B/C), superseded by `paper_figures/source/plot_paper_figures.py` |
| `generate_llm_data.py`, `run_llm.py`, `legacy_llm/` | Earlier implementation of the LLM QA experiment, superseded by the standalone `llm_study` repository |

Some of these scripts resolve imports relative to the repository root, so after the move they may need to be run as `python -m` from the root, or with `sys.path` adjusted.
