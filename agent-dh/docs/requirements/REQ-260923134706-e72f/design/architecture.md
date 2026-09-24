---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10]
sides: [frontend, backend]
---

# 架构设计（REQ-260923134706-e72f）会话流程节点详情弹框重构

> 读者：工程/agent。设计基线 = `packages/web/dsh-pmboard/stage-modals-alpine.html`（用户已定稿的交互原型，可点击）。
> 一句话目标：会话顶部流程图的节点详情弹框，从"纯文字流水账"重做为"锚定式下拉面板 + 两层头 + 基础信息/执行流程双折叠"，
> 其中执行流程是**规定 vs 实际**的合规对照（规定=阶段提示词原文，实际=台账留痕）。

## 1. 目标与改动面 <!-- serves: FR-1, FR-2, FR-3 -->

改动面 = pmboard 插件内：新增 2 个 client 渲染模块 + 1 个 client 样式分片 + 1 个 host 只读路由；
改 3 个既有文件（conversation-progress.ts / styles.ts / stages.ts / routes.ts / index.ts 为接线级小改）；
改 6 份 brainstorming 模板（FR-10）；新增 3 个测试文件。
**不动**：`src/client/stage-panel.ts`（另一窗口有在途改动与测试锁定，本需求新增模块而非改造它）、
协议枚举、看板其他页面、数据表结构。

## 2. 总体结构与数据流 <!-- serves: FR-1, FR-6 -->

```
会话标题栏槽位 conversation.session.header.utilities
  └─ RequirementProgressAction（conversation-progress.ts，React）
       ├─ 流程条（既有，dsh-pm-flow-*，不动）
       └─ 锚定面板（.dsh-pm-cprog-detail-panel 既有定位壳 + × 关闭按钮）
            └─ dangerouslySetInnerHTML = renderNodePanel(input)   ← 纯函数，零 IO
                 ├─ .dsh-pm-np-req（REQ 胶囊 + 标题）
                 ├─ .dsh-pm-np-head（状态胶囊 + 一句话 + 相对时间）
                 ├─ <details> ℹ️ 基础信息（默认 open；实施节点无此块）
                 └─ <details> 🔄 执行流程（默认收起）
                      ├─ 📝 提示词注入 ← injection-log（已有端点）
                      ├─ ⚙️ 执行动作对照 ← STAGE_PROCESS.check(StageDetail)
                      └─ 🗜️ 上下文管理 ← isolation-log（新端点）

数据：
  StageOverview        ── fetchStageOverview（既有）
  requirement 标题/难度 ── session progress（既有端点 + 一个字段）
  注入留痕             ── injection-log（既有端点，client fetchInjectionInfo 已有）
  隔离留痕             ── isolation-log（新增只读端点，照抄 injection.ts 形状）
```

## 3. 模块清单与职责 <!-- serves: FR-1, FR-3, FR-6, FR-8 -->

| 文件 | 新增/改动 | 职责（一句话） |
|---|---|---|
| `src/client/node-panel.ts` | 新增 | 面板纯渲染器：面板头两层 + 基础信息折叠 + 各节点专属内容 + DAG/泳道 |
| `src/client/node-panel-process.ts` | 新增 | 「执行流程」：STAGE_PROCESS 对照表（规定）+ 对 StageDetail/留痕求值（实际）+ 渲染 |
| `src/client/styles/node-panel.ts` | 新增 | `.dsh-pm-np` 作用域内的苹果风样式（720px/68vh/胶囊/细线/泳道） |
| `src/client/styles.ts` | 改动 | 拼接链末尾追加 NODE_PANEL_CSS（不动既有分片） |
| `src/client/conversation-progress.ts` | 改动 | 面板改用 renderNodePanel；面板头换成 REQ 胶囊行；去底部三按钮；加 × ；拉取 isolation-log |
| `src/client/api.ts` | 改动 | 新增 fetchIsolationLog（照抄 fetchInjectionInfo 形状） |
| `src/http/routers/isolation.ts` | 新增 | GET isolation-log 只读路由（照抄 injection.ts） |
| `src/http/routes.ts` | 改动 | 注册 isolation-log 路由 + deps 接线 |
| `src/http/routers/stages.ts` | 改动 | progress 的 requirement 对象补 promptDifficulty 字段 |
| `src/index.ts` | 改动 | 把已构造的 isolationTrace 以只读端口身份传入路由 deps（injectionLog 同款） |
| `templates/brainstorming/*.md` | 改动×6 | FR-10：补门禁认得的条款定义形态 + bug 模板去 G1/G2 + feature 模板与文档集策略对齐 |
| `src/client/stage-panel.ts` | **不动** | 另一窗口在途；新面板不复用其渲染器，避免合流冲突 |

## 4. 关键决策与理由 <!-- serves: FR-1, FR-6, FR-9 -->

- **新模块而不是改 stage-panel.ts**：该文件正被另一窗口改（artifact-labels 收敛）且测试锁定；新模块零冲突，旧 renderStageNode 保留给既有测试，不删。
- **折叠用原生 `<details>`**（本仓既有约定 .dsh-pm-fold 同款机制）：面板经 dangerouslySetInnerHTML 注入，零 JS 依赖、天然键盘可达；15s 轮询仅在数据真变时重渲染，折叠态重置为默认（基础信息开/执行流程收），与设计稿一致。
- **泳道/DAG 不复用 views/stage-detail.ts 的 buildDag/buildTaskColumns**：那两个渲染器服务于需求详情页（六列看板 + 子卡折叠），与本设计的"横向泳道"形态不同；node-panel.ts 自带轻量实现，类名全在 .dsh-pm-np 作用域内，不碰全局样式。
- **执行动作用"合规对照表 + 真实留痕求值"，不接工具调用日志**：PTC 模式下内部工具调用统一呈现为 run_code 且不落库，拿不到"窗口调了什么"；而 artifacts/timeline/tasks.executions/isolation 是持久、按节点切分、可核验的真实记录。
- **去底部三按钮**：设计稿形态（× 关闭 + 点外部关闭）；打开看板入口保留在侧边栏与看板页（FR-9）。

## 5. 数据层与回滚 <!-- serves: FR-6 -->

- **不改表、不改 schema、无迁移**：两个留痕数据源（prompt-injection-log.json / node-isolation-log.json）是既有 ring buffer 文件，只读。
- 新增端点只读，不写任何状态；progress 增量字段是既有字段的透传。
- **回滚**：client 回退 conversation-progress.ts + styles.ts 即可（新模块成为死代码，无渲染入口）；host 端点是纯增量，留着无害、删路由即回滚；模板改动回滚 = git revert（FR-10 的守护单测同步回滚）。
