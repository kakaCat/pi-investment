# @pi-investment/learning

自我学习插件：经验追踪、模式挖掘、知识蒸馏、策略优化

## 概述

实现 RFC 003 的核心能力，让 Agent-DH 能够从执行结果中学习并持续改进。

## 工具

### 1. learning_track
手动追踪执行经验（自动追踪已覆盖主要工具）

### 2. learning_analyze
分析经验库，挖掘成功/失败模式

### 3. learning_distill
从复杂推理中提取简单规则

### 4. learning_apply
应用学习结果，生成代码/配置改动

## 特性

- **自动拦截**: 自动追踪关键工具调用（portfolio_trade、strategy_execute 等）
- **奖励计算**: 根据执行结果自动计算奖励信号
- **经验持久化**: 存储到 memory 系统，支持语义检索
- **模式挖掘**: 识别成功/失败模式，生成改进建议
- **知识蒸馏**: 复杂推理 → 简单规则
- **安全应用**: 集成 self_restart 安全验证

## 使用示例

```typescript
// 1. 自动追踪（无需手动调用）
await tools.portfolio_trade({ action: 'BUY', symbol: '600519', quantity: 100 });
// learning 插件自动记录经验

// 2. 分析学习机会
const analysis = await tools.learning_analyze({
  scope: 'recent',
  focus: 'patterns',
  time_range_days: 30
});

// 3. 知识蒸馏
const rules = await tools.learning_distill({
  source: 'successful_trades',
  target_format: 'rules',
  min_confidence: 0.7
});

// 4. 应用改进（先预览）
const preview = await tools.learning_apply({
  improvement_type: 'rule',
  improvement_spec: rules.rules[0],
  dry_run: true
});

// 5. 确认后应用并重启验证
await tools.learning_apply({
  improvement_type: 'rule',
  improvement_spec: rules.rules[0],
  dry_run: false,
  restart_after: true
});
```

## 学习循环

```
执行工具 → 自动追踪 → 计算奖励 → 存入 memory
    ↓
定期分析 → 挖掘模式 → 生成建议
    ↓
知识蒸馏 → 提取规则 → 应用改动
    ↓
self_restart → 验证效果 → 合并/回滚
```

## 配置

```yaml
- id: learning
  name: '@pi-investment/learning'
  config:
    quantsysV2:
      baseURL: http://localhost:5001
    learning:
      minSamplesForPattern: 10
      rewardDecayFactor: 0.95
      distillConfidenceThreshold: 0.7
```

## 依赖

- memory 插件：经验持久化
- lifecycle 插件：安全重启验证
- quantsys-v2：数据支持

## 路线图

- [x] Phase 1: 基础设施
- [ ] Phase 2: 高级模式挖掘算法
- [ ] Phase 3: LLM 辅助代码生成
- [ ] Phase 4: 元学习优化
