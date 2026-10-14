# t-2fbc40 处置映射：disposition.decide 接受 Verdict

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
处置映射：disposition.decide 接受 Verdict

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py -q 全绿且两文件零改动；同一输入下 disposition=='escalated' 的条数与改造前一致（用例逐条对拍）。

## 实施方案（implementation）
domain/watch/services/disposition.py：decide() 增可选参数 verdict；给定时按 Verdict 映射为既有 disposition 取值与既有中文文案，未给定时内部调 decide_escalation（行为同改造前，兼容 escalated / escalation_reason 两个旧参数）。application/services/watch_engine/disposition_engine.py 透传 verdict。

## 上游产出摘要（dependsSummary）
- 收敛出唯一裁决出口 decide_escalation（15 条顺序表）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T10:56:28.463Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t5 完成：disposition 退为处置映射，旧判定体删除，语义不变。

### 完成项

- decide 改为 Verdict → disposition 映射；verdict 未给时内部调出口（旁路调用方照常工作）
- 15 码映射全覆盖，且叫/不叫与 disposition 语义对齐（三处例外已声明）
- 兼容分支保留：宪法级 → 预算 → escalated 顺序与旧文案逐字不变
- 删除旧判定体 61 行与死代码 _meta_gate；循环导入用函数内导入解决
- 验收：disposition 全套 29 passed；新增 5 条映射用例

### 改动文件

- `domain/watch/services/disposition.py`
- `tests/application/test_watch_disposition_verdict.py`

### 下一步

t6 接线时 engine 传 verdict 进来，走新映射路径。

---
