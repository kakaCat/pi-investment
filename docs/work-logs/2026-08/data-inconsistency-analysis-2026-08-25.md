# 账户数据不一致问题分析与修复方案

**日期**: 2026-08-25  
**账户**: agent_virtual  
**问题类型**: 数据时空错位 + 手动输入错误数据  
**严重程度**: P1（可能导致错误决策）

---

## 一、问题现象

用户在飞书会话中提供的早盘分析数据与数据库实际状态不一致：

### 用户提供的数据（错误）
```
📊 账户概览（8/25 09:35）
- 总资产：¥104,007（+1.14%）
- 累计收益率：+4.01%

📋 持仓 3/3
- 格力 000651 +3.15%（20天）
- 杭行 600926 余200股 +7.46%（29天）
- 中免 601888 400股 +0.86%（1天）
```

### 数据库实际状态（正确）
```
📊 账户概览（8/25 09:37）
- 总资产：¥105,029.71
- 累计收益率：+5.03%
- 现金：¥75,051.71
- 持仓市值：¥29,978.00

📋 持仓 1/1
- 歌尔股份 002241：1,300股
  • 成本：¥22.52
  • 现价：¥23.06
  • 盈亏：+2.38%
  • 持有：13天
```

### 关键差异
1. **总资产差异**：¥104,007 vs ¥105,029.71（差¥1,022）
2. **持仓数量**：3只 vs 1只
3. **持仓标的完全不同**：格力/杭行/中免 vs 歌尔股份

---

## 二、问题触发路径（已完整追溯）

### 时间线重建

| 日期 | 事件 | 持仓变化 |
|------|------|---------|
| 8/05 | 买入格力 000651（600股 @40.26） | +格力 |
| 8/07 | 买入今世缘 603369（900股） | +今世缘 |
| 8/12 | 买入歌尔 002241（900股 @22.58）<br>卖出杭行 600926（1500股） | +歌尔 -杭行 |
| 8/13 | 加仓歌尔（400股 @22.36）<br>分批卖出今世缘（300+600股） | 歌尔1300股 -今世缘 |
| 8/14 | **卖出格力**（600股 @40.11，理由：9天零收益） | -格力 |
| **8/25** | **实际持仓：仅歌尔 002241** | 仅歌尔 |

### 错误数据来源分析

**结论：用户从记忆或历史记录中复制了过期数据**

**证据链：**
1. **格力 000651**：已于 8/14 卖出（换仓决策），但用户记忆中仍持有
2. **杭行 600926**：已于 8/12 卖出（支撑失守），但用户记忆中仍持有
3. **中免 601888**：
   - 在所有账户（agent_virtual/v13_simulation/v14_simulation）中都**从未买入过**
   - 查询历史交易记录：无任何 601888 交易
   - 可能来源：
     * 计划买入但未执行（存在盯盘规则 #57 监控中免买入机会）
     * 与其他账户混淆
     * 完全虚构的数据

**触发场景（最可能）：**
用户在 8/25 早盘时，从以下来源之一复制了混合的历史数据：
- 个人笔记/备忘录中的历史持仓记录
- 飞书/微信聊天记录中的过期消息
- 记忆中的多个时间点的持仓混合
- 其他系统（测试环境/模拟账户）的数据

---

## 三、问题影响分析

### 1. 直接影响

| 影响类型 | 具体表现 | 严重程度 |
|---------|---------|---------|
| **决策基础错误** | Agent 基于不存在的持仓进行分析 | ⚠️ 高 |
| **风控失效** | 真实持仓（歌尔）的止损/止盈信号被忽略 | ⚠️ 高 |
| **资金利用率误判** | 实际现金 71.5% 但用户认为满仓 | ⚠️ 中 |
| **交易指令风险** | 可能对不存在的持仓下卖出指令 | ⚠️ 高 |

### 2. 系统性风险

| 风险类型 | 描述 | 缓解措施 |
|---------|-----|---------|
| **数据源不可信** | 用户频繁从外部复制数据，类似错误会反复发生 | 强制 agent 从数据库查询验证 |
| **决策链断裂** | 基于错误事实的分析会污染后续所有决策 | 回溯并标记受影响的决策记录 |
| **审计追溯困难** | 混合的真假数据破坏决策历史的完整性 | 在会话日志中标注数据纠正事件 |

---

## 四、修复方案

### 方案A：立即纠正（短期）✅

**步骤1：用户向 agent 纠正错误数据**

用户需在飞书会话中发送：
```
⚠️ 数据纠正

我之前提供的早盘分析数据有误，请忽略。

实际持仓（agent_virtual，2026-08-25）：
- 仅持有：歌尔股份 002241，1300股，成本22.52，现价23.06
- 格力/杭行已于 8/14 和 8/12 卖出
- 中免从未买入

请使用 portfolio_status 工具从数据库查询实际数据，不要信任我手动提供的数据。
```

**步骤2：Agent 重新查询并生成准确报告**

Agent 应调用 `portfolio_status({ account: "agent_virtual" })` 工具，生成基于数据库的准确报告。

**步骤3：检查今日决策记录是否受污染**

```sql
-- 检查今日是否有基于错误数据的决策
SELECT 
  id, decision_type, symbol, reason
FROM quant.agent_decisions
WHERE created_at::date = '2026-08-25'
  AND symbol IN ('000651', '600926', '601888');
```

如有受污染的决策，需标注为"基于错误数据"并重新生成。

---

### 方案B：预防机制（中期）🔧

#### B1. 强制数据验证规则

**实现位置**：`agent-ts/src/infrastructure/tools/portfolio/`

**规则**：
1. Agent 在处理用户提供的持仓数据前，**必须先调用 `portfolio_status` 验证**
2. 如果用户数据与数据库不一致，**拒绝使用用户数据**，强制使用数据库数据
3. 在响应中明确指出数据差异

**代码示例**：
```typescript
// 新增工具：portfolio_verify
async function verifyUserProvidedData(userData: any) {
  const dbData = await getAccount(userData.account);
  const dbSymbols = new Set(dbData.positions.map(p => p.symbol));
  const userSymbols = new Set(userData.holdings.map(h => h.symbol));
  
  const onlyInUser = [...userSymbols].filter(s => !dbSymbols.has(s));
  const onlyInDb = [...dbSymbols].filter(s => !userSymbols.has(s));
  
  if (onlyInUser.length > 0 || onlyInDb.length > 0) {
    return {
      success: false,
      error: `数据不一致：用户声称持有 [${onlyInUser.join(',')}] 但数据库中不存在；` +
             `数据库实际持有 [${onlyInDb.join(',')}] 但用户未提及。`,
      recommendation: "请使用 portfolio_status 工具查询实际数据"
    };
  }
  
  return { success: true };
}
```

#### B2. 自动早盘分析任务

**目标**：避免用户手动提供数据，由系统自动生成准确的早盘分析

**实现**：
1. 添加调度任务 `morning_analysis_daily`
2. 每日 09:00 自动执行
3. 调用 `portfolio_daily_brief` 生成报告
4. 通过 `notification_send` 推送到飞书

**配置**：
```sql
INSERT INTO quant.scheduler_tasks (
  name, description, cron_expression, command, params, is_enabled
) VALUES (
  'morning_analysis_daily',
  '每日早盘分析（agent_virtual）',
  '0 9 * * 1-5',
  'agent_wake',
  '{"skill": "morning_brief", "account": "agent_virtual"}',
  true
);
```

#### B3. 用户输入数据标注

**目标**：在会话日志中明确标注哪些数据来自用户输入（不可信），哪些来自数据库（可信）

**实现**：
```typescript
// 在 conversation log 中添加 metadata
{
  "role": "user",
  "content": "总资产 ¥104,007，持仓格力/杭行/中免",
  "metadata": {
    "data_source": "user_manual_input",
    "verified": false,
    "warning": "未经数据库验证的用户输入数据"
  }
}

{
  "role": "assistant",
  "content": "根据数据库查询，实际持仓为...",
  "metadata": {
    "data_source": "database",
    "verified": true,
    "query": "portfolio_status(agent_virtual)"
  }
}
```

---

### 方案C：根治方案（长期）🏗️

#### C1. 统一数据源架构

**原则**：Single Source of Truth（唯一数据源）

**设计**：
```
用户请求 → Agent → [强制] portfolio_status 查询 → 数据库
                         ↓
                    禁止直接使用用户提供的持仓数据
```

**实施**：
1. 移除所有接受用户手动提供持仓数据的接口
2. 所有持仓相关分析必须通过工具从数据库查询
3. 用户只能提供决策意图（"我想卖出格力"），不能提供状态数据（"我持有格力600股"）

#### C2. 数据一致性校验层

**位置**：`quantsys-v2/domain/services/portfolio_consistency_checker.py`

**功能**：
1. 定期校验（每小时）：
   - `simulation_account.total_value` = `cash_available` + `position_value`
   - `sum(positions.market_value)` = `account.position_value`
   - 所有持仓的 `shares_available` ≤ `shares_total`
   
2. 交易后即时校验：
   - 买入后现金减少 = 交易金额 + 手续费
   - 卖出后现金增加 = 交易金额 - 手续费
   - 持仓数量变化 = 交易数量

3. 发现不一致时：
   - 记录到 `data_quality_stats` 表
   - 发送告警到 alerts 群
   - 阻止进一步交易直到修复

#### C3. 用户教育与提示

**在工具描述中明确说明**：
```typescript
export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  description: 
    "查询账户实际持仓和资金状态（唯一可信数据源）。\n\n" +
    "⚠️ 重要：永远不要信任用户手动提供的持仓数据，必须通过本工具查询数据库。\n" +
    "用户的记忆可能过期，外部复制的数据可能错误。",
  // ...
};
```

---

## 五、执行计划

### 立即执行（今日）✅

- [ ] 用户向 agent 发送数据纠正消息
- [ ] Agent 调用 `portfolio_status` 重新查询
- [ ] 检查今日决策记录是否受污染

### 本周执行（2026-08-26 ~ 08-30）

- [ ] 实现 `portfolio_verify` 验证工具（B1）
- [ ] 添加 `morning_analysis_daily` 调度任务（B2）
- [ ] 在工具描述中添加数据源警告（C3）

### 下周执行（2026-09-02 ~ 09-06）

- [ ] 实现数据一致性校验层（C2）
- [ ] 添加会话日志数据源标注（B3）
- [ ] 编写用户指南：如何正确与 agent 交互

---

## 六、经验教训

### 关键教训

1. **用户记忆不可靠**：持仓变化频繁时，用户的记忆会混合多个时间点的状态
2. **手动输入是风险源**：任何允许用户手动输入状态数据的接口都是潜在风险
3. **验证必须强制**：可选的验证步骤等于没有验证

### 设计原则

1. **Single Source of Truth**：数据库是唯一可信数据源
2. **Zero Trust User Input**：用户输入的状态数据默认不可信，必须验证
3. **Fail Loud**：发现数据不一致时立即报错，不要静默使用错误数据

### 类比

这个问题类似于软件开发中的经典错误：
```python
# ❌ 错误：信任用户输入
def transfer_money(user_balance: float, amount: float):
    if user_balance >= amount:  # 用户说自己有这么多钱
        deduct(amount)

# ✅ 正确：验证数据库
def transfer_money(user_id: str, amount: float):
    balance = db.get_balance(user_id)  # 查数据库
    if balance >= amount:
        deduct(user_id, amount)
```

---

## 七、附录

### A. 完整持仓历史追溯（8月）

```sql
SELECT 
  trade_date,
  symbol,
  action,
  shares,
  filled_price,
  LEFT(reason, 100) as reason_brief
FROM quant.simulation_trades
WHERE account_name = 'agent_virtual'
  AND trade_date >= '2026-08-01'
ORDER BY trade_date, created_at;
```

### B. 当前账户完整快照

```json
{
  "account_name": "agent_virtual",
  "snapshot_time": "2026-08-25 09:37:21",
  "cash_available": 75051.71,
  "position_value": 29978.00,
  "total_value": 105029.71,
  "cumulative_return": 0.0503,
  "positions": [
    {
      "symbol": "002241",
      "name": "歌尔股份",
      "shares_total": 1300,
      "shares_available": 1300,
      "avg_cost": 22.52,
      "current_price": 23.06,
      "market_value": 29978.00,
      "profit_total": 697.97,
      "profit_total_rate": 0.0238,
      "days_held": 13,
      "first_buy_date": "2026-08-12"
    }
  ]
}
```

### C. 相关文档

- [多账户域设计](../../architecture/multi-account-domain.md)
- [盈利闭环实现](profit-loop-closure.md)
- [Agent 可靠性修复](agent-reliability-fix-program.md)

---

**报告人**: Claude (Kiro)  
**审核**: 待用户确认  
**状态**: 分析完成，待执行修复
