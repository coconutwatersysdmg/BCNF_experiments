"""Plot and summarize experiment CSVs (pandas + matplotlib, no seaborn)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import RESULTS_DIR


def _load_csv(path: Path):
    import pandas as pd

    if not path.exists():
        print(f"[skip] missing {path}")
        return None
    return pd.read_csv(path)


def plot_runtime_vs_n(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    d = df[df["timeout"].astype(str).str.lower().isin(["false", "0"])].copy()
    if d.empty:
        return
    d["total_time_sec"] = pd_to_numeric(d["total_time_sec"])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for algo, g in d.groupby("algorithm"):
        med = g.groupby("n")["total_time_sec"].median()
        ax.plot(med.index, med.values, marker="o", label=algo)
    # Mark timeouts
    tdf = df[df["timeout"].astype(str).str.lower().isin(["true", "1"])]
    if not tdf.empty:
        for algo, g in tdf.groupby("algorithm"):
            xs = sorted(g["n"].unique())
            ax.scatter(xs, [d[d["algorithm"] == algo].groupby("n")["total_time_sec"].median().get(x, float("nan")) for x in xs],
                       marker="x", s=80, label=f"{algo} timeout")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n")
    ax.set_ylabel("runtime (sec, median)")
    ax.set_title("Runtime vs n")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_runtime_vs_n.pdf")
    fig.savefig(out_dir / "fig_runtime_vs_n.png", dpi=150)
    plt.close(fig)


def plot_memory_vs_n(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    d = df.copy()
    d["python_peak_mb"] = pd_to_numeric(d.get("python_peak_mb", d.get("peak_memory_mb")))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for algo, g in d.groupby("algorithm"):
        med = g.groupby("n")["python_peak_mb"].median()
        ax.plot(med.index, med.values, marker="o", label=algo)
    ax.set_xscale("log")
    ax.set_xlabel("n")
    ax.set_ylabel("python_peak_mb (median)")
    ax.set_title("Memory vs n")
    ax.legend()
    ax.grid(True, ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_memory_vs_n.pdf")
    fig.savefig(out_dir / "fig_memory_vs_n.png", dpi=150)
    plt.close(fig)


def plot_sensitivity(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    experiments = df["experiment"].unique()
    n = len(experiments)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3.8), squeeze=False)
    for i, exp in enumerate(experiments):
        ax = axes[0][i]
        sub = df[df["experiment"] == exp]
        for algo, g in sub.groupby("algorithm"):
            med = g.groupby("param_value")["total_time_sec"].median()
            # sort param values if numeric
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


def plot_incremental(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for metric, label in (
        ("incremental_time", "incremental"),
        ("static_rebuild_time", "static rebuild"),
    ):
        med = df.groupby("batch_size")[metric].median()
        ax.plot(med.index, med.values, marker="o", label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("batch size")
    ax.set_ylabel("time (sec, median)")
    ax.set_title("Incremental vs static rebuild")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_incremental.pdf")
    fig.savefig(out_dir / "fig_incremental.png", dpi=150)
    plt.close(fig)


def plot_llm(df, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    # Conflict metrics by category under dirty_fd_prompt
    sub = df[df["condition"] == "dirty_fd_prompt"].copy()
    if sub.empty:
        return
    cats = sorted(sub["category"].unique())
    prec, rec, f1, acc = [], [], [], []
    for c in cats:
        g = sub[sub["category"] == c]
        tp = ((g["expected_conflict"] == True) & (g["predicted_conflict"] == True)).sum()  # noqa: E712
        fp = ((g["expected_conflict"] == False) & (g["predicted_conflict"] == True)).sum()  # noqa: E712
        fn = ((g["expected_conflict"] == True) & (g["predicted_conflict"] == False)).sum()  # noqa: E712
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        a = g["correct"].astype(str).str.lower().isin(["true", "1"]).mean()
        prec.append(p)
        rec.append(r)
        f1.append(f)
        acc.append(a)
    x = range(len(cats))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    w = 0.2
    ax.bar([i - 1.5 * w for i in x], acc, width=w, label="QA Acc")
    ax.bar([i - 0.5 * w for i in x], prec, width=w, label="Conflict P")
    ax.bar([i + 0.5 * w for i in x], rec, width=w, label="Conflict R")
    ax.bar([i + 1.5 * w for i in x], f1, width=w, label="Conflict F1")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_title("LLM metrics by category (dirty_fd_prompt)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_llm_conflict_ratio.pdf")
    fig.savefig(out_dir / "fig_llm_conflict_ratio.png", dpi=150)
    plt.close(fig)


def pd_to_numeric(series):
    import pandas as pd

    return pd.to_numeric(series, errors="coerce")


def table_algorithm_summary(df, out_dir: Path) -> None:
    import pandas as pd

    d = df[df["timeout"].astype(str).str.lower().isin(["false", "0"])].copy()
    d["total_time_sec"] = pd_to_numeric(d["total_time_sec"])
    g = (
        d.groupby(["algorithm", "case_type", "n"])
        .agg(
            median_time=("total_time_sec", "median"),
            mean_time=("total_time_sec", "mean"),
            std_time=("total_time_sec", "std"),
        )
        .reset_index()
    )
    g.to_csv(out_dir / "table_algorithm_summary.csv", index=False)


def table_llm_summary(df, out_dir: Path) -> None:
    rows = []
    for (model, condition, category), g in df.groupby(["model", "condition", "category"]):
        acc = g["correct"].astype(str).str.lower().isin(["true", "1"]).mean()
        exp = g["expected_conflict"].astype(str).str.lower().isin(["true", "1"])
        pred = g["predicted_conflict"].astype(str).str.lower().isin(["true", "1"])
        tp = ((exp) & (pred)).sum()
        fp = ((~exp) & (pred)).sum()
        fn = ((exp) & (~pred)).sum()
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        rows.append(
            {
                "model": model,
                "condition": condition,
                "category": category,
                "qa_accuracy": acc,
                "conflict_precision": p,
                "conflict_recall": r,
                "conflict_f1": f,
            }
        )
    import pandas as pd

    pd.DataFrame(rows).to_csv(out_dir / "table_llm_summary.csv", index=False)


def table_candidate_checked(path: Path, out_dir: Path) -> None:
    import json

    import pandas as pd

    if not path.exists():
        return
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for ratio, payload in obj.items():
        rows.append(
            {
                "error_ratio": ratio,
                "candidate_validity": payload["candidate"]["is_repair"],
                "checked_validity": payload["checked"]["is_repair"],
                "candidate_consistent": payload["candidate"]["candidate_consistent"],
                "checked_consistent": payload["checked"]["candidate_consistent"],
            }
        )
    pd.DataFrame(rows).to_csv(out_dir / "table_candidate_checked.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot experiment results")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    out_dir = args.results_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    static = _load_csv(out_dir / "static.csv")
    if static is not None:
        plot_runtime_vs_n(static, out_dir)
        plot_memory_vs_n(static, out_dir)
        table_algorithm_summary(static, out_dir)

    sens = _load_csv(out_dir / "sensitivity.csv")
    if sens is not None:
        plot_sensitivity(sens, out_dir)

    inc = _load_csv(out_dir / "incremental.csv")
    if inc is not None:
        plot_incremental(inc, out_dir)

    llm = _load_csv(out_dir / "llm.csv")
    if llm is not None:
        plot_llm(llm, out_dir)
        table_llm_summary(llm, out_dir)

    from config import LLM_QA_DIR

    table_candidate_checked(LLM_QA_DIR / "candidate_checked_repairs.json", out_dir)
    print(f"Plots/tables written under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
