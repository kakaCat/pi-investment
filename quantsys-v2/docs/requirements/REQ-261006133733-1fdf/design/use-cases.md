# REQ-261006133733-1fdf · 设计：用例与场景

**读法**：每个场景写清「触发 → 期望行为 → 可核验面 → 与改前的差别」。

## 1. 场景 A：普通股票，K 线充足且无异常（serves: FR-1, FR-2）

- **触发**：每日数据质量检查（task 232）扫到一只正常股票（40+ 行、价格量平稳）。
- **改前**：成交量段抛 `TypeError` 被吞 → 返回 `has_anomalies=False`（看起来"干净"）、
  且每条股票留一条 error（4 分钟 7995 条）；价格异常即使算出来也被一起丢弃。
- **改后**：`ok=True`、`has_anomalies=False`、`unknown_reason=None`、`total_anomalies=0`，**无 error**。
- **可核验面**：返回值三态；`grep -c 检测异常值失败` 归零。

## 2. 场景 B：真有异常（价格或成交量）（serves: FR-1, FR-4）

- **触发**：某股出现 5σ 的价格跳变或成交量尖峰。
- **改前**：**永远不会被发现**（检测恒失败）；质量分的异常率 20 分白送；`stocks_with_issues` 不含它。
- **改后**：`has_anomalies=True`，`price_anomalies` / `volume_anomalies` 给出日期与 `z_score`；
  质量分异常率分量按 `anomaly_rate` 扣分；审计 warnings 里出现 `type='anomaly'`；
  该股（若因此越过阈值）进入 `stocks_with_issues`。
- **可核验面**：T2/T3/T8/T14。

## 3. 场景 C：次新股 / 长停股（K 线 <30 行）（serves: FR-2, FR-4）

- **触发**：只有 20 行历史。
- **改前**：`has_anomalies=False`（"无异常"）——实际是"没法判"，但读数与"干净"无法区分；
  质量分仍白拿 20 分。
- **改后**：`ok=True`、`has_anomalies=None`、`unknown_reason='insufficient_data'`、
  `message` 保留既有文案；**不计入 `has_issues`**（新股不是质量问题）；
  质量分**剔除该分量并重新归一**（不奖不罚）；汇总计入 `insufficient_history_count`。
- **为什么这样定**：判"不适用"是业务事实，不该伪装成"无异常"（会让人以为检测过），
  也不该扣分（会把次新股一律打成低分）。
- **可核验面**：T4/T9/T12。

## 4. 场景 D：检测失败（取数异常 / 代码异常）（serves: FR-2, FR-3）

- **触发**：repo 抛错、或指标计算异常。
- **改前**：`has_anomalies=False` + `error` 字段（无人读）→ **失败 = 干净**，质量分白送 20 分。
- **改后**：`ok=False`、`has_anomalies=None`、`unknown_reason=<摘要>`；
  `has_issues` **计入**（当"待查"，宁可多查不得漏）；质量分分量 **0 分** + error 留痕；
  汇总 `anomaly_unknown_count` +1；审计 warnings 写 `type='anomaly_detection_unknown'`。
- **可核验面**：T5/T10/T11/T14。

## 5. 场景 E：人看质量报告 / 日报（serves: FR-3, FR-4）

- **触发**：人（或 agent）读当天的质量检查结果。
- **改前**：`data_quality_score=95.01`，其中 20 分是白送的；报错 7995 条淹没真信号。
- **改后**：分数里的异常率分量第一次有依据；汇总里能同时看到
  `anomaly_unknown_count` 与 `insufficient_history_count`（"没跑成"与"没得判"分开计数）；
  日志干净（无 7995 条）。
- **可核验面**：`quant.scheduler_runs.result` 里的新键（data-model §3）；
  读法变化写进验收材料，避免被当成回归（架构 §6）。

## 6. 场景 F：回滚（serves: FR-3）

- **触发**：改动引发不可接受的问题，需要退回。
- **期望**：还原提交即可（零迁移、零开关）；退回后行为 = "假阴性 + 7995 条日志"。
- **代价**：质量分重新白送 20 分、异常重新不可见——即回到本次要治的病。
- **可核验面**：回滚后重跑 T3 应重新变红（说明"退回的确实是旧行为"）。

## 7. 非目标：同型写法的一并处置（明确不做）（serves: FR-5）

- 全仓还有 10+ 处 `for kline in klines:`（E9），它们**未必**同病（取决于数据来源是 polars 还是 `list[dict]`）。
- 本需求**只登记不判定**（后续线 1）。理由：逐个溯源是独立工作量，且用户已裁定边界 B（D-2）；
  顺手改会造成"未验证的批量改动"，风险高于收益。
- 若要推进，应新开一项"数据层形态审计"：先出清单与定性，再分批判定修复。
