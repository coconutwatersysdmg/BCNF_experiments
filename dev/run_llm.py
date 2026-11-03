"""Run LLM QA experiments under multiple evidence conditions."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.io_utils import read_json, read_jsonl, write_csv
from common.reproducibility import snapshot_config
from config import LLM_MAX_TOKENS, LLM_QA_DIR, LLM_TEMPERATURE, RESULTS_DIR
from llm.prompts import build_dirty_fd_messages, build_plain_messages, relation_fd_string


CONDITIONS = (
    "clean",
    "dirty",
    "dirty_fd_prompt",
    "repaired",
    "candidate_repair",
    "checked_repair",
)


def normalize_answer(text: str) -> str:
    s = text.strip()
    s = s.strip("`\"' ")
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    # Numeric normalization
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        if "." in s:
            return str(float(s))
        return str(int(s))
    return s


def answers_equal(pred: str, gold: Any) -> bool:
    p = normalize_answer(pred)
    g = normalize_answer(str(gold))
    if p.lower() == g.lower():
        return True
    # Try numeric compare
    try:
        return float(p) == float(g)
    except Exception:
        return False


def is_conflict(pred: str) -> bool:
    return normalize_answer(pred).upper() == "CONFLICT"


def evidence_for_condition(item: dict[str, Any], condition: str, cand_checked: Optional[dict] = None) -> list[dict]:
    if condition == "clean":
        return item["clean_evidence"]
    if condition == "dirty" or condition == "dirty_fd_prompt":
        return item["dirty_evidence"]
    if condition == "repaired":
        return item["repair_evidence"]
    if condition in ("candidate_repair", "checked_repair"):
        # Fall back to dirty/repair if dedicated relation-level dump unused for this Q
        if condition == "candidate_repair":
            return item.get("candidate_evidence") or item["dirty_evidence"]
        return item.get("checked_evidence") or item["repair_evidence"]
    raise ValueError(condition)


def build_client(args):
    if args.backend == "openai-compatible":
        from llm.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
        )
    if args.backend == "local":
        from llm.local_transformers import LocalTransformersClient

        return LocalTransformersClient(model=args.model)
    raise ValueError(f"Unknown backend: {args.backend}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM QA evaluation")
    parser.add_argument("--backend", choices=["openai-compatible", "local"], default="openai-compatible")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--conditions", nargs="+", default=["clean", "dirty", "dirty_fd_prompt", "repaired"])
    parser.add_argument("--questions", type=Path, default=LLM_QA_DIR / "questions.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "llm.csv")
    parser.add_argument("--dry-run", action="store_true", help="Build prompts only; no API calls")
    args = parser.parse_args()

    snapshot_config(RESULTS_DIR / "llm_config.json", {k: str(v) for k, v in vars(args).items()})

    if not args.questions.exists():
        print(f"Questions file not found: {args.questions}", file=sys.stderr)
        print("Run scripts/generate_llm_data.py first.", file=sys.stderr)
        return 1

    items = read_jsonl(args.questions)
    if args.limit is not None:
        items = items[: args.limit]

    cand_path = LLM_QA_DIR / "candidate_checked_repairs.json"
    cand_checked = read_json(cand_path) if cand_path.exists() else None

    client = None
    if not args.dry_run:
        client = build_client(args)

    rows = []
    for item in items:
        for condition in args.conditions:
            if condition not in CONDITIONS:
                raise ValueError(f"Unsupported condition: {condition}")
            ev = evidence_for_condition(item, condition, cand_checked)
            if condition == "dirty_fd_prompt":
                messages = build_dirty_fd_messages(
                    ev, item["question"], relation_fd_string(item["relation"])
                )
            else:
                messages = build_plain_messages(ev, item["question"])

            expected_conflict = (
                condition == "dirty_fd_prompt"
                and item["category"] == "Answer-Critical-Conflict"
            )
            # Irrelevant conflicts under dirty_fd_prompt also violate F on evidence
            if condition == "dirty_fd_prompt" and item["category"] == "Irrelevant-Conflict":
                expected_conflict = True

            if args.dry_run:
                raw = ""
                latency = 0.0
                pt = None
                ct = None
            else:
                assert client is not None
                resp = client.generate(
                    messages, temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS
                )
                raw = resp.text
                latency = resp.latency_sec
                pt = resp.prompt_tokens
                ct = resp.completion_tokens

            norm = normalize_answer(raw) if raw else ""
            pred_conflict = is_conflict(raw) if raw else False
            if expected_conflict:
                correct = pred_conflict
            else:
                correct = (not pred_conflict) and answers_equal(raw, item["answer"]) if raw else False

            rows.append(
                {
                    "question_id": item["question_id"],
                    "model": args.model,
                    "condition": condition,
                    "category": item["category"],
                    "ground_truth": item["answer"],
                    "raw_answer": raw,
                    "normalized_answer": norm,
                    "correct": correct,
                    "expected_conflict": expected_conflict,
                    "predicted_conflict": pred_conflict,
                    "latency_sec": latency,
                    "prompt_tokens": pt if pt is not None else "",
                    "completion_tokens": ct if ct is not None else "",
                }
            )

    fieldnames = [
        "question_id",
        "model",
        "condition",
        "category",
        "ground_truth",
        "raw_answer",
        "normalized_answer",
        "correct",
        "expected_conflict",
        "predicted_conflict",
        "latency_sec",
        "prompt_tokens",
        "completion_tokens",
    ]
    write_csv(args.out, fieldnames, rows)
    print(f"Wrote {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
