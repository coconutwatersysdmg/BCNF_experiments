# BCNF Subset Repair Checking — Experiment Suite

This repository implements reproducible experiments for the paper:

**《BCNF条件下的数据库子集修复检查问题研究》**

It studies the **subset repair (S-repair) checking** problem: given a relation
schema \(R(U,F)\), a database instance \(r\), and a candidate repair \(r'\),
decide whether \(r'\) is an S-repair of \(r\) w.r.t. \(F\).

---

## 1. Research problem

Decide whether a candidate \(r'\) is a **subset repair** of \(r\) under \(F\):

1. \(r' \subseteq r\) (set semantics; no duplicate tuple copies);
2. \(r'\) satisfies \(F\) (**consistency**);
3. \(r\) does **not** satisfy \(F\) in typical dirty cases (experimental setting);
4. There is no \(r''\) with \(r' \subset r'' \subseteq r\) that still satisfies \(F\)
   (**maximality** / inclusion-maximality — **not** maximum-cardinality).

**S-repair = consistency + maximality.**

This project does **not** implement C-repair, minimum-deletion repair, weighted
repair, or other repair semantics.

---

## 2. Notation: \(R(U,F)\)

- \(U\): attribute set of the relation.
- \(F\): a set of functional dependencies (FDs).
- Schemas are always written \(R(U,F)\), never bare \(R(U)\).

An FD \(X \rightarrow Y\) is satisfied by instance \(I\) iff there are no distinct
tuples \(t_1,t_2 \in I\) with \(t_1[X]=t_2[X]\) but \(t_1[Y]\neq t_2[Y]\).

---

## 3. BCNF premise

Formal BCNF algorithm experiments require \(R(U,F)\) to be in **BCNF**:

> For every nontrivial FD \(X\rightarrow Y\) in (the engineering proxy of) \(F^+\),
> \(X\) is a superkey, i.e. \(\mathrm{closure}(X,F)=U\).

`BCNFRepairChecker` calls `schema.validate_bcnf()` at initialization and
**raises `ValueError`** if the schema is not BCNF. It does **not** silently
fall back to a general-FD algorithm.

---

## 4. S-repair definition (strict)

| Concept | Meaning |
|--------|---------|
| consistency | \(r'\) satisfies \(F\) |
| maximality | no proper superset of \(r'\) inside \(r\) still satisfies \(F\) |
| S-repair | both |

**Important scientific constraints:**

- S-repair is **inclusion-maximal**, not maximum-cardinality.
- Passing the checker does **not** mean a tuple is a “true fact”.
- A deleted tuple is **not** necessarily erroneous.
- Legal S-repairs need not be unique.
- Clean ground truth is used only for synthetic evaluation / LLM answers; it is
  **never** an input to the repair checker.

---

## 5. Algorithms

| Name | Module | Role |
|------|--------|------|
| Exhaustive oracle | `algorithms/general.py` | Enumerates all nonempty \(A\subseteq D=r\setminus r'\). **Small-scale only.** |
| Singleton-FullScan | `algorithms/singleton_fullscan.py` | FD baseline with \(c=1\) (singleton extension property). Full `satisfies_fds` per deleted tuple. **No BCNF index.** |
| FD-Hash | `algorithms/fd_hash.py` | General FD hash indexes on each original FD. **No BCNF key compression.** |
| BCNF-Index | `algorithms/bcnf_index.py` | Formal BCNF static checker: minimize superkeys, optional greedy key-cover, key collision tests. |
| Incremental | `algorithms/incremental.py` | `BCNFRepairState` with four update ops + `validate_against_static()`. |

### Why \(c=1\) is allowed

For **FDs** (not BCNF-specific): if some nonempty \(A\subseteq D\) can be added
while preserving \(F\), then some singleton \(\{t\}\subseteq A\) can also be
added. Scalable baselines may therefore use \(c=1\).

### Why `general.py` is only an oracle

It enumerates \(2^{|D|}-1\) subsets and is capped by `max_deleted` (default 15).
It must **not** be used at \(10^5\)–\(10^6\) scales and must **not** be described
as the scalable theoretical algorithm. This project does **not** implement the
incorrect \(c=\max|X|\) idea from older drafts.

### Separating optimizations

- **FD-Hash** isolates “ordinary hash indexing”.
- **BCNF-Index** isolates “BCNF candidate-key compression / locality”.

---

## 6. Install

```bash
cd experiments
python -m pip install -r requirements.txt
```

Optional:

```bash
pip install psutil          # RSS memory column
pip install transformers torch   # local LLM backend only
```

Algorithm experiments run without LLM packages.

---

## 7. Correctness (1000 cases)

```bash
python scripts/run_correctness.py --cases 1000 --max-deleted 15 --seed 42
```

Output: `results/correctness.csv`  
Requires `all_match=True` for every case; otherwise exit code ≠ 0.

---

## 8. Static scalability

```bash
python scripts/run_static.py --sizes 1000 10000 100000 1000000 --seeds 1 2 3 4 5
```

Reduce sizes on smaller machines:

```bash
python scripts/run_static.py --sizes 1000 10000 --seeds 1 2 3
```

- Warmup: 1; measured repeats: 5; report median (raw reps stored).
- Timeout default: 600s (baseline timeout does not abort the whole run).
- Exhaustive oracle is **not** included.

Output: `results/static.csv`

---

## 9. Sensitivity

```bash
python scripts/run_sensitivity.py --n 1000000 --seeds 1 2 3 4 5
```

One factor at a time: conflict ratio, FD count, key width, skew.  
Compares FD-Hash vs BCNF-Index; records `compression_ratio`.

Output: `results/sensitivity.csv`

---

## 10. Incremental

```bash
python scripts/run_incremental.py --n 1000000 --updates 10000 --batch-sizes 1 10 100 1000 10000
```

Smoke / CI-friendly:

```bash
python scripts/run_incremental.py --n 10000 --updates 1000 --batch-sizes 1 10 100
```

Each batch: incremental update → static rebuild → assert identical repair status.

Output: `results/incremental.csv`

---

## 11. Generate LLM QA

```bash
python scripts/generate_llm_data.py
```

Creates:

- `data/llm_qa/questions.jsonl` (≥900 QA; No-Conflict / Irrelevant-Conflict / Answer-Critical-Conflict)
- Clean STUDENT / COURSE / ENROLLMENT BCNF DBs
- `candidate_checked_repairs.json` for Candidate- vs Checked-Repair

Schemas:

- STUDENT: `student_id → name, major, grade_level`
- COURSE: `course_id → course_name, credits, department`
- ENROLLMENT: `(student_id, course_id) → score`

---

## 12. Run LLM

```bash
# help works without API keys
python scripts/run_llm.py --help

# OpenAI-compatible (GLM / DeepSeek / ...)
set LLM_API_KEY=...
set LLM_BASE_URL=https://your-endpoint/v1
python scripts/run_llm.py --backend openai-compatible --model your-model \
  --conditions clean dirty dirty_fd_prompt repaired
```

Local (optional deps):

```bash
python scripts/run_llm.py --backend local --model Qwen/Qwen2.5-1.5B-Instruct --limit 20
```

Temperature=0, max_tokens=64, no tools, no LLM-as-judge.  
Output: `results/llm.csv`

---

## 13. Plotting

```bash
python plot_results.py
```

Produces figures/tables under `results/` from existing CSVs (log-scale runtime;
timeouts marked when present).

---

## 14. Output files

| File | Content |
|------|---------|
| `results/correctness.csv` | Oracle vs baselines agreement |
| `results/static.csv` | Per-rep static timings/memory |
| `results/sensitivity.csv` | One-factor sweeps |
| `results/incremental.csv` | Inc. vs static differential |
| `results/llm.csv` | LLM answers + metrics fields |
| `results/*_config.json` | Saved experiment configs / seeds |
| `data/llm_qa/questions.jsonl` | QA dataset |

Memory columns: `python_peak_mb` (tracemalloc) and optional `rss_peak_mb` (psutil).

---

## 15. Common errors

| Symptom | Cause / fix |
|---------|-------------|
| `ValueError: ... not in BCNF` | Schema failed validation; fix FDs / projection |
| `DeletedTooLargeError` | Exhaustive oracle \|D\| > max_deleted |
| Singleton timeout at large n | Expected; increase timeout or drop that algo via smaller `--sizes` |
| LLM ImportError for transformers | Optional; algorithm path does not need it |
| `r_prime must be a subset of r` | Construction bug / bad input |

---

## 16. Reproducibility

- All generators / scripts take explicit `--seed` values.
- Config snapshots are written next to results.
- Set semantics throughout (hashable tuples).
- Single-threaded correctness first; multiprocessing is not required for validity.
- Do not tune data to “look good”.

---

## 17. TPC-H (optional)

Interface: `generators/tpch_loader.py`.

Provide external `.tbl`/`.csv`, **explicit** attributes + FDs, then
`validate_bcnf`. Suggested key-determined projections: CUSTOMER, ORDERS, PART.
Non-BCNF projections are **rejected**.

---

## 18. Tests

```bash
python -m pytest tests -q
```

Covers FD utilities, small multi-algorithm agreement, BCNF index cases, and
≥1000 mixed incremental updates vs static rebuild.

---

## Suggested full paper pipeline

```bash
python -m pytest tests -q
python scripts/run_correctness.py --cases 1000 --max-deleted 15 --seed 42
python scripts/run_static.py --sizes 1000 10000 100000 1000000 --seeds 1 2 3 4 5
python scripts/run_sensitivity.py --n 1000000 --seeds 1 2 3 4 5
python scripts/run_incremental.py --n 1000000 --updates 10000
python scripts/generate_llm_data.py
python scripts/run_llm.py --backend openai-compatible --model <model> --base-url <url>
python plot_results.py
```
