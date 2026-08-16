"""Conflict injection for positive (PASS) and negative (FAIL) S-repair cases."""

from __future__ import annotations

import math
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


def _allocate_counts(
    d: int,
    B: int,
    distribution: str,
    zipf_alpha: float,
) -> list[int]:
    """Allocate d deleted conflicts across B active blocks (each >= 1 when d >= B)."""
    if d <= 0 or B <= 0:
        return []
    B = min(B, d)
    if distribution == "uniform":
        base = d // B
        rem = d % B
        return [base + (1 if i < rem else 0) for i in range(B)]

    # Zipf: weight_i ∝ 1 / (i+1)^alpha
    weights = [1.0 / ((i + 1) ** zipf_alpha) for i in range(B)]
    total_w = sum(weights)
    # Ensure each active block gets ≥1, then distribute remainder by Zipf
    counts = [1] * B
    rem = d - B
    if rem > 0:
        # Proportional allocation of remainder
        raw = [rem * (w / total_w) for w in weights]
        extras = [int(math.floor(x)) for x in raw]
        leftover = rem - sum(extras)
        order = sorted(range(B), key=lambda i: -(raw[i] - extras[i]))
        for i in range(leftover):
            extras[order[i]] += 1
        counts = [1 + extras[i] for i in range(B)]
    return counts


def compute_deleted_block_stats(
    schema: RelationSchema,
    r_prime: Sequence[Row],
    deleted: Sequence[Row],
    index_keys: Optional[Sequence[tuple[str, ...]]] = None,
) -> dict[str, Any]:
    """Statistics of deleted conflict block sizes |G_K(v)| under primary index key.

    Uses index_keys[0] (paper single-key experiments); for multi-key schemas the
    first selected candidate key defines the reported block distribution.
    """
    if index_keys is None:
        index_keys = select_index_keys(schema, use_key_cover=False)
    if not index_keys:
        return {
            "active_block_count": 0,
            "mean_deleted_block_size": 0.0,
            "median_deleted_block_size": 0.0,
            "p95_deleted_block_size": 0.0,
            "p99_deleted_block_size": 0.0,
            "max_deleted_block_size": 0,
        }
    k = index_keys[0]
    attr_to_idx = schema.attr_to_idx
    retained_vals = {project_row(s, k, attr_to_idx) for s in r_prime}
    sizes: dict[tuple[Any, ...], int] = {}
    for t in deleted:
        kv = project_row(t, k, attr_to_idx)
        if kv in retained_vals:
            sizes[kv] = sizes.get(kv, 0) + 1
    vals = sorted(sizes.values())
    if not vals:
        return {
            "active_block_count": 0,
            "mean_deleted_block_size": 0.0,
            "median_deleted_block_size": 0.0,
            "p95_deleted_block_size": 0.0,
            "p99_deleted_block_size": 0.0,
            "max_deleted_block_size": 0,
        }

    def _pct(p: float) -> float:
        if len(vals) == 1:
            return float(vals[0])
        idx = (len(vals) - 1) * (p / 100.0)
        lo = int(math.floor(idx))
        hi = min(lo + 1, len(vals) - 1)
        if lo == hi:
            return float(vals[lo])
        frac = idx - lo
        return float(vals[lo] + (vals[hi] - vals[lo]) * frac)

    mid = len(vals) // 2
    if len(vals) % 2 == 1:
        median = float(vals[mid])
    else:
        median = 0.5 * (vals[mid - 1] + vals[mid])

    return {
        "active_block_count": len(vals),
        "mean_deleted_block_size": float(sum(vals)) / len(vals),
        "median_deleted_block_size": median,
        "p95_deleted_block_size": _pct(95),
        "p99_deleted_block_size": _pct(99),
        "max_deleted_block_size": int(vals[-1]),
    }


def make_positive_repair_case(
    schema: RelationSchema,
    r_prime: Sequence[Row],
    conflict_ratio: float = 0.1,
    seed: int = 42,
    verify_small: bool = False,
    max_deleted_oracle: int = 15,
    block_distribution: str = "uniform",
    zipf_alpha: float = 1.2,
    active_block_fraction: float = 0.1,
) -> RepairInstance:
    """PASS case: all injected deleted tuples conflict with r_prime on some key.

    block_distribution controls how deleted conflicts are allocated across
    retained candidate-key values (uniform vs zipf), NOT update-sampling skew.
    """
    if not (0.0 <= conflict_ratio <= 1.0):
        raise ValueError("conflict_ratio must be in [0,1]")
    dist = block_distribution.lower().strip()
    if dist.startswith("zipf"):
        # accept "zipf", "zipf_1.2"
        parts = dist.split("_")
        if len(parts) == 2:
            try:
                zipf_alpha = float(parts[1])
            except ValueError:
                pass
        dist = "zipf"
    elif dist != "uniform":
        raise ValueError(f"unknown block_distribution: {block_distribution}")

    schema.validate_bcnf()
    attr_to_idx = schema.attr_to_idx
    if not satisfies_fds(r_prime, schema.fds, attr_to_idx):
        raise ValueError("r_prime must satisfy F for PASS construction")

    rng = random.Random(seed)
    index_keys = select_index_keys(schema, use_key_cover=False)
    if not index_keys:
        raise ValueError("no index keys available")
    # Primary key used for conflict injection / block distribution
    primary_key = index_keys[0]

    n = len(r_prime)
    n_conflict = int(round(n * conflict_ratio))
    # Ensure at least one conflict when ratio > 0 and n > 0
    if conflict_ratio > 0 and n > 0:
        n_conflict = max(1, n_conflict)

    retained = list(r_prime)
    deleted: list[Row] = []

    if n > 0 and n_conflict > 0:
        # Active blocks B must be << d, otherwise uniform/zipf collapse to size-1 blocks.
        # Default: B ≈ active_block_fraction * d  (mean block size ≈ 1/fraction).
        # Optional: if active_block_fraction >= 1 treat as fraction of n (legacy brief example),
        # but clamp so mean size >= 2 whenever d >= 2.
        if active_block_fraction <= 1.0:
            B = max(1, int(round(active_block_fraction * n_conflict)))
        else:
            B = max(1, int(round(active_block_fraction)))
        B = min(B, n_conflict, n)
        if n_conflict >= 2:
            B = min(B, n_conflict // 2)  # ensure mean size >= 2
        B = max(1, B)
        counts = _allocate_counts(n_conflict, B, dist, zipf_alpha)
        parents = rng.sample(retained, k=len(counts))
        tag = 0
        for parent, cnt in zip(parents, counts):
            for _ in range(cnt):
                t = _mutate_nonkey(schema, parent, primary_key, rng, tag=tag)
                assert project_row(t, primary_key, attr_to_idx) == project_row(
                    parent, primary_key, attr_to_idx
                )
                assert t != parent
                deleted.append(t)
                tag += 1

    r = list(retained) + deleted
    # Set semantics
    if len(set(r)) != len(r):
        # Extremely rare collision; retag duplicates
        uniq = []
        seen = set()
        for i, row in enumerate(r):
            if row in seen:
                vals = list(row[: len(schema.attributes)])
                vals[-1] = (vals[-1], "dup", i)
                row = tuple(vals)
            seen.add(row)
            uniq.append(row)
        r = uniq
        deleted = [row for row in r if row not in set(retained)]

    block_stats = compute_deleted_block_stats(schema, retained, deleted, index_keys)

    inst = RepairInstance(
        schema=schema,
        r=tuple(r),
        r_prime=tuple(retained),
        metadata={
            "case_type": "pass",
            "conflict_ratio": conflict_ratio,
            "seed": seed,
            "deleted_count": len(deleted),
            "block_distribution": dist if dist == "uniform" else f"zipf_{zipf_alpha}",
            "zipf_alpha": zipf_alpha if dist == "zipf" else None,
            "r_size": len(r),
            "r_prime_size": len(retained),
            **block_stats,
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
    block_distribution: str = "uniform",
    zipf_alpha: float = 1.2,
) -> RepairInstance:
    """FAIL case: PASS conflicts plus at least one addable fresh tuple.

    addable_position in [0,1] places addable tuples late in deleted iteration
    order (default 0.9) so fail benchmarks are not dominated by early exit.
    Deleted iteration order follows r = retained + deleted_list (stream order).
    """
    if not (0.0 <= addable_position <= 1.0):
        raise ValueError("addable_position must be in [0,1]")
    rng = random.Random(seed)
    base = make_positive_repair_case(
        schema,
        r_prime,
        conflict_ratio=conflict_ratio,
        seed=seed,
        verify_small=False,
        block_distribution=block_distribution,
        zipf_alpha=zipf_alpha,
    )
    index_keys = select_index_keys(schema, use_key_cover=False)
    retained = list(base.r_prime)
    # Preserve generator order (not frozenset): conflicts then addables at position
    deleted = [t for t in base.r if t not in set(retained)]

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
            "block_distribution": base.metadata.get("block_distribution", "uniform"),
            "zipf_alpha": base.metadata.get("zipf_alpha"),
            "r_size": len(r),
            "r_prime_size": len(retained),
            "active_block_count": base.metadata.get("active_block_count"),
            "mean_deleted_block_size": base.metadata.get("mean_deleted_block_size"),
            "median_deleted_block_size": base.metadata.get("median_deleted_block_size"),
            "p95_deleted_block_size": base.metadata.get("p95_deleted_block_size"),
            "p99_deleted_block_size": base.metadata.get("p99_deleted_block_size"),
            "max_deleted_block_size": base.metadata.get("max_deleted_block_size"),
        },
    )
