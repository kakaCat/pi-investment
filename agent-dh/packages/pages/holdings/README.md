# @pi-investment/dashboard-holdings

账户持仓看板 — DSH GUI 双半插件（Phase 1）

## 概述

`@pi-investment/dashboard-holdings` 是 PI Investment 系统的持仓可视化插件，提供：

- **多账户摘要** - 账户切换、资产总览、盈亏统计
- **持仓明细** - 实时持仓、成本价、浮动盈亏
- **合规监控** - 现金占比、单股占比、行业集中度、回撤监控
- **今日交易** - 自动交易记录、成交价格、实现盈亏
- **盯盘中心** - 监控规则、触发条件、执行状态

> **状态（2026-09-04）**：本包为 /dashboard/api/holdings 的唯一 owner（双半插件标准）。
> 曾短暂并入 execution 插件内联实现（偏离「两个独立插件」设计），经用户裁决 1B 恢复独立包；
> execution 侧已剥离全部 holdings 代码（host 路由 / client 入口 / holdings-* 文件 / services-holdings / types-holdings）。
> package.json 的 dsh.client.inject 已修为 ["slots"]（此前为 []，client 半因此无法注册侧栏席位——按钮不出现的主因之一）。
> host 半已去除调试残留（/tmp 标记、[HOLDINGS-DEBUG]/[HOLDINGS-APPLY] 噪声）。
> 产品档（~/.dsh）与 dev 档（~/.dsh-agent-dh）cordis.patch.yml + node_modules 均已注册/链接本包。

## 架构

### 双半插件模式

```
┌─────────────────────────────────────────────┐
│  DSH Web Shell (Browser)                    │
│  ┌───────────────────────────────────────┐  │
│  │ Client Half (lib/client.js)           │  │
│  │ • Sidebar footer button               │  │
│  │ • Center panel board view             │  │
│  │ • Fetch /dashboard/api/holdings       │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
              ↓ HTTP GET
┌─────────────────────────────────────────────┐
│  DSH Host (Node.js)                         │
│  ┌───────────────────────────────────────┐  │
│  │ Host Half (src/index.ts)              │  │
│  │ • Route: /dashboard/api/holdings      │  │
│  │ • Aggregates data from v2 APIs        │  │
│  │ • Returns { success, data }           │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
              ↓ HTTP GET
┌─────────────────────────────────────────────┐
│  quantsys-v2 (Python FastAPI :5001)         │
│  • /api/simulation/accounts                 │
│  • /api/portfolio/summary                   │
│  • /api/portfolio/positions                 │
│  • /api/simulation/trades                   │
│  • /api/watch/rules                         │
└─────────────────────────────────────────────┘
```

### 文件结构

```
packages/pages/holdings/
├── package.json              # 包元信息 + dsh.client 声明
├── tsdown.client.config.ts   # Client 半构建配置
├── scripts/wrap-client.mjs   # ModuleLoader 包装脚本
├── src/
│   ├── index.ts              # Host 半入口（注册路由）
│   ├── types/
│   │   └── index.ts          # 数据契约类型
│   ├── services/
│   │   ├── http.ts           # HTTP 客户端
│   │   ├── name-map.ts       # 股票代码→名称映射
│   │   └── portfolio-aggregation.ts  # 持仓数据聚合
│   ├── routes/
│   │   └── holdings-routes.ts        # /dashboard/api/holdings 路由
│   └── client/               # Client 半（浏览器端）
│       ├── index.ts          # Client 入口（注册 slot）
│       ├── dom.ts            # DOM 选择器和工具
│       ├── types.ts          # Client 侧类型
│       ├── footer-action.ts  # Sidebar footer 按钮组件
│       ├── styles.ts         # 样式注入
│       ├── view.ts           # 视图渲染逻辑
│       ├── board-mount.ts    # 看板控制器和挂载
│       └── react-shim.d.ts   # React 类型 shim
└── README.md                 # 本文件
```

## 开发

### 构建 Client 半

```bash
cd agent-dh/packages/pages/holdings
pnpm build:client
```

构建产物：
- `lib/client.cjs` - tsdown 编译的 CJS bundle
- `lib/client.js` - wrap-client.mjs 包装后的浏览器模块

### 接线到 Profile

1. **添加依赖** - 编辑 `~/.dsh/profiles/investment/package.json`：
   ```json
   {
     "dependencies": {
       "@pi-investment/dashboard-holdings": "file:~/pi-investment/agent-dh/packages/pages/holdings"
     }
   }
   ```

2. **创建 symlink**：
   ```bash
   cd ~/.dsh/profiles/investment/node_modules/@pi-investment
   ln -s ~/pi-investment/agent-dh/packages/pages/holdings dashboard-holdings
   ```

3. **注册插件** - 编辑 `~/.dsh/profiles/investment/cordis.patch.yml`（patch 格式；无需自定义 loader——cordis 直接读包 `main` 即 `src/index.ts`）：
   ```yaml
   - insert:
       - id: dashboard-holdings
         name: '@pi-investment/dashboard-holdings'
         config: {}
   ```

4. **重启 DSH**（精确停启本实例，禁止 pkill -f 模糊匹配；多实例铁律见 agent-dh/CLAUDE.md）：
   ```bash
   cd ~/.dsh/profiles/investment
   ./stop.sh
   ./start.sh 13080
   ```
   或由 agent 调 self_restart（自动 wip 检查点 + 启动后自动续跑验证）
   ```

## 验证

### 1. 验证 API 端点

```bash
curl http://127.0.0.1:13080/dashboard/api/holdings?account=agent_virtual
```

预期响应：
```json
{
  "success": true,
  "data": {
    "accounts": [...],
    "currentAccount": "agent_virtual",
    "summary": {...},
    "positions": [...],
    "todayTrades": [...],
    "watchRules": [...],
    "compliance": {...}
  }
}
```

### 2. 验证 Client Bundle

```bash
curl http://127.0.0.1:13080/plugins/??@pi-investment/dashboard-holdings/client.js
```

应返回 JavaScript 代码（ModuleLoader.load 调用）。

### 3. 验证 GUI

1. 打开 DSH web (http://127.0.0.1:13080)
2. 左下角应显示「持仓看板」按钮（在「执行看板」下方，order 200）
3. 点击按钮，中心栏应显示持仓看板
4. 检查浏览器控制台：
   ```
   [dashboard-holdings] footer action clicked — dispatching dashboard-holdings:open-board
   [dashboard-holdings] open-board event { open: true } boardOpen: false
   [dashboard-holdings] opening board
   ```

## 数据契约

### GET /dashboard/api/holdings?account={account_name}

**Query 参数**：
- `account` - 账户名称（可选，默认 `agent_virtual`）

**响应**：
```typescript
{
  success: true,
  data: {
    accounts: Account[],           // 多账户列表
    currentAccount: string,        // 当前账户
    summary: PortfolioSummary,     // 账户摘要
    positions: Position[],         // 持仓明细
    todayTrades: Trade[],          // 今日交易
    watchRules: WatchRule[],       // 盯盘规则
    compliance: {                  // 合规指标
      cashRatio: number,           // 现金占比 %
      maxSingleStock: number,      // 最大单股占比 %
      maxIndustry: number,         // 最大行业占比 %
      maxDrawdown60d: number       // 60日最大回撤 %
    }
  }
}
```

详细类型定义见 `src/types/index.ts`。

## 命名空间隔离

- **DOM 属性**: `data-dsh-hld-*`
- **CSS 类**: `.dsh-hld-*`
- **激活属性**: `html[data-dsh-hld-active]`
- **面板名**: `dashboard-holdings`
- **事件**: `dashboard-holdings:open-board`

与 `dashboard-execution` (dsh-exec-*) 完全隔离，互不冲突。

## Phase 1 范围

✅ **已实现**：
- Host 半路由和数据聚合
- Client 半 GUI（sidebar button + center panel）
- 账户切换
- 持仓明细表格
- 摘要卡片
- 合规指标
- 今日交易列表
- 盯盘规则列表

⏳ **Phase 2 计划**：
- 买卖点合成（止损档 + ZigZag + 盯盘条件）
- 多账户记忆（localStorage）
- 行业集中度实际计算（需行业分类数据）
- 60日回撤实际计算（需净值时间序列）

## 故障排查

### API 返回 500

检查 v2 服务是否运行：
```bash
curl http://127.0.0.1:5001/api/health
```

### Client bundle 404

1. 检查 `lib/client.js` 是否存在
2. 重新构建：`pnpm build:client`
3. 检查 symlink 是否正确

### Footer 按钮不显示

1. 检查浏览器控制台是否有错误
2. 检查 `cordis.patch.yml` 插件是否注册
3. 检查 DSH 日志：`~/.dsh/profiles/investment/state/launchd.out.log`

### 看板不显示数据

1. 打开浏览器开发者工具 Network 面板
2. 点击「持仓看板」按钮
3. 检查 `/dashboard/api/holdings` 请求
4. 查看响应内容和状态码

## 相关文档

- [实施方案](../../../docs/design/page1-holdings-implementation-plan.md)
- [Dashboard 总方案](../../../docs/design/dashboard-implementation-plan.md)
- [Execution 看板](../execution/README.md)

## License

MIT
