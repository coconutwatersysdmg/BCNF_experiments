"""Conflict injection for positive (PASS) and negative (FAIL) S-repair cases."""

from __future__ import annotations

import random
from typing import Any, Optional, Sequence

from algorithms.bcnf_index import select_index_keys
from common.fd_utils import project_row, satisfies_fds
from common.types import RelationSchema, RepairInstance, Row


def _mutate_nonkey(
    schema: RelationSchema,
    row: Row,
    key: Sequence[str],
    rng: random.Random,
    tag: Any,
) -> Row:
    """Copy row, keep key projection, change at least one non-key attribute."""
    attr_to_idx = schema.attr_to_idx
    values = list(row)
    key_set = set(key)
    nonkeys = [a for a in schema.attributes if a not in key_set]
    if not nonkeys:
        raise ValueError("cannot mutate: no non-key attributes")
    # Change all nonkeys slightly for a clear conflict under key equality
    for a in nonkeys:
        idx = attr_to_idx[a]
        values[idx] = (values[idx], "conflict", tag)
    new_row = tuple(values)
    if new_row == row:
        # Extremely unlikely; force change on first nonkey
        a = nonkeys[0]
        values[attr_to_idx[a]] = ("forced", tag, rng.randint(0, 10**9))
        new_row = tuple(values)
    return new_row


def _fresh_tuple(
    schema: RelationSchema,
    r_prime: Sequence[Row],
    rng: random.Random,
    tag: Any,
    index_keys: Sequence[tuple[str, ...]],
) -> Row:
    """Create a tuple whose every index-key projection is fresh w.r.t. r_prime."""
    attr_to_idx = schema.attr_to_idx
    occupied: dict[tuple[str, ...], set[tuple[Any, ...]]] = {}
    for k in index_keys:
        occupied[k] = {project_row(s, k, attr_to_idx) for s in r_prime}

    # Start from a template of zeros / placeholders
    values: list[Any] = [0] * len(schema.attributes)
    # Assign unique key values not in occupied
    nonce = rng.randint(10**9, 2 * 10**9)
    for k in index_keys:
        for a in k:
            values[attr_to_idx[a]] = ("fresh", tag, nonce, a)
    # Fill remaining attributes
    key_attrs = {a for k in index_keys for a in k}
    for a in schema.attributes:
        if a not in key_attrs:
            values[attr_to_idx[a]] = ("fresh_val", tag, nonce, a)

    t = tuple(values)
    for k in index_keys:
        kv = project_row(t, k, attr_to_idx)
        if kv in occupied[k]:
            raise RuntimeError("fresh tuple collided unexpectedly")
    return t


def make_positive_repair_case(
    schema: RelationSchema,
    r_prime: Sequence[Row],
    conflict_ratio: float = 0.1,
    seed: int = 42,
    verify_small: bool = False,
    max_deleted_oracle: int = 15,
) -> RepairInstance:
    """PASS case: all injected deleted tuples conflict with r_prime on some key.

    Final r_prime should be an S-repair of r = r_prime ∪ conflicts.
    """
    if not (0.0 <= conflict_ratio <= 1.0):
        raise ValueError("conflict_ratio must be in [0,1]")
    schema.validate_bcnf()
    attr_to_idx = schema.attr_to_idx
    if not satisfies_fds(r_prime, schema.fds, attr_to_idx):
        raise ValueError("r_prime must satisfy F for PASS construction")

    rng = random.Random(seed)
    index_keys = select_index_keys(schema, use_key_cover=True)
    if not index_keys:
        raise ValueError("no index keys available")

    n = len(r_prime)
    n_conflict = int(round(n * conflict_ratio))
    # Ensure at least one conflict when ratio > 0 and n > 0
    if conflict_ratio > 0 and n > 0:
        n_conflict = max(1, n_conflict)

    retained = list(r_prime)
    if n == 0:
        deleted: list[Row] = []
    else:
        targets = rng.sample(retained, k=min(n_conflict, n))
        deleted = []
        for j, s in enumerate(targets):
            k = index_keys[j % len(index_keys)]
            t = _mutate_nonkey(schema, s, k, rng, tag=j)
            # Ensure same key projection
            assert project_row(t, k, attr_to_idx) == project_row(s, k, attr_to_idx)
            assert t != s
            deleted.append(t)

    r = list(retained) + deleted
    # Set semantics
    if len(set(r)) != len(r):
        # Extremely rare collision; retag duplicates
        uniq = []
        seen = set()
        for i, row in enumerate(r):
            if row in seen:
                row = row + ("dupfix", i)  # type: ignore[operator]
                # pad/truncate to schema width — better rebuild last attr
                vals = list(row[: len(schema.attributes)])
                vals[-1] = (vals[-1], "dup", i)
                row = tuple(vals)
            seen.add(row)
            uniq.append(row)
        r = uniq

    inst = RepairInstance(
        schema=schema,
        r=tuple(r),
        r_prime=tuple(retained),
        metadata={
            "case_type": "pass",
            "conflict_ratio": conflict_ratio,
            "seed": seed,
            "deleted_count": len(deleted),
        },
    )

    if verify_small and len(inst.deleted_rows) <= max_deleted_oracle:
        from algorithms.general import is_subset_repair_exhaustive

        res = is_subset_repair_exhaustive(
            schema, inst.r, inst.r_prime, max_deleted=max_deleted_oracle
        )
        if not res.is_repair:
            raise AssertionError("PASS case failed exhaustive oracle")
    return inst


def make_negative_repair_case(
    schema: RelationSchema,
    r_prime: Sequence[Row],
    conflict_ratio: float = 0.1,
    seed: int = 42,
    addable_position: float = 0.9,
    n_addable: int = 1,
) -> RepairInstance:
    """FAIL case: PASS conflicts plus at least one addable fresh tuple.

    addable_position in [0,1] places addable tuples late in deleted iteration
    order (default 0.9) so fail benchmarks are not dominated by early exit.
    """
    if not (0.0 <= addable_position <= 1.0):
        raise ValueError("addable_position must be in [0,1]")
    rng = random.Random(seed)
    base = make_positive_repair_case(
        schema, r_prime, conflict_ratio=conflict_ratio, seed=seed, verify_small=False
    )
    index_keys = select_index_keys(schema, use_key_cover=True)
    retained = list(base.r_prime)
    deleted = list(base.deleted_rows)

    addables: list[Row] = []
    for j in range(n_addable):
        t_new = _fresh_tuple(schema, retained, rng, tag=("addable", j), index_keys=index_keys)
        # Confirm addable under F
        if not satisfies_fds(retained + [t_new], schema.fds, schema.attr_to_idx):
            raise RuntimeError("constructed addable tuple unexpectedly violates F")
        addables.append(t_new)

    # Place addables at desired position in deleted list
    if not deleted:
        deleted = list(addables)
    else:
        insert_at = int(round(addable_position * len(deleted)))
        insert_at = min(max(insert_at, 0), len(deleted))
        deleted = deleted[:insert_at] + addables + deleted[insert_at:]

    r = retained + deleted
    return RepairInstance(
        schema=schema,
        r=tuple(r),
        r_prime=tuple(retained),
        metadata={
            "case_type": "fail",
            "conflict_ratio": conflict_ratio,
            "seed": seed,
            "addable_position": addable_position,
            "deleted_count": len(deleted),
            "n_addable": n_addable,
        },
    )
