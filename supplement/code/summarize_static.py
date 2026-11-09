"""Generate every reported value/figure from protocol-v2 raw records."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent


def main():
    raw = ROOT / 'data/static_raw.jsonl'
    rows = [json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines()]
    df = pd.DataFrame(rows)
    timed = df[(df.phase == 'timing') & (df.status == 'ok')].copy()
    assert timed.instrumented_wall_sec.isna().all()
    assert timed.python_peak_bytes.isna().all()
    assert timed.is_repair.all() and timed.candidate_consistent.all()
    group = ['kind', 'n', 'q', 'method']
    summary = timed.groupby(group).agg(
        median_sec=('wall_sec', 'median'), p25_sec=('wall_sec', lambda x: x.quantile(.25)),
        p75_sec=('wall_sec', lambda x: x.quantile(.75)), samples=('wall_sec', 'size'),
        seeds=('seed', 'nunique'), median_build_sec=('build_sec', 'median'),
        median_check_sec=('check_sec', 'median'),
        median_validation_sec=('validation_sec', 'median'),
        median_internal_sec=('total_internal_sec', 'median')).reset_index()
    summary.to_csv(ROOT / 'data/static_summary.csv', index=False)
    paired = timed.pivot(index=['kind', 'n', 'q', 'seed', 'rep'], columns='method', values='wall_sec')
    ratios = []
    for method in ['FD-Hash', 'FD-Hash-Cover']:
        good = paired[[method, 'BCNF-Index']].dropna().reset_index()
        good['speedup'] = good[method] / good['BCNF-Index']
        for keys, part in good.groupby(['kind', 'n', 'q']):
            ratios.append(dict(zip(['kind', 'n', 'q'], keys), baseline=method,
                               median_paired_speedup=part.speedup.median(),
                               p25=part.speedup.quantile(.25), p75=part.speedup.quantile(.75),
                               paired_samples=len(part), seeds=part.seed.nunique()))
    ratio = pd.DataFrame(ratios)
    ratio.to_csv(ROOT / 'data/static_paired_speedups.csv', index=False)
    memory = df[(df.phase == 'allocation') & (df.status == 'ok')].copy()
    memory[['kind', 'n', 'q', 'seed', 'method', 'python_peak_bytes', 'instrumented_wall_sec']].to_csv(
        ROOT / 'data/static_separate_allocation.csv', index=False)
    skips = df[df.status.astype(str).str.startswith('skipped')].copy()
    skips.drop(columns=['schema'], errors='ignore').to_csv(ROOT / 'data/static_skipped.csv', index=False)
    figs = ROOT / 'fig'
    figs.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'serif', 'font.serif':['Times New Roman','DejaVu Serif'],
                         'mathtext.fontset':'stix', 'font.size':8, 'axes.labelsize':8,
                         'xtick.labelsize':7, 'ytick.labelsize':7, 'legend.fontsize':7,
                         'pdf.fonttype':42, 'ps.fonttype':42, 'axes.linewidth':.7})
    colors = {'FD-Hash':'#9B5F31', 'FD-Hash-Cover':'#66737F', 'BCNF-Index':'#1F5B87'}
    markers = {'FD-Hash':'s', 'FD-Hash-Cover':'^', 'BCNF-Index':'o'}
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.65))
    for ax in axes:
        ax.tick_params(direction='in', top=True, right=True, width=.65, length=3)
        ax.grid(axis='y', color='#DFE3E7', linewidth=.45)
        ax.set_axisbelow(True)
    for method in ['FD-Hash', 'FD-Hash-Cover', 'BCNF-Index']:
        part = summary[(summary.kind == 'legacy') & (summary.method == method)].sort_values('n')
        axes[0].plot(part.n * 1.1, part.median_sec, color=colors[method], marker=markers[method],
                     markerfacecolor='white', markeredgewidth=.9, markersize=4, linewidth=1,
                     label=method)
    axes[0].set(xscale='log', yscale='log', xlabel=r'Total tuples $|r|$', ylabel='Elapsed time (s)')
    axes[0].set_title('(a) Original four-FD workload', fontsize=8, pad=7)
    axes[0].legend(frameon=False, loc='upper left', handlelength=1.5, borderaxespad=.5)
    for method in ['FD-Hash-Cover', 'BCNF-Index']:
        part = summary[(summary.kind == 'keys') & (summary.n == 250000) &
                       (summary.method == method)].sort_values('q')
        axes[1].errorbar(part.q, part.median_sec,
                         yerr=np.vstack([part.median_sec-part.p25_sec, part.p75_sec-part.median_sec]),
                         color=colors[method], marker=markers[method], markerfacecolor='white',
                         markeredgewidth=.9, markersize=4, linewidth=1, elinewidth=.65, capsize=2,
                         label=method)
    axes[1].set(xticks=[1,2,4,8], xlabel=r'Distinct keys $q$', ylabel='Elapsed time (s)', ylim=(0,None))
    axes[1].set_title(r'(b) 250,000 retained tuples, 16 FDs', fontsize=8, pad=7)
    axes[1].legend(frameon=False, loc='upper left', handlelength=1.5, borderaxespad=.5)
    part = memory[(memory.kind == 'legacy') & (memory.n == 100000)]
    names = ['FD-Hash', 'FD-Hash-Cover', 'BCNF-Index']
    vals = [part[part.method == m].python_peak_bytes.iloc[0] / 2**20 if len(part[part.method == m]) else np.nan for m in names]
    axes[2].bar(np.arange(3), vals, width=.60, color=[colors[m] for m in names], linewidth=.6, edgecolor='black')
    axes[2].set(xticks=np.arange(3), xticklabels=['Raw FD','FD cover','BCNF'],
                ylabel='Peak Python allocation (MiB)', xlabel='Separate allocation run')
    axes[2].set_title('(c) 100,000 retained tuples', fontsize=8, pad=7)
    axes[2].margins(y=.2)
    for i,y in enumerate(vals):
        if np.isfinite(y):
            axes[2].annotate(f'{y:.1f}', (i,y), xytext=(0,3), textcoords='offset points', ha='center', fontsize=7)
    fig.tight_layout(pad=.7, w_pad=1.1)
    for ext, opts in [('pdf',{}), ('png',{'dpi':400})]:
        fig.savefig(figs / f'fair_static.{ext}', bbox_inches='tight', pad_inches=.07, **opts)
    plt.close(fig)
    jobs = df[df.phase == 'job']
    protocol = json.loads((ROOT / 'data/static_protocol.json').read_text())
    lines = ['# Static supplemental experiment report', '',
             'Protocol: v2. All times below are actual measurements, with no imputed/skipped observations.', '',
             f'- Frozen commit: `{protocol["commit"]}`.',
             f'- Python: `{protocol["python"].splitlines()[0]}`.',
             f'- Completed jobs: {len(jobs[jobs.status == "completed"])}/{len(json.loads((ROOT / "data/jobs.json").read_text()))}.',
             f'- Ordinary timing observations: {len(timed)}; separate allocation observations: {len(memory)}.',
             f'- Explicit memory skips: {len(skips)}. See `data/static_skipped.csv`.',
             '- Each full timing cell has three seeds × three repeats, after one untimed warmup per seed/method.',
             '- Ordinary time includes subset validation, index build, deleted-tuple scan, and index release. Schema preprocessing and workload generation are outside the timer.',
             '- Build/check/validation times are internal diagnostics and exclude some cleanup; compare outer wall times for the headline results.',
             '- Allocation is measured separately with tracemalloc (one observation per selected configuration), covers only Python allocations, and is not total process RAM.',
             '- Randomized method order; PYTHONHASHSEED=0; sequential workers. No external model calls.',
             '- Pilot v1 files are retained for audit, but excluded from all summaries and figures.', '',
             '## Wall-time medians', '',
             '|Workload|Retained|Keys|Method|Median (s)|IQR (s)|Samples|Seeds|',
             '|---|---:|---:|---|---:|---|---:|---:|']
    for row in summary.itertuples():
        lines.append(f'|{row.kind}|{row.n:,}|{row.q}|{row.method}|{row.median_sec:.6f}|{row.p25_sec:.6f}–{row.p75_sec:.6f}|{row.samples}|{row.seeds}|')
    lines += ['', '## Paired speedups over BCNF-Index', '',
              '|Workload|Retained|Keys|Baseline|Median paired speedup|Pairs|Seeds|',
              '|---|---:|---:|---|---:|---:|---:|']
    for row in ratio.itertuples():
        lines.append(f'|{row.kind}|{row.n:,}|{row.q}|{row.baseline}|{row.median_paired_speedup:.3f}×|{row.paired_samples}|{row.seeds}|')
    lines += ['', '## Interpretation and limits', '',
              'The equivalent-cover baseline controls for redundant FD syntax; compare it separately from raw per-FD hashing. The key-count control fixes 16 attributes and 16 input FDs, and varies q independently. Both covers are checked for implication equivalence. Small-schema preprocessing is measured separately and is not claimed as a new key-discovery contribution.', '',
              'Results are from the existing Python prototype on this machine and controlled synthetic data. The original static curves included tracemalloc during timing; the new times should not be silently mixed with those times. Their experimental conditions and timing boundaries differ. Memory-guarded omissions are not timeouts and are not evidence of algorithmic failure. Extrapolation to a production database engine requires the planned SQL/benchmark-derived experiment.', '',
              '## Exact reproduction', '', '```powershell',
              'python -m unittest test_supplement -v',
              'python -u run_static_supplement.py', 'python summarize_static.py', '```', '',
              'Run in a fresh output directory or archive an existing run first: raw records are append-only and the analysis rejects duplicate measurement keys.', '',
              f'Raw SHA-256: `{hashlib.sha256(raw.read_bytes()).hexdigest()}`.', '']
    (ROOT / 'STATIC_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(summary.to_string(index=False))
    print('\nPAIRED\n' + ratio.to_string(index=False))
    print(f'Generated report, CSVs, and figures; {len(timed)} timing observations.')


if __name__ == '__main__':
    main()
