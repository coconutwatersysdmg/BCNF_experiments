# dev — 开发期脚本

本目录不属于论文实验流程，复现论文结果不需要这里的任何文件。保留它们仅为记录开发过程中的诊断与早期实现。

| 文件 | 说明 |
|---|---|
| `run_diagnostics.py` | 开发期诊断：证书开销、增量计时口径的交叉验证 |
| `run_incremental_stress.py` | 增量状态的混合更新压力测试 |
| `run_formal.py`、`run_formal_pipeline.ps1` | 早期实验编排脚本，已被 `scripts/run_final_pipeline.ps1` 取代 |
| `plot_results_legacy.py` | 早期绘图脚本（Fig_A/B/C），已被 `paper_figures/source/plot_paper_figures.py` 取代 |
| `generate_llm_data.py`、`run_llm.py`、`legacy_llm/` | 早期的 LLM 问答实验实现，已被独立仓库 `llm_study` 取代 |

这些脚本的部分导入路径按仓库根目录书写，移动到本目录后可能需要在仓库根目录下用 `python -m` 方式运行，或自行调整 `sys.path`。
