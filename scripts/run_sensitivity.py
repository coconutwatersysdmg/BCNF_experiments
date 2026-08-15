"""Sensitivity experiments: vary one parameter at a time (default n=1e6)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker, is_subset_repair_bcnf_index
from algorithms.fd_hash import is_subset_repair_fd_hash
from common.fd_utils import nontrivial_fds
from common.io_utils import write_csv
from common.metrics import measure_resources, summarize_runs
from common.reproducibility import set_global_seed, snapshot_config
from config import (
    RESULTS_DIR,
    SENSITIVITY_CONFLICT_RATIOS,
    SENSITIVITY_FD_COUNTS,
    SENSITIVITY_KEY_WIDTHS,
    SENSITIVITY_N,
    SENSITIVITY_SKEWS,
)
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


def _eval_pair(schema, inst, repeats: int = 5):
    raw_fd = len(nontrivial_fds(schema.fds))
    checker = BCNFRepairChecker(schema, use_key_cover=True)
    bcnf_idx = checker.index_count
    compression = (raw_fd - bcnf_idx) / raw_fd if raw_fd else 0.0

    rows = []
    for algo_name, fn in (
        ("FD-Hash", is_subset_repair_fd_hash),
        ("BCNF-Index", is_subset_repair_bcnf_index),
    ):
        times = []
        last = None
        for rep in range(repeats):
            with measure_resources() as mem:
                last = fn(schema, inst.r, inst.r_prime)
            times.append(last.total_time_sec)
            rows.append(
                {
                    "algorithm": algo_name,
                    "rep": rep,
                    "total_time_sec": last.total_time_sec,
                    "build_time_sec": last.build_time_sec,
                    "check_time_sec": last.check_time_sec,
                    "python_peak_mb": mem["python_peak_mb"],
                    "rss_peak_mb": mem["rss_peak_mb"] if mem["rss_peak_mb"] is not None else "",
                    "result": last.is_repair,
                    "raw_fd_index_count": raw_fd,
                    "bcnf_index_count": bcnf_idx,
                    "compression_ratio": compression,
                    "index_count": last.index_count,
                }
            )
        summary = summarize_runs(times)
        print(f"  {algo_name}: median={summary['median']:.6f}s compression={compression:.3f}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sensitivity analysis for FD-Hash vs BCNF-Index")
    parser.add_argument("--n", type=int, default=SENSITIVITY_N)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--experiments",
        nargs="+",
        default=["conflict_ratio", "fd_count", "key_width", "skew"],
        choices=["conflict_ratio", "fd_count", "key_width", "skew"],
    )
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "sensitivity.csv")
    args = parser.parse_args()

    set_global_seed(args.seeds[0])
    snapshot_config(RESULTS_DIR / "sensitivity_config.json", vars(args))

    all_rows: list[dict[str, Any]] = []
    base = {
        "n": args.n,
        "conflict_ratio": 0.1,
        "fd_count": 4,
        "key_width": 1,
        "skew": "uniform",
    }

    def run_cfg(exp_name: str, param_name: str, param_value: Any, cfg: dict):
        for seed in args.seeds:
            schema = generate_single_key_bcnf(
                n_attrs=8,
                key_width=cfg["key_width"],
                fd_count=cfg["fd_count"],
                seed=seed,
            )
            clean = generate_clean_instance(schema, n=cfg["n"], seed=seed, skew=cfg["skew"])
            inst = make_positive_repair_case(
                schema, clean, conflict_ratio=cfg["conflict_ratio"], seed=seed + 3
            )
            print(f"{exp_name}: {param_name}={param_value} seed={seed}")
            for row in _eval_pair(schema, inst, repeats=args.repeats):
                row.update(
                    {
                        "experiment": exp_name,
                        "param_name": param_name,
                        "param_value": param_value,
                        "n": cfg["n"],
                        "seed": seed,
                        "conflict_ratio": cfg["conflict_ratio"],
                        "fd_count": cfg["fd_count"],
                        "candidate_key_width": cfg["key_width"],
                        "skew": cfg["skew"],
                        "deleted_count": len(inst.deleted_rows),
                    }
                )
                all_rows.append(row)

    if "conflict_ratio" in args.experiments:
        for cr in SENSITIVITY_CONFLICT_RATIOS:
            cfg = dict(base)
            cfg["conflict_ratio"] = cr
            run_cfg("A_conflict_ratio", "conflict_ratio", cr, cfg)

    if "fd_count" in args.experiments:
        for fc in SENSITIVITY_FD_COUNTS:
            cfg = dict(base)
            cfg["fd_count"] = fc
            run_cfg("B_fd_count", "fd_count", fc, cfg)

    if "key_width" in args.experiments:
        for kw in SENSITIVITY_KEY_WIDTHS:
            cfg = dict(base)
            cfg["key_width"] = kw
            run_cfg("C_key_width", "key_width", kw, cfg)

    if "skew" in args.experiments:
        for sk in SENSITIVITY_SKEWS:
            cfg = dict(base)
            cfg["skew"] = sk
            run_cfg("D_skew", "skew", sk, cfg)

    fieldnames = [
        "experiment",
        "param_name",
        "param_value",
        "algorithm",
        "n",
        "seed",
        "rep",
        "conflict_ratio",
        "fd_count",
        "candidate_key_width",
        "skew",
        "deleted_count",
        "raw_fd_index_count",
        "bcnf_index_count",
        "compression_ratio",
        "index_count",
        "build_time_sec",
        "check_time_sec",
        "total_time_sec",
        "python_peak_mb",
        "rss_peak_mb",
        "result",
    ]
    write_csv(args.out, fieldnames, all_rows)
    print(f"Wrote {args.out} ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
