# Static supplemental experiment report

Protocol: v2. All times below are actual measurements, with no imputed/skipped observations.

- Frozen commit: `f9093e1b9e19aa2c1bf77fa5eb3872b0c3392f37`.
- Python: `3.12.7 | packaged by Anaconda, Inc. | (main, Oct  4 2024, 13:17:27) [MSC v.1929 64 bit (AMD64)]`.
- Completed jobs: 14/14.
- Ordinary timing observations: 360; separate allocation observations: 15.
- Explicit memory skips: 6. See `data/static_skipped.csv`.
- Each full timing cell has three seeds × three repeats, after one untimed warmup per seed/method.
- Ordinary time includes subset validation, index build, deleted-tuple scan, and index release. Schema preprocessing and workload generation are outside the timer.
- Build/check/validation times are internal diagnostics and exclude some cleanup; compare outer wall times for the headline results.
- Allocation is measured separately with tracemalloc (one observation per selected configuration), covers only Python allocations, and is not total process RAM.
- Randomized method order; PYTHONHASHSEED=0; sequential workers. No external model calls.
- Pilot v1 files are retained for audit, but excluded from all summaries and figures.

## Wall-time medians

|Workload|Retained|Keys|Method|Median (s)|IQR (s)|Samples|Seeds|
|---|---:|---:|---|---:|---|---:|---:|
|keys|50,000|1|BCNF-Index|0.049577|0.049005–0.049686|9|3|
|keys|50,000|1|FD-Hash|0.965091|0.961806–0.971166|9|3|
|keys|50,000|1|FD-Hash-Cover|0.124580|0.122524–0.124907|9|3|
|keys|50,000|2|BCNF-Index|0.077529|0.077087–0.078045|9|3|
|keys|50,000|2|FD-Hash|0.980532|0.976480–0.988746|9|3|
|keys|50,000|2|FD-Hash-Cover|0.172330|0.171825–0.173351|9|3|
|keys|50,000|4|BCNF-Index|0.133012|0.130255–0.134334|9|3|
|keys|50,000|4|FD-Hash|1.071142|1.061068–1.082092|9|3|
|keys|50,000|4|FD-Hash-Cover|0.269337|0.268146–0.278022|9|3|
|keys|50,000|8|BCNF-Index|0.243789|0.240157–0.246831|9|3|
|keys|50,000|8|FD-Hash|1.265375|1.231406–1.269800|9|3|
|keys|50,000|8|FD-Hash-Cover|0.477769|0.475973–0.479439|9|3|
|keys|250,000|1|BCNF-Index|0.271596|0.267144–0.284579|9|3|
|keys|250,000|1|FD-Hash|5.064390|4.964276–5.108631|9|3|
|keys|250,000|1|FD-Hash-Cover|0.645572|0.642034–0.658418|9|3|
|keys|250,000|2|BCNF-Index|0.420628|0.414982–0.424338|9|3|
|keys|250,000|2|FD-Hash|5.122793|5.058731–5.166962|9|3|
|keys|250,000|2|FD-Hash-Cover|0.892253|0.885486–0.909344|9|3|
|keys|250,000|4|BCNF-Index|0.704476|0.700018–0.715567|9|3|
|keys|250,000|4|FD-Hash|5.622151|5.583082–5.652574|9|3|
|keys|250,000|4|FD-Hash-Cover|1.406052|1.401968–1.424535|9|3|
|keys|250,000|8|BCNF-Index|1.287494|1.274610–1.313158|9|3|
|keys|250,000|8|FD-Hash|6.506336|6.468650–6.555755|9|3|
|keys|250,000|8|FD-Hash-Cover|2.437659|2.405570–2.513697|9|3|
|keys|1,000,000|1|BCNF-Index|1.366486|1.353749–2.289020|9|3|
|keys|1,000,000|1|FD-Hash-Cover|2.909169|2.867665–3.692299|9|3|
|keys|1,000,000|2|BCNF-Index|3.087912|1.939659–3.201399|9|3|
|keys|1,000,000|2|FD-Hash-Cover|4.645315|4.101602–5.877228|9|3|
|legacy|1,000|1|BCNF-Index|0.000668|0.000643–0.000690|9|3|
|legacy|1,000|1|FD-Hash|0.003704|0.003627–0.003957|9|3|
|legacy|1,000|1|FD-Hash-Cover|0.001514|0.001444–0.001580|9|3|
|legacy|10,000|1|BCNF-Index|0.007827|0.007633–0.007970|9|3|
|legacy|10,000|1|FD-Hash|0.041252|0.041026–0.041377|9|3|
|legacy|10,000|1|FD-Hash-Cover|0.016540|0.015856–0.016796|9|3|
|legacy|100,000|1|BCNF-Index|0.092927|0.091898–0.094639|9|3|
|legacy|100,000|1|FD-Hash|0.455694|0.452068–0.458938|9|3|
|legacy|100,000|1|FD-Hash-Cover|0.183017|0.179601–0.185821|9|3|
|legacy|1,000,000|1|BCNF-Index|1.208682|1.196919–1.252103|9|3|
|legacy|1,000,000|1|FD-Hash|5.220131|5.102452–5.254530|9|3|
|legacy|1,000,000|1|FD-Hash-Cover|2.123948|2.119531–2.133104|9|3|

## Paired speedups over BCNF-Index

|Workload|Retained|Keys|Baseline|Median paired speedup|Pairs|Seeds|
|---|---:|---:|---|---:|---:|---:|
|keys|50,000|1|FD-Hash|19.622×|9|3|
|keys|50,000|2|FD-Hash|12.742×|9|3|
|keys|50,000|4|FD-Hash|8.130×|9|3|
|keys|50,000|8|FD-Hash|5.123×|9|3|
|keys|250,000|1|FD-Hash|18.462×|9|3|
|keys|250,000|2|FD-Hash|12.236×|9|3|
|keys|250,000|4|FD-Hash|7.986×|9|3|
|keys|250,000|8|FD-Hash|5.074×|9|3|
|legacy|1,000|1|FD-Hash|5.573×|9|3|
|legacy|10,000|1|FD-Hash|5.269×|9|3|
|legacy|100,000|1|FD-Hash|4.904×|9|3|
|legacy|1,000,000|1|FD-Hash|4.351×|9|3|
|keys|50,000|1|FD-Hash-Cover|2.507×|9|3|
|keys|50,000|2|FD-Hash-Cover|2.235×|9|3|
|keys|50,000|4|FD-Hash-Cover|2.073×|9|3|
|keys|50,000|8|FD-Hash-Cover|1.948×|9|3|
|keys|250,000|1|FD-Hash-Cover|2.379×|9|3|
|keys|250,000|2|FD-Hash-Cover|2.132×|9|3|
|keys|250,000|4|FD-Hash-Cover|2.000×|9|3|
|keys|250,000|8|FD-Hash-Cover|1.894×|9|3|
|keys|1,000,000|1|FD-Hash-Cover|2.098×|9|3|
|keys|1,000,000|2|FD-Hash-Cover|1.889×|9|3|
|legacy|1,000|1|FD-Hash-Cover|2.247×|9|3|
|legacy|10,000|1|FD-Hash-Cover|2.075×|9|3|
|legacy|100,000|1|FD-Hash-Cover|1.954×|9|3|
|legacy|1,000,000|1|FD-Hash-Cover|1.757×|9|3|

## Interpretation and limits

The equivalent-cover baseline controls for redundant FD syntax; compare it separately from raw per-FD hashing. The key-count control fixes 16 attributes and 16 input FDs, and varies q independently. Both covers are checked for implication equivalence. Small-schema preprocessing is measured separately and is not claimed as a new key-discovery contribution.

Results are from the existing Python prototype on this machine and controlled synthetic data. The original static curves included tracemalloc during timing; the new times should not be silently mixed with those times. Their experimental conditions and timing boundaries differ. Memory-guarded omissions are not timeouts and are not evidence of algorithmic failure. Extrapolation to a production database engine requires the planned SQL/benchmark-derived experiment.

## Exact reproduction

```powershell
python -m unittest test_supplement -v
python -u run_static_supplement.py
python summarize_static.py
```

Run in a fresh output directory or archive an existing run first: raw records are append-only and the analysis rejects duplicate measurement keys.

Raw SHA-256: `cb904e09666a37f5f6c15426bb8d2a37c8e236b27ff782fa26db9fb49024a58e`.
