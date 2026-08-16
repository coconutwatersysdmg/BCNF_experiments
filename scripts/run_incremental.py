"""Incremental vs static rebuild differential benchmark (contamination-free).

Workload generation (UpdateOp planning) is OUTSIDE all algorithm timers.
Incremental and Static replay the exact same batch_plan.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker
from algorithms.incremental import BCNFRepairState, PlainRepairState, UpdateOp
from common.fd_utils import project_row
from common.io_utils import write_csv
from common.reproducibility import get_code_version, set_global_seed, snapshot_config
from config import FINAL_RESULTS_DIR, INCREMENTAL_BATCH_SIZES
from generators.conflict_injector import (
    _mutate_nonkey,
    compute_deleted_block_stats,
    make_positive_repair_case,
)
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


# ---------------------------------------------------------------------------
# Legacy Zipf helpers (NOT used by final paper benchmarks)
# ---------------------------------------------------------------------------


def _zipf_choice(items: Sequence[Any], rng: random.Random, alpha: float = 1.0):
    """LEGACY: sample from items with Zipf-like preference. Do not use in final bench."""
    n = len(items)
    if n == 0:
        raise ValueError("empty")
    if n == 1:
        return items[0]
    u = max(rng.random(), 1e-12)
    if alpha <= 1e-12:
        return items[int(u * n) % n]
    rank = int(u ** (-1.0 / alpha)) - 1
    rank = max(0, min(n - 1, rank))
    return items[rank]


def _choose_from_set(rows: set, rng: random.Random, distribution: str):
    """LEGACY helper for mixed correctness stress only."""
    if not rows:
        raise ValueError("empty")
    seq = tuple(rows)
    if distribution.startswith("zipf"):
        return _zipf_choice(seq, rng, alpha=1.0)
    return rng.choice(seq)


def _fingerprint(rows: set) -> str:
    """Cheap size+xor fingerprint for large-n equality checks."""
    h = 0
    for t in rows:
        h ^= hash(t)
    return f"{len(rows)}:{h & 0xFFFFFFFFFFFFFFFF:016x}"


def _states_match(
    inc: BCNFRepairState,
    plain: PlainRepairState,
    *,
    full_equality: bool,
) -> bool:
    if full_equality:
        return (
            inc.r == plain.r
            and inc.r_prime == plain.r_prime
            and inc.D == plain.D
        )
    return (
        len(inc.r) == len(plain.r)
        and len(inc.r_prime) == len(plain.r_prime)
        and len(inc.D) == len(plain.D)
        and _fingerprint(inc.r) == _fingerprint(plain.r)
        and _fingerprint(inc.r_prime) == _fingerprint(plain.r_prime)
        and _fingerprint(inc.D) == _fingerprint(plain.D)
    )


# ---------------------------------------------------------------------------
# Workload planners (outside timers)
# ---------------------------------------------------------------------------


def _conflicting_deleted_for_parent(
    schema,
    parent,
    primary_key,
    existing: set,
    rng: random.Random,
    tag: int,
):
    """Generate a unique conflicting deleted tuple for retained parent."""
    for attempt in range(1000):
        t = _mutate_nonkey(schema, parent, primary_key, rng, tag=(tag, attempt))
        if t not in existing and t != parent:
            return t
    raise RuntimeError("failed to synthesize unique conflicting deleted tuple")


def plan_d_only_batch(
    schema,
    state_view: BCNFRepairState,
    rng: random.Random,
    batch_size: int,
    tag_counter: list[int],
) -> list[UpdateOp]:
    """Workload A: add/remove conflicting deleted tuples only (repair stays valid)."""
    ops: list[UpdateOp] = []
    # Working mirrors of partitions for planning (not the real state)
    D = set(state_view.D)
    r = set(state_view.r)
    r_prime = set(state_view.r_prime)
    primary_key = state_view.index_keys[0]
    parents = list(r_prime)

    for _ in range(batch_size):
        # Prefer add when D is small; otherwise mix 50/50
        do_add = (not D) or (rng.random() < 0.5) or (len(D) < max(1, len(r_prime) // 20))
        if do_add and parents:
            parent = rng.choice(parents)
            tag_counter[0] += 1
            t = _conflicting_deleted_for_parent(
                schema, parent, primary_key, r, rng, tag_counter[0]
            )
            ops.append(UpdateOp("add_deleted", t))
            r.add(t)
            D.add(t)
        elif D:
            t = rng.choice(tuple(D))
            ops.append(UpdateOp("remove_deleted", t))
            D.remove(t)
            r.remove(t)
        else:
            break
    return ops


def plan_swap_batch(
    schema,
    state_view: BCNFRepairState,
    rng: random.Random,
    batch_size: int,
) -> tuple[list[UpdateOp], int]:
    """Workload B: representative swaps within conflict blocks.

    Each logical swap = 2 primitive moves. Returns (ops, primitive_update_count).
    """
    ops: list[UpdateOp] = []
    primary_key = state_view.index_keys[0]
    attr_to_idx = schema.attr_to_idx
    k = primary_key

    retained_by_v = {
        project_row(s, k, attr_to_idx): s for s in state_view.r_prime
    }

    candidates: list[tuple[Any, Row, Row]] = []
    for v, group in state_view.G[k].items():
        if not group:
            continue
        if state_view.C[k].get(v, 0) != 1:
            continue
        retained = retained_by_v.get(v)
        if retained is None:
            continue
        t = next(iter(group))
        candidates.append((v, retained, t))

    if not candidates:
        return [], 0

    rng.shuffle(candidates)
    for item in candidates[:batch_size]:
        _v, s, t = item
        ops.append(UpdateOp("swap", s, aux_row=t))

    return ops, len(ops) * 2


def plan_mixed_stress_batch(
    schema,
    state_view: BCNFRepairState,
    rng: random.Random,
    batch_size: int,
    fresh_counter: list[int],
) -> list[UpdateOp]:
    """Mixed primitive updates for correctness stress only (not paper perf)."""
    ops: list[UpdateOp] = []
    D = set(state_view.D)
    r = set(state_view.r)
    r_prime = set(state_view.r_prime)
    kinds = ["add_deleted", "remove_deleted", "move_deleted_to_retained", "move_retained_to_deleted"]

    for _ in range(batch_size):
        kind = rng.choice(kinds)
        if kind == "add_deleted":
            fresh_counter[0] += 1
            cid = fresh_counter[0]
            t = tuple(("upd", cid, a) for a in schema.attributes)
            if t in r:
                continue
            ops.append(UpdateOp("add_deleted", t))
            r.add(t)
            D.add(t)
        elif kind == "remove_deleted":
            if not D:
                continue
            t = rng.choice(tuple(D))
            ops.append(UpdateOp("remove_deleted", t))
            D.remove(t)
            r.remove(t)
        elif kind == "move_deleted_to_retained":
            if not D:
                continue
            t = rng.choice(tuple(D))
            ops.append(UpdateOp("move_deleted_to_retained", t))
            D.remove(t)
            r_prime.add(t)
        else:
            if not r_prime:
                continue
            t = rng.choice(tuple(r_prime))
            ops.append(UpdateOp("move_retained_to_deleted", t))
            r_prime.remove(t)
            D.add(t)
    return ops


def run_one_config(
    schema,
    inst,
    *,
    workload: str,
    batch_sizes: Sequence[int],
    batches_per_config: int,
    seed: int,
    block_distribution: str,
    zipf_alpha: float,
    rows: list[dict[str, Any]],
    full_equality: bool,
    code_version: str,
) -> bool:
    """Run all batch sizes. Return False on any mismatch."""
    block_stats = {
        k: inst.metadata.get(k)
        for k in (
            "active_block_count",
            "mean_deleted_block_size",
            "median_deleted_block_size",
            "p95_deleted_block_size",
            "p99_deleted_block_size",
            "max_deleted_block_size",
        )
    }
    dist_label = (
        block_distribution
        if block_distribution == "uniform"
        else f"zipf_{zipf_alpha}"
    )

    for batch_size in batch_sizes:
        rng = random.Random(seed + batch_size * 17 + hash(dist_label) % 997)
        inc_state = BCNFRepairState(schema, inst.r, inst.r_prime, use_key_cover=False)
        plain_state = PlainRepairState(inst.r, inst.r_prime)
        tag_counter = [0]
        fresh_counter = [0]
        all_match = True

        for b in range(batches_per_config):
            # ---- Plan OUTSIDE timers ----
            if workload == "d_only":
                batch_plan = plan_d_only_batch(
                    schema, inc_state, rng, batch_size, tag_counter
                )
                primitive_update_count = len(batch_plan)
            elif workload == "swap":
                batch_plan, primitive_update_count = plan_swap_batch(
                    schema, inc_state, rng, batch_size
                )
            else:  # mixed_stress
                batch_plan = plan_mixed_stress_batch(
                    schema, inc_state, rng, batch_size, fresh_counter
                )
                primitive_update_count = len(batch_plan)

            if not batch_plan:
                # Nothing to do; still record a no-op measurement of 0
                rows.append(
                    {
                        "workload": workload,
                        "batch_size": batch_size,
                        "batch_index": b,
                        "block_distribution": dist_label,
                        "zipf_alpha": zipf_alpha if dist_label.startswith("zipf") else "",
                        "n": len(inst.r),
                        "r_size": len(inst.r),
                        "r_prime_size": len(inst.r_prime),
                        "n_r": len(inc_state.r),
                        "n_r_prime": len(inc_state.r_prime),
                        "deleted_count": len(inc_state.D),
                        "seed": seed,
                        "incremental_total_time": 0.0,
                        "static_update_time": 0.0,
                        "static_check_time": 0.0,
                        "static_total_time": 0.0,
                        "speedup": "",
                        "touched_block_entries": 0,
                        "touched_block_count": 0,
                        "primitive_update_count": 0,
                        "result_match": True,
                        "inc_is_repair": inc_state.is_repair(),
                        "static_is_repair": True,
                        "code_version": code_version,
                        **block_stats,
                    }
                )
                continue

            # ---- Incremental timed ----
            inc_state.reset_work_counters()
            t0 = time.perf_counter()
            inc_state.apply_batch(batch_plan)
            inc_repair = inc_state.is_repair()
            inc_t = time.perf_counter() - t0

            # ---- Static timed: apply same plan + rebuild/check ----
            t_su0 = time.perf_counter()
            plain_state.apply_batch(batch_plan)
            static_update_t = time.perf_counter() - t_su0

            t_sc0 = time.perf_counter()
            static = BCNFRepairChecker(schema, use_key_cover=False)
            static.index_keys = list(inc_state.index_keys)
            sres = static.check(
                list(plain_state.r),
                list(plain_state.r_prime),
                collect_certificates=False,
            )
            static_check_t = time.perf_counter() - t_sc0
            static_total_t = static_update_t + static_check_t

            # ---- Correctness outside timers ----
            if not inc_state.candidate_consistent():
                match = (
                    (not sres.is_repair)
                    and (not sres.candidate_consistent)
                    and (not inc_repair)
                )
            else:
                match = (sres.is_repair == inc_repair) and sres.candidate_consistent

            state_ok = _states_match(inc_state, plain_state, full_equality=full_equality)
            match = match and state_ok
            if not match:
                all_match = False

            # Refresh block stats from current deleted set (cheap on primary key)
            live_stats = compute_deleted_block_stats(
                schema,
                list(inc_state.r_prime),
                list(inc_state.D),
                inc_state.index_keys,
            )

            speedup = (static_total_t / inc_t) if inc_t > 0 else float("inf")
            rows.append(
                {
                    "workload": workload,
                    "batch_size": batch_size,
                    "batch_index": b,
                    "block_distribution": dist_label,
                    "zipf_alpha": zipf_alpha if dist_label.startswith("zipf") else "",
                    "n": len(inst.r),
                    "r_size": len(inc_state.r),
                    "r_prime_size": len(inc_state.r_prime),
                    "n_r": len(inc_state.r),
                    "n_r_prime": len(inc_state.r_prime),
                    "deleted_count": len(inc_state.D),
                    "seed": seed,
                    "incremental_total_time": inc_t,
                    "static_update_time": static_update_t,
                    "static_check_time": static_check_t,
                    "static_total_time": static_total_t,
                    "speedup": speedup,
                    "touched_block_entries": inc_state.touched_block_entries,
                    "touched_block_count": inc_state.touched_block_count,
                    "primitive_update_count": primitive_update_count,
                    "result_match": match,
                    "inc_is_repair": inc_repair,
                    "static_is_repair": sres.is_repair,
                    "code_version": code_version,
                    **live_stats,
                }
            )

            if not match:
                print(
                    f"MISMATCH seed={seed} workload={workload} batch={batch_size} "
                    f"b={b} state_ok={state_ok} inc={inc_repair} static={sres.is_repair}",
                    file=sys.stderr,
                    flush=True,
                )
                return False

        print(
            f"seed={seed} dist={dist_label} workload={workload} "
            f"batch_size={batch_size} batches={batches_per_config} all_match={all_match}",
            flush=True,
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Incremental vs static differential benchmark (fair timing)"
    )
    parser.add_argument("--n", type=int, default=1_000_000, help="base_clean_size (= |r'| before conflicts)")
    parser.add_argument("--conflict-ratio", type=float, default=0.1)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=list(INCREMENTAL_BATCH_SIZES))
    parser.add_argument("--batches-per-config", type=int, default=100)
    parser.add_argument("--seed", type=int, default=None, help="Single seed (legacy)")
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument(
        "--block-distributions",
        nargs="+",
        default=["uniform", "zipf_1.2"],
        help="Deleted conflict block size distributions",
    )
    parser.add_argument(
        "--workloads",
        nargs="+",
        default=["d_only", "swap"],
        choices=["d_only", "swap", "mixed_stress"],
    )
    parser.add_argument("--key-width", type=int, default=1)
    parser.add_argument("--fd-count", type=int, default=4)
    parser.add_argument(
        "--full-equality",
        action="store_true",
        help="Full set equality each batch (use for smoke/correctness)",
    )
    parser.add_argument("--out", type=Path, default=FINAL_RESULTS_DIR / "incremental.csv")
    parser.add_argument(
        "--config-out",
        type=Path,
        default=FINAL_RESULTS_DIR / "incremental_config.json",
    )
    args = parser.parse_args()

    seeds = args.seeds if args.seeds is not None else ([args.seed] if args.seed is not None else [42])
    code_version = get_code_version()

    set_global_seed(seeds[0])
    snapshot_config(
        args.config_out,
        {
            **{k: v for k, v in vars(args).items()},
            "seeds": seeds,
            "code_version": code_version,
            "n_definition": "n = |r| (dirty database size) in CSV; --n is base_clean_size",
        },
    )

    fieldnames = [
        "workload",
        "batch_size",
        "batch_index",
        "block_distribution",
        "zipf_alpha",
        "n",
        "r_size",
        "r_prime_size",
        "n_r",
        "n_r_prime",
        "deleted_count",
        "seed",
        "incremental_total_time",
        "static_update_time",
        "static_check_time",
        "static_total_time",
        "speedup",
        "touched_block_entries",
        "touched_block_count",
        "active_block_count",
        "mean_deleted_block_size",
        "median_deleted_block_size",
        "p95_deleted_block_size",
        "p99_deleted_block_size",
        "max_deleted_block_size",
        "primitive_update_count",
        "result_match",
        "inc_is_repair",
        "static_is_repair",
        "code_version",
    ]
    rows: list[dict[str, Any]] = []

    for seed in seeds:
        schema = generate_single_key_bcnf(
            n_attrs=8, key_width=args.key_width, fd_count=args.fd_count, seed=seed
        )
        for dist in args.block_distributions:
            zipf_alpha = 1.2
            dist_name = dist
            if dist.startswith("zipf"):
                parts = dist.split("_")
                if len(parts) == 2:
                    zipf_alpha = float(parts[1])
                dist_name = "zipf"

            print(
                f"Generating base_clean_size={args.n} seed={seed} dist={dist} ...",
                flush=True,
            )
            clean = generate_clean_instance(schema, n=args.n, seed=seed)
            inst = make_positive_repair_case(
                schema,
                clean,
                conflict_ratio=args.conflict_ratio,
                seed=seed + 1,
                block_distribution=dist_name,
                zipf_alpha=zipf_alpha,
            )
            del clean

            # Sanity: uniform vs zipf must differ in block stats when both requested
            print(
                f"  block_stats: active={inst.metadata.get('active_block_count')} "
                f"mean={inst.metadata.get('mean_deleted_block_size')} "
                f"max={inst.metadata.get('max_deleted_block_size')}",
                flush=True,
            )

            for workload in args.workloads:
                ok = run_one_config(
                    schema,
                    inst,
                    workload=workload,
                    batch_sizes=args.batch_sizes,
                    batches_per_config=args.batches_per_config,
                    seed=seed,
                    block_distribution=dist_name,
                    zipf_alpha=zipf_alpha,
                    rows=rows,
                    full_equality=args.full_equality or args.n <= 20_000,
                    code_version=code_version,
                )
                if not ok:
                    print("INCREMENTAL MISMATCH DETECTED", file=sys.stderr)
                    write_csv(args.out, fieldnames, rows)
                    return 1

    # Cross-check: if both uniform and zipf present for same seed, block stats must differ
    by_dist: dict[str, list[float]] = {}
    for row in rows:
        if row.get("batch_index") == 0 and row.get("batch_size") == batch_sizes_first(args):
            d = str(row["block_distribution"])
            by_dist.setdefault(d, []).append(float(row.get("max_deleted_block_size") or 0))
    if len(by_dist) >= 2:
        means = {d: (sum(vs) / len(vs) if vs else 0.0) for d, vs in by_dist.items()}
        vals = list(means.values())
        if max(vals) <= min(vals) * 1.05 + 1e-9:
            print(
                f"ERROR: block distributions look identical: {means}. "
                "Generator failed Phase 5 requirement.",
                file=sys.stderr,
            )
            write_csv(args.out, fieldnames, rows)
            return 1

    write_csv(args.out, fieldnames, rows)
    print(f"Wrote {args.out}; all result_match=True ({len(rows)} rows)", flush=True)
    return 0


def batch_sizes_first(args) -> int:
    return int(args.batch_sizes[0]) if args.batch_sizes else 1


if __name__ == "__main__":
    raise SystemExit(main())
