# t-ddb59a 补告警口径用例与四条反例锁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
补告警口径用例与四条反例锁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
① ./venv/bin/python -m pytest tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py -q 全过；② 任务汇报里附 L1-L4 改前红/改后绿的两次输出（L1 改前返回 806、L3 改前 original_count==0、L4 改前目标含 5 只已退市），缺一即视为锁无效。

## 实施方案（implementation）
① 新建 tests/test_data_quality_alert_scope.py，实现设计 test-cases 文档 §1 的 T8-T17：域内均值与 D 计数（不含存量）、阈值双向边界（20/21、88.0/87.9）、掉出名单与 20 只截断不冒充 count、回填样本门槛（n=7 不判 / n=10 判）、回填目标限域、original_count 非 0、count_by_grade_on 去重、partial 截断标注、per_symbol 缺失降级；② 更新 tests/test_data_quality_job_guardrails.py:70 的替身 check_data_quality，补 per_symbol；③ 四条反例锁 L1-L4 在改动前的代码上各跑一次并保留输出。

## 上游产出摘要（dependsSummary）
- 作业层接线：域内聚合、新告警判据与回填限域

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T08:55:03.655Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

t6 完成：告警口径用例与两条反例锁交付，既有护栏用例适配后无回归。

### 完成项

- tests/test_data_quality_alert_scope.py 12 条覆盖 T8-T17，含 L1（同日两行不翻倍）与 L2（旧口径必误报）两条反例锁
- 既有 tests/test_data_quality_job_guardrails.py 替身同步适配（补 per_symbol 与 kline_repo、4 处新签名）后 17 条全过
- 四文件合计 59 passed，notify-guard 零外发
- 3 张子卡（研发/复核/测试）全部完成

### 改动文件

- `tests/test_data_quality_alert_scope.py`
- `tests/test_data_quality_job_guardrails.py`

### 下一步

t7 全市场实跑已复验，回填失败率一项未达标（已登记后续线）

---
