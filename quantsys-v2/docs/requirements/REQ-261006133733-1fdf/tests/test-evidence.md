# 测试证据（REQ-261006133733-1fdf）

**测试入口（唯一）**：`tests/test_data_validator_anomaly_detection.py`（16 条）
**命令与结果**：

```bash
$ ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q
16 passed
$ ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py tests/test_data_quality_job_guardrails.py -q
33 passed
notify-guard intercepted=0 egress=0 offenders=[]
```

## 1. 用例矩阵（design/test-cases.md T1–T15 → 实际用例）

| 设计编号 | 用例函数（节选名） | 断言要点 | 结果 |
|---|---|---|---|
| T1 | `test_three_state_normal_no_anomaly` | 平稳 40 行 → `ok=True` / `has_anomalies is False` / 无 error | ✅ |
| T2 | `test_price_anomaly_is_reported` | 价格 5σ 尖峰 → `price_anomalies` 非空、`z_score>3` | ✅ |
| **T3（缺陷直击）** | `test_volume_anomaly_is_reported` | 成交量尖峰 → `volume_anomalies` 非空、`total_anomalies≥1` | ✅ |
| T4 | `test_insufficient_data_is_unknown_not_clean` | 20 行 → `has_anomalies is None` / `insufficient_data` / message 文案保留 | ✅ |
| T5 | `test_detection_failure_is_not_clean_and_does_not_raise` | 仓储抛错 → `ok=False` / `None` / reason 含原因 / 不抛 | ✅ |
| T6 | `test_key_set_is_backward_compatible` | 三态八键齐备 | ✅ |
| T7 | `test_score_clean_gets_full_component` | 覆盖率 90% → 94.0 | ✅ |
| T8 | `test_score_with_anomaly_deducts` | 2/40 → 74.0 | ✅ |
| T9 | `test_score_insufficient_data_renormalizes` | 数据不足 → 92.5（**不是** 94.0） | ✅ |
| T10 | `test_score_detection_failure_gets_zero_component` | 失败 → 74.0 且必须留 error | ✅ |
| T11 | `test_consumer_counts_failure_as_issue` | 失败计入问题 + `anomaly_unknown` 留痕 | ✅ |
| T12 | `test_consumer_insufficient_data_not_an_issue` | 数据不足**不**计问题 + 单独计数 | ✅ |
| T13 | `test_summary_counts_three_states` | counts 1/1、问题清单仅失败那只 | ✅ |
| T14 | `test_audit_records_anomaly_and_unknown` | 有异常写 `type=anomaly`；失败写 `type=anomaly_detection_unknown` | ✅ |
| T15 | `test_static_no_truthiness_on_has_anomalies` | 全仓 `has_anomalies` 无真值语境 | ✅ |
| 补充 | `test_anomaly_state_helper_is_backward_compatible` | 缺 `ok` 键旧形按 A 态（既有 stub 不被误伤） | ✅ |

## 2. 红→绿（反例锁：证明这些锁真能抓住原缺陷）

| 锁 | 注入 | 结果 | 复原 |
|---|---|---|---|
| **L1** | 把成交量段改回 `for kline in klines:`（原缺陷） | **4 红**：`test_three_state_normal_no_anomaly`、`test_price_anomaly_is_reported`、`test_volume_anomaly_is_reported`、`test_summary_counts_three_states` | 复原后 16 passed；shasum 与注入前一致；`INJECT` 残留 0 |
| **L4/T15** | 注入一行 `if anomaly_info['has_anomalies']:` | `test_static_no_truthiness_on_has_anomalies` **红** | 复原后全绿 |
| **T7/T9 区分度** | （复核修正）覆盖率 100 → 90 | 修正后两态数值互异：94.0 vs 92.5 | —— |

## 3. 既有回归（改动未带坏别处）

```
tests/test_data_quality_job_guardrails.py                     17 passed
tests/infrastructure/test_service_factory_p2.py + tests/test_anomaly_detection_stage.py   20 passed, 1 skipped
数据质量链三件套（护栏 + 服务工厂 + 回测异常段）               37 passed, 1 skipped
```

## 4. 实跑证据（非单测）

- 抽样 20 只（K 线 ≥60 行）：`ok=False` = **0**；有异常 **19/20**；分布 `[0,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,3,4,4]`。
- 整跑（run 3382，success，331s）：`check_summary` 含 `anomaly_unknown_count=0`、`insufficient_history_count=402`。
- 对照 00:00 基线：报错 7995 → **0**；`data_quality_score` 95.01 → **86.28**；`stocks_with_issues` 748 → **4623**。
- 详见 [../notes/anomaly-recheck.md](../notes/anomaly-recheck.md)。

## 5. 测试口径的已知限制（如实登记）

1. **中文日志不能用 grep**：`logs/api.log` 中文为 `\uXXXX`，`grep 中文` 恒 0（假绿）→ 一律用 JSON 扫描。
2. **本需求首次把真实运行读数纳入证据**（run 3382），但它依赖人工触发；自然排班（每日 00:00）的复现属长期观察。
3. **pytest 环境用测试库**（`quant_test`）：抽样与整跑证据取自生产库（显式连接），与单测的库不同——单测不依赖库（全部桩定）。

## 6. 卡覆盖标注（covers，供覆盖度门禁对账）

本文件与用例文件覆盖以下全部任务卡（父卡与其研发/复核/测试子卡）：

covers: t-0a6461
covers: t-a75776
covers: t-af8fa3
covers: t-e8a5e3
covers: t-163105
covers: t-9dc9eb
covers: t-02907b
covers: t-0a6147
covers: t-b1dd5c
covers: t-da0215
covers: t-97f26c
covers: t-7463bd
covers: t-420a52
covers: t-45f50a
covers: t-0dd2ae
covers: t-9050ff

**对照说明**：单测（16 条）覆盖 t-0a6461 / t-b1dd5c 及其子卡；
三态消费探针与审计探针覆盖 t-163105 及其子卡；实跑复验（run 3382 等）覆盖 t-420a52 及其子卡。
