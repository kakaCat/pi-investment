# 股票热力图（Stock Heatmap）设计文档

日期：2026-07-31
状态：已确认（用户逐段批准）

## 1. 目标与用途

在 web-frontend 新增"市场热力图"页面。核心用途不是单纯看行情，而是 **agent 判断的可视化校验**：

> 人通过一张图，把"agent 当时的判断"（信号 / 池调整 / 行业态度）与"市场后续实际走势"（验证窗内涨跌幅）叠加对照，一眼看出 agent 判断的对错。

## 2. 已确认的决策记录

| 决策点 | 结论 |
|---|---|
| 叠加层 | 全部三层：个股信号、股票池调整、行业判断（可切换开关） |
| 时间维度 | 方案 B：选判断日 D + 验证窗 N（1/5/20 交易日可切），颜色 = D→D+N 实际涨跌 |
| 股票覆盖 | 方案 C：主体为 agent 相关股票（in_scope），同行业池外股票作灰色背景参照 |
| 实现路径 | 方案 1：新增后端热力图聚合 API，数据全部来自本地 PostgreSQL，无外部行情调用 |
| 视觉编码 | 颜色=涨跌幅（红涨绿跌，发散色阶，深浅=幅度）；面积=市值；白实线框+▲▼=信号；虚线框=池事件；行业边框=stance |
| 行业 stance 来源 | v1 从 agent 行为推导（非显式表态记录），见 §4.4 |

## 3. 架构总览

```
web-frontend (新视图 StockHeatmap)
   │  GET /api/market/heatmap?date=D&window=N
   ▼
quantsys-v2  HeatmapService（纯 SQL 聚合）
   ├─ daily_klines      → D 收盘 → D+N 收盘 涨跌幅
   ├─ stocks            → industry / market_cap / name
   ├─ signals 表        → D 前 30 天内信号
   ├─ 池变更日志         → 回放 D 时点池成员 / 池事件
   └─ 持仓              → 当前持仓
```

- 前端：Vue 3 + Element Plus + ECharts 6（内置 treemap，**无新依赖**）
- 后端：Flask 生产路由（:5001）+ FastAPI parity 路由各一份，遵循现有迁移模式
- 一次请求返回全量数据；日期/验证窗切换才重新请求，叠加层开关纯前端控制

## 4. 后端设计

### 4.1 端点

```
GET /api/market/heatmap?date=2026-07-24&window=5
```

- `date`：判断日；缺省 = 最近已收盘交易日；非交易日自动对齐到之前最近交易日
- `window`：验证窗，取值 1/5/20（交易日），默认 5

### 4.2 响应结构

```json
{
  "date": "2026-07-24",
  "window": 5,
  "actual_end_date": "2026-07-31",
  "partial": false,
  "scope_degraded": false,
  "excluded_count": 0,
  "industries": [
    {
      "name": "半导体",
      "change_pct": 4.2,
      "agent_stance": "bullish",
      "stocks": [
        {
          "symbol": "688981", "name": "中芯国际",
          "change_pct": 8.2, "market_cap": 450000000000,
          "in_scope": true,
          "signals": [{"type": "buy", "date": "2026-07-23", "strategy": "v13"}],
          "pool_events": [{"action": "add", "pool": "高质量池", "date": "2026-07-22"}]
        },
        {
          "symbol": "300999", "name": "某池外股",
          "change_pct": 1.1, "market_cap": 20000000000,
          "in_scope": false
        }
      ]
    }
  ]
}
```

错误走现有 `{success: false, message}` 信封；`date` 无 K 线覆盖时返回 `industries: []` + `message`。

### 4.3 核心计算（HeatmapService）

- **个股涨跌**：`close(D)` → `close(D 之后第 N 个交易日)`，数据源 `daily_klines` 表（单位契约：volume=股、amount=元，本功能只用 close）
- **partial**：若 D+N 超出已有最新 K 线，用最后可得交易日，置 `partial: true`，`actual_end_date` 如实返回
- **停牌/缺数据**：缺 D 或 D+N 收盘价的股票剔除出图，计入 `excluded_count`
- **in_scope**（agent 相关，满足任一）：
  1. D 日前 30 天内有信号记录
  2. D 时点在任一动态池内（从池变更日志回放）
  3. 当前持仓（指请求时刻的当前持仓，非 D 时点持仓——持仓历史快照不存在，此为已知近似）
- **scope_degraded**：若池变更日志在 D 前无记录导致无法回放池成员，退化为"信号+持仓"口径并置 `scope_degraded: true`
- 池外同行业股票一并返回（`in_scope: false`），前端渲染为灰色背景块

### 4.4 行业 stance 推导规则（v1）

对某行业，取 D 日前 30 天内该行业 in_scope 股票的 agent 行为：
- 正向行为 = 买入信号数 + 池调入数；负向行为 = 卖出信号数 + 池调出数
- 净正 → `bullish`；净负 → `bearish`；无行为或正负相抵 → `neutral`

⚠️ 已知限制：这是**从行为推导**而非 agent 显式表态。若后续 agent 落库显式行业判断（如 battlefield assessment 持久化），替换数据源即可，端点契约不变。

## 5. 前端设计

### 5.1 文件

- `web-frontend/src/views/StockHeatmap/index.vue` — 页面主体
- `web-frontend/src/views/StockHeatmap/heatmap-options.ts` — ECharts treemap option 构建（纯函数，可单测，参照 KLineChart 的 chart-options.ts 模式）
- `web-frontend/src/services/api/market.ts` — 增加 `getHeatmap(date, window)`（apiClient 已解包 `{success,data}` 信封，直接用解包后形状）
- `web-frontend/src/router/index.ts` — 路由 `/stock-heatmap`，meta.title「市场热力图」
- `web-frontend/src/components/layout/MainLayout.vue` — 菜单项放「研究分析」组

### 5.2 页面结构

```
┌──────────────────────────────────────────────┐
│ 📅日期选择 | 验证窗[1日][5日][20日] | ☑信号 ☑池调整 ☑行业 │
├──────────────────────────────────────────────┤
│  ECharts treemap（行业→个股两级）              │
│   - 面积=市值，颜色=涨跌幅(红涨绿跌发散色阶)      │
│   - in_scope=false → 灰色低饱和背景块          │
│   - 信号→label 角标▲▼；池事件→边框样式          │
│   - 行业 stance → 行业区块边框色               │
│   - hover tooltip：明细+信号+池事件+对错判定     │
├──────────────────────────────────────────────┤
│  底部统计条：判断对 X / 错 Y / 待定 Z（partial 时）│
└──────────────────────────────────────────────┘
```

### 5.3 对错判定（前端纯函数）

- 买信号 & `change_pct > 0` → 对；卖信号 & `change_pct < 0` → 对；反向 → 错
- 池调入 & 涨 → 对；池调出 & 跌 → 对；反向 → 错
- 行业 stance bullish & 行业加权涨 → 对；bearish & 行业加权跌 → 对；反向 → 错
- `partial: true` 时顶部提示「验证窗未满（实际到 X 日）」，统计计入"待定"

### 5.4 交互（v1 范围）

- 点击股票方块 → 跳现有 StockDetail 页
- 点击行业区块 → treemap drilldown（ECharts 自带）
- 日期 / 验证窗切换 → 重新请求；叠加层开关 → 纯前端重渲染
- 非交易日对齐、scope_degraded、excluded_count 均以轻提示展示，不弹错误框

## 6. 错误处理汇总

| 场景 | 行为 |
|---|---|
| date 非交易日 | 对齐到之前最近交易日，响应带回实际 date |
| date 早于数据覆盖 | `industries: []` + message，前端空态 |
| 个股停牌/缺 K 线 | 剔除 + `excluded_count` |
| 池日志无法回放 | 退化口径 + `scope_degraded: true` |
| 后端异常 | `{success:false}` 信封，apiClient 统一处理 |

## 7. 测试（TDD）

- **后端 pytest**：HeatmapService 窗口聚合（含 partial、停牌剔除、非交易日对齐、scope 退化）；端点契约测试（响应形状冻结）；stance 推导规则用例
- **前端 jest**：heatmap-options.ts 纯函数单测（数据→option、颜色映射、对错判定）。注意基线存在预存在失败（见 memory baseline-failing-tests），只要求新增测试全绿；agent-ts 不适用，前端用其自身测试命令
- **冒烟**：真实 DB 对最近交易日跑 window=5 请求，人工抽查若干股票涨跌数

## 8. 非目标（YAGNI）

- ❌ 时间轴回放动画（方案 C，后续迭代候选）
- ❌ 实时盘中刷新（本设计基于收盘日线）
- ❌ 每日预计算快照表（方案 3，仅在性能成为问题时叠加）
- ❌ agent 显式行业表态存储（v1 用行为推导）
