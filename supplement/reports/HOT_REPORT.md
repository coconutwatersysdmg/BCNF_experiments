# Hot-group incremental experiment

Fixed 50,000 retained and 10,000 excluded tuples. One declared candidate key; varying the size of the repeatedly updated conflict group. Three seeds and 30 successive batches per cell. Full partition equality and exact work counters are checked after every batch, outside timers. No model calls or tracemalloc.

All percentiles are descriptive. Sequential batches within a seed are dependent; 90 observations are not 90 independent generated databases. Static rebuild includes applying the same updates, list conversion, validation, index construction, checking, and index release. Initialization is outside batch times and reported separately.

|Hot group|Swaps/batch|Incremental median (ms)|Rebuild median (ms)|Incremental p95 (ms)|p99 (ms)|Paired speedup|Samples|
|---:|---:|---:|---:|---:|---:|---:|---:|
|1|1|0.0491|118.6900|0.0647|0.0722|2453.674x|90|
|1|10|0.1036|118.9687|0.1393|0.1594|1151.530x|90|
|1|100|0.6277|124.4435|1.1509|1.4140|192.828x|90|
|100|1|0.1148|124.5521|0.1658|0.1996|1120.883x|90|
|100|10|0.4685|124.2771|0.6451|0.9822|264.941x|90|
|100|100|4.1392|125.5890|5.7135|6.8786|30.458x|90|
|10000|1|6.3006|118.3892|9.3636|11.6210|19.537x|90|
|10000|10|55.1307|114.3835|78.9844|85.9035|2.096x|90|
|10000|100|507.1572|116.7098|750.5738|815.4170|0.226x|90|

Total measured batches: 810; decision/partition disagreements: 0.
A paired speedup below one means rebuilding was faster in that configuration. Do not omit such crossover observations.
