"""Phase 15: Incremental vs static correctness stress (not for performance plots)."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker
from algorithms.incremental import BCNFRepairState, UpdateOp
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf
from scripts.run_incremental import plan_mixed_stress_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Incremental differential stress test")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--updates", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    schema = generate_single_key_bcnf(n_attrs=6, key_width=1, fd_count=3, seed=args.seed)
    clean = generate_clean_instance(schema, n=args.n, seed=args.seed)
    inst = make_positive_repair_case(schema, clean, conflict_ratio=0.1, seed=args.seed + 1)
    state = BCNFRepairState(schema, inst.r, inst.r_prime, use_key_cover=False)
    rng = random.Random(args.seed)
    fresh = [0]

    for step in range(args.updates):
        plan = plan_mixed_stress_batch(schema, state, rng, 1, fresh)
        if not plan:
            continue
        state.apply_batch(plan)

        static = BCNFRepairChecker(schema, use_key_cover=False)
        static.index_keys = list(state.index_keys)
        res = static.check(list(state.r), list(state.r_prime), collect_certificates=False)
        inc = state.is_repair()
        if not state.candidate_consistent():
            ok = (not res.candidate_consistent) and (not res.is_repair) and (not inc)
        else:
            ok = res.candidate_consistent and (res.is_repair == inc)
        if not ok:
            print(
                f"MISMATCH step={step} inc={inc} static={res.is_repair} "
                f"cons_inc={state.candidate_consistent()} cons_static={res.candidate_consistent}",
                file=sys.stderr,
            )
            return 1
        if (step + 1) % 500 == 0:
            print(f"ok through step {step + 1}", flush=True)

    print(f"INCREMENTAL STRESS OK: {args.updates} updates on n={args.n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
