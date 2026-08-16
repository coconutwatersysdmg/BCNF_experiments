# Final Audit Report — BCNF Subset Repair Checking Experiments

Date: 2026-08-15  
Branch: `exp-final-audit`  
Pre-audit snapshot: `d5d1513`  
Code label: `final-audit-v1`  
Archive of old results: `results/archive_pre_audit/`  
New outputs: `results/final/` only (old `results/*.csv` untouched)

---

## 1. Files modified

| File | Change |
|------|--------|
| `algorithms/bcnf_index.py` | `collect_certificates=False`; stream deleted order; `use_key_cover=False`; schema-order keys; `find_conflict_witness`; unified timing metadata |
| `algorithms/fd_hash.py` | stream deleted; same timing definition; no certificates |
| `algorithms/incremental.py` | `.get` for C reads; no `list()` G copies; work counters; `UpdateOp`/`PlainRepairState`; `use_key_cover=False` |
| `algorithms/singleton_fullscan.py` | stream deleted order (FAIL addable_position) |
| `generators/conflict_injector.py` | `block_distribution` uniform/zipf; block stats; order-preserving FAIL |
| `generators/qa_generator.py` | `complete_by_checker`; residual=gate only; no GT conflict resolution |
| `scripts/run_incremental.py` | fair timing protocol; D-only + swap workloads |
| `scripts/run_sensitivity.py` | cover=False; cert=False; actual FD counts; block_distribution |
| `scripts/run_static.py` | PASS-default; size fields; paper defaults |
| `scripts/run_correctness.py` | writes `results/final/` |
| `scripts/run_diagnostics.py` | **new** Diagnostic A/B |
| `scripts/run_incremental_stress.py` | **new** Phase 15 stress |
| `scripts/summarize_final_algorithms.py` | **new** median-based summaries |
| `scripts/run_final_pipeline.ps1` | **new** formal pipeline |
| `scripts/generate_llm_data.py` | separate over_deletion / residual_conflict |
| `plot_results.py` | Fig_A / Fig_B / Fig_C |
| `config.py` | `FINAL_RESULTS_DIR`; block distributions; QA=1200 |
| `common/metrics.py` | clarified python_peak vs RSS |
| `common/reproducibility.py` | `get_code_version()` |
| `tests/test_key_cover_and_audit.py` | **new** 500-case cover + audit tests |

---

## 2. Old results invalidated for the paper

Do **not** use for final paper tables/figures:

- `results/static.csv`, `sensitivity.csv`, `incremental.csv` (and archive copies)
- Reasons: certificate overhead in BCNF; `use_key_cover=True` vs paper; incremental timer contamination (Zipf sampling / set→tuple inside timer); skew ≠ conflict-block distribution; `n` often meant `|r'|`.

Keep them only as historical archive under `results/archive_pre_audit/`.

---

## 3. Correctness gates (passed)

| Gate | Result |
|------|--------|
| `pytest tests` | **623 passed** |
| 2000-case Exhaustive/Singleton/FD-Hash/BCNF | **2000/2000 match** → `results/final/correctness.csv` |
| Key-cover differential (500 cases) | **passed** (in pytest) |
| Incremental stress n=10k, 5000 mixed updates | **passed** |

---

## 4. Diagnostic A (certificate overhead) — PASSED

At `|r'| = 1e6`, `cr=0.10`, deleted=100000:

| Mode | check_time |
|------|------------|
| BCNF decision (`collect_certificates=False`) | **0.439 s** |
| BCNF certificate (`True`) | **0.697 s** (~1.6×) |
| Certificate entries | 100000 |

Paper decision benchmarks must keep certificates off.

---

## 5. Diagnostic B (incremental) — PASSED

- Workload generation outside timers; same `batch_plan` replayed.
- `touched_block_entries` for swap batch=1: uniform max≈20 (≈2× block size 10); zipf max≫1.
- uniform max_block=10 vs zipf max_block≈2077 at n=1e5.

---

## 6. Recommended full experiment commands

```powershell
# Already safe to run (gates passed):
powershell -ExecutionPolicy Bypass -File scripts/run_final_pipeline.ps1

# Or stepwise:
python scripts/run_static.py --case pass --sizes 1000 10000 100000 1000000 --seeds 1 2 3 4 5 --repeats 5 --hard-timeout --out results/final/static.csv
python scripts/run_sensitivity.py --n 1000000 --seeds 1 2 3 4 5 --repeats 5 --out results/final/sensitivity.csv
python scripts/run_incremental.py --n 1000000 --seeds 1 2 3 4 5 --block-distributions uniform zipf_1.2 --workloads d_only swap --batch-sizes 1 10 100 1000 --batches-per-config 100 --out results/final/incremental.csv
python scripts/summarize_final_algorithms.py
python plot_results.py --results-dir results/final
```

Then freeze:

```powershell
git add -A
git commit -m "freeze final BCNF repair checking experiments"
git rev-parse HEAD
```

LLM (after freeze):

```powershell
python scripts/generate_llm_data.py --n-questions 1200
python scripts/run_llm.py ...   # two models, temperature=0
```

---

## 7. Estimated runtimes (machine-dependent)

| Experiment | Estimate |
|------------|----------|
| Static to 1e6, 5 seeds × 5 reps, 3 algos | **2–8 h** (Singleton TO early) |
| Sensitivity 1e6, 4 axes × 5 seeds × 5 reps × 2 algos | **4–12 h** |
| Incremental 1e6, 2 dists × 2 workloads × 4 batch × 100 × 5 seeds | **6–20 h** |
| Diagnostic A (done) | ~1.5 min |
| Diagnostic B (done) | ~1–2 min |

---

## 8. Known limitations (do not affect main claims)

1. `python_peak_mb` is allocator peak in-process, not RSS; RSS not used as primary memory claim.
2. Swap planner builds `retained_by_v` in O(|r'|) outside the timer — planning cost excluded by design.
3. Zipf block allocation uses deterministic proportional rounding (not multinomial sampling); distribution still clearly skewed vs uniform.
4. Optional `greedy_key_cover` retained for ablation only; main paper algorithm uses dedup only.
5. Formal million-scale CSVs may still be running; smoke CSVs already validate the new protocol.

---

## 9. Freeze checklist (A–H)

- [x] A Correctness 100% match (2000)
- [x] B Incremental differential stress 100%
- [ ] C Static scaling to \|r\|≈1e6 (pipeline started / pending completion)
- [ ] D FD sensitivity actual counts recorded (pending formal run)
- [x] E touched_block_entries correct (Diagnostic B + smoke)
- [x] F Workload generation outside timer
- [x] G collect_certificates=False in benchmarks
- [x] H use_key_cover=False for paper main algorithm
