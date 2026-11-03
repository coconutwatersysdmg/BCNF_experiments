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
from common.reproducibility import get_code_version, set_global_seed, snapshot_config
from config import (
    FINAL_RESULTS_DIR,
    SENSITIVITY_BLOCK_DISTRIBUTIONS,
    SENSITIVITY_CONFLICT_RATIOS,
    SENSITIVITY_FD_COUNTS,
    SENSITIVITY_KEY_WIDTHS,
    SENSITIVITY_N,
)
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


def _eval_pair(schema, inst, repeats: int = 5, code_version: str = "final-audit-v1"):
    requested_fd_count = len(schema.fds)
    actual_nontrivial_fd_count = len(nontrivial_fds(schema.fds))
    checker = BCNFRepairChecker(schema, use_key_cover=False)
    bcnf_idx = checker.index_count
    compression = (
        (actual_nontrivial_fd_count - bcnf_idx) / actual_nontrivial_fd_count
        if actual_nontrivial_fd_count
        else 0.0
    )

    rows = []
    last_results: dict[str, Any] = {}
    for algo_name, fn in (
        ("FD-Hash", lambda s, r, rp: is_subset_repair_fd_hash(s, r, rp)),
        (
            "BCNF-Index",
            lambda s, r, rp: is_subset_repair_bcnf_index(
                s, r, rp, use_key_cover=False, collect_certificates=False
            ),
        ),
    ):
        times = []
        last = None
        for rep in range(repeats):
            with measure_resources() as mem:
                last = fn(schema, inst.r, inst.r_prime)
            # Correctness assertions for PASS cases
            if not last.candidate_consistent or not last.is_repair:
                raise AssertionError(
                    f"{algo_name} failed PASS assertion: "
                    f"consistent={last.candidate_consistent} is_repair={last.is_repair}"
                )
            times.append(last.total_time_sec)
            last_results[algo_name] = last
            rows.append(
                {
                    "algorithm": algo_name,
                    "rep": rep,
                    "total_time_sec": last.total_time_sec,
                    "build_time_sec": last.build_time_sec,
                    "check_time_sec": last.check_time_sec,
                    "validation_time_sec": last.metadata.get("validation_time_sec", ""),
                    "python_peak_mb": mem["python_peak_mb"],
                    "rss_peak_mb": mem["rss_peak_mb"] if mem["rss_peak_mb"] is not None else "",
                    "result": last.is_repair,
                    "candidate_consistent": last.candidate_consistent,
                    "requested_fd_count": requested_fd_count,
                    "actual_nontrivial_fd_count": actual_nontrivial_fd_count,
                    "raw_fd_index_count": actual_nontrivial_fd_count,
                    "bcnf_index_count": bcnf_idx,
                    "compression_ratio": compression,
                    "index_count": last.index_count,
                    "code_version": code_version,
                }
            )
        summary = summarize_runs(times)
        print(
            f"  {algo_name}: median={summary['median']:.6f}s "
            f"compression={compression:.3f} "
            f"actual_fd={actual_nontrivial_fd_count} bcnf_idx={bcnf_idx}"
        )

    if last_results["FD-Hash"].is_repair != last_results["BCNF-Index"].is_repair:
        raise AssertionError("FD-Hash / BCNF-Index is_repair mismatch on PASS case")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sensitivity analysis for FD-Hash vs BCNF-Index")
    parser.add_argument("--n", type=int, default=SENSITIVITY_N, help="base_clean_size")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--experiments",
        nargs="+",
        default=["conflict_ratio", "fd_count", "key_width", "block_distribution"],
        choices=["conflict_ratio", "fd_count", "key_width", "block_distribution"],
    )
    parser.add_argument("--out", type=Path, default=FINAL_RESULTS_DIR / "sensitivity.csv")
    parser.add_argument(
        "--config-out",
        type=Path,
        default=FINAL_RESULTS_DIR / "sensitivity_config.json",
    )
    args = parser.parse_args()

    code_version = get_code_version()
    set_global_seed(args.seeds[0])
    snapshot_config(args.config_out, {**vars(args), "code_version": code_version})

    all_rows: list[dict[str, Any]] = []
    base = {
        "n": args.n,
        "conflict_ratio": 0.1,
        "fd_count": 4,
        "key_width": 1,
        "block_distribution": "uniform",
        "zipf_alpha": 1.2,
    }

    def run_cfg(exp_name: str, param_name: str, param_value: Any, cfg: dict):
        for seed in args.seeds:
            schema = generate_single_key_bcnf(
                n_attrs=8,
                key_width=cfg["key_width"],
                fd_count=cfg["fd_count"],
                seed=seed,
            )
            clean = generate_clean_instance(schema, n=cfg["n"], seed=seed, skew="uniform")
            dist = cfg["block_distribution"]
            zipf_alpha = float(cfg.get("zipf_alpha", 1.2))
            dist_name = dist
            if str(dist).startswith("zipf"):
                parts = str(dist).split("_")
                if len(parts) == 2:
                    zipf_alpha = float(parts[1])
                dist_name = "zipf"
            inst = make_positive_repair_case(
                schema,
                clean,
                conflict_ratio=cfg["conflict_ratio"],
                seed=seed + 3,
                block_distribution=dist_name,
                zipf_alpha=zipf_alpha,
            )
            print(f"{exp_name}: {param_name}={param_value} seed={seed}")
            for row in _eval_pair(schema, inst, repeats=args.repeats, code_version=code_version):
                row.update(
                    {
                        "experiment": exp_name,
                        "param_name": param_name,
                        "param_value": param_value,
                        "base_clean_size": cfg["n"],
                        "n": len(inst.r),  # paper n = |r|
                        "r_size": len(inst.r),
                        "r_prime_size": len(inst.r_prime),
                        "seed": seed,
                        "conflict_ratio": cfg["conflict_ratio"],
                        "fd_count": cfg["fd_count"],
                        "candidate_key_width": cfg["key_width"],
                        "block_distribution": inst.metadata.get(
                            "block_distribution", dist
                        ),
                        "zipf_alpha": inst.metadata.get("zipf_alpha", ""),
                        "deleted_count": len(inst.deleted_rows),
                        "active_block_count": inst.metadata.get("active_block_count", ""),
                        "mean_deleted_block_size": inst.metadata.get(
                            "mean_deleted_block_size", ""
                        ),
                        "max_deleted_block_size": inst.metadata.get(
                            "max_deleted_block_size", ""
                        ),
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

    if "block_distribution" in args.experiments:
        for bd in SENSITIVITY_BLOCK_DISTRIBUTIONS:
            cfg = dict(base)
            cfg["block_distribution"] = bd
            run_cfg("D_block_distribution", "block_distribution", bd, cfg)

    fieldnames = [
        "experiment",
        "param_name",
        "param_value",
        "algorithm",
        "base_clean_size",
        "n",
        "r_size",
        "r_prime_size",
        "seed",
        "rep",
        "conflict_ratio",
        "fd_count",
        "requested_fd_count",
        "actual_nontrivial_fd_count",
        "candidate_key_width",
        "block_distribution",
        "zipf_alpha",
        "deleted_count",
        "active_block_count",
        "mean_deleted_block_size",
        "max_deleted_block_size",
        "raw_fd_index_count",
        "bcnf_index_count",
        "compression_ratio",
        "index_count",
        "validation_time_sec",
        "build_time_sec",
        "check_time_sec",
        "total_time_sec",
        "python_peak_mb",
        "rss_peak_mb",
        "result",
        "candidate_consistent",
        "code_version",
    ]
    write_csv(args.out, fieldnames, all_rows)
    print(f"Wrote {args.out} ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
