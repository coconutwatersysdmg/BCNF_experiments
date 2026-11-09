"""Sequential benchmark-derived single/composite-key and invalid-candidate study."""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import psutil
import supplement as s
from run_static_supplement import measure, environment

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
QUERIES = {
    'customer': ('SELECT c_custkey, c_nationkey, c_name, c_acctbal::DOUBLE AS c_acctbal, '
                 'c_mktsegment, c_comment FROM customer ORDER BY c_custkey', ('c_custkey',)),
    'lineitem': ('SELECT l_orderkey, l_linenumber, l_partkey, l_quantity::DOUBLE AS l_quantity, '
                 'l_extendedprice::DOUBLE AS l_extendedprice, l_comment '
                 'FROM lineitem ORDER BY l_orderkey,l_linenumber', ('l_orderkey','l_linenumber')),
}


def emit(row):
    row['utc'] = datetime.now(timezone.utc).isoformat()
    with (DATA / 'tpch_raw.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def generate(sf):
    import duckdb
    path = DATA / f'tpch_sf{sf}.duckdb'
    with duckdb.connect(str(path)) as conn:
        conn.execute('SET threads=1')
        conn.execute("SET memory_limit='384MB'")
        extension = ROOT / '.duckdb_extensions'
        extension.mkdir(exist_ok=True)
        conn.execute("SET extension_directory='" + str(extension).replace("'", "''") + "'")
        conn.execute('INSTALL tpch')
        conn.execute('LOAD tpch')
        exists = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='lineitem'").fetchone()[0]
        if not exists:
            start = time.perf_counter()
            conn.execute(f'CALL dbgen(sf={sf})')
            emit(dict(phase='generation', sf=sf, generation_sec=time.perf_counter()-start, status='ok'))
        counts = {table:conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in QUERIES}
    emit(dict(phase='dataset', sf=sf, table_counts=counts, status='ok',
              duckdb_version=duckdb.__version__, file_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))


def run_python(method, schema, cover, r, rp):
    checker = s.BCNFRepairChecker(schema) if method == 'BCNF-Index' else None
    gc.collect()
    start = time.perf_counter()
    result = checker.check(r, rp) if checker else s.is_subset_repair_fd_hash(cover, r, rp)
    # Both implementation styles release their temporary indexes inside timer.
    del checker
    wall = time.perf_counter()-start
    return dict(wall_sec=wall, load_sec=0., total_with_load_sec=wall,
                is_repair=result.is_repair, candidate_consistent=result.candidate_consistent,
                validation_sec=result.metadata.get('validation_time_sec'),
                build_sec=result.build_time_sec, check_sec=result.check_time_sec)


def worker(args):
    import duckdb
    from common.fd_utils import satisfies_fds
    with duckdb.connect(str(DATA / f'tpch_sf{args.sf}.duckdb'), read_only=True) as conn:
        query, key = QUERIES[args.table]
        result = conn.execute(query)
        attrs = tuple(col[0] for col in result.description)
        clean = result.fetchall()
    schema = s.RelationSchema(attrs, (s.FD(key, tuple(a for a in attrs if a not in key)),),
                              name=f'TPCH-{args.table}-projection')
    schema.validate_bcnf()
    assert satisfies_fds(clean, schema.fds, schema.attr_to_idx)
    cover = s.equivalent_cover(schema)
    for seed in [101,202,303]:
        for case, r, rp, expected, position in s.benchmark_cases(schema, clean, seed):
            common = dict(table=args.table, sf=args.sf, seed=seed, case=case,
                          clean_rows=len(clean), retained=len(rp), original=len(r),
                          excluded=len(r)-len(rp), witness_position=position,
                          expected=list(expected), schema=schema.to_json())
            methods = ['BCNF-Index', 'FD-Hash-Cover', 'DuckDB-SQL']
            sql = None
            # The Python input is shared; SQL tuple import is explicitly measured.
            if psutil.virtual_memory().available > 512*1024**2 + len(r)*300:
                try:
                    sql = s.SQLChecker(cover, r, rp)
                except Exception as exc:
                    emit(dict(common, method='DuckDB-SQL', phase='load', status='error', error=repr(exc)))
            else:
                emit(dict(common, method='DuckDB-SQL', phase='load', status='skipped_memory'))
            if sql is None:
                methods.remove('DuckDB-SQL')
            def call(method):
                if method != 'DuckDB-SQL':
                    return run_python(method, schema, cover, r, rp)
                gc.collect()
                start = time.perf_counter()
                decision = sql.check()
                wall = time.perf_counter()-start
                return dict(wall_sec=wall, load_sec=sql.load_sec,
                            total_with_load_sec=wall+sql.load_sec,
                            is_repair=decision[0], candidate_consistent=decision[1], **sql.last_parts)
            for method in methods.copy():
                try:
                    out = call(method)
                    assert (out['is_repair'],out['candidate_consistent']) == expected
                except AssertionError:
                    raise
                except Exception as exc:
                    if method != 'DuckDB-SQL':
                        raise
                    emit(dict(common, method=method, phase='warmup', status='error', error=repr(exc)))
                    methods.remove(method)
            rng = random.Random(seed + len(clean) + len(rp))
            for rep in range(3):
                order = methods.copy()
                rng.shuffle(order)
                for index, method in enumerate(order):
                    out = call(method)
                    assert (out['is_repair'],out['candidate_consistent']) == expected
                    emit(dict(common, **out, method=method, rep=rep, order=index,
                              phase='timing', status='ok'))
                print(f'TPCH sf={args.sf} {args.table} {case} seed={seed} rep={rep}', flush=True)
            if sql:
                sql.close()
            del sql, r, rp
            gc.collect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--sf', type=float, default=.01)
    parser.add_argument('--table', choices=list(QUERIES))
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    DATA.mkdir(exist_ok=True)
    with (ROOT / 'timing.lock').open('x', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    try:
        import duckdb
        protocol = environment()
        protocol.update(duckdb_version=duckdb.__version__, sql_threads=1, sql_memory_limit='256MB',
                        data_source='DuckDB tpch extension; benchmark-derived, injected conflicts, not natural dirty data',
                        scales=[.01,.1], projections={k:{'query':v[0],'key':v[1]} for k,v in QUERIES.items()},
                        comparison='Python cold checker vs SQL resident query; SQL load+query also reported',
                        sql_load_repetitions='one load per seed/candidate; added to each resident query observation, not three independent loads',
                        python_null_semantics='No NULLs in selected/generated values',
                        source_url='https://duckdb.org/docs/2.0/core_extensions/tpch')
        (DATA/'tpch_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
        for sf in [.01,.1]:
            generate(sf)
            for table in QUERIES:
                start = time.perf_counter()
                run = subprocess.run([sys.executable,'-u',__file__,'--worker','--sf',str(sf),'--table',table],
                                     env=dict(os.environ,PYTHONHASHSEED='0'))
                emit(dict(phase='job',sf=sf,table=table,exit_code=run.returncode,
                          elapsed_sec=time.perf_counter()-start,
                          status='completed' if run.returncode==0 else 'error'))
                if run.returncode:
                    raise RuntimeError(f'TPC-H worker failed: {sf} {table}')
    finally:
        (ROOT/'timing.lock').unlink(missing_ok=True)


if __name__=='__main__':
    main()
