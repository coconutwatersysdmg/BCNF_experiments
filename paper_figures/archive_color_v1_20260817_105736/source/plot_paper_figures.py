#!/usr/bin/env python3
"""Publication figures for 《计算机研究与发展》— BCNF subset-repair experiments.

Reads final audited CSVs only; aggregates by median/IQR; exports EPS/TIFF/PNG.
Academic colorblind-friendly palette (Okabe–Ito) with linestyle/marker cues.
Does NOT modify raw experiment CSVs.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.ticker import LogLocator, NullFormatter
from PIL import Image

# ---------------------------------------------------------------------------
# Layout (easy to retune to journal column width)
# ---------------------------------------------------------------------------
SINGLE_COLUMN_MM = 80.0
DOUBLE_COLUMN_MM = 165.0
FIG1_WIDTH_MM = 85.0
FONT_PT = 7.5
LINEWIDTH = 1.1
MARKERSIZE = 4.5
AXES_LW = 0.9
DPI_OUT = 600

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_FINAL = PROJECT_ROOT / "results" / "final"
OUT_ROOT = PROJECT_ROOT / "paper_figures"
OUT_SOURCE = OUT_ROOT / "source"
OUT_EPS = OUT_ROOT / "eps"
OUT_TIF = OUT_ROOT / "tif"
OUT_PREVIEW = OUT_ROOT / "preview"

# Academic colorblind-friendly palette (Okabe–Ito), plus linestyle/marker
STYLE_ALGO = {
    "BCNF-Index": dict(color="#0072B2", linestyle="-", marker="o", zorder=5),
    "FD-Hash": dict(color="#E69F00", linestyle="--", marker="s", zorder=4),
    "Singleton-FullScan": dict(color="#009E73", linestyle="-.", marker="^", zorder=3),
}
STYLE_DIST = {
    "uniform": dict(color="#0072B2", linestyle="-", marker="o", label="Uniform"),
    "zipf_1.2": dict(color="#D55E00", linestyle="--", marker="s", label="Zipf-1.2"),
}

REQUIRED_STATIC = {
    "algorithm",
    "case_type",
    "r_size",
    "r_prime_size",
    "seed",
    "rep",
    "total_time_sec",
    "python_peak_mb",
    "timeout",
}
REQUIRED_SENS = {
    "experiment",
    "param_value",
    "algorithm",
    "actual_nontrivial_fd_count",
    "raw_fd_index_count",
    "bcnf_index_count",
    "compression_ratio",
    "total_time_sec",
    "python_peak_mb",
    "block_distribution",
}
REQUIRED_INC = {
    "workload",
    "batch_size",
    "block_distribution",
    "incremental_total_time",
    "static_total_time",
    "speedup",
    "touched_block_entries",
    "touched_block_count",
    "result_match",
}

# Sanity expectations (detect wrong CSV)
SANITY_STATIC = {
    1100: {"BCNF-Index": 0.002586, "FD-Hash": 0.018610, "Singleton-FullScan": 0.487365},
    11000: {"BCNF-Index": 0.029231, "FD-Hash": 0.186176, "Singleton-FullScan": 48.893930},
    110000: {"BCNF-Index": 0.309120, "FD-Hash": 1.930301},
    1100000: {"BCNF-Index": 3.352710, "FD-Hash": 19.692411},
}
SANITY_FD_TIME = {
    1: {"FD-Hash": 7.220, "BCNF-Index": 3.836},
    2: {"FD-Hash": 12.363, "BCNF-Index": 4.030},
    4: {"FD-Hash": 20.625, "BCNF-Index": 3.507},
    8: {"FD-Hash": 42.834, "BCNF-Index": 3.797},
    15: {"FD-Hash": 74.095, "BCNF-Index": 3.516},
}
SANITY_FD_MEM = {
    1: {"FD-Hash": 225.33, "BCNF-Index": 133.78},
    2: {"FD-Hash": 349.25, "BCNF-Index": 133.78},
    4: {"FD-Hash": 597.10, "BCNF-Index": 133.78},
    8: {"FD-Hash": 1123.31, "BCNF-Index": 133.78},
    15: {"FD-Hash": 2097.59, "BCNF-Index": 133.78},
}


def mm_to_inch(mm: float) -> float:
    return mm / 25.4


def _fail(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    raise SystemExit(1)


def locate_csv(kind: str, required: set[str]) -> Path:
    """Prefer *(new).csv under results/final; else match by columns."""
    candidates: list[Path] = []
    patterns = {
        "static": ["static(new).csv", "static.csv"],
        "sensitivity": ["sensitivity(new).csv", "sensitivity.csv"],
        "incremental": ["incremental(new).csv", "incremental.csv"],
    }
    for name in patterns[kind]:
        p = RESULTS_FINAL / name
        if p.exists():
            candidates.append(p)
    # also scan final for column match
    for p in sorted(RESULTS_FINAL.glob("*.csv")):
        if p in candidates:
            continue
        if kind.split("_")[0] in p.name.lower() or kind in p.name.lower():
            candidates.append(p)

    for p in candidates:
        try:
            cols = set(pd.read_csv(p, nrows=0).columns)
        except Exception:
            continue
        if required <= cols:
            return p.resolve()
    _fail(
        f"Cannot locate a valid {kind} CSV with required columns {sorted(required)}. "
        f"Searched under {RESULTS_FINAL}"
    )
    raise AssertionError  # unreachable


def setup_fonts() -> dict[str, Any]:
    """Prefer 方正书宋 + Times New Roman. Never copy font files into the repo."""
    info: dict[str, Any] = {
        "times_ok": False,
        "fzshusong_ok": False,
        "times_path": None,
        "chinese_path": None,
        "chinese_name": None,
        "warning": None,
    }

    # Times New Roman
    times_path = Path(r"C:\Windows\Fonts\times.ttf")
    if times_path.exists():
        fm.fontManager.addfont(str(times_path))
        info["times_ok"] = True
        info["times_path"] = str(times_path)
    else:
        for f in fm.fontManager.ttflist:
            if f.name == "Times New Roman":
                info["times_ok"] = True
                info["times_path"] = f.fname
                break

    # 方正书宋 — search common Windows locations / names
    fz_names = (
        "方正书宋",
        "FZShuSong-Z01",
        "FZShuSong-Z01S",
        "FZShuSong",
        "FZ ShuSong",
    )
    search_dirs = [
        Path(r"C:\Windows\Fonts"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
    ]
    fz_file = None
    for d in search_dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            low = f.name.lower()
            if "fzss" in low or "shusong" in low or "书宋" in f.name:
                fz_file = f
                break
        if fz_file:
            break
    if fz_file is not None:
        fm.fontManager.addfont(str(fz_file))
        # resolve registered name
        for f in fm.fontManager.ttflist:
            if Path(f.fname).resolve() == fz_file.resolve():
                info["fzshusong_ok"] = True
                info["chinese_path"] = f.fname
                info["chinese_name"] = f.name
                break

    if not info["fzshusong_ok"]:
        # Preview fallback: STSong (华文宋体) — NOT journal-compliant
        st = Path(r"C:\Windows\Fonts\STSONG.TTF")
        if st.exists():
            fm.fontManager.addfont(str(st))
            info["chinese_path"] = str(st)
            info["chinese_name"] = "STSong"
        else:
            info["chinese_name"] = "SimSun"
            info["chinese_path"] = r"C:\Windows\Fonts\simsun.ttc"
        info["warning"] = (
            "WARNING: 方正书宋 not found. Preview figures use "
            f"{info['chinese_name']} as temporary fallback. "
            "正式投稿前需在安装方正书宋的环境中重新导出图片。"
        )
        print("\n" + "=" * 72)
        print(info["warning"])
        print("=" * 72 + "\n")

    chinese = info["chinese_name"] or "SimSun"
    times = "Times New Roman" if info["times_ok"] else "DejaVu Serif"

    mpl.rcParams.update(
        {
            "font.size": FONT_PT,
            "axes.labelsize": FONT_PT,
            "xtick.labelsize": FONT_PT,
            "ytick.labelsize": FONT_PT,
            "legend.fontsize": FONT_PT,
            "axes.titlesize": FONT_PT,
            "font.family": "serif",
            "font.serif": [times, chinese, "DejaVu Serif"],
            "axes.unicode_minus": False,
            "mathtext.fontset": "stix",
            "ps.fonttype": 42,
            "pdf.fonttype": 42,
            "savefig.dpi": DPI_OUT,
            "figure.dpi": 150,
            "axes.linewidth": AXES_LW,
            "xtick.major.width": AXES_LW,
            "ytick.major.width": AXES_LW,
            "xtick.minor.width": 0.6,
            "ytick.minor.width": 0.6,
            "lines.linewidth": LINEWIDTH,
            "lines.markersize": MARKERSIZE,
            "legend.frameon": False,
            "legend.handlelength": 2.2,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.grid": False,
        }
    )
    # Prefer Chinese font for CJK via fontproperties helper
    info["fp_cn"] = fm.FontProperties(
        fname=info["chinese_path"] if info["chinese_path"] else None,
        size=FONT_PT,
    )
    info["fp_en"] = fm.FontProperties(
        fname=info["times_path"] if info["times_path"] else None,
        size=FONT_PT,
    )
    return info


def set_label(ax, which: str, text: str, font_info: dict) -> None:
    """Axis labels: Chinese via 书宋/fallback, keep ASCII numerals in Times via default mix."""
    fp = font_info["fp_cn"]
    if which == "x":
        ax.set_xlabel(text, fontproperties=fp)
    else:
        ax.set_ylabel(text, fontproperties=fp)


def style_legend(ax, font_info: dict, loc: str = "best", **kwargs) -> None:
    leg = ax.legend(loc=loc, prop=font_info["fp_cn"], **kwargs)
    if leg is not None:
        for t in leg.get_texts():
            # Prefer Times for Latin tokens; matplotlib uses single font — use CN font that has Latin
            t.set_fontproperties(font_info["fp_en"])


def agg_median_iqr(df: pd.DataFrame, group_cols: list[str], value_col: str) -> pd.DataFrame:
    g = df.groupby(group_cols, dropna=False)[value_col]
    out = g.agg(
        median="median",
        q1=lambda s: s.quantile(0.25),
        q3=lambda s: s.quantile(0.75),
        n="count",
    ).reset_index()
    return out


def approx_close(a: float, b: float, rtol: float = 0.08, atol: float = 1e-4) -> bool:
    return abs(a - b) <= max(atol, rtol * abs(b))


def save_figure(fig: plt.Figure, stem: str, font_info: dict) -> dict[str, Path]:
    """Save EPS + 600dpi LZW RGB TIFF + PNG preview (academic color)."""
    paths = {}
    eps = OUT_EPS / f"{stem}.eps"
    tif = OUT_TIF / f"{stem}.tif"
    png = OUT_PREVIEW / f"{stem}.png"

    fig.savefig(eps, format="eps", bbox_inches="tight", pad_inches=0.02)
    paths["eps"] = eps

    fig.savefig(png, format="png", dpi=DPI_OUT, bbox_inches="tight", pad_inches=0.02)
    paths["png"] = png

    # Keep RGB for color academic figures; LZW (no JPEG compression)
    im = Image.open(png).convert("RGB")
    im.save(tif, format="TIFF", compression="tiff_lzw", dpi=(DPI_OUT, DPI_OUT))
    paths["tif"] = tif

    with Image.open(tif) as chk:
        dpi = chk.info.get("dpi", (None, None))
        paths["tif_meta"] = {
            "mode": chk.mode,
            "size": chk.size,
            "dpi": dpi,
            "compression": chk.info.get("compression", "tiff_lzw"),
        }
    return paths

def plot_fig1(static: pd.DataFrame, font_info: dict, report: list[str]) -> None:
    df = static.copy()
    df = df[df["case_type"].astype(str).str.lower() == "pass"].copy()
    df["timeout"] = df["timeout"].astype(str).str.lower().isin(["true", "1"])
    for c in ["r_size", "total_time_sec", "python_peak_mb"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    report.append("Fig.1 filter: case_type==pass; aggregate median over seed×rep")
    report.append(f"Fig.1 rows after filter: {len(df)}")

    ok = df[~df["timeout"]]
    med = agg_median_iqr(ok, ["algorithm", "r_size"], "total_time_sec")

    # Sanity
    for rsize, expect in SANITY_STATIC.items():
        for algo, exp_v in expect.items():
            row = med[(med.algorithm == algo) & (med.r_size == rsize)]
            if row.empty:
                _fail(f"Fig.1 sanity: missing median for {algo} r_size={rsize}")
            got = float(row["median"].iloc[0])
            if not approx_close(got, exp_v):
                _fail(
                    f"Fig.1 sanity FAIL: {algo} r_size={rsize}: got {got:.6f}, "
                    f"expected ≈{exp_v}. Wrong CSV?"
                )
    # timeouts present
    to = df[df["timeout"]]
    to_sizes = sorted(to["r_size"].dropna().unique())
    if 110000 not in to_sizes or 1100000 not in to_sizes:
        _fail("Fig.1 sanity: Singleton timeouts at 1e5/1e6 not found")

    # speedup at 1e6
    bcnf_1m = float(med[(med.algorithm == "BCNF-Index") & (med.r_size == 1100000)]["median"].iloc[0])
    fd_1m = float(med[(med.algorithm == "FD-Hash") & (med.r_size == 1100000)]["median"].iloc[0])
    speedup_1m = fd_1m / bcnf_1m
    report.append(f"Fig.1 |r|=1.1e6 speedup FD/BCNF = {speedup_1m:.4f}x")

    # Save aggregate data
    data_rows = []
    for _, r in med.iterrows():
        data_rows.append(
            {
                "algorithm": r["algorithm"],
                "r_size": int(r["r_size"]),
                "median_total_time_sec": r["median"],
                "q1_total_time_sec": r["q1"],
                "q3_total_time_sec": r["q3"],
                "n_runs": int(r["n"]),
                "timeout": False,
            }
        )
    for rsize in (110000, 1100000):
        data_rows.append(
            {
                "algorithm": "Singleton-FullScan",
                "r_size": rsize,
                "median_total_time_sec": np.nan,
                "q1_total_time_sec": np.nan,
                "q3_total_time_sec": np.nan,
                "n_runs": int(((to["algorithm"] == "Singleton-FullScan") & (to["r_size"] == rsize)).sum()),
                "timeout": True,
            }
        )
    data_df = pd.DataFrame(data_rows).sort_values(["algorithm", "r_size"])
    data_path = OUT_SOURCE / "fig1_data.csv"
    data_df.to_csv(data_path, index=False)

    # Plot
    w = mm_to_inch(FIG1_WIDTH_MM)
    h = w * 0.72
    fig, ax = plt.subplots(figsize=(w, h))

    order = ["BCNF-Index", "FD-Hash", "Singleton-FullScan"]
    for algo in order:
        sub = med[med.algorithm == algo].sort_values("r_size")
        if sub.empty:
            continue
        st = STYLE_ALGO[algo]
        yerr = np.vstack(
            [
                sub["median"] - sub["q1"],
                sub["q3"] - sub["median"],
            ]
        )
        ax.errorbar(
            sub["r_size"],
            sub["median"],
            yerr=yerr,
            label=algo,
            color=st["color"],
            linestyle=st["linestyle"],
            marker=st["marker"],
            linewidth=LINEWIDTH,
            markersize=MARKERSIZE,
            capsize=2.0,
            elinewidth=0.7,
            zorder=st["zorder"],
        )

    # TO annotations near top for Singleton at large x
    ymax = ax.get_ylim()[1]
    # after log scale set
    ax.set_xscale("log")
    ax.set_yscale("log")
    set_label(ax, "x", "数据库规模/条", font_info)
    set_label(ax, "y", "运行时间/s", font_info)

    # place TO above last drawn Singleton median at 11000, at x=1e5 and 1e6
    y_to = float(med[(med.algorithm == "Singleton-FullScan") & (med.r_size == 11000)]["median"].iloc[0])
    for xto in (110000, 1100000):
        ax.annotate(
            "TO",
            xy=(xto, y_to),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontproperties=font_info["fp_en"],
            fontsize=FONT_PT,
            color="#333333",
        )
        ax.plot(
            [xto],
            [y_to],
            marker="x",
            color=STYLE_ALGO["Singleton-FullScan"]["color"],
            markersize=5,
            linestyle="none",
            zorder=6,
        )

    style_legend(ax, font_info, loc="upper left")
    for spine in ax.spines.values():
        spine.set_linewidth(AXES_LW)
    fig.tight_layout(pad=0.15)
    paths = save_figure(fig, "fig1_static_scalability", font_info)
    plt.close(fig)
    report.append(f"Fig.1 saved: {paths['eps']}, {paths['tif']}, {paths['png']}")
    report.append(f"Fig.1 TIFF meta: {paths['tif_meta']}")
    report.append(f"Fig.1 size: {FIG1_WIDTH_MM} mm wide")
    report.append("Fig.1 sanity: PASSED")


def plot_fig2(sens: pd.DataFrame, font_info: dict, report: list[str]) -> None:
    df = sens[sens["experiment"] == "B_fd_count"].copy()
    if df.empty:
        _fail("Fig.2: no rows with experiment==B_fd_count")
    for c in [
        "actual_nontrivial_fd_count",
        "total_time_sec",
        "python_peak_mb",
        "raw_fd_index_count",
        "bcnf_index_count",
        "compression_ratio",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    report.append("Fig.2 filter: experiment==B_fd_count; x=actual_nontrivial_fd_count")
    report.append(f"Fig.2 rows: {len(df)}")

    tmed = agg_median_iqr(df, ["algorithm", "actual_nontrivial_fd_count"], "total_time_sec")
    mmed = agg_median_iqr(df, ["algorithm", "actual_nontrivial_fd_count"], "python_peak_mb")

    # index stats (from BCNF / FD rows)
    idx_rows = []
    for fd in sorted(df["actual_nontrivial_fd_count"].dropna().unique()):
        sub = df[df["actual_nontrivial_fd_count"] == fd]
        raw = float(sub["raw_fd_index_count"].median())
        bci = float(sub["bcnf_index_count"].median())
        comp = float(sub["compression_ratio"].median())
        idx_rows.append(
            {
                "actual_nontrivial_fd_count": int(fd),
                "raw_fd_index_count": raw,
                "bcnf_index_count": bci,
                "compression_ratio": comp,
            }
        )
        for algo in ("FD-Hash", "BCNF-Index"):
            tr = tmed[(tmed.algorithm == algo) & (tmed.actual_nontrivial_fd_count == fd)]
            mr = mmed[(mmed.algorithm == algo) & (mmed.actual_nontrivial_fd_count == fd)]
            if tr.empty or mr.empty:
                _fail(f"Fig.2 missing aggregate for {algo} fd={fd}")
            et = SANITY_FD_TIME[int(fd)][algo]
            em = SANITY_FD_MEM[int(fd)][algo]
            gt = float(tr["median"].iloc[0])
            gm = float(mr["median"].iloc[0])
            if not approx_close(gt, et, rtol=0.08):
                _fail(f"Fig.2 time sanity FAIL {algo} fd={fd}: got {gt:.3f} expected ≈{et}")
            if not approx_close(gm, em, rtol=0.08):
                _fail(f"Fig.2 mem sanity FAIL {algo} fd={fd}: got {gm:.2f} expected ≈{em}")

    idx_df = pd.DataFrame(idx_rows)
    last = idx_df[idx_df.actual_nontrivial_fd_count == 15].iloc[0]
    if int(last.raw_fd_index_count) != 15 or int(last.bcnf_index_count) != 1:
        _fail(f"Fig.2 index sanity FAIL at fd=15: raw={last.raw_fd_index_count}, bcnf={last.bcnf_index_count}")
    if not approx_close(float(last.compression_ratio), 0.9333, rtol=0.02):
        _fail(f"Fig.2 compression sanity FAIL: {last.compression_ratio}")

    # merge data csv
    data = tmed.merge(
        mmed,
        on=["algorithm", "actual_nontrivial_fd_count"],
        suffixes=("_time", "_mem"),
    )
    data = data.merge(idx_df, on="actual_nontrivial_fd_count", how="left")
    data = data.rename(
        columns={
            "median_time": "median_total_time_sec",
            "q1_time": "q1_total_time_sec",
            "q3_time": "q3_total_time_sec",
            "n_time": "n_runs_time",
            "median_mem": "median_python_peak_mb",
            "q1_mem": "q1_python_peak_mb",
            "q3_mem": "q3_python_peak_mb",
            "n_mem": "n_runs_mem",
        }
    )
    # fix names from merge
    rename_map = {}
    for c in data.columns:
        if c == "median_x":
            rename_map[c] = "median_total_time_sec"
        elif c == "q1_x":
            rename_map[c] = "q1_total_time_sec"
        elif c == "q3_x":
            rename_map[c] = "q3_total_time_sec"
        elif c == "n_x":
            rename_map[c] = "n_runs"
        elif c == "median_y":
            rename_map[c] = "median_python_peak_mb"
        elif c == "q1_y":
            rename_map[c] = "q1_python_peak_mb"
        elif c == "q3_y":
            rename_map[c] = "q3_python_peak_mb"
        elif c == "n_y":
            rename_map[c] = "n_runs_mem"
    data = data.rename(columns=rename_map)
    data.to_csv(OUT_SOURCE / "fig2_data.csv", index=False)

    fd15_fd = float(tmed[(tmed.algorithm == "FD-Hash") & (tmed.actual_nontrivial_fd_count == 15)]["median"].iloc[0])
    fd15_bc = float(tmed[(tmed.algorithm == "BCNF-Index") & (tmed.actual_nontrivial_fd_count == 15)]["median"].iloc[0])
    mem15_fd = float(mmed[(mmed.algorithm == "FD-Hash") & (mmed.actual_nontrivial_fd_count == 15)]["median"].iloc[0])
    mem15_bc = float(mmed[(mmed.algorithm == "BCNF-Index") & (mmed.actual_nontrivial_fd_count == 15)]["median"].iloc[0])
    report.append(f"Fig.2 fd=15 runtime speedup = {fd15_fd/fd15_bc:.4f}x")
    report.append(f"Fig.2 fd=15 memory reduction = {mem15_fd/mem15_bc:.4f}x")
    report.append(f"Fig.2 index compression at fd=15 = {float(last.compression_ratio)*100:.2f}% (15→1)")

    w = mm_to_inch(DOUBLE_COLUMN_MM)
    h = w * 0.38
    fig, axes = plt.subplots(1, 2, figsize=(w, h))

    # (a) runtime
    ax = axes[0]
    for algo in ("FD-Hash", "BCNF-Index"):
        sub = tmed[tmed.algorithm == algo].sort_values("actual_nontrivial_fd_count")
        st = STYLE_ALGO[algo]
        yerr = np.vstack([sub["median"] - sub["q1"], sub["q3"] - sub["median"]])
        ax.errorbar(
            sub["actual_nontrivial_fd_count"],
            sub["median"],
            yerr=yerr,
            label=algo,
            color=st["color"],
            linestyle=st["linestyle"],
            marker=st["marker"],
            linewidth=LINEWIDTH,
            markersize=MARKERSIZE,
            capsize=2.0,
            elinewidth=0.7,
        )
    set_label(ax, "x", "非平凡函数依赖数量/个", font_info)
    set_label(ax, "y", "运行时间/s", font_info)
    ax.set_xticks([1, 2, 4, 8, 15])
    style_legend(ax, font_info, loc="upper left")
    ax.text(
        0.02,
        0.98,
        "(a)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
    )

    # (b) memory
    ax = axes[1]
    for algo in ("FD-Hash", "BCNF-Index"):
        sub = mmed[mmed.algorithm == algo].sort_values("actual_nontrivial_fd_count")
        st = STYLE_ALGO[algo]
        yerr = np.vstack([sub["median"] - sub["q1"], sub["q3"] - sub["median"]])
        ax.errorbar(
            sub["actual_nontrivial_fd_count"],
            sub["median"],
            yerr=yerr,
            label=algo,
            color=st["color"],
            linestyle=st["linestyle"],
            marker=st["marker"],
            linewidth=LINEWIDTH,
            markersize=MARKERSIZE,
            capsize=2.0,
            elinewidth=0.7,
        )
    set_label(ax, "x", "非平凡函数依赖数量/个", font_info)
    set_label(ax, "y", "峰值内存/MB", font_info)
    ax.set_xticks([1, 2, 4, 8, 15])
    style_legend(ax, font_info, loc="upper left")
    # compact annotation if space
    ax.text(
        0.98,
        0.55,
        "15 → 1 indexes\n93.3%",
        transform=ax.transAxes,
        ha="right",
        va="center",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
        color="#333333",
    )
    ax.text(
        0.02,
        0.98,
        "(b)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
    )

    for ax in axes:
        for spine in ax.spines.values():
            spine.set_linewidth(AXES_LW)

    fig.tight_layout(pad=0.4, w_pad=1.0)
    paths = save_figure(fig, "fig2_fd_scaling", font_info)
    plt.close(fig)
    report.append(f"Fig.2 saved: {paths['eps']}, {paths['tif']}, {paths['png']}")
    report.append(f"Fig.2 TIFF meta: {paths['tif_meta']}")
    report.append(f"Fig.2 size: {DOUBLE_COLUMN_MM} mm wide")
    report.append("Fig.2 sanity: PASSED")


def _log_bins(values: np.ndarray, n_bins: int = 18) -> np.ndarray:
    values = values[np.isfinite(values) & (values > 0)]
    if len(values) == 0:
        return np.array([])
    lo, hi = values.min(), values.max()
    if lo == hi:
        return np.array([lo, hi * 1.01 + 1e-12])
    return np.logspace(np.log10(lo), np.log10(hi), n_bins + 1)


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import spearmanr

    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return float("nan")
    r, _ = spearmanr(x[m], y[m])
    return float(r)


def plot_fig3(inc: pd.DataFrame, font_info: dict, report: list[str]) -> None:
    df = inc[inc["workload"] == "swap"].copy()
    if df.empty:
        _fail("Fig.3: no swap workload rows")
    for c in [
        "batch_size",
        "incremental_total_time",
        "static_total_time",
        "speedup",
        "touched_block_entries",
        "touched_block_count",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # drop zero-touch empty plans for panel a correlation clarity? Keep all >0 for locality
    report.append("Fig.3 filter: workload==swap")
    report.append(f"Fig.3 rows: {len(df)}")

    # Spearman
    rho_u = spearman_rho(
        df[df.block_distribution == "uniform"]["touched_block_entries"].to_numpy(),
        df[df.block_distribution == "uniform"]["incremental_total_time"].to_numpy(),
    )
    rho_z = spearman_rho(
        df[df.block_distribution == "zipf_1.2"]["touched_block_entries"].to_numpy(),
        df[df.block_distribution == "zipf_1.2"]["incremental_total_time"].to_numpy(),
    )
    rho_all = spearman_rho(
        df["touched_block_entries"].to_numpy(),
        df["incremental_total_time"].to_numpy(),
    )
    report.append(f"Fig.3 Spearman rho uniform={rho_u:.6f}")
    report.append(f"Fig.3 Spearman rho zipf_1.2={rho_z:.6f}")
    report.append(f"Fig.3 Spearman rho all_swap={rho_all:.6f}")
    if not approx_close(rho_all, 0.986, rtol=0.03, atol=0.03):
        _fail(f"Fig.3 Spearman all={rho_all:.4f} far from expected ≈0.986; wrong CSV?")

    # Panel a: log-bin medians
    bin_rows = []
    for dist in ("uniform", "zipf_1.2"):
        sub = df[df.block_distribution == dist].copy()
        sub = sub[sub["touched_block_entries"] > 0]
        edges = _log_bins(sub["touched_block_entries"].to_numpy(), n_bins=18)
        sub["bin"] = pd.cut(sub["touched_block_entries"], bins=edges, include_lowest=True)
        for b, g in sub.groupby("bin", observed=True):
            if len(g) < 3:
                continue
            bin_rows.append(
                {
                    "block_distribution": dist,
                    "bin": str(b),
                    "median_touched_block_entries": g["touched_block_entries"].median(),
                    "median_incremental_total_time": g["incremental_total_time"].median(),
                    "q1_incremental_total_time": g["incremental_total_time"].quantile(0.25),
                    "q3_incremental_total_time": g["incremental_total_time"].quantile(0.75),
                    "n": len(g),
                }
            )
    bin_df = pd.DataFrame(bin_rows)

    # Panel b: speedup by batch
    sp = agg_median_iqr(df, ["block_distribution", "batch_size"], "speedup")
    # sanity speedups
    expect_u = {1: 44278, 10: 11382, 100: 1450, 1000: 166}
    expect_z = {1: 51703, 10: 12408, 100: 1888, 1000: 180}
    for bs, exp in expect_u.items():
        got = float(sp[(sp.block_distribution == "uniform") & (sp.batch_size == bs)]["median"].iloc[0])
        if not approx_close(got, exp, rtol=0.15):
            _fail(f"Fig.3b uniform batch={bs} speedup got {got:.1f} expected ≈{exp}")
    for bs, exp in expect_z.items():
        got = float(sp[(sp.block_distribution == "zipf_1.2") & (sp.batch_size == bs)]["median"].iloc[0])
        if not approx_close(got, exp, rtol=0.15):
            _fail(f"Fig.3b zipf batch={bs} speedup got {got:.1f} expected ≈{exp}")

    # save fig3 data
    out_a = bin_df.copy()
    out_a["panel"] = "a"
    out_b = sp.copy()
    out_b["panel"] = "b"
    out_b = out_b.rename(
        columns={
            "median": "median_speedup",
            "q1": "q1_speedup",
            "q3": "q3_speedup",
            "n": "n_runs",
        }
    )
    # write combined-ish: two sections via keys
    with open(OUT_SOURCE / "fig3_data.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# panel_a: binned touched_block_entries vs latency\n")
        out_a.to_csv(f, index=False)
        f.write("\n# panel_b: batch_size vs speedup\n")
        out_b.to_csv(f, index=False)
    # also clean separate for tooling
    out_a.to_csv(OUT_SOURCE / "fig3a_binned_data.csv", index=False)
    out_b.to_csv(OUT_SOURCE / "fig3b_speedup_data.csv", index=False)

    w = mm_to_inch(DOUBLE_COLUMN_MM)
    h = w * 0.38
    fig, axes = plt.subplots(1, 2, figsize=(w, h))

    # (a)
    ax = axes[0]
    for dist in ("uniform", "zipf_1.2"):
        sub = bin_df[bin_df.block_distribution == dist].sort_values("median_touched_block_entries")
        if sub.empty:
            continue
        st = STYLE_DIST[dist]
        y = sub["median_incremental_total_time"]
        yerr = np.vstack([y - sub["q1_incremental_total_time"], sub["q3_incremental_total_time"] - y])
        ax.errorbar(
            sub["median_touched_block_entries"],
            y,
            yerr=yerr,
            label=st["label"],
            color=st["color"],
            linestyle=st["linestyle"],
            marker=st["marker"],
            linewidth=LINEWIDTH,
            markersize=MARKERSIZE,
            capsize=2.0,
            elinewidth=0.7,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    set_label(ax, "x", "实际访问冲突块条目数/条", font_info)
    set_label(ax, "y", "增量更新时间/s", font_info)
    style_legend(ax, font_info, loc="upper left")
    ax.text(
        0.98,
        0.05,
        f"ρ={rho_u:.3f}\nρ={rho_z:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
        color="#333333",
    )
    ax.text(
        0.02,
        0.98,
        "(a)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
    )

    # (b)
    ax = axes[1]
    for dist in ("uniform", "zipf_1.2"):
        sub = sp[sp.block_distribution == dist].sort_values("batch_size")
        st = STYLE_DIST[dist]
        yerr = np.vstack([sub["median"] - sub["q1"], sub["q3"] - sub["median"]])
        ax.errorbar(
            sub["batch_size"],
            sub["median"],
            yerr=yerr,
            label=st["label"],
            color=st["color"],
            linestyle=st["linestyle"],
            marker=st["marker"],
            linewidth=LINEWIDTH,
            markersize=MARKERSIZE,
            capsize=2.0,
            elinewidth=0.7,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    set_label(ax, "x", "批大小/次", font_info)
    set_label(ax, "y", "加速比/倍", font_info)
    ax.set_xticks([1, 10, 100, 1000])
    ax.get_xaxis().set_major_formatter(mpl.ticker.ScalarFormatter())
    # y=1 reference if in range
    ymin, ymax = ax.get_ylim()
    if ymin < 1 < ymax:
        ax.axhline(1.0, color="#888888", linestyle=":", linewidth=0.8)
    style_legend(ax, font_info, loc="upper right")
    ax.text(
        0.02,
        0.98,
        "(b)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
    )

    for ax in axes:
        for spine in ax.spines.values():
            spine.set_linewidth(AXES_LW)

    fig.tight_layout(pad=0.4, w_pad=1.0)
    paths = save_figure(fig, "fig3_incremental_locality", font_info)
    plt.close(fig)
    report.append(f"Fig.3 saved: {paths['eps']}, {paths['tif']}, {paths['png']}")
    report.append(f"Fig.3 TIFF meta: {paths['tif_meta']}")
    report.append(f"Fig.3 size: {DOUBLE_COLUMN_MM} mm wide")
    report.append("Fig.3 sanity: PASSED")


def write_d_only_summary(inc: pd.DataFrame) -> None:
    df = inc[inc["workload"] == "d_only"].copy()
    for c in ["batch_size", "incremental_total_time", "static_total_time", "speedup"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    rows = []
    for dist in ("uniform", "zipf_1.2"):
        for bs in (1, 10, 100, 1000):
            g = df[(df.block_distribution == dist) & (df.batch_size == bs)]
            rows.append(
                {
                    "workload": "d_only",
                    "block_distribution": dist,
                    "batch_size": bs,
                    "median_incremental_total_time": g["incremental_total_time"].median(),
                    "median_static_total_time": g["static_total_time"].median(),
                    "median_speedup": g["speedup"].median(),
                    "n": len(g),
                }
            )
    pd.DataFrame(rows).to_csv(OUT_SOURCE / "d_only_summary.csv", index=False)


def write_sensitivity_compact(sens: pd.DataFrame) -> None:
    rows = []
    for exp in ("A_conflict_ratio", "C_key_width", "D_block_distribution"):
        sub = sens[sens["experiment"] == exp].copy()
        sub["total_time_sec"] = pd.to_numeric(sub["total_time_sec"], errors="coerce")
        sub["python_peak_mb"] = pd.to_numeric(sub["python_peak_mb"], errors="coerce")
        key = "param_value"
        for pv, g in sub.groupby(key):
            fd = g[g.algorithm == "FD-Hash"]["total_time_sec"].median()
            bc = g[g.algorithm == "BCNF-Index"]["total_time_sec"].median()
            fdm = g[g.algorithm == "FD-Hash"]["python_peak_mb"].median()
            bcm = g[g.algorithm == "BCNF-Index"]["python_peak_mb"].median()
            rows.append(
                {
                    "experiment": exp,
                    "param_value": pv,
                    "median_FD_Hash_total_time_sec": fd,
                    "median_BCNF_Index_total_time_sec": bc,
                    "speedup_FD_over_BCNF": (fd / bc) if bc and bc > 0 else np.nan,
                    "median_FD_Hash_python_peak_mb": fdm,
                    "median_BCNF_Index_python_peak_mb": bcm,
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_SOURCE / "sensitivity_compact_summary.csv", index=False)

    # checks
    a = out[out.experiment == "A_conflict_ratio"]
    if (a["speedup_FD_over_BCNF"] <= 1).any():
        _fail("sensitivity compact: BCNF not always faster on conflict_ratio")
    c = out[out.experiment == "C_key_width"]
    bc_times = c["median_BCNF_Index_total_time_sec"]
    if not ((bc_times >= 3.0) & (bc_times <= 4.5)).all():
        print(f"[WARN] key_width BCNF times outside 3.6–3.9 band: {list(bc_times)}")


def main() -> int:
    for d in (OUT_SOURCE, OUT_EPS, OUT_TIF, OUT_PREVIEW):
        d.mkdir(parents=True, exist_ok=True)

    # copy this script into source/ for archival (read source file)
    src_self = Path(__file__).resolve()
    archived = OUT_SOURCE / "plot_paper_figures.py"
    if src_self != archived:
        archived.write_text(src_self.read_text(encoding="utf-8"), encoding="utf-8")

    font_info = setup_fonts()
    report: list[str] = []
    report.append("=== Paper figure generation report ===")
    report.append(f"Times New Roman available: {font_info['times_ok']} ({font_info['times_path']})")
    report.append(f"方正书宋 available: {font_info['fzshusong_ok']} ({font_info.get('chinese_path')})")
    if font_info["warning"]:
        report.append(font_info["warning"])
        report.append("正式投稿前需在安装方正书宋的环境中重新导出图片。")

    static_path = locate_csv("static", REQUIRED_STATIC)
    sens_path = locate_csv("sensitivity", REQUIRED_SENS)
    inc_path = locate_csv("incremental", REQUIRED_INC)

    static = pd.read_csv(static_path)
    sens = pd.read_csv(sens_path)
    inc = pd.read_csv(inc_path)

    report.append(f"static CSV: {static_path}  rows={len(static)}")
    report.append(f"sensitivity CSV: {sens_path}  rows={len(sens)}")
    report.append(f"incremental CSV: {inc_path}  rows={len(inc)}")
    report.append("Aggregation: median over seed×rep (or all matching runs); IQR = Q1–Q3")
    report.append(f"SINGLE_COLUMN_MM={SINGLE_COLUMN_MM}, DOUBLE_COLUMN_MM={DOUBLE_COLUMN_MM}, FIG1_WIDTH_MM={FIG1_WIDTH_MM}")
    report.append(f"Target TIFF dpi={DPI_OUT}")

    plot_fig1(static, font_info, report)
    plot_fig2(sens, font_info, report)
    plot_fig3(inc, font_info, report)
    write_d_only_summary(inc)
    write_sensitivity_compact(sens)
    report.append(f"Wrote {OUT_SOURCE / 'd_only_summary.csv'}")
    report.append(f"Wrote {OUT_SOURCE / 'sensitivity_compact_summary.csv'}")

    report_path = OUT_ROOT / "figure_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\n[OK] figure_report → {report_path}")
    if not font_info["fzshusong_ok"]:
        print(
            "\n*** 正式投稿前请安装方正书宋后重新运行本脚本导出 EPS/TIFF ***",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
