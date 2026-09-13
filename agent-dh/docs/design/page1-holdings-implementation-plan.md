---
id: design-page1-holdings-implementation-plan
title: page1 账户持仓看板（dashboard-holdings）实施方案
summary: holdings 独立包补齐方案（已实施）：当时「包从未创建」缺口是怎么闭合的。
type: design
status: archived
updated: 2026-09-13
owners: [w-76653429]
tags: [design]
---

# page1 账户持仓看板（dashboard-holdings）实施方案

> **状态：archived（已实施，2026-09-14 标注）**：缺口已闭合，holdings 恢复为独立包并独占
> ``/dashboard/api/holdings``。现状以 [包 README](../../packages/pages/holdings/README.md) 为准。


> 日期：2026-09-04 · 作者：investor（agent:investor · w-76653429）
> 前置：dashboard-implementation-plan.md（双插件总方案）、dashboard-implementation-detail.md（实现细节）
> 状态：✅ 已实施（2026-09-04 按用户裁决 1B：holdings 独立包恢复为 /dashboard/api/holdings 唯一 owner；execution 中内联合并副本已剥离、client 注入 slots 修复）。原「包从未创建」缺口已闭合

---

## 1. 缺口澄清（为什么「应该是 2 个页面」）

总方案定义 dashboard 为 **2 个独立插件 / 2 页**：

| 页 | 插件 | 内容 | 现状 |
|---|---|---|---|
| page1 | `@pi-investment/dashboard-holdings` | 账户持仓看板（多账户摘要/持仓明细/今日自动交易/盯盘中心） | ❌ **包从未创建**（无目录、无 profile 注册、无 boot 入口） |
| page2 | `@pi-investment/dashboard-execution` | 双线执行确认看板（健康/检查点/时间轴/任务） | ✅ GUI 入口 + 中心栏视图已接线（本轮已重建重启） |

**page1 缺失 = 交付不完整**。本方案补齐 page1，与 page2 完全同构（双半插件），杜绝第 3 种实现方式。

## 2. 复用 page2 已验证架构（零新增模式）

page2 已在本仓库与真实 profile 验证全链路：官方侧栏槽位注册 → boot manifest → client bundle 加载 → 中心栏挂载 → API 数据。page1 **逐文件镜像** page2，仅替换「聚合数据来源」与「视图内容」：

```
packages/pages/holdings/                 # 新包 @pi-investment/dashboard-holdings
├── package.json                         # 同 page2（type module / dsh.client web / exports["./client"]）
├── tsdown.client.config.ts              # 同 page2
├── scripts/wrap-client.mjs              # 同 page2（复制）
├── src/
│   ├── index.ts                         # host 半：惰性注入 webServer → 注册 /dashboard/api/holdings
│   ├── routes/
│   │   └── holdings-routes.ts           # 薄路由：200 {success,data} / 500 {success:false,error}
│   ├── services/
│   │   ├── http.ts                      # 同 page2（复制，轻量 fetchJson/fetchData）
│   │   ├── portfolio-aggregation.ts     # ← 新逻辑：聚合多账户/摘要/持仓/交易/盯盘
│   │   └── name-map.ts                  # ← 新：代码→名称（v2 positions.name 为空，需补）
│   ├── types/
│   │   └── index.ts                     # HoldingsData 类型 + 端点契约注释
│   └── client/                          # GUI 半（镜像 page2 client，命名空间改 dsh-hld-*）
│       ├── index.ts                     # 注册侧栏入口 + 创建 controller + 挂载 + 事件接线
│       ├── footer-action.ts             # 「持仓看板」按钮 occupant（宽/窄两态，点击 dispatch open）
│       ├── holdings-board.ts            # BoardController + mount（中心栏容器、轮询 API）
│       ├── dom.ts                       # 选择器/激活属性/跨面板互斥（own 命名空间）
│       ├── view.ts                      # buildView + renderAll（分区渲染）
│       ├── styles.ts                    # 显隐样式（html[data-dsh-hld-active]）
│       └── types.ts                     # client 侧数据形状（与 host 侧一致）
└── README.md
```

**命名空间隔离**：DOM 标记用 `dsh-hld-*`、激活属性 `data-dsh-hld-active`、面板名 `dashboard-holdings`、激活事件沿用 `dsh-panel-activate`（detail=dashboard-holdings）。page1 打开时驱逐 page2/taskboard/ssh 激活属性，反之亦然——两页互斥，各自可开可关。

## 3. GUI 呈现形态（请用户拍板）

page2 已占 `sidebar.footer.action` 槽位（list kind，多 occupant 本就允许）。page1 两种落法：

### 方案 A（推荐）：侧栏第二入口按钮「持仓看板」
- 同一官方槽位注册第二 occupant（id=`dashboard-holdings`，order=200，label=`持仓看板`），与「执行看板」并列左下角。
- 点击各自 toggle 自己的中心栏视图；互斥（激活事件驱逐）。
- ✅ 与 taskboard 双半标准一致、与 page2 对称；两页独立开关。
- ⚠️ 待验证：footer 渲染宽度能否容纳两按钮（窄 rail 折叠为图标）——若拥挤降级方案 B。

### 方案 B（备选）：page2 看板内顶部 tab 切换两页
- page1 不注册独立入口，作 page2 中心栏视图的第二 tab。
- ❌ 偏离「两个独立插件」总设计（独立演进/禁用/故障隔离），需改造已完成的 page2 client。
- 仅当方案 A footer 空间不成立时采用。

## 4. 页面内容与数据映射（真实探测 2026-09-04）

v2 `:5001` 端点已 curl 实测 200，字段与设计稿对齐：

| 设计稿区块 | 数据来源 | 实测契约要点 |
|---|---|---|
| 多账户切换 | `GET /api/simulation/accounts` | `data.accounts[]`: account_name/display_name/strategy_name/status/cash_available/position_value/total_value/cumulative_return/positions_count |
| 账户摘要 | `GET /api/portfolio/summary?account_name=` | `data`: totalValue/totalCost/totalMarketValue/totalPnl/totalPnlPct/dailyChange/positions/cash/liquidAssets/profitCount/lossCount/lastUpdated |
| 持仓明细 | `GET /api/portfolio/positions?account_name=` | `data.positions[]`: symbol/name(空!)/quantity/sharesAvailable/avgCost/currentPrice/currentValue/profitLoss/profitLossPct/profitToday |
| 今日自动交易 | `GET /api/simulation/trades?account_name=` | action/shares/price/filled_price/realized_pnl/reason/order_id（按日过滤） |
| 盯盘中心 | `GET /api/watch/rules` | rules[]: id/symbol/enabled/conditions[]/context |
| 名称补全 | name-map.ts 静态表 | positions.name 空 → host 补名（缺失显代码） |

合规口径（client 展示用，与交易宪法一致）：现金 ≥10%、单股 ≤20%、单行业 ≤40%、60 日回撤 -8% 熔断线。

## 5. 阶段划分（增量纪律：每阶段一个可验证结果）

### Phase 1 — 核心块（先保证成功）
- host：`/dashboard/api/holdings` = 多账户列表 + 单账户摘要 + 持仓明细（默认 agent_virtual，可传 account）。
- client：侧栏「持仓看板」入口（第二 occupant）+ 中心栏视图渲染三块 + 顶部账户切换。
- 验收：刷新 → 左下角出现「持仓看板」→ 点击开板，中心栏显示真实持仓/摘要；与执行看板互斥；控制台有日志。

### Phase 2 — 完整化
- 今日自动交易块（当日过滤 + 状态徽标）。
- 盯盘中心块（rules 列表 + 条件解析）。
- 买卖点合成（止损档 + 就近 ZigZag 拐点 + 盯盘条件 → 每行参考买卖点）。
- 多账户记忆（localStorage）。

### Phase 3 — 收尾
- 设计稿逐块核对、README、文档、经验沉淀。

> 每阶段结束向用户确认再进下一阶段。

## 6. profile 接线（同 page2 三步）
1. `pnpm build:client` 产出 lib/client.js（先 build 后重启，缺 bundle host 启动即失败）。
2. profile：package.json dependencies + `node_modules/@pi-investment/` symlink + cordis.patch.yml 追加 loader 行。
3. 精确重启（ps 验 pid → kill → tree-A start.sh）→ boot manifest 含 holdings entry → curl 验证 API 200 + bundle。

## 7. 风险与对策
| 风险 | 对策 |
|---|---|
| footer 两按钮拥挤/窄 rail 折叠 | 验证后降级方案 B（tab）或调 order/label |
| positions.name 为空 | host name-map 补全（缺失显代码）；不阻塞 |
| 多账户聚合性能 | host 端 Promise.all 并发 + 4s 超时；单账户失败降级该块不整页 500 |
| 与 page2 等面板状态冲突 | own 命名空间 + ACTIVATE_EVENT 互斥（taskboard 实证） |

## 8. 立即下一步（待评审通过）
Phase 1 实施：① 镜像脚手架建包 → ② host（types+aggregation+routes+index）→ ③ client（入口+controller+view/styles）→ ④ build+接线 → ⑤ 重启验证 → ⑥ 用户点击验收。

---

## 相关页面

- [holdings 包](../../packages/pages/holdings/README.md)
- [双插件总方案](dashboard-implementation-plan.md)
- [页面插件契约](../architecture/page-plugin-contract.md)
