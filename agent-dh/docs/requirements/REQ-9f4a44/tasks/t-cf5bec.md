# t-cf5bec 单测与 13080 实测（含历史 done 兼容）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
单测与 13080 实测（含历史 done 兼容）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：test
- 端侧：fullstack

## 验收标准
vitest 全绿（含新转移/兼容/流程图断言）；13080 实测：造一个 accepting 需求 → 会话确认验收 → 状态直接 archived、无人工归档动作、流程图无 done、会话收到备料提示；含 done 的历史台账载入不报错

## 上游产出摘要（dependsSummary）
- 状态机改造：新增 accepting→archived、移除 done 相关转移与门
- 验收通过落点改 archived + archive_submit 放宽为 archived 可用
- 移除流程图与分类档案中的 done 节点
- 验收通过后注入"请准备归档材料"提示
- 看板：archived 且无 archive 产物显示"归档材料待补"

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T16:58:54.100Z，窗口 session-24ded829-8d22-4e59-9318-bad027351335）

t6 单测与实测：395 用例全绿 + 历史 done 兼容 + 新门禁链路实测

### 完成项

- 单测：8 个测试文件适配新流程（四道门/7 节点/accepting→archived/归档自动化），24 文件 395 用例全绿
- 实测 1（历史兼容）：重启后 18 个 legacy done 需求正常载入（MAIN 去 done、ALL_REQ_STATUSES 保留）
- 实测 2（新门禁）：decomposing→implementing 经 ask_user_question 确认 → confirm_artifact(via=session) → 放行成功
- 待验收环节实测：验收通过 → 直接 archived（即将执行）

### 改动文件

- `packages/pages/dsh-pmboard/tests/*（8 个测试文件）`

### 下一步

验收流程实测（验收即归档）

---
