"""Sequential formal paper-scale experiment driver."""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
LOG = RESULTS / f"formal_master_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], log_name: str) -> int:
    log("RUN: " + " ".join(cmd))
    out_path = RESULTS / log_name
    with out_path.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            out.write(line)
            out.flush()
        return proc.wait()


def main() -> int:
    log(f"START formal pipeline root={ROOT}")
    log("Skip n=1e7: insufficient free RAM for safe 1e7 runs on this machine")

    # Probe RAM
    try:
        import psutil  # type: ignore

        avail = psutil.virtual_memory().available / 1e9
        log(f"available_RAM_GB={avail:.2f}")
    except Exception as exc:  # noqa: BLE001
        log(f"RAM probe failed: {exc}")

    t0 = time.perf_counter()
    rc1 = run(
        [
            sys.executable,
            "-u",
            "scripts/run_static.py",
            "--sizes",
            "1000",
            "10000",
            "100000",
            "1000000",
            "--seeds",
            "1",
            "2",
            "3",
            "4",
            "5",
            "--case",
            "both",
            "--repeats",
            "5",
            "--warmup",
            "1",
            "--timeout",
            "600",
            "--hard-timeout",
            "--out",
            "results/static.csv",
        ],
        "static_formal.log",
    )
    log(f"STATIC exit={rc1} elapsed_min={(time.perf_counter()-t0)/60:.1f}")

    t1 = time.perf_counter()
    rc2 = run(
        [
            sys.executable,
            "-u",
            "scripts/run_sensitivity.py",
            "--n",
            "1000000",
            "--seeds",
            "1",
            "2",
            "3",
            "4",
            "5",
            "--repeats",
            "5",
            "--experiments",
            "conflict_ratio",
            "fd_count",
            "key_width",
            "--out",
            "results/sensitivity.csv",
        ],
        "sensitivity_formal.log",
    )
    log(f"SENSITIVITY exit={rc2} elapsed_min={(time.perf_counter()-t1)/60:.1f}")

    t2 = time.perf_counter()
    rc3 = run(
        [
            sys.executable,
            "-u",
            "scripts/run_incremental.py",
            "--n",
            "1000000",
            "--updates",
            "10000",
            "--max-batches",
            "50",
            "--batch-sizes",
            "1",
            "10",
            "100",
            "1000",
            "10000",
            "--seeds",
            "1",
            "2",
            "3",
            "4",
            "5",
            "--distributions",
            "uniform",
            "zipf",
            "--out",
            "results/incremental.csv",
        ],
        "incremental_formal.log",
    )
    log(f"INCREMENTAL exit={rc3} elapsed_min={(time.perf_counter()-t2)/60:.1f}")
    log(f"DONE static={rc1} sensitivity={rc2} incremental={rc3}")
    return 0 if (rc1 == 0 and rc2 == 0 and rc3 == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
