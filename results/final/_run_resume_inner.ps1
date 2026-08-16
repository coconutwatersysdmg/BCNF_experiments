Set-Location 'E:\Homework\1研究生课程\AAA小论文\A论文编写\计算机研究与发展\experiments'
function Log($m) { Add-Content -Path 'results/final/formal_pipeline_resume.log' -Value ((Get-Date -Format o) + ' ' + $m) }
Log '=== RESUME sensitivity + incremental ==='
Log '[sensitivity formal]'
python scripts/run_sensitivity.py --n 1000000 --seeds 1 2 3 4 5 --repeats 5 --out results/final/sensitivity.csv --config-out results/final/sensitivity_config.json
if ($LASTEXITCODE -ne 0) { Log 'sensitivity FAIL'; exit 1 }
Log '[incremental formal]'
python scripts/run_incremental.py --n 1000000 --seeds 1 2 3 4 5 --block-distributions uniform zipf_1.2 --workloads d_only swap --batch-sizes 1 10 100 1000 --batches-per-config 100 --out results/final/incremental.csv --config-out results/final/incremental_config.json
if ($LASTEXITCODE -ne 0) { Log 'incremental FAIL'; exit 1 }
Log '[summarize/plot]'
python scripts/summarize_final_algorithms.py
python plot_results.py --results-dir results/final
Log '=== DONE ==='
