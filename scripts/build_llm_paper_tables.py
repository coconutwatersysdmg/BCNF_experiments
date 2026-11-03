#!/usr/bin/env python3
"""Build paper tables for LLM Exp2 + Dirty+FD from final summaries.

No API calls. No dataset regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
LLM_FINAL = EXPERIMENTS_ROOT.parent / "llm_study" / "results" / "final"
OUT_DIR = EXPERIMENTS_ROOT / "paper_tables"


def weighted_mean(df: pd.DataFrame, value_col: str, weight_col: str = "n") -> float:
    if df.empty:
        return float("nan")
    w = df[weight_col].astype(float)
    v = df[value_col].astype(float)
    s = w.sum()
    if s <= 0:
        return float("nan")
    return float((v * w).sum() / s)


def build_checker_table() -> pd.DataFrame:
    over = pd.read_csv(LLM_FINAL / "exp2_overdeletion_summary.csv")
    residual = pd.read_csv(LLM_FINAL / "exp2_residual_summary.csv")
    for c in ("accuracy", "unknown_rate", "n", "error_rate"):
        if c in over.columns:
            over[c] = pd.to_numeric(over[c], errors="coerce")
    for c in (
        "checker_detection_rate",
        "unchecked_exposure_rate",
        "checked_exposure_rate",
        "unchecked_affected_accuracy",
        "candidate_count",
        "rejected_count",
        "error_rate",
    ):
        if c in residual.columns:
            residual[c] = pd.to_numeric(residual[c], errors="coerce")

    rows = []
    for provider, model in (
        ("zhipu", "GLM-4-Flash"),
        ("bailian", "Qwen3.7-Flash"),
    ):
        sub = over[over["provider"] == provider]
        # Part A over-deletion
        def pick(condition: str, subset: str, col: str) -> float:
            part = sub[(sub["condition"] == condition) & (sub["subset"] == subset)]
            return weighted_mean(part, col, "n")

        # Part B residual — weight by candidate_count
        rsub = residual[residual["provider"] == provider].copy()
        if "candidate_count" not in rsub.columns or rsub["candidate_count"].isna().all():
            rsub["candidate_count"] = 1.0
        det = weighted_mean(rsub, "checker_detection_rate", "candidate_count")
        uexp = weighted_mean(rsub, "unchecked_exposure_rate", "candidate_count")
        cexp = weighted_mean(rsub, "checked_exposure_rate", "candidate_count")
        uaff = weighted_mean(rsub, "unchecked_affected_accuracy", "candidate_count")

        rows.append(
            {
                "model": model,
                "provider": provider,
                "candidate_affected_accuracy": pick("candidate", "affected", "accuracy"),
                "checked_affected_accuracy": pick("checked", "affected", "accuracy"),
                "candidate_unaffected_accuracy": pick("candidate", "unaffected", "accuracy"),
                "checked_unaffected_accuracy": pick("checked", "unaffected", "accuracy"),
                "candidate_affected_unknown_rate": pick("candidate", "affected", "unknown_rate"),
                "checked_affected_unknown_rate": pick("checked", "affected", "unknown_rate"),
                "checker_detection_rate": det,
                "unchecked_invalid_exposure_rate": uexp,
                "checked_invalid_exposure_rate": cexp,
                "unchecked_affected_qa_accuracy": uaff,
            }
        )
    return pd.DataFrame(rows)


def build_fd_table() -> pd.DataFrame:
    fd = pd.read_csv(LLM_FINAL / "exp1_conflict_summary.csv")
    out = []
    for _, r in fd.iterrows():
        out.append(
            {
                "Model": "GLM-4-Flash" if r["provider"] == "zhipu" else "Qwen3.7-Flash",
                "Conflict Precision": float(r["conflict_precision"]),
                "Conflict Recall": float(r["conflict_recall"]),
                "Conflict F1": float(r["conflict_f1"]),
                "Non-conflict Answer Accuracy": float(r["non_conflict_answer_accuracy"]),
            }
        )
    return pd.DataFrame(out)


def build_statistics_md(
    checker: pd.DataFrame,
    fd: pd.DataFrame,
) -> str:
    exp1 = pd.read_csv(LLM_FINAL / "exp1_summary.csv")
    pair = pd.read_csv(LLM_FINAL / "exp1_pairwise.csv")
    usage = pd.read_csv(LLM_FINAL / "model_usage_summary.csv")
    for c in ("accuracy", "n"):
        exp1[c] = pd.to_numeric(exp1[c], errors="coerce")

    lines = [
        "# LLM Paper Statistics (no interpretation)",
        "",
        "## 1–4. Exp1 paired comparisons",
        "",
    ]
    for _, r in pair.iterrows():
        lines.append(
            f"- {r['provider']} {r['comparison']}: "
            f"acc_a={r['acc_a']} acc_b={r['acc_b']} "
            f"diff={r['diff_a_minus_b']} CI=[{r['ci_low']},{r['ci_high']}] "
            f"McNemar p={r['mcnemar_p']}"
        )

    lines += ["", "## 5. Answer-Critical Dirty accuracy", ""]
    for prov in ("zhipu", "bailian"):
        row = exp1[
            (exp1.provider == prov)
            & (exp1.condition == "dirty")
            & (exp1.category == "Answer-Critical-Conflict")
        ].iloc[0]
        lines.append(f"- {prov}: accuracy={row['accuracy']:.6f} n={int(row['n'])}")

    lines += ["", "## 6. Dirty+FD P/R/F1", ""]
    for _, r in fd.iterrows():
        lines.append(
            f"- {r['Model']}: P={r['Conflict Precision']:.6f} "
            f"R={r['Conflict Recall']:.6f} F1={r['Conflict F1']:.6f} "
            f"non-conflict-acc={r['Non-conflict Answer Accuracy']:.6f}"
        )

    lines += ["", "## 7. Over-deletion Affected Candidate vs Checked", ""]
    for _, r in checker.iterrows():
        lines.append(
            f"- {r['model']}: Candidate-Affected={r['candidate_affected_accuracy']:.6f}, "
            f"Checked-Affected={r['checked_affected_accuracy']:.6f}, "
            f"Candidate-Unaffected={r['candidate_unaffected_accuracy']:.6f}, "
            f"Checked-Unaffected={r['checked_unaffected_accuracy']:.6f}, "
            f"Candidate-Affected-UNKNOWN={r['candidate_affected_unknown_rate']:.6f}, "
            f"Checked-Affected-UNKNOWN={r['checked_affected_unknown_rate']:.6f}"
        )

    lines += ["", "## 8. Residual checker detection / exposure", ""]
    for _, r in checker.iterrows():
        lines.append(
            f"- {r['model']}: detection={r['checker_detection_rate']:.6f}, "
            f"unchecked_exposure={r['unchecked_invalid_exposure_rate']:.6f}, "
            f"checked_exposure={r['checked_invalid_exposure_rate']:.6f}, "
            f"unchecked_affected_qa={r['unchecked_affected_qa_accuracy']:.6f}"
        )

    lines += ["", "## 9. Final API completeness", ""]
    for _, r in usage.iterrows():
        if str(r["file"]).startswith("smoke"):
            continue
        lines.append(
            f"- {r['file']}: requests={r['requests']} success={r['success']} "
            f"failures={r['failures']} retries={r['retries']}"
        )

    lines += ["", "## Exp1 overall (category=ALL, n)", ""]
    for prov in ("zhipu", "bailian"):
        for cond in ("clean", "dirty", "valid_repair"):
            row = exp1[
                (exp1.provider == prov)
                & (exp1.condition == cond)
                & (exp1.category == "ALL")
            ].iloc[0]
            lines.append(
                f"- {prov} {cond}: accuracy={row['accuracy']:.6f} n={int(row['n'])}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checker = build_checker_table()
    fd = build_fd_table()
    checker_path = OUT_DIR / "table_llm_checker.csv"
    fd_path = OUT_DIR / "table_fd_prompt.csv"
    md_path = OUT_DIR / "llm_paper_statistics.md"
    checker.to_csv(checker_path, index=False, float_format="%.6f")
    fd.to_csv(fd_path, index=False, float_format="%.6f")
    md_path.write_text(build_statistics_md(checker, fd), encoding="utf-8")
    print(f"[OK] {checker_path}")
    print(checker.to_string(index=False))
    print(f"[OK] {fd_path}")
    print(fd.to_string(index=False))
    print(f"[OK] {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
