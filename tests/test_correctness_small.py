"""Small random correctness: exhaustive vs scalable algorithms."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import is_subset_repair_bcnf_index
from algorithms.fd_hash import is_subset_repair_fd_hash
from algorithms.general import is_subset_repair_exhaustive
from algorithms.singleton_fullscan import is_subset_repair_singleton_fullscan
from generators.conflict_injector import make_negative_repair_case, make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_multi_key_bcnf, generate_single_key_bcnf


@pytest.mark.parametrize("seed", range(50))
def test_algorithms_agree_pass_single(seed: int) -> None:
    schema = generate_single_key_bcnf(n_attrs=6, key_width=1, fd_count=3, seed=seed)
    clean = generate_clean_instance(schema, n=12, seed=seed)
    # Keep a small retained set so |D| stays within oracle budget
    r_prime = clean[:8]
    inst = make_positive_repair_case(
        schema, r_prime, conflict_ratio=0.25, seed=seed + 1000, verify_small=True
    )
    assert len(inst.deleted_rows) <= 15
    results = [
        is_subset_repair_exhaustive(schema, inst.r, inst.r_prime, max_deleted=15),
        is_subset_repair_singleton_fullscan(schema, inst.r, inst.r_prime),
        is_subset_repair_fd_hash(schema, inst.r, inst.r_prime),
        is_subset_repair_bcnf_index(schema, inst.r, inst.r_prime),
    ]
    flags = [r.is_repair for r in results]
    assert all(flags), flags
    assert all(r.candidate_consistent for r in results)


@pytest.mark.parametrize("seed", range(50))
def test_algorithms_agree_fail_single(seed: int) -> None:
    schema = generate_single_key_bcnf(n_attrs=6, key_width=2, fd_count=3, seed=seed)
    clean = generate_clean_instance(schema, n=12, seed=seed + 7)
    r_prime = clean[:8]
    inst = make_negative_repair_case(
        schema, r_prime, conflict_ratio=0.2, seed=seed + 2000, addable_position=0.5
    )
    assert len(inst.deleted_rows) <= 15
    results = [
        is_subset_repair_exhaustive(schema, inst.r, inst.r_prime, max_deleted=15),
        is_subset_repair_singleton_fullscan(schema, inst.r, inst.r_prime),
        is_subset_repair_fd_hash(schema, inst.r, inst.r_prime),
        is_subset_repair_bcnf_index(schema, inst.r, inst.r_prime),
    ]
    flags = [r.is_repair for r in results]
    assert not any(flags), flags


def test_multi_key_agreement() -> None:
    schema = generate_multi_key_bcnf(n_attrs=8, n_keys=2, key_width=1)
    clean = generate_clean_instance(schema, n=10, seed=0)
    r_prime = clean[:6]
    pos = make_positive_repair_case(schema, r_prime, conflict_ratio=0.3, seed=1)
    neg = make_negative_repair_case(schema, r_prime, conflict_ratio=0.3, seed=2)
    for inst, expect in ((pos, True), (neg, False)):
        assert len(inst.deleted_rows) <= 15
        vals = [
            is_subset_repair_exhaustive(schema, inst.r, inst.r_prime).is_repair,
            is_subset_repair_singleton_fullscan(schema, inst.r, inst.r_prime).is_repair,
            is_subset_repair_fd_hash(schema, inst.r, inst.r_prime).is_repair,
            is_subset_repair_bcnf_index(schema, inst.r, inst.r_prime).is_repair,
        ]
        assert all(v == expect for v in vals), (expect, vals)
