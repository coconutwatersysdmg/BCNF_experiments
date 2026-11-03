"""Phase 14: BCNF use_key_cover True/False must agree with exhaustive."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker, is_subset_repair_bcnf_index
from algorithms.general import is_subset_repair_exhaustive
from generators.conflict_injector import (
    compute_deleted_block_stats,
    make_negative_repair_case,
    make_positive_repair_case,
)
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


@pytest.mark.parametrize("seed", range(500))
def test_key_cover_agrees_with_exhaustive(seed: int) -> None:
    schema = generate_single_key_bcnf(
        n_attrs=7,
        key_width=1,
        fd_count=4,
        seed=seed,
        include_redundant_superkeys=True,
    )
    clean = generate_clean_instance(schema, n=12, seed=seed)
    r_prime = clean[:8]
    if seed % 2 == 0:
        inst = make_positive_repair_case(schema, r_prime, 0.3, seed=seed + 50)
    else:
        inst = make_negative_repair_case(schema, r_prime, 0.25, seed=seed + 50)

    assert len(inst.deleted_rows) <= 15
    oracle = is_subset_repair_exhaustive(schema, inst.r, inst.r_prime, max_deleted=15)
    no_cover = is_subset_repair_bcnf_index(
        schema, inst.r, inst.r_prime, use_key_cover=False, collect_certificates=False
    )
    with_cover = is_subset_repair_bcnf_index(
        schema, inst.r, inst.r_prime, use_key_cover=True, collect_certificates=False
    )
    assert no_cover.is_repair == oracle.is_repair == with_cover.is_repair
    assert (
        no_cover.candidate_consistent
        == oracle.candidate_consistent
        == with_cover.candidate_consistent
    )


def test_certificates_off_by_default() -> None:
    schema = generate_single_key_bcnf(n_attrs=5, key_width=1, fd_count=2, seed=1)
    clean = generate_clean_instance(schema, n=20, seed=1)
    inst = make_positive_repair_case(schema, clean, 0.2, seed=2)
    checker = BCNFRepairChecker(schema)
    res = checker.check(inst.r, inst.r_prime)
    assert res.certificate == {}
    assert res.metadata.get("collect_certificates") is False

    # On-demand witness
    deleted = [t for t in inst.r if t not in set(inst.r_prime)]
    assert deleted
    w = checker.find_conflict_witness(deleted[0])
    assert w is not None
    assert "key" in w and "retained_row" in w


def test_addable_position_order_preserved() -> None:
    schema = generate_single_key_bcnf(n_attrs=5, key_width=1, fd_count=2, seed=3)
    clean = generate_clean_instance(schema, n=30, seed=3)
    inst = make_negative_repair_case(
        schema, clean, conflict_ratio=0.3, seed=4, addable_position=0.9, n_addable=1
    )
    deleted = [t for t in inst.r if t not in set(inst.r_prime)]
    # Addable should be late in deleted order
    pos = int(round(0.9 * (len(deleted) - 1)))
    # The addable is marked with fresh tag
    addable_indices = [
        i for i, t in enumerate(deleted) if any(
            isinstance(v, tuple) and v and v[0] == "fresh" for v in t
        )
    ]
    assert addable_indices
    assert addable_indices[0] >= max(0, pos - 2)


def test_block_distribution_uniform_vs_zipf() -> None:
    schema = generate_single_key_bcnf(n_attrs=6, key_width=1, fd_count=2, seed=7)
    clean = generate_clean_instance(schema, n=500, seed=7)
    u = make_positive_repair_case(
        schema, clean, conflict_ratio=0.2, seed=8, block_distribution="uniform"
    )
    z = make_positive_repair_case(
        schema, clean, conflict_ratio=0.2, seed=8, block_distribution="zipf", zipf_alpha=1.2
    )
    assert u.metadata["max_deleted_block_size"] < z.metadata["max_deleted_block_size"] or (
        u.metadata["mean_deleted_block_size"] != z.metadata["mean_deleted_block_size"]
    )
    # Same total deleted count (approx)
    assert abs(u.metadata["deleted_count"] - z.metadata["deleted_count"]) <= 1
