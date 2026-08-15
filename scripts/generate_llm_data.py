"""Generate LLM QA dataset under data/llm_qa/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.io_utils import write_json, write_jsonl
from common.reproducibility import set_global_seed, snapshot_config
from config import LLM_QA_DIR, QA_TARGET_COUNT
from generators.conflict_injector import make_positive_repair_case
from generators.qa_generator import (
    generate_clean_university_db,
    generate_qa_dataset,
    inject_candidate_repair_errors,
    save_university_db,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LLM QA data")
    parser.add_argument("--n-questions", type=int, default=QA_TARGET_COUNT)
    parser.add_argument("--n-students", type=int, default=1000)
    parser.add_argument("--n-courses", type=int, default=100)
    parser.add_argument("--n-enrollments", type=int, default=15000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=LLM_QA_DIR)
    args = parser.parse_args()

    set_global_seed(args.seed)
    snapshot_config(args.out_dir / "generation_config.json", vars(args))

    db = generate_clean_university_db(
        n_students=args.n_students,
        n_courses=args.n_courses,
        n_enrollments=args.n_enrollments,
        seed=args.seed,
    )
    save_university_db(db, args.out_dir / "clean_db")

    questions = generate_qa_dataset(db, n_questions=args.n_questions, seed=args.seed)
    out_q = args.out_dir / "questions.jsonl"
    write_jsonl(out_q, questions)
    print(f"Wrote {out_q} ({len(questions)} questions)")

    # Candidate vs Checked repair artifacts for STUDENT relation
    from generators.qa_generator import student_schema

    schema = student_schema()
    students = db["STUDENT"]["rows"]
    # Build a valid S-repair scenario on STUDENT
    inst = make_positive_repair_case(schema, students, conflict_ratio=0.05, seed=args.seed)
    cand_checked = {}
    for ratio in (0.01, 0.05, 0.10, 0.20):
        cand_checked[str(ratio)] = inject_candidate_repair_errors(
            schema,
            inst.r,
            inst.r_prime,
            error_ratio=ratio,
            seed=args.seed + int(ratio * 1000),
            clean_gt=students,
        )
    write_json(args.out_dir / "candidate_checked_repairs.json", cand_checked)
    print(f"Wrote candidate/checked repairs for ratios {list(cand_checked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
