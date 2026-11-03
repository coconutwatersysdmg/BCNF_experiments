# 复现论文第 4.2-4.4 节全部实验与图3/图4/图5（Windows PowerShell）。
# 用法（仓库根目录）：powershell -ExecutionPolicy Bypass -File scripts/run_final_pipeline.ps1
# 所有输出写入 results/final/ 与 paper_figures/。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PY = "python"

Write-Host "=== [1/7] unit tests ==="
& $PY -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "=== [2/7] correctness check (2000 cases, exhaustive oracle) ==="
& $PY scripts/run_correctness.py --cases 2000 --seed 42 `
  --out results/final/correctness.csv `
  --config-out results/final/correctness_config.json
if ($LASTEXITCODE -ne 0) { throw "correctness failed" }

Write-Host "=== [3/7] static scalability (Fig.3) ==="
& $PY scripts/run_static.py `
  --case pass `
  --sizes 1000 10000 100000 1000000 `
  --seeds 1 2 3 4 5 `
  --repeats 5 `
  --hard-timeout `
  --out results/final/static.csv `
  --config-out results/final/static_config.json
if ($LASTEXITCODE -ne 0) { throw "static failed" }

Write-Host "=== [4/7] structural sensitivity (Fig.4) ==="
& $PY scripts/run_sensitivity.py `
  --n 1000000 `
  --seeds 1 2 3 4 5 `
  --repeats 5 `
  --out results/final/sensitivity.csv `
  --config-out results/final/sensitivity_config.json
if ($LASTEXITCODE -ne 0) { throw "sensitivity failed" }

Write-Host "=== [5/7] incremental vs static rebuild (Fig.5) ==="
& $PY scripts/run_incremental.py `
  --n 1000000 `
  --seeds 1 2 3 4 5 `
  --block-distributions uniform zipf_1.2 `
  --workloads d_only swap `
  --batch-sizes 1 10 100 1000 `
  --batches-per-config 100 `
  --out results/final/incremental.csv `
  --config-out results/final/incremental_config.json
if ($LASTEXITCODE -ne 0) { throw "incremental failed" }

Write-Host "=== [6/7] summary tables ==="
& $PY scripts/summarize_final_algorithms.py --final-dir results/final
if ($LASTEXITCODE -ne 0) { throw "summarize failed" }

Write-Host "=== [7/7] paper figures (Fig.3/4/5 + Fig.6) ==="
& $PY paper_figures/source/plot_paper_figures.py
if ($LASTEXITCODE -ne 0) { throw "figure plotting failed" }
& $PY paper_figures/source/plot_llm_figures.py
if ($LASTEXITCODE -ne 0) { Write-Host "Fig.6 skipped: llm_study/results/final/exp1_summary.csv not found." }

Write-Host "DONE -> results/final/, paper_figures/{eps,tif,preview}/"
