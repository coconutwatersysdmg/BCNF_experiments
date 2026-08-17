#!/usr/bin/env python3
"""Fig.4 — LLM structured QA under different data-consistency conditions.

Reads llm_study/results/final/exp1_summary.csv only.
Does NOT call APIs, regenerate datasets, or modify Prompts.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from PIL import Image

DOUBLE_COLUMN_MM = 165.0
FONT_PT = 7.5
AXES_LW = 0.9
ERR_LW = 0.9
DPI_OUT = 600
BAR_WIDTH = 0.36

# experiments/paper_figures/source/ → experiments/
EXPERIMENTS_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = EXPERIMENTS_ROOT / "paper_figures"
OUT_SOURCE = OUT_ROOT / "source"
OUT_EPS = OUT_ROOT / "eps"
OUT_TIF = OUT_ROOT / "tif"
OUT_PREVIEW = OUT_ROOT / "preview"
LLM_FINAL = EXPERIMENTS_ROOT.parent / "llm_study" / "results" / "final"

CONDITIONS = ["clean", "dirty", "valid_repair"]
COND_LABELS = ["Clean", "Dirty", "Valid Repair"]
MODEL_ORDER = [
    ("zhipu", "GLM-4-Flash"),
    ("bailian", "Qwen3.7-Flash"),
]

# Sanity anchors (detect wrong CSV; never hard-code into plot)
SANITY = {
    ("bailian", "ALL", "clean"): 1.000,
    ("bailian", "ALL", "dirty"): 0.7358,
    ("bailian", "ALL", "valid_repair"): 1.000,
    ("bailian", "Answer-Critical-Conflict", "dirty"): 0.3396,
    ("zhipu", "ALL", "clean"): 1.000,
    ("zhipu", "ALL", "dirty"): 0.813,
    ("zhipu", "ALL", "valid_repair"): 1.000,
    ("zhipu", "Answer-Critical-Conflict", "dirty"): 0.533,
}


def mm_to_inch(mm: float) -> float:
    return mm / 25.4


def setup_fonts() -> dict[str, Any]:
    info: dict[str, Any] = {
        "times_ok": False,
        "fzshusong_ok": False,
        "times_path": None,
        "chinese_path": None,
        "chinese_name": None,
        "warning": None,
    }
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

    fz_file = None
    for d in (
        Path(r"C:\Windows\Fonts"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
    ):
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
        for f in fm.fontManager.ttflist:
            if Path(f.fname).resolve() == fz_file.resolve():
                info["fzshusong_ok"] = True
                info["chinese_path"] = f.fname
                info["chinese_name"] = f.name
                break

    if not info["fzshusong_ok"]:
        st = Path(r"C:\Windows\Fonts\STSONG.TTF")
        if st.exists():
            fm.fontManager.addfont(str(st))
            info["chinese_path"] = str(st)
            info["chinese_name"] = "STSong"
        else:
            info["chinese_name"] = "SimSun"
            info["chinese_path"] = r"C:\Windows\Fonts\simsun.ttc"
        info["warning"] = (
            "WARNING: 方正书宋 not found. Figures use "
            f"{info['chinese_name']} as temporary fallback (NOT silent). "
            "正式投稿前需在安装方正书宋的环境中重新导出 EPS/TIFF。"
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
            "font.family": "serif",
            "font.serif": [times, chinese, "DejaVu Serif"],
            "axes.unicode_minus": False,
            "ps.fonttype": 42,
            "pdf.fonttype": 42,
            "savefig.dpi": DPI_OUT,
            "figure.dpi": 150,
            "axes.linewidth": AXES_LW,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.grid": False,
            "legend.frameon": False,
        }
    )
    info["fp_cn"] = fm.FontProperties(
        fname=info["chinese_path"] if info["chinese_path"] else None,
        size=FONT_PT,
    )
    info["fp_en"] = fm.FontProperties(
        fname=info["times_path"] if info["times_path"] else None,
        size=FONT_PT,
    )
    return info


def load_exp1() -> pd.DataFrame:
    path = LLM_FINAL / "exp1_summary.csv"
    if not path.exists():
        raise SystemExit(f"[FATAL] missing {path}")
    df = pd.read_csv(path)
    for c in ("accuracy", "ci_low", "ci_high", "n"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def sanity_check(df: pd.DataFrame) -> None:
    for (prov, cat, cond), expect in SANITY.items():
        row = df[
            (df["provider"] == prov)
            & (df["category"] == cat)
            & (df["condition"] == cond)
        ]
        if row.empty:
            print(f"[WARN] sanity missing row {prov}/{cat}/{cond}")
            continue
        acc = float(row.iloc[0]["accuracy"])
        if abs(acc - expect) > 0.02:
            print(
                f"[WARN] sanity mismatch {prov}/{cat}/{cond}: "
                f"got {acc:.4f} expect≈{expect}"
            )


def bar_style(provider: str) -> dict[str, Any]:
    if provider == "zhipu":
        return dict(
            facecolor="0.95",
            edgecolor="black",
            hatch="///",
            linewidth=0.8,
        )
    return dict(
        facecolor="0.45",
        edgecolor="black",
        hatch="\\\\\\",
        linewidth=0.8,
    )


def plot_panel(
    ax: plt.Axes,
    df: pd.DataFrame,
    category: str,
    font_info: dict,
    panel: str,
    annotate_dirty: bool,
) -> pd.DataFrame:
    x = np.arange(len(CONDITIONS))
    records = []
    for i, (prov, label) in enumerate(MODEL_ORDER):
        accs, yerr_lo, yerr_hi = [], [], []
        style = bar_style(prov)
        for cond in CONDITIONS:
            row = df[
                (df["provider"] == prov)
                & (df["category"] == category)
                & (df["condition"] == cond)
            ]
            if row.empty:
                raise SystemExit(f"missing {prov} {category} {cond}")
            r = row.iloc[0]
            acc = float(r["accuracy"]) * 100.0
            lo = float(r["ci_low"]) * 100.0
            hi = float(r["ci_high"]) * 100.0
            accs.append(acc)
            yerr_lo.append(acc - lo)
            yerr_hi.append(hi - acc)
            records.append(
                {
                    "panel": panel,
                    "category": category,
                    "provider": prov,
                    "model_label": label,
                    "condition": cond,
                    "accuracy": float(r["accuracy"]),
                    "accuracy_pct": acc,
                    "ci_low": float(r["ci_low"]),
                    "ci_high": float(r["ci_high"]),
                    "n": int(r["n"]),
                }
            )
        offset = -BAR_WIDTH / 2 if i == 0 else BAR_WIDTH / 2
        bars = ax.bar(
            x + offset,
            accs,
            BAR_WIDTH,
            label=label,
            yerr=np.vstack([yerr_lo, yerr_hi]),
            error_kw=dict(ecolor="black", lw=ERR_LW, capsize=2.0, capthick=ERR_LW),
            zorder=3,
            **style,
        )
        if annotate_dirty:
            # annotate Dirty bars only
            dirty_idx = CONDITIONS.index("dirty")
            ax.text(
                x[dirty_idx] + offset,
                accs[dirty_idx] + 2.5,
                f"{accs[dirty_idx]:.1f}",
                ha="center",
                va="bottom",
                fontproperties=font_info["fp_en"],
                fontsize=FONT_PT,
            )
        _ = bars

    ax.set_xticks(x)
    ax.set_xticklabels(COND_LABELS, fontproperties=font_info["fp_en"])
    ax.set_ylim(0, 105)
    ax.set_ylabel("准确率/%", fontproperties=font_info["fp_cn"])
    ax.set_xlabel("数据条件", fontproperties=font_info["fp_cn"])
    ax.text(
        -0.08,
        1.02,
        panel,
        transform=ax.transAxes,
        fontproperties=font_info["fp_en"],
        fontsize=FONT_PT,
        va="bottom",
        ha="left",
    )
    for spine in ax.spines.values():
        spine.set_linewidth(AXES_LW)
        spine.set_color("black")
    ax.tick_params(width=AXES_LW, colors="black")
    for lab in ax.get_yticklabels():
        lab.set_fontproperties(font_info["fp_en"])
    return pd.DataFrame(records)


def save_figure(fig: plt.Figure, stem: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    eps = OUT_EPS / f"{stem}.eps"
    tif = OUT_TIF / f"{stem}.tif"
    png = OUT_PREVIEW / f"{stem}.png"

    fig.savefig(eps, format="eps", bbox_inches="tight", pad_inches=0.02)
    paths["eps"] = eps

    fig.savefig(png, format="png", dpi=DPI_OUT, bbox_inches="tight", pad_inches=0.02)
    paths["png"] = png

    # grayscale TIFF 600dpi LZW
    im = Image.open(png).convert("L")
    im.save(tif, format="TIFF", compression="tiff_lzw", dpi=(DPI_OUT, DPI_OUT))
    paths["tif"] = tif
    with Image.open(tif) as chk:
        paths["tif_meta"] = {
            "mode": chk.mode,
            "size": chk.size,
            "dpi": chk.info.get("dpi"),
        }
    return paths


def main() -> int:
    for d in (OUT_SOURCE, OUT_EPS, OUT_TIF, OUT_PREVIEW):
        d.mkdir(parents=True, exist_ok=True)

    src_self = Path(__file__).resolve()
    archived = OUT_SOURCE / "plot_llm_figures.py"
    if src_self != archived:
        archived.write_text(src_self.read_text(encoding="utf-8"), encoding="utf-8")

    font_info = setup_fonts()
    df = load_exp1()
    sanity_check(df)

    # completeness: ALL must be n=1200; Answer-Critical must be n=480
    expected_n = {"ALL": 1200, "Answer-Critical-Conflict": 480}
    for prov, _ in MODEL_ORDER:
        for cond in CONDITIONS:
            for cat, need in expected_n.items():
                row = df[
                    (df.provider == prov) & (df.condition == cond) & (df.category == cat)
                ]
                n = int(row.iloc[0]["n"]) if not row.empty else -1
                if n != need:
                    print(f"[WARN] expected n={need} for {prov}/{cond}/{cat}, got {n}")

    fig_w = mm_to_inch(DOUBLE_COLUMN_MM)
    fig_h = mm_to_inch(70.0)
    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))

    rec_a = plot_panel(
        axes[0], df, "ALL", font_info, "(a)", annotate_dirty=True
    )
    rec_b = plot_panel(
        axes[1],
        df,
        "Answer-Critical-Conflict",
        font_info,
        "(b)",
        annotate_dirty=True,
    )

    # shared legend inside panel (a) whitespace
    handles, labels = axes[0].get_legend_handles_labels()
    leg = axes[0].legend(
        handles,
        labels,
        loc="lower left",
        bbox_to_anchor=(0.02, 0.02),
        prop=font_info["fp_en"],
        frameon=False,
    )

    fig.tight_layout(w_pad=1.2)
    source = pd.concat([rec_a, rec_b], ignore_index=True)
    csv_path = OUT_SOURCE / "fig4_llm_data_quality.csv"
    source.to_csv(csv_path, index=False)

    paths = save_figure(fig, "fig4_llm_data_quality")
    plt.close(fig)

    print(f"[OK] source CSV → {csv_path}")
    for k, v in paths.items():
        if k != "tif_meta":
            print(f"[OK] {k} → {v}")
        else:
            print(f"[OK] tif_meta → {v}")
    if font_info["warning"]:
        print(font_info["warning"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
