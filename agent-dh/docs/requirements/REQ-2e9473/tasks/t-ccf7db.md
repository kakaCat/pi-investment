# t-ccf7db REQ 目录产物自动发现（W4）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
REQ 目录产物自动发现（W4）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：fullstack

## 验收标准
新文件落 docs/requirements/<REQ>/ 后详情页文档记录区自动出现（带自动发现徽标）；重复扫描幂等

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T10:04:25.712Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

REQ 目录产物自动发现落地（事故 E）：新增 sync-artifacts.ts——discoverArtifacts 纯扫描需求目录（文件名→种类：requirement/plan/decomposition/verification/archive/task_detail，其余归新增的 notes 种类），syncReqArtifacts/syncAllReqArtifacts 幂等落库（autoDiscovered 标记 + mtime + size + 评论留痕）。board 状态端点与 stage 详情/概览渲染前调用，"落进目录即产物"

### 完成项

- protocol.ts：ArtifactKind 增 notes（过程产物兜底，不参与任何 stage 闸门）+ StageArtifact 加 autoDiscovered/fileMtime/fileSize
- sync-artifacts.ts：kindForRelPath / discoverArtifacts（纯函数）/ syncReqArtifacts / syncAllReqArtifacts / reqDirRel
- routes.ts：handleState（board 状态）+ handleStageDetail + handleStageOverview 渲染前同步（扫描失败不阻断看板）
- 6 个新用例：种类推断/扫描带标记/已登记跳过/目录不存在不炸/落库幂等/全量扫描

### 改动文件

- `packages/pages/dsh-pmboard/src/shared/protocol.ts`
- `packages/pages/dsh-pmboard/src/host/sync-artifacts.ts`
- `packages/pages/dsh-pmboard/src/host/routes.ts`
- `packages/pages/dsh-pmboard/tests/sync-artifacts.test.ts`

### 下一步

t12（任务文件上浮+evidence 存在性+归档漏登）依赖本任务已就绪；t13/t17 也可推进

---
