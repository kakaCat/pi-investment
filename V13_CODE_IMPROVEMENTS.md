# V13量化交易系统代码改进报告

**日期**: 2026-06-29
**改进目标**: 修复数据同步问题，防止重复交易，增强数据一致性

---

## 🎯 改进概览

### 改进前的问题

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| 持仓内存与数据库不同步 | 持仓表缺失4只股票 | 🔴 严重 |
| 没有持仓数量检查 | 300342重复卖出4次 | 🔴 严重 |
| 账户计算依赖不完整数据 | total_value错误 | 🔴 严重 |
| 缺少数据一致性校验 | 问题发生后才发现 | 🟡 重要 |
| 缺少每日快照 | 无法绘制收益曲线 | 🟡 重要 |

### 改进后的效果

✅ **单一数据源**：所有持仓从 `simulation_trades` 计算
✅ **自动修复**：调仓前自动检查并修复数据不一致
✅ **防止重复**：卖出前检查持仓数量
✅ **每日快照**：自动记录到 `account_balance` 表
✅ **日志告警**：数据异常时自动告警

---

## 📝 代码改进详情

### 1. 添加"从交易记录重建持仓"方法

**文件**: `quantsys-v2/live_trading/simulation_trader.py`

**新增方法**: `_rebuild_portfolio_from_trades()`

```python
def _rebuild_portfolio_from_trades(self):
    """从交易记录重建持仓（单一数据源）"""
    query = '''
        SELECT
            symbol,
            SUM(CASE WHEN action = 'BUY' THEN shares
                     WHEN action = 'SELL' THEN -shares
                     ELSE 0 END) as total_shares,
            SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) /
            NULLIF(SUM(CASE WHEN action = 'BUY' THEN shares END), 0) as avg_price
        FROM quant.simulation_trades
        WHERE account_name = 'default'
        GROUP BY symbol
        HAVING SUM(...) > 0
    '''
    # 返回真实持仓
```

**作用**：
- ✅ 从交易记录汇总计算真实持仓
- ✅ 避免依赖可能不完整的持仓表
- ✅ 确保数据的单一来源（simulation_trades）

---

### 2. 修改加载账户逻辑

**修改**: `_load_account_from_db()`

**改进前**：
```python
# 从持仓表加载（可能不完整）
positions = self.repo.get_all_positions()
for pos in positions:
    self.portfolio[pos.symbol] = {...}
```

**改进后**：
```python
# ✅ 从交易记录重建持仓
self.portfolio = self._rebuild_portfolio_from_trades()

# 验证一致性
db_count = len(self.repo.get_all_positions())
real_count = len(self.portfolio)

if db_count != real_count:
    logging.warning(f"⚠️ 持仓不一致: 数据库{db_count}只 vs 交易记录{real_count}只")
```

**作用**：
- ✅ 启动时从交易记录重建持仓
- ✅ 自动检测数据不一致
- ✅ 记录警告日志

---

### 3. 修改保存账户逻辑

**修改**: `_save_account_to_db()`

**改进前**：
```python
# 只保存内存中的持仓（可能不完整）
for symbol, pos in self.portfolio.items():
    self.repo.upsert_position(...)
```

**改进后**：
```python
# ✅ 先从交易记录重建持仓
self.portfolio = self._rebuild_portfolio_from_trades()

# ✅ 清空持仓表
self.repo.clear_all_positions('default')

# ✅ 重建持仓表
for symbol, pos in self.portfolio.items():
    self.repo.upsert_position(...)

# ✅ 保存每日快照
self._save_daily_snapshot(total_value, cumulative_return)
```

**作用**：
- ✅ 每次保存前重建持仓，确保一致性
- ✅ 清空旧数据，避免残留
- ✅ 同时保存每日快照

---

### 4. 添加防重复卖出检查

**修改**: `_execute_trades_with_risk_control()`

**改进前**：
```python
for symbol in list(self.portfolio.keys()):
    if symbol not in target_symbols_set:
        shares = self.portfolio[symbol]['shares']
        # 直接卖出，没有检查
        trade = self.broker.sell(symbol, shares, price)
```

**改进后**：
```python
for symbol in list(self.portfolio.keys()):
    if symbol not in target_symbols_set:
        shares = self.portfolio[symbol]['shares']
        
        # ✅ 防止重复卖出：检查持仓数量
        if shares <= 0:
            logging.warning(f"跳过 {symbol}: 持仓数量={shares}，无需卖出")
            del self.portfolio[symbol]
            continue
        
        trade = self.broker.sell(symbol, shares, price)
```

**作用**：
- ✅ 卖出前检查持仓数量
- ✅ 如果已经没有持仓，跳过卖出
- ✅ 记录警告日志

---

### 5. 添加数据一致性检查

**新增方法**: `_validate_data_consistency()`

```python
def _validate_data_consistency(self):
    """调仓前数据一致性检查"""
    # 1. 从交易记录计算真实持仓
    real_portfolio = self._rebuild_portfolio_from_trades()
    
    # 2. 检查数据库持仓表
    db_symbols = {pos.symbol for pos in self.repo.get_all_positions()}
    
    # 3. 对比
    real_symbols = set(real_portfolio.keys())
    missing = real_symbols - db_symbols
    extra = db_symbols - real_symbols
    
    # 4. 自动修复
    if missing or extra:
        logging.warning(f"⚠️ 数据不一致，自动修复中...")
        self.repo.clear_all_positions('default')
        for symbol, pos in real_portfolio.items():
            self.repo.upsert_position(...)
        logging.info(f"✅ 已自动修复持仓表")
```

**调用位置**: `rebalance()` 方法开头

**作用**：
- ✅ 每次调仓前自动检查数据一致性
- ✅ 发现不一致自动修复
- ✅ 防止错误累积

---

### 6. 添加每日快照功能

**新增方法**: `_save_daily_snapshot()`

```python
def _save_daily_snapshot(self, total_value: float, cumulative_return: float):
    """保存每日账户快照到 account_balance 表"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 检查今天是否已有记录
    if exists:
        # 更新
        UPDATE quant.account_balance SET ...
    else:
        # 插入
        INSERT INTO quant.account_balance ...
```

**作用**：
- ✅ 每次保存账户时自动记录快照
- ✅ 支持绘制收益曲线
- ✅ 用于回溯分析

---

### 7. 添加清空持仓方法

**文件**: `quantsys-v2/adapters/outbound/repositories/simulation_repository.py`

**新增方法**: `clear_all_positions()`

```python
def clear_all_positions(self, account_name: str) -> bool:
    """清空账户所有持仓"""
    deleted = self.session.query(SimulationPosition).filter_by(
        account_name=account_name
    ).delete()
    self.session.commit()
    logger.info(f"Cleared {deleted} positions for account {account_name}")
    return True
```

**作用**：
- ✅ 批量清空持仓表
- ✅ 用于重建持仓前清理
- ✅ 记录删除数量

---

## 🔄 数据流改进对比

### 改进前

```
启动 → 从持仓表加载（不完整）→ 内存 self.portfolio（不完整）
       ↓
调仓 → 卖出/买入 → 更新 self.portfolio
       ↓
保存 → 只保存 self.portfolio（不完整）→ 持仓表缺失数据
       ↓
账户计算 → 基于不完整的 self.portfolio → total_value 错误
```

**问题**：持仓表和内存不同步，数据越来越不一致

---

### 改进后

```
启动 → 从交易记录重建 → self.portfolio（完整）
       ↓ 验证一致性
       ↓
调仓前 → 数据一致性检查 → 自动修复不一致
       ↓
卖出 → 检查 shares > 0 → 防止重复卖出
       ↓
保存前 → 从交易记录重建 → 清空持仓表 → 重建持仓表
       ↓
账户计算 → 基于完整的持仓 → total_value 正确
       ↓
保存快照 → account_balance 表 → 可绘制收益曲线
```

**优势**：单一数据源，自动修复，数据始终一致

---

## 📊 关键改进指标

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 数据源 | 多个（持仓表+内存） | 单一（交易记录） |
| 持仓准确性 | 50%（4/8只） | 100%（8/8只） |
| 自动修复 | ❌ 无 | ✅ 有 |
| 重复卖出保护 | ❌ 无 | ✅ 有 |
| 每日快照 | ❌ 无 | ✅ 有 |
| 数据校验 | ❌ 无 | ✅ 每次调仓 |

---

## 🧪 测试验证

### 测试场景1：启动时持仓不一致

**预期**：
1. 检测到持仓表只有4只，但交易记录显示8只
2. 记录警告日志
3. 从交易记录加载完整的8只持仓

**验证**：查看启动日志是否有 `⚠️ 持仓不一致` 警告

---

### 测试场景2：调仓前自动修复

**预期**：
1. 调仓前检查数据一致性
2. 发现持仓表缺失4只股票
3. 自动清空并重建持仓表
4. 记录 `✅ 已自动修复持仓表`

**验证**：查看调仓日志是否有自动修复记录

---

### 测试场景3：防止重复卖出

**预期**：
1. 尝试卖出持仓数量≤0的股票
2. 跳过卖出，记录警告
3. 不再产生交易记录

**验证**：
- 检查日志是否有 `跳过 XXX: 持仓数量=0`
- 检查交易记录表没有重复卖出

---

### 测试场景4：每日快照

**预期**：
1. 每次保存账户时自动保存快照
2. 记录到 `account_balance` 表
3. 可以查询历史收益曲线

**验证**：
```sql
SELECT date, total_value, cumulative_return
FROM quant.account_balance
WHERE account_name = 'default'
ORDER BY date;
```

---

## 🚀 执行步骤

### 1. 先修复历史数据

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
./scripts/fix_simulation_data.sh
```

**修复内容**：
- 删除300342重复卖出记录
- 重建持仓表（添加缺失的4只股票）
- 重新计算账户total_value

---

### 2. 验证代码改进

```bash
# 启动V13交易
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python live_trading/simulation_trader.py
```

**观察日志**：
- `从交易记录重建持仓: X只股票`
- `数据一致性检查通过`
- `保存每日快照: 2026-06-29`

---

### 3. 验证数据修复结果

```sql
-- 检查持仓表
SELECT symbol, shares, avg_price
FROM quant.simulation_positions
WHERE account_name = 'default';
-- 应该有8只股票

-- 检查账户状态
SELECT 
    ROUND(cash::numeric, 2) as 现金,
    ROUND(total_value::numeric, 2) as 总资产,
    ROUND((cumulative_return * 100)::numeric, 2) as 收益率
FROM quant.simulation_account
WHERE account_name = 'default';
-- 总资产应该是 ¥110,719

-- 检查每日快照
SELECT date, total_value, cumulative_return
FROM quant.account_balance
WHERE account_name = 'default'
ORDER BY date DESC LIMIT 7;
-- 应该有每日记录
```

---

## 📈 预期改进效果

### 数据准确性

- ✅ 持仓表始终与交易记录一致
- ✅ total_value 计算准确
- ✅ cumulative_return 正确反映真实收益

### 系统稳定性

- ✅ 不再出现重复卖出bug
- ✅ 自动修复数据不一致
- ✅ 错误自动告警

### 可观测性

- ✅ 每日快照支持绘制收益曲线
- ✅ 数据异常自动记录日志
- ✅ 便于回溯分析

---

## 🎯 后续优化建议

### 短期（本周）

1. **运行完整2周观察期**
   - 验证代码改进效果
   - 收集完整数据

2. **添加单元测试**
   - 测试 `_rebuild_portfolio_from_trades()`
   - 测试 `_validate_data_consistency()`

3. **监控日志**
   - 关注是否有数据不一致警告
   - 关注是否有重复卖出

### 中期（下周）

4. **添加价格异常检查**
   - 涨停/跌停检查
   - 停牌检查
   - 价格剧烈波动告警

5. **优化风险检查**
   - 每日盘中风险检查（不仅调仓时）
   - 流动性检查
   - 集中度风险预警

6. **完善异常处理**
   - 数据库写入失败回滚
   - 网络请求失败重试
   - 模型预测失败降级

### 长期（下月）

7. **性能监控**
   - 添加性能指标计算（夏普比率、索提诺比率）
   - 绘制收益曲线
   - 生成完整回测报告

8. **全量ORM迁移**
   - 迁移所有Repository到ORM
   - 统一数据访问层
   - 提高代码可维护性

---

## ✅ 改进总结

**核心原则**：单一数据源 + 自动修复 + 防御性编程

**关键改进**：
1. ✅ 所有持仓从 `simulation_trades` 计算
2. ✅ 每次调仓前自动检查并修复不一致
3. ✅ 卖出前检查持仓数量
4. ✅ 每日自动保存快照
5. ✅ 异常情况自动告警

**预期效果**：
- 数据准确性：从50%提升到100%
- 系统稳定性：不再出现重复交易bug
- 可维护性：问题自动发现、自动修复

---

**报告生成**: Claude (Kiro)  
**生成时间**: 2026-06-29
**改进版本**: V13.1
