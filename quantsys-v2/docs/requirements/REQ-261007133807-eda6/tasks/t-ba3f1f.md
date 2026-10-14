# t-ba3f1f 卡面「升级原因」行（旧渲染 + 分级渲染两条路径）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
卡面「升级原因」行（旧渲染 + 分级渲染两条路径）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/notification/test_watch_escalation_reason_line.py -q 全绿；同一组变量喂两条渲染路径，两处「升级原因」行同形；escalation_code 与 reason 都为空时该行不出现；变量缺失（旧调用方）时输出与改造前逐字相同。

## 实施方案（implementation）
infrastructure/notification/formatters/watch_level_templates.py：WatchCardItem 增 escalation_code / escalation_reason 两字段，card_item_from_variables 取值，_skeleton_lines 在「处置」行后插入 _escalation_line；infrastructure/notification/formatters/feishu_formatters.py 旧渲染路径同样追加该行（同一条件表：无理由隐藏、只有码显示码）。行序保持 c392 四段契约不变。

## 上游产出摘要（dependsSummary）
- tick() 单链路接线（裁决 → 处置 → 去重覆盖 → 通知）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T11:13:57.552Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t9 完成：卡面「升级原因」行两条路径都写，四段子卡全绿。

### 完成项

- 两条渲染路径各追加「升级原因」行（旧渲染 + 分级渲染），同形同义
- 三种形态：码+理由 / 只有码 / 都没有（不渲染）；未收录码显示码本身
- 行序在「处置」与「下一步」之间，c392 四段动线未破
- 如实登记边界：P0 与 P1 首项有该行；P1 其余项与 P2/P3 聚合摘要为一方式，不显示该行
- 6 条用例 + 通知目录 93 passed

### 改动文件

- `infrastructure/notification/formatters/watch_level_templates.py`
- `infrastructure/notification/formatters/feishu_formatters.py`
- `tests/notification/test_watch_escalation_reason_line.py`

### 下一步

t13 端到端验收汇总。

---
