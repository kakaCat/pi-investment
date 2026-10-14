# t-9dc9eb 下游按三态处置：失败不当干净、数据不足不扣分·研发

> 需求：REQ-261006133733-1fdf 异常值检测静默失效：成交量段迭代错对象（每只必抛错、被 except 吞成无异常）

## 在做什么
下游按三态处置：失败不当干净、数据不足不扣分·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T05:44:41.442Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

研发阶段完成：下游按三态处置，失败计问题、数据不足只计数；审计空转同步修好。

### 完成项

- 交付物：application/services/data_quality_service.py（同一份三态判定 helper + 两处消费点 + 汇总两计数 + 审计留痕修复）
- 新增模块级 _anomaly_state(anomaly_info) → (failed, unknown, unknown_reason)：两处消费点共用，禁止真值判断
- check_data_quality 汇总实测：anomaly_unknown_count=1、insufficient_history_count=1、stocks_with_issues=1（清单只含失败那只 C）
- 「数据不足」不计入 has_issues（实测 B.SH 未被误判为问题）；「检测失败」计入（C.SH 条目 anomaly_unknown=True、reason=RuntimeError: boom-provider）
- 审计留痕修复实测：有异常 → warnings 写出 type=anomaly（price/volume 两条，改前恒为空转）；失败 → 写出 type=anomaly_detection_unknown
- validate_data_quality（第二处消费点）同规则 + 同两个计数（summary 内）
- 既有回归：tests/test_data_quality_job_guardrails.py 17 passed
- 静态：data_quality_service 内 has_anomalies 无真值判断（均 is True / is None）
- git diff --stat：data_quality_service.py 80 行变更
- 模板不符：本卡 acceptance 的 npx vitest 不适用本仓 Python 栈，改用 pytest 等价口径

### 改动文件

- `application/services/data_quality_service.py`

### 下一步

复核子卡独立审：两处消费点是否真的是同一份规则、计数是否漏计/重计、审计 warnings 是否与既有 error 列表冲突。

---
