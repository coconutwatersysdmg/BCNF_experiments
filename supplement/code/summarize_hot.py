from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent

def main():
    df=pd.DataFrame([json.loads(x) for x in (ROOT/'data/hot_raw.jsonl').read_text().splitlines()])
    assert df.decisions_equal.all() and df.partitions_equal.all()
    assert not df.duplicated(['seed','hot_group_size','batch_size','rep']).any()
    stats=df.groupby(['hot_group_size','batch_size']).agg(
        inc_ms=('inc_sec',lambda x:x.median()*1000),static_ms=('static_sec',lambda x:x.median()*1000),
        inc_p95_ms=('inc_sec',lambda x:x.quantile(.95)*1000),
        inc_p99_ms=('inc_sec',lambda x:x.quantile(.99)*1000),
        median_paired_speedup=('speedup','median'),samples=('inc_sec','size'),
        init_ms=('init_sec',lambda x:x.median()*1000),touched=('touched','first')).reset_index()
    stats.to_csv(ROOT/'data/hot_summary.csv',index=False)
    lines=['# Hot-group incremental experiment','',
           'Fixed 50,000 retained and 10,000 excluded tuples. One declared candidate key; varying the size of the repeatedly updated conflict group. Three seeds and 30 successive batches per cell. Full partition equality and exact work counters are checked after every batch, outside timers. No model calls or tracemalloc.','',
           'All percentiles are descriptive. Sequential batches within a seed are dependent; 90 observations are not 90 independent generated databases. Static rebuild includes applying the same updates, list conversion, validation, index construction, checking, and index release. Initialization is outside batch times and reported separately.','',
           '|Hot group|Swaps/batch|Incremental median (ms)|Rebuild median (ms)|Incremental p95 (ms)|p99 (ms)|Paired speedup|Samples|',
           '|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in stats.itertuples():
        lines.append(f'|{r.hot_group_size}|{r.batch_size}|{r.inc_ms:.4f}|{r.static_ms:.4f}|{r.inc_p95_ms:.4f}|{r.inc_p99_ms:.4f}|{r.median_paired_speedup:.3f}x|{r.samples}|')
    lines+=['',f'Total measured batches: {len(df)}; decision/partition disagreements: 0.',
            'A paired speedup below one means rebuilding was faster in that configuration. Do not omit such crossover observations.']
    (ROOT/'reports'/'HOT_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(stats.to_string(index=False))

if __name__=='__main__':
    main()
