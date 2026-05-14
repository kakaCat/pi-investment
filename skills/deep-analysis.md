---
name: deep-analysis
description: 对单只A股做全面投研分析（基本面+估值+技术面+资金面，港股请用 get_hk_analysis）
---

# 深度分析技能 — 专业投资人工作流 v4（异步并行版）

## 📝 输出格式规范（覆盖 IDENTITY 限制）

**本技能使用完整 markdown 格式输出分析报告**：
- ✅ 使用 `##` 一级标题、`###` 二级标题
- ✅ 标题前后必须有空行
- ✅ 使用列表、表格、粗体等格式
- ⚠️ 本技能输出格式优先级高于 IDENTITY.md 的格式限制

## 允许的工具（Skill Guard 白名单）

本技能允许调用以下工具：
- `plan_task()`
- `task_create()`
- `task_update()`
- `task_execute_async()`
- `get_market_overview()`
- `get_quality_score()`
- `get_financial_data()`
- `manage_portfolio()`
- `get_stock_price()`
- `get_stock_info()`
- `get_valuation()`
- `get_pe_percentile()`
- `analyze_price_action()`
- `analyze_technical()`
- `analyze_candlestick()`
- `predict_stock_signal()`
- `get_stock_news()`
- `get_announcements()`
- `get_buy_range()`
- `get_stock_fund_flow()`
- `get_holder_changes()`
- `get_macro_data()`
- `get_north_flow()`
- `reflect()`

## 触发条件

用户要求分析某只具体 **A股** 股票时使用此技能。

关键词：分析、研究、评估、值不值得买、怎么看、帮我看看

> 港股（1-5位代码）→ 使用 `get_hk_analysis`，不走本流程。

---

## ⚠️ 强制约束

**禁止直接调用投资工具！** 必须通过 task_execute_async 异步执行。

**第一步必须是 plan_task**，否则违反流程。

---

## 执行流程（使用异步任务系统）

### 📋 Stage 0 — 规划（第一步，强制执行）

**步骤0**: 读取用户画像（如果存在）
- 使用 `memory_search` 查询：资金量、风险偏好、投资周期
- 用于后续个性化建议

**步骤1**: 使用 `plan_task()` 规划整体分析流程

**步骤2**: 使用 `task_create` 批量创建所有分析任务

⚠️ **强制要求**：必须创建以下17个任务，缺一不可：

```
task_create({
  tasks: [
    {subject: "获取大盘状态", description: "get_market_overview"},
    {subject: "获取质量评分", description: "get_quality_score"},
    {subject: "获取财务数据", description: "get_financial_data"},
    {subject: "检查持仓状态", description: "manage_portfolio"},
    {subject: "获取实时价格", description: "get_stock_price"},
    {subject: "获取股票信息", description: "get_stock_info"},
    {subject: "获取估值数据", description: "get_valuation"},
    {subject: "获取PE分位", description: "get_pe_percentile"},
    {subject: "技术面分析", description: "analyze_price_action"},
    {subject: "量化技术分析", description: "analyze_technical"},
    {subject: "K线形态分析", description: "analyze_candlestick"},
    {subject: "机器学习预测", description: "predict_stock_signal"},
    {subject: "获取新闻舆情", description: "get_stock_news"},
    {subject: "获取公告信息", description: "get_announcements"},
    {subject: "计算买入区间", description: "get_buy_range"},
    {subject: "获取资金流向", description: "get_stock_fund_flow"},
    {subject: "获取股东变化", description: "get_holder_changes"}
  ]
})
```

**检查清单**（创建后自查）：
- [ ] 17个任务全部创建
- [ ] 包含 predict_stock_signal（量化预测）
- [ ] 包含 analyze_candlestick（K线形态）
- [ ] 包含 get_buy_range（买入区间）
- [ ] 包含 manage_portfolio（持仓检查）
- [ ] 包含 get_holder_changes（股东变化）

---

### ⚡ Stage 1 — 第0步：宏观环境 + 过滤关（异步并行）

使用 `task_execute_async` 并行执行前4个任务：

```
task_execute_async({
  executions: [
    {task_id: 1, tool_name: "get_market_overview", params: {}},
    {task_id: 2, tool_name: "get_quality_score", params: {symbol: "600519"}},
    {task_id: 3, tool_name: "get_financial_data", params: {symbol: "600519"}},
    {task_id: 4, tool_name: "manage_portfolio", params: {action: "get_with_pnl"}}
  ]
})
```

**等待结果**：下一轮收到 `<background-results>` 后继续

**过滤规则**：
- 质量分 < 50 → 直接回避，终止流程
- 财务数据失败 → 停止，提示重试

---

### 📊 Stage 2 — 第1步：基本面（异步并行）

```
task_execute_async({
  executions: [
    {task_id: 5, tool_name: "get_stock_price", params: {symbol: "600519"}},
    {task_id: 6, tool_name: "get_stock_info", params: {symbol: "600519"}}
  ]
})
```

**周期股额外任务**（识别到石油/煤炭/钢铁/有色/化工时）：
- 创建额外任务并异步执行宏观数据和北向资金

---

### 🔍 Stage 3 — 第2步：估值 + 技术 + 量化 + 舆情（异步并行）

```
task_execute_async({
  executions: [
    {task_id: 7, tool_name: "get_valuation", params: {symbol: "600519"}},
    {task_id: 8, tool_name: "get_pe_percentile", params: {symbol: "600519"}},
    {task_id: 9, tool_name: "analyze_price_action", params: {symbol: "600519"}},
    {task_id: 10, tool_name: "analyze_technical", params: {symbol: "600519"}},
    {task_id: 11, tool_name: "analyze_candlestick", params: {symbol: "600519"}},
    {task_id: 12, tool_name: "predict_stock_signal", params: {symbol: "600519"}},
    {task_id: 13, tool_name: "get_stock_news", params: {symbol: "600519"}},
    {task_id: 14, tool_name: "get_announcements", params: {symbol: "600519"}}
  ]
})
```

---

### 💰 Stage 4 — 第3步：聪明钱验证（异步并行）

```
task_execute_async({
  executions: [
    {task_id: 15, tool_name: "get_buy_range", params: {symbol: "600519"}},
    {task_id: 16, tool_name: "get_stock_fund_flow", params: {symbol: "600519"}},
    {task_id: 17, tool_name: "get_holder_changes", params: {symbol: "600519"}}
  ]
})
```

---

### 🏦 Stage 5 — 第4步（条件触发）：机构认可度

**触发条件**（全部满足）：
- 质量分 ≥ 60
- 主力近5日净流入 > 0
- 当前价在买入区间内

创建并异步执行机构数据任务。

---

## 关键改进

1. **使用 task_execute_async** 替代同步并行调用
2. **所有任务预先创建** 便于追踪进度
3. **自动等待机制** Agent Loop 自动等待后台任务完成
4. **更快的执行速度** 真正的并行执行，不阻塞主线程

---

## 公告解析规则

拿到公告标题后，强制打标签：

| 信号类型 | 关键词 |
|---------|--------|
| 🟢 利好 | 回购、增持、业绩预增、重大合同、战略合作、分红、股权激励 |
| 🔴 利空 | 减持、质押、诉讼/仲裁、业绩预减/亏损、监管处罚、高管离职 |
| 🟡 需判断 | 重组（看对价）、定增（看价格用途）、股权变更（看买方） |

---

## 输出格式（必须严格遵守）

**CRITICAL: 禁止输出详细报告！用户要的是操作建议，不是数据堆砌！**

### 强制三段式结构

```
【操作建议】
- 结论：买入/观望/回避（一句话理由）
- 买入区间：XX ~ XX 元
- 分批策略：第1批30%在XX元，第2批40%在XX元，第3批30%在XX元
- 止损位：XX 元
- 止盈目标：XX 元
- 仓位建议：XX%（大盘弱势减半）

【核心数据】
- 大盘：上证XXXX（XX%），市场状态XX
- 持仓：未持有 / 已持有XX股，成本XX元，盈亏XX%
- 质量：XX/100分（grade X），财务趋势XX
- 估值：PE XX倍，历史XX%分位（低估/合理/高估）
- 走势：短期XX，中期XX，支撑XX元，阻力XX元
- 量化：上涨概率XX%，技术信号XX，K线形态XX
- 主力：近5日XX亿，股东人数XX
- 风险：XX（最重要的1-2条）

💡 想了解详细分析？可以问我：
- "为什么是这个买入价？" → 展开估值和技术支撑
- "财务数据怎么样？" → 详解ROE、负债率、利润趋势
- "技术指标如何？" → 展开KDJ、RSI、MACD、量价
- "有什么风险？" → 展开公告、新闻、机构动向
```

### 用户追问时才展开的详细数据

- 估值详情：格雷厄姆估值、PB、市值对比
- 技术详情：KDJ、RSI、CCI、MACD、量比、OBV、ATR、回撤、52周高低
- 量化详情：上涨概率模型、K线形态分析、技术指标信号
- 资金详情：龙虎榜、基金持仓、北向资金
- 消息详情：公告解析、新闻舆情

---

## 关键约束

1. **数据规则**：结论 100% 基于工具返回，禁止用训练知识补充
2. **关键工具失败**（价格/财务）→ 停止，告知用户
3. **辅助工具失败**（新闻/公告）→ 继续，标注"XX数据不可用"
4. **估值数据为0**（PE=0/PB=0）→ 不输出格雷厄姆价，改用 PE 分位
5. **并行调用**：同一步内工具必须在同一条消息中全部发起
6. **大盘降级**：弱势大盘下所有结论自动降一级，明确标注原因
7. **周期股规则**：PE 分位权重 ≤ 30%，股息率和大宗品价格权重 ≥ 50%
8. **购买指南强制输出**：结论为"买入"时，必须输出完整的【购买指南】区块
9. **分批价格计算**：基于买入区间和技术支撑位，不能随意编造
10. **资金示例真实性**：根据当前股价和建议仓位计算，确保可执行
11. **量化分析强制**：所有股票分析必须包含量化预测（predict_stock_signal）
12. **技术分析完整**：必须同时调用 analyze_price_action 和 analyze_candlestick
13. **上涨概率权重**：上涨概率>70%为强看涨信号，<30%为强看跌信号
14. **矛盾信号处理**：量化信号与传统分析矛盾时，在风险中明确说明
