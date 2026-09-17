# t-0a1ad4 验收通过落点改 archived + archive_submit 放宽为 archived 可用

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
验收通过落点改 archived + archive_submit 放宽为 archived 可用

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
handleVerifyDecision(pass=true) 写 status=archived（pass=false 仍回 implementing）；reqboard_archive_submit 在 archived 态可调且仍按 ARCHIVE_DOC_RULES 校验；单测覆盖两项

## 上游产出摘要（dependsSummary）
- 状态机改造：新增 accepting→archived、移除 done 相关转移与门

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T16:57:02.875Z，窗口 session-24ded829-8d22-4e59-9318-bad027351335）

t2 验收落点改 archived

### 完成项

- handleVerifyDecision(pass=true) → status=archived
- archive_submit 前置放宽为 archived（done 兼容）
- 移除人点归档接口 /req/archive + handleArchive（归档自动化后失效）
- archive_submit 补写 archivePath（原人点归档承担的落章）

### 下一步

见 t6

---
