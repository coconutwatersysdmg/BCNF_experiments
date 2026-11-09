"""Hot-group tail latency and crossover, fixed 50k retained/10k excluded."""
import argparse
import gc
import json
import os
from pathlib import Path
import random
import sys
import time
import supplement as s
from algorithms.incremental import BCNFRepairState, PlainRepairState, UpdateOp

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    n,deleted_count=(100,20) if args.smoke else (50000,10000)
    groups=[1,10] if args.smoke else [1,100,10000]
    batches=[1,3] if args.smoke else [1,10,100]
    seeds=[101] if args.smoke else [101,202,303]
    count=2 if args.smoke else 30
    (ROOT/'data').mkdir(exist_ok=True)
    target=args.output or ROOT/'data'/('hot_smoke_raw.jsonl' if args.smoke else 'hot_raw.jsonl')
    if target.exists():
        raise FileExistsError(f'Existing results must be archived, not appended twice: {target}')
    schema=s.RelationSchema(('A','B','C','P'),(s.FD(('A',),('B','C','P')),),name='HotGroup')
    if not args.smoke:
        (ROOT/'data/hot_protocol.json').write_text(json.dumps(dict(
            retained=n,deleted=deleted_count,hot_group_sizes=groups,batch_sizes=batches,seeds=seeds,
            batches_per_cell=count,threads='Python single thread',warmup='one swap plus inverse',
            tracing=False,source='frozen BCNFRepairState, PlainRepairState, UpdateOp',
            timing='inc apply+decision; static apply+list conversion+rebuild+decision+index release',
            validation='full partition equality, repair+consistency agreement and exact 2*h*batch touched entries after every batch',
            percentiles='descriptive p95/p99 over 90 measured batches per configuration; not independent-trial confidence bounds'
        ),indent=2),encoding='utf-8')
    lock=ROOT/'timing.lock'
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    try:
        with target.open('x',encoding='utf-8') as out:
            for seed in seeds:
                for h in groups:
                    for batch in batches:
                        rng=random.Random(seed)
                        retained=[(i,i+1,i+2,f'v{i}') for i in range(n)]
                        hot=[(0,-i-1,-i-2,f'hot{i}') for i in range(h)]
                        parents=rng.sample(range(1,n),deleted_count-h)
                        cold=[(p,-j-100000,-j-100001,f'cold{j}') for j,p in enumerate(parents)]
                        original=retained+hot+cold
                        t0=time.perf_counter()
                        inc=BCNFRepairState(schema,original,retained)
                        init=time.perf_counter()-t0
                        plain=PlainRepairState(original,retained)
                        a,b=retained[0],hot[0]
                        for op in [UpdateOp('swap',a,b),UpdateOp('swap',b,a)]:
                            inc.apply(op);plain.apply(op)
                        assert inc.is_repair() and inc.candidate_consistent()
                        for rep in range(count):
                            ops=[]
                            for _ in range(batch):
                                ops.append(UpdateOp('swap',a,b));a,b=b,a
                            checker=s.BCNFRepairChecker(schema)
                            inc.reset_work_counters()
                            gc.collect()
                            start=time.perf_counter()
                            inc.apply_batch(ops)
                            decision=inc.is_repair()
                            inc_time=time.perf_counter()-start
                            gc.collect()
                            start=time.perf_counter()
                            plain.apply_batch(ops)
                            result=checker.check(list(plain.r),list(plain.r_prime))
                            del checker
                            static_time=time.perf_counter()-start
                            assert decision==result.is_repair
                            assert inc.candidate_consistent()==result.candidate_consistent
                            assert inc.r==plain.r and inc.r_prime==plain.r_prime and inc.D==plain.D
                            assert inc.touched_block_entries==2*h*batch
                            row=dict(seed=seed,hot_group_size=h,batch_size=batch,rep=rep,
                                     retained=n,excluded=deleted_count,inc_sec=inc_time,
                                     static_sec=static_time,speedup=static_time/inc_time,
                                     touched=inc.touched_block_entries,init_sec=init,
                                     is_repair=decision,candidate_consistent=inc.candidate_consistent(),
                                     partitions_equal=True,decisions_equal=True)
                            out.write(json.dumps(row)+'\n');out.flush()
                        print(f'HOT seed={seed} h={h} batch={batch} batches={count} passed',flush=True)
                        del inc,plain,original,retained,hot,cold,result
                        gc.collect()
    finally:
        lock.unlink(missing_ok=True)


if __name__=='__main__':
    main()
