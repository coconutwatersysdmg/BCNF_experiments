"""Unit tests for BCNFRepairChecker indexing and repair decisions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import (
    BCNFRepairChecker,
    compute_candidate_keys_from_fds,
    greedy_key_cover,
    select_index_keys,
)
from common.types import FD, RelationSchema
from generators.conflict_injector import make_negative_repair_case, make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_multi_key_bcnf, generate_single_key_bcnf


def test_single_key_basic() -> None:
    schema = generate_single_key_bcnf(n_attrs=5, key_width=1, fd_count=2)
    checker = BCNFRepairChecker(schema)
    assert checker.index_count >= 1
    clean = generate_clean_instance(schema, n=20, seed=1)
    inst = make_positive_repair_case(schema, clean, conflict_ratio=0.1, seed=2)
    res = checker.check(inst.r, inst.r_prime)
    assert res.is_repair
    assert res.candidate_consistent


def test_multiple_fds_same_key() -> None:
    schema = generate_single_key_bcnf(n_attrs=8, key_width=1, fd_count=4)
    keys = compute_candidate_keys_from_fds(schema)
    # After minimization, often a single candidate key
    assert any(len(k) == 1 for k in keys)


def test_redundant_superkey_compression() -> None:
    schema = generate_single_key_bcnf(
        n_attrs=7, key_width=1, fd_count=3, include_redundant_superkeys=True
    )
    dedup = select_index_keys(schema, use_key_cover=False)
    covered = select_index_keys(schema, use_key_cover=True)
    assert len(covered) <= len(dedup)
    assert len(covered) >= 1


def test_multiple_candidate_keys() -> None:
    schema = generate_multi_key_bcnf(n_attrs=9, n_keys=3, key_width=1)
    keys = compute_candidate_keys_from_fds(schema)
    assert len(keys) >= 2
    checker = BCNFRepairChecker(schema)
    clean = generate_clean_instance(schema, n=15, seed=3)
    pos = make_positive_repair_case(schema, clean, 0.2, seed=4)
    neg = make_negative_repair_case(schema, clean, 0.2, seed=5)
    assert checker.check(pos.r, pos.r_prime).is_repair
    assert not checker.check(neg.r, neg.r_prime).is_repair


def test_repair_true_false() -> None:
    schema = generate_single_key_bcnf(n_attrs=6, key_width=2, fd_count=2)
    clean = generate_clean_instance(schema, n=30, seed=9)
    pos = make_positive_repair_case(schema, clean, 0.15, seed=10)
    neg = make_negative_repair_case(schema, clean, 0.15, seed=11)
    c = BCNFRepairChecker(schema)
    assert c.check(pos.r, pos.r_prime).is_repair is True
    assert c.check(neg.r, neg.r_prime).is_repair is False
    assert c.check(neg.r, neg.r_prime).addable_tuple is not None


def test_inconsistent_r_prime() -> None:
    schema = generate_single_key_bcnf(n_attrs=5, key_width=1, fd_count=2)
    clean = generate_clean_instance(schema, n=5, seed=1)
    # Duplicate key with different non-key values inside r_prime
    s = clean[0]
    vals = list(s)
    # mutate last attribute
    vals[-1] = (vals[-1], "bad")
    bad = tuple(vals)
    # Same key as s
    r_prime = (s, bad)
    r = r_prime
    checker = BCNFRepairChecker(schema)
    res = checker.check(r, r_prime)
    assert res.candidate_consistent is False
    assert res.is_repair is False


def test_non_bcnf_raises() -> None:
    schema = RelationSchema(
        attributes=("A", "B", "C"),
        fds=(FD(("A",), ("B",)),),
        name="NotBCNF",
    )
    with pytest.raises(ValueError):
        BCNFRepairChecker(schema)


def test_greedy_key_cover_unit() -> None:
    schema = generate_single_key_bcnf(
        n_attrs=6, key_width=1, fd_count=4, include_redundant_superkeys=True
    )
    cands = compute_candidate_keys_from_fds(schema)
    covered = greedy_key_cover(schema, cands)
    assert covered
