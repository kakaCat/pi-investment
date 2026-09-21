---
req_id: REQ-c48f99
doc: design/architecture
serves: FR-1, FR-4
status: design
---

# REQ-c48f99 设计 · 架构：client 定制卡片 + host 人话首行

## 1. 总体方案  `serves: FR-1, FR-5`

两条互不依赖的改动线，同需求交付：

- **线 1（定制卡片，FR-1~FR-4）**：dsh-pmboard client 新增 `src/client/toolviews/` 模块，
  经 `ctx.slots.inject('tool.call.toolview', …)` 为首批 9 个高频业务工具注册 keyed 行组件。
- **线 2（人话首行，FR-5）**：pmboard host 侧 `renderJson` 升级——返回文本首行为中文摘要，
  后附 JSON 明细。通用卡输出区与 errorSummary 均取首行，**未注册卡片的工具也立即受益**。

**选址决策**：卡片注册放 dsh-pmboard client（已声明 dsh.client + slots inject + 全局加载 +
wrap/verify 构建链齐备，零新基础设施）。卡片只读会话事件 block 数据，与 pmboard 业务域无耦合。
否掉"新建 session-toolviews 插件包"：轻档不增新包，模块长大后可再拆。

## 2. 模块结构  `serves: FR-1, FR-4`

```
src/client/toolviews/
├── index.ts        # bizToolviews = { name:'biz-toolviews', inject:['slots'], apply(ctx){…} }
│                   #   在 client/index.ts 的 apply() 里注册全部 9 张卡片
├── shared.ts       # parseArgs(block)/resultText(block)/resultJson(block) 纯函数
│                   # + BizRow 通用行布局（icon+标题+摘要+chevron，展开体）
│                   # + fallbackRow()：解析失败时的简化通用行（FR-4 兜底）
└── rows/
    ├── task-move.ts      submit.ts        ask-confirm.ts
    ├── status.ts         capture.ts       memory-write.ts
    ├── decision-audit.ts trade.ts         watch-manage.ts
```

技术约束：只用 react（external，shell 种子提供），**禁止新增 bare npm 依赖**（pmboard client
自包含原则）；样式走注入 <style>（styles.ts 同款），不用 CSS module（wrap 链不吃）。

## 3. 关键机制（spike 已核实）  `serves: FR-1, FR-4`

- `tool.call.toolview` 是 keyed、session 级插槽（ui-tool 注册 ToolCallTree 时声明
  `children: { 'tool.call.toolview': { kind:'keyed', scope:'session' } }`）；
- 注册即替换：keyed 命中**替换** GenericToolCard（框架注释明示）→ 组件必须自带兜底（FR-4）；
- pmboard client 已有同类先例：conversation-progress.ts 占用 conversation.session.header.utilities；
- 构建链：`pnpm build:client`（tsdown → wrap-client.mjs → verify-client-build.mjs，
  WRAP_SENTINEL 门禁必须过，禁止逐行字符串变换——2026-09-16 wrap 污染教训）。

## 4. 风险与回滚  `serves: FR-4, FR-6`

| 风险 | 应对 |
|---|---|
| keyed 命中替换通用行，卡片 bug 直接遮信息 | fallbackRow 兜底 + 单测四档输入；出错只影响该行 |
| client bundle 增大 | 9 卡片均为小组件，预估 +15KB min 内 |
| 框架升级改 slot 契约 | 注册集中在 index.ts 一处，适配面小 |
| 回滚 | 摘除 index.ts 注册行 + render 复原，无状态残留 |
