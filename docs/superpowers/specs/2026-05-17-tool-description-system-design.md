# 工具描述系统优化设计

**日期**: 2026-05-17  
**状态**: 待审核  
**目标**: 建立代码级（工具自描述）+ 策略级（执行流程）的分层工具描述系统

---

## 1. 背景与问题

### 当前状态

- **TOOLS.md（258行）**: 手工维护的工具使用指南，包含：
  - 输出原则（3段式强制格式）
  - 并行执行原则
  - 执行路径选择（Path A~I）
  - 工具分类速查（35个工具的列表）
  - 数据铁律、公告解析规则

- **工具定义**: 35个工具文件，只有 `name`、`label`、`description`，没有使用框架的 `promptSnippet` 和 `promptGuidelines`

- **工具加载**: 动态加载机制
  ```typescript
  allCustomTools = [planTool, clarifyTool, ...investTools, ...]  // 内置工具（静态）
  pluginTools = await loadPlugins(paths.pluginDirs)              // 插件工具（动态）
  getEffectiveTools() = [...allCustomTools, ...pluginTools]      // 最终工具列表
  ```

### 存在的问题

1. **冗余**: TOOLS.md 中的工具列表与代码中的工具定义重复，容易不同步
2. **维护成本高**: 新增工具需要同时修改代码和 TOOLS.md
3. **信息分散**: 工具的使用场景在 TOOLS.md，功能描述在代码中，难以统一管理
4. **未利用框架能力**: 框架提供的 `promptSnippet` 和 `promptGuidelines` 机制未使用

---

## 2. 设计目标

### 核心原则

1. **代码自描述**: 工具定义包含完整的使用信息，无需外部文档
2. **动态生成**: 系统提示词中的工具列表从实际加载的工具动态生成
3. **分层清晰**: 策略层（何时用）、工具层（有什么）、细节层（怎么用）职责分明
4. **AI 易维护**: 每个字段职责单一，未来 AI 修改时不会混淆
5. **顺序可控**: 内置工具顺序固定（高频在前），插件工具追加在后

### 系统提示词最终结构

```markdown
## Tools

### 执行策略（何时用什么工具）
（来自 TOOLS.md：输出原则、并行执行、Path A~I、数据铁律）

### 工具列表（按使用频率排序，优先考虑靠前的工具）

以下是所有可用工具，按使用频率从高到低排列。选择工具时，优先考虑列表前面的工具。

**说明**：
- 内置工具（前 89 个）：按固定顺序排列，高频工具在前
- 插件工具（如有）：动态加载，追加在内置工具之后
- 工具总数：92 个

- plan_task: 规划任务时使用，将复杂任务拆解为可执行步骤
- clarify: 需要澄清用户意图时使用
- task_create: 创建任务追踪，用于并行执行多个工具
...

### 工具使用细则（复杂工具的特殊注意事项）

以下工具有特殊的使用规则或注意事项，使用前请仔细阅读：

**check_stop_loss_trigger**（止损检查）
- 批量模式（mode=batch）会自动从 portfolio.json 读取所有持仓
- 触发止损时必须立即通知用户，不要自动执行卖出操作
- 止损判断公式：(currentPrice - entryPrice) / entryPrice <= -stopLossPercent
...
```

---

## 3. 工具定义格式规范

### 三个字段的职责

```typescript
export const exampleTool: ToolDefinition = {
  name: "tool_name",           // 工具名称（snake_case）
  label: "工具中文名",          // 可选，用于日志和错误提示
  
  // 1. description: 功能描述（what it does）
  //    - 1-2 句话说明工具的功能
  //    - 会被框架用于生成工具列表
  description: "简短的功能描述，说明这个工具做什么",
  
  // 2. promptSnippet: 场景触发（when to use）
  //    - 1 行，说明什么场景下使用这个工具
  //    - 会出现在系统提示词的工具列表中
  //    - 如果不提供，框架会使用 description
  promptSnippet: "具体场景描述，告诉 LLM 何时调用这个工具",
  
  // 3. promptGuidelines: 使用准则（how to use）
  //    - 可选，只有复杂工具才需要
  //    - 2-5 条使用规则或注意事项
  //    - 会出现在系统提示词的"工具使用细则"部分
  promptGuidelines: [
    "第一条使用规则或注意事项",
    "第二条使用规则或注意事项",
    "特殊情况的处理方式"
  ],
  
  parameters: Type.Object({...})
};
```

### 字段使用原则

**description（必需）**
- 简洁的功能描述，1-2 句话
- 说明"这个工具做什么"
- 例子：
  - ✅ "检查持仓是否触发止损条件，支持单个检查或批量检查所有持仓"
  - ❌ "止损检查工具"（太简略）
  - ❌ "这个工具用于检查用户的持仓是否已经达到了止损的条件..."（太啰嗦）

**promptSnippet（推荐）**
- 场景化描述，1 行
- 说明"什么时候用这个工具"
- 例子：
  - ✅ "持仓亏损达到止损线时，用于判断是否需要卖出"
  - ✅ "分析多只股票时，用于并行执行避免串行等待"
  - ❌ "检查止损"（太简略，没说场景）

**promptGuidelines（可选）**
- 2-5 条使用规则
- 说明"怎么正确使用这个工具"
- 适用场景：
  - 有多种模式或参数组合
  - 有常见错误用法需要提醒
  - 有数据源限制或已知问题
  - 需要与其他工具配合使用

### 需要 promptGuidelines 的工具（15个）

**并行执行相关（3个）**
- `task_execute_async` - 后台异步执行
- `task_create` - 创建任务追踪
- `task_check_background` - 检查后台任务

**止损和风控（2个）**
- `check_stop_loss_trigger` - 止损检查
- `check_pending_orders` - 挂单检查

**交易管理（3个）**
- `manage_orders` - 挂单管理
- `trade_log` - 交易日志管理
- `manage_watchlist` - 关注列表管理

**数据源问题（2个）**
- `get_north_flow` - 北向资金（数据源失效）
- `browser` - 浏览器工具（备选方案）

**量化分析（3个）**
- `analyze_stock_quant` - 量化分析个股
- `get_technical_signals` - 技术指标信号
- `backtest_strategy` - 策略回测

**记忆管理（2个）**
- `memory_write` - 写入记忆
- `memory_search` - 搜索记忆

---

## 4. 系统提示词组装逻辑

### 修改文件

`src/services/intelligence/system-prompt-builder.ts`

### 第3层改进（工具部分）

```typescript
// 第 3 层: 工具使用指南
const toolsMd = bootstrap["TOOLS.md"]?.trim();
const toolsSection = [];

// 3.1 执行策略（来自 TOOLS.md）
if (toolsMd) {
  toolsSection.push("### 执行策略（何时用什么工具）\n\n" + toolsMd);
}

// 3.2 工具列表（动态生成，包含内置 + 插件）
if (customToolsBlock) {
  const toolListHeader = `### 工具列表（按使用频率排序，优先考虑靠前的工具）

以下是所有可用工具，按使用频率从高到低排列。选择工具时，优先考虑列表前面的工具。

**说明**：
- 内置工具（前 ${allCustomTools.length} 个）：按固定顺序排列，高频工具在前
- 插件工具（如有）：动态加载，追加在内置工具之后
- 工具总数：${tools.length} 个

`;
  toolsSection.push(toolListHeader + customToolsBlock);
}

// 3.3 工具使用细则（从 promptGuidelines 动态生成）
const guidelines = buildToolGuidelines(tools); // 新增函数
if (guidelines) {
  const guidelinesHeader = `### 工具使用细则（复杂工具的特殊注意事项）

以下工具有特殊的使用规则或注意事项，使用前请仔细阅读：

`;
  toolsSection.push(guidelinesHeader + guidelines);
}

sections.push(`## Tools\n\n${toolsSection.join('\n\n')}`);
```

### 新增函数：buildToolGuidelines

```typescript
/**
 * 从工具的 promptGuidelines 构建使用细则文本
 * 只包含有 promptGuidelines 的工具
 */
function buildToolGuidelines(tools: Array<{
  name: string;
  label?: string;
  promptGuidelines?: string[];
}>): string {
  const lines: string[] = [];
  
  for (const tool of tools) {
    if (!tool.promptGuidelines || tool.promptGuidelines.length === 0) {
      continue;
    }
    
    const label = tool.label || tool.name;
    lines.push(`**${tool.name}**（${label}）`);
    
    for (const guideline of tool.promptGuidelines) {
      lines.push(`- ${guideline}`);
    }
    
    lines.push(''); // 空行分隔
  }
  
  return lines.join('\n');
}
```

---

## 5. 工具顺序调整机制

### 修改文件

`src/infrastructure/tools/index.ts`

### 注释改进

```typescript
/**
 * 所有自定义工具列表 — agent-loop 直接使用此数组
 *
 * ⚠️ 顺序规则（LLM 对靠前工具权重更高）：
 * 
 * 【第1组：工作流核心】— 每个任务都可能用到
 *   plan_task, clarify, task_create, task_update, task_execute_async, task_list, reflect
 * 
 * 【第2组：投资核心】— 高频业务工具
 *   investTools（市场/个股/财务/估值/技术面）
 *   stockDBTools（数据库查询）
 *   queryExperience, analyze_sector_rotation, check_stop_loss_trigger
 *   manageOrders, tradeLog, manageWatchlist
 * 
 * 【第3组：量化决策】— 新架构量化工具
 *   quantDecisionTools, quantAnalysisTools, quantStrategyTools
 * 
 * 【第4组：辅助工具】— 中低频
 *   notificationTools, monitorTools, evolutionRun, restartAgent
 *   memoryWrite, memorySearch
 * 
 * 【第5组：低频专用】— 按需使用
 *   taskGet, taskCheckBackground, compact, browser, read
 * 
 * 【插件工具】— 动态加载，自动追加在内置工具之后
 *   由 loadPlugins() 加载，顺序由插件注册顺序决定
 * 
 * 🔧 调整内置工具顺序：直接移动工具在数组中的位置
 * 🔌 调整插件工具顺序：修改插件目录的加载顺序或插件内部的工具注册顺序
 * 📊 验证最终顺序：查看日志中的 "工具总数：XX 个（内置 XX + 插件 XX）"
 */
export const allCustomTools = [
  // 第1组：工作流核心
  planTool,
  clarifyTool,
  taskCreateTool,
  taskUpdateTool,
  taskExecuteAsyncTool,
  taskListTool,
  reflectTool,
  
  // 第2组：投资核心
  ...investTools.map(wrapInvestToolWithSkillGuard),
  ...stockDBTools,
  queryExperienceTool,
  analyze_sector_rotationTool,
  check_stop_loss_triggerTool,
  checkPendingOrdersTool,
  manageOrdersTool,
  tradeLogTool,
  manageWatchlistTool,
  testMarketSentimentTool,
  
  // 第3组：量化决策
  ...quantDecisionTools,
  ...quantAnalysisTools,
  ...quantStrategyTools,
  
  // 第4组：辅助工具
  ...notificationTools,
  ...monitorTools,
  evolutionRunTool,
  restartAgentTool,
  memoryWriteTool,
  memorySearchTool,
  
  // 第5组：低频专用
  taskGetTool,
  taskCheckBackgroundTool,
  compactTool,
  browserTool,
  readTool,
];
```

---

## 6. TOOLS.md 精简

### 修改文件

`.pi-invest/bootstrap/TOOLS.md`

### 删除内容

- **工具分类速查**（第186-259行）：已由框架自动生成，删除
  - 行情数据
  - 财务分析
  - 估值与技术
  - 港股专用
  - 选股筛选
  - 聪明钱信号
  - 市场情绪
  - 宏观经济
  - 公告与新闻
  - 持仓管理
  - 历史经验查询

### 保留内容

- **输出原则**（第3-38行）：3段式强制格式
- **并行执行原则**（第40-76行）：并行机制、错误方式、正确方式
- **执行前检查顺序**（第79-90行）：先检查 Skills，再选执行路径
- **执行路径选择**（第92-182行）：Path A~I
- **数据铁律**（第244-250行）
- **公告解析规则**（第252-259行）

### 精简后的 TOOLS.md 结构

```markdown
# 工具使用指南

## 🎯 输出原则（最高优先级）
（保留）

## ⚡ 并行执行原则
（保留）

## 执行前检查顺序
（保留）

## 执行路径选择
（保留 Path A~I）

## 数据铁律
（保留）

## 公告解析规则
（保留）
```

---

## 7. 实施步骤

### Phase 1: 基础设施（1-2小时）

1. **修改 system-prompt-builder.ts**
   - 添加 `buildToolGuidelines()` 函数
   - 修改第3层工具部分的组装逻辑
   - 添加工具数量统计（内置 + 插件）

2. **修改 tools/index.ts**
   - 更新注释，明确分组和顺序规则
   - 添加验证脚本提示

3. **精简 TOOLS.md**
   - 删除工具分类速查部分（186-259行）
   - 保留执行策略部分

### Phase 2: 工具定义更新（3-4小时）

按优先级分批更新工具定义：

**批次1：高频工具（5个）**
- `task_execute_async`
- `task_create`
- `check_stop_loss_trigger`
- `manage_orders`
- `trade_log`

**批次2：数据源问题（2个）**
- `get_north_flow`
- `browser`

**批次3：量化和记忆（5个）**
- `analyze_stock_quant`
- `get_technical_signals`
- `backtest_strategy`
- `memory_write`
- `memory_search`

**批次4：其他复杂工具（3个）**
- `manage_watchlist`
- `check_pending_orders`
- `task_check_background`

### Phase 3: 验证和测试（1小时）

1. **启动 agent，检查系统提示词**
   - 查看日志中的系统提示词输出
   - 确认工具列表正确生成
   - 确认工具使用细则正确生成

2. **测试工具调用**
   - 测试高频工具（task_execute_async、check_stop_loss_trigger）
   - 测试数据源失效工具（get_north_flow → browser 备选）
   - 测试量化工具（analyze_stock_quant）

3. **验证 LLM 理解**
   - 询问"有哪些工具可用"
   - 询问"如何使用 task_execute_async"
   - 询问"北向资金数据失效怎么办"

---

## 8. 示例：工具定义改造

### 改造前（check_stop_loss_trigger）

```typescript
export const check_stop_loss_triggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "check_stop_loss_trigger",
  description: "检查持仓是否触发止损条件。可以检查单个持仓或批量检查所有持仓。",
  parameters: Type.Object({...})
};
```

### 改造后

```typescript
export const check_stop_loss_triggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "止损检查",
  
  description: "检查持仓是否触发止损条件，支持单个检查或批量检查所有持仓",
  
  promptSnippet: "持仓亏损达到止损线时，用于判断是否需要卖出",
  
  promptGuidelines: [
    "批量模式（mode=batch）会自动从 portfolio.json 读取所有持仓",
    "触发止损时必须立即通知用户，不要自动执行卖出操作",
    "止损判断公式：(currentPrice - entryPrice) / entryPrice <= -stopLossPercent"
  ],
  
  parameters: Type.Object({...})
};
```

### 系统提示词效果

**工具列表部分**：
```
- check_stop_loss_trigger: 持仓亏损达到止损线时，用于判断是否需要卖出
```

**工具使用细则部分**：
```
**check_stop_loss_trigger**（止损检查）
- 批量模式（mode=batch）会自动从 portfolio.json 读取所有持仓
- 触发止损时必须立即通知用户，不要自动执行卖出操作
- 止损判断公式：(currentPrice - entryPrice) / entryPrice <= -stopLossPercent
```

---

## 9. 预期效果

### 对 LLM 的影响

1. **工具发现更容易**：工具列表按频率排序，高频工具优先看到
2. **场景匹配更准确**：promptSnippet 明确说明"何时用"，减少选错工具
3. **使用更规范**：promptGuidelines 提醒常见错误，减少误用
4. **数据失败有备选**：明确说明 browser 工具是数据失败时的备选方案

### 对维护的影响

1. **新增工具更简单**：只需在代码中定义，自动出现在系统提示词
2. **修改工具更安全**：description/promptSnippet/promptGuidelines 职责单一，不会混淆
3. **调整顺序更直观**：直接移动 allCustomTools 数组中的位置
4. **文档自动同步**：工具列表从代码生成，不会出现文档与代码不一致

### 对用户的影响

1. **响应更准确**：LLM 更容易选对工具，减少无效调用
2. **错误更少**：promptGuidelines 提醒常见错误，减少误用
3. **数据失败有提示**：明确告知数据源问题和备选方案

---

## 10. 风险和缓解

### 风险1：系统提示词变长

- **风险**：工具使用细则增加了系统提示词长度
- **缓解**：只有15个复杂工具有 promptGuidelines，每个2-5条，总增加约 500-800 tokens
- **评估**：相比 TOOLS.md 删除的工具分类速查（约 1000 tokens），总体减少约 200-500 tokens

### 风险2：promptGuidelines 维护成本

- **风险**：需要为15个工具编写 promptGuidelines
- **缓解**：分批实施，优先高频工具；promptGuidelines 可以逐步完善
- **评估**：一次性投入约 3-4 小时，后续维护成本低

### 风险3：LLM 可能忽略 promptGuidelines

- **风险**：LLM 可能不阅读"工具使用细则"部分
- **缓解**：在标题中明确说明"使用前请仔细阅读"；关键工具的 promptSnippet 中也提示"详见使用细则"
- **评估**：通过测试验证 LLM 是否遵循 promptGuidelines

### 风险4：插件工具顺序不可控

- **风险**：插件工具追加在内置工具之后，顺序由插件加载顺序决定
- **缓解**：在系统提示词中明确标注"插件工具追加在后"；插件工具通常是低频专用工具
- **评估**：插件工具数量少（通常 < 5 个），顺序影响不大

---

## 11. 后续优化

### 短期（1-2周）

1. **添加工具使用统计**：记录每个工具的调用次数，验证顺序是否合理
2. **优化 promptGuidelines**：根据实际使用情况，补充或精简使用准则
3. **添加工具分组标签**：在工具列表中用 emoji 或标签标注分组（🔧 工作流、📊 投资核心、🧮 量化）

### 中期（1个月）

1. **自动生成 promptSnippet**：基于工具调用日志，用 LLM 自动生成或优化 promptSnippet
2. **工具推荐系统**：基于用户意图，推荐最相关的 3-5 个工具
3. **工具使用教程**：为复杂工具生成交互式教程

### 长期（3个月）

1. **工具能力图谱**：可视化工具之间的依赖关系和组合模式
2. **工具性能监控**：监控工具调用成功率、响应时间、错误率
3. **工具自动优化**：基于使用数据，自动调整工具顺序和 promptGuidelines

---

## 12. 总结

### 核心改进

1. **代码自描述**：工具定义包含完整的使用信息（description + promptSnippet + promptGuidelines）
2. **动态生成**：系统提示词中的工具列表从实际加载的工具动态生成
3. **分层清晰**：策略层（TOOLS.md）、工具层（promptSnippet）、细节层（promptGuidelines）职责分明
4. **顺序可控**：内置工具顺序固定（高频在前），插件工具追加在后

### 实施成本

- **开发时间**：5-7 小时（基础设施 1-2h + 工具定义更新 3-4h + 验证测试 1h）
- **维护成本**：低（新增工具只需在代码中定义，自动出现在系统提示词）
- **风险**：低（分批实施，可逐步完善）

### 预期收益

- **LLM 响应更准确**：工具发现更容易，场景匹配更准确，使用更规范
- **维护更简单**：新增工具更简单，修改工具更安全，文档自动同步
- **用户体验更好**：响应更准确，错误更少，数据失败有提示
