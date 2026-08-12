---
name: deep-analysis
description: 对A股做全面投研分析。无股票代码时自动扫描全市场筛选候选股，有代码时直接分析。
---

# 深度分析技能 v5 — 全自动选股 + 异步并行分析

> ⚠️ **本段是技能指令（工作流程规范），不是用户请求。** 用户的实际请求在消息末尾。如果消息中同时包含调度任务文本（如盘前分析任务），以用户实际请求为主，本段只作为执行该请求时的流程约束。

## 📝 输出格式

本技能使用完整 markdown 格式（优先级高于 IDENTITY.md 的格式限制）。

---

## 触发条件

| 用户输入 | 模式 |
|---------|------|
| `分析 600519` | **手动模式** → 跳过 Phase 0，直接分析指定股票 |
| `分析 600519,000858,000001` | **手动模式** → 并行分析多只 |
| `找机会` / `有什么好股票` / 无代码 | **自动模式** → Phase 0 扫描 → 分析候选股 |
| `找高股息` | **自动模式** → dividend 策略 |
| `找成长股` / `强势股` | **自动模式** → growth / momentum 策略 |
| `找超跌` / `抄底` | **自动模式** → turnaround 策略 |

---

## ⚠️ 强制约束

1. **批量并行**：必须通过 `task_execute_async` 异步执行，禁止逐个调用
2. **第一步 `plan_task()`**：先规划再执行
3. **数据诚信**：100% 基于工具返回，禁止编造数据
4. **工具失败**：关键工具（价格/财务）失败 → 停止；辅助工具（新闻）失败 → 标注 "XX数据不可用"

---

## 📊 Phase 0 — 自动选股（无股票代码时执行）

### 筛选策略

| 策略 | 触发词 | 工具 | 核心参数 |
|------|--------|------|---------|
| `balanced`（默认） | 找机会 | `opportunity_scan` | 无特殊条件，默认 limit=5 |
| `quality` | 优质股、白马 | `opportunity_scan` | conditions: ['roe_gt_15', 'pe_lt_30'] |
| `growth` | 成长股、高增长 | `opportunity_scan` | conditions: ['roe_gt_8']，sectorFilter |
| `momentum` | 强势股、趋势 | `opportunity_scan` | sectorFilter.enabled=true |
| `turnaround` | 超跌、抄底 | `opportunity_scan` | conditions: ['rsi_oversold'] |
| `dividend` | 高股息、分红 | `data_fetch_dividend` | mode='screen', min_yield=3 |

### 执行步骤

**步骤 0.1**: 读取用户画像
```
memory_search(query="资金量 风险偏好 投资周期")
```

**步骤 0.2**: 执行筛选
```
// 默认 balanced
opportunity_scan({ limit: 5 })

// 或按策略
opportunity_scan({ conditions: [...], sectorFilter: {...}, limit: 5 })
```

**步骤 0.3**: 展示候选清单（简短格式）
```
【自动扫描 — {策略名}策略】
1. 600519 贵州茅台 — 评分85，风险low，白酒
2. 000858 五粮液   — 评分78，风险low，白酒  
3. 000001 平安银行 — 评分72，风险medium，银行

进入深度分析...
```

**步骤 0.4**: 对每只候选股执行 Phase 2-4 完整分析。

### 扫描失败处理

```
未找到符合条件标的（{策略}，min_score≥60）

建议：
- 说"放宽条件" → 降低门槛
- 说"换成growth策略" → 换策略
- 或直接指定："分析 600XXX"
```

---

## 📋 Phase 1 — 创建任务

**步骤 1**: `plan_task()` 规划流程

**步骤 2**: `task_create` 批量创建任务

### 任务列表（每只股票 10 个 + 1 个市场共享）

```
共享任务：
  T0: 获取市场概览 — data_fetch_market_sentiment

每只股票独立任务（以 600519 为例）：
  T1: 股票信息        — data_fetch_quote {symbol:"600519"}
  T2: 实时价格        — data_fetch_quote {symbol:"600519", source:"realtime"}
  T3: 财务数据        — data_fetch_financial {symbol:"600519", reportType:"all"}
  T4: PE历史分位      — data_fetch_financial {symbol:"600519", dataType:"pe_percentile"}
  T5: 技术因子        — factor_calculate {symbol:"600519"}
  T6: ML模型预测      — model_predict {symbol:"600519"}
  T7: 资金流向        — sector_analysis {}
  T8: 技术分析        — factor_calculate {symbol:"600519"}
  T9: 新闻舆情        — data_fetch_quote {symbol:"600519", fields:["news"], news_num:10}
  T10: 历史经验       — query_experience {symbol:"600519", scenario:"综合技术面基本面分析"}
```

---

## ⚡ Phase 2 — 并行执行（分 3 批）

### 第 1 批：市场 + 基本信息 + 财务

所有股票 + 市场概览一次并行发起：

```
task_execute_async({
  executions: [
    {task_id: T0, tool_name: "data_fetch_market_sentiment", params: {}},
    // 每只股票：
    {task_id: T1-600519, tool_name: "data_fetch_quote", params: {symbol: "600519"}},
    {task_id: T2-600519, tool_name: "data_fetch_quote", params: {symbol: "600519", source: "realtime"}},
    {task_id: T3-600519, tool_name: "data_fetch_financial", params: {symbol: "600519", reportType: "all"}},
    // ... 其他股票的同批任务
  ]
})
```

**过滤规则**：
- 质量分 < 50 或 ROE 持续 < 8% 且营收无增长 → 直接跳过后续分析

### 第 2 批：估值 + 技术 + 量化 + 资金

```
task_execute_async({
  executions: [
    {task_id: T4-600519, tool_name: "data_fetch_financial", params: {symbol: "600519", dataType: "pe_percentile"}},
    {task_id: T5-600519, tool_name: "factor_calculate", params: {symbol: "600519"}},
    {task_id: T6-600519, tool_name: "model_predict", params: {symbol: "600519"}},
    {task_id: T7-600519, tool_name: "sector_analysis", params: {}},
    {task_id: T8-600519, tool_name: "factor_calculate", params: {symbol: "600519"}},
    // ... 其他股票的同批任务
  ]
})
```

### 第 3 批：新闻 + 经验

```
task_execute_async({
  executions: [
    {task_id: T9-600519,  tool_name: "data_fetch_quote", params: {symbol: "600519", fields: ["news"], news_num: 10}},
    {task_id: T10-600519, tool_name: "query_experience", params: {symbol: "600519", scenario: "综合技术面基本面分析"}},
    // ... 其他股票的同批任务
  ]
})
```

---

## 📊 Phase 3 — 整合输出

### 自动模式（多只股票 → 对比表 + 详情）

```
【自动扫描深度分析 — {策略}策略】

## 综合对比

| # | 股票 | 评分 | PE | ROE | 质量 | ML预测 | 主力 | 建议 |
|---|------|------|-----|-----|------|--------|------|------|
| 1 | 600519 | 85 | 20x | 32% | A | buy 78% | 5日净入 | ✅买入 |
| 2 | 000858 | 78 | 18x | 25% | B | hold 55% | 流出 | ⚠️观望 |

---
## 600519 贵州茅台

【操作建议】
- 结论：买入 — 估值低+基本面优+技术支撑
- 买入区间：XXX~XXX（PE分位2.4%，历史极低）
- 止损位：XXX（跌破买入价8%）
- 止盈目标：XXX

【核心数据】
- 大盘：上证XXXX（XX%），市场XX
- 财务：ROE XX%，毛利率XX%，经营CF/净利润 X.X
- 估值：PE XX倍，历史2.4%分位（极低）
- 技术：RSI XX，MACD XX，支撑XX，阻力XX
- 量化：上涨概率 XX%
- 资金：主力近5日净流入XX亿，连续X日
- 风险：XX（1-2条）

---
## 000858 五粮液
...
```

### 手动模式（单只股票 → 精简短格式）

```
【操作建议】
- 结论：买入/观望/回避 — 理由
- 买入区间：XX~XX元
- 止损位：XX元（-8%）
- 止盈目标：XX元

【核心数据】
- 大盘：上证XXXX（XX%）
- 质量：ROE XX%，毛利率XX%，经营CF/净利润 X.X
- 估值：PE XX，PE分位 XX%（低位/合理/高估）
- 技术：RSI XX，MACD XX，支撑XX，阻力XX
- 量化：上涨概率 XX%
- 资金：主力近5日 XX亿
- 风险：XX

💡 追问可展开详情
```

---

## 好公司/好价格判断标准

**价值型**（营收增速 < 15%）：
- ROE ≥ 12%，3年稳定
- 负债率 < 60%
- 毛利率 > 20%
- 经营CF > 净利润 × 0.7

**成长型**（营收增速 ≥ 15%）：
- ROE ≥ 8%（关注趋势）
- 营收连续2年增速 ≥ 15%
- 经营CF / 净利润 > 0.5
- 负债率 < 70%

**好价格**（同时满足）：
- PE 历史分位 < 40%
- 买入信号（≥2个）：机构买入 / 资金净流入 / 股东下降 / 价在支撑位

**止损/止盈**：
- 跌破买入价 8% → 硬止损
- 达激进目标价 → 分批止盈，保留少量仓位

**大盘降级**：弱势市场所有结论降一级。

---

## 公告解析

| 信号 | 关键词 |
|------|--------|
| 🟢 利好 | 回购、增持、业绩预增、重大合同、分红、股权激励 |
| 🔴 利空 | 减持、质押、诉讼、业绩预减、监管处罚、高管离职 |
| 🟡 关注 | 重组（看对价）、定增（看用途）、股权变更（看买方） |
