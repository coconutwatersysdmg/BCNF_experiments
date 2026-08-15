"""Static scalability benchmark: Singleton-FullScan / FD-Hash / BCNF-Index."""

from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import is_subset_repair_bcnf_index
from algorithms.fd_hash import is_subset_repair_fd_hash
from algorithms.singleton_fullscan import is_subset_repair_singleton_fullscan
from common.io_utils import write_csv
from common.metrics import measure_resources, summarize_runs
from common.reproducibility import set_global_seed, snapshot_config
from config import DEFAULT_TIMEOUT_SEC, RESULTS_DIR
from generators.conflict_injector import make_negative_repair_case, make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


ALGORITHMS: dict[str, Callable[..., Any]] = {
    "Singleton-FullScan": is_subset_repair_singleton_fullscan,
    "FD-Hash": is_subset_repair_fd_hash,
    "BCNF-Index": is_subset_repair_bcnf_index,
}


def _worker_from_spec(spec: dict[str, Any], q: "mp.Queue[Any]") -> None:
    """Rebuild instance inside the child (avoid pickling million-row payloads)."""
    try:
        schema = generate_single_key_bcnf(
            n_attrs=int(spec["n_attrs"]),
            key_width=int(spec["key_width"]),
            fd_count=int(spec["fd_count"]),
            seed=int(spec["seed"]),
        )
        clean = generate_clean_instance(
            schema, n=int(spec["n"]), seed=int(spec["seed"]), skew=str(spec["skew"])
        )
        if spec["case_type"] == "pass":
            inst = make_positive_repair_case(
                schema, clean, conflict_ratio=float(spec["conflict_ratio"]), seed=int(spec["seed"]) + 11
            )
        else:
            inst = make_negative_repair_case(
                schema,
                clean,
                conflict_ratio=float(spec["conflict_ratio"]),
                seed=int(spec["seed"]) + 11,
                addable_position=0.9,
            )
        fn = ALGORITHMS[str(spec["algo"])]
        with measure_resources(track_memory=True) as mem:
            result = fn(schema, inst.r, inst.r_prime)
        q.put(
            (
                "ok",
                {
                    "is_repair": result.is_repair,
                    "candidate_consistent": result.candidate_consistent,
                    "build_time_sec": result.build_time_sec,
                    "check_time_sec": result.check_time_sec,
                    "total_time_sec": result.total_time_sec,
                    "index_count": result.index_count,
                    "python_peak_mb": mem["python_peak_mb"],
                    "rss_peak_mb": mem["rss_peak_mb"],
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        q.put(("err", repr(exc)))


def run_with_hard_timeout(spec: dict[str, Any], timeout_sec: float):
    """Hard-kill runaway baselines (esp. Singleton-FullScan) without pickling r."""
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker_from_spec, args=(spec, q))
    proc.start()
    proc.join(timeout_sec)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return None, True
    if q.empty():
        return None, True
    status, payload = q.get()
    if status != "ok":
        raise RuntimeError(payload)
    return payload, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Static S-repair scalability benchmark")
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 100000, 1000000])
    parser.add_argument("--conflict-ratio", type=float, default=0.1)
    parser.add_argument("--fd-count", type=int, default=4)
    parser.add_argument("--key-width", type=int, default=1)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--case", choices=["pass", "fail", "both"], default="both")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument(
        "--hard-timeout",
        action="store_true",
        help="Hard-kill Singleton-FullScan via subprocess regenerating from seed "
        "(does not pickle large instances). Other algos stay in-process.",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=list(ALGORITHMS.keys()),
        choices=list(ALGORITHMS.keys()),
    )
    parser.add_argument("--n-attrs", type=int, default=8)
    parser.add_argument("--skew", type=str, default="uniform")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "static.csv")
    args = parser.parse_args()

    set_global_seed(args.seeds[0])
    snapshot_config(RESULTS_DIR / "static_config.json", vars(args))

    case_types = ["pass", "fail"] if args.case == "both" else [args.case]
    raw_rows: list[dict[str, Any]] = []
    fieldnames = [
        "algorithm",
        "case_type",
        "n",
        "seed",
        "rep",
        "conflict_ratio",
        "fd_count",
        "candidate_key_width",
        "deleted_count",
        "index_count",
        "build_time_sec",
        "check_time_sec",
        "total_time_sec",
        "python_peak_mb",
        "rss_peak_mb",
        "peak_memory_mb",
        "result",
        "timeout",
    ]
    # Once Singleton times out at size n, skip it for all larger sizes.
    singleton_skip_from_n: Optional[int] = None

    for n in args.sizes:
        for seed in args.seeds:
            schema = generate_single_key_bcnf(
                n_attrs=args.n_attrs,
                key_width=args.key_width,
                fd_count=args.fd_count,
                seed=seed,
            )
            print(f"Generating n={n} seed={seed} ...", flush=True)
            clean = generate_clean_instance(schema, n=n, seed=seed, skew=args.skew)
            for case_type in case_types:
                if case_type == "pass":
                    inst = make_positive_repair_case(
                        schema, clean, conflict_ratio=args.conflict_ratio, seed=seed + 11
                    )
                else:
                    inst = make_negative_repair_case(
                        schema,
                        clean,
                        conflict_ratio=args.conflict_ratio,
                        seed=seed + 11,
                        addable_position=0.9,
                    )
                deleted_count = len(inst.deleted_rows)

                for algo in args.algorithms:
                    if (
                        algo == "Singleton-FullScan"
                        and singleton_skip_from_n is not None
                        and n >= singleton_skip_from_n
                    ):
                        raw_rows.append(
                            {
                                "algorithm": algo,
                                "case_type": case_type,
                                "n": n,
                                "seed": seed,
                                "rep": 0,
                                "conflict_ratio": args.conflict_ratio,
                                "fd_count": args.fd_count,
                                "candidate_key_width": args.key_width,
                                "deleted_count": deleted_count,
                                "index_count": "",
                                "build_time_sec": "",
                                "check_time_sec": "",
                                "total_time_sec": "",
                                "python_peak_mb": "",
                                "rss_peak_mb": "",
                                "peak_memory_mb": "",
                                "result": "",
                                "timeout": True,
                            }
                        )
                        print(
                            f"n={n} seed={seed} {case_type} {algo}: SKIP(timeout@>={singleton_skip_from_n})",
                            flush=True,
                        )
                        continue

                    use_hard = args.hard_timeout and algo == "Singleton-FullScan"

                    if not use_hard:
                        for _ in range(args.warmup):
                            try:
                                ALGORITHMS[algo](schema, inst.r, inst.r_prime)
                            except Exception:
                                break

                    times: list[float] = []
                    last_payload: Optional[dict[str, Any]] = None
                    timed_out = False

                    for rep in range(args.repeats):
                        if use_hard:
                            spec = {
                                "algo": algo,
                                "n": n,
                                "seed": seed,
                                "n_attrs": args.n_attrs,
                                "key_width": args.key_width,
                                "fd_count": args.fd_count,
                                "skew": args.skew,
                                "conflict_ratio": args.conflict_ratio,
                                "case_type": case_type,
                            }
                            out, is_timeout = run_with_hard_timeout(spec, args.timeout)
                        else:
                            t0 = time.perf_counter()
                            with measure_resources(track_memory=True) as mem:
                                result = ALGORITHMS[algo](schema, inst.r, inst.r_prime)
                            elapsed = time.perf_counter() - t0
                            out = {
                                "is_repair": result.is_repair,
                                "candidate_consistent": result.candidate_consistent,
                                "build_time_sec": result.build_time_sec,
                                "check_time_sec": result.check_time_sec,
                                "total_time_sec": result.total_time_sec,
                                "index_count": result.index_count,
                                "python_peak_mb": mem["python_peak_mb"],
                                "rss_peak_mb": mem["rss_peak_mb"],
                            }
                            is_timeout = elapsed > args.timeout

                        if is_timeout:
                            timed_out = True
                            if algo == "Singleton-FullScan":
                                singleton_skip_from_n = n
                            raw_rows.append(
                                {
                                    "algorithm": algo,
                                    "case_type": case_type,
                                    "n": n,
                                    "seed": seed,
                                    "rep": rep,
                                    "conflict_ratio": args.conflict_ratio,
                                    "fd_count": args.fd_count,
                                    "candidate_key_width": args.key_width,
                                    "deleted_count": deleted_count,
                                    "index_count": "",
                                    "build_time_sec": "",
                                    "check_time_sec": "",
                                    "total_time_sec": "",
                                    "python_peak_mb": "",
                                    "rss_peak_mb": "",
                                    "peak_memory_mb": "",
                                    "result": "",
                                    "timeout": True,
                                }
                            )
                            break

                        assert out is not None
                        last_payload = out
                        times.append(float(out["total_time_sec"]))
                        raw_rows.append(
                            {
                                "algorithm": algo,
                                "case_type": case_type,
                                "n": n,
                                "seed": seed,
                                "rep": rep,
                                "conflict_ratio": args.conflict_ratio,
                                "fd_count": args.fd_count,
                                "candidate_key_width": args.key_width,
                                "deleted_count": deleted_count,
                                "index_count": out["index_count"],
                                "build_time_sec": out["build_time_sec"],
                                "check_time_sec": out["check_time_sec"],
                                "total_time_sec": out["total_time_sec"],
                                "python_peak_mb": out["python_peak_mb"],
                                "rss_peak_mb": (
                                    out["rss_peak_mb"] if out["rss_peak_mb"] is not None else ""
                                ),
                                "peak_memory_mb": out["python_peak_mb"],
                                "result": out["is_repair"],
                                "timeout": False,
                            }
                        )

                    if times and not timed_out:
                        summary = summarize_runs(times)
                        print(
                            f"n={n} seed={seed} {case_type} {algo}: "
                            f"median={summary['median']:.6f}s "
                            f"result={last_payload['is_repair'] if last_payload else None}",
                            flush=True,
                        )
                    elif timed_out:
                        print(
                            f"n={n} seed={seed} {case_type} {algo}: TIMEOUT",
                            flush=True,
                        )

                # Checkpoint after each (n, seed, case)
                write_csv(args.out, fieldnames, raw_rows)

    write_csv(args.out, fieldnames, raw_rows)
    print(f"Wrote {args.out} ({len(raw_rows)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
