"""Differential testing: incremental vs static BCNF checker."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.bcnf_index import BCNFRepairChecker
from algorithms.incremental import BCNFRepairState
from generators.conflict_injector import make_positive_repair_case
from generators.instance_generator import generate_clean_instance
from generators.schema_generator import generate_single_key_bcnf


def test_incremental_1000_mixed_updates() -> None:
    seed = 42
    rng = random.Random(seed)
    schema = generate_single_key_bcnf(n_attrs=6, key_width=1, fd_count=3)
    clean = generate_clean_instance(schema, n=40, seed=seed)
    inst = make_positive_repair_case(schema, clean, conflict_ratio=0.2, seed=seed + 1)
    state = BCNFRepairState(schema, inst.r, inst.r_prime)

    # Pool of fresh tuples for add_deleted
    fresh_id = 0

    def make_fresh():
        nonlocal fresh_id
        fresh_id += 1
        values = []
        for a in schema.attributes:
            values.append(("inc", fresh_id, a))
        return tuple(values)

    n_steps = 1000
    for step in range(n_steps):
        op = rng.randrange(4)
        try:
            if op == 0:
                # 25% add_deleted
                t = make_fresh()
                state.add_deleted(t)
            elif op == 1:
                # 25% remove_deleted
                if not state.D:
                    continue
                t = rng.choice(tuple(state.D))
                state.remove_deleted(t)
            elif op == 2:
                # 25% D -> r_prime
                if not state.D:
                    continue
                t = rng.choice(tuple(state.D))
                state.move_deleted_to_retained(t)
            else:
                # 25% r_prime -> D
                if not state.r_prime:
                    continue
                t = rng.choice(tuple(state.r_prime))
                state.move_retained_to_deleted(t)
        except ValueError:
            continue

        static = BCNFRepairChecker(schema)
        static.index_keys = list(state.index_keys)
        res = static.check(list(state.r), list(state.r_prime))
        inc = state.is_repair()
        if not state.candidate_consistent():
            assert not res.candidate_consistent
            assert not res.is_repair
            assert not inc
        else:
            assert res.candidate_consistent
            assert res.is_repair == inc, (
                f"mismatch at step {step}: static={res.is_repair} inc={inc} "
                f"bad={state.bad_block_count} unblocked={state.unblocked_count}"
            )


def test_validate_against_static_helper() -> None:
    schema = generate_single_key_bcnf(n_attrs=5, key_width=1, fd_count=2)
    clean = generate_clean_instance(schema, n=20, seed=7)
    inst = make_positive_repair_case(schema, clean, 0.15, seed=8)
    state = BCNFRepairState(schema, inst.r, inst.r_prime)
    assert state.validate_against_static()
