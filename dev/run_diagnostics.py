"""Phase 16 diagnostics: certificate overhead + incremental timing/touched blocks."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker, is_subset_repair_bcnf_index
from algorithms.fd_hash import is_subset_repair_fd_hash
from common.io_utils import write_csv
from common.reproducibility import get_code_version, set_global_seed, snapshot_config
from config import FINAL_RESULTS_DIR
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf
from scripts.run_incremental import run_one_config


def diagnostic_a(out: Path) -> int:
    """Certificate overhead at n≈1e6 across conflict ratios."""
    import gc

    code_version = get_code_version()
    rows = []
    seed = 1
    schema = generate_single_key_bcnf(n_attrs=8, key_width=1, fd_count=4, seed=seed)
    print("Diagnostic A: generating clean n=1e6 once ...", flush=True)
    clean = generate_clean_instance(schema, n=1_000_000, seed=seed)

    for cr in (0.01, 0.05, 0.10, 0.20, 0.40):
        print(f"Diagnostic A: inject conflicts cr={cr} ...", flush=True)
        inst = make_positive_repair_case(schema, clean, conflict_ratio=cr, seed=seed + 11)
        r_size = len(inst.r)
        gc.collect()

        for rep in range(1):  # 1 repeat sufficient for overhead diagnosis
            t0 = time.perf_counter()
            fd = is_subset_repair_fd_hash(schema, inst.r, inst.r_prime)
            fd_t = time.perf_counter() - t0

            t1 = time.perf_counter()
            bcnf_dec = is_subset_repair_bcnf_index(
                schema, inst.r, inst.r_prime, use_key_cover=False, collect_certificates=False
            )
            bcnf_dec_wall = time.perf_counter() - t1

            rows.append(
                {
                    "diag": "A",
                    "mode": "decision",
                    "conflict_ratio": cr,
                    "r_size": r_size,
                    "r_prime_size": len(inst.r_prime),
                    "deleted_count": len(inst.deleted_rows),
                    "rep": rep,
                    "algorithm": "FD-Hash",
                    "check_time_sec": fd.check_time_sec,
                    "total_time_sec": fd.total_time_sec,
                    "wall_sec": fd_t,
                    "is_repair": fd.is_repair,
                    "code_version": code_version,
                }
            )
            rows.append(
                {
                    "diag": "A",
                    "mode": "decision",
                    "conflict_ratio": cr,
                    "r_size": r_size,
                    "r_prime_size": len(inst.r_prime),
                    "deleted_count": len(inst.deleted_rows),
                    "rep": rep,
                    "algorithm": "BCNF-Index",
                    "check_time_sec": bcnf_dec.check_time_sec,
                    "total_time_sec": bcnf_dec.total_time_sec,
                    "wall_sec": bcnf_dec_wall,
                    "is_repair": bcnf_dec.is_repair,
                    "code_version": code_version,
                }
            )
            print(
                f"  cr={cr} FD-Hash check={fd.check_time_sec:.4f}s "
                f"BCNF-decision check={bcnf_dec.check_time_sec:.4f}s",
                flush=True,
            )

            if not fd.is_repair or not bcnf_dec.is_repair:
                print("Diagnostic A correctness failure", file=sys.stderr)
                return 1

        if cr == 0.10:
            checker = BCNFRepairChecker(schema, use_key_cover=False)
            t2 = time.perf_counter()
            with_cert = checker.check(inst.r, inst.r_prime, collect_certificates=True)
            cert_wall = time.perf_counter() - t2
            rows.append(
                {
                    "diag": "A",
                    "mode": "certificate",
                    "conflict_ratio": cr,
                    "r_size": r_size,
                    "r_prime_size": len(inst.r_prime),
                    "deleted_count": len(inst.deleted_rows),
                    "rep": 0,
                    "algorithm": "BCNF-Index",
                    "check_time_sec": with_cert.check_time_sec,
                    "total_time_sec": with_cert.total_time_sec,
                    "wall_sec": cert_wall,
                    "is_repair": with_cert.is_repair,
                    "certificate_entries": len(with_cert.certificate),
                    "code_version": code_version,
                }
            )
            print(
                f"  cert vs decision (cr=0.10): "
                f"cert_check={with_cert.check_time_sec:.4f}s "
                f"decision_check={bcnf_dec.check_time_sec:.4f}s "
                f"entries={len(with_cert.certificate)}",
                flush=True,
            )

        del inst
        gc.collect()
        # Checkpoint after each ratio
        write_csv(
            out,
            [
                "diag",
                "mode",
                "conflict_ratio",
                "r_size",
                "r_prime_size",
                "deleted_count",
                "rep",
                "algorithm",
                "check_time_sec",
                "total_time_sec",
                "wall_sec",
                "is_repair",
                "certificate_entries",
                "code_version",
            ],
            rows,
        )

    print(f"Wrote {out}")
    return 0


def diagnostic_b(out: Path) -> int:
    """Incremental timing contamination check + touched_block_entries sanity."""
    code_version = get_code_version()
    rows: list = []
    n = 100_000
    schema = generate_single_key_bcnf(n_attrs=8, key_width=1, fd_count=4, seed=42)

    for dist, alpha in (("uniform", 1.2), ("zipf", 1.2)):
        clean = generate_clean_instance(schema, n=n, seed=42)
        inst = make_positive_repair_case(
            schema,
            clean,
            conflict_ratio=0.1,
            seed=43,
            block_distribution=dist,
            zipf_alpha=alpha,
        )
        del clean
        print(
            f"Diagnostic B dist={dist}: max_block={inst.metadata.get('max_deleted_block_size')} "
            f"mean={inst.metadata.get('mean_deleted_block_size')}",
            flush=True,
        )
        ok = run_one_config(
            schema,
            inst,
            workload="swap",
            batch_sizes=[1, 10, 100],
            batches_per_config=20,
            seed=42,
            block_distribution=dist,
            zipf_alpha=alpha,
            rows=rows,
            full_equality=False,
            code_version=code_version,
        )
        if not ok:
            return 1

        # Sanity: for swap batch=1, if max block is large, some runs should touch many entries
        swap1 = [
            r
            for r in rows
            if r.get("batch_size") == 1
            and str(r.get("block_distribution", "")).startswith(dist if dist == "uniform" else "zipf")
            and r.get("workload") == "swap"
        ]
        max_touched = max((int(r.get("touched_block_entries") or 0) for r in swap1), default=0)
        max_block = int(inst.metadata.get("max_deleted_block_size") or 0)
        print(f"  max_touched_block_entries(batch=1)={max_touched} max_block={max_block}")
        # Counter sanity: for any swap on a size-|G| block, touched ≈ 2*|G| (1→0 then 0→1).
        # Random batches may miss the global max block; require touched >> 1 when blocks > 1.
        if max_block > 1 and max_touched <= 1:
            print("Diagnostic B FAILED: touched_block_entries stuck at ~1", file=sys.stderr)
            write_csv(out, list(rows[0].keys()) if rows else ["error"], rows)
            return 1
        if max_block >= 5 and max_touched < 4:
            print(
                "Diagnostic B FAILED: touched_block_entries too small for non-trivial blocks",
                file=sys.stderr,
            )
            write_csv(out, list(rows[0].keys()) if rows else ["error"], rows)
            return 1

    write_csv(out, list(rows[0].keys()) if rows else [], rows)
    print(f"Wrote {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 16 diagnostics")
    parser.add_argument("--which", choices=["A", "B", "both"], default="both")
    parser.add_argument("--out-a", type=Path, default=FINAL_RESULTS_DIR / "diagnostic_A.csv")
    parser.add_argument("--out-b", type=Path, default=FINAL_RESULTS_DIR / "diagnostic_B.csv")
    args = parser.parse_args()
    set_global_seed(42)
    snapshot_config(
        FINAL_RESULTS_DIR / "diagnostic_config.json",
        {**vars(args), "code_version": get_code_version()},
    )
    if args.which in ("A", "both"):
        rc = diagnostic_a(args.out_a)
        if rc != 0:
            return rc
    if args.which in ("B", "both"):
        rc = diagnostic_b(args.out_b)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
