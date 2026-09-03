# Agent-DH 自主能力体系

## 概述

Agent-DH 已具备完整的**自我管理、自我学习、自我进化**能力，参考深度学习训练循环设计，实现真正的自主运行。

---

## 能力矩阵

| 能力层次 | 现有工具 | 新增工具 | 作用 |
|---------|---------|---------|------|
| **L4 元学习** | - | meta_profile, meta_curriculum, meta_transfer | 学习如何学习 |
| **L3 架构层** | self_restart, self_finalize, self_status | learning_apply | 修改代码、插件 |
| **L2 策略层** | evolution_run, evolution_leaderboard | learning_analyze, learning_distill | 优化策略参数 |
| **L1 记忆层** | memory_search, memory_write, experience_write | learning_track | 积累经验 |

---

## 1. 现有能力（已实现）

### 1.1 生命周期管理 (lifecycle 插件)

#### `self_restart` - 自我重启
- **能力**: 修改代码 → 重启生效 → 自动验证
- **安全机制**: git wip 分支检查点、启动失败自动回滚
- **限流**: 每小时最多 10 次
- **续跑**: 自动注入续跑消息到原会话

#### `self_finalize` - 完成自修复
- **merge**: 验证通过，合并回基线
- **rollback**: 验证失败，放弃修改

#### `self_status` - 状态查询
- 当前分支、待续跑任务、重启历史

**典型流程**:
```
发现 bug → 修改代码 → self_restart(reason, resume_task)
    ↓
自动重启 → 自动续跑 → 执行验证
    ↓
验证通过 → self_finalize(merge) ✅
验证失败 → self_finalize(rollback) ❌
```

### 1.2 长期记忆 (memory 插件)

#### `memory_write` - 写入记忆
- 保存分析结论、决策依据
- 重要性评分影响检索排序
- 支持命名空间（default/experience/decision/analysis）

#### `memory_search` - 搜索记忆
- 语义搜索历史经验
- 复用过往分析

#### `experience_write` - 记录交易经验
- 专门记录交易得失
- 自动标记亏损为高重要性

### 1.3 策略进化 (evolution 插件)

#### `evolution_run` - 策略进化
- 回测参数变体
- 评估适应度
- 生成改进建议

#### `evolution_leaderboard` - 排行榜
- 查看各策略适应度评分

---

## 2. 新增能力（RFC 003）

### 2.1 自我学习引擎 (learning 插件) ✨ NEW

#### `learning_track` - 追踪经验
- **自动拦截**: 自动追踪关键工具调用（无需手动）
- **结构化记录**: 行动 + 上下文 + 结果 + 奖励
- **持久化**: 存入 memory，支持语义检索

**自动追踪的工具**:
- portfolio_trade
- strategy_execute
- model_predict
- opportunity_scan
- rotation_execute

#### `learning_analyze` - 分析学习机会
- **模式挖掘**: 识别成功/失败的共性
- **改进建议**: 自动生成优化方向
- **可蒸馏识别**: 标记可提取为规则的模式

**输出示例**:
```json
{
  "patterns": [
    {
      "pattern_type": "RSI<30 且大盘上涨",
      "success_rate": 0.82,
      "avg_reward": 0.65,
      "sample_size": 23
    }
  ],
  "improvements": [
    {
      "target": "momentum_strategy",
      "issue": "震荡市成功率偏低",
      "suggestion": "增加波动率过滤"
    }
  ]
}
```

#### `learning_distill` - 知识蒸馏
- **复杂 → 简单**: 50次推理 → 10条规则
- **格式支持**: rules / code / decision_tree / prompt_snippet
- **置信度过滤**: 只输出高置信度规则

**蒸馏流程**:
```
输入: 100个成功交易的完整分析过程
   ↓ 特征提取
识别共性: "当 RSI<30 且大盘趋势向上 时买入"
   ↓ 规则生成
输出: if (rsi < 30 && market_trend == 'up') then buy()
```

#### `learning_apply` - 应用学习结果
- **真实语义（2026-09-03 Fix③）**: 规则生命周期状态机——learning_distill 蒸馏出的规则以 `kind=rule / status=testing` 持久化在 OS 记忆，learning_apply 将指定规则转正为 `status=active`（含 applied_at/applied_by/applied_context 审计字段）。
- **入参**: `rule_id`（distill 返回的稳定规则 ID）+ `context`（应用上下文）+ `dry_run`（默认 true）
- **安全预览**: dry_run=true 只模拟（返回 impact 与 action_taken），不落库
- **幂等**: 已 active 的规则重复应用返回 `already_active: true`，不重复写入
- **诚实失败**: 规则不存在返回 `applied: false` + 指引先 distill 的消息，绝不伪造成功

**改进类型**: 由 learning_distill 生成（rule / code / decision_tree / prompt_snippet），apply 不重新发明类型，只负责把已蒸馏的规则转正为可执行状态。

### 2.2 元学习插件 (metalearn) 📋 TODO

#### `meta_profile` - 自我画像
```json
{
  "strengths": ["技术分析", "风险控制"],
  "weaknesses": ["宏观判断准确率 45%"],
  "learning_velocity": {
    "strategy": 0.12,  // 每周改进率
    "coding": 0.08
  },
  "skill_tree": { ... }
}
```

#### `meta_curriculum` - 课程规划
- 根据能力画像生成学习路径
- Week 1: 收集案例
- Week 2: 训练规则
- Week 3: 回测验证
- Week 4: 上线监控

#### `meta_transfer` - 知识迁移
- 股票筛选因子 → 行业轮动
- 跨领域知识复用

### 2.3 基准测试插件 (benchmark) 📋 TODO

#### `benchmark_run` - 基准测试
- 运行标准测试集
- 量化能力水平

#### `benchmark_compare` - 版本对比
- A/B 测试改进效果
- 自动回滚指标下降版本

---

## 3. 完整学习循环

```
┌─────────────────────────────────────────────────────────┐
│  日常运行: 自动追踪                                        │
│  • 工具调用 → learning 自动拦截 → 记录经验 → 存入 memory  │
└─────────────────────────────────────────────────────────┘
              ↓ 积累 50+ 经验
┌─────────────────────────────────────────────────────────┐
│  定期分析: learning_analyze                               │
│  • 挖掘模式 → 识别问题 → 生成建议 → 标记可蒸馏规则         │
└─────────────────────────────────────────────────────────┘
              ↓ 发现改进机会
┌─────────────────────────────────────────────────────────┐
│  知识蒸馏: learning_distill                               │
│  • 提取规则 → 验证置信度 → 生成代码/配置                   │
└─────────────────────────────────────────────────────────┐
              ↓ 规则通过验证
┌─────────────────────────────────────────────────────────┐
│  安全应用: learning_apply（规则 testing→active 转正）       │
│  • 应用即进入活跃集供决策检索（无 self_restart 集成）        │
└─────────────────────────────────────────────────────────┘
              ↓ 持续优化
┌─────────────────────────────────────────────────────────┐
│  元学习: meta_* 工具                                      │
│  • 跟踪学习效率 → 优化学习策略 → 知识迁移                  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 训练循环类比

| 概念 | 深度学习 | Agent-DH |
|-----|---------|----------|
| 训练数据 | ImageNet | Experience Buffer (memory) |
| 模型参数 | Weights | 策略参数 + 代码 |
| 前向传播 | Forward Pass | 工具执行 |
| 损失函数 | Loss | Reward Signal |
| 反向传播 | Backprop | learning_analyze + distill |
| 梯度下降 | SGD | learning_apply |
| Epoch | 遍历数据集 | 每周学习周期 |
| Batch | Mini-batch | Experience Replay |
| 验证集 | Val Set | Backtest |
| Early Stop | 验证集 loss 上升停止 | benchmark 指标下降回滚 |
| Checkpoint | 保存模型权重 | git wip + self_restart |
| 迁移学习 | Fine-tune | meta_transfer |
| 知识蒸馏 | Teacher → Student | 复杂推理 → 简单规则 |

---

## 5. 奖励信号设计

### 5.1 交易类
```python
reward = (
  0.5 * normalized_return +       # 收益率
  0.3 * (1 - drawdown_ratio) +    # 回撤控制
  0.2 * risk_adjusted_return      # 夏普比率
)
```

### 5.2 分析类
```python
reward = (
  0.4 * prediction_accuracy +     # 预测准确率
  0.3 * user_feedback +           # 用户评分
  0.3 * execution_efficiency      # 执行效率
)
```

### 5.3 系统类
```python
reward = (
  0.5 * (1 - error_rate) +        # 稳定性
  0.3 * latency_improvement +     # 性能提升
  0.2 * code_quality              # 代码质量
)
```

---

## 6. 安全机制

### 6.1 改动限制
- ✅ 单次改动 ≤ 3 个文件
- ✅ 关键模块需额外验证
- ✅ 必须通过 benchmark

### 6.2 回滚触发
- ✅ 启动失败（lifecycle 已实现）
- 🆕 关键指标下降 > 10%
- 🆕 连续 3 次任务失败

### 6.3 学习速率控制
- **初期**: 保守（只调参数）
- **稳定期**: 激进（可改代码）
- **异常期**: 冻结（只记录不应用）

---

## 7. 使用示例

### 7.1 完整学习周期

```typescript
// Day 1-7: 日常运行，自动积累经验
// （无需手动调用，learning 自动拦截工具调用）

// Day 7: 定期分析
const analysis = await tools.learning_analyze({
  scope: 'recent',
  focus: 'patterns',
  time_range_days: 7
});

console.log('发现模式:', analysis.patterns);
console.log('改进建议:', analysis.improvements);

// 发现：momentum 策略在震荡市表现差
// 建议：增加波动率过滤

// Day 8: 知识蒸馏（2026-09-03 Fix③：蒸馏即落库）
// rules 以 kind=rule/status=testing 持久化到 OS 记忆，返回带 memory_id/rule_id
const rules = await tools.learning_distill({
  source: 'successful_trades',
  target_format: 'code',
  min_confidence: 0.8
});

// 提取到规则：if (volatility > 15%) skip momentum
// rules[0].rule_id = 'rule_8f3a...'，rules[0].persistence = {persisted: N, ...}

// Day 9: 应用改进（先预览，不落库）
const preview = await tools.learning_apply({
  rule_id: rules[0].rule_id,
  context: { symbol: '000001', strategy_id: 3 },
  dry_run: true
});

console.log('模拟应用:', preview.impact);   // {from_status:'testing', to_status:'active', ...}
console.log('已应用:', preview.applied);     // false（dry_run）

// Day 10: 确认后真实应用（testing → active 转正 + 审计字段）
const result = await tools.learning_apply({
  rule_id: rules[0].rule_id,
  context: { symbol: '000001', strategy_id: 3 },
  dry_run: false
});

// 自动：记忆内规则状态 testing→active，payload 增 applied_at/applied_by/applied_context
// 规则进入活跃集，供未来决策检索（非 self_restart 集成——已下线该不实承诺）
```

### 7.2 快速修复循环

```typescript
// 发现 bug: risk_controller 计算超时

// 1. 分析
const issue = await tools.learning_analyze({
  scope: 'all',
  focus: 'failures',
  time_range_days: 1
});

// 2. 生成修复（可以让 LLM 生成优化代码）
const fix = {
  file: 'packages/risk/src/controller.ts',
  description: '添加计算缓存',
  code: 'const cache = new Map(); ...'
};

// 3. 应用并验证（真实语义：将已蒸馏规则 testing→active 转正）
await tools.learning_apply({
  rule_id: fixRule.rule_id,
  context: { component: 'risk_controller' },
  dry_run: false
});

// 4. 规则进入活跃集供决策检索；复盘由 weekly_report / validation_gate 承担
```

---

## 8. 路线图

### Phase 1: 基础设施 ✅ (当前)
- [x] RFC 003 设计文档
- [x] learning 插件骨架
- [x] 自动追踪机制
- [x] 经验持久化
- [x] 基础模式挖掘

### Phase 2: 智能分析 (2 周)
- [ ] 高级模式挖掘算法
- [ ] LLM 辅助规则蒸馏
- [ ] benchmark 插件
- [ ] 自动回滚机制

### Phase 3: 代码生成 (3 周)
- [ ] LLM 驱动的代码生成
- [ ] 单元测试自动生成
- [ ] 多文件协同修改
- [ ] 冲突检测与解决

### Phase 4: 元学习 (2 周)
- [ ] metalearn 插件
- [ ] 能力画像系统
- [ ] 自适应课程规划
- [ ] 跨任务知识迁移

---

## 9. 成功指标

### 短期（1 个月）
- ✅ 自动追踪覆盖率 > 80%
- 🎯 策略优化成功率 > 60%
- 🎯 蒸馏规则准确率 > 75%
- 🎯 改进周期 < 24 小时

### 中期（3 个月）
- 🎯 整体夏普比率提升 20%
- 🎯 代码质量改进 15%
- 🎯 可复用技能库 > 50 条
- 🎯 自主解决问题 > 60%

### 长期（6 个月）
- 🎯 学习效率提升 2x
- 🎯 知识迁移成功案例 > 10
- 🎯 自主解决 80% 常见问题
- 🎯 用户干预频率降低 50%

---

## 10. 与现有系统集成

| 现有插件 | 新增插件 | 集成方式 |
|---------|---------|---------|
| lifecycle (self_restart) | learning (apply) | 安全应用改动 |
| memory | learning (track) | 经验持久化 |
| evolution | learning (analyze) | 智能搜索方向 |
| strategy | learning (distill) | 规则验证 |
| risk | learning (apply) | 改动前风险评估 |

---

## 11. 核心优势

### vs 传统 Agent
- ❌ 传统: 固定规则，不会学习
- ✅ Agent-DH: 从经验中持续学习

### vs 纯 LLM
- ❌ 纯 LLM: 每次重新推理，成本高
- ✅ Agent-DH: 蒸馏为规则，快速决策

### vs 人工优化
- ❌ 人工: 周期长（数周），主观
- ✅ Agent-DH: 自动化（数小时），客观

---

## 附录: 完整工具清单

### 生命周期管理
- `self_restart` - 重启自己
- `self_finalize` - 完成自修复
- `self_status` - 查看状态

### 记忆系统
- `memory_write` - 写入记忆
- `memory_search` - 搜索记忆
- `experience_write` - 记录交易经验

### 策略进化
- `evolution_run` - 策略进化
- `evolution_leaderboard` - 排行榜

### 自我学习 ✨ NEW
- `learning_track` - 追踪经验
- `learning_analyze` - 分析机会
- `learning_distill` - 知识蒸馏
- `learning_apply` - 应用改进

### 元学习 📋 TODO
- `meta_profile` - 自我画像
- `meta_curriculum` - 课程规划
- `meta_transfer` - 知识迁移

### 基准测试 📋 TODO
- `benchmark_run` - 基准测试
- `benchmark_compare` - 版本对比

---

**状态**: 🚀 Phase 1 完成，Phase 2-4 设计中

**文档版本**: 1.0

**最后更新**: 2026-08-20
