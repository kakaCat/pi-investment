# akshare-ts 模块拆分设计文档

**日期：** 2026-05-14  
**状态：** 设计阶段  
**架构改进项：** P0-1 拆解 `src/infrastructure/akshare-ts/index.ts`（1,248 行上帝模块）

---

## 1. 背景与目标

### 当前问题

`src/infrastructure/akshare-ts/index.ts` 当前有 1,248 行代码，包含 22 个导出函数，职责混杂：
- 市场数据获取（A股/港股实时、历史行情）
- 技术指标计算（MA/MACD/RSI/BOLL/KDJ/ATR/OBV/CCI）
- 财务数据分析（质量评分、估值、PE分位数）
- 资金流和大股东分析
- 组合分析服务（买入区间、走势分析、K线形态）
- 持仓管理

**问题：**
- 单文件过大，难以维护和理解
- 职责不清晰，违反单一职责原则
- 修改风险高，容易引入回归问题
- 测试困难，无法针对特定领域进行单元测试

### 重构目标

1. **清晰的分层架构** — 数据层 → 指标层 → 服务层
2. **单一职责** — 每个模块只负责一个明确的领域
3. **向后兼容** — 所有公共 API 保持不变
4. **可测试性** — 每个模块可独立测试
5. **可扩展性** — 未来添加新功能时有明确的归属位置

---

## 2. 架构设计

### 2.1 目录结构

```
src/infrastructure/akshare-ts/
├── data/
│   ├── market.ts          # 市场数据获取（~150行）
│   └── financial.ts       # 财务数据获取（~200行）
├── indicators/
│   ├── technical.ts       # 技术指标计算（~150行）
│   └── chart-patterns.ts  # K线形态识别（~200行）
├── services/
│   ├── buy-range.ts       # 买入区间计算（~80行）
│   ├── price-action.ts    # 走势分析（~120行）
│   ├── exit-plan.ts       # 止盈计划（~60行）
│   └── peer-comparison.ts # 同业对比（~80行）
├── portfolio.ts           # 持仓管理（~60行）
├── shared.ts              # 共享工具函数（~100行）
└── index.ts               # 统一导出（~80行）
```

**总计：** 10 个文件，预计总行数 ~1,280 行（略有增加是因为模块边界和导入语句）

### 2.2 分层架构

```
┌─────────────────────────────────────────┐
│           index.ts (导出层)              │
│  统一导出所有公共函数 + 函数注册表        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         services/ (服务层)               │
│  组合多个数据源和指标，提供高级分析功能   │
│  - buy-range, price-action, exit-plan   │
│  - peer-comparison                      │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       indicators/ (指标层)               │
│  纯技术指标计算和图表分析                │
│  - technical, chart-patterns            │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│          data/ (数据层)                  │
│  纯数据获取，无业务逻辑                  │
│  - market, financial                    │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    shared.ts (工具层) + portfolio.ts     │
│  工具函数、类型定义、持仓管理            │
└─────────────────────────────────────────┘
```

**依赖规则：**
- ✅ 服务层可以调用数据层和指标层
- ✅ 指标层可以调用数据层
- ✅ 所有层都可以使用 shared.ts
- ❌ 数据层不能调用指标层或服务层
- ❌ 指标层不能调用服务层
- ❌ 同层模块之间避免相互依赖

---

## 3. 模块职责详细说明

### 3.1 数据层 (data/)

#### data/market.ts (~150行)

**职责：** 纯市场数据获取，无业务逻辑

**导出函数：**
- `get_stock_realtime_price(symbol: string)` — A股实时行情
- `get_stock_history(symbol, period?, start?, end?, adjust?, _skip_cache?)` — A股历史行情（含数据库缓存逻辑）
- `get_stock_info(symbol: string, saveToMemory?)` — A股基本信息
- `get_market_overview()` — 大盘概览（上证/深证/创业板/沪深300/中证500）
- `get_sector_list()` — 板块列表
- `get_hk_stock_price(symbol: string)` — 港股实时行情
- `get_hk_stock_info(symbol: string)` — 港股基本信息
- `get_hk_stock_history(symbol: string, period?)` — 港股历史行情

**依赖：**
- `../data-sources/sina.js` — 新浪财经数据源
- `../data-sources/eastmoney.js` — 东方财富数据源
- `../data-sources/stooq.js` — Stooq 港股数据源
- `../../services/data/stock-db-index.js` — StockDBService, KlineCacheService
- `./shared.js` — 工具函数

**特殊逻辑：**
- `get_stock_history` 包含缓存优先逻辑：先查 KlineCacheService，缺失时调用 Python bridge

---

#### data/financial.ts (~200行)

**职责：** 财务数据获取和基本面评分

**导出函数：**
- `get_quality_score(symbol: string)` — 质量评分（ROE/毛利率/负债率/现金流/营收增长）
- `get_stock_valuation(symbol: string)` — 估值数据（调用 Python bridge）
- `get_pe_percentile(symbol: string, years?)` — PE 历史分位数（调用 Python bridge）
- `get_stock_fund_flow(symbol: string, days?)` — 资金流向（主力/大单/中单/小单）
- `get_holder_changes(symbol: string)` — 大股东变动（最近两个季度对比）

**内部辅助函数：**
- `extractStatementRows(payload, sectionKey)` — 提取财务报表行
- `fetchTopHolderSnapshot(symbol, reportDate)` — 获取单个季度的十大股东快照

**依赖：**
- `../tools/python-bridge.js` — callPythonDaemon
- `./shared.js` — callPythonBridge, findNumber, findString, normalizeHolderName, computeQuarterEnds

---

### 3.2 指标层 (indicators/)

#### indicators/technical.ts (~150行)

**职责：** 纯技术指标计算，返回结构化数据

**导出函数：**
- `calculate_technical_indicators(symbol: string)` — 综合技术指标（MA5/10/20/60, MACD, RSI, BOLL）

**计算逻辑：**
1. 获取历史 K 线（优先从数据库缓存）
2. 获取实时价格（用于补充当日数据）
3. 混合模式：如果实时日期比缓存更新，追加合成 K 线
4. 计算所有技术指标
5. 生成信号（短期多头排列、RSI超买/超卖、MACD金叉/死叉等）

**依赖：**
- `../data-sources/technical.js` — rollingMean, calcRsi, calcMacd, bollinger, klinesToNumbers
- `../data/market.js` — get_stock_history, get_stock_realtime_price
- `./shared.js` — r2, r4, lastNum, today

---

#### indicators/chart-patterns.ts (~200行)

**职责：** K线形态识别和图表分析

**导出函数：**
- `analyze_candlestick(symbol: string)` — K线形态 + 趋势线 + 斐波那契 + 缺口识别

**分析维度：**
1. **K线形态** — 锤子线、吞没、十字星等（最近10根K线）
2. **趋势线** — 支撑线和阻力线（最近60根K线）
3. **斐波那契回调** — 0.236/0.382/0.5/0.618/0.786 回调位
4. **缺口识别** — 跳空缺口及回补状态

**依赖：**
- `../data-sources/technical.js` — candlestickPatterns, trendLines, fibonacci, priceGaps
- `../data-sources/sina.js` — fetchSinaKlines
- `./shared.js` — r2, cleanSymbol, today

---

### 3.3 服务层 (services/)

#### services/buy-range.ts (~80行)

**职责：** 买入区间计算服务，组合技术指标生成交易建议

**导出函数：**
- `calculate_buy_range(symbol: string, current_price?: number)` — 计算安全买入价、理想买入价、止损位、目标价

**计算逻辑：**
1. 获取近90天日线数据
2. 计算技术支撑位：MA20、MA60、近20日低点、布林带下轨
3. 取最低的两个支撑位平均值作为技术支撑
4. 生成买入建议（分批建仓策略）

**依赖：**
- `../data-sources/sina.js` — fetchSinaKlines
- `../data-sources/technical.js` — rollingMean, bollinger, klinesToNumbers
- `./shared.js` — r2, cleanSymbol, lastNum, today

---

#### services/price-action.ts (~120行)

**职责：** 走势深度分析服务，组合多维度技术分析

**导出函数：**
- `analyze_price_action(symbol: string, period?)` — 趋势方向、支撑阻力位、成交量分析、突破信号、动量指标、波动率

**分析维度：**
1. **趋势分析** — 短期/中期趋势方向，MA5/20/60 排列
2. **支撑阻力位** — Swing 高低点识别（最近20日）
3. **成交量分析** — 量比、OBV 趋势、放量/缩量状态
4. **突破信号** — 向上/向下突破确认
5. **动量指标** — KDJ、CCI、RSI
6. **波动率** — ATR 绝对值和百分比

**依赖：**
- `../data-sources/sina.js` — fetchSinaKlines
- `../data-sources/technical.js` — 全部技术指标函数
- `./shared.js` — r2, cleanSymbol, today

---

#### services/exit-plan.ts (~60行)

**职责：** 止盈计划服务，基于 PE 估值和买入价计算卖出策略

**导出函数：**
- `get_exit_plan(symbol: string, buy_price: number, shares?)` — 保守/中等/激进目标价 + 分批卖出建议

**计算逻辑：**
1. 获取当前价格和 PE
2. 如果 PE 有效，基于 EPS 和合理 PE 计算目标价
3. 否则使用固定涨幅（20%/40%/60%）
4. 生成分批卖出建议（30%/40%/30%）

**依赖：**
- `../data/market.js` — get_stock_realtime_price
- `./shared.js` — r2, cleanSymbol, today

---

#### services/peer-comparison.ts (~80行)

**职责：** 同业对比服务，跨股票数据聚合

**导出函数：**
- `compare_peers(symbol: string)` — 获取目标股票行业信息，返回对比框架

**工作流程：**
1. 获取目标股票基本信息（行业）
2. 获取板块列表，匹配行业名称
3. 并行获取目标股票实时价格
4. 返回目标股票数据 + 提示调用 `screen_stocks_quality` 补充同行数据

**依赖：**
- `../data/market.js` — get_stock_info, get_sector_list, get_stock_realtime_price
- `./shared.js` — safeFloat, today

---

### 3.4 其他模块

#### portfolio.ts (~60行)

**职责：** 持仓管理，文件 I/O 操作

**导出函数：**
- `manage_portfolio(action, symbol?, quantity?, avg_cost?, notes?)` — 增删查持仓记录

**操作：**
- `get` — 读取持仓列表
- `add` — 添加/更新持仓
- `remove` — 删除持仓

**数据存储：** `.pi-invest/portfolio.json`

**依赖：**
- Node.js `fs` 模块
- `./shared.js` — today, nowStr

---

#### shared.ts (~100行)

**职责：** 共享工具函数、类型定义、常量

**导出内容：**

**Python 桥接：**
- `callPython(func, args)` — 直接调用 Python（execFileAsync）
- `callPythonBridge(func, args)` — 调用 Python daemon（JSON-RPC）

**工具函数：**
- `r2(v)` / `r4(v)` — 四舍五入到2位/4位小数
- `toNumber(value)` — 字符串转数字（支持亿/万单位）
- `findNumber(record, keys)` — 从对象中查找数字字段
- `findString(record, keys)` — 从对象中查找字符串字段
- `median(values)` — 中位数
- `normalizeHolderName(name)` — 股东名称标准化
- `computeQuarterEnds(limit)` — 计算最近N个季度末日期
- `getQualityRating(score)` — 质量评分等级（优秀/良好/一般/较差）

**共享服务（懒加载）：**
- `getStockDB()` — StockDBService 单例
- `getKlineCache()` — KlineCacheService 单例

**类型定义：**
- `JsonRecord` — `Record<string, unknown>`
- `PortfolioData` — 持仓数据结构
- `TsFn` — 函数注册表类型

---

#### index.ts (~80行)

**职责：** 统一导出所有公共函数 + 函数注册表

**内容：**

```typescript
// Re-export all public functions
export * from './data/market.js';
export * from './data/financial.js';
export * from './indicators/technical.js';
export * from './indicators/chart-patterns.js';
export * from './services/buy-range.js';
export * from './services/price-action.js';
export * from './services/exit-plan.js';
export * from './services/peer-comparison.js';
export * from './portfolio.js';
export { callPython, getQualityRating } from './shared.js';

// Function registry for tool routing
export const TS_FUNCTIONS: Record<string, TsFn> = {
  get_stock_realtime_price: (a) => get_stock_realtime_price(a.symbol as string),
  get_stock_history: (a) => get_stock_history(a.symbol as string, ...),
  // ... 所有22个函数的映射
};
```

---

## 4. 数据流示例

### 示例 1：简单数据获取

```
用户调用 get_stock_realtime_price('600519')
    ↓
data/market.ts
    ↓ fetchSinaAShareRealtime (data-sources/sina)
    ↓ fetchPeData (data-sources/eastmoney)
    ↓ 使用 safeFloat, r2 (shared.ts)
    ↓
返回实时行情 JSON
```

### 示例 2：技术指标计算

```
用户调用 calculate_technical_indicators('600519')
    ↓
indicators/technical.ts
    ↓ 调用 get_stock_history (data/market.ts)
    ↓ 调用 get_stock_realtime_price (data/market.ts)
    ↓ 调用 rollingMean/calcMacd/calcRsi/bollinger (data-sources/technical)
    ↓ 使用 r2, r4, lastNum (shared.ts)
    ↓
返回技术指标 JSON
```

### 示例 3：组合分析服务

```
用户调用 calculate_buy_range('600519')
    ↓
services/buy-range.ts
    ↓ fetchSinaKlines (data-sources/sina) — 获取历史数据
    ↓ rollingMean/bollinger (data-sources/technical) — 计算支撑位
    ↓ 使用 r2, cleanSymbol, lastNum (shared.ts)
    ↓ 组合多个支撑位，生成买入建议
    ↓
返回买入区间 JSON
```

---

## 5. 迁移策略

### 5.1 迁移步骤

**阶段 1：准备工作**
1. 创建新目录结构：`data/`, `indicators/`, `services/`
2. 创建所有空文件（10 个 .ts 文件）

**阶段 2：提取共享层**
3. 创建 `shared.ts`，迁移所有工具函数和类型定义：
   - Python 桥接函数（callPython, callPythonBridge）
   - 工具函数（r2, r4, toNumber, findNumber, findString, median, etc.）
   - 共享服务（getStockDB, getKlineCache）
   - 类型定义（JsonRecord, PortfolioData, TsFn）

**阶段 3：数据层迁移**
4. 迁移 `data/market.ts`（8 个函数）：
   - get_stock_realtime_price
   - get_stock_history
   - get_stock_info
   - get_market_overview
   - get_sector_list
   - get_hk_stock_price
   - get_hk_stock_info
   - get_hk_stock_history

5. 迁移 `data/financial.ts`（5 个函数 + 2 个辅助函数）：
   - get_quality_score
   - get_stock_valuation
   - get_pe_percentile
   - get_stock_fund_flow
   - get_holder_changes
   - extractStatementRows (内部)
   - fetchTopHolderSnapshot (内部)

**阶段 4：指标层迁移**
6. 迁移 `indicators/technical.ts`（1 个函数）：
   - calculate_technical_indicators

7. 迁移 `indicators/chart-patterns.ts`（1 个函数）：
   - analyze_candlestick

**阶段 5：服务层迁移**
8. 迁移 `services/buy-range.ts`（1 个函数）：
   - calculate_buy_range

9. 迁移 `services/price-action.ts`（1 个函数）：
   - analyze_price_action

10. 迁移 `services/exit-plan.ts`（1 个函数）：
    - get_exit_plan

11. 迁移 `services/peer-comparison.ts`（1 个函数）：
    - compare_peers

**阶段 6：其他模块**
12. 迁移 `portfolio.ts`（1 个函数 + 辅助函数）：
    - manage_portfolio
    - loadPortfolio (内部)
    - savePortfolio (内部)

**阶段 7：导出层**
13. 重写 `index.ts` 为纯导出：
    - Re-export 所有公共函数
    - 重建 TS_FUNCTIONS 注册表

**阶段 8：更新消费者**
14. 更新所有 import 路径的消费者：
    - `src/infrastructure/tools/invest-tools.ts` — 主要消费者
    - 其他可能的引用点

**阶段 9：清理**
15. 删除旧的 `index.ts`（1,248 行版本）
16. 验证所有测试通过

---

### 5.2 向后兼容保证

**公共 API 不变：**
- 所有 22 个导出函数的签名完全一致
- `index.ts` 的导出接口与原来相同
- `TS_FUNCTIONS` 注册表保持完整

**外部调用者无需修改：**
```typescript
// 重构前
import { get_stock_realtime_price } from '../infrastructure/akshare-ts/index.js';

// 重构后（完全相同）
import { get_stock_realtime_price } from '../infrastructure/akshare-ts/index.js';
```

**内部实现变化：**
```typescript
// 重构前：所有函数在 index.ts 中
// 重构后：函数分散在各模块，通过 index.ts 统一导出
```

---

### 5.3 风险控制

**风险点：**
1. **循环依赖** — 模块之间相互引用
2. **路径错误** — import 路径写错
3. **遗漏函数** — 某些函数未正确导出
4. **类型丢失** — 类型定义未正确迁移

**缓解措施：**
1. **严格遵循分层依赖规则** — 数据层 → 指标层 → 服务层
2. **逐模块验证** — 每迁移一个模块，立即测试其导出
3. **保留原文件** — 迁移完成前不删除原 index.ts
4. **自动化测试** — 运行现有测试套件验证功能一致性

---

## 6. 测试验证

### 6.1 验证清单

**编译验证：**
- [ ] 所有新文件通过 TypeScript 编译
- [ ] 无循环依赖警告
- [ ] 无类型错误

**导出验证：**
- [ ] `index.ts` 导出所有 22 个函数
- [ ] `TS_FUNCTIONS` 注册表包含所有函数映射
- [ ] 外部调用者可以正常 import

**功能验证（手动测试关键函数）：**
- [ ] `get_stock_realtime_price('600519')` — 返回实时行情
- [ ] `get_stock_history('600519', 'daily')` — 返回历史数据
- [ ] `calculate_technical_indicators('600519')` — 返回技术指标
- [ ] `calculate_buy_range('600519')` — 返回买入区间
- [ ] `analyze_price_action('600519')` — 返回走势分析
- [ ] `analyze_candlestick('600519')` — 返回K线形态
- [ ] `get_quality_score('600519')` — 返回质量评分
- [ ] `manage_portfolio('get')` — 返回持仓列表

**集成验证：**
- [ ] `src/infrastructure/tools/invest-tools.ts` 正常工作
- [ ] Agent 可以正常调用所有工具函数
- [ ] 现有测试套件全部通过（如果有）

---

### 6.2 预期结果

**代码结构：**
- ✅ 10 个模块文件，每个 60-200 行
- ✅ 总行数 ~1,280 行（略有增加）
- ✅ 清晰的分层架构

**功能行为：**
- ✅ 所有函数行为完全一致
- ✅ 返回数据格式不变
- ✅ 性能无明显下降

**可维护性：**
- ✅ 每个模块职责单一
- ✅ 依赖关系清晰
- ✅ 易于添加新功能

---

## 7. 未来扩展

### 7.1 新功能归属指南

**添加新的市场数据源：**
- 放在 `data/market.ts` 或 `data/financial.ts`

**添加新的技术指标：**
- 纯计算逻辑 → `indicators/technical.ts`
- 图表分析 → `indicators/chart-patterns.ts`

**添加新的分析服务：**
- 组合多个数据源/指标 → `services/` 下新建文件

**添加新的工具函数：**
- 通用工具 → `shared.ts`
- 特定领域工具 → 对应模块内部

---

### 7.2 进一步优化方向

**如果某个模块继续膨胀（>300行）：**
1. `data/market.ts` → 拆分为 `data/market-cn.ts` 和 `data/market-hk.ts`
2. `data/financial.ts` → 拆分为 `data/financial-score.ts` 和 `data/financial-flow.ts`
3. `services/` → 按业务场景细分

**性能优化：**
- 考虑缓存层（Redis）替代文件缓存
- 批量数据获取接口
- 并行请求优化

**测试覆盖：**
- 为每个模块添加单元测试
- 集成测试覆盖关键数据流
- Mock 外部数据源

---

## 8. 总结

### 8.1 设计要点

1. **分层架构** — 数据层 → 指标层 → 服务层，依赖单向流动
2. **单一职责** — 每个模块只负责一个明确的领域
3. **向后兼容** — 公共 API 完全不变，外部调用者无需修改
4. **渐进迁移** — 分 9 个阶段逐步迁移，每步可验证

### 8.2 预期收益

**短期收益：**
- 代码可读性提升 — 每个文件职责清晰
- 修改风险降低 — 改动范围可控
- 测试更容易 — 可针对单个模块测试

**长期收益：**
- 可维护性提升 — 新人更容易理解代码结构
- 可扩展性提升 — 新功能有明确的归属位置
- 团队协作更顺畅 — 不同人可以并行开发不同模块

---

**设计完成日期：** 2026-05-14  
**下一步：** 编写实施计划（implementation plan）

