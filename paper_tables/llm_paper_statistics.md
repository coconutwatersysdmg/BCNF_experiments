# LLM Paper Statistics (auto-generated; no interpretation)

## 1–4. Exp1 paired comparisons
- zhipu clean_vs_dirty: acc_a=1.000000 acc_b=0.813333 diff=0.186667 CI=[0.164167,0.209167] McNemar_p=7.41841e-68
- zhipu dirty_vs_valid_repair: acc_a=0.813333 acc_b=1.000000 diff=-0.186667 CI=[-0.209167,-0.164167] McNemar_p=7.41841e-68
- zhipu clean_vs_valid_repair: acc_a=1.000000 acc_b=1.000000 diff=0.000000 CI=[0.000000,0.000000] McNemar_p=1
- bailian clean_vs_dirty: acc_a=1.000000 acc_b=0.735833 diff=0.264167 CI=[0.239167,0.289167] McNemar_p=7.49068e-96
- bailian dirty_vs_valid_repair: acc_a=0.735833 acc_b=1.000000 diff=-0.264167 CI=[-0.289167,-0.239167] McNemar_p=7.49068e-96
- bailian clean_vs_valid_repair: acc_a=1.000000 acc_b=1.000000 diff=0.000000 CI=[0.000000,0.000000] McNemar_p=1

## 5. Answer-Critical Dirty accuracy
- zhipu: accuracy=0.533333 n=480
- bailian: accuracy=0.339583 n=480

## 6. Dirty+FD P/R/F1
- zhipu: P=1.000000 R=0.672917 F1=0.804483 non_conflict_acc=0.997222
- bailian: P=0.721805 R=1.000000 F1=0.838428 non_conflict_acc=0.983178

## 7. Over-deletion affected Candidate vs Checked
- GLM-4-Flash: Candidate-Affected=0.000000 Checked-Affected=1.000000 Cand-Unaffected=1.000000 Chk-Unaffected=1.000000
- Qwen3.7-Flash: Candidate-Affected=0.000000 Checked-Affected=1.000000 Cand-Unaffected=1.000000 Chk-Unaffected=1.000000

## 8. Residual checker detection / exposure
- GLM-4-Flash: detection=1.000000 unchecked_exposure=1.000000 checked_exposure=0.000000 unchecked_affected_acc=0.554054
- Qwen3.7-Flash: detection=1.000000 unchecked_exposure=1.000000 checked_exposure=0.000000 unchecked_affected_acc=0.276062

## 9. API completeness (formal files)
- exp1_zhipu.jsonl: success=4800/4800 failures=0
- exp1_bailian.jsonl: success=4800/4800 failures=0
- exp2_overdeletion_zhipu.jsonl: success=3136/3136 failures=0
- exp2_overdeletion_bailian.jsonl: success=3136/3136 failures=0
- exp2_residual_zhipu.jsonl: success=2072/2072 failures=0
- exp2_residual_bailian.jsonl: success=2072/2072 failures=0

## Exp1 n completeness (ALL)
- zhipu clean: n=1200 acc=1.000000
- zhipu dirty: n=1200 acc=0.813333
- zhipu valid_repair: n=1200 acc=1.000000
- bailian clean: n=1200 acc=1.000000
- bailian dirty: n=1200 acc=0.735833
- bailian valid_repair: n=1200 acc=1.000000
