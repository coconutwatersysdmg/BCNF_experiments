"""Run 1000-case correctness comparison across all S-repair algorithms."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import is_subset_repair_bcnf_index
from algorithms.fd_hash import is_subset_repair_fd_hash
from algorithms.general import is_subset_repair_exhaustive
from algorithms.singleton_fullscan import is_subset_repair_singleton_fullscan
from common.io_utils import write_csv
from common.reproducibility import set_global_seed, snapshot_config
from config import RESULTS_DIR
from generators.conflict_injector import make_negative_repair_case, make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_multi_key_bcnf, generate_single_key_bcnf


def build_case(case_id: int, seed: int, want_repair: bool, max_deleted: int):
    rng_seed = seed + case_id * 17
    family = "single" if (case_id % 3) != 0 else "multi"
    if family == "single":
        kw = 1 if case_id % 2 == 0 else 2
        schema = generate_single_key_bcnf(
            n_attrs=6 + (case_id % 3),
            key_width=kw,
            fd_count=2 + (case_id % 3),
            seed=rng_seed,
        )
    else:
        schema = generate_multi_key_bcnf(
            n_attrs=8,
            n_keys=2,
            key_width=1,
        )
    n = 10 + (case_id % 6)  # 10..15 retained base
    clean = generate_clean_instance(schema, n=n, seed=rng_seed)
    # Cap conflicts so |D| <= max_deleted
    # positive: n_conflict ≈ ratio * n; keep ratio small
    ratio = min(0.4, max_deleted / max(n, 1))
    if want_repair:
        inst = make_positive_repair_case(
            schema, clean, conflict_ratio=ratio, seed=rng_seed + 1, verify_small=False
        )
    else:
        # leave room for addable tuples
        ratio = min(ratio, max(0.0, (max_deleted - 1) / max(n, 1)))
        inst = make_negative_repair_case(
            schema,
            clean,
            conflict_ratio=ratio,
            seed=rng_seed + 1,
            addable_position=0.5,
            n_addable=1,
        )
    # If somehow too large, shrink by regenerating with smaller n
    if len(inst.deleted_rows) > max_deleted:
        clean = generate_clean_instance(schema, n=max(6, max_deleted), seed=rng_seed)
        if want_repair:
            inst = make_positive_repair_case(
                schema, clean, conflict_ratio=0.3, seed=rng_seed + 2
            )
        else:
            inst = make_negative_repair_case(
                schema, clean, conflict_ratio=0.2, seed=rng_seed + 2, n_addable=1
            )
    return schema, inst


def main() -> int:
    parser = argparse.ArgumentParser(description="Correctness comparison (oracle vs baselines)")
    parser.add_argument("--cases", type=int, default=1000)
    parser.add_argument("--max-deleted", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "correctness.csv",
    )
    args = parser.parse_args()

    set_global_seed(args.seed)
    snapshot_config(
        RESULTS_DIR / "correctness_config.json",
        {"cases": args.cases, "max_deleted": args.max_deleted, "seed": args.seed},
    )

    n_cases = args.cases
    n_pass = n_cases // 2
    rows = []
    mismatches = 0

    for case_id in range(n_cases):
        want_repair = case_id < n_pass
        schema, inst = build_case(case_id, args.seed, want_repair, args.max_deleted)
        deleted_count = len(inst.deleted_rows)

        oracle = is_subset_repair_exhaustive(
            schema, inst.r, inst.r_prime, max_deleted=args.max_deleted
        )
        singleton = is_subset_repair_singleton_fullscan(schema, inst.r, inst.r_prime)
        fd_hash = is_subset_repair_fd_hash(schema, inst.r, inst.r_prime)
        bcnf = is_subset_repair_bcnf_index(schema, inst.r, inst.r_prime)

        flags = {
            "oracle": oracle.is_repair,
            "singleton": singleton.is_repair,
            "fd_hash": fd_hash.is_repair,
            "bcnf": bcnf.is_repair,
        }
        # Also require consistency agreement when oracle says inconsistent
        cons = {
            "oracle": oracle.candidate_consistent,
            "singleton": singleton.candidate_consistent,
            "fd_hash": fd_hash.candidate_consistent,
            "bcnf": bcnf.candidate_consistent,
        }
        all_match = len(set(flags.values())) == 1 and len(set(cons.values())) == 1
        if want_repair and not oracle.is_repair:
            # Construction bug — still record mismatch
            all_match = False
        if (not want_repair) and oracle.is_repair:
            all_match = False
        if not all_match:
            mismatches += 1

        rows.append(
            {
                "case_id": case_id,
                "seed": args.seed,
                "n": len(inst.r),
                "deleted_count": deleted_count,
                "expected_repair": want_repair,
                "oracle": oracle.is_repair,
                "singleton": singleton.is_repair,
                "fd_hash": fd_hash.is_repair,
                "bcnf": bcnf.is_repair,
                "all_match": all_match,
            }
        )

    fieldnames = [
        "case_id",
        "seed",
        "n",
        "deleted_count",
        "expected_repair",
        "oracle",
        "singleton",
        "fd_hash",
        "bcnf",
        "all_match",
    ]
    write_csv(args.out, fieldnames, rows)
    print(f"Wrote {args.out}  cases={n_cases} mismatches={mismatches}")
    if mismatches:
        print("CORRECTNESS FAILED: algorithm disagreement or construction mismatch", file=sys.stderr)
        return 1
    print("CORRECTNESS OK: all_match=True for all cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
