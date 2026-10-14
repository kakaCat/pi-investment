# t-cba0af 作业层接线：域内聚合、新告警判据与回填限域·测试

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
作业层接线：域内聚合、新告警判据与回填限域·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T08:52:13.806Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

测试段完成：告警口径用例与反例锁全绿，既有护栏用例同步适配后无回归。

### 完成项

- tests/test_data_quality_alert_scope.py 12 条：域内均值/D 计数、阈值双向边界、掉出截断、回填门槛、限域选取、审计列、partial、降级
- 反例锁 L1（同日两行不翻倍）与 L2（旧口径必误报）已落成用例
- 既有 tests/test_data_quality_job_guardrails.py 17 条改造后全过（替身补 per_symbol 与 kline_repo）
- 四文件合计 59 passed；notify-guard intercepted=0 egress=0
- 如实声明：子卡模板给的是 pnpm test / tsc（本仓 Python），实际用 pytest 口径自证

### 改动文件

- `tests/test_data_quality_alert_scope.py`
- `tests/test_data_quality_job_guardrails.py`

---
