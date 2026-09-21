---
req: REQ-c48f99
title: 会话框业务工具节点可读性改造（定制卡片 + 人话摘要）
category: feature
status: archived
created: 2026-09-21
window: w-85447f15
---

# REQ-c48f99 会话框业务工具节点可读性改造

## 背景与证据

审计报告：`docs/work-logs/2026-09/session-node-display-audit.md`（样本=REQ-4842fe 源会话
session-d41c9696，4127 条事件全量分析 + 渲染源码核对）。核心实证：

- agent-dh 全部业务工具在会话框回落 GenericToolCard 的 others 类：**折叠行摘要 = 工具名 +
  args 第一个字符串参数**——76 行 reqboard_task_move 折叠态全部显示 `reqboard_task_move · t-b0b327`，
  看不出 to=开工/完工/送测；
- 业务工具结果 = 裸 JSON 文本墙（全仓 39 处 `JSON.stringify` render，最大单节点 20.7KB）；
- 用户复核后指示：立项修改。

**spike 已结案（2026-09-21，本窗口）**：`tool.call.toolview` 是 keyed session 级插槽，任何声明
`dsh.client` 的插件均可在 client 半边 `ctx.slots.inject("tool.call.toolview", …)` 注册
（ui-tool 的 ask-question/todo toolview 即此模式）；dsh-pmboard 已声明 dsh.client（inject 含 slots）
且 client 全局加载，已有会话注入先例（conversation-progress.ts 占用 conversation.session.header.utilities）。
**方案 B 可行，无需降级。**

## 产品定义

让会话框里 agent-dh 业务工具节点「折叠态一眼看懂动作、展开态首行即人话」——
把当前"工具名+无意义参数首行+裸 JSON"的毛坯展示，升级为带中文动作摘要的定制卡片。

## 用户与角色

- **主要用户**：人类用户（看会话框复盘 agent 行为、确认推进是否按预期）
- **次要用户**：其他窗口的 agent（回看自己/他人会话做归因时，节点内容即证据）

## 功能点

### FR-1: 业务工具定制卡片注册通道
dsh-pmboard client 新增 toolviews 模块，经 `tool.call.toolview` keyed 插槽为首批 9 个
高频业务工具（reqboard_task_move/submit/ask_confirm/status/capture、memory_write、
decision_audit、portfolio_trade、watch_manage）注册定制行组件。

### FR-2: 折叠行=中文动作摘要
定制卡片折叠行显示动作化摘要（如 `t-b0b327 → 完工`），同一工具连续多次不同参数的调用，
折叠行文案必须两两可区分。

### FR-3: 展开体=结构化字段
定制卡片展开体显示结构化关键字段（from→to、reason、状态等），不再是裸 JSON 全文。

### FR-4: 畸形数据兜底不白屏
keyed 命中会替换通用行，卡片组件对缺 argsRaw、结果 JSON 解析失败、error 态必须自行渲染
兜底行（工具名+参数首行+输出首行），禁止白屏或抛错中断会话渲染。

### FR-5: renderJson 人话首行
pmboard host 侧 render 升级为「首行中文摘要 + 空行 + JSON 明细」，13 个 pmboard 工具逐个
配 summarize；未注册定制卡片的工具经此也立即获得可读首行（通用卡输出区与错误摘要都取首行）。

### FR-6: 未注册工具零回归
bash/read/edit/run_code 等已有专用 variant 的工具展示与改前一致；todo_write 已有框架级
专用行（审计复核修正），不在本需求改动范围。

## 边界

1. **只做展示层**：不改任何工具行为、后端 API、会话事件模型。
2. **不动 DSH 框架**：长 turn 自动折叠、SUMMARY_KEYS per-tool 上游配置、会话级固定进度面板
   归方案 C，另行立项（如需）。
3. **todo_write 不在范围**：框架已有专用 toolview（审计复核修正）。

## 验收口径

1. 重启 profile 后的新会话里连续执行 3 次不同 `to` 值的 reqboard_task_move，
   **折叠行文案两两不同且含中文动作词**（如 `t-b0b327 → 完工`）；
2. reqboard_status 展开体**第一行是中文摘要**而非 `{`；
3. bash/read/edit 显示**零回归**（与改前肉眼一致）；
4. 定制卡片对畸形数据**不白屏**，回落为简化通用行。

## L3 轻路径依据 + 单向升级

走轻档依据：唯一关键未知（第三方插件能否注入 toolview 插槽）已由 spike 结案；改动面 =
1 个 client 模块 + render 约定，无新决策点、不动架构、不增子系统、不改数据模型。

**升级信号（任一出现立即停手升重档）**：toolview 组件需要新增 host 侧 API；需要改会话事件
投影逻辑；需要给工具 schema/结果新增持久化字段。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |

> 🔴 **未被接收（6 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6

<!-- reqboard:marks:end -->
