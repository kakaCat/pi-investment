# Evolution System 技术文档

> 生成时间: 2026-05-15  
> 更新时间: 2026-05-15  
> 用途: 系统架构和实现状态文档

---

## 1. 系统架构

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Evolution Service                         │
│                   (evolution-service.ts)                     │
│                      主协调器                                 │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│  Comparator │  │ Attributor  │
│  (减法器)    │  │  (归因器)    │
│  计算差距    │  │  分析原因    │
└─────────────┘  └─────────────┘
       │               │
       └───────┬───────┘
               ▼
       ┌─────────────┐
       │ Compensator │
       │  (补偿器)    │
       │  生成建议    │
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │  Executor   │
       │  (执行器)    │
       │  应用变更    │
       └──────┬──────┘
              │
       ┌──────┴──────┬──────────┬──────────┐
       ▼             ▼          ▼          ▼
┌────────────┐ ┌──────────┐ ┌──────┐ ┌──────┐
│Code        │ │Sandbox   │ │Branch│ │Session│
│Generator   │ │Validator │ │Manager│ │Analyzer│
└────────────┘ └──────────┘ └──────┘ └──────┘
```

### 1.2 数据流

```
输入数据源
├── portfolio.json (持仓)
├── trades.json (交易记录)
├── reviews/*.md (复盘报告)
└── sessions/*.jsonl (Session 日志)
         │
         ▼
    数据处理层
    ├── 过滤交易窗口
    ├── 计算已实现收益
    ├── 分析 Session 日志
    └── 提取决策质量
         │
         ▼
    分析层
    ├── 计算性能差距
    ├── 归因分析
    ├── 工具效能评估
    └── 模式识别
         │
         ▼
    决策层
    ├── 确定优化策略
    ├── 生成优化建议
    └── 参考历史经验
         │
         ▼
    执行层
    ├── 生成代码
    ├── 沙箱验证
    ├── Git 分支管理
    └── 自动合并
         │
         ▼
    输出
    ├── evolution-{date}.md (进化报告)
    ├── execution-{date}.json (执行结果)
    ├── evolution-history.json (历史记录)
    └── experience-summary.json (经验总结)
```

---

## 2. 核心模块详解

### 2.1 Evolution Service (主入口)

**文件**: `src/services/intelligence/evolution-service.ts`

**职责**: 协调整个进化流程

**关键流程**:
1. 加载配置和数据（交易、持仓、复盘）
2. 计算已实现收益和胜率
3. 评估上次进化效果
4. 执行 Session 分析计算工具效能
5. 调用补偿器生成优化建议
6. 执行优化建议
7. 保存进化历史和经验总结
8. 更新版本历史

**配置参数**:
```typescript
{
  targetReturn: 10,              // 目标收益率 (%)
  tradeWindowDays: 90,           // 交易窗口 (天)
  reviewWindowCount: 10,         // 复盘报告数量
  evolutionWindowRecent: 3,      // 进化历史（决策参考）
  evolutionWindowLearning: 100   // 进化历史（经验学习）
}
```

**关键算法**:
- **FIFO 配对算法**: 计算已实现盈亏，按先买后卖配对
- **决策质量评估**: 从复盘报告提取止损建议频率

---

### 2.2 Session Analyzer (Session 分析器)

**文件**: `src/services/intelligence/session-analyzer.ts`

**职责**: 解析 Session 日志，计算工具效能

**核心功能**:
1. 解析 `.pi-invest/sessions/` 下的日志文件
2. 提取工具调用记录和决策链路
3. 关联工具调用与交易结果
4. 计算每个工具的 ROI、胜率、Token 消耗

**工具效能指标**:
```typescript
{
  tool_name: string,
  call_count: number,           // 调用次数
  decisions_after_call: number, // 调用后产生决策的次数
  win_rate: number,             // 胜率
  avg_return: number,           // 平均收益
  avg_tokens: number,           // 平均 Token 消耗
  cost_per_call: number,        // 每次调用成本
  roi: number,                  // ROI = avg_return / cost_per_call
  rating: 1-5                   // 评级（基于 ROI）
}
```

**评级规则**:
- ROI ≥ 50 → 5 星
- ROI ≥ 20 → 4 星
- ROI ≥ 5 → 3 星
- ROI ≥ 0 → 2 星
- ROI < 0 → 1 星

---

### 2.3 Compensator (补偿器)

**文件**: `src/services/intelligence/evolution-compensator.ts`

**职责**: 根据性能差距生成优化建议

**策略级别**:
- `minor`: gap < 3% → 微调参数
- `moderate`: 3% ≤ gap < 10% → 调整工具 + 更新经验
- `major`: gap ≥ 10% → 全面优化（新增工具 + 修改代码）

**建议类型**:
1. `add_tool`: 生成新工具（能力缺失）
2. `remove_tool`: 移除低效工具
3. `update_experience`: 更新经验库
4. `update_prompt`: 修改提示词
5. `update_code`: 修改代码
6. `adjust_parameter`: 调整参数

**增强特性**:
- 参考最近 N 次进化历史，避免重复建议
- 参考经验总结，优先推荐高成功率的工具类型

---

### 2.4 Code Generator (代码生成器)

**文件**: `src/services/intelligence/code-generator.ts`

**职责**: 使用 Agent 自身能力生成工具代码

**生成流程**:
1. 读取现有工具作为参考示例
2. 构造详细的生成提示词（包含规格、要求、格式）
3. 调用 Agent Session 生成代码
4. 提取代码块（工具实现 + 单元测试）
5. 返回生成结果

**代码要求**:
- 符合 `ToolDefinition` 接口
- 使用 TypeBox 定义参数 schema
- 包含完整的错误处理
- 生成对应的 Jest 测试

---

### 2.5 Sandbox Validator (沙箱验证器)

**文件**: `src/services/intelligence/sandbox-validator.ts`

**职责**: 三级验证生成的代码

**验证级别**:
1. **编译验证**: TypeScript 类型检查 (`tsc --noEmit`)
2. **单元测试**: Jest 测试执行
3. **集成测试**: 动态加载工具，验证结构

**验证结果**:
```typescript
{
  passed: boolean,
  level: 'compile' | 'unit_test' | 'integration_test',
  errors: string[],
  warnings: string[],
  duration: number
}
```

**失败处理**: 任一级别失败则终止后续验证，回滚变更

---

### 2.6 Evolution Executor (执行器)

**文件**: `src/services/intelligence/evolution-executor.ts`

**职责**: 自动应用优化建议

**执行流程**:
1. 遍历所有建议
2. 根据类型分发到对应执行器
3. 记录执行日志
4. 保存回滚数据
5. 生成执行报告

**自动执行的类型**:
- ✅ `update_experience`: 直接添加到经验库
- ✅ `add_tool`: 生成代码 → 验证 → 注册 → 提交 → 合并
- ✅ `remove_tool`: 从工具注册表移除
- ✅ `adjust_parameter`: 更新运行时配置
- ✅ `update_prompt`: 修改提示词文件
- ⚠️ `update_code`: 生成修改计划（需人工确认）

**Git 分支管理**:
- 创建进化分支 `evolution/{date}`
- 提交变更到分支
- 自动合并到 `main`
- 失败时回滚到原分支

---

### 2.7 Experience Query (经验查询)

**文件**: `src/services/intelligence/experience-query.ts`

**职责**: 让 Agent 在决策时查询历史经验

**查询流程**:
1. 文本相似度匹配（Jaccard 相似度）
2. 条件匹配过滤
3. 置信度过滤
4. 股票代码过滤（可选）
5. 综合排序（相似度 40% + 置信度 60%）

**经验结构**:
```typescript
{
  scenario: string,           // 场景描述
  pattern: {
    conditions: string[],     // 触发条件
    action: 'buy'|'sell'|'hold'
  },
  outcomes: {
    total_cases: number,      // 总案例数
    win_rate: number,         // 胜率
    avg_return: number        // 平均收益
  },
  recommendation: string,     // 建议（aggressive/moderate/cautious/avoid）
  confidence: number          // 置信度
}
```

---

## 3. 调用链路

### 3.1 定时触发（Cron）

```
CRON.json (weekly_evolution)
    ↓
src/api/index.ts (CronService)
    ↓
getSession({ type: 'cron_evolution' })  ← 新增
    ↓
runWeeklyEvolution()
    ↓
生成报告 + 执行建议
```

**Cron 配置**:
```json
{
  "id": "weekly-evolution",
  "schedule": "0 20 * * 0",  // 每周日 20:00
  "payload": { "kind": "weekly_evolution" }
}
```

---

### 3.2 手动触发（CLI）

```bash
npm run evolution                    # 默认配置
npm run evolution -- --days 30       # 最近 30 天
npm run evolution -- --target 15     # 目标 15%
npm run evolution -- --view          # 查看最近报告
```

**CLI 入口**: `src/scripts/evolution-cli.ts`

---

### 3.3 工具添加完整流程

```
建议生成 (Compensator)
    ↓
创建分支 (evolution/{date})
    ↓
生成代码 (Code Generator)
    ├── 读取示例工具
    ├── 构造提示词
    └── 调用 Agent Session
    ↓
写入文件 (src/infrastructure/tools/)
    ↓
沙箱验证 (Sandbox Validator)
    ├── 编译验证
    ├── 单元测试
    └── 集成测试
    ↓
注册工具 (index.ts)
    ├── 添加 import
    └── 添加到 allCustomTools
    ↓
提交变更 (Git commit)
    ↓
合并到 main (Git merge)
    ↓
记录执行日志
```

---

## 4. 代码质量评估

### 4.1 优点 ✅

1. **模块化设计**: 职责清晰，每个模块独立可测试
2. **完整的验证机制**: 三级验证确保代码质量
3. **Git 分支管理**: 安全的变更流程，支持回滚
4. **历史学习机制**: 评估上次进化效果，避免重复错误
5. **经验总结系统**: 从历史中提取模式和反模式
6. **配置灵活**: 支持多种预设和自定义参数
7. **Session Context 机制**: 根据场景切换 prompt
8. **测试覆盖**: 4 个核心模块有单元测试（comparator, evolution-reporter, experience-manager, session-analyzer）
9. **完整的评分系统**: 对每次进化和每个建议进行量化评估（0-100 分）
10. **经验库版本管理**: 支持增量更新、自动备份、冲突解决

---

### 4.2 潜在改进点 ⚠️

#### 代码质量优化（P1）

1. **Session 日志格式统一性**
   - 位置: `session-analyzer.ts`
   - 建议: 添加日志版本号，支持增量分析

2. **工具注册逻辑健壮性**
   - 位置: `evolution-executor.ts:357-391`
   - 问题: 使用字符串匹配，格式变化会失败
   - 建议: 使用 TypeScript Compiler API 进行 AST 解析

3. **错误处理增强**
   - 位置: `evolution-service.ts` 多处
   - 建议: 为所有异步操作添加 try-catch，优雅降级

4. **代码生成鲁棒性**
   - 位置: `code-generator.ts:23-41`
   - 建议: 添加多轮对话修正机制，支持代码生成模板

5. **沙箱验证优化**
   - 位置: `sandbox-validator.ts`
   - 建议: 添加超时机制、并行验证、结果缓存

---

## 5. 优化建议

### 5.1 高优先级（P1 - 重要改进）

#### 1. 增强错误处理

```typescript
// 在所有异步操作外包裹 try-catch
try {
  const result = await riskyOperation();
  // 处理结果
} catch (error) {
  console.error('[模块名] 操作失败:', error);
  // 优雅降级或返回默认值
}
```

---

#### 2. 修复工具注册逻辑

**方案 1**: 使用 AST 解析（推荐）
```typescript
import * as ts from 'typescript';

function addToolToIndex(toolName: string) {
  const sourceFile = ts.createSourceFile(...);
  // 使用 TypeScript Compiler API 修改 AST
}
```

**方案 2**: 使用更健壮的正则
```typescript
const importRegex = /import\s+\{([^}]+)\}\s+from\s+['"]\.\/([^'"]+)['"]/g;
const toolsRegex = /export\s+const\s+allCustomTools\s*=\s*\[([^\]]+)\]/s;
```

---

### 5.2 中优先级（P2 - 重要改进）

#### 3. 优化 Session 分析

- 统一 Session 日志格式（添加版本号）
- 实现增量分析（只分析新日志）
- 添加日志压缩和归档

#### 4. 增强代码生成

- 添加代码生成模板
- 支持多轮对话修正
- 添加代码质量检查（ESLint）

#### 5. 改进沙箱验证

- 添加超时机制（防止卡死）
- 支持并行验证（加速）
- 缓存验证结果（避免重复）

#### 6. 优化 Git 分支管理

- 添加冲突检测
- 支持手动合并模式
- 保留分支历史（可选）

---

### 5.3 低优先级（P3 - 锦上添花）

#### 7. 性能优化

- 缓存交易数据计算结果
- 并行执行独立的建议
- 使用流式处理大文件

#### 8. 可观测性增强

- 添加详细的性能指标
- 实现进度条显示
- 生成可视化报告

#### 9. 测试覆盖扩展

- 为剩余模块添加单元测试（当前 4/10 已覆盖）
- 添加集成测试
- 添加端到端测试

---

### 5.4 架构改进（长期）

#### 11. 依赖注入

```typescript
class EvolutionService {
  constructor(
    private compensator: Compensator,
    private executor: Executor,
    private analyzer: SessionAnalyzer
  ) {}
}
```

#### 12. 事件驱动架构

```typescript
eventBus.on('evolution:started', () => {...});
eventBus.on('suggestion:generated', () => {...});
eventBus.on('code:generated', () => {...});
```

#### 13. 配置管理

- 支持环境变量覆盖
- 添加配置验证（JSON Schema）
- 支持热重载

#### 14. 数据持久化

- 使用数据库替代 JSON 文件（SQLite/PostgreSQL）
- 添加数据迁移机制
- 实现数据备份

---

## 6. 关键文件清单

### 6.1 核心模块 ✅

| 文件 | 状态 | 测试 | 说明 |
|-----|------|------|------|
| `evolution-service.ts` | ✅ | - | 主服务，协调整个流程（577 行） |
| `evolution-executor.ts` | ✅ | - | 执行器，应用优化建议 |
| `evolution-compensator.ts` | ✅ | - | 补偿器，生成优化建议 |
| `code-generator.ts` | ✅ | - | 代码生成器 |
| `sandbox-validator.ts` | ✅ | - | 沙箱验证器 |
| `session-analyzer.ts` | ✅ | ✅ | Session 分析器 |
| `experience-query.ts` | ✅ | - | 经验查询服务 |
| `evolution-cli.ts` | ✅ | - | CLI 入口 |
| `evolution.ts` (types) | ✅ | - | 类型定义 |
| `agent-loop.ts` | ✅ | - | Session Context 机制 |

---

### 6.2 支撑模块 ✅

| 文件 | 状态 | 测试 | 说明 |
|-----|------|------|------|
| `comparator.ts` | ✅ | ✅ | 减法器，计算差距和归因（184 行） |
| `evolution-reporter.ts` | ✅ | ✅ | 报告生成器，Markdown 格式化（272 行） |
| `experience-manager.ts` | ✅ | ✅ | 经验库管理，版本控制+备份（420 行） |
| `evolution-history.ts` | ✅ | - | 历史记录管理，评分系统（355 行） |
| `experience-learner.ts` | ✅ | - | 经验学习器，模式提取（260+ 行） |
| `evolution-branch-manager.ts` | ✅ | - | Git 分支管理器（220 行） |

---

## 7. 总结

### 7.1 当前状态

Evolution 系统是一个**完整实现的自我进化框架**，设计理念先进，包含完整的分析-决策-执行闭环。

**完成度**: 约 **95%**
- ✅ 核心架构已完成（10 个核心模块）
- ✅ 支撑模块已完成（6 个支撑模块）
- ✅ Session Context 机制已完成
- ✅ 评分和学习系统已完成
- ✅ 部分单元测试已覆盖（4/16 模块）
- ⚠️ 工具注册逻辑需要增强（使用 AST）
- ⚠️ 测试覆盖需要扩展

---

### 7.2 主要亮点

1. **完整的代码生成和验证流程**（三级验证：编译 → 单元测试 → 集成测试）
2. **基于历史的学习机制**（评分系统 0-100，自动评估每次进化效果）
3. **安全的 Git 分支管理**（独立分支 + 自动合并 + 回滚支持）
4. **灵活的配置系统**（5 个可调参数，支持预设和自定义）
5. **Session Context 机制**（根据场景切换 prompt）
6. **经验库版本管理**（增量更新、自动备份、冲突解决）
7. **工具效能分析**（ROI、胜率、Token 消耗、5 星评级）
8. **模式识别系统**（成功模式、反模式、经验规律提取）

---

### 7.3 下一步行动

#### 高优先级（P1 - 本周）
1. 增强错误处理（所有异步操作添加 try-catch）
2. 修复工具注册逻辑（使用 TypeScript Compiler API）
3. 端到端测试（验证完整流程）

#### 中优先级（P2 - 本月）
4. 优化 Session 分析（增量分析、日志版本号）
5. 改进沙箱验证（超时、并行、缓存）
6. 扩展测试覆盖（目标：12/16 模块）

#### 低优先级（P3 - 季度）
7. 性能优化（缓存、并行执行）
8. 可观测性增强（性能指标、可视化报告）
9. 架构改进（依赖注入、事件驱动）

---

## 附录

### A. 配置示例

```json
{
  "targetReturn": 10,
  "tradeWindowDays": 90,
  "reviewWindowCount": 10,
  "evolutionWindowRecent": 3,
  "evolutionWindowLearning": 100
}
```

### B. 使用示例

```bash
# 查看最近报告
npm run evolution -- --view

# 分析最近 30 天
npm run evolution -- --days 30

# 设置目标 15%
npm run evolution -- --target 15

# 分析全部交易
npm run evolution -- --all
```

### C. 相关文档

- [进化配置指南](./evolution-config-guide.md)
- [完全自动化配置](./evolution-automation.md)
- [P0 功能完成报告](./p0-features-completion.md)
- [改进总结](./evolution-improvement-summary.md)

---

**文档维护**: 请在重大变更后更新此文档
