# tests/research —— 假设检验脚本（**测试用**，非生产代码）

## 为什么在这里

用户 2026-09-13 裁定：**「脚本不能写到 v2 项目中，脚本只能测试用」**。
这些脚本的用途就是**检验假设**（某个信号到底有没有超额），属于测试，不属于生产依赖 ——
故从 `scripts/` 迁到 `tests/research/`。

## 边界（很重要）

· **生产链路不得 import 这里的任何文件**。可复用的评估引擎已上迁到
  `application/services/strategy_evaluation_service.py`（T+1 次日开盘、含成本、同池等权基准超额）——
  要评估策略请用那个，不要 copy 这里的代码。
· 这里只保留**一次性假设检验的可复现记录**。每条结论都已写进
  `docs/work-logs/2026-09/strategy-research-journal.md`（含窗口、样本量、口径、安慰剂对照）。

## 文件与结论索引（全部为负结果，这正是它们的价值）

| 脚本 | 检验的假设 | 结论 |
|------|-----------|------|
| `strategy_xsec.py` / `strategy_xsec2.py` | 横截面动量 / 反转选股 | 无超额（同池等权基准对照） |
| `strategy_industry_mom.py` | 行业动量轮动 | 倾斜效应 ≈ +0.29pp（噪声级）；多空价差 −0.14%/月 |
| `strategy_fund.py` | 基本面（ROE/估值）选股 | 无超额 |
| `strategy_tilt_ab.py` | 风格倾斜 A/B | 无法检验（本库仅 8 行风格数据，样本不足） |
| `placebo_diagnostic.py` | **方法自检**：度量本身是否有偏 | 随机 (标的,起始日) 20 日超额 = −0.004% → 度量无偏（安慰剂的高基线来自票池本身，不是度量 bug） |
| `event_study.py` | 财报事件（PEAD） | 事件 +1.43% vs **安慰剂 +0.75%** → 伪影 |
| `event_type_study_v2.py` | 公告事件类型（**全样本 + 样本外 + 双向聚类**，取代 v1） | 无任何做多类型可复现；唯一稳健结论是 **regulatory 显著为负** |

## 运行方式

```bash
cd quantsys-v2 && source activate-py313.sh
python tests/research/event_type_study.py --help
```

> 依赖本地 `quant_investment` 库与 min_bars 足够的历史数据。
> 注意：这些脚本的 `ROOT` 已随目录迁移改为 `parents[2]`（迁移时踩到过路径基准漂移）。

## 版本治理（2026-09-13）

- `event_type_study.py`（v1，薄样本）**已删除** —— 它跑在 m_and_a 70 条/27 个事件日的样本上，
  结论不足以定论；`event_type_study_v2.py` 用全样本（去重后 4.85 万条 / 207 事件日）取代，
  并补上了样本外切分与双向聚类。**保留旧版只会让人误引薄样本结论。**
- 全部脚本已逐个验证可执行（py_compile + argparse/import 链），结论索引见
  `docs/work-logs/2026-09/strategy-research-journal.md`。
