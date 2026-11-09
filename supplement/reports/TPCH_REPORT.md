# Benchmark-derived candidate study

Source: DuckDB 2.0.0 tpch extension, scale factors 0.01 and 0.1. These are controlled projections with injected conflicts; this is not a TPC-H throughput benchmark or a natural dirty-data study.
[Generator documentation](https://duckdb.org/docs/2.0/core_extensions/tpch). The extension documents small differences from the official TPC-H specification.

- CUSTOMER projection: six mixed-type attributes, declared key c_custkey.
- LINEITEM projection: six mixed-type attributes, declared key (l_orderkey,l_linenumber).
- Only the declared key FDs are checked. Cross-relation foreign-key constraints and unspecified accidental FDs are not checked.
- 10% of clean tuples receive a distinct comment variant, preserving the key and changing a dependent value.
- Valid candidates retain the clean rows; non-maximal candidates omit one entire untouched key group, with the sole add-back witness placed at 0%, 50%, or 100% of the excluded order.
- Inconsistent candidates additionally retain one conflicting variant.
- Three seeds × three repeats, one warmup per method/seed/candidate, randomized method order, no tracemalloc.
- SQL uses one thread, a 256 MiB engine memory limit, subset anti-join, per-FD GROUP BY consistency tests, and correlated NOT EXISTS singleton tests.
- Resident SQL timings exclude tuple import. SQL + load adds measured Arrow conversion/table creation. Loading occurs once per seed/candidate; the three query repetitions reuse that measured load, so they are not independent end-to-end loading repetitions.
- Python cold checker timings include subset validation, index build, scan, and index release, operating on shared Python tuples. No candidate-key specialization is used in the SQL baseline.

Timing observations: 531. Decision disagreements: 0 among completed observations. Explicit load/query errors or memory skips: 3.

|Table|SF|Candidate|Method|Retained|Median query/check (ms)|Median + load (ms)|Samples|
|---|---:|---|---|---:|---:|---:|---:|
|customer|0.01|inconsistent|BCNF-Index|1,501.0|1.476|1.476|9|
|customer|0.01|inconsistent|DuckDB-SQL|1,501.0|6.207|13.757|9|
|customer|0.01|inconsistent|FD-Hash-Cover|1,501.0|2.795|2.795|9|
|customer|0.01|nonmax_0.0|BCNF-Index|1,499.0|1.576|1.576|9|
|customer|0.01|nonmax_0.0|DuckDB-SQL|1,499.0|12.895|20.677|9|
|customer|0.01|nonmax_0.0|FD-Hash-Cover|1,499.0|2.899|2.899|9|
|customer|0.01|nonmax_0.5|BCNF-Index|1,499.0|1.788|1.788|9|
|customer|0.01|nonmax_0.5|DuckDB-SQL|1,499.0|13.375|20.461|9|
|customer|0.01|nonmax_0.5|FD-Hash-Cover|1,499.0|3.090|3.090|9|
|customer|0.01|nonmax_1.0|BCNF-Index|1,499.0|1.729|1.729|9|
|customer|0.01|nonmax_1.0|DuckDB-SQL|1,499.0|12.480|20.637|9|
|customer|0.01|nonmax_1.0|FD-Hash-Cover|1,499.0|3.222|3.222|9|
|customer|0.01|repair|BCNF-Index|1,500.0|1.791|1.791|9|
|customer|0.01|repair|DuckDB-SQL|1,500.0|13.763|23.826|9|
|customer|0.01|repair|FD-Hash-Cover|1,500.0|3.353|3.353|9|
|customer|0.1|inconsistent|BCNF-Index|15,001.0|15.143|15.143|9|
|customer|0.1|inconsistent|DuckDB-SQL|15,001.0|18.547|55.535|9|
|customer|0.1|inconsistent|FD-Hash-Cover|15,001.0|29.776|29.776|9|
|customer|0.1|nonmax_0.0|BCNF-Index|14,999.0|18.630|18.630|9|
|customer|0.1|nonmax_0.0|DuckDB-SQL|14,999.0|31.926|63.055|9|
|customer|0.1|nonmax_0.0|FD-Hash-Cover|14,999.0|32.646|32.646|9|
|customer|0.1|nonmax_0.5|BCNF-Index|14,999.0|19.410|19.410|9|
|customer|0.1|nonmax_0.5|DuckDB-SQL|14,999.0|31.039|66.000|9|
|customer|0.1|nonmax_0.5|FD-Hash-Cover|14,999.0|35.018|35.018|9|
|customer|0.1|nonmax_1.0|BCNF-Index|14,999.0|20.174|20.174|9|
|customer|0.1|nonmax_1.0|DuckDB-SQL|14,999.0|31.458|63.249|9|
|customer|0.1|nonmax_1.0|FD-Hash-Cover|14,999.0|36.386|36.386|9|
|customer|0.1|repair|BCNF-Index|15,000.0|22.864|22.864|9|
|customer|0.1|repair|DuckDB-SQL|15,000.0|39.222|477.579|6|
|customer|0.1|repair|FD-Hash-Cover|15,000.0|43.369|43.369|9|
|lineitem|0.01|inconsistent|BCNF-Index|60,176.0|78.925|78.925|9|
|lineitem|0.01|inconsistent|DuckDB-SQL|60,176.0|35.565|124.756|9|
|lineitem|0.01|inconsistent|FD-Hash-Cover|60,176.0|129.781|129.781|9|
|lineitem|0.01|nonmax_0.0|BCNF-Index|60,174.0|99.685|99.685|9|
|lineitem|0.01|nonmax_0.0|DuckDB-SQL|60,174.0|69.293|169.148|9|
|lineitem|0.01|nonmax_0.0|FD-Hash-Cover|60,174.0|155.513|155.513|9|
|lineitem|0.01|nonmax_0.5|BCNF-Index|60,174.0|107.777|107.777|9|
|lineitem|0.01|nonmax_0.5|DuckDB-SQL|60,174.0|65.624|152.660|9|
|lineitem|0.01|nonmax_0.5|FD-Hash-Cover|60,174.0|165.776|165.776|9|
|lineitem|0.01|nonmax_1.0|BCNF-Index|60,174.0|111.084|111.084|9|
|lineitem|0.01|nonmax_1.0|DuckDB-SQL|60,174.0|73.108|161.939|9|
|lineitem|0.01|nonmax_1.0|FD-Hash-Cover|60,174.0|181.406|181.406|9|
|lineitem|0.01|repair|BCNF-Index|60,175.0|109.302|109.302|9|
|lineitem|0.01|repair|DuckDB-SQL|60,175.0|65.913|178.709|9|
|lineitem|0.01|repair|FD-Hash-Cover|60,175.0|169.151|169.151|9|
|lineitem|0.1|inconsistent|BCNF-Index|600,573.0|1108.658|1108.658|9|
|lineitem|0.1|inconsistent|DuckDB-SQL|600,573.0|390.406|1333.117|6|
|lineitem|0.1|inconsistent|FD-Hash-Cover|600,573.0|1642.891|1642.891|9|
|lineitem|0.1|nonmax_0.0|BCNF-Index|600,571.0|1424.652|1424.652|9|
|lineitem|0.1|nonmax_0.0|DuckDB-SQL|600,571.0|705.632|1811.555|9|
|lineitem|0.1|nonmax_0.0|FD-Hash-Cover|600,571.0|1967.247|1967.247|9|
|lineitem|0.1|nonmax_0.5|BCNF-Index|600,571.0|1565.193|1565.193|9|
|lineitem|0.1|nonmax_0.5|DuckDB-SQL|600,571.0|626.684|1694.312|9|
|lineitem|0.1|nonmax_0.5|FD-Hash-Cover|600,571.0|2030.605|2030.605|9|
|lineitem|0.1|nonmax_1.0|BCNF-Index|600,571.0|1504.391|1504.391|9|
|lineitem|0.1|nonmax_1.0|DuckDB-SQL|600,571.0|669.677|1645.534|9|
|lineitem|0.1|nonmax_1.0|FD-Hash-Cover|600,571.0|2177.782|2177.782|9|
|lineitem|0.1|repair|BCNF-Index|600,572.0|1511.772|1511.772|9|
|lineitem|0.1|repair|DuckDB-SQL|600,572.0|619.172|1592.924|6|
|lineitem|0.1|repair|FD-Hash-Cover|600,572.0|2172.703|2172.703|9|

## Reproduction

```powershell
python -u run_tpch_supplement.py
python summarize_tpch.py
```

See the protocol JSON for source commit, exact SQL projections, versions, and environmental information. See raw JSONL for every timing and declared expected decision.