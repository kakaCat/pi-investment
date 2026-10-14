---
id: data-quality-anomaly-semantics
title: 数据质量：异常检测的三态语义与两个口径坑
summary: 「检测没跑成」不得写成「数据干净」——三态契约、polars 迭代陷阱、日志中文 grep 假绿；以及告警分母必须先说清（可交易域 / distinct 标的 / 阈值随口径重定）。
type: architecture
status: living
updated: 2026-10-06
owners: [project]
tags: [data-quality, anomaly, contract, pitfall, alert-scope, domain]
---

# 数据质量：异常检测的三态语义与两个口径坑

> 来源：[REQ-261006133733-1fdf](../requirements/REQ-261006133733-1fdf/requirement.md)（2026-10-06 验收归档）。
> 本页是 L2 结论；过程与逐条证据在 L3（该需求目录）。

## 1. 核心规则：「没跑成」不得写成「数据干净」

`DataValidator.detect_anomalies(symbol, start, end, threshold=3.0) -> Dict` 返回**三态**：

| 态 | `ok` | `has_anomalies` | `unknown_reason` | 语义 |
|---|---|---|---|---|
| A 正常 | `True` | `True` / `False` | `None` | 真的检测过 |
| B 数据不足（K 线 <30 行） | `True` | **`None`** | `'insufficient_data'` | 判定**不适用** |
| C 检测失败 | **`False`** | **`None`** | 错误摘要 | 判定**没跑成** |

**不变量**：`has_anomalies is False` **只**表示"真的检测过且没有异常"；
**禁止**用真值判断（`if info['has_anomalies']`）——`None` 也是假值，那就是把失败读成干净。
调用方一律写 `is True` / `is False` / `is None`。

**下游处置（两处消费点共用 `_anomaly_state`）**：
- 检测失败 → 计入 `has_issues`（当"待查"）+ `anomaly_unknown_count` + 审计 warning `anomaly_detection_unknown`；
- 数据不足 → **不计** `has_issues` + `insufficient_history_count`；质量分该分量**剔除并重新归一**（不奖不罚）；
- 确无异常 → 质量分异常率分量给满分；有异常 → 按 `max(0, 20 - anomaly_rate*4)` 扣分。

## 2. 坑一：迭代 polars DataFrame 产出的是 Series

```python
klines = repo.get_daily_klines(...)      # KlineORMRepository → **polars DataFrame**
for row in klines:                       # ❌ row 是 pl.Series
    row['volume']                        # → TypeError: cannot select elements using Sequence with elements of type 'str'
for row in klines.to_dicts():            # ✅ list[dict]
    row['volume']
```
后果：该异常被 `except` 吞成 `has_anomalies=False` ⇒ **异常检测 100% 假阴性**、质量分白送 20 分、
每只股票一条 error（实测 4 分钟 7995 条）。**任何"迭代取数结果"的地方都要先确认拿到的是 DataFrame 还是 list。**

## 3. 坑二：日志中文是 `\uXXXX`，grep 中文恒为 0（假绿）

`logs/api.log` 的中文被 JSON 转义（`检测异常值失败` → `\u68c0...`），因此：

```bash
grep -c "检测异常值失败" logs/api.log     # ❌ 恒 0 —— 看起来"没有错误"，实为匹配不到
```
**正确口径**：用 Python 解析 JSON 行并按 `event`/`timestamp` 统计（见需求目录 notes/anomaly-recheck.md §0）。

## 4. 现状读数（2026-10-06 修好后）

| 读数 | 旧（假） | 新（真） | 说明 |
|---|---|---|---|
| `检测异常值失败` | 7995 条/4 分钟 | 0 | 迭代修好 |
| `data_quality_score` | 95.01 | 86.28 | 异常率分量第一次有依据 |
| `stocks_with_issues` | 748 | 4623 | 多出"仅异常"一类 |
| 新增台账键 | —— | `anomaly_unknown_count` / `insufficient_history_count` | 失败与"没得判"分开计数 |

⚠️ **未决**：既有 `Z-score > 3` 阈值使 **4623/5686（81.3%）** 股票被判"有异常"（含除权/停牌/异动），
质量门禁的筛选价值因此被稀释。**阈值是否需要重定属独立议题**，本页只登记现象。

## 5. 检查域与告警口径：分母必须先说清（2026-10-06 补）

> 来源：[REQ-261006163444-8e4f](../requirements/REQ-261006163444-8e4f/requirement.md)（同日验收归档）。

**症状**：飞书收到「数据质量告警（3 项）」——D级 806 只 / 评分 86.28 < 95 / 回填失败率 71.4%。
**三项没有一项代表数据变差**，全是口径造的：

| 告警 | 表面值 | 真值 | 成因 |
|---|---|---|---|
| D级股票数量过多 | 806 只 | **404 只**（域内仅 1 只） | `count_by_grade_on` 数**行数**不数标的；当天跑 3 次 ⇒ 1207 行 / 404 只 |
| 数据质量评分偏低 | 86.28 | **90.87** | 分母含 403 只退市/长停标的（窗口内 0 数据） |
| 回填失败率过高 | 71.4% | 5/7，**分母无效** | 目标取自被截断的 50 条明细，7 只里 5 只已退市 |

**三条口径纪律**（新代码照此写）：

1. **分母必须是可交易域**。判据取**数据事实**：
   `gap = 标的最后一个有 K 线的交易日在交易日倒序里的名次 − 1`；`0 = 可交易域`、
   `1–4 = 观察中`、`≥5 = 存量`。**不要**用 `is_delisted` / `is_suspended` 标记定义域
   （实测标记只覆盖死标的的 46%，55 只停更标的全部未标）。
   实现：`application/services/kline_domain.py`（纯函数，无 DB 依赖）。
   ⚠️ **取交易日必须取够 5 个**：只取 2 个时 `gap 2–4` 的标的名次查不到，
   会被当成 `UNKNOWN_GAP` **静默丢进存量**（实测观察中假报 2 只 / 存量 404 只；取够后 3 / 403）。
2. **计数按 distinct 标的，不按行**。同一标的同一天可能写多行（同日多跑各写一行）。
   `KlineQualityRepository.count_by_grade_on` 已改 distinct；告警统计另改读本次 run 的
   `per_symbol`（全量，不受展示层 `stocks_with_issues[:50]` 截断影响）。
3. **分母口径变更必须同步重定阈值**。旧阈值 95.0 与旧口径的评分上限
   （`0.6×覆盖率 + 40` = 95.02）只差 0.02 分 ⇒ 等价于**永久红灯**。
   新阈值：域内 D级 > 20 / 评分 < 88.0 / 覆盖率仅信息项 / 回填失败率需**分母 ≥ 10** 才判。

**新增哨兵**：「本期掉出可交易域」（`gap == 1`）——新掉出必亮相（warning，不报 error），
连续 ≥5 个交易日转存量后不再逐日点名。**没有它，新口径会把「采集漏批」静默豁免**。
已知盲区：整条管道停摆时 `D_last` 本身滞后，本哨兵测不到（责任方 `freshness_guard`），
故告警正文恒打印最后交易日，让人一眼辨出。

**未决（本页只登记，不在该需求内解决）**：回填目标按"缺失天数降序"选，
实测 Top-50 全是 920xxx/688xxx 次新与北交所标的，其缺失段是**窗口起点起的那一段**
（数据源对上市前区间本就取不到）⇒ 回填 0/50、失败率 100%，新口径下每天仍会发 2 条 error。
解法方向：按标的**首条 K 线**裁剪回填区间；`backfill_failed` 区分
「数据源不可用」与「该区间本无数据」。
