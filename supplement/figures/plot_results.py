"""Redraw audited result figures in the visual style of the supplied peer paper.

Run from any directory. Inputs are the unmodified CSVs in ../data; the hot-group
records are an exact copy of the previously measured JSONL. No experiments run.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter, MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
TEAL = '#477F91'
GOLD = '#DAB35B'
SALMON = '#C77C6A'
GRAY = '#56616D'
PALE = '#E9EDF0'
INK = '#282E33'
DIST = [('uniform', TEAL, 'o', '-', 'Uniform'),
        ('zipf_1.2', SALMON, 's', '--', 'Zipf-1.2')]
METHODS = [('FD-Hash', GRAY, 's', '--'),
           ('FD-Hash-Cover', GOLD, '^', '-.'),
           ('BCNF-Index', TEAL, 'o', '-')]
POINTS = []


def configure():
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
        'mathtext.fontset': 'stix', 'font.size': 8.5, 'axes.labelsize': 8.7,
        'xtick.labelsize': 8.0, 'ytick.labelsize': 8.0, 'legend.fontsize': 8.2,
        'axes.linewidth': .65, 'axes.edgecolor': '#7D858D',
        'text.color': INK, 'axes.labelcolor': INK,
        'xtick.color': INK, 'ytick.color': INK,
        'xtick.direction': 'out', 'ytick.direction': 'out',
        'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
        'xtick.minor.size': 1.2, 'ytick.minor.size': 1.2,
        'xtick.major.width': .55, 'ytick.major.width': .55,
        'xtick.minor.width': .4, 'ytick.minor.width': .4,
        'xtick.major.pad': 2.5, 'ytick.major.pad': 2.5,
        'axes.labelpad': 3, 'legend.frameon': False,
        'legend.handlelength': 1.8, 'legend.handletextpad': .45,
        'legend.columnspacing': 1.4, 'lines.linewidth': 1.25,
        'lines.markersize': 4.5, 'hatch.linewidth': .5,
        'pdf.fonttype': 42, 'ps.fonttype': 42,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'savefig.facecolor': 'white',
    })


def frame(ax, grid='y'):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(top=False, right=False)
    ax.set_axisbelow(True)
    ax.grid(axis=grid, which='major', color='#E2E5E8', linewidth=.5)


def log_axis(ax, which, *, limit=None):
    getattr(ax, f'set_{which}scale')('log')
    axis = getattr(ax, f'{which}axis')
    axis.set_major_locator(LogLocator(base=10, numticks=6))
    axis.set_minor_locator(LogLocator(base=10, subs=[2, 5], numticks=16))
    axis.set_minor_formatter(NullFormatter())
    if limit:
        getattr(ax, f'set_{which}lim')(*limit)


def record(figure, panel, series, x, y, lo=None, hi=None, interval=None):
    POINTS.append(dict(figure=figure, panel=panel, series=series,
                       x=np.asarray(x).tolist(), y=np.asarray(y).tolist(),
                       low=None if lo is None else np.asarray(lo).tolist(),
                       high=None if hi is None else np.asarray(hi).tolist(),
                       interval=interval))


def curve(ax, x, y, color, marker, ls='-', lo=None, hi=None):
    y=np.asarray(y, float)
    if lo is not None:
        ax.errorbar(x, y, yerr=np.maximum(0, np.vstack([y-lo, hi-y])),
                    fmt='none', ecolor=INK, elinewidth=.55,
                    capsize=1.8, capthick=.55, zorder=4)
    return ax.plot(x, y, color=color, marker=marker, ls=ls,
                   mfc=color if marker=='o' else 'white', mec=color,
                   mew=.85, ms=4.5, lw=1.25, zorder=5)[0]


def key(fig, handles, labels, ncol=None):
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.52, .995),
               ncol=ncol or len(labels), borderaxespad=0)


def panels(fig, axes, labels):
    for ax,label in zip(axes,labels):
        box=ax.get_position()
        fig.text((box.x0+box.x1)/2, .025, label, ha='center', va='bottom',
                 fontsize=9.0, color=INK)


def save(fig, number):
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    outside=[]
    for t in fig.findobj(match=matplotlib.text.Text):
        if t.get_visible() and t.get_text():
            bb=t.get_window_extent(renderer)
            # Tick locators can create invisible off-axis labels on log axes.
            if bb.width and bb.height and t.get_clip_on() is False:
                if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig.bbox.width+1 or bb.y1 > fig.bbox.height+1:
                    outside.append(t.get_text())
    if outside:
        raise ValueError(f'Figure {number}: labels outside canvas: {outside}')
    fig.savefig(ROOT/'fig'/f'fig{number}.pdf')
    fig.savefig(ROOT/'fig'/f'fig{number}.png', dpi=450)
    plt.close(fig)


def figure2():
    d=pd.read_csv(ROOT/'data/static_summary.csv')
    mem=pd.read_csv(ROOT/'data/static_separate_allocation.csv')
    fig,axs=plt.subplots(1,3,figsize=(7.16,2.65))
    fig.subplots_adjust(left=.075,right=.985,bottom=.27,top=.84,wspace=.49)
    hs=[]
    for name,col,marker,ls in METHODS:
        s=d[(d.kind=='legacy')&(d.method==name)].sort_values('n')
        x=s.n.to_numpy()*1.1;y=s.median_sec.to_numpy()
        hs.append(curve(axs[0],x,y,col,marker,ls))
        record(2,'a',name,x,y)
    log_axis(axs[0],'x',limit=(800,1.5e6));log_axis(axs[0],'y',limit=(3e-4,12))
    axs[0].set(xlabel=r'Total tuples $|r|$',ylabel='Checking time (s)')
    axs[0].set_xticks([1e3,1e4,1e5,1e6])
    for name,col,marker,ls in METHODS[1:]:
        s=d[(d.kind=='keys')&(d.n==250000)&(d.method==name)].sort_values('q')
        x=s.q.to_numpy();y=s.median_sec.to_numpy();lo=s.p25_sec.to_numpy();hi=s.p75_sec.to_numpy()
        curve(axs[1],x,y,col,marker,ls,lo,hi);record(2,'b',name,x,y,lo,hi,'IQR')
    axs[1].set(xlabel=r'Distinct keys $q$',ylabel='Checking time (s)',
               xticks=[1,2,4,8],xlim=(.6,8.5),ylim=(0,2.95))
    names=[x[0] for x in METHODS]
    m=mem[(mem.kind=='legacy')&(mem.n==100000)].set_index('method')
    vals=m.loc[names].python_peak_bytes.to_numpy()/2**20
    axs[2].barh(np.arange(3),vals,height=.55,color=[x[1] for x in METHODS],
                edgecolor='#49515A',linewidth=.45,zorder=3)
    axs[2].set(yticks=np.arange(3),yticklabels=['Raw FD','FD cover','BCNF'],
               xlim=(0,82),xlabel='Peak allocation (MiB)')
    axs[2].set_xticks([0,20,40,60,80]);axs[2].invert_yaxis()
    axs[2].tick_params(axis='y',length=0)
    for i,v in enumerate(vals):axs[2].text(v+1.8,i,f'{v:.2f}',ha='left',va='center',fontsize=8.0)
    record(2,'c','allocation',names,vals)
    for ax in axs[:2]:frame(ax)
    frame(axs[2],'x')
    key(fig,hs,names)
    panels(fig,axs,['(a) Static scalability','(b) Matched index counts','(c) Separate allocation'])
    save(fig,2)


def figure3():
    raw=pd.read_csv(ROOT/'data/fig4_swap_records.csv')
    bins=pd.read_csv(ROOT/'data/fig4_locality_bins.csv')
    summary=pd.read_csv(ROOT/'data/fig4_incremental_summary.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.16,2.80))
    fig.subplots_adjust(left=.083,right=.985,bottom=.25,top=.84,wspace=.30)
    hs=[]
    x=np.arange(4);w=.31
    for j,(dist,col,mark,ls,label) in enumerate(DIST):
        r=raw[(raw.block_distribution==dist)&(raw.touched_block_entries>0)]
        axs[0].scatter(r.touched_block_entries,r.incremental_total_time*1000,
                       s=3,c=col,alpha=.10,edgecolors='none',rasterized=True,zorder=2)
        b=bins[bins.distribution==dist].sort_values('x')
        hs.append(curve(axs[0],b.x.to_numpy(),b.y.to_numpy()*1000,col,mark,ls))
        record(3,'a',label,b.x.to_numpy(),b.y.to_numpy()*1000)
        s=summary[(summary.workload=='swap')&(summary.block_distribution==dist)].sort_values('batch_size')
        y=s.speedup_median.to_numpy();lo=s.speedup_p25.to_numpy();hi=s.speedup_p75.to_numpy()
        pos=x+(j-.5)*w
        axs[1].bar(pos,y-1,bottom=1,width=w*.88,color=col,edgecolor=GRAY,
                    hatch='' if j==0 else '///',linewidth=.45,zorder=3)
        axs[1].errorbar(pos,y,yerr=np.vstack([y-lo,hi-y]),fmt='none',
                         ecolor=INK,elinewidth=.6,capsize=2,capthick=.6,zorder=4)
        axs[1].annotate(f'{y[-1]:.1f}',xy=(pos[-1],hi[-1]),
                         xytext=(-2,4) if j==0 else (2,4),textcoords='offset points',
                         ha='right' if j==0 else 'left',va='bottom',fontsize=8.0)
        record(3,'b',label,s.batch_size.to_numpy(),y,lo,hi,'IQR')
    log_axis(axs[0],'x',limit=(1.6,1.4e5));log_axis(axs[0],'y',limit=(.025,70))
    axs[0].set(xlabel='Visited group entries',ylabel='Update time (ms)')
    axs[0].text(.97,.08,r'$\rho=0.968$ (Uniform)'+'\n'+r'$\rho=0.979$ (Zipf-1.2)',
                transform=axs[0].transAxes,ha='right',va='bottom',fontsize=8.1,color=INK)
    log_axis(axs[1],'y',limit=(1,2e5))
    axs[1].set(xlabel='Batch size',ylabel=r'Paired speedup ($\times$)',
               xticks=x,xticklabels=['1','10','100','1,000'],xlim=(-.6,3.6))
    axs[1].yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    for ax in axs:frame(ax)
    key(fig,hs,[s[4] for s in DIST])
    panels(fig,axs,['(a) Locality of swap updates','(b) Speedup over reconstruction'])
    save(fig,3)


def figure4():
    raw=pd.read_json(ROOT/'data/hot_raw.jsonl',lines=True)
    fig,axs=plt.subplots(1,2,figsize=(7.16,2.80))
    fig.subplots_adjust(left=.083,right=.985,bottom=.25,top=.84,wspace=.30)
    hs=[];labels=[]
    for h,col,mark,ls in [(1,TEAL,'o','-'),(100,GOLD,'^','-.'),(10000,SALMON,'s','--')]:
        label=rf'$h={h:,}$';labels.append(label)
        for k,(ax,field,mult) in enumerate([(axs[0],'inc_sec',1000),(axs[1],'speedup',1)]):
            g=raw[raw.hot_group_size==h].groupby('batch_size')[field]
            x=g.median().index.to_numpy();y=g.median().to_numpy()*mult
            lo=g.quantile(.25).to_numpy()*mult;hi=g.quantile(.75).to_numpy()*mult
            handle=curve(ax,x,y,col,mark,ls,lo,hi)
            if k==0:hs.append(handle)
            record(4,'ab'[k],label,x,y,lo,hi,'IQR')
    for ax in axs:
        log_axis(ax,'x',limit=(.75,140));log_axis(ax,'y')
        ax.set_xticks([1,10,100]);ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xlabel('Swaps per batch');frame(ax)
    axs[0].set_ylabel('Incremental latency (ms)');axs[0].set_ylim(.025,1400)
    axs[1].set_ylabel(r'Paired speedup ($\times$)');axs[1].set_ylim(.09,15000)
    axs[1].axhspan(.09,1,color=SALMON,alpha=.075,zorder=0)
    axs[1].axhline(1,color=GRAY,lw=.8,ls=(0,(3,3)),zorder=2)
    axs[1].text(.025,.13,'Rebuild faster',transform=axs[1].transAxes,
                ha='left',va='center',fontsize=8.0,color=INK)
    val=raw[(raw.hot_group_size==10000)&(raw.batch_size==100)].speedup.median()
    axs[1].annotate(f'{val:.3f}'+r'$\times$',xy=(100,val),xytext=(23,.14),
                    arrowprops=dict(arrowstyle='-',color=GRAY,lw=.6),
                    fontsize=8.3,ha='center',va='center')
    key(fig,hs,labels)
    panels(fig,axs,['(a) Update latency under hot groups','(b) Reconstruction crossover'])
    save(fig,4)


def figure5():
    d=pd.read_csv(ROOT/'data/tpch_summary.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.16,2.95))
    fig.subplots_adjust(left=.125,right=.985,bottom=.25,top=.83,wspace=.38)
    cats=[('customer',.01),('customer',.1),('lineitem',.01),('lineitem',.1)]
    specs=[('FD-Hash-Cover','FD-Hash-Cover',GOLD,''),
           ('BCNF-Index','BCNF-Index',TEAL,''),
           ('DuckDB-SQL','SQL resident',GRAY,''),
           ('DuckDB-SQL','SQL + load',PALE,'///')]
    handles=[];centers=np.arange(4);w=.16
    for j,(method,label,color,hatch) in enumerate(specs):
        values=[]
        for table,sf in cats:
            s=d[(d.table==table)&(d.sf==sf)&(d.case=='repair')&(d.method==method)]
            field='median_with_load_sec' if label=='SQL + load' else 'median_sec'
            values.append(float(s[field].iloc[0])*1000)
        axs[0].barh(centers+(j-1.5)*w,np.asarray(values)-1,left=1,height=w*.9,
                     color=color,hatch=hatch,edgecolor=GRAY,linewidth=.4,zorder=3)
        handles.append(Patch(facecolor=color,edgecolor=GRAY,hatch=hatch,linewidth=.4))
        record(5,'a',label,[f'{t}_{sf}' for t,sf in cats],values)
    log_axis(axs[0],'x',limit=(1,1e4))
    axs[0].set(yticks=centers,yticklabels=['Customer\nSF 0.01','Customer\nSF 0.1',
                                         'Lineitem\nSF 0.01','Lineitem\nSF 0.1'],
               xlabel='Elapsed time (ms)')
    axs[0].invert_yaxis();axs[0].tick_params(axis='y',length=0)
    frame(axs[0],'x')
    for method,col,mark,ls in [('FD-Hash-Cover',GOLD,'^','-.'),
                              ('BCNF-Index',TEAL,'o','-'),
                              ('DuckDB-SQL',GRAY,'s','--')]:
        s=d[(d.table=='lineitem')&(d.sf==.1)&(d.method==method)]
        cells=s.set_index('case').loc[['nonmax_0.0','nonmax_0.5','nonmax_1.0']]
        y=cells.median_sec.to_numpy()*1000;lo=cells.p25_sec.to_numpy()*1000;hi=cells.p75_sec.to_numpy()*1000
        curve(axs[1],[0,50,100],y,col,mark,ls,lo,hi)
        record(5,'b',method,[0,50,100],y,lo,hi,'IQR')
    axs[1].set(xlabel='Add-back witness position (%)',ylabel='Elapsed time (ms)',
               xticks=[0,50,100],xlim=(-7,107),ylim=(0,2550))
    frame(axs[1]);key(fig,handles,[s[1] for s in specs],4)
    panels(fig,axs,['(a) Valid repair candidates','(b) Non-maximal Lineitem, SF 0.1'])
    save(fig,5)


def figure6():
    d=pd.read_csv(ROOT/'data/fig6_llm_accuracy.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.16,2.65))
    fig.subplots_adjust(left=.145,right=.985,bottom=.25,top=.84,wspace=.45)
    specs=[('dirty',SALMON,'','Dirty evidence'),
           ('valid_repair',TEAL,'','Checked repair'),
           ('clean',PALE,'///','Clean control')]
    ybase=np.arange(2);w=.22
    for ax,category,panel in zip(axs,['ALL','Answer-Critical-Conflict'],['a','b']):
        for j,(condition,fill,hatch,label) in enumerate(specs):
            s=d[(d.category==category)&(d.condition==condition)].set_index('provider').loc[['zhipu','bailian']]
            vals=s.accuracy.to_numpy()*100;lo=s.ci_low.to_numpy()*100;hi=s.ci_high.to_numpy()*100
            pos=ybase+(j-1)*w
            ax.barh(pos,vals,height=w*.86,color=fill,edgecolor=GRAY,
                     hatch=hatch,linewidth=.4,zorder=3)
            ax.errorbar(vals,pos,xerr=np.maximum(0,np.vstack([vals-lo,hi-vals])),fmt='none',
                         ecolor=INK,elinewidth=.55,capsize=1.6,capthick=.55,zorder=4)
            for k,v in enumerate(vals):
                if condition=='dirty':
                    ax.text(hi[k]+1.3,pos[k],f'{v:.2f}',ha='left',va='center',fontsize=8.0)
                else:
                    ax.text(96.8,pos[k],'100',ha='right',va='center',fontsize=8.0,
                            color='white' if condition=='valid_repair' else INK)
            record(6,panel,condition,['zhipu','bailian'],vals,lo,hi,'95% Wilson')
        ax.set(xlabel='Accuracy (%)',xlim=(0,113),xticks=[0,25,50,75,100],
               yticks=ybase,yticklabels=['GLM-4-Flash','Qwen3.7-Flash'],ylim=(-.52,1.52))
        ax.invert_yaxis();ax.tick_params(axis='y',length=0);frame(ax,'x')
    key(fig,[Patch(facecolor=c,edgecolor=GRAY,hatch=h,linewidth=.4) for _,c,h,_ in specs],
        [s[3] for s in specs])
    panels(fig,axs,[r'(a) Overall ($n=1{,}200$)',r'(b) Answer-critical ($n=480$)'])
    save(fig,6)


def main():
    configure()
    (ROOT/'fig').mkdir(exist_ok=True)
    for fn in [figure2,figure3,figure4,figure5,figure6]:fn()
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').iterdir() if p.is_file()}
    (ROOT/'qa').mkdir(exist_ok=True)
    (ROOT/'qa/plot_values.json').write_text(json.dumps(POINTS,indent=2),encoding='utf-8')
    (ROOT/'qa/plot_input_sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print('Rendered five result figures from unchanged measurements; recorded',len(POINTS),'plotted series.')


if __name__=='__main__':main()
