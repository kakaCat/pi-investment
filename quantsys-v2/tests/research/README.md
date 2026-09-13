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
| `event_study.py` | 财报事件（PEAD） | 事件 +1.43% vs **安慰剂 +0.75%** → 伪影 |
| `event_type_study.py` | 公告事件类型（并购/增减持/监管/定增） | 均值正但**中位数全为负 + 头部贡献 118%~2945%** → 伪影 |

## 运行方式

```bash
cd quantsys-v2 && source activate-py313.sh
python tests/research/event_type_study.py --help
```

> 依赖本地 `quant_investment` 库与 min_bars 足够的历史数据。
> 注意：这些脚本的 `ROOT` 已随目录迁移改为 `parents[2]`（迁移时踩到过路径基准漂移）。
