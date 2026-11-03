"""Prompt templates for structured DB QA (identical across models)."""

from __future__ import annotations

import json
from typing import Any, Sequence


SYSTEM_PLAIN = (
    "你是结构化数据库问答助手。只能依据给出的数据库记录回答问题。"
    "若记录无法支持唯一答案，输出 UNKNOWN。只输出最终答案，不解释。"
)

SYSTEM_DIRTY_FD = (
    "你是结构化数据库问答助手。只能依据给出的数据库记录回答问题。"
    "给定关系模式满足指定函数依赖。如果当前证据违反给定函数依赖，输出 CONFLICT；"
    "否则回答问题。只输出 CONFLICT 或最终答案，不解释。"
)


def format_evidence(evidence: Sequence[dict[str, Any]]) -> str:
    return json.dumps(list(evidence), ensure_ascii=False, indent=2)


def format_fd(fd_text: str) -> str:
    return fd_text


def build_plain_messages(evidence: Sequence[dict[str, Any]], question: str) -> list[dict[str, str]]:
    user = f"数据库记录：\n{format_evidence(evidence)}\n\n问题：\n{question}"
    return [
        {"role": "system", "content": SYSTEM_PLAIN},
        {"role": "user", "content": user},
    ]


def build_dirty_fd_messages(
    evidence: Sequence[dict[str, Any]],
    question: str,
    fd: str,
) -> list[dict[str, str]]:
    user = (
        f"函数依赖：\n{fd}\n\n"
        f"数据库记录：\n{format_evidence(evidence)}\n\n"
        f"问题：\n{question}"
    )
    return [
        {"role": "system", "content": SYSTEM_DIRTY_FD},
        {"role": "user", "content": user},
    ]


def relation_fd_string(relation: str) -> str:
    mapping = {
        "STUDENT": "student_id -> name, major, grade_level",
        "COURSE": "course_id -> course_name, credits, department",
        "ENROLLMENT": "student_id, course_id -> score",
    }
    return mapping[relation]
