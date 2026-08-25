# 验证门回测腿验收测试（2026-08-25）

## 实施内容

验证门回测腿接入：策略类 candidate 先过三窗口回测（牛/熊/震荡），夏普<0.5 或回撤<-15% 当场拒绝（省 5 天观察期）；提示词类跳过回测腿直接进模拟盘观察门。

**改动**：
- `agent-dh/packages/strategy/src/index.ts`：strategy_execute 回测模式新增 start_date/end_date/initial_capital 参数透传（修复原硬编码空串 bug）
- `agent-dh/packages/evolver/src/index.ts`：
  - CandidateRecord 扩展：mutation_type/strategy_id/params_override/backtest_verdict（P4 元学习数据地基）
  - judgeCandidates 新增回测腿（第一级门）：策略类 candidate 三窗口回测 → 失败当场 reject（跳过观察门）
  - registerCandidate 参数扩展：接受 mutation_type/strategy_id/params_override
  - validation_gate 描述更新：两级门机制

**回测窗口**（2026-08-25 测试后修正）：
- ~~三窗口（熊/震荡/牛）~~：短窗口 MA60 策略信号稀疏，门槛 sharpe≥0.5 误杀好策略（178/267 三窗口全 0 信号）
- **修正为**：全区间单窗口（002716 湖南白银 2025-01-02 ~ 2026-08-21，394 交易日）

**回测腿通过条件**（放宽门槛，只拦截明显垃圾）：
- 拒绝：夏普 <0（亏钱策略）**或** 回撤 <-30%（超激进）**或** 0 信号（策略根本没执行）
- 通过：否则（包括低夏普但有交易的保守策略）

## 验收标准

### 1. strategy_execute 回测日期透传修复

```bash
# 调用回测 API 指定日期窗口，返回真实回测结果（非空）
curl -X POST http://localhost:5001/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":178,"symbol":"002716","start_date":"2026-06-01","end_date":"2026-08-21","initial_capital":100000}' \
  | jq '.data.sharpeRatio, .data.totalTrades'
# 预期：返回夏普值和交易笔数（非 0）
```

**实测**（2026-08-25 全区间 002716）：
```
267 通道波段：sharpe=0.38 mdd=-9.8% trades=2 → 通过 ✅（低夏普但有交易，不误杀）
178 value-macd：sharpe=1.24 mdd=-7.3% trades=1 → 通过 ✅
268 趋势跟踪：sharpe=1.58 mdd=-36.3% trades=3 → 拒绝 ✅（正确拦截超激进策略）
```
逻辑验证通过：宽松门槛不误杀保守策略，同时拦截超激进/亏钱/无效策略。

### 2. 回测腿拒绝垃圾策略

手动创建策略类 candidate（mutation_type='strategy_param', strategy_id=999-假设垃圾策略），调用 validation_gate：

```typescript
// 手动编辑 ~/.dsh/profiles/investment/data/candidates.json 添加测试 candidate
{
  "id": "cand_test_backtest_reject",
  "section": "rules",
  "section_version": 6,
  "genome_version": "g13",
  "baseline_version": "g12",
  "created_at": "2026-08-25T07:00:00Z",
  "observe_until": "2026-08-20T00:00:00Z",  // 已到期
  "status": "watching",
  "mutation_type": "strategy_param",
  "strategy_id": 164,  // 用 164 三频共振（002716 牛窗口应该信号少/夏普低）
}

// 调用 validation_gate(force=true)
// 预期：backtest_verdict.passed = false, status = 'rejected'
```

**实测**：待首个策略类 candidate 自然产生后验证（当前所有 candidate 都是 prompt 类）

### 3. 回测腿通过好策略

策略类 candidate（strategy_id=178 or 268）：
```
预期：backtest_verdict.passed = true，进入观察门（第二级）
```

### 4. 提示词类 candidate 跳过回测腿

当前 g10 candidate（lessons 改写，mutation_type='prompt'，无 strategy_id）：
```
预期：判决日志显示"跳过回测腿（prompt 类）"，直接进观察门
```

**实测**（2026-08-25）：g10 candidate 明天 15:30 例程裁决时自动验证

### 5. candidates.json 包含 backtest_verdict

任何经过回测腿的 candidate（无论通过/拒绝），其 candidates.json 记录必须包含 backtest_verdict 字段（三窗口结果 + passed + reason）。

## 当前状态

- ✅ 代码实现完成（commit 921ae1aa，含测试后修正）
- ✅ 编译通过（pnpm build）
- ✅ 单元逻辑测试通过（267/178/268 三策略验证拒绝/通过路径正确）
- 🔶 端到端验收：等首个策略类 candidate 或 g10 明天裁决
- ⏳ 文档：RFC 008 §8 补充两级门机制说明（待补）

## 下一步

1. g10 candidate 明天裁决时观察日志（验证提示词类跳过回测腿）
2. 策略×regime 矩阵工单出炉后，首个策略类 candidate 进入验证门时验证回测腿拒绝/通过路径
3. RFC 008 文档更新：两级门实际形态 + mutation_type 分流规则
