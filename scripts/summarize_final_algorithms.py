"""Summarize final algorithm CSVs into paper-ready tables."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.io_utils import read_csv, write_csv
from common.metrics import summarize_runs
from config import FINAL_RESULTS_DIR


def _f(row: dict[str, str], key: str) -> float:
    v = row.get(key, "")
    if v == "" or v is None:
        return float("nan")
    return float(v)


def _group_key(row: dict[str, str], keys: list[str]) -> tuple:
    return tuple(row.get(k, "") for k in keys)


def summarize_static(path: Path, out: Path) -> None:
    rows = read_csv(path)
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    keys = ["algorithm", "case_type", "n", "r_size"]
    for r in rows:
        if str(r.get("timeout", "")).lower() in ("true", "1"):
            groups[_group_key(r, keys)].append(r)
            continue
        groups[_group_key(r, keys)].append(r)

    out_rows = []
    for gk, items in sorted(groups.items()):
        timed = [i for i in items if str(i.get("timeout", "")).lower() not in ("true", "1")]
        if not timed:
            out_rows.append(
                {
                    "algorithm": gk[0],
                    "case_type": gk[1],
                    "n": gk[2],
                    "r_size": gk[3],
                    "median_total_time": "TO",
                    "mean_total_time": "TO",
                    "std_total_time": "",
                    "p25_total_time": "",
                    "p75_total_time": "",
                    "n_runs": len(items),
                    "timeout": True,
                }
            )
            continue
        times = [_f(i, "total_time_sec") for i in timed]
        mems = [_f(i, "python_peak_mb") for i in timed]
        ts = summarize_runs(times)
        ms = summarize_runs(mems)
        out_rows.append(
            {
                "algorithm": gk[0],
                "case_type": gk[1],
                "n": gk[2],
                "r_size": gk[3],
                "median_total_time": ts["median"],
                "mean_total_time": ts["mean"],
                "std_total_time": ts["std"],
                "p25_total_time": ts["p25"],
                "p75_total_time": ts["p75"],
                "median_python_peak_mb": ms["median"],
                "n_runs": len(timed),
                "timeout": False,
            }
        )

    # Speedup vs FD-Hash medians for BCNF
    by_cfg: dict[tuple, dict[str, float]] = {}
    for row in out_rows:
        if row.get("timeout"):
            continue
        cfg = (row["case_type"], row["n"])
        by_cfg.setdefault(cfg, {})[row["algorithm"]] = float(row["median_total_time"])
    for row in out_rows:
        if row["algorithm"] != "BCNF-Index" or row.get("timeout"):
            continue
        cfg = (row["case_type"], row["n"])
        base = by_cfg.get(cfg, {}).get("FD-Hash")
        if base and float(row["median_total_time"]) > 0:
            row["speedup_vs_fd_hash_median"] = base / float(row["median_total_time"])

    write_csv(
        out,
        [
            "algorithm",
            "case_type",
            "n",
            "r_size",
            "median_total_time",
            "mean_total_time",
            "std_total_time",
            "p25_total_time",
            "p75_total_time",
            "median_python_peak_mb",
            "speedup_vs_fd_hash_median",
            "n_runs",
            "timeout",
        ],
        out_rows,
    )


def summarize_sensitivity(path: Path, out: Path) -> None:
    rows = read_csv(path)
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    keys = [
        "experiment",
        "param_name",
        "param_value",
        "algorithm",
        "actual_nontrivial_fd_count",
        "block_distribution",
    ]
    for r in rows:
        groups[_group_key(r, keys)].append(r)

    out_rows = []
    medians: dict[tuple, float] = {}
    for gk, items in sorted(groups.items()):
        times = [_f(i, "total_time_sec") for i in items]
        mems = [_f(i, "python_peak_mb") for i in items]
        ts = summarize_runs(times)
        ms = summarize_runs(mems)
        row = {
            "experiment": gk[0],
            "param_name": gk[1],
            "param_value": gk[2],
            "algorithm": gk[3],
            "actual_nontrivial_fd_count": gk[4],
            "block_distribution": gk[5],
            "median_total_time": ts["median"],
            "mean_total_time": ts["mean"],
            "std_total_time": ts["std"],
            "p25_total_time": ts["p25"],
            "p75_total_time": ts["p75"],
            "median_python_peak_mb": ms["median"],
            "n_runs": len(items),
            "bcnf_index_count": items[0].get("bcnf_index_count", ""),
            "raw_fd_index_count": items[0].get("raw_fd_index_count", ""),
        }
        out_rows.append(row)
        medians[(gk[0], gk[1], gk[2], gk[3], gk[4], gk[5])] = ts["median"]

    for row in out_rows:
        if row["algorithm"] != "BCNF-Index":
            continue
        key_fd = (
            row["experiment"],
            row["param_name"],
            row["param_value"],
            "FD-Hash",
            row["actual_nontrivial_fd_count"],
            row["block_distribution"],
        )
        base = medians.get(key_fd)
        bcnf = float(row["median_total_time"])
        if base and bcnf > 0:
            row["speedup_vs_fd_hash_median"] = base / bcnf

    write_csv(
        out,
        [
            "experiment",
            "param_name",
            "param_value",
            "algorithm",
            "actual_nontrivial_fd_count",
            "block_distribution",
            "raw_fd_index_count",
            "bcnf_index_count",
            "median_total_time",
            "mean_total_time",
            "std_total_time",
            "p25_total_time",
            "p75_total_time",
            "median_python_peak_mb",
            "speedup_vs_fd_hash_median",
            "n_runs",
        ],
        out_rows,
    )


def summarize_incremental(path: Path, out: Path) -> None:
    rows = read_csv(path)
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    keys = ["workload", "batch_size", "block_distribution", "seed"]
    # Aggregate across batches for each config; also produce overall medians
    keys2 = ["workload", "batch_size", "block_distribution"]
    for r in rows:
        groups[_group_key(r, keys2)].append(r)

    out_rows = []
    for gk, items in sorted(groups.items()):
        inc = [_f(i, "incremental_total_time") for i in items]
        st = [_f(i, "static_total_time") for i in items]
        touched = [_f(i, "touched_block_entries") for i in items]
        si = summarize_runs(inc)
        ss = summarize_runs(st)
        stouch = summarize_runs(touched)
        med_inc = si["median"]
        med_st = ss["median"]
        speedup = (med_st / med_inc) if med_inc > 0 else float("nan")
        out_rows.append(
            {
                "workload": gk[0],
                "batch_size": gk[1],
                "block_distribution": gk[2],
                "median_incremental_total_time": med_inc,
                "mean_incremental_total_time": si["mean"],
                "std_incremental_total_time": si["std"],
                "p25_incremental_total_time": si["p25"],
                "p75_incremental_total_time": si["p75"],
                "median_static_total_time": med_st,
                "mean_static_total_time": ss["mean"],
                "speedup_median_static_over_median_inc": speedup,
                "median_touched_block_entries": stouch["median"],
                "mean_touched_block_entries": stouch["mean"],
                "n_runs": len(items),
            }
        )
    write_csv(
        out,
        [
            "workload",
            "batch_size",
            "block_distribution",
            "median_incremental_total_time",
            "mean_incremental_total_time",
            "std_incremental_total_time",
            "p25_incremental_total_time",
            "p75_incremental_total_time",
            "median_static_total_time",
            "mean_static_total_time",
            "speedup_median_static_over_median_inc",
            "median_touched_block_entries",
            "mean_touched_block_entries",
            "n_runs",
        ],
        out_rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize final algorithm experiment CSVs")
    parser.add_argument("--final-dir", type=Path, default=FINAL_RESULTS_DIR)
    args = parser.parse_args()
    d = args.final_dir

    if (d / "static.csv").exists():
        summarize_static(d / "static.csv", d / "table_static_summary.csv")
        print(f"Wrote {d / 'table_static_summary.csv'}")
    if (d / "sensitivity.csv").exists():
        summarize_sensitivity(d / "sensitivity.csv", d / "table_sensitivity_summary.csv")
        print(f"Wrote {d / 'table_sensitivity_summary.csv'}")
    if (d / "incremental.csv").exists():
        summarize_incremental(d / "incremental.csv", d / "table_incremental_summary.csv")
        print(f"Wrote {d / 'table_incremental_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
