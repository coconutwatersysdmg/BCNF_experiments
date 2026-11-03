# BCNF 条件下子集修复检查实验代码

本仓库是论文《BCNF条件下的数据库子集修复检查问题研究》第 4.2–4.4 节的实验代码，产出正文图3（静态扩展性）、图4（函数依赖数量的影响）、图5（增量修复的局部更新性能）及 165.7 倍加速比数据；一条命令 `powershell -ExecutionPolicy Bypass -File scripts/run_final_pipeline.ps1` 即可重跑全部实验并重出图；环境为 Python 3.12 + `pip install -r requirements.txt`（numpy / pandas / matplotlib / Pillow / pytest）。

## 1. 仓库与论文的对应关系

| 仓库文件 | 论文位置 | 内容 | 生成脚本 | 数据文件 |
|---|---|---|---|---|
| `paper_figures/tif/fig1_static_scalability.tif` | 图3（4.2 节） | 三种算法在 \|r\|=10³–10⁶ 上的运行时间与内存 | `scripts/run_static.py` | `results/final/static.csv` |
| `paper_figures/tif/fig2_fd_scaling.tif` | 图4（4.3 节） | 非平凡函数依赖数量 1–15 的索引压缩与性能 | `scripts/run_sensitivity.py` | `results/final/sensitivity.csv` |
| `paper_figures/tif/fig3_incremental_locality.tif` | 图5（4.4 节） | 增量维护与静态重建的对比、访问冲突块条目数与耗时的关系 | `scripts/run_incremental.py` | `results/final/incremental.csv` |
| `paper_figures/tif/fig4_llm_data_quality.tif` | 图6（4.5 节） | LLM 结构化问答准确率 | `paper_figures/source/plot_llm_figures.py` | 读取同级 `llm_study/results/final/exp1_summary.csv` |
| `paper_tables/table_fd_prompt.csv`、`table_llm_checker.csv` | 表1、表2 | 冲突识别 P/R/F1、候选修复缺陷的影响 | `scripts/build_llm_paper_tables.py` | 同上（`llm_study/results/final/`） |

仓库内图片文件名 `fig1..fig4` 是从 1 开始的内部编号，与论文图号相差 2：`fig1`→图3、`fig2`→图4、`fig3`→图5、`fig4`→图6。

图6 与表1、表2 的问答实验在独立仓库 `llm_study` 中运行，本仓库只负责据其结果绘图与建表；两个仓库放在同一父目录下即可。

## 2. 复现 165.7 倍

论文 4.4 节报告的 165.7 倍对应 `swap` 更新、批大小 1000、`uniform` 冲突块分布这一组配置，由 5 个随机种子 × 100 个更新批次共 500 次独立运行得到。

```powershell
# 重跑该组配置（单机约 5–10 分钟）
python scripts/run_incremental.py --n 1000000 --seeds 1 2 3 4 5 `
  --block-distributions uniform --workloads swap --batch-sizes 1000 `
  --batches-per-config 100 --out results/final/incremental.csv `
  --config-out results/final/incremental_config.json

# 复算该数字（每批次加速比取中位数）
python -c "import pandas as pd; d=pd.read_csv('results/final/incremental.csv'); s=d[(d.workload=='swap')&(d.batch_size==1000)&(d.block_distribution=='uniform')]; print((s.static_total_time/s.incremental_total_time).median())"
```

固定条件：`--n 1000000`（即 |r|）、`--conflict-ratio 0.1`、`--key-width 1`、`--fd-count 4`、种子 `1 2 3 4 5`、每配置 100 批。随机性由 `--seeds` 决定，`common/reproducibility.py` 的 `set_global_seed()` 统一设置全局种子，不需要额外环境变量。

图5 的完整曲线用 `--block-distributions uniform zipf_1.2 --workloads d_only swap --batch-sizes 1 10 100 1000` 运行，即 `scripts/run_final_pipeline.ps1` 的第 5 步。

## 3. 目录结构

```
algorithms/      BCNF-Index、FD-Hash、Singleton-FullScan、Exhaustive 四种检查器 + 增量维护状态
common/          函数依赖工具、类型定义、度量、复现性工具
generators/      BCNF 模式生成、实例生成、冲突注入（数据全部由此生成，无需外部数据集）
scripts/         实验入口：correctness / static / sensitivity / incremental / 汇总 / 建表
paper_figures/   source（绘图脚本）、eps、tif、preview
paper_tables/    论文表1、表2 的 CSV
results/final/   论文引用的全部原始数据（CSV）与运行配置（JSON）
tests/           单元测试，含 500 例 key-cover 差分测试
dev/             开发期脚本与早期 LLM runner，非论文实验所需，不参与复现
```

## 4. 环境

Python 3.12：

```bash
pip install -r requirements.txt
python -m pytest tests -q        # 623 项测试应全部通过
```

实验数据不随仓库分发（体积大），由 `generators/` 按固定种子现场生成；`results/final/` 中保存的是论文引用的那一份数据，用于核对，不必重新生成。

## 5. 关键实现约定

- **算法只报告确定性结果**：`BCNFRepairChecker` 初始化时调用 `schema.validate_bcnf()`，模式不满足 BCNF 直接抛 `ValueError`，不回退到一般函数依赖算法。
- **S-repair 为包含极大**，不是基数最大。检查器通过只说明候选满足函数依赖且不可再扩充，不表示被保留的元组是“真实事实”。
- **计时口径**：增量实验的更新序列（`UpdateOp` 计划）在计时器之外预先生成，增量与静态重放同一批更新，两侧计时范围一致。
- **正确性门槛**：`results/final/correctness.csv` 记录 2000 个随机用例上 Exhaustive / Singleton-FullScan / FD-Hash / BCNF-Index 的判定一致性。

## 6. 引用

若使用本仓库代码，请引用论文《BCNF条件下的数据库子集修复检查问题研究》，计算机研究与发展。

## 7. 许可

MIT 许可，见 [`LICENSE`](LICENSE)。
