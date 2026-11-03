# Formal paper-scale experiment pipeline (sequential; limits RAM pressure).
# Skips 1e7: free RAM was ~2GB at launch time.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $Root "run_static.py")) {
  # script lives in experiments/scripts
  $Root = Split-Path -Parent $Root
}
Set-Location $Root
$LogDir = Join-Path $Root "results"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$MasterLog = Join-Path $LogDir "formal_run_$Stamp.log"

function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Write-Host $line
  Add-Content -Path $MasterLog -Value $line
}

$env:PYTHONUNBUFFERED = "1"
Log "START formal pipeline cwd=$Root"
try {
  $avail = (python -c "import psutil; print(round(psutil.virtual_memory().available/1e9,2))")
  Log "available_RAM_GB=$avail (1e7 skipped if <8GB free)"
} catch {
  Log "psutil unavailable for RAM probe"
}
Log "Skip size 1e7 under current memory budget"

Log "=== STATIC n=1e3..1e6 seeds=1..5 pass+fail repeats=5 ==="
& python -u scripts/run_static.py `
  --sizes 1000 10000 100000 1000000 `
  --seeds 1 2 3 4 5 `
  --case both `
  --repeats 5 `
  --warmup 1 `
  --timeout 600 `
  --hard-timeout `
  --out results/static.csv `
  2>&1 | Tee-Object -FilePath (Join-Path $LogDir "static_$Stamp.log")
$staticExit = $LASTEXITCODE
Log "STATIC exit=$staticExit"

Log "=== SENSITIVITY n=1e6 conflict_ratio / fd_count / key_width ==="
& python -u scripts/run_sensitivity.py `
  --n 1000000 `
  --seeds 1 2 3 4 5 `
  --repeats 5 `
  --experiments conflict_ratio fd_count key_width `
  --out results/sensitivity.csv `
  2>&1 | Tee-Object -FilePath (Join-Path $LogDir "sensitivity_$Stamp.log")
$sensExit = $LASTEXITCODE
Log "SENSITIVITY exit=$sensExit"

Log "=== INCREMENTAL n=1e6 uniform+zipf seeds=1..5 max-batches=50 ==="
& python -u scripts/run_incremental.py `
  --n 1000000 `
  --updates 10000 `
  --max-batches 50 `
  --batch-sizes 1 10 100 1000 10000 `
  --seeds 1 2 3 4 5 `
  --distributions uniform zipf `
  --out results/incremental.csv `
  2>&1 | Tee-Object -FilePath (Join-Path $LogDir "incremental_$Stamp.log")
$incExit = $LASTEXITCODE
Log "INCREMENTAL exit=$incExit"

Log "DONE static=$staticExit sensitivity=$sensExit incremental=$incExit"
if (($staticExit -ne 0) -or ($sensExit -ne 0) -or ($incExit -ne 0)) { exit 1 }
exit 0
