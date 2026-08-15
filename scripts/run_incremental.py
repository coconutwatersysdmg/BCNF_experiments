"""Incremental vs static rebuild differential benchmark."""

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
from algorithms.incremental import BCNFRepairState
from common.fd_utils import project_row
from common.io_utils import write_csv
from common.reproducibility import set_global_seed, snapshot_config
from config import INCREMENTAL_BATCH_SIZES, RESULTS_DIR
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


def _make_fresh(schema, counter: list[int]):
    counter[0] += 1
    cid = counter[0]
    return tuple(("upd", cid, a) for a in schema.attributes)


def _zipf_choice(items: Sequence[Any], rng: random.Random, alpha: float = 1.0):
    """Sample from items with Zipf-like preference for earlier ranks."""
    n = len(items)
    if n == 0:
        raise ValueError("empty")
    if n == 1:
        return items[0]
    # weights ~ 1/(i+1)^alpha over current list order
    # For large n avoid O(n) weight build every time: invert approx
    u = max(rng.random(), 1e-12)
    if alpha <= 1e-12:
        return items[int(u * n) % n]
    rank = int(u ** (-1.0 / alpha)) - 1
    rank = max(0, min(n - 1, rank))
    return items[rank]


def _choose_from_set(
    rows: set,
    rng: random.Random,
    distribution: str,
    schema=None,
    state: Optional[BCNFRepairState] = None,
    prefer_hot_blocks: bool = False,
):
    """Choose a row; under zipf, bias toward high retained-count key blocks."""
    if not rows:
        raise ValueError("empty")
    seq = tuple(rows)
    if distribution == "uniform" or not prefer_hot_blocks or state is None or schema is None:
        if distribution.startswith("zipf"):
            return _zipf_choice(seq, rng, alpha=1.0)
        return rng.choice(seq)

    # Build candidates weighted by max retained count over index keys
    # Sample a hot key-value from C, then a row in that block if present in rows.
    k = state.index_keys[0]
    counts = state.C[k]
    if not counts:
        return _zipf_choice(seq, rng, alpha=1.0)
    # Rank key values by count descending (stable by repr)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], repr(kv[0])))
    # Zipf over hot blocks
    pair = _zipf_choice(ranked, rng, alpha=1.0)
    v = pair[0]
    # Find rows in target set with this key value
    attr_to_idx = schema.attr_to_idx
    matches = [t for t in seq if project_row(t, k, attr_to_idx) == v]
    if matches:
        return rng.choice(matches)
    return _zipf_choice(seq, rng, alpha=1.0)


def apply_mixed_batch(
    state: BCNFRepairState,
    schema,
    rng: random.Random,
    batch_size: int,
    fresh_counter: list[int],
    distribution: str = "uniform",
) -> int:
    """Apply batch_size mixed updates. Returns affected_block_rows estimate."""
    affected = 0
    ops = ["add_deleted", "remove_deleted", "D_to_retained", "retained_to_D"]
    skewed = distribution.startswith("zipf")

    for _ in range(batch_size):
        op = rng.choice(ops)
        try:
            if op == "add_deleted":
                t = _make_fresh(schema, fresh_counter)
                state.add_deleted(t)
                affected += 1
            elif op == "remove_deleted":
                if not state.D:
                    continue
                t = _choose_from_set(
                    state.D, rng, distribution, schema, state, prefer_hot_blocks=skewed
                )
                state.remove_deleted(t)
                affected += 1
            elif op == "D_to_retained":
                if not state.D:
                    continue
                t = _choose_from_set(
                    state.D, rng, distribution, schema, state, prefer_hot_blocks=False
                )
                before_u = state.unblocked_count
                state.move_deleted_to_retained(t)
                affected += abs(before_u - state.unblocked_count) + 1
            else:
                if not state.r_prime:
                    continue
                t = _choose_from_set(
                    state.r_prime, rng, distribution, schema, state, prefer_hot_blocks=skewed
                )
                before_u = state.unblocked_count
                state.move_retained_to_deleted(t)
                affected += abs(before_u - state.unblocked_count) + 1
        except ValueError:
            continue
    return affected


def run_one_config(
    schema,
    inst,
    *,
    batch_sizes: Sequence[int],
    updates: int,
    max_batches: Optional[int],
    seed: int,
    distribution: str,
    rows: list[dict[str, Any]],
) -> bool:
    """Run all batch sizes for one (seed, distribution). Return False on mismatch."""
    for batch_size in batch_sizes:
        rng = random.Random(seed + batch_size * 17 + (0 if distribution == "uniform" else 99))
        state = BCNFRepairState(schema, inst.r, inst.r_prime)
        fresh_counter = [0]
        n_batches = max(1, updates // batch_size)
        if max_batches is not None:
            n_batches = min(n_batches, max_batches)
        all_match = True

        for b in range(n_batches):
            t0 = time.perf_counter()
            affected = apply_mixed_batch(
                state, schema, rng, batch_size, fresh_counter, distribution
            )
            inc_t = time.perf_counter() - t0

            t1 = time.perf_counter()
            static = BCNFRepairChecker(schema)
            static.index_keys = list(state.index_keys)
            sres = static.check(list(state.r), list(state.r_prime))
            static_t = time.perf_counter() - t1

            inc_repair = state.is_repair()
            if not state.candidate_consistent():
                match = (not sres.is_repair) and (not sres.candidate_consistent) and (not inc_repair)
            else:
                match = (sres.is_repair == inc_repair) and sres.candidate_consistent
            if not match:
                all_match = False

            speedup = (static_t / inc_t) if inc_t > 0 else float("inf")
            rows.append(
                {
                    "batch_size": batch_size,
                    "batch_index": b,
                    "distribution": distribution,
                    "n": len(inst.r_prime),
                    "seed": seed,
                    "incremental_time": inc_t,
                    "static_rebuild_time": static_t,
                    "speedup": speedup,
                    "result_match": match,
                    "affected_block_rows": affected,
                    "inc_is_repair": inc_repair,
                    "static_is_repair": sres.is_repair,
                }
            )

        print(
            f"seed={seed} dist={distribution} batch_size={batch_size} "
            f"batches={n_batches} all_match={all_match}",
            flush=True,
        )
        if not all_match:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Incremental vs static differential benchmark")
    parser.add_argument("--n", type=int, default=1_000_000)
    parser.add_argument("--conflict-ratio", type=float, default=0.1)
    parser.add_argument("--updates", type=int, default=10000)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=list(INCREMENTAL_BATCH_SIZES))
    parser.add_argument("--seed", type=int, default=None, help="Single seed (legacy)")
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument(
        "--distribution",
        choices=["uniform", "zipf"],
        default=None,
        help="Single distribution (legacy)",
    )
    parser.add_argument(
        "--distributions",
        nargs="+",
        default=None,
        choices=["uniform", "zipf"],
        help="One or more key-block distributions",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Cap batches per (seed, dist, batch_size); useful at n=1e6",
    )
    parser.add_argument("--key-width", type=int, default=1)
    parser.add_argument("--fd-count", type=int, default=4)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "incremental.csv")
    args = parser.parse_args()

    seeds = args.seeds if args.seeds is not None else ([args.seed] if args.seed is not None else [42])
    distributions = (
        args.distributions
        if args.distributions is not None
        else ([args.distribution] if args.distribution is not None else ["uniform"])
    )

    set_global_seed(seeds[0])
    snapshot_config(
        RESULTS_DIR / "incremental_config.json",
        {
            **{k: v for k, v in vars(args).items()},
            "seeds": seeds,
            "distributions": distributions,
        },
    )

    fieldnames = [
        "batch_size",
        "batch_index",
        "distribution",
        "n",
        "seed",
        "incremental_time",
        "static_rebuild_time",
        "speedup",
        "result_match",
        "affected_block_rows",
        "inc_is_repair",
        "static_is_repair",
    ]
    rows: list[dict[str, Any]] = []

    for seed in seeds:
        schema = generate_single_key_bcnf(
            n_attrs=8, key_width=args.key_width, fd_count=args.fd_count, seed=seed
        )
        print(f"Generating n={args.n} seed={seed} ...", flush=True)
        clean = generate_clean_instance(schema, n=args.n, seed=seed)
        inst = make_positive_repair_case(
            schema, clean, conflict_ratio=args.conflict_ratio, seed=seed + 1
        )
        # free clean list reference (inst holds rows)
        del clean

        for dist in distributions:
            ok = run_one_config(
                schema,
                inst,
                batch_sizes=args.batch_sizes,
                updates=args.updates,
                max_batches=args.max_batches,
                seed=seed,
                distribution=dist,
                rows=rows,
            )
            if not ok:
                print("INCREMENTAL MISMATCH DETECTED", file=sys.stderr)
                write_csv(args.out, fieldnames, rows)
                return 1

    write_csv(args.out, fieldnames, rows)
    print(f"Wrote {args.out}; all result_match=True ({len(rows)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
