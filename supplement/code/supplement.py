"""Supplemental checks; never modifies the frozen experiment repositories."""
from __future__ import annotations
import itertools
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# supplement/code/ -> experiments/ (the algorithm repository this depends on)
EXPERIMENTS = ROOT.parent.parent
sys.path.insert(0, str(EXPERIMENTS))
from common.types import FD, RelationSchema
from common.fd_utils import attribute_closure
from algorithms.bcnf_index import BCNFRepairChecker
from algorithms.fd_hash import is_subset_repair_fd_hash


def equivalent_cover(schema):
    """Singleton RHS, remove extraneous LHS/redundant FDs, regroup LHS.

    This is one equivalent reduced cover, not an assertion of a unique or
    globally minimum-cardinality representation. Check both implications.
    """
    rules = list(dict.fromkeys((frozenset(fd.lhs), a) for fd in schema.fds
                              for a in fd.rhs if a not in fd.lhs))
    def closure(x, rs):
        return attribute_closure(x, [FD(tuple(sorted(lhs)), (rhs,)) for lhs, rhs in rs])
    for i in range(len(rules)):
        lhs, rhs = rules[i]
        for a in sorted(lhs):
            if rhs in closure(lhs - {a}, rules):
                lhs = lhs - {a}
                rules[i] = lhs, rhs
    rules = list(dict.fromkeys(rules))
    i = 0
    while i < len(rules):
        lhs, rhs = rules[i]
        if rhs in closure(lhs, rules[:i] + rules[i+1:]):
            rules.pop(i)
        else:
            i += 1
    grouped = defaultdict(set)
    for lhs, rhs in rules:
        grouped[lhs].add(rhs)
    fds = tuple(FD(tuple(sorted(lhs)), tuple(sorted(rhs)))
                for lhs, rhs in grouped.items())
    for old, new in [(schema.fds, fds), (fds, schema.fds)]:
        for fd in old:
            assert fd.rhs_set <= attribute_closure(fd.lhs, new), 'Unequal FD covers'
    return RelationSchema(schema.attributes, fds, name=schema.name + '-cover')


def definition_oracle(schema, r, retained):
    """Pairwise FDs + all strict supersets; no candidate keys/singleton shortcut."""
    positions = schema.attr_to_idx
    def consistent(rows):
        for x, y in itertools.combinations(rows, 2):
            for fd in schema.fds:
                if (all(x[positions[a]] == y[positions[a]] for a in fd.lhs)
                    and any(x[positions[a]] != y[positions[a]] for a in fd.rhs)):
                    return False
        return True
    if not consistent(retained):
        return False, False
    selected = set(retained)
    deleted = [t for t in r if t not in selected]
    if len(deleted) > 15:
        raise ValueError('Definition oracle is bounded to 15 excluded tuples')
    for size in range(1, len(deleted) + 1):
        for extension in itertools.combinations(deleted, size):
            if consistent(list(retained) + list(extension)):
                return False, True
    return True, True


def make_schema(q, m=16):
    attrs = tuple([f'K{i}' for i in range(8)] + [f'P{i}' for i in range(8)])
    fds = [FD((f'K{i}',), tuple(a for a in attrs if a != f'K{i}')) for i in range(q)]
    extras = [c for width in [1, 2, 3] for c in itertools.combinations(attrs[8:], width)]
    for j in range(m - q):
        extra = extras[j // q]
        fds.append(FD((f'K{j % q}',) + extra,
                      (next(a for a in attrs[8:] if a not in extra),)))
    schema = RelationSchema(attrs, tuple(fds), name=f'q{q}_m{m}')
    schema.validate_bcnf()
    return schema


def synthetic_rows(schema, n, seed):
    rng = random.Random(seed)
    retained = [tuple(i * 17 + j for j in range(16)) for i in range(n)]
    q = len(BCNFRepairChecker(schema).index_keys)
    deleted = []
    for i in range(max(1, n // 10)):
        ref = retained[rng.randrange(n)]
        row = [-((i + 1) * 17 + j + 1) for j in range(16)]
        k = i % q
        row[k] = ref[k]
        deleted.append(tuple(row))
    return retained + deleted, retained


def benchmark_cases(schema, clean, seed):
    """Controlled perturbations of a clean single/composite-primary-key table."""
    rng = random.Random(seed)
    count = max(1, len(clean) // 10)
    chosen = rng.sample(range(len(clean)), count)
    variants = []
    for i in chosen:
        row = list(clean[i])
        row[-1] = str(row[-1]) + f' [variant {seed}/{i}]'
        variants.append(tuple(row))
    yield 'repair', clean + variants, clean, (True, True), None
    untouched = next(i for i in range(len(clean)) if i not in set(chosen))
    witness = clean[untouched]
    rp = clean[:untouched] + clean[untouched + 1:]
    for fraction in [0.0, 0.5, 1.0]:
        position = int(fraction * len(variants))
        deleted = variants[:position] + [witness] + variants[position:]
        yield f'nonmax_{fraction:.1f}', rp + deleted, rp, (False, True), position
    yield 'inconsistent', clean + variants, clean + variants[:1], (False, False), None


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


class SQLChecker:
    """General FD SQL baseline, without candidate-key specialization.

    One-thread DuckDB, tables loaded outside query timer. load_sec includes
    Arrow conversion and table creation. Queries include subset validation,
    per-FD consistency, and singleton add-back tests using anti-existence.
    Generated inputs have no NULL values and use set semantics.
    """
    def __init__(self, schema, r, retained):
        import duckdb
        import pyarrow as pa
        self.schema = schema
        self.conn = duckdb.connect()
        self.conn.execute("SET threads=1")
        self.conn.execute("SET memory_limit='256MB'")
        temp = ROOT / 'duckdb_tmp'
        temp.mkdir(exist_ok=True)
        self.conn.execute('SET temp_directory=' + "'" + str(temp).replace("'", "''") + "'")
        t0 = time.perf_counter()
        original = pa.table({a: [row[i] for row in r] for i, a in enumerate(schema.attributes)})
        retained_table = pa.Table.from_arrays(
            [pa.array([row[i] for row in retained], type=original.schema.field(i).type)
             for i in range(len(schema.attributes))], schema=original.schema)
        for name, table in [('original', original), ('candidate', retained_table)]:
            self.conn.register('_incoming', table)
            self.conn.execute(f'CREATE TABLE {name} AS SELECT * FROM _incoming')
            self.conn.unregister('_incoming')
        self.load_sec = time.perf_counter() - t0
        self.last_parts = {}

    def check(self):
        attrs = ','.join(quoted(a) for a in self.schema.attributes)
        t0 = time.perf_counter()
        invalid_subset = self.conn.execute(
            f'SELECT 1 FROM candidate ANTI JOIN original USING ({attrs}) LIMIT 1').fetchone()
        if invalid_subset:
            raise ValueError('Candidate is not a subset')
        validation = time.perf_counter() - t0
        t1 = time.perf_counter()
        fds = [fd for fd in self.schema.fds if not fd.is_trivial()]
        for fd in fds:
            lhs = ','.join(quoted(a) for a in fd.lhs)
            rhs = ','.join(quoted(a) for a in fd.rhs)
            group = f'GROUP BY {lhs}' if fd.lhs else ''
            bad = self.conn.execute(
                f'SELECT 1 FROM candidate {group} '
                f'HAVING COUNT(DISTINCT ROW({rhs})) > 1 LIMIT 1').fetchone()
            if bad:
                self.last_parts = dict(validation_sec=validation,
                                       consistency_sec=time.perf_counter()-t1, maximality_sec=0.)
                return False, False
        consistency = time.perf_counter() - t1
        conditions = []
        for fd in fds:
            lhs = ' AND '.join(f'd.{quoted(a)}=s.{quoted(a)}' for a in fd.lhs) or 'TRUE'
            rhs = ' OR '.join(f'd.{quoted(a)}<>s.{quoted(a)}' for a in fd.rhs) or 'FALSE'
            conditions.append(f'NOT EXISTS (SELECT 1 FROM candidate s WHERE ({lhs}) AND ({rhs}))')
        t2 = time.perf_counter()
        where = ' AND '.join(conditions) or 'TRUE'
        unblocked = self.conn.execute(
            f'WITH d AS (SELECT original.* FROM original ANTI JOIN candidate USING ({attrs})) '
            f'SELECT 1 FROM d WHERE {where} LIMIT 1').fetchone()
        self.last_parts = dict(validation_sec=validation, consistency_sec=consistency,
                               maximality_sec=time.perf_counter()-t2)
        return not bool(unblocked), True

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
