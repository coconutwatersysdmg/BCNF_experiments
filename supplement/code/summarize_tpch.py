"""Aggregate benchmark-derived results, including the SQL loading boundary."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent.parent


def main():
    rows=[json.loads(x) for x in (ROOT/'data/tpch_raw.jsonl').read_text(encoding='utf-8').splitlines()]
    df=pd.DataFrame(rows)
    timed=df[(df.phase=='timing') & (df.status=='ok')].copy()
    for row in timed.itertuples():
        assert [row.is_repair,row.candidate_consistent]==row.expected
    assert not timed.duplicated(['table','sf','seed','case','method','rep']).any()
    stats=timed.groupby(['table','sf','case','method']).agg(
        retained=('retained','first'), excluded=('excluded','first'),
        median_sec=('wall_sec','median'), p25_sec=('wall_sec',lambda x:x.quantile(.25)),
        p75_sec=('wall_sec',lambda x:x.quantile(.75)),
        median_with_load_sec=('total_with_load_sec','median'), median_load_sec=('load_sec','median'),
        samples=('wall_sec','size'), seeds=('seed','nunique')).reset_index()
    stats.to_csv(ROOT/'data/tpch_summary.csv',index=False)
    errors=df[df.status.isin(['error','skipped_memory'])]
    errors.drop(columns=['schema'],errors='ignore').to_csv(ROOT/'data/tpch_errors.csv',index=False)
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
                         'mathtext.fontset':'stix','font.size':8,'axes.labelsize':8,
                         'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,
                         'pdf.fonttype':42,'axes.linewidth':.7})
    fig,axes=plt.subplots(1,2,figsize=(7.15,2.65))
    for ax in axes:
        ax.tick_params(direction='in',top=True,right=True,length=3,width=.65)
        ax.set_axisbelow(True)
        ax.grid(axis='y',color='#DFE3E7',linewidth=.45)
    cats=[('customer',.01),('customer',.1),('lineitem',.01),('lineitem',.1)]
    styles=[('FD-Hash-Cover','FD cover','#66737F',''),
            ('BCNF-Index','BCNF index','#1F5B87',''),
            ('DuckDB-SQL','SQL resident','#B67B49',''),
            ('DuckDB-SQL','SQL + load','#D4B392','//')]
    for j,(method,label,color,hatch) in enumerate(styles):
        values=[]
        for table,sf in cats:
            part=stats[(stats.table==table)&(stats.sf==sf)&(stats.case=='repair')&(stats.method==method)]
            field='median_with_load_sec' if label=='SQL + load' else 'median_sec'
            values.append(float(part[field].iloc[0])*1000 if len(part) else np.nan)
        axes[0].bar(np.arange(4)+(j-1.5)*.19,values,.18,label=label,color=color,hatch=hatch,
                     edgecolor='black',linewidth=.45)
    axes[0].set(yscale='log',ylabel='Elapsed time (ms)',xticks=np.arange(4),
                xticklabels=['Customer\nSF 0.01','Customer\nSF 0.1','Lineitem\nSF 0.01','Lineitem\nSF 0.1'])
    axes[0].set_title('(a) Valid repair candidates',fontsize=8,pad=7)
    axes[0].legend(frameon=False,ncol=2,loc='upper left',fontsize=6.8,handlelength=1.2)
    axes[0].margins(y=.3)
    for method,label,color,marker in [('FD-Hash-Cover','FD cover','#66737F','^'),
                                      ('BCNF-Index','BCNF index','#1F5B87','o'),
                                      ('DuckDB-SQL','SQL resident','#B67B49','s')]:
        sub=stats[(stats.table=='lineitem')&(stats.sf==.1)&(stats.method==method)]
        values=[]; lows=[]; highs=[]
        for fraction in [0.,.5,1.]:
            cell=sub[sub.case==f'nonmax_{fraction:.1f}']
            values.append(cell.median_sec.iloc[0]*1000 if len(cell) else np.nan)
            lows.append(cell.p25_sec.iloc[0]*1000 if len(cell) else np.nan)
            highs.append(cell.p75_sec.iloc[0]*1000 if len(cell) else np.nan)
        axes[1].errorbar([0,50,100],values,
                         yerr=np.vstack([np.array(values)-lows,np.array(highs)-values]),
                         label=label,color=color,marker=marker,markerfacecolor='white',
                         markersize=4,linewidth=1,elinewidth=.65,capsize=2)
    axes[1].set(xlabel='Add-back witness position in excluded tuples (%)',
                ylabel='Elapsed time (ms)',xticks=[0,50,100],ylim=(0,None))
    axes[1].set_title('(b) Non-maximal candidates, Lineitem SF 0.1',fontsize=8,pad=7)
    axes[1].legend(frameon=False,loc='best',handlelength=1.5)
    fig.tight_layout(pad=.7,w_pad=1.2)
    (ROOT/'fig').mkdir(exist_ok=True)
    for ext,opts in [('pdf',{}),('png',{'dpi':400})]:
        fig.savefig(ROOT/'fig'/f'benchmark_candidates.{ext}',bbox_inches='tight',pad_inches=.07,**opts)
    plt.close(fig)
    lines=['# Benchmark-derived candidate study','',
           'Source: DuckDB 2.0.0 tpch extension, scale factors 0.01 and 0.1. These are controlled projections with injected conflicts; this is not a TPC-H throughput benchmark or a natural dirty-data study.',
           '[Generator documentation](https://duckdb.org/docs/2.0/core_extensions/tpch). The extension documents small differences from the official TPC-H specification.','',
           '- CUSTOMER projection: six mixed-type attributes, declared key c_custkey.',
           '- LINEITEM projection: six mixed-type attributes, declared key (l_orderkey,l_linenumber).',
           '- Only the declared key FDs are checked. Cross-relation foreign-key constraints and unspecified accidental FDs are not checked.',
           '- 10% of clean tuples receive a distinct comment variant, preserving the key and changing a dependent value.',
           '- Valid candidates retain the clean rows; non-maximal candidates omit one entire untouched key group, with the sole add-back witness placed at 0%, 50%, or 100% of the excluded order.',
           '- Inconsistent candidates additionally retain one conflicting variant.',
           '- Three seeds × three repeats, one warmup per method/seed/candidate, randomized method order, no tracemalloc.',
           '- SQL uses one thread, a 256 MiB engine memory limit, subset anti-join, per-FD GROUP BY consistency tests, and correlated NOT EXISTS singleton tests.',
           '- Resident SQL timings exclude tuple import. SQL + load adds measured Arrow conversion/table creation. Loading occurs once per seed/candidate; the three query repetitions reuse that measured load, so they are not independent end-to-end loading repetitions.',
           '- Python cold checker timings include subset validation, index build, scan, and index release, operating on shared Python tuples. No candidate-key specialization is used in the SQL baseline.','',
           f'Timing observations: {len(timed)}. Decision disagreements: 0 among completed observations. Explicit load/query errors or memory skips: {len(errors)}.','',
           '|Table|SF|Candidate|Method|Retained|Median query/check (ms)|Median + load (ms)|Samples|',
           '|---|---:|---|---|---:|---:|---:|---:|']
    for row in stats.itertuples():
        lines.append(f'|{row.table}|{row.sf}|{row.case}|{row.method}|{row.retained:,}|{row.median_sec*1000:.3f}|{row.median_with_load_sec*1000:.3f}|{row.samples}|')
    lines += ['', '## Reproduction','', '```powershell',
              'python -u run_tpch_supplement.py','python summarize_tpch.py','```','',
              'See the protocol JSON for source commit, exact SQL projections, versions, and environmental information. See raw JSONL for every timing and declared expected decision.']
    (ROOT/'reports'/'TPCH_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(stats.to_string(index=False))
    print(f'Completed observations {len(timed)}; errors/skips {len(errors)}')


if __name__=='__main__':
    main()
