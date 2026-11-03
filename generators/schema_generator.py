"""BCNF synthetic schema generators (single-key and multi-key families)."""

from __future__ import annotations

import itertools
from typing import Optional, Sequence

from common.fd_utils import validate_bcnf
from common.types import FD, RelationSchema


def _attrs(n: int, prefix: str = "A") -> tuple[str, ...]:
    return tuple(f"{prefix}{i}" for i in range(n))


def generate_single_key_bcnf(
    n_attrs: int = 8,
    key_width: int = 1,
    fd_count: int = 4,
    include_redundant_superkeys: bool = True,
    name: str = "SingleKeyBCNF",
    seed: Optional[int] = None,
) -> RelationSchema:
    """Single-key BCNF family: one base candidate key K0 determines others.

    All FD left-hand sides contain K0, hence are superkeys.
    """
    if key_width < 1 or key_width >= n_attrs:
        raise ValueError("key_width must satisfy 1 <= key_width < n_attrs")
    U = _attrs(n_attrs)
    K0 = U[:key_width]
    nonkey = U[key_width:]
    if not nonkey:
        raise ValueError("need at least one non-key attribute")

    fds: list[FD] = []
    # Primary: K0 -> non-key attributes (batched into up to fd_count FDs)
    # Distribute nonkey attrs across FDs.
    chunks: list[tuple[str, ...]] = []
    remaining = list(nonkey)
    n_primary = max(1, min(fd_count, len(remaining)))
    # Split remaining into n_primary roughly equal parts
    for i in range(n_primary):
        chunks.append(())
    for i, a in enumerate(remaining):
        chunks[i % n_primary] = chunks[i % n_primary] + (a,)
    for rhs in chunks:
        if rhs:
            fds.append(FD(lhs=K0, rhs=rhs))

    # Redundant superkey FDs: K0 + extra -> other attrs
    if include_redundant_superkeys and len(nonkey) >= 2:
        extra = nonkey[0]
        target = nonkey[1:]
        if target:
            fds.append(FD(lhs=K0 + (extra,), rhs=tuple(target[: max(1, len(target) // 2)])))

    # Trim / expand toward requested fd_count if needed
    while len(fds) < fd_count and len(nonkey) >= 1:
        # Add more redundant forms with different extras when possible
        extras = [a for a in nonkey if a]
        for e in extras:
            rhs = tuple(a for a in nonkey if a != e)[:1]
            if not rhs:
                continue
            cand = FD(lhs=K0 + (e,), rhs=rhs)
            if cand not in fds:
                fds.append(cand)
            if len(fds) >= fd_count:
                break
        break
    fds = fds[: max(fd_count, 1)]

    schema = RelationSchema(
        attributes=U,
        fds=tuple(fds),
        candidate_keys=(K0,),
        name=name,
    )
    if not validate_bcnf(schema.U, schema.fds):
        raise ValueError("Generated single-key schema failed BCNF validation")
    schema.validate_bcnf()
    return schema


def generate_multi_key_bcnf(
    n_attrs: int = 10,
    n_keys: int = 2,
    key_width: int = 1,
    include_redundant_superkeys: bool = True,
    name: str = "MultiKeyBCNF",
) -> RelationSchema:
    """Multi-key BCNF family with 2/3/4 candidate keys.

    Each Ki determines all other attributes. Clean instances must keep each
    Ki unique. Redundant superkey FDs containing some Ki may also be added.
    """
    if n_keys not in (2, 3, 4):
        raise ValueError("n_keys must be 2, 3, or 4")
    need = n_keys * key_width
    if n_attrs <= need:
        raise ValueError("n_attrs too small for requested keys")

    U = _attrs(n_attrs)
    keys: list[tuple[str, ...]] = []
    for i in range(n_keys):
        start = i * key_width
        keys.append(U[start : start + key_width])

    fds: list[FD] = []
    for Ki in keys:
        others = tuple(a for a in U if a not in Ki)
        # Split others into one or two FDs for variety
        mid = max(1, len(others) // 2)
        fds.append(FD(lhs=Ki, rhs=others[:mid]))
        if others[mid:]:
            fds.append(FD(lhs=Ki, rhs=others[mid:]))

    if include_redundant_superkeys:
        K0 = keys[0]
        extra_candidates = [a for a in U if a not in K0]
        if extra_candidates:
            e = extra_candidates[0]
            rhs = tuple(a for a in U if a not in K0 and a != e)[:2]
            if rhs:
                fds.append(FD(lhs=K0 + (e,), rhs=rhs))

    schema = RelationSchema(
        attributes=U,
        fds=tuple(fds),
        candidate_keys=tuple(keys),
        name=name,
    )
    if not validate_bcnf(schema.U, schema.fds):
        raise ValueError("Generated multi-key schema failed BCNF validation")
    schema.validate_bcnf()
    return schema


def generate_bcnf_schema(
    family: str = "single",
    n_attrs: int = 8,
    key_width: int = 1,
    fd_count: int = 4,
    n_keys: int = 2,
    **kwargs: object,
) -> RelationSchema:
    """Dispatch schema generation by family name."""
    if family in ("single", "single_key", "SingleKeyBCNF"):
        return generate_single_key_bcnf(
            n_attrs=n_attrs,
            key_width=key_width,
            fd_count=fd_count,
            **{k: v for k, v in kwargs.items() if k in ("include_redundant_superkeys", "name", "seed")},  # type: ignore[arg-type]
        )
    if family in ("multi", "multi_key", "MultiKeyBCNF"):
        return generate_multi_key_bcnf(
            n_attrs=n_attrs,
            n_keys=n_keys,
            key_width=key_width,
            **{k: v for k, v in kwargs.items() if k in ("include_redundant_superkeys", "name")},  # type: ignore[arg-type]
        )
    raise ValueError(f"Unknown schema family: {family}")
