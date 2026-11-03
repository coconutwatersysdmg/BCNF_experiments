"""TPC-H projection loader with explicit BCNF validation.

Does not assume the full TPC-H schema is BCNF. Users must specify the
projected attributes and FDs; the loader rejects non-BCNF projections.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, Sequence

from common.fd_utils import validate_bcnf
from common.types import FD, RelationSchema, Row


# Suggested projections (must still be validated):
SUGGESTED = {
    "CUSTOMER": {
        "attributes": ("C_CUSTKEY", "C_NAME", "C_ADDRESS", "C_NATIONKEY", "C_PHONE", "C_ACCTBAL", "C_MKTSEGMENT", "C_COMMENT"),
        "fds": [(("C_CUSTKEY",), ("C_NAME", "C_ADDRESS", "C_NATIONKEY", "C_PHONE", "C_ACCTBAL", "C_MKTSEGMENT", "C_COMMENT"))],
        "candidate_keys": (("C_CUSTKEY",),),
    },
    "ORDERS": {
        "attributes": ("O_ORDERKEY", "O_CUSTKEY", "O_ORDERSTATUS", "O_TOTALPRICE", "O_ORDERDATE", "O_ORDERPRIORITY", "O_CLERK", "O_SHIPPRIORITY", "O_COMMENT"),
        "fds": [(("O_ORDERKEY",), ("O_CUSTKEY", "O_ORDERSTATUS", "O_TOTALPRICE", "O_ORDERDATE", "O_ORDERPRIORITY", "O_CLERK", "O_SHIPPRIORITY", "O_COMMENT"))],
        "candidate_keys": (("O_ORDERKEY",),),
    },
    "PART": {
        "attributes": ("P_PARTKEY", "P_NAME", "P_MFGR", "P_BRAND", "P_TYPE", "P_SIZE", "P_CONTAINER", "P_RETAILPRICE", "P_COMMENT"),
        "fds": [(("P_PARTKEY",), ("P_NAME", "P_MFGR", "P_BRAND", "P_TYPE", "P_SIZE", "P_CONTAINER", "P_RETAILPRICE", "P_COMMENT"))],
        "candidate_keys": (("P_PARTKEY",),),
    },
}


def make_schema(
    name: str,
    attributes: Sequence[str],
    fds: Sequence[tuple[Sequence[str], Sequence[str]]],
    candidate_keys: Sequence[Sequence[str]] = (),
) -> RelationSchema:
    schema = RelationSchema(
        attributes=tuple(attributes),
        fds=tuple(FD(tuple(l), tuple(r)) for l, r in fds),
        candidate_keys=tuple(tuple(k) for k in candidate_keys),
        name=name,
    )
    if not validate_bcnf(schema.U, schema.fds):
        raise ValueError(
            f"TPC-H projection {name} is not BCNF under the provided FDs; refusing experiment."
        )
    schema.validate_bcnf()
    return schema


def load_tbl(
    path: Path,
    attributes: Sequence[str],
    delimiter: str = "|",
) -> list[Row]:
    """Load a .tbl / CSV file into tuples (set semantics enforced by caller)."""
    rows: list[Row] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        # TPC-H .tbl often has a trailing delimiter
        for line in f:
            line = line.rstrip("\n\r")
            if not line:
                continue
            parts = line.split(delimiter)
            if parts and parts[-1] == "":
                parts = parts[:-1]
            if len(parts) < len(attributes):
                raise ValueError(f"Row has {len(parts)} fields, expected >= {len(attributes)}")
            rows.append(tuple(parts[: len(attributes)]))
    return rows


def load_csv_header(path: Path, attributes: Optional[Sequence[str]] = None) -> tuple[tuple[str, ...], list[Row]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")
        attrs = tuple(attributes) if attributes else tuple(reader.fieldnames)
        rows = [tuple(row[a] for a in attrs) for row in reader]
    return attrs, rows


def load_tpch_relation(
    path: Path,
    name: str,
    attributes: Sequence[str],
    fds: Sequence[tuple[Sequence[str], Sequence[str]]],
    candidate_keys: Sequence[Sequence[str]] = (),
) -> tuple[RelationSchema, list[Row]]:
    """Load external TPC-H data and validate BCNF on the explicit projection."""
    schema = make_schema(name, attributes, fds, candidate_keys)
    if path.suffix.lower() == ".csv":
        _, rows = load_csv_header(path, attributes)
    else:
        rows = load_tbl(path, attributes)
    # set semantics
    rows = list(dict.fromkeys(rows))
    return schema, rows
