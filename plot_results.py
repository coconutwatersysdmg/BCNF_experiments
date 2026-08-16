"""Plot and summarize experiment CSVs (pandas + matplotlib, no seaborn).

Paper figures (Phase 19):
  Fig_A_static_scalability.pdf
  Fig_B_fd_scaling.pdf
  Fig_C_incremental.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import FINAL_RESULTS_DIR, RESULTS_DIR


def _load_csv(path: Path):
    import pandas as pd

    if not path.exists():
        print(f"[skip] missing {path}")
        return None
    return pd.read_csv(path)


def pd_to_numeric(series):
    import pandas as pd

    return pd.to_numeric(series, errors="coerce")


def plot_fig_a_static(df, out_dir: Path) -> None:
    """Fig A: static scalability — x=|r|, y=runtime (log), Singleton TO marked."""
    import matplotlib.pyplot as plt
    import pandas as pd

    d = df.copy()
    d["timeout"] = d["timeout"].astype(str).str.lower().isin(["true", "1"])
    xcol = "r_size" if "r_size" in d.columns else "n"
    d[xcol] = pd_to_numeric(d[xcol])
    d["total_time_sec"] = pd_to_numeric(d["total_time_sec"])
    # Main plot uses PASS cases when available
    if "case_type" in d.columns:
        d_pass = d[d["case_type"].astype(str).str.lower() == "pass"]
        if not d_pass.empty:
            d = d_pass

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ok = d[~d["timeout"]]
    for algo, g in ok.groupby("algorithm"):
        med = g.groupby(xcol)["total_time_sec"].median()
        ax.plot(med.index, med.values, marker="o", label=algo)

    to = d[d["timeout"]]
    if not to.empty:
        for algo, g in to.groupby("algorithm"):
            xs = sorted(pd_to_numeric(g[xcol]).dropna().unique())
            ymax = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1.0
            # Place TO markers near top of current scale after first draw
            ys = []
            for x in xs:
                base = ok[ok["algorithm"] == algo].groupby(xcol)["total_time_sec"].median()
                ys.append(base.get(x, float("nan")))
            ax.scatter(xs, ys, marker="x", s=90, zorder=5)
            for x, y in zip(xs, ys):
                if y == y:  # not nan
                    ax.annotate("TO", (x, y), textcoords="offset points", xytext=(4, 6), fontsize=8)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("|r|")
    ax.set_ylabel("runtime (sec, median)")
    ax.set_title("Fig A: Static scalability")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_dir / "Fig_A_static_scalability.pdf")
    fig.savefig(out_dir / "Fig_A_static_scalability.png", dpi=150)
    plt.close(fig)


def plot_fig_b_fd_scaling(df, out_dir: Path) -> None:
    """Fig B: actual FD count vs runtime / python peak memory + index counts."""
    import matplotlib.pyplot as plt

    if "experiment" in df.columns:
        sub = df[df["experiment"].astype(str).str.contains("fd", case=False)]
        if sub.empty:
            sub = df
    else:
        sub = df
    fd_col = (
        "actual_nontrivial_fd_count"
        if "actual_nontrivial_fd_count" in sub.columns
        else "fd_count"
    )
    sub = sub.copy()
    sub[fd_col] = pd_to_numeric(sub[fd_col])
    sub["total_time_sec"] = pd_to_numeric(sub["total_time_sec"])
    sub["python_peak_mb"] = pd_to_numeric(sub["python_peak_mb"])

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    ax = axes[0]
    for algo, g in sub.groupby("algorithm"):
        med = g.groupby(fd_col)["total_time_sec"].median()
        ax.plot(med.index, med.values, marker="o", label=algo)
    ax.set_xlabel("actual nontrivial FD count")
    ax.set_ylabel("runtime (sec, median)")
    ax.set_title("FD count vs runtime")
    ax.legend()
    ax.grid(True, ls="--", alpha=0.4)

    ax = axes[1]
    for algo, g in sub.groupby("algorithm"):
        med = g.groupby(fd_col)["python_peak_mb"].median()
        ax.plot(med.index, med.values, marker="o", label=algo)
    # Index compression overlay from BCNF rows
    bcnf = sub[sub["algorithm"] == "BCNF-Index"]
    if not bcnf.empty and "bcnf_index_count" in bcnf.columns:
        raw = bcnf.groupby(fd_col)["raw_fd_index_count"].median() if "raw_fd_index_count" in bcnf.columns else None
        idx = bcnf.groupby(fd_col)["bcnf_index_count"].median()
        ax2 = ax.twinx()
        if raw is not None:
            ax2.plot(raw.index, pd_to_numeric(raw), ls="--", marker="s", color="gray", label="raw FD indexes")
        ax2.plot(idx.index, pd_to_numeric(idx), ls="--", marker="^", color="black", label="BCNF indexes")
        ax2.set_ylabel("index count")
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="best")
    else:
        ax.legend()
    ax.set_xlabel("actual nontrivial FD count")
    ax.set_ylabel("python_peak_mb (median)")
    ax.set_title("FD count vs memory")
    ax.grid(True, ls="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(out_dir / "Fig_B_fd_scaling.pdf")
    fig.savefig(out_dir / "Fig_B_fd_scaling.png", dpi=150)
    plt.close(fig)


def plot_fig_c_incremental(df, out_dir: Path) -> None:
    """Fig C: touched_block_entries vs incremental latency; optional speedup panel."""
    import matplotlib.pyplot as plt

    d = df.copy()
    tcol = (
        "incremental_total_time"
        if "incremental_total_time" in d.columns
        else "incremental_time"
    )
    d[tcol] = pd_to_numeric(d[tcol])
    if "touched_block_entries" not in d.columns:
        print("[skip] Fig C needs touched_block_entries")
        return
    d["touched_block_entries"] = pd_to_numeric(d["touched_block_entries"])
    d["batch_size"] = pd_to_numeric(d["batch_size"])
    if "static_total_time" in d.columns:
        d["static_total_time"] = pd_to_numeric(d["static_total_time"])
        d["speedup"] = d["static_total_time"] / d[tcol]
    elif "speedup" in d.columns:
        d["speedup"] = pd_to_numeric(d["speedup"])

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    ax = axes[0]
    if "block_distribution" in d.columns:
        for dist, g in d.groupby("block_distribution"):
            # scatter subsample for readability
            sample = g.sample(n=min(len(g), 800), random_state=0) if len(g) > 800 else g
            ax.scatter(
                sample["touched_block_entries"],
                sample[tcol],
                s=12,
                alpha=0.45,
                label=str(dist),
            )
    else:
        ax.scatter(d["touched_block_entries"], d[tcol], s=12, alpha=0.45)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("touched_block_entries")
    ax.set_ylabel("incremental latency (sec)")
    ax.set_title("Latency vs touched block entries")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.4)

    ax = axes[1]
    if "speedup" in d.columns:
        group_col = "block_distribution" if "block_distribution" in d.columns else (
            "workload" if "workload" in d.columns else None
        )
        if group_col:
            for key, g in d.groupby(group_col):
                med = g.groupby("batch_size")["speedup"].median()
                ax.plot(med.index, med.values, marker="o", label=str(key))
            ax.legend()
        else:
            med = d.groupby("batch_size")["speedup"].median()
            ax.plot(med.index, med.values, marker="o")
        ax.set_xscale("log")
        ax.set_xlabel("batch size")
        ax.set_ylabel("speedup (static/inc, median)")
        ax.set_title("Batch size vs speedup")
        ax.grid(True, ls="--", alpha=0.4)
    else:
        ax.set_visible(False)

    fig.tight_layout()
    fig.savefig(out_dir / "Fig_C_incremental.pdf")
    fig.savefig(out_dir / "Fig_C_incremental.png", dpi=150)
    plt.close(fig)


# ---- legacy thin wrappers ----


def plot_runtime_vs_n(df, out_dir: Path) -> None:
    plot_fig_a_static(df, out_dir)


def plot_incremental(df, out_dir: Path) -> None:
    plot_fig_c_incremental(df, out_dir)


def plot_sensitivity(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    experiments = list(df["experiment"].unique())
    n = len(experiments)
    fig, axes = plt.subplots(1, n, figsize=(4 * max(n, 1), 3.8), squeeze=False)
    for i, exp in enumerate(experiments):
        ax = axes[0][i]
        sub = df[df["experiment"] == exp]
        for algo, g in sub.groupby("algorithm"):
            med = g.groupby("param_value")["total_time_sec"].median()
            try:
                idx = sorted(med.index, key=lambda x: float(x))
            except Exception:
                idx = list(med.index)
            ax.plot(range(len(idx)), [med[x] for x in idx], marker="o", label=algo)
            ax.set_xticks(range(len(idx)))
            ax.set_xticklabels([str(x) for x in idx], rotation=45, ha="right")
        ax.set_title(str(exp))
        ax.set_ylabel("runtime (sec)")
        ax.legend()
        ax.grid(True, ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_sensitivity.pdf")
    fig.savefig(out_dir / "fig_sensitivity.png", dpi=150)
    plt.close(fig)


def plot_llm(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    cat_col = "question_category" if "question_category" in df.columns else "category"
    sub = df[df["condition"].astype(str).str.contains("dirty", case=False)].copy()
    if sub.empty:
        sub = df.copy()
    if cat_col not in sub.columns:
        return
    cats = sorted(sub[cat_col].astype(str).unique())
    acc = []
    for c in cats:
        g = sub[sub[cat_col].astype(str) == c]
        a = g["correct"].astype(str).str.lower().isin(["true", "1"]).mean()
        acc.append(a)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(len(cats)), acc)
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("QA accuracy")
    ax.set_title("Fig 4/5 style: LLM accuracy by category")
    fig.tight_layout()
    fig.savefig(out_dir / "Fig_D_llm_by_category.pdf")
    fig.savefig(out_dir / "Fig_D_llm_by_category.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot experiment results")
    parser.add_argument("--results-dir", type=Path, default=FINAL_RESULTS_DIR)
    args = parser.parse_args()
    out_dir = args.results_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    static = _load_csv(out_dir / "static.csv")
    if static is not None:
        plot_fig_a_static(static, out_dir)

    sens = _load_csv(out_dir / "sensitivity.csv")
    if sens is not None:
        plot_fig_b_fd_scaling(sens, out_dir)
        plot_sensitivity(sens, out_dir)

    inc = _load_csv(out_dir / "incremental.csv")
    if inc is not None:
        plot_fig_c_incremental(inc, out_dir)

    llm = _load_csv(out_dir / "llm.csv")
    if llm is not None:
        plot_llm(llm, out_dir)

    print(f"Plots written under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
