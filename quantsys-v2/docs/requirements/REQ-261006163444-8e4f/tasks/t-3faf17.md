# t-3faf17 落盘迁移、兼容与回滚清单

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
落盘迁移、兼容与回滚清单

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
① 文档五节齐全且每节指到具体文件/行；② grep -c "零 schema" docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md ≥ 1；③ 旧调用方清单条数与 grep -rn "check_data_quality(" --include='*.py' 的命中数一致（9 处，含定义与同名异类）。

## 实施方案（implementation）
新建 docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md，写清五节：① 零 schema 变更的声明与依据；② 旧调用方核对清单（adapters/inbound/fastapi_app/routes/data_quality_async.py:162、tests/test_data_validator_anomaly_detection.py:212、tests/test_data_quality_job_guardrails.py:70 的替身）逐条结论；③ 配置旧值 quality_threshold=95.0 与回滚步骤（还原提交 + 改回 95.0）；④ 历史 original_count=0 行的阅读口径（2026-10-06 前不可用、不追改）；⑤ 部分回滚的两条路径与后果。

## 上游产出摘要（dependsSummary）
- 作业层接线：域内聚合、新告警判据与回填限域

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T08:56:30.766Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

t8 完成：迁移/兼容/回滚清单交付，含实跑复验与新发现。

### 完成项

- 交付 notes/migration-rollback.md：零 schema 变更声明与依据、旧调用方逐条结论、配置旧值与回滚、历史 original_count 阅读口径、部分回滚两条路径
- 第七节补记全市场实跑复验结果（4 项验收 3 过 1 不过）与新发现根因
- 2 张子卡（研发/复核）全部完成

### 改动文件

- `docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md`

### 下一步

回填目标选取与失败语义建议另开需求（见第七节）

---
