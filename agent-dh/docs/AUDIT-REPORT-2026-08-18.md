# Agent-DH 完整审计报告

**审计日期**: 2026-08-18
**审计范围**: agent-dh 全部 19 个包/插件 + profile 配置
**审计维度**: 架构设计、代码质量、功能完整性、依赖关系、潜在风险

---

## 一、架构总览

```
agent-dh/
├── packages/
│   ├── investment              ✅ 已优化 (8 tools)
│   ├── trading                 ⚠️ 需优化 (6 tools)
│   ├── intelligence            ⚠️ 需优化 (3 tools)
│   ├── competition             ⚠️ 需优化 (3 tools)
│   ├── market                  ⚠️ 需优化 (3 tools)
│   ├── risk                    ⚠️ 需优化 (3 tools)
│   ├── strategy                ⚠️ 需优化 (6 tools)
│   ├── factor                  ⚠️ 需优化 (2 tools)
│   ├── model                   ⚠️ 需优化 (3 tools)
│   ├── memory                  ⚠️ 需优化 (3 tools)
│   ├── evolution               ⚠️ 需优化 (2 tools)
│   ├── scheduler               ⚠️ 需优化 (1 tool)
│   ├── notification            ⚠️ 需优化 (2 tools)
│   ├── data-manager            ⚠️ 需优化 (2 tools)
│   ├── quantsys-v2-client      ✅ 客户端库
│   ├── agent-os-client         ✅ 客户端库
│   ├── agent-dh-client         ⚠️ 旧架构兼容层
│   └── investment-agent-loop   ⚠️ 旧架构兼容层
├── profile/ (~/.dsh/profiles/investment/)
│   ├── cordis.patch.yml        ✅ 14插件配置
│   ├── cordis.yml              ✅ 基础配置
│   ├── package.json            ⚠️ 路径硬编码
│   └── start.sh                ✅ 启动脚本
```

**插件统计**: 14 个 PI 插件，48 个工具（investment 8 个已优化，其余 40 个待优化）

---

## 二、按维度审计

### 2.1 架构设计 ✅ 良好

**设计模式**: 所有 14 个插件统一使用 Cordis Service 模式：
- `class extends Service`
- `static inject = ['tools']`
- `static Config = z.object(...)`
- 构造函数中注册工具

**分层清晰**:
- **数据层**: `quantsys-v2-client` → HTTP API 调用
- **插件层**: 14 个领域插件 → 工具注册
- **配置层**: `cordis.patch.yml` → 插件加载与系统提示词

**双后端支持**:
- quantsys-v2 插件（11 个）→ 端口 5001
- agent-os 插件（4 个）→ 端口 8080

### 2.2 代码质量

#### ✅ 优点

1. **统一错误处理**: quantsys-v2-client 有 axios-retry（3 次指数退避重试）
2. **响应信封解包**: `unwrap()` 方法处理 `{success, data}`、`{success, rules}`、无信封三种模式
3. **类型定义完整**: `types.ts` 定义了所有数据接口
4. **工具描述规范**: investment 插件示范了"用于：..."+示例+单位标注的规范

#### ⚠️ 问题

| # | 问题 | 严重程度 | 位置 |
|---|------|---------|------|
| 1 | **大量方法存根未实现** | 🔴 高 | quantsys-v2-client |
| 2 | **插件 package.json 依赖错误** | 🔴 高 | memory/evolution/scheduler/notification |
| 3 | **旧架构残留代码** | 🟡 中 | trading/intelligence 的 tools/ 目录 |
| 4 | **agent-dh-client 指向 dist** | 🟡 中 | package.json main |
| 5 | **profile package.json 硬编码路径** | 🟡 中 | ~/.dsh/profiles/investment/package.json |
| 6 | **投资插件 3 个工具无真实 API** | 🟡 中 | data_fetch_macro/north_flow/market_sentiment |
| 7 | **scheduler_manage 部分操作未实现** | 🟡 中 | enable/disable/delete |
| 8 | **缺少输入验证** | 🟢 低 | 多数工具 execute 无参数校验 |

### 2.3 功能完整性

#### 🔴 未实现的方法存根（quantsys-v2-client）

以下方法被插件调用但 **客户端中不存在**，运行时会抛 `TypeError: qv2.xxx is not a function`：

| 插件 | 工具 | 调用的缺失方法 |
|------|------|--------------|
| trading | portfolio_trade | `executeTrade()` |
| trading | trade_monitor | `getTradeHistory()` |
| trading | algo_execute | `executeAlgo()` |
| trading | trade_verify | `verifyTrades()` |
| intelligence | watch_manage | `manageWatchRule()` |
| intelligence | market_alert | `getAlerts()` |
| competition | opponent_behavior | `getOpponentBehavior()` |
| competition | pool_battlefield | `getPoolBattlefield()` |
| competition | manipulation_detect | `detectManipulation()` |
| market | sector_analysis | `getSectorAnalysis()` |
| risk | risk_controller | `riskControl()` |
| risk | risk_metrics | `getRiskMetrics()` |
| risk | risk_barra_decomposition | `getBarraDecomposition()` |
| strategy | strategy_execute | `generateSignals()` |
| strategy | opportunity_scan | `scanOpportunities()` |
| strategy | screening | `screenStocks()` |
| strategy | rotation_proposal | `generateRotationProposal()` |
| strategy | rotation_simulate | `simulateRotation()` |
| strategy | rotation_execute | `executeRotation()` |
| factor | factor_calculate | `calculateFactors()` |
| factor | factor_analyze | `analyzeFactor()` |
| model | model_predict | `predictWithModel()` |
| model | model_train | `trainModel()` |
| model | model_evaluate | `evaluateModel()` |
| data-manager | data_quality_report | `getDataQualityReport()` |
| data-manager | data_manager | `dataManager()` |

**总计**: 25 个缺失方法，涉及 12 个插件的 25 个工具

#### 🟡 部分实现的方法

| 方法 | 状态 | 说明 |
|------|------|------|
| `getFinancialData()` | ⚠️ 特殊处理 | 使用 `.data.data \|\| .data` fallback，非标准 unwrap |
| `listWatchRules()` | ✅ 已实现 | 特殊信封 `{success, rules}` |
| `getPositions()` | ✅ 已实现 | 解包后取 `.positions` |
| `getPortfolioSummary()` | ✅ 已实现 | 标准 unwrap |
| `getEvolutionLeaderboard()` | ✅ 已实现 | 标准 unwrap |
| `getEvolutionDecisionScores()` | ✅ 已实现 | 标准 unwrap |

#### 🟡 无真实后端 API 的工具（返回 mock/note）

| 工具 | 插件 | 当前行为 |
|------|------|---------|
| data_fetch_macro | investment | 返回 `{indicator, note: 'API endpoint needed'}` |
| data_fetch_north_flow | investment | 返回 `{days, note: 'API endpoint needed'}` |
| data_fetch_market_sentiment | investment | 返回 `{note: 'API endpoint needed'}` |

### 2.4 依赖关系

#### 🔴 严重：4 个 agent-os 插件依赖错误

memory、evolution、scheduler、notification 的 `package.json` 声明了：
```json
"dependencies": {
  "@pi-investment/quantsys-v2-client": "workspace:*"   // ❌ 错误
}
```

但它们实际使用的是 `@pi-investment/agent-os-client`，**缺少依赖声明**。

当前能运行是因为 profile 的 package.json 同时声明了两者，但插件自身依赖不完整。

**修复方案**:
```json
"dependencies": {
  "@pi-investment/agent-os-client": "workspace:*",    // ✅ 添加
  // 删除 @pi-investment/quantsys-v2-client            // ✅ 删除不需要的
}
```

#### 🟡 agent-dh-client 未适配 tsx 模式

```json
"main": "./dist/index.mjs"   // ❌ tsx 无法直接加载
```

当前 profile package.json 未引用 `@pi-investment/agent-dh-client`，所以不影响。但如需使用，应改为 `"main": "./src/index.ts"`。

#### 🟡 profile package.json 硬编码绝对路径

```json
"@pi-investment/investment": "file:/Users/yunpeng/pi-investment/agent-dh/packages/investment"
```

这导致配置不可移植。应使用 workspace 链接或相对路径。

### 2.5 旧架构残留

trading 和 intelligence 插件有旧架构的残留文件：

```
trading/src/tools/
  ├── account-info-tool.ts      # 旧工厂函数模式
  └── position-list-tool.ts     # 旧工厂函数模式
├── smoke.test.ts               # 引用旧 API
└── tools.test.ts               # 引用旧 API

intelligence/src/tools/
  ├── evolution-status-tool.ts  # 旧工厂函数模式
  └── watch-list-tool.ts        # 旧工厂函数模式
```

这些文件使用 `createXxxTool(mockClient)` 工厂函数模式，与当前 Cordis Service 模式不兼容。

investment-agent-loop 包也是旧架构产物，当前未被 profile 引用。

---

## 三、工具描述质量对比

### ✅ 已优化（investment 插件）

| 维度 | 质量 |
|------|------|
| 使用场景 | 开头明确"用于：..." |
| 参数示例 | 包含具体股票代码示例 |
| 枚举解释 | 每个枚举值都有中文说明 |
| 输出字段 | 完整 schema，含单位标注 |
| 单位标注 | 元/股/% 明确 |

### ⚠️ 待优化（其他 13 个插件）

| 维度 | 典型问题 |
|------|---------|
| 使用场景 | 部分有"用于："，部分没有 |
| 参数示例 | 部分缺少具体示例 |
| 枚举解释 | 部分枚举值无中文说明 |
| 输出字段 | 部分使用泛型描述（如"订单列表"） |
| 单位标注 | 部分缺少单位 |

---

## 四、风险评级

| 风险 | 等级 | 影响 | 修复优先级 |
|------|------|------|-----------|
| 25 个方法存根未实现 | 🔴 高 | 工具调用崩溃 | P0 |
| 4 个插件依赖声明错误 | 🔴 高 | 潜在运行时错误 | P0 |
| 3 个投资工具无真实 API | 🟡 中 | 返回空数据 | P1 |
| scheduler 部分操作未实现 | 🟡 中 | enable/disable/delete 无效 | P1 |
| profile 硬编码路径 | 🟡 中 | 不可移植 | P1 |
| 旧架构残留文件 | 🟢 低 | 代码冗余 | P2 |
| 40 个工具描述待优化 | 🟢 低 | LLM 理解效果 | P2 |

---

## 五、修复建议

### P0 - 必须立即修复

1. **在 quantsys-v2-client 中实现 25 个缺失方法**
   - 每个方法至少返回 mock 数据，避免运行时崩溃
   - 优先实现 trading 和 intelligence 的 9 个方法（核心交易链路）

2. **修复 4 个 agent-os 插件的 package.json**
   - 添加 `@pi-investment/agent-os-client` 依赖
   - 移除不需要的 `@pi-investment/quantsys-v2-client` 依赖

### P1 - 尽快修复

3. **为 3 个无 API 的投资工具添加后端端点或 mock**
   - `data_fetch_macro` → 对接宏观数据 API
   - `data_fetch_north_flow` → 对接北向资金 API
   - `data_fetch_market_sentiment` → 对接情绪指标 API

4. **完成 scheduler_manage 的 enable/disable/delete 操作**

5. **将 profile package.json 改为相对路径或 workspace 链接**

### P2 - 后续优化

6. **清理旧架构残留文件**（trading/src/tools/, intelligence/src/tools/, investment-agent-loop/）

7. **优化 40 个工具描述**（可并行批量处理）

8. **添加 execute 参数校验**

---

## 六、运行状态

当前 DSH 可以正常启动：
```bash
cd ~/.dsh/profiles/investment
./start.sh 13080
# → dsh web: http://127.0.0.1:13080
```

但调用未实现方法的工具时会崩溃。已实现的工具（investment 的 8 个 + 部分其他）可以正常工作。

---

## 七、总结

**Agent-DH 架构设计良好**，Cordis Service 模式统一、清晰。主要问题是：

1. **功能缺口大**: 25/48 个工具（52%）调用的方法未实现
2. **依赖有错误**: 4 个插件声明了错误的依赖
3. **描述待优化**: 40/48 个工具（83%）描述可提升

**建议修复顺序**: P0 依赖修正 → P0 方法存根实现 → P1 API 补齐 → P2 描述优化
