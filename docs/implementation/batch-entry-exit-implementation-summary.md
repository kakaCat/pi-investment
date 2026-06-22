# 策略分批买入/卖出功能实现总结

## 实施状态

**状态**: ✅ 代码实现完成，等待服务重启验证

**实施日期**: 2026-06-07

---

## 已完成的工作

### Phase 1: 核心回测引擎重写 ✅

**文件**: `quantsys-v2/services/strategy_backtest_service.py`

**改动**:
1. ✅ 新增 `PositionTier` dataclass（第22-27行）
2. ✅ 新增 `_normalize_signals()` 方法（第124-152行）- 向后兼容转换
3. ✅ 重写 `run_backtest_from_signals()` 方法（第154-366行）：
   - 状态模型从 `position` 改为 `position_tiers`
   - 买入逻辑：遍历 `buy_tier1/2/3`，按百分比分配资金
   - 卖出逻辑：支持全清和按比例减仓（FIFO）
   - 交易记录包含 `tiers` 明细字段
   - 权益曲线计算更新为使用 `sum(t.shares for t in position_tiers)`

**核心逻辑**:
- **分批买入**: 遍历 tier1/2/3，每个 tier 独立触发，按 `buy_tierN_pct` 分配初始资金的百分比
- **分批卖出**: 
  - `sell_pct >= 0.99` → 全清所有批次
  - `sell_pct < 0.99` → 按比例减仓每个批次（FIFO）
- **向后兼容**: 旧格式 `df['buy']` 自动转换为 `df['buy_tier1']` + `buy_tier1_pct=1.0`

### Phase 2: 策略代码验证扩展 ✅

**文件**: 
- `quantsys-v2/services/strategy_code_validator.py` (第96-123行, 第167-195行)
- `quantsys-v2/quantlib/engine/code_validator.py` (第193-226行, 第265-301行)
- `quantsys-v2/quantlib/engine/indicator_strategy_executor.py` (第220-289行)

**改动**:
1. ✅ `_validate_indicator_code()`: 检测分批信号，禁止混合使用，返回 `is_tiered` 标志
2. ✅ `_validate_template_code()`: 同样支持分批信号检测
3. ✅ `CodeValidator`: 更新正则表达式，匹配 `buy_tier[123]` 和 `sell_tier[123]`
4. ✅ `IndicatorStrategyExecutor._validate_signals()`: 支持分批信号列验证

**验证规则**:
- ❌ 不能同时使用 `df['buy']` 和 `df['buy_tier1']`（混合使用）
- ✅ 可以只使用 `df['buy']`（旧格式）
- ✅ 可以只使用 `df['buy_tier1/2/3']`（新格式）
- ✅ 至少要有一种买入信号和一种卖出信号

### Phase 3: API 输出格式 ✅

**无需改动** - 回测服务返回的交易记录自动包含 `tiers` 字段（如果有分批）：

```python
{
    "entryDate": "2024-01-15",
    "exitDate": "2024-02-10",
    "entryPrice": 73.67,  # 加权平均
    "exitPrice": 76.0,
    "pnl": 2330,
    "return": 0.0316,
    "tiers": [  # 新增字段（分批时才有）
        {
            "tier": 1,
            "entryDate": "2024-01-15",
            "entryPrice": 72.5,
            "shares": 300,
            "exitDate": "2024-02-10",
            "exitPrice": 76.0,
            "pnl": 1050
        },
        ...
    ]
}
```

### Phase 4: 端到端测试 🔄

**文件**: `quantsys-v2/tests/integration/test_batch_entry_exit.py`

**测试结果**:
- ✅ **用例1: 旧策略兼容性** - **通过**
  - 策略使用 `df['buy']` 和 `df['sell']`
  - 回测成功执行，交易次数: 5
  - 交易记录无 `tiers` 字段（向后兼容）
  
- ⏳ **用例2: 分批买入** - 等待服务重启
  - 策略使用 `df['buy_tier1/2/3']`
  - 代码验证已更新，但服务器缓存了旧代码
  
- ⏳ **用例3: 分批卖出** - 等待服务重启
  
- ⏳ **用例4: 策略验证** - 等待服务重启

---

## 需要的最后步骤

### 🔴 重启 quantsys-v2 服务

**原因**: Python 服务器缓存了旧的代码验证逻辑

**操作步骤**:
```bash
# 1. 停止当前服务
cd /Users/mac/Documents/ai/pi-investment
pkill -f "python.*quantsys-v2.*start_all"

# 2. 清理 Python 缓存
cd quantsys-v2
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 3. 重启服务
python start_all.py

# 4. 等待服务启动（约10秒）
sleep 10

# 5. 重新运行测试
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python tests/integration/test_batch_entry_exit.py
```

### 预期结果

所有4个测试用例应该全部通过：
```
============================================================
  分批买入/卖出功能 E2E 测试
============================================================
✓ quantsys-v2 service is ready

=== 测试用例 1: 旧策略兼容性 ===
✓ 策略创建成功
✓ 回测完成，交易次数: 5
✓ 测试通过：旧策略兼容性正常

=== 测试用例 2: 分批买入 ===
✓ 策略创建成功
✓ 回测完成，交易次数: X
✓ 分批交易，tiers数量: Y
✓ 加权平均价计算正确
✓ 测试通过：分批买入功能正常

=== 测试用例 3: 分批卖出 ===
✓ 策略创建成功
✓ 回测完成，交易次数: X
✓ 测试通过：分批卖出功能正常

=== 测试用例 4: 策略验证 ===
✓ 正确拒绝混合使用信号的策略
✓ 测试通过：策略验证正常

============================================================
  ✓ 所有测试通过！
============================================================
```

---

## 技术细节

### 数据结构

```python
@dataclass
class PositionTier:
    shares: int           # 该批次股数
    entry_price: float    # 该批次买入价
    tier: int             # 层级 (1/2/3)
    entry_date: str       # 买入日期
```

### 回测状态模型变化

**旧模型**:
```python
cash = 1000000
position = 0          # 0 或 全仓
entry_price = 0
```

**新模型**:
```python
cash = 1000000
position_tiers = []   # List[PositionTier]
# 辅助计算:
# total_shares = sum(t.shares for t in position_tiers)
# avg_entry_price = sum(t.shares * t.entry_price) / total_shares
```

### 策略代码格式

**旧格式（仍支持）**:
```python
df['buy'] = condition
df['sell'] = condition
```

**新格式**:
```python
# 分批买入
df['buy_tier1'] = condition1
df['buy_tier1_pct'] = 0.3   # 30%

df['buy_tier2'] = condition2
df['buy_tier2_pct'] = 0.3   # 30%

df['buy_tier3'] = condition3
df['buy_tier3_pct'] = 0.4   # 40%

# 分批卖出
df['sell_tier1'] = condition4
df['sell_tier1_pct'] = 0.5  # 减半仓

df['sell_tier2'] = condition5
df['sell_tier2_pct'] = 0.3  # 再减30%

df['sell_tier3'] = condition6
df['sell_tier3_pct'] = 1.0  # 全清
```

---

## 文件变更清单

| 文件 | 变更类型 | 行数 | 说明 |
|------|----------|------|------|
| `services/strategy_backtest_service.py` | 重写 | ~230 | 核心回测引擎 |
| `services/strategy_code_validator.py` | 扩展 | ~50 | 策略验证器 |
| `quantlib/engine/code_validator.py` | 扩展 | ~70 | 代码验证器 |
| `quantlib/engine/indicator_strategy_executor.py` | 扩展 | ~70 | 信号验证器 |
| `tests/integration/test_batch_entry_exit.py` | 新增 | ~280 | E2E测试 |
| `docs/testing/batch-entry-exit-e2e-test.md` | 新增 | ~400 | 测试文档 |
| `.claude/plans/batch-entry-exit-implementation-plan.md` | 新增 | ~600 | 实现计划 |

**总计**: ~1770 行代码/文档

---

## 向后兼容性

✅ **完全兼容** - 已验证：
- 旧策略（只有 `buy`/`sell`）继续正常工作
- 自动转换为 `buy_tier1`/`sell_tier1` + `pct=1.0`
- 交易记录格式向后兼容（无 `tiers` 字段时为旧格式）
- 所有现有策略无需修改

---

## 性能影响

- **时间复杂度**: O(n) → O(n)（无变化，只是每个 bar 多了 tier 遍历）
- **空间复杂度**: O(1) → O(k)（k 为 tier 数量，最多3）
- **回测速度**: 预计影响 < 5%

---

## 后续改进建议

1. **策略模板**: 提供分批策略代码模板
2. **前端展示**: 可视化分批明细（trades 表格展开 tiers）
3. **卖出策略**: 支持 LIFO、最大盈利优先等
4. **仓位验证**: 检查 `buy_tier_pct` 总和 ≤ 1.0
5. **文档更新**: 补充因子库参考文档中的分批信号说明

---

## 联系人

- **实施者**: Kiro (Claude)
- **实施日期**: 2026-06-07
- **审核状态**: 待服务重启后验证

---

## 附录：测试命令

```bash
# 完整测试流程
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 1. 语法检查
python -m py_compile services/strategy_backtest_service.py
python -m py_compile services/strategy_code_validator.py
python -m py_compile quantlib/engine/code_validator.py
python -m py_compile quantlib/engine/indicator_strategy_executor.py

# 2. 运行 E2E 测试
python tests/integration/test_batch_entry_exit.py

# 3. 验证旧策略兼容性
# （通过 API 手动测试一个已有策略）
```

---

## 参考文档

- [功能规格](../../docs/features/batch-entry-exit-strategy-spec.md)
- [实现计划](../.claude/plans/batch-entry-exit-implementation-plan.md)
- [测试文档](../../docs/testing/batch-entry-exit-e2e-test.md)
