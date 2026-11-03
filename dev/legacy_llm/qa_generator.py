"""LLM QA dataset generator for BCNF STUDENT / COURSE / ENROLLMENT relations."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from algorithms.bcnf_index import BCNFRepairChecker
from common.fd_utils import project_row, satisfies_fds, validate_bcnf
from common.io_utils import ensure_dir, write_json, write_jsonl
from common.types import FD, RelationSchema, Row


def student_schema() -> RelationSchema:
    s = RelationSchema(
        attributes=("student_id", "name", "major", "grade_level"),
        fds=(FD(("student_id",), ("name", "major", "grade_level")),),
        candidate_keys=(("student_id",),),
        name="STUDENT",
    )
    assert validate_bcnf(s.U, s.fds)
    s.validate_bcnf()
    return s


def course_schema() -> RelationSchema:
    s = RelationSchema(
        attributes=("course_id", "course_name", "credits", "department"),
        fds=(FD(("course_id",), ("course_name", "credits", "department")),),
        candidate_keys=(("course_id",),),
        name="COURSE",
    )
    assert validate_bcnf(s.U, s.fds)
    s.validate_bcnf()
    return s


def enrollment_schema() -> RelationSchema:
    s = RelationSchema(
        attributes=("student_id", "course_id", "score"),
        fds=(FD(("student_id", "course_id"), ("score",)),),
        candidate_keys=(("student_id", "course_id"),),
        name="ENROLLMENT",
    )
    assert validate_bcnf(s.U, s.fds)
    s.validate_bcnf()
    return s


MAJORS = ("Computer Science", "Mathematics", "Physics", "Chemistry", "Economics")
GRADE_LEVELS = ("Freshman", "Sophomore", "Junior", "Senior")
DEPARTMENTS = ("CS", "MATH", "PHYS", "CHEM", "ECON")
COURSE_NAMES = (
    "Intro Programming",
    "Data Structures",
    "Databases",
    "Algorithms",
    "Linear Algebra",
    "Probability",
    "Operating Systems",
    "Networks",
    "AI Foundations",
    "Discrete Math",
)


def generate_clean_university_db(
    n_students: int = 1000,
    n_courses: int = 100,
    n_enrollments: int = 15000,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate clean BCNF university relations."""
    rng = random.Random(seed)
    stud_s = student_schema()
    cour_s = course_schema()
    enr_s = enrollment_schema()

    students: list[Row] = []
    for i in range(n_students):
        sid = f"S{i:04d}"
        students.append(
            (
                sid,
                f"Student_{i}",
                MAJORS[i % len(MAJORS)],
                GRADE_LEVELS[i % len(GRADE_LEVELS)],
            )
        )

    courses: list[Row] = []
    for j in range(n_courses):
        cid = f"C{j:03d}"
        courses.append(
            (
                cid,
                COURSE_NAMES[j % len(COURSE_NAMES)] + f"_{j}",
                2 + (j % 4),
                DEPARTMENTS[j % len(DEPARTMENTS)],
            )
        )

    enrollments: list[Row] = []
    seen = set()
    # Deterministic enrollments without rejection explosion
    target = min(n_enrollments, n_students * min(8, n_courses))
    k = 0
    for i in range(n_students):
        # each student takes a few courses
        n_take = 3 + (i % 6)
        for t in range(n_take):
            j = (i * 7 + t * 13) % n_courses
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            sid = f"S{i:04d}"
            cid = f"C{j:03d}"
            score = 50 + ((i * 17 + j * 31) % 51)
            enrollments.append((sid, cid, score))
            k += 1
            if k >= target:
                break
        if k >= target:
            break

    assert satisfies_fds(students, stud_s.fds, stud_s.attr_to_idx)
    assert satisfies_fds(courses, cour_s.fds, cour_s.attr_to_idx)
    assert satisfies_fds(enrollments, enr_s.fds, enr_s.attr_to_idx)

    return {
        "STUDENT": {"schema": stud_s, "rows": students},
        "COURSE": {"schema": cour_s, "rows": courses},
        "ENROLLMENT": {"schema": enr_s, "rows": enrollments},
        "meta": {
            "n_students": len(students),
            "n_courses": len(courses),
            "n_enrollments": len(enrollments),
            "seed": seed,
        },
    }


def _row_dict(schema: RelationSchema, row: Row) -> dict[str, Any]:
    return {a: row[i] for i, a in enumerate(schema.attributes)}


def _lookup(schema: RelationSchema, rows: Sequence[Row], key_attrs: Sequence[str], key_vals: Sequence[Any]) -> Optional[Row]:
    attr_to_idx = schema.attr_to_idx
    for row in rows:
        if all(row[attr_to_idx[a]] == v for a, v in zip(key_attrs, key_vals)):
            return row
    return None


QUESTION_TEMPLATES = [
    {
        "relation": "STUDENT",
        "template": "学生 {student_id} 的专业是什么？",
        "query_key": ("student_id",),
        "answer_attr": "major",
    },
    {
        "relation": "STUDENT",
        "template": "学生 {student_id} 的年级是什么？",
        "query_key": ("student_id",),
        "answer_attr": "grade_level",
    },
    {
        "relation": "COURSE",
        "template": "课程 {course_id} 的学分是多少？",
        "query_key": ("course_id",),
        "answer_attr": "credits",
    },
    {
        "relation": "COURSE",
        "template": "课程 {course_id} 由哪个院系开设？",
        "query_key": ("course_id",),
        "answer_attr": "department",
    },
    {
        "relation": "ENROLLMENT",
        "template": "学生 {student_id} 在课程 {course_id} 的成绩是多少？",
        "query_key": ("student_id", "course_id"),
        "answer_attr": "score",
    },
]


def _inject_conflict_on_key(
    schema: RelationSchema,
    clean_row: Row,
    rng: random.Random,
    tag: str,
) -> Row:
    """Create a conflicting tuple sharing the candidate key, differing elsewhere."""
    key = schema.candidate_keys[0]
    values = list(clean_row)
    key_set = set(key)
    for a in schema.attributes:
        if a not in key_set:
            idx = schema.attr_to_idx[a]
            values[idx] = (values[idx], "dirty", tag, rng.randint(0, 10**6))
    return tuple(values)


@dataclass
class QAItem:
    question_id: str
    question: str
    relation: str
    query_key: dict[str, Any]
    answer: Any
    category: str
    clean_evidence: list[dict[str, Any]]
    dirty_evidence: list[dict[str, Any]]
    repair_evidence: list[dict[str, Any]]
    metadata: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "relation": self.relation,
            "query_key": self.query_key,
            "answer": self.answer,
            "category": self.category,
            "clean_evidence": self.clean_evidence,
            "dirty_evidence": self.dirty_evidence,
            "repair_evidence": self.repair_evidence,
            "metadata": self.metadata,
        }


def generate_qa_dataset(
    db: dict[str, Any],
    n_questions: int = 900,
    seed: int = 42,
    ratios: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Generate QA items with No-Conflict / Irrelevant-Conflict / Answer-Critical-Conflict."""
    if ratios is None:
        ratios = {
            "No-Conflict": 0.30,
            "Irrelevant-Conflict": 0.30,
            "Answer-Critical-Conflict": 0.40,
        }
    rng = random.Random(seed)
    n_no = int(round(n_questions * ratios["No-Conflict"]))
    n_irr = int(round(n_questions * ratios["Irrelevant-Conflict"]))
    n_crit = n_questions - n_no - n_irr

    items: list[QAItem] = []
    qid = 0

    def next_template():
        return QUESTION_TEMPLATES[qid % len(QUESTION_TEMPLATES)]

    def sample_entity(tmpl):
        rel = tmpl["relation"]
        schema: RelationSchema = db[rel]["schema"]
        rows: list[Row] = db[rel]["rows"]
        row = rng.choice(rows)
        key = tmpl["query_key"]
        key_vals = {a: row[schema.attr_to_idx[a]] for a in key}
        answer = row[schema.attr_to_idx[tmpl["answer_attr"]]]
        question = tmpl["template"].format(**key_vals)
        return schema, rows, row, key_vals, answer, question

    def make_item(category: str):
        nonlocal qid
        tmpl = next_template()
        schema, rows, row, key_vals, answer, question = sample_entity(tmpl)
        clean_ev = [_row_dict(schema, row)]

        if category == "No-Conflict":
            dirty_ev = list(clean_ev)
            repair_ev = list(clean_ev)
            meta = {"conflict": False}
        elif category == "Irrelevant-Conflict":
            # Conflict on a different key, not answering this question
            other = rng.choice(rows)
            # Ensure different key
            tries = 0
            while other == row and tries < 10:
                other = rng.choice(rows)
                tries += 1
            dirty_other = _inject_conflict_on_key(schema, other, rng, f"irr{qid}")
            dirty_ev = clean_ev + [_row_dict(schema, other), _row_dict(schema, dirty_other)]
            # Repair keeps clean answer row; drops the dirty duplicate of other
            repair_ev = clean_ev + [_row_dict(schema, other)]
            meta = {
                "conflict": True,
                "conflict_relevant_to_answer": False,
                "conflict_key": _row_dict(schema, other),
            }
        else:
            # Answer-Critical-Conflict: conflict on the queried key
            dirty = _inject_conflict_on_key(schema, row, rng, f"crit{qid}")
            dirty_ev = [_row_dict(schema, row), _row_dict(schema, dirty)]
            repair_ev = [_row_dict(schema, row)]  # keep clean choice
            meta = {
                "conflict": True,
                "conflict_relevant_to_answer": True,
                "expected_conflict_token": "CONFLICT",
            }

        item = QAItem(
            question_id=f"Q{qid:04d}",
            question=question,
            relation=tmpl["relation"],
            query_key=key_vals,
            answer=answer,
            category=category,
            clean_evidence=clean_ev,
            dirty_evidence=dirty_ev,
            repair_evidence=repair_ev,
            metadata=meta,
        )
        qid += 1
        items.append(item)

    for _ in range(n_no):
        make_item("No-Conflict")
    for _ in range(n_irr):
        make_item("Irrelevant-Conflict")
    for _ in range(n_crit):
        make_item("Answer-Critical-Conflict")

    rng.shuffle(items)
    return [it.to_json() for it in items]


def complete_by_checker(
    schema: RelationSchema,
    r: Sequence[Row],
    r_prime: Sequence[Row],
    max_iters: int = 1000,
) -> dict[str, Any]:
    """Restore S-repair maximality for over-deletion candidates.

    Does NOT resolve residual conflicts (cannot choose real-world truth).
    If candidate_consistent=False, stops immediately (gate path).
    """
    checker = BCNFRepairChecker(schema, use_key_cover=False)
    current = set(r_prime)
    universe = set(r)
    added: list[Row] = []
    iterations = 0
    last = None
    for iterations in range(1, max_iters + 1):
        last = checker.check(
            list(universe), list(current), collect_certificates=False
        )
        if not last.candidate_consistent:
            return {
                "r_prime": list(current),
                "final_is_repair": False,
                "candidate_consistent": False,
                "checker_rejected": True,
                "number_of_checker_iterations": iterations,
                "added_back_count": len(added),
                "added_back": added,
            }
        if last.is_repair:
            return {
                "r_prime": list(current),
                "final_is_repair": True,
                "candidate_consistent": True,
                "checker_rejected": False,
                "number_of_checker_iterations": iterations,
                "added_back_count": len(added),
                "added_back": added,
            }
        if last.addable_tuple is None:
            break
        current.add(last.addable_tuple)
        added.append(last.addable_tuple)
    return {
        "r_prime": list(current),
        "final_is_repair": bool(last.is_repair) if last else False,
        "candidate_consistent": bool(last.candidate_consistent) if last else False,
        "checker_rejected": bool(last and not last.candidate_consistent),
        "number_of_checker_iterations": iterations,
        "added_back_count": len(added),
        "added_back": added,
    }


def inject_candidate_repair_errors(
    schema: RelationSchema,
    r: Sequence[Row],
    r_prime: Sequence[Row],
    error_ratio: float,
    seed: int,
    clean_gt: Sequence[Row],
    error_type: str = "mixed",
) -> dict[str, Any]:
    """Inject residual_conflict and/or over_deletion into a valid S-repair.

    clean_gt is used ONLY to choose which tuples to over-delete for the
    experiment design (prefer answer-critical clean rows). It is NEVER used
    by the checker to pick a 'true' residual conflict survivor.

    error_type:
      - over_deletion: only over-delete; checked path uses complete_by_checker
      - residual_conflict: only inject conflicting twins; checked path = gate reject
      - mixed: both (legacy artifact generation)
    """
    rng = random.Random(seed)
    r_set = set(r)
    cand = list(r_prime)
    D = list(r_set - set(cand))

    n_err = max(1, int(round(len(cand) * error_ratio))) if cand else 0
    if error_type == "over_deletion":
        n_residual, n_over = 0, n_err
    elif error_type == "residual_conflict":
        n_residual, n_over = n_err, 0
    else:
        n_residual = n_err // 2
        n_over = n_err - n_residual

    residual_injected: list[Row] = []
    over_deleted: list[Row] = []

    # residual_conflict: keep two conflicting tuples in candidate
    for i in range(n_residual):
        if not cand:
            break
        s = rng.choice(cand)
        twin = _inject_conflict_on_key(schema, s, rng, f"resid{i}")
        cand.append(twin)
        r_set.add(twin)
        residual_injected.append(twin)

    # over_deletion: remove a keepable tuple from candidate into D
    clean_set = set(clean_gt)
    for _i in range(n_over):
        keepable = [t for t in cand if t in clean_set]
        if not keepable:
            if len(cand) <= 1:
                break
            keepable = list(cand)
        t = rng.choice(keepable)
        cand.remove(t)
        D.append(t)
        over_deleted.append(t)

    candidate_r = tuple(r_set)
    candidate_rp = tuple(cand)

    checker = BCNFRepairChecker(schema, use_key_cover=False)
    check_res = checker.check(
        candidate_r, candidate_rp, collect_certificates=False
    )

    # Checked path depends on error type — never use clean GT to resolve conflicts
    if residual_injected and not check_res.candidate_consistent:
        # Gate only: reject inconsistent candidate; do not invent truth
        checked = {
            "r": list(candidate_r),
            "r_prime": list(candidate_rp),
            "is_repair": False,
            "candidate_consistent": False,
            "checker_rejected": True,
            "number_of_checker_iterations": 1,
            "added_back_count": 0,
        }
    elif over_deleted:
        completion = complete_by_checker(schema, candidate_r, candidate_rp)
        checked = {
            "r": list(candidate_r),
            "r_prime": completion["r_prime"],
            "is_repair": completion["final_is_repair"],
            "candidate_consistent": completion["candidate_consistent"],
            "checker_rejected": completion["checker_rejected"],
            "number_of_checker_iterations": completion["number_of_checker_iterations"],
            "added_back_count": completion["added_back_count"],
        }
    else:
        checked = {
            "r": list(candidate_r),
            "r_prime": list(candidate_rp),
            "is_repair": check_res.is_repair,
            "candidate_consistent": check_res.candidate_consistent,
            "checker_rejected": False,
            "number_of_checker_iterations": 1,
            "added_back_count": 0,
        }

    return {
        "candidate": {
            "r": list(candidate_r),
            "r_prime": list(candidate_rp),
            "is_repair": check_res.is_repair,
            "candidate_consistent": check_res.candidate_consistent,
        },
        "checked": checked,
        "errors": {
            "error_ratio": error_ratio,
            "error_type": error_type,
            "residual_injected": len(residual_injected),
            "over_deleted": len(over_deleted),
        },
        "checker_view": {
            "saw_consistent_candidate": check_res.candidate_consistent,
            "saw_is_repair": check_res.is_repair,
            "addable_tuple": list(check_res.addable_tuple) if check_res.addable_tuple else None,
        },
    }


def save_university_db(db: dict[str, Any], out_dir: Path) -> None:
    ensure_dir(out_dir)
    for rel in ("STUDENT", "COURSE", "ENROLLMENT"):
        schema: RelationSchema = db[rel]["schema"]
        rows: list[Row] = db[rel]["rows"]
        write_json(out_dir / f"{rel.lower()}_schema.json", schema.to_json())
        with (out_dir / f"{rel.lower()}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(_row_dict(schema, row), ensure_ascii=False) + "\n")
    write_json(out_dir / "meta.json", db["meta"])
