# LLM Paper Statistics (no interpretation)

## 1–4. Exp1 paired comparisons

- zhipu clean_vs_dirty: acc_a=1.0 acc_b=0.813333 diff=0.186667 CI=[0.164167,0.209167] McNemar p=7.41841e-68
- zhipu dirty_vs_valid_repair: acc_a=0.813333 acc_b=1.0 diff=-0.186667 CI=[-0.209167,-0.164167] McNemar p=7.41841e-68
- zhipu clean_vs_valid_repair: acc_a=1.0 acc_b=1.0 diff=0.0 CI=[0.0,0.0] McNemar p=1.0
- bailian clean_vs_dirty: acc_a=1.0 acc_b=0.735833 diff=0.264167 CI=[0.239167,0.289167] McNemar p=7.49068e-96
- bailian dirty_vs_valid_repair: acc_a=0.735833 acc_b=1.0 diff=-0.264167 CI=[-0.289167,-0.239167] McNemar p=7.49068e-96
- bailian clean_vs_valid_repair: acc_a=1.0 acc_b=1.0 diff=0.0 CI=[0.0,0.0] McNemar p=1.0

## 5. Answer-Critical Dirty accuracy

- zhipu: accuracy=0.533333 n=480
- bailian: accuracy=0.339583 n=480

## 6. Dirty+FD P/R/F1

- GLM-4-Flash: P=1.000000 R=0.672917 F1=0.804483 non-conflict-acc=0.997222
- Qwen3.7-Flash: P=0.721805 R=1.000000 F1=0.838428 non-conflict-acc=0.983178

## 7. Over-deletion Affected Candidate vs Checked

- GLM-4-Flash: Candidate-Affected=0.000000, Checked-Affected=1.000000, Candidate-Unaffected=1.000000, Checked-Unaffected=1.000000, Candidate-Affected-UNKNOWN=1.000000, Checked-Affected-UNKNOWN=0.000000
- Qwen3.7-Flash: Candidate-Affected=0.000000, Checked-Affected=1.000000, Candidate-Unaffected=1.000000, Checked-Unaffected=1.000000, Candidate-Affected-UNKNOWN=1.000000, Checked-Affected-UNKNOWN=0.000000

## 8. Residual checker detection / exposure

- GLM-4-Flash: detection=1.000000, unchecked_exposure=1.000000, checked_exposure=0.000000, unchecked_affected_qa=0.554054
- Qwen3.7-Flash: detection=1.000000, unchecked_exposure=1.000000, checked_exposure=0.000000, unchecked_affected_qa=0.276062

## 9. Final API completeness

- exp1_zhipu.jsonl: requests=4800 success=4800 failures=0 retries=139
- exp1_bailian.jsonl: requests=4800 success=4800 failures=0 retries=0
- exp2_overdeletion_zhipu.jsonl: requests=3136 success=3136 failures=0 retries=125
- exp2_overdeletion_bailian.jsonl: requests=3136 success=3136 failures=0 retries=0
- exp2_residual_zhipu.jsonl: requests=2072 success=2072 failures=0 retries=46
- exp2_residual_bailian.jsonl: requests=2072 success=2072 failures=0 retries=0

## Exp1 overall (category=ALL, n)

- zhipu clean: accuracy=1.000000 n=1200
- zhipu dirty: accuracy=0.813333 n=1200
- zhipu valid_repair: accuracy=1.000000 n=1200
- bailian clean: accuracy=1.000000 n=1200
- bailian dirty: accuracy=0.735833 n=1200
- bailian valid_repair: accuracy=1.000000 n=1200
