# t-d24cfb 落码表与裁决结果契约（EscalationCode + Verdict）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
落码表与裁决结果契约（EscalationCode + Verdict）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/services/test_watch_escalation_verdict.py -q -k code_table 全绿；python -c 断言 len(EscalationCode.ALL)==15 且 set(PATH_LABEL)==set(ALL)，退出码 0；对 Verdict 赋值抛 FrozenInstanceError。

## 实施方案（implementation）
新建 domain/watch/services/escalation_verdict.py：先落 EscalationCode（15 个受控码 + ALL + PATH_LABEL 映射）与 frozen dataclass Verdict(should_wake, code, reason, path, note) 及 overridden()；不写裁决逻辑。测试 tests/services/test_watch_escalation_verdict.py 先写码表断言（15 值、PATH_LABEL 覆盖全部码、Verdict 不可变）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T10:46:28.113Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

落成升级裁决的词表与结果契约：新增 EscalationCode（15 个受控码，叫与没叫两侧都在内）与冻结的 Verdict（should_wake 由码派生，覆盖走 overridden 且保留原判）。

### 完成项

- 码表 15 值：叫侧 6 个 + 没叫侧 6 个 + 覆盖 2 个 + UNKNOWN
- ALL 由 PATH_LABEL 派生，避免码表两处手写漂移
- Verdict 冻结；should_wake 按码强制归一（不许自相矛盾）
- 未受控码归一为 UNKNOWN 并把原文留在 note（禁止臆造理由）
- overridden 返回新实例并把原判写进理由文本
- 验收：pytest -k code_table 4 passed；断言 exit 0；FrozenInstanceError 已验

### 改动文件

- `domain/watch/services/escalation_verdict.py`
- `tests/services/test_watch_escalation_verdict.py`

### 下一步

t2 在本契约上实现 decide_escalation 的 15 条判据顺序表与 decide_escalation_paths。

---
