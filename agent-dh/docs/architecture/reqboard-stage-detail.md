---
id: reqboard-stage-detail
title: 需求节点详情系统（stage-detail）
summary: 会话框流程条节点点开看详情：StageDetail 契约 + 模板模式双端装配 + 分类流程档案 + 产物闸门 + 追溯链 + 接力任务卡 + 前端工作记录渲染器；含子任务层与自动链控制面（REQ-4842fe）。
type: architecture
status: living
updated: 2026-09-21
owners: [w-8913546f]
tags: [reqboard, stage-detail, gui, REQ-31e11f]
---

# 需求节点详情系统（stage-detail）

> 来源：REQ-31e11f。一句话：**点会话框流程条的节点，就地看到这个节点的工作记录**——
> 与看板同源同渲染器，不会脱节。

## 1. 解决什么问题

会话框顶部需求进度条原本只有节点名，不知道"agent 这一步干了什么、谁干的、产物在哪"。
本系统让每个节点可点开，展示该节点的**产物文档、拆分方案、实施列表（做到哪/做了多少/
还剩多少）、每个任务的执行者（窗口/subagent）与耗时**，可追溯、可点开文档全文。

## 2. 架构：契约单一定义 + 模板模式双端

```
shared/protocol.ts        domain：StageKey（8 节点）/ StageDetail 判别联合 / StageOverview（全览）
                          StageArtifact / STAGE_ARTIFACT_REQUIREMENTS / CATEGORY_FLOW_PROFILES
host/stage-detail.ts      application：StageDetailAssembler 模板基类 assemble()
                          （骨架：enabled/artifacts/pendingConfirmation/timeline + buildBody 可变步）
                          + 8 个节点装配器；assembleStageOverview() 一次装全 8 节点
host/routes.ts            GET /requirements/:id/stage/:stage（单节点）
                          GET /requirements/:id/stages（全览，监控用）
client/stage-panel.ts     presentation：StageRenderers 注册表 + renderStagePanel（单节点工作记录）
                          + renderStageNode(overview, stage)（看板/会话框共用入口）
```

**双端共享同一份 StageDetail shape**——新增节点只改 domain + 一个装配器 + 一个渲染器。

## 3. 关键概念

### 3.1 分类流程档案 CATEGORY_FLOW_PROFILES

6 类需求（feature/bug/doc/refactor/spike/chore）各自声明启用阶段子集与必备产物。
跳过的节点返回 enabled:false，UI 标灰"本分类跳过"，不算缺失。

### 3.2 产物闸门（两级校验）

① 产物存在门：缺必备产物拒绝转移（missing_artifact）；
② 人工确认门：产物已登记但未经人确认拒绝转移（artifact_not_confirmed）。
看板有 human-only 一键确认动作（POST /req/artifact/confirm）。

### 3.3 产物追溯链

需求→计划→拆分→任务卡→验收→归档，固定顺序渲染在节点面板头部，逐个可点开全文。
task_detail 汇总显示"任务卡×N"（任务列表里已有各自链接）。

### 3.4 接力任务卡（handoff）

decompose 时为每个任务生成自足任务卡（tasks/t-xxx.md：提示词/验收标准/依赖/执行方式），
新窗口/subagent 零会话历史即可开工；reqboard_task_report 追加执行记录
（completed/files_changed/next_step），幂等不重复登记。

### 3.5 阶段提示词钩子

状态转移后，绑定会话下一回合自动收到该阶段纪律提示词（stage-prompts.ts 插件内常量，
不走 skill）。

## 4. 前端渲染器 v4（工作记录风格）

设计原则（用户拍板）：**纯文字、零装饰、监控视角**——无 pill/徽章/卡片/底色块；
颜色纪律：正文黑 / 辅助灰 / 链接蓝 / 警示红。

- 面板头：状态一句话（"8/9 完成 · 剩 1 个 · 进行中 t-xxx"）+ 相对时间；
- 拆分节点：DAG 拓扑分层（第 N 层 · N 个可并行）；
- 实施节点：按状态分组（进行中/已完成/待开始），任务两行（标题行 + id·执行者·时间·任务卡链接行）；
- 评论/动态：聊天式（谁+时间在上，内容在下全宽）；
- 产物缺失：追溯链尾红字"（缺失）"。

### 4.1 文档弹窗（markdown）

点击产物链接弹窗看全文：marked 渲染（`{ gfm: true }`，**禁止 breaks:true**——它会把
列表延续行拆散、缩进误判为代码块）；overlay 用 vanilla DOM 挂 document.body
（React 内嵌会被父容器 stacking context 困住 fixed 定位）；click handler 挂 document 级
（挂组件 ref 上会在 detailOpen 切换时因 React 重建 DOM 丢失）。

两套弹窗（会话框 .dsh-pm-doc-overlay / 看板 .dsh-pm-doc-modal-overlay）**共享
.dsh-pm-md markdown 样式类**——2026-09-16 曾因两类名分裂导致看板弹窗样式裸奔。

### 4.2 版本戳纪律

弹窗标题带构建时间戳（如 md·19:15）。页面插件 bundle 由服务启动时读入内存，
**改完必须重启才生效**；用户看不到变化时先问"弹窗里有没有戳"——没戳 = 浏览器缓存旧包。

## 5. 部署注意（本 REQ 踩过的坑）

- client bundle（lib/client.js）由服务启动时读入内存，重启才生效；改完必须
  restart-with-build.sh（或 build:client + kickstart）。
- launchd 作业可能从 domain 消失（kickstart 报 "Could not find service"），此时端口被
  孤儿进程占着：先精确 kill 端口进程，再 launchctl bootstrap 重注册。
- 构建后必须跑 scripts/verify-client-build.mjs（括号配对 + 关键符号），防 styles.ts
  截断事故重演。

## 6. 子任务层与自动链控制面（REQ-4842fe，2026-09-21）

**一句话**：任务卡之下多了「子任务层」，由事件链自动推进；**看板是观察与控制面，不是必经入口**。

- **父卡开工懒展开**：`task_move → in_progress` 同事务按卡类型落子卡链（feature = 研发→联调→复核→测试，
  review 在前、测试在后；未知类型回退 研发→复核）。父卡**不存**子卡 id，由 `parentId` 反查（单一事实源）。
- **一张子卡 = 一次独立 workflow run**：`reqboard_task_run` → AdvanceChain → `ctx.workflowEngine`；
  引擎经端口 `WorkflowRunner` 隔离，引擎类型只出现在 `adapters/WorkflowEngineRunner.ts`（层边界）。
- **自动链（FR-11/FR-12）**：台账 `RequirementRecord.autoRun` + `advance{history,noopStreak,pausedReason}`；
  看板徽标四态 **运行中 / 已暂停 / 熔断 / 手动**（`autoRun` 缺省 = 存量需求，外观与推进方式不变）；
  控制面 `POST /dashboard/api/reqboard/req/autorun`——暂停=关开关；**继续=置开关并立即触发一次推进事件**
  （推进器未装配时接口如实说明，不伪装"已续跑"）。
- **门合并**：批准计划即批准拆分清单——批准后自动 decompose + autoRun=true + 触发首个事件，
  中途不再弹「确认拆分清单」；批准弹框写明"批准后将自动拆分并立即开跑"。
- **失败语义**：失败即**暂停**（不自动重试）并以**会话内弹框**请人三选一（重跑该卡 / 退回上游重描述 / 取消）；
  **不发飞书、不接通知面**（requirement §8 #17；弹框指令壳见 §8 #18）。

## 相关页面

- [需求看板实操](../guides/reqboard-workflow.md)
- [需求归档规范](requirement-archive.md)
- [页面插件契约](page-plugin-contract.md)
- 档案：docs/requirements/REQ-31e11f/（含 retro.md 复盘）
