# RFC 010: M3 信号择时实施方案

| 字段 | 内容 |
|---|---|
| RFC 编号 | 010 |
| 标题 | M3 信号择时实施方案 |
| 作者 | investor (w-c2cc8593) |
| 状态 | 草稿 |
| 创建日期 | 2026-08-26 |
| 上游设计 | [RFC 004 盈利引擎设计](004-profit-engine-design.md) M3 模块；[RFC 005 工单包](005-profit-engine-work-tickets.md) M3-1/M3-2/M3-3 |
| 前置依赖 | M3-1 ✅ 已完成（R-009 + signal-grading.md）；M3-3 依赖 M1-1 ✅；M3-2 无依赖 |
| 实施 commits | 待补充 |
| 完成度 | M3-1 ✅ 100%、M3-2 🟢 0%、M3-3 🟢 0%，总体 33% |

---

## 1. 背景与目标

### 1.1 当前问题

**M3 信号择时是盈利引擎的核心**，但当前存在：
1. **M3-1 信号分级**：✅ 已完成（R-009 + docs/architecture/signal-grading.md）
2. **M3-2 策略回测**：❌ 未实施，不知道哪些策略在不同市场环境下有效
3. **M3-3 信号追踪**：❌ 未实施，无法评估信号质量和胜率

**核心矛盾**：
- 有信号分级规则（A/B/C），但**没有历史验证数据**
- 有策略工具（strategy_execute），但**没有跨环境回测**
- 下单后**无法追踪信号表现**，学习飞轮断链

### 1.2 目标

**M3-2 候选策略跨环境回测**：
- 选出 5 个候选策略
- 在牛市/熊市/震荡 3 个区间回测
- 输出收益/回撤/夏普矩阵
- 选出 ≥3 个样本外夏普 >1 的策略

**M3-3 信号质量追踪**：
- 每个买入信号后续 5/10/20 日表现落库
- 可查询信号追踪表
- 可计算胜率

---

## 2. 工单分析

### 2.1 M3-1 信号分级制 ✅ 已完成

**RFC 005 验收标准**：
- ✅ 文档合入 docs/
- ✅ 分级定义+仓位映射
- ✅ 至少 3 个历史信号回溯分级示例

**当前状态**：
- ✅ R-009 规则已写入 genome（2026-08-23）
- ✅ docs/architecture/signal-grading.md 已存在
- ✅ 分级定义清晰：A级（≥3维共振）→ 标准仓、B级（2维）→ 半仓、C级（1维）→ 只观察

**结论**：M3-1 已完成，无需实施。

---

### 2.2 M3-2 候选策略跨环境回测 🟢 待实施

**RFC 005 验收标准**：
- `strategy_execute(mode=backtest)` 对 5 策略 × 3 区间
- 输出收益/回撤/夏普矩阵
- 选出 ≥3 个样本外夏普 >1

**问题**：
1. **哪 5 个策略？**（需要从 strategy_list 中选）
2. **3 个区间如何划分？**（牛市/熊市/震荡的日期范围）
3. **样本外是什么？**（训练集 vs 测试集）

**解决方案**（稍后设计）。

---

### 2.3 M3-3 信号质量追踪 🟢 待实施

**RFC 005 验收标准**：
- 每个买入信号后续 5/10/20 日表现落库
- 查信号追踪表
- 每个信号有后续表现记录，可算胜率

**当前问题**：
1. **如何追踪信号？**（portfolio_trade 后自动记录？）
2. **落库到哪里？**（osMemory？PostgreSQL？）
3. **如何计算表现？**（5/10/20 日后价格 vs 买入价）

**解决方案**（稍后设计）。

---

## 3. 技术方案

### 3.1 M3-3: 信号质量追踪（优先实施）

#### 3.1.1 需求

**核心能力**：
- 买入信号产生时，记录：标的、价格、信号来源、分级、时间戳
- 定期（每日盘后）回填表现：5/10/20 日后价格、涨跌幅、胜负
- 提供查询接口：按信号来源/分级/时间查胜率

**数据结构**：
```typescript
interface SignalRecord {
  signal_id: string;           // 信号唯一 ID
  symbol: string;              // 标的代码
  signal_date: string;         // 信号日期
  entry_price: number;         // 买入价格
  source: string;              // 信号来源（strategy_execute / opportunity_scan / mainline_stocks）
  grade: 'A' | 'B' | 'C';      // 信号分级
  reason: string;              // 信号理由
  
  // 表现回填（盘后例程）
  performance_5d?: {
    date: string;
    price: number;
    return_pct: number;
    win: boolean;              // 是否盈利
  };
  performance_10d?: { ... };
  performance_20d?: { ... };
  
  // 实际交易（如果执行了）
  executed: boolean;
  execution_price?: number;
  execution_date?: string;
}
```

#### 3.1.2 实施方案

**步骤 1: 扩展 trading 插件**

在 `portfolio_trade` 执行后，自动调用 `signal_track(action='record')`：

```typescript
// trading/src/index.ts
if (result.success && action === 'BUY') {
  await this.signalTrack.record({
    symbol: args.symbol,
    signal_date: new Date().toISOString().slice(0, 10),
    entry_price: executedPrice,
    source: inferSourceFromReason(args.reason), // 从 reason 推断来源
    grade: inferGradeFromReason(args.reason),   // 从 reason 推断分级
    reason: args.reason,
    executed: true,
    execution_price: executedPrice,
  });
}
```

**步骤 2: 新增 signal_track 工具**

在现有 `intelligence` 插件或新建 `signal-tracking` 插件：

```typescript
ctx.tools.register(defineTool({
  name: 'signal_track',
  description: '信号质量追踪：record 记录买入信号，update 回填表现，report 统计胜率',
  parameters: {
    action: {
      type: 'string',
      enum: ['record', 'update', 'report'],
      required: true,
    },
    // ... 其他参数
  },
  execute: async (args) => {
    if (args.action === 'record') {
      // 落库到 osMemory 或 quantsys-v2
      return await osMemory.write({
        title: `信号记录：${args.symbol}`,
        content: JSON.stringify(args),
        namespace: 'signal_tracking',
        tags: ['signal', args.source, args.grade, args.symbol],
      });
    }
    
    if (args.action === 'update') {
      // 盘后例程：读取所有未回填的信号，计算表现
      const signals = await osMemory.search({
        namespace: 'signal_tracking',
        query: 'performance_5d:null',
      });
      
      for (const sig of signals) {
        const klines = await qv2.getKlines(sig.symbol, sig.signal_date, ...);
        const perf5d = calculatePerformance(klines, 5);
        await osMemory.update(sig.id, { performance_5d: perf5d });
      }
    }
    
    if (args.action === 'report') {
      // 统计胜率
      const signals = await osMemory.search({
        namespace: 'signal_tracking',
        filters: { source: args.source, grade: args.grade },
      });
      
      const winRate = signals.filter(s => s.performance_20d?.win).length / signals.length;
      return { win_rate: winRate, ... };
    }
  },
}));
```

**步骤 3: Agent OS 盘后例程**

创建 `signal_tracking_daily_update` 任务：

```yaml
- id: signal_tracking_daily_update
  name: '信号追踪表现回填'
  schedule: '0 30 16 * * 1-5'  # 工作日 16:30
  action: tool_call
  tool: signal_track
  arguments:
    action: update
```

#### 3.1.3 验收标准

**功能验收**：
- ✅ 买入后自动记录信号（signal_track record）
- ✅ 盘后自动回填表现（signal_track update）
- ✅ 可查询信号追踪表（signal_track report）
- ✅ 每个信号有 5/10/20 日表现记录

**数据验收**：
- ✅ 至少 10 条信号记录
- ✅ 至少 5 条已回填表现
- ✅ 可计算胜率（胜率 = 盈利信号数 / 总信号数）

---

### 3.2 M3-2: 候选策略跨环境回测（次优先）

#### 3.2.1 需求

**目标**：
- 选出 5 个候选策略
- 在牛市/熊市/震荡 3 个区间回测
- 输出收益/回撤/夏普矩阵
- 选出 ≥3 个样本外夏普 >1

**区间划分**（基于上证指数）：
- **牛市**：2020-07-01 ~ 2021-02-28（3000 → 3731）
- **熊市**：2021-03-01 ~ 2022-04-30（3731 → 2863）
- **震荡**：2022-05-01 ~ 2023-12-31（2863 → 2974）

**候选策略**（从 strategy_list 选 5 个）：
1. MACD 金叉
2. 均线多头排列
3. RSI 超卖反弹
4. 突破前高
5. 低估值+高 ROE

#### 3.2.2 实施方案

**步骤 1: 确认候选策略**

```bash
# 调用 strategy_list 查看可用策略
curl http://localhost:5001/api/strategies/list
```

**步骤 2: 跨环境回测**

```bash
# 对每个策略在 3 个区间回测
for strategy_id in 1 2 3 4 5; do
  for period in "bull" "bear" "sideways"; do
    strategy_execute(
      strategy_id=$strategy_id,
      mode='backtest',
      start_date=...,
      end_date=...,
      initial_capital=100000
    )
  done
done
```

**步骤 3: 汇总矩阵**

```
| 策略 | 牛市夏普 | 熊市夏普 | 震荡夏普 | 平均夏普 | 最大回撤 |
|---|---|---|---|---|---|
| MACD 金叉 | 1.2 | -0.5 | 0.8 | 0.5 | -15% |
| 均线多头 | 1.5 | 0.3 | 1.1 | 0.97 | -12% |
| ... | ... | ... | ... | ... | ... |
```

**步骤 4: 选出优胜策略**

- 筛选：平均夏普 >1 且最大回撤 <-20%
- 选出 ≥3 个策略作为"生产级策略池"

#### 3.2.3 验收标准

**功能验收**：
- ✅ 5 个策略 × 3 个区间 = 15 次回测
- ✅ 输出收益/回撤/夏普矩阵
- ✅ 选出 ≥3 个样本外夏普 >1

**数据验收**：
- ✅ 回测矩阵完整
- ✅ 至少 3 个策略夏普 >1
- ✅ 输出策略推荐清单

---

## 4. 实施优先级

| 工单 | 优先级 | 依赖 | 工作量 | 状态 |
|---|---|---|---|---|
| **M3-1** | P0 | 无 | 0h | ✅ 已完成 |
| **M3-3** | **P0** | M1-1 ✅ | **4h** | 🟢 立即实施 |
| **M3-2** | P1 | 无 | 3h | 🟡 次优先 |

**建议**：先 M3-3（信号追踪是学习飞轮基础），再 M3-2（策略回测）。

---

## 5. 风险与限制

### 5.1 数据存储

**问题**：信号追踪数据存储在 osMemory 还是 quantsys-v2 PostgreSQL？

**决策**：
- **短期**：osMemory（快速实施）
- **长期**：迁移到 PostgreSQL（结构化查询）

### 5.2 表现计算

**问题**：如何定义"胜负"？
- 5/10/20 日后涨幅 >0% 算胜？
- 还是涨幅 >5% 算胜？

**决策**：
- **胜**：涨幅 >0%（保守）
- **大胜**：涨幅 >10%（标记）

### 5.3 信号分级推断

**问题**：从 `reason` 字符串推断信号分级不准确。

**解决方案**：
- portfolio_trade 增加 `signal_grade` 参数（可选）
- 没有则从 reason 推断，有则直接使用

---

## 6. 下一步行动

**今日（2026-08-26）**：
1. ✅ RFC 010 设计完成
2. 🟢 开始实施 M3-3 信号追踪

**本周**：
1. M3-3 信号追踪完整实施（4h）
2. M3-2 候选策略回测（3h）

**验收标准**：
- M3-3: 至少 10 条信号记录，可查胜率
- M3-2: 5×3 回测矩阵，选出 ≥3 个夏普>1 策略

---

## 附录

### A. 相关文档

- [RFC 004 盈利引擎设计](004-profit-engine-design.md)
- [RFC 005 工单包](005-profit-engine-work-tickets.md)
- [docs/architecture/signal-grading.md](../architecture/signal-grading.md)

### B. 工具清单

- `strategy_list`: 列出候选策略
- `strategy_execute`: 策略回测
- `signal_track`: 信号追踪（待实现）
- `portfolio_trade`: 买卖交易

---

**状态**：草稿  
**作者**：investor (w-c2cc8593)  
**日期**：2026-08-26

