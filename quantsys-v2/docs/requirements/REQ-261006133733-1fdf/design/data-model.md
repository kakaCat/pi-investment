# REQ-261006133733-1fdf · 设计：数据层与契约

**结论先行**：**零 DDL、零迁移、零新表列、零开关**。新增信息全部落在既有的 **jsonb** 载体里
（审计表 `public.kline_data_quality.errors/warnings`、任务结果 `quant.scheduler_runs.result`）。

## 1. 是否改表 / 改 schema（serves: FR-3）

| 问题 | 答案 | 依据 |
|---|---|---|
| 新增表 / 列？ | **否** | 未知态与两个新计数都是"结果 JSON 里的键"，不是列 |
| 需要迁移脚本？ | **否** | 无 schema 变更 |
| 需要回填历史？ | **否** | 历史质量分/异常数**不追认**（它们是在缺陷下产生的假读数，改不了也不该改）；按「后续线 4」重新解读 |
| 需要开关 / 灰度？ | **否** | 纯代码路径；开关会制造"关掉就回到假读数"的隐性风险 |
| 有 DDL 回滚动作？ | **不需要** | 回滚 = 还原代码 |

## 2. 写入面 1：审计表 `public.kline_data_quality`（serves: FR-3）

| 项 | 值 |
|---|---|
| 写入者 | `application/services/data_quality_service._record_quality_check`（:498+）→ `KlineQualityRepository.record_check_result` |
| 表 | `public.kline_data_quality`（**注意**：不是 `quant.data_quality_records`——后者属 p1 批处理另一条线） |
| 本需求涉及的列 | `errors` (jsonb) / `warnings` (jsonb) —— **只往这两个 jsonb 数组里加元素** |
| 现状缺陷（一并修） | `:546` 读 `anomaly_info.get('anomalies', [])`，而返回里**没有** `anomalies` 键（真键是 `price_anomalies` / `volume_anomalies`）⇒ 异常**从未**进过审计 warnings（空转） |
| 改后写入的 warning 形态 | 异常：`{'type': 'anomaly', 'field': 'price'\|'volume', 'message': …}`；未知：`{'type': 'anomaly_detection_unknown', 'reason': 'insufficient_data'\|'<错误摘要>', 'message': …}` |

## 3. 写入面 2：任务结果 `quant.scheduler_runs.result`（jsonb）（serves: FR-3）

「每日数据质量检查」（task 232）把 `check_data_quality` 的汇总原样写进 `result`（实测今日那条
`result.details.details.check_summary` 就在里面）。本需求新增的键因此**自然落库**：

| 新键 | 类型 | 位置 | 含义 |
|---|---|---|---|
| `anomaly_unknown_count` | int | `check_summary`（与 `stocks_with_issues` 同级） | 因**检测失败**而未知的股票数 |
| `insufficient_history_count` | int | 同上 | 因**数据不足**而未知的股票数 |
| `anomaly_unknown` | bool | `stocks_with_issues[]` 每条 | 该股异常检测是否未知 |
| `anomaly_unknown_reason` | `str\|None` | 同条 | `insufficient_data` 或错误摘要 |

- **只增不改**：既有键（`stocks_with_issues` / `checked_stocks` /……）一个不删；
  消费者忽略未知键即可（jsonb 无 schema 约束）。
- **已被观察到的既有事实**：`quant.data_contracts` 里对质量相关数据集有行数/新鲜度契约，
  但**不涉及**这些键 → 无契约冲突。

## 4. 质量分口径变化（读数契约）（serves: FR-4）

| 检测态 | 异常率分量 | 对总分的影响 |
|---|---|---|
| 有异常 | `max(0, 20 - anomaly_rate*4)` | 既有 |
| 确无异常 | `20` | 既有 |
| 数据不足 | 剔除并重新归一 `(coverage+dup)/80*100` | 与"确无异常"相比可能少 0–20 分，但**不惩罚历史短** |
| 检测失败 | `0` | 最多 −20 分，且**必然**伴随一条 error + 一个 `anomaly_unknown` 计数 |

- **可观测**：分量的取值不再隐含（失败有日志、未知有计数）；不再存在"恒得满分"的路径。
- **对下游阈值的影响**：job 的告警阈值（如 `quality_threshold=95.0`）**不改**；
  改后分数下降属预期（架构 §6），若阈值因此频繁触发，属**另一项决定**（不在本需求，登记）。

## 5. 读契约：`detect_anomalies` 的输入数据（serves: FR-1）

| 项 | 值 |
|---|---|
| 数据源 | `KlineORMRepository.get_daily_klines(symbol, start, end)` → **polars DataFrame** |
| 最小行数 | **30**（既有门槛，不改）：`is_empty()` 或 `len < 30` → 走 B 态（数据不足） |
| 列依赖 | `close` / `volume` / `trade_date`（成交量仅统计 >0 的行，既有逻辑不变） |
| 本次改动 | **不改**取数、不改过滤、不改统计量（mean/stdev） |

## 6. 不写什么（负向契约）（serves: FR-2, FR-3）

1. **不写"未知 = 干净"**：任何路径都不许把 B/C 两态落成 `has_anomalies=False`。
2. **不新增 `quant.*` 表/列/索引**；不写 `data_quality_records`（属另一条线）。
3. **不落"每只股票一条 error 行"到库**：失败只走日志 + 汇总计数（今日 7995 条是日志，不是表行）。
4. **不改历史行**：已写入的 `kline_data_quality` 历史 warnings 保持原样。
