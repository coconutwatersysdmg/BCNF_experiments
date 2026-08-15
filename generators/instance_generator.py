"""Clean BCNF instance generators (set semantics, unique candidate keys)."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Optional, Sequence

from common.fd_utils import project_row, satisfies_fds
from common.types import RelationSchema, Row


def _stable_hash_int(seed: int, *parts: Any) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode())
    for p in parts:
        h.update(b"|")
        h.update(str(p).encode())
    return int.from_bytes(h.digest(), "little")


def _zipf_rank(rng: random.Random, n: int, alpha: float) -> int:
    """Sample a rank in [0, n) with Zipf-like weights ~ 1/(i+1)^alpha."""
    if n <= 1:
        return 0
    # Inverse-CDF via harmonic-like weights without building full array for large n:
    # use approximate sampling with truncated harmonic.
    # For reproducibility and speed at large n, use rejection-friendly alias-free method:
    # sample u ~ U(0, H) where H ≈ zeta, then invert.
    # Simpler exact for moderate n; for large n use log trick.
    if n <= 100_000:
        weights = [1.0 / ((i + 1) ** alpha) for i in range(n)]
        total = sum(weights)
        u = rng.random() * total
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if u <= acc:
                return i
        return n - 1
    # Large-n approximation: invert continuous Zipf.
    # P(R <= k) ≈ H_k^{(a)} / H_n^{(a)}
    # Use u^{ -1/a } transform for classic Zipf when alpha>0.
    u = max(rng.random(), 1e-12)
    if alpha <= 1e-12:
        return int(u * n) % n
    # Approximate: rank = floor(u^{-1/alpha}) clipped
    rank = int(u ** (-1.0 / alpha)) - 1
    return max(0, min(n - 1, rank % n))


def generate_clean_instance(
    schema: RelationSchema,
    n: int,
    seed: int = 42,
    skew: str = "uniform",
) -> list[Row]:
    """Generate a clean instance r_clean that satisfies F.

    Candidate-key values are constructed from row id to guarantee uniqueness
    without rejection sampling (critical for large n).
    Non-key attributes use deterministic pseudo-random values; optional
    skew applies to non-key attributes only.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    schema.validate_bcnf()
    rng = random.Random(seed)
    attrs = schema.attributes
    attr_to_idx = schema.attr_to_idx
    keys = schema.candidate_keys
    if not keys:
        # Fall back: use minimize of first FD lhs via schema FDs
        from common.fd_utils import minimize_superkey, nontrivial_fds

        nfs = nontrivial_fds(schema.fds)
        if not nfs:
            raise ValueError("schema has no nontrivial FDs / candidate keys")
        k = minimize_superkey(nfs[0].lhs, attrs, schema.fds)
        keys = (tuple(sorted(k)),)

    key_attr_set = set()
    for k in keys:
        key_attr_set.update(k)

    alpha = 0.0
    if skew.startswith("zipf_"):
        alpha = float(skew.split("_", 1)[1])
    elif skew not in ("uniform",):
        raise ValueError(f"Unknown skew mode: {skew}")

    rows: list[Row] = []
    for i in range(n):
        values: list[Any] = [None] * len(attrs)
        # Unique key values from row id (and key index to separate multi-keys)
        for ki, key in enumerate(keys):
            for pos, a in enumerate(key):
                # Encode (i, ki, pos) into a unique integer-like value
                values[attr_to_idx[a]] = i * 10_000 + ki * 100 + pos
        # Non-key attributes
        for a in attrs:
            if a in key_attr_set:
                continue
            if alpha > 0:
                # Skewed categorical domain derived from zipf rank
                rank = _zipf_rank(rng, max(n, 2), alpha)
                values[attr_to_idx[a]] = f"v{rank}"
            else:
                values[attr_to_idx[a]] = _stable_hash_int(seed, i, a) % (10 * max(n, 1) + 7)
        # Ensure FD satisfaction for multi-key schemas: non-key attrs must be
        # a deterministic function of EACH candidate key. Using row-id-based
        # values already does this because each key uniquely identifies i, and
        # non-key values are functions of i (and attribute name / skew sample
        # tied to i). For zipf, reseat by i for determinism:
        if alpha > 0:
            for a in attrs:
                if a in key_attr_set:
                    continue
                # Deterministic per-row skewed value (not re-sampled independently
                # of key), so all keys determining the same row agree.
                local = random.Random(_stable_hash_int(seed, i, "skew"))
                rank = _zipf_rank(local, max(n, 2), alpha)
                values[attr_to_idx[a]] = f"v{rank}"
        rows.append(tuple(values))

    # Set semantics: uniqueness already by keys
    assert len(set(rows)) == len(rows)
    assert satisfies_fds(rows, schema.fds, attr_to_idx)
    # Candidate key uniqueness
    for key in keys:
        seen = set()
        for row in rows:
            kv = project_row(row, key, attr_to_idx)
            if kv in seen:
                raise AssertionError(f"candidate key {key} not unique")
            seen.add(kv)
    return rows
