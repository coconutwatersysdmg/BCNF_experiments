"""Sequential, checkpointed wall-time and separate-allocation experiments."""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
import psutil
import supplement as s

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data'
METHODS = ['FD-Hash', 'FD-Hash-Cover', 'BCNF-Index']


def append(row):
    row['utc'] = datetime.now(timezone.utc).isoformat()
    DATA.mkdir(exist_ok=True)
    with (DATA / 'static_raw.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def environment():
    try:
        code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=s.EXPERIMENTS, text=True).strip()
        tag = subprocess.check_output(['git', 'rev-parse', 'paper-v1^{commit}'], cwd=s.EXPERIMENTS, text=True).strip()
        dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=s.EXPERIMENTS, text=True).strip()
    except Exception:
        code, tag, dirty = None, None, None
    if code and (code != tag or dirty):
        print('[warn] checkout is not a clean paper-v1 tree; provenance will record the actual HEAD',
              file=sys.stderr)
    sources = {}
    for folder in ['algorithms', 'common', 'generators']:
        for p in (s.EXPERIMENTS / folder).glob('*.py'):
            sources[str(p.relative_to(s.EXPERIMENTS))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(commit=code, tag=tag, python=sys.version, executable=sys.executable,
                platform=platform.platform(), processor=platform.processor(),
                physical_bytes=psutil.virtual_memory().total,
                available_bytes=psutil.virtual_memory().available,
                cpu_count=psutil.cpu_count(), sources=sources,
                new_sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in ROOT.glob('*.py')},
                seeds_legacy=[1, 2, 3], seeds_key_control=[101, 202, 303],
                warmup=1, repetitions=3, hashseed=os.environ.get('PYTHONHASHSEED'),
                timing='public check + index release wall time; schema preprocessing excluded; no tracemalloc; protocol v2',
                allocation='separate seed-1 or seed-101 run, one observation; Python allocation only',
                reserve_bytes=512 * 1024**2)


def prepare(kind, q, n, seed):
    if kind == 'legacy':
        from generators.schema_generator import generate_single_key_bcnf
        from generators.instance_generator import generate_clean_instance
        from generators.conflict_injector import make_positive_repair_case
        schema = generate_single_key_bcnf(n_attrs=8, key_width=1, fd_count=4, seed=seed)
        clean = generate_clean_instance(schema, n=n, seed=seed, skew='uniform')
        inst = make_positive_repair_case(schema, clean, conflict_ratio=.1,
                                        seed=seed+11, block_distribution='uniform')
        return schema, inst.r, inst.r_prime
    schema = s.make_schema(q, 16)
    r, rp = s.synthetic_rows(schema, n, seed)
    return schema, r, rp


def measure(method, schema, cover, r, rp, phase):
    # No retained index from a previous check survives into this check.
    checker = s.BCNFRepairChecker(schema) if method == 'BCNF-Index' else None
    gc.collect()
    if tracemalloc.is_tracing():
        raise RuntimeError('Unexpected tracing during ordinary timing')
    if phase == 'allocation':
        tracemalloc.start()
    before = psutil.Process().memory_info().rss
    start = time.perf_counter()
    if checker:
        result = checker.check(r, rp)
        # FD-Hash releases its local indexes before returning. Include the
        # equivalent release for the object-oriented BCNF implementation.
        del checker
        checker = None
    else:
        result = s.is_subset_repair_fd_hash(cover if method == 'FD-Hash-Cover' else schema, r, rp)
    wall = time.perf_counter() - start
    peak = None
    if phase == 'allocation':
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    assert result.is_repair and result.candidate_consistent, result.to_dict()
    row = dict(method=method, phase=phase, status='ok',
               wall_sec=wall if phase == 'timing' else None,
               instrumented_wall_sec=wall if phase == 'allocation' else None,
               python_peak_bytes=peak, process_rss_before=before,
               total_internal_sec=result.total_time_sec,
               validation_sec=result.metadata.get('validation_time_sec'),
               build_sec=result.build_time_sec, check_sec=result.check_time_sec,
               index_count=result.index_count, is_repair=result.is_repair,
               candidate_consistent=result.candidate_consistent)
    del checker, result
    gc.collect()
    return row


def worker(args):
    seeds = [1, 2, 3] if args.kind == 'legacy' else [101, 202, 303]
    for seed in seeds:
        available = psutil.virtual_memory().available
        # Conservative input estimate, followed by per-method admission checks.
        input_estimate = args.n * (450 if args.kind == 'legacy' else 720)
        reserve = 512 * 1024**2
        if available < input_estimate + reserve:
            append(dict(kind=args.kind, q=args.q, n=args.n, seed=seed, status='skipped_input_memory',
                        available_bytes=available, estimate_bytes=input_estimate))
            continue
        t0 = time.perf_counter()
        schema, r, rp = prepare(args.kind, args.q, args.n, seed)
        generation = time.perf_counter() - t0
        t0 = time.perf_counter()
        cover = s.equivalent_cover(schema)
        cover_sec = time.perf_counter() - t0
        t0 = time.perf_counter()
        keys = s.BCNFRepairChecker(schema).index_keys
        key_sec = time.perf_counter() - t0
        common = dict(kind=args.kind, q=len(keys), n=args.n, seed=seed, retained=len(rp),
                      original=len(r), raw_fd_count=len(schema.fds), cover_fd_count=len(cover.fds),
                      schema=schema.to_json(), generation_sec=generation,
                      cover_preprocess_sec=cover_sec, key_preprocess_sec=key_sec)
        append(dict(common, phase='configuration', status='ok'))
        active = []
        for method in METHODS:
            gc.collect()
            available = psutil.virtual_memory().available
            count = len(keys) if method == 'BCNF-Index' else len(cover.fds if method == 'FD-Hash-Cover' else schema.fds)
            index_bytes = (155 if method == 'BCNF-Index' else 250) * count * args.n
            estimate = index_bytes + 125 * args.n
            if available < estimate + reserve:
                append(dict(common, phase='timing', method=method, status='skipped_method_memory',
                            available_bytes=available, estimate_bytes=estimate))
                continue
            # One untimed warmup for every admitted method and generated instance.
            measure(method, schema, cover, r, rp, 'timing')
            active.append(method)
        rng = random.Random(seed + args.n + args.q)
        for rep in range(3):
            order = active.copy()
            rng.shuffle(order)
            for order_index, method in enumerate(order):
                row = measure(method, schema, cover, r, rp, 'timing')
                append(dict(common, **row, rep=rep, order=order_index,
                            available_after_bytes=psutil.virtual_memory().available))
                print(f'{args.kind} n={args.n} q={len(keys)} seed={seed} rep={rep} '
                      f'{method}: {row["wall_sec"]:.4f}s', flush=True)
        # Separate memory collection at the original small/control scale only.
        if seed == seeds[0] and args.n in [50000, 100000]:
            for method in active:
                gc.collect()
                count = len(keys) if method == 'BCNF-Index' else len(cover.fds if method == 'FD-Hash-Cover' else schema.fds)
                estimate = (500 * count + 150) * args.n
                if psutil.virtual_memory().available < estimate + reserve:
                    append(dict(common, method=method, phase='allocation', status='skipped_memory_tracing_budget'))
                    continue
                row = measure(method, schema, cover, r, rp, 'allocation')
                append(dict(common, **row, rep=0))
        del r, rp, schema, cover
        gc.collect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--kind', choices=['legacy', 'keys'])
    parser.add_argument('--q', type=int, default=1)
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    DATA.mkdir(exist_ok=True)
    lock = ROOT / 'timing.lock'
    with lock.open('x', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    try:
        env = dict(os.environ, PYTHONHASHSEED='0')
        manifest = environment()
        manifest['hashseed'] = '0 (child processes)'
        (DATA / 'static_protocol.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        jobs = [('legacy', 1, n) for n in [1000, 10000, 100000, 1000000]]
        jobs += [('keys', q, n) for n in [50000, 250000] for q in [1, 2, 4, 8]]
        jobs += [('keys', 1, 1000000), ('keys', 2, 1000000)]
        if args.smoke:
            jobs = [('legacy', 1, 1000)]
        (DATA / 'jobs.json').write_text(json.dumps(jobs, indent=2), encoding='utf-8')
        for index, (kind, q, n) in enumerate(jobs):
            print(f'JOB {index+1}/{len(jobs)} {kind} q={q} n={n}', flush=True)
            start = time.perf_counter()
            run = subprocess.run([sys.executable, '-u', __file__, '--worker', '--kind', kind,
                                  '--q', str(q), '--n', str(n)], env=env)
            append(dict(phase='job', kind=kind, q=q, n=n, exit_code=run.returncode,
                        elapsed_sec=time.perf_counter()-start,
                        status='completed' if run.returncode == 0 else 'error'))
            if run.returncode:
                raise RuntimeError(f'Worker failed: {kind}, q={q}, n={n}')
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
