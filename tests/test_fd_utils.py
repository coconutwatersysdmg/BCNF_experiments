"""Tests for FD utilities: closure, satisfaction, BCNF, key minimization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.fd_utils import (
    attribute_closure,
    is_superkey,
    minimize_superkey,
    satisfies_fds,
    validate_bcnf,
)
from common.types import FD, RelationSchema


def test_attribute_closure_classic() -> None:
    fds = (FD(("A",), ("B",)), FD(("B",), ("C",)))
    assert attribute_closure({"A"}, fds) == frozenset({"A", "B", "C"})
    assert attribute_closure({"B"}, fds) == frozenset({"B", "C"})
    assert attribute_closure({"C"}, fds) == frozenset({"C"})


def test_attribute_closure_empty() -> None:
    fds = (FD(("A",), ("B",)),)
    assert attribute_closure(set(), fds) == frozenset()


def test_is_superkey() -> None:
    U = {"A", "B", "C"}
    fds = (FD(("A",), ("B",)), FD(("A",), ("C",)))
    assert is_superkey({"A"}, U, fds)
    assert not is_superkey({"B"}, U, fds)


def test_minimize_superkey_removes_redundant() -> None:
    U = ("A", "B", "C", "D")
    fds = (
        FD(("A", "B"), ("C",)),
        FD(("A", "B"), ("D",)),
    )
    # Superkey ABD minimizes to AB (C is determined by AB; D removable from ABD)
    k = minimize_superkey(["A", "B", "D"], U, fds)
    assert k == frozenset({"A", "B"})


def test_validate_bcnf_true() -> None:
    U = {"A", "B", "C"}
    fds = (FD(("A",), ("B",)), FD(("A",), ("C",)))
    assert validate_bcnf(U, fds)


def test_validate_bcnf_false() -> None:
    # Classic non-BCNF: A->B with A not a superkey when C is independent.
    U = {"A", "B", "C"}
    fds = (FD(("A",), ("B",)),)
    assert not validate_bcnf(U, fds)


def test_satisfies_fds_true_and_false() -> None:
    attrs = ("A", "B", "C")
    attr_to_idx = {a: i for i, a in enumerate(attrs)}
    fds = (FD(("A",), ("B",)),)
    ok = ((1, 10, 0), (2, 20, 0), (3, 10, 1))
    assert satisfies_fds(ok, fds, attr_to_idx)
    bad = ((1, 10, 0), (1, 11, 0))
    assert not satisfies_fds(bad, fds, attr_to_idx)


def test_schema_validate_bcnf_raises() -> None:
    schema = RelationSchema(
        attributes=("A", "B", "C"),
        fds=(FD(("A",), ("B",)),),
        name="Bad",
    )
    with pytest.raises(ValueError):
        schema.validate_bcnf()


def test_fd_serialization() -> None:
    fd = FD(("student_id",), ("name", "major"))
    obj = fd.to_json()
    assert FD.from_json(obj) == fd
