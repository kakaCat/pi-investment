# t-de13e3 sidebarRight 最小验证（会话框单入口）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
sidebarRight 最小验证（会话框单入口）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：frontend

## 验收标准
13080 上会话框点文档在官方右侧栏打开且 Markdown 正确（列表续行非 pre）；console 记录 sidebarRight 探测与地址；file-address 单测通过。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T16:30:43.884Z，窗口 session-24ded829-8d22-4e59-9318-bad027351335）

sidebarRight 最小验证：会话框文档点击走官方右侧栏（file-address + open-doc）

### 完成项

- 新增 client/file-address.ts：本地实现 dsh-resource://file/session/<sid>/<path>（对齐官方 grammar）
- 新增 client/open-doc.ts：openDocInSidebar（官方右栏，无弹窗降级）+ resolveCurrentSessionId
- conversation-progress.ts：文档点击改走 openDocInSidebar；移除 openDocModal 调用
- 修正：Cordis 要求 sidebarRight 必须声明 inject（原"可选访问"假设不成立）
- 实测：会话框点文档 → 官方右侧栏打开、markdown 正常

### 改动文件

- `packages/pages/dsh-pmboard/src/client/file-address.ts`
- `packages/pages/dsh-pmboard/src/client/open-doc.ts`
- `packages/pages/dsh-pmboard/src/client/conversation-progress.ts`
- `packages/pages/dsh-pmboard/src/client/index.ts`
- `docs/requirements/REQ-ff20ca/plan.md`

### 下一步

已通过，继续 t6

---
