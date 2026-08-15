"""Singleton-FullScan: scalable naive FD baseline using c=1.

Uses the FD candidate-extension singleton property: if any non-empty A ⊆ D
can be added while preserving F, then some singleton {t} ⊆ A can also be
added. This is an FD property (not BCNF-specific).

Does NOT use BCNF-specialized indexes; each candidate re-runs full FD checks.
"""

from __future__ import annotations

import time
from typing import Sequence

from common.fd_utils import satisfies_fds
from common.types import RelationSchema, RepairCheckResult, Row, ensure_subset


def is_subset_repair_singleton_fullscan(
    schema: RelationSchema,
    r: Sequence[Row],
    r_prime: Sequence[Row],
) -> RepairCheckResult:
    """Check S-repair by testing each deleted tuple alone against full F."""
    t0 = time.perf_counter()
    ensure_subset(r, r_prime)
    attr_to_idx = schema.attr_to_idx
    fds = schema.fds

    if not satisfies_fds(r_prime, fds, attr_to_idx):
        total = time.perf_counter() - t0
        return RepairCheckResult(
            is_repair=False,
            candidate_consistent=False,
            check_time_sec=total,
            total_time_sec=total,
            metadata={"algorithm": "Singleton-FullScan", "reason": "r_prime_inconsistent"},
        )

    r_prime_list = list(r_prime)
    d = frozenset(r) - frozenset(r_prime)
    t_check0 = time.perf_counter()
    for t in d:
        candidate = r_prime_list + [t]
        if satisfies_fds(candidate, fds, attr_to_idx):
            check_t = time.perf_counter() - t_check0
            total = time.perf_counter() - t0
            return RepairCheckResult(
                is_repair=False,
                candidate_consistent=True,
                addable_tuple=t,
                witness_addable_subset=(t,),
                check_time_sec=check_t,
                total_time_sec=total,
                metadata={"algorithm": "Singleton-FullScan"},
            )

    check_t = time.perf_counter() - t_check0
    total = time.perf_counter() - t0
    return RepairCheckResult(
        is_repair=True,
        candidate_consistent=True,
        check_time_sec=check_t,
        total_time_sec=total,
        metadata={"algorithm": "Singleton-FullScan", "deleted_count": len(d)},
    )
