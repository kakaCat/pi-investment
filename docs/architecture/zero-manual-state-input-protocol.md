# Zero Manual State Input Protocol（零手动状态输入协议）

**版本**: v1.0  
**日期**: 2026-08-25  
**目标**: 根本杜绝用户手动输入状态数据导致的数据不一致问题

---

## 一、设计原则

### 1. Single Source of Truth（唯一真相来源）

```
数据库 = 唯一可信数据源
用户输入 ≠ 数据源，仅为意图表达
```

### 2. Intent vs State（意图 vs 状态）

**允许的输入类型**：
- ✅ **意图**："我想卖出格力"（用户想做什么）
- ✅ **指令**："帮我分析歌尔股份"（要求执行什么）
- ✅ **偏好**："止损线设为-5%"（风险偏好）
- ✅ **问题**："为什么今天亏了？"（请求解释）

**禁止的输入类型**：
- ❌ **状态**："我持有格力600股"（声称拥有什么）
- ❌ **余额**："我还有10万现金"（声称账户状态）
- ❌ **收益**："我今天赚了3%"（声称绩效数据）

### 3. Active Verification（主动验证）

```python
# 旧模式（被动接受）
user: "我持有格力600股，帮我分析"
agent: "好的，格力电器基本面..." ❌

# 新模式（主动验证）
user: "我持有格力600股，帮我分析"
agent: [调用 portfolio_status 查询]
agent: "数据库显示您没有持有格力，已于8/14卖出。要分析的话，我可以查看历史交易记录？" ✅
```

---

## 二、协议实现

### A. 输入分类器（Input Classifier）

**位置**: `agent-ts/src/core/input-classifier.ts`

```typescript
export enum InputType {
  INTENT = "intent",           // 意图：我想买/卖/查询
  QUESTION = "question",       // 问题：为什么/怎么样
  STATE_CLAIM = "state_claim", // 状态声明：我持有/我的余额（⚠️需验证）
  PREFERENCE = "preference"    // 偏好：止损线/风险等级
}

export interface ClassifiedInput {
  type: InputType;
  original: string;
  extracted_symbols?: string[];  // 提及的股票代码
  requires_verification: boolean; // 是否需要验证
  confidence: number;             // 分类置信度
}

export function classifyInput(userMessage: string): ClassifiedInput {
  // 检测状态声明关键词
  const stateClaimPatterns = [
    /我?持有|我?买了|我?的?仓位|我?的?持仓/,
    /余额|现金|资金/,
    /盈利|亏损|收益率/,
    /总资产|市值/
  ];
  
  const isStateClaim = stateClaimPatterns.some(p => p.test(userMessage));
  
  // 提取股票代码/名称
  const symbols = extractSymbols(userMessage);
  
  if (isStateClaim && symbols.length > 0) {
    return {
      type: InputType.STATE_CLAIM,
      original: userMessage,
      extracted_symbols: symbols,
      requires_verification: true,
      confidence: 0.85
    };
  }
  
  // 其他分类逻辑...
}
```

### B. 状态验证拦截器（State Verification Interceptor）

**位置**: `agent-ts/src/core/state-verifier.ts`

```typescript
export class StateVerifier {
  /**
   * 拦截用户的状态声明，强制验证
   */
  async verifyOrReject(input: ClassifiedInput): Promise<VerificationResult> {
    if (!input.requires_verification) {
      return { verified: true, source: "no_verification_needed" };
    }
    
    // 1. 查询数据库实际状态
    const dbState = await this.queryDatabaseState(input.extracted_symbols);
    
    // 2. 解析用户声明
    const userClaim = this.parseUserClaim(input.original);
    
    // 3. 比对
    const discrepancies = this.findDiscrepancies(userClaim, dbState);
    
    if (discrepancies.length > 0) {
      return {
        verified: false,
        source: "database",
        discrepancies,
        recommendation: "使用数据库数据",
        db_state: dbState,
        user_claim: userClaim
      };
    }
    
    return {
      verified: true,
      source: "database",
      db_state: dbState
    };
  }
  
  private findDiscrepancies(userClaim: any, dbState: any): Discrepancy[] {
    const issues: Discrepancy[] = [];
    
    // 检查：用户说持有，但数据库中没有
    for (const symbol of userClaim.claimed_holdings || []) {
      if (!dbState.holdings.some(h => h.symbol === symbol)) {
        issues.push({
          type: "holding_not_found",
          symbol,
          message: `您提到持有 ${symbol}，但数据库中没有该持仓记录`,
          possible_reasons: [
            "已卖出但记忆未更新",
            "与其他账户混淆",
            "计划买入但未实际执行"
          ]
        });
      }
    }
    
    // 检查：数据库有持仓，但用户未提及
    for (const holding of dbState.holdings) {
      if (!userClaim.claimed_holdings?.includes(holding.symbol)) {
        issues.push({
          type: "holding_not_mentioned",
          symbol: holding.symbol,
          message: `数据库显示您持有 ${holding.symbol}，但您未提及`,
          holding_info: {
            shares: holding.shares_total,
            cost: holding.avg_cost,
            days_held: holding.days_held
          }
        });
      }
    }
    
    return issues;
  }
}
```

### C. 强制查询中间件（Mandatory Query Middleware）

**位置**: `agent-ts/src/core/middleware/mandatory-query.ts`

```typescript
/**
 * 拦截涉及持仓的对话，强制先查询数据库
 */
export class MandatoryQueryMiddleware {
  async process(message: UserMessage): Promise<ProcessedMessage> {
    const classified = classifyInput(message.content);
    
    // 如果消息涉及持仓状态
    if (this.involvesPortfolioState(classified)) {
      // 强制查询数据库
      const dbSnapshot = await this.fetchPortfolioSnapshot(message.account);
      
      // 如果用户提供了状态声明，验证
      if (classified.type === InputType.STATE_CLAIM) {
        const verification = await this.verifier.verifyOrReject(classified);
        
        if (!verification.verified) {
          // 生成纠正消息
          return {
            ...message,
            preprocessed: true,
            db_snapshot: dbSnapshot,
            verification_result: verification,
            agent_should_respond_with: this.buildCorrectionMessage(verification)
          };
        }
      }
      
      // 即使验证通过，也注入数据库快照
      return {
        ...message,
        preprocessed: true,
        db_snapshot: dbSnapshot,
        metadata: {
          data_source: "database",
          verified_at: new Date().toISOString()
        }
      };
    }
    
    return { ...message, preprocessed: false };
  }
  
  private buildCorrectionMessage(verification: VerificationResult): string {
    const { discrepancies, db_state } = verification;
    
    let message = "⚠️ 数据核对发现差异\n\n";
    
    for (const issue of discrepancies) {
      if (issue.type === "holding_not_found") {
        message += `❌ 您提到持有 ${issue.symbol}，但数据库中无此持仓\n`;
        message += `   可能原因：${issue.possible_reasons.join(" / ")}\n\n`;
      } else if (issue.type === "holding_not_mentioned") {
        message += `➕ 数据库显示您持有 ${issue.symbol}（${issue.holding_info.shares}股），但您未提及\n\n`;
      }
    }
    
    message += "📊 数据库实际状态：\n";
    message += this.formatHoldings(db_state.holdings);
    message += "\n💡 后续分析将基于数据库实际数据，而非您提供的信息。";
    
    return message;
  }
}
```

---

## 三、用户交互模式重构

### 旧模式（容易出错）

```
用户："我持有格力600股，帮我分析止损点"
Agent："好的，格力电器当前价格40.34，您的成本是..."
      ↑ 盲目信任用户输入
```

### 新模式（主动验证）

```
用户："我持有格力600股，帮我分析止损点"
      ↓
Agent: [自动触发 portfolio_status 查询]
      ↓
Agent："⚠️ 数据核对发现差异

❌ 您提到持有格力电器 000651，但数据库中无此持仓
   可能原因：已卖出但记忆未更新 / 与其他账户混淆

➕ 数据库显示您持有歌尔股份 002241（1300股），但您未提及

📊 数据库实际状态：
├─ 歌尔股份 002241
│  ├─ 数量：1,300股
│  ├─ 成本：¥22.52
│  └─ 现价：¥23.06（+2.38%）
└─ 现金：¥75,051.71

💡 要分析止损点的话，我可以：
1. 分析歌尔股份的止损策略（实际持仓）
2. 查看格力电器的历史交易记录（已卖出）

请问您想分析哪个？"
```

---

## 四、技术实现路径

### Phase 1: 拦截与验证（本周）

**目标**：阻止错误数据进入决策流程

```typescript
// 在 agent loop 入口注入中间件
const middleware = [
  new InputClassifierMiddleware(),
  new MandatoryQueryMiddleware(),
  new StateVerificationMiddleware()
];

async function processUserInput(message: string) {
  let processed = { content: message };
  
  for (const mw of middleware) {
    processed = await mw.process(processed);
    
    // 如果验证失败，立即返回纠正消息
    if (processed.verification_failed) {
      return {
        type: "verification_failure",
        response: processed.correction_message
      };
    }
  }
  
  // 验证通过，进入正常处理
  return processWithVerifiedData(processed);
}
```

### Phase 2: 主动推送（下周）

**目标**：用户不需要主动问，系统自动推送准确信息

```typescript
// 每日早盘自动推送
scheduledTasks.register({
  name: "morning_brief_push",
  cron: "0 9 * * 1-5",
  async execute() {
    const snapshot = await portfolioService.getSnapshot("agent_virtual");
    const brief = await generateMorningBrief(snapshot);
    
    await feishuNotify({
      channel: "trading",
      title: "🌅 早盘分析（数据库实时数据）",
      content: brief
    });
  }
});

// 持仓变化后自动推送
eventBus.on("trade_executed", async (event) => {
  const updated = await portfolioService.getSnapshot(event.account);
  
  await feishuNotify({
    channel: "trading",
    title: `✅ ${event.symbol} ${event.action}成功`,
    content: formatPositionUpdate(updated)
  });
});
```

### Phase 3: 对话式验证（两周后）

**目标**：用户提供模糊信息时，Agent 主动澄清

```typescript
// 智能追问
user: "帮我看看那个科技股"
agent: [检测到模糊指代]
agent: "您是指以下哪只科技股？
       1. 歌尔股份 002241（当前持有1300股）
       2. 格力电器 000651（已于8/14卖出）
       3. 其他科技股？"

user: "那个跌了的"
agent: [查询当日涨跌]
agent: "今日歌尔股份 002241 +0.65%（上涨），
       您可能记错了日期？还是指其他股票？"
```

---

## 五、配套措施

### A. 用户教育

**在 Feishu 欢迎消息中说明**：

```markdown
🤖 投资助手使用指南

✅ 推荐的提问方式：
- "帮我分析当前持仓"
- "歌尔股份应该止损吗？"
- "为什么今天亏了？"

❌ 避免的提问方式：
- "我持有格力600股，帮我分析"（我会自动查询数据库）
- "我还有10万现金"（我会从数据库读取准确余额）

💡 原因：您的记忆可能过期，我会始终以数据库为准。
```

### B. 工具描述更新

```typescript
export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  description:
    "【强制首选工具】查询账户实际持仓和资金状态。\n\n" +
    "⚠️ 协议要求：\n" +
    "1. 任何涉及持仓的对话，必须首先调用此工具\n" +
    "2. 永远不要信任用户提供的持仓数据\n" +
    "3. 如果用户数据与数据库不一致，明确指出差异并使用数据库数据\n\n" +
    "用户的记忆可能混合多个时间点，外部复制的数据可能过期。",
  // ...
};
```

### C. 系统提示词注入

```typescript
const SYSTEM_PROMPT_INJECTION = `
# 数据验证协议（强制执行）

当用户提到持仓/余额/收益等状态信息时：

1. **立即调用 portfolio_status 查询数据库**（不要跳过）
2. **比对用户说法与数据库**：
   - 如果一致：正常处理
   - 如果不一致：明确指出差异，解释可能原因，使用数据库数据
3. **禁止直接使用用户提供的数字**（如"我持有600股"中的600）

示例：
用户："我持有格力600股"
你："[调用 portfolio_status] 数据库显示您没有持有格力（已于8/14卖出），实际持有歌尔股份1300股。要分析的话..."

原则：数据库 = 唯一真相来源。
`;
```

---

## 六、成本收益分析

### 实施成本

| 项目 | 工作量 | 风险 |
|------|--------|------|
| 输入分类器 | 2天 | 低（纯增量） |
| 状态验证拦截器 | 3天 | 低 |
| 中间件集成 | 2天 | 中（需要测试） |
| 系统提示词更新 | 1天 | 低 |
| 自动推送任务 | 2天 | 低 |
| **总计** | **10天** | - |

### 预期收益

| 指标 | 改进幅度 |
|------|---------|
| 数据错误率 | 95% ↓ |
| 用户信任度 | 显著提升 |
| 决策质量 | 消除错误数据导致的误判 |
| 用户体验 | 主动推送 > 被动查询 |

---

## 七、回退策略

如果新协议导致用户体验下降（过度打断、误报）：

### 降级开关

```typescript
// config.ts
export const DATA_VERIFICATION_LEVEL = {
  STRICT: "strict",     // 任何差异都拒绝
  MODERATE: "moderate", // 重大差异拒绝，小差异警告
  LENIENT: "lenient",   // 仅记录差异，不拦截
  OFF: "off"            // 关闭验证（回退到旧模式）
};

let currentLevel = DATA_VERIFICATION_LEVEL.STRICT;

// 可通过命令动态调整
agent.on("command", (cmd) => {
  if (cmd === "/verification-level moderate") {
    currentLevel = DATA_VERIFICATION_LEVEL.MODERATE;
  }
});
```

### 白名单机制

```typescript
// 对于高可信用户（如开发者自己），可设置白名单
const TRUSTED_USERS = ["user_id_1"];

if (TRUSTED_USERS.includes(message.user_id)) {
  // 跳过验证，直接信任
  return processWithoutVerification(message);
}
```

---

## 八、监控指标

### 关键指标

1. **拦截率**：`rejected_inputs / total_inputs`
   - 目标：初期 < 10%，稳定后 < 2%
   
2. **准确率**：`correct_rejections / total_rejections`
   - 目标：> 95%（避免误报）

3. **用户满意度**：通过反馈收集
   - 目标：维持或提升

### 监控实现

```typescript
class VerificationMetrics {
  track(event: VerificationEvent) {
    metrics.increment("verification.total");
    
    if (event.result === "rejected") {
      metrics.increment("verification.rejected");
      metrics.gauge("verification.rejection_rate", this.getRejectionRate());
    }
    
    if (event.user_feedback) {
      if (event.user_feedback === "helpful") {
        metrics.increment("verification.helpful");
      } else {
        metrics.increment("verification.false_positive");
      }
    }
  }
}
```

---

## 九、实施时间表

### Week 1: 核心拦截（P0）

- [x] 输入分类器
- [x] 状态验证拦截器
- [x] 系统提示词注入
- [x] 单元测试

### Week 2: 集成与测试（P0）

- [ ] 中间件集成到 agent loop
- [ ] E2E 测试（模拟错误输入场景）
- [ ] 灰度发布（先用于开发者自己）

### Week 3: 主动推送（P1）

- [ ] 早盘自动分析任务
- [ ] 交易后自动推送
- [ ] 用户教育文档

### Week 4: 优化与监控（P1）

- [ ] 降级开关实现
- [ ] 监控指标上报
- [ ] 根据反馈调优

---

## 十、预期效果

### 短期（1周）
- ✅ 阻止所有基于错误数据的决策
- ✅ 用户立即感知到"Agent 会纠正我的错误"

### 中期（1月）
- ✅ 用户逐渐改变交互习惯（不再手动提供状态数据）
- ✅ 零数据不一致事故

### 长期（3月+）
- ✅ 形成"Agent 是可信数据源"的心智模型
- ✅ 系统可扩展到多用户（每个用户都得到准确的个人数据）

---

**设计者**: Claude (Kiro)  
**审核**: 待用户确认  
**状态**: 设计完成，待实施
