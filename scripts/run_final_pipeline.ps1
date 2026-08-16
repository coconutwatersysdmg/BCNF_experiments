# Final audit experiment pipeline (run AFTER correctness gates).
# Do NOT overwrite results/*.csv — all outputs go to results/final/.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Final algorithm experiment pipeline ==="

Write-Host "[1/6] pytest"
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "[2/6] Diagnostic A (certificate overhead)"
python scripts/run_diagnostics.py --which A
if ($LASTEXITCODE -ne 0) { throw "Diagnostic A failed" }

Write-Host "[3/6] Diagnostic B (incremental timing)"
python scripts/run_diagnostics.py --which B
if ($LASTEXITCODE -ne 0) { throw "Diagnostic B failed" }

Write-Host "[4/6] Static scalability (PASS, to 1e6)"
python scripts/run_static.py `
  --case pass `
  --sizes 1000 10000 100000 1000000 `
  --seeds 1 2 3 4 5 `
  --repeats 5 `
  --hard-timeout `
  --out results/final/static.csv `
  --config-out results/final/static_config.json
if ($LASTEXITCODE -ne 0) { throw "static failed" }

Write-Host "[5/6] Sensitivity"
python scripts/run_sensitivity.py `
  --n 1000000 `
  --seeds 1 2 3 4 5 `
  --repeats 5 `
  --out results/final/sensitivity.csv `
  --config-out results/final/sensitivity_config.json
if ($LASTEXITCODE -ne 0) { throw "sensitivity failed" }

Write-Host "[6/6] Incremental"
python scripts/run_incremental.py `
  --n 1000000 `
  --seeds 1 2 3 4 5 `
  --block-distributions uniform zipf_1.2 `
  --workloads d_only swap `
  --batch-sizes 1 10 100 1000 `
  --batches-per-config 100 `
  --out results/final/incremental.csv `
  --config-out results/final/incremental_config.json
if ($LASTEXITCODE -ne 0) { throw "incremental failed" }

Write-Host "Summarize + plot"
python scripts/summarize_final_algorithms.py
python plot_results.py --results-dir results/final

Write-Host "DONE. Review results/final/ then freeze with:"
Write-Host '  git add -A; git commit -m "freeze final BCNF repair checking experiments"'
