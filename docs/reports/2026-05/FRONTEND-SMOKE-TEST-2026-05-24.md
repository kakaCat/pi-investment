# 前端页面测试记录

**测试时间**: 2026-05-24  
**测试对象**: `web-frontend` Vue/Vite 前端  
**测试地址**: `http://127.0.0.1:3002/`  
**测试方式**: Vitest 单测、TypeScript/Vite 构建、Playwright 浏览器冒烟测试、移动端抽样检查

## 测试环境

- 工作目录: `/Users/mac/Documents/ai/pi-investment/web-frontend`
- 启动命令: `npm run dev -- --host 127.0.0.1`
- Vite 端口: `3001` 被占用，自动切换到 `3002`
- API 配置: `VITE_API_BASE_URL=http://127.0.0.1:5001`
- WebSocket 配置: `VITE_WS_URL=ws://127.0.0.1:5003`

## 命令验证结果

### `npm run test`

结果: 未通过

- 测试文件: 11 个，8 个通过，3 个失败
- 测试用例: 152 个，149 个通过，3 个失败
- 额外问题: 1 个 unhandled rejection

失败项:

| 文件 | 用例 | 现象 |
| --- | --- | --- |
| `tests/unit/ResponsiveLayout.test.ts:49` | Dashboard stat cards md breakpoint | 测试期望 `:md="6"`，当前页面源码为 `:md="8"` |
| `tests/unit/api-contract.test.ts:94` | indicator endpoint contract | 测试期望 `post('/api/indicators/run/7', { symbol, limit })`，实际最后调用参数为 `'/api/indicators/run/7', '000001.SZ'` |
| `tests/unit/composables/useTable.test.ts:203` | select same row twice should deselect | 重复选择后 `selectedRows` 长度为 2，测试期望 0 |
| `src/services/api/data.ts:151` | unhandled rejection | `startUpdate` 读取 `response.job_id` 时 `response` 为 `undefined` |

### `npm run build`

结果: 未通过

TypeScript 错误:

| 文件 | 行号 | 错误 |
| --- | --- | --- |
| `src/components/charts/KLineChart/index.vue` | 110 | `TradingSignal` 类型不存在 `time` 属性 |
| `src/views/IndicatorIDE/index.vue` | 427 | `Indicator` 类型不存在 `codeContent` 属性 |

## 浏览器冒烟测试结果

桌面视口测试了 20 个路由。所有路由都能打开并渲染主内容，未发现空白页或路由加载失败。

| 路由 | 页面标题 | 渲染结果 | 控制台情况 |
| --- | --- | --- | --- |
| `/dashboard` | 仪表盘 | 通过 | 无新增问题 |
| `/indicator-ide` | 指标IDE | 通过 | 无新增问题 |
| `/stock-list` | 图表研究 | 通过 | 无新增问题 |
| `/stocks/000001.SZ` | 股票详情 | 通过 | K 线接口 404，WebSocket 连接失败 |
| `/factors` | 因子分析 | 通过 | 无新增问题 |
| `/signals` | 交易信号 | 通过 | 运行时异常: `Cannot read properties of undefined (reading 'toUpperCase')` |
| `/opportunity-radar` | 机会雷达 | 通过 | WebSocket 连接失败 |
| `/backtest` | 回测与快速交易 | 通过 | Element Plus radio `label` 弃用警告 |
| `/portfolio` | 持仓管理 | 通过 | WebSocket 连接失败 |
| `/orders` | 订单管理 | 通过 | 无新增问题 |
| `/risk` | 风控检查 | 通过 | 无新增问题 |
| `/strategy-center` | 策略运营中心 | 通过 | 运行时异常: `Cannot read properties of undefined (reading 'toFixed')` |
| `/ml` | ML引擎 | 通过 | 无新增问题 |
| `/trades` | 交易记录 | 通过 | 无新增问题 |
| `/quant-pipeline` | 量化链路 | 通过 | Vue 组件解析警告: `Database`、`Shield` |
| `/strategy-config` | 策略配置 | 通过 | 无新增问题 |
| `/scheduler` | 定时任务 | 通过 | 无新增问题 |
| `/data-update` | 数据更新 | 通过 | 无新增问题 |
| `/daily-report` | 日报 | 通过 | 无新增问题 |
| `/executions` | 执行记录 | 通过 | 无新增问题 |

## 移动端抽样结果

移动端视口: `390 x 844`

抽样路由: `/dashboard`、`/stock-list`、`/stocks/000001.SZ`、`/signals`、`/portfolio`、`/scheduler`

结果:

- 6 个抽样页面均能显示预期标题和主内容
- 未发现明显横向溢出，最大横向溢出为 `0px`
- 控制台问题与桌面测试一致，集中在股票详情接口/WebSocket、交易信号运行时异常

## 重点问题定位

1. 交易信号页运行时异常
   - 位置: `src/views/SignalList/index.vue:127`
   - 表达式: `row.type.toUpperCase()`
   - 现象: 当 `row.type` 缺失时页面产生 `Cannot read properties of undefined`

2. 策略运营中心运行时异常
   - 位置: `src/views/StrategyCenter/index.vue:133`
   - 表达式: `strategy.sharpeRatio.toFixed(2)`
   - 现象: 当 `strategy.sharpeRatio` 缺失时页面产生 `Cannot read properties of undefined`

3. 量化链路图标组件未解析
   - 位置: `src/views/QuantPipeline/index.vue:64`、`src/views/QuantPipeline/index.vue:124`
   - 组件: `Database`、`Shield`
   - 现象: Vue 警告未解析组件，可能缺少图标 import 或注册

4. 股票详情页后端依赖未满足
   - 位置: `src/views/StockDetail/index.vue:193`
   - 现象: K 线数据接口返回 404，WebSocket `127.0.0.1:5003` 拒绝连接
   - 备注: 页面本身仍有降级内容渲染

## 截图记录

桌面截图位于 `.playwright-mcp/`:

- `smoke-dashboard-2026-05-24.png`
- `smoke-indicator-ide-2026-05-24.png`
- `smoke-stock-list-2026-05-24.png`
- `smoke-stocks-000001-SZ-2026-05-24.png`
- `smoke-signals-2026-05-24.png`
- `smoke-strategy-center-2026-05-24.png`
- `smoke-quant-pipeline-2026-05-24.png`
- 其余页面同名 `smoke-<route>-2026-05-24.png`

移动端截图位于 `.playwright-mcp/`:

- `mobile-dashboard-2026-05-24.png`
- `mobile-stock-list-2026-05-24.png`
- `mobile-stocks-000001-SZ-2026-05-24.png`
- `mobile-signals-2026-05-24.png`
- `mobile-portfolio-2026-05-24.png`
- `mobile-scheduler-2026-05-24.png`

## 结论

前端路由冒烟测试结果为: 页面可访问，主内容可渲染。

项目验证结果为: 未通过。当前存在 3 个单测失败、1 个测试未处理异步异常、2 个 TypeScript 构建错误，以及若干浏览器运行时/控制台问题。建议优先处理构建错误和交易信号页、策略运营中心的运行时异常，再重新执行本测试记录中的命令和路由冒烟测试。
