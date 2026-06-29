# V13虚拟账户持仓业务逻辑诊断报告

**生成时间**: 2026-06-29
**问题**: 账户计算错误，持仓数据不一致

---

## 📋 业务逻辑梳理

### 正确的业务流程

```
1. 交易发生
   ↓
2. 记录到 simulation_trades 表（交易记录）
   ↓
3. 更新内存 self.portfolio (SimulationTrader)
   ↓
4. 调用 upsert_position() 更新 simulation_positions 表
   ↓
5. 计算 total_value = cash + Σ(持仓市值)
   ↓
6. 调用 update_account() 更新 simulation_account 表
```

---

## 🚨 发现的问题

### 问题1: 持仓表数据不完整

**现象**:
- `simulation_trades` 表有9只股票的交易记录
- `simulation_positions` 表只有4只股票
- 缺失6月22日买入的4只股票：300657, 300131, 300790, 300632

**原因分析**:

```python
# simulation_trader.py 第177-184行
def _save_account_to_db(self):
    # ...
    # 保存持仓
    for symbol, pos in self.portfolio.items():  # ← 只保存 self.portfolio 中的
        self.repo.upsert_position(
            account_name='default',
            symbol=symbol,
            shares=pos['shares'],
            avg_price=pos['avg_price']
        )
```

**问题**: `self.portfolio` 只包含最近调仓的股票，历史持仓未包含在内

---

### 问题2: total_value 计算错误

**现象**:
- 数据库记录 total_value = ¥59,791.30
- 真实应该是 = ¥110,719.30

**原因分析**:

```python
# simulation_trader.py 第186-210行
def _calculate_total_value_from_portfolio(self):
    """从持仓计算总资产"""
    if not self.portfolio:
        return self.cash
    
    # 计算持仓市值
    portfolio_value = sum(
        self.portfolio[symbol]['shares'] * prices.get(symbol, ...)
        for symbol in self.portfolio  # ← 只计算 self.portfolio 中的
    )
    
    return self.cash + portfolio_value
```

**问题**: 只计算了 `self.portfolio` 中的持仓，忽略了历史持仓

---

### 问题3: 重复卖出BUG (300342)

**现象**:
- 只买入200股
- 却有4条卖出记录（800股）
- 导致做空600股

**待定位**: 需要查看调仓逻辑中的卖出代码

---

## 🔍 根本原因

### 核心问题: self.portfolio 不完整

```python
# self.portfolio 的数据来源

1. 启动时从数据库加载:
   self._load_account_from_db()  # 只加载 simulation_positions 表中的

2. 调仓时更新:
   rebalance() 方法中只更新本次调仓的股票

3. 保存时:
   _save_account_to_db() 只保存 self.portfolio 中的
```

**问题链**:
```
simulation_positions 表不完整
        ↓
self.portfolio 加载不完整
        ↓
_calculate_total_value_from_portfolio() 计算错误
        ↓
_save_account_to_db() 保存错误的 total_value
        ↓
数据库中 total_value 错误
```

---

## 💡 正确的业务逻辑

### 方案A: 基于交易记录计算（推荐）

**原则**: 交易记录是唯一真相来源

```python
def _get_real_positions_from_trades(self):
    """从交易记录计算真实持仓"""
    cursor = self.repo.session.connection().connection.cursor()
    
    cursor.execute("""
        SELECT 
            symbol,
            SUM(CASE WHEN action = 'BUY' THEN shares 
                     WHEN action = 'SELL' THEN -shares END) as shares,
            -- 加权平均成本计算
            SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
            SUM(CASE WHEN action = 'BUY' THEN shares END) as avg_price
        FROM quant.simulation_trades
        WHERE account_name = %s
        GROUP BY symbol
        HAVING SUM(CASE WHEN action = 'BUY' THEN shares 
                        WHEN action = 'SELL' THEN -shares END) != 0
    """, ('default',))
    
    positions = {}
    for row in cursor.fetchall():
        symbol, shares, avg_price = row
        positions[symbol] = {
            'shares': int(shares),
            'avg_price': float(avg_price)
        }
    
    cursor.close()
    return positions

def _calculate_total_value(self):
    """计算真实总资产"""
    # 1. 从交易记录获取真实持仓
    real_positions = self._get_real_positions_from_trades()
    
    # 2. 获取当前价格
    portfolio_value = 0
    for symbol, pos in real_positions.items():
        current_price = self._get_current_price(symbol) or pos['avg_price']
        portfolio_value += pos['shares'] * current_price
    
    # 3. 总资产 = 现金 + 持仓市值
    return self.cash + portfolio_value

def _save_account_to_db(self):
    """保存账户状态"""
    # 1. 从交易记录计算真实持仓
    real_positions = self._get_real_positions_from_trades()
    
    # 2. 更新所有持仓到数据库
    for symbol, pos in real_positions.items():
        current_price = self._get_current_price(symbol)
        self.repo.upsert_position(
            account_name='default',
            symbol=symbol,
            shares=pos['shares'],
            avg_price=pos['avg_price'],
            current_price=current_price
        )
    
    # 3. 删除已清仓的持仓
    # （shares = 0 的持仓）
    
    # 4. 计算真实总资产
    total_value = self._calculate_total_value()
    
    # 5. 更新账户
    cumulative_return = (total_value / self.config['initial_capital'] - 1)
    max_drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0
    
    self.repo.update_account(
        account_name='default',
        cash=self.cash,
        total_value=total_value,
        peak_value=self.peak_value,
        cumulative_return=cumulative_return,
        max_drawdown=max_drawdown,
        last_rebalance_date=self.last_rebalance_date
    )
```

**优势**:
- ✅ 交易记录是单一真相来源
- ✅ 不依赖 self.portfolio 的完整性
- ✅ 自动处理所有历史持仓
- ✅ 避免数据不一致

---

### 方案B: 修复 self.portfolio（不推荐）

每次都完整加载所有持仓到 self.portfolio

**问题**:
- ❌ self.portfolio 和数据库双重维护
- ❌ 容易出现数据不一致
- ❌ 依赖内存状态

---

## 🔧 修复步骤

### 步骤1: 修复 simulation_trader.py

**需要修改的方法**:
1. `_get_real_positions_from_trades()` - 新增
2. `_calculate_total_value_from_portfolio()` - 重命名为 `_calculate_total_value()`
3. `_save_account_to_db()` - 修改逻辑
4. `_load_account_from_db()` - 从交易记录加载

**伪代码**:
```python
class SimulationTrader:
    
    def _load_account_from_db(self):
        """从数据库加载账户"""
        account = self.repo.get_account(account_name='default')
        
        if account:
            self.cash = float(account.cash)
            self.peak_value = float(account.peak_value)
            self.last_rebalance_date = account.last_rebalance_date
            
            # 从交易记录加载真实持仓
            self.portfolio = self._get_real_positions_from_trades()
            
            logging.info(f"加载账户: {len(self.portfolio)}只持仓")
        else:
            # 初始化
            self.cash = self.config['initial_capital']
            self.peak_value = self.cash
            self.last_rebalance_date = None
            self.portfolio = {}
    
    def _get_real_positions_from_trades(self):
        """从交易记录计算真实持仓（单一真相来源）"""
        # SQL查询实现（见上）
        pass
    
    def _calculate_total_value(self):
        """计算总资产"""
        # 1. 从交易记录获取真实持仓
        real_positions = self._get_real_positions_from_trades()
        
        # 2. 计算市值
        portfolio_value = 0
        for symbol, pos in real_positions.items():
            price = self._get_current_price(symbol) or pos['avg_price']
            portfolio_value += pos['shares'] * price
        
        return self.cash + portfolio_value
    
    def _save_account_to_db(self):
        """保存账户状态"""
        # 1. 获取真实持仓
        real_positions = self._get_real_positions_from_trades()
        
        # 2. 同步所有持仓到数据库
        for symbol, pos in real_positions.items():
            current_price = self._get_current_price(symbol)
            self.repo.upsert_position(
                account_name='default',
                symbol=symbol,
                shares=pos['shares'],
                avg_price=pos['avg_price'],
                current_price=current_price
            )
        
        # 3. 删除已清仓的（可选）
        # TODO: 删除 shares = 0 的持仓记录
        
        # 4. 计算并更新账户
        total_value = self._calculate_total_value()
        cumulative_return = (total_value / self.config['initial_capital'] - 1)
        max_drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0
        
        self.repo.update_account(
            account_name='default',
            cash=self.cash,
            total_value=total_value,
            peak_value=self.peak_value,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
            last_rebalance_date=self.last_rebalance_date
        )
```

---

### 步骤2: 清理脏数据

```sql
-- 1. 删除300342的重复卖出记录（保留第一条）
DELETE FROM quant.simulation_trades
WHERE id IN (
    SELECT id FROM quant.simulation_trades
    WHERE account_name = 'default' 
        AND symbol = '300342' 
        AND action = 'SELL'
        AND trade_date = '2026-06-28'
    ORDER BY id
    OFFSET 1
);

-- 2. 从交易记录重建持仓表
DELETE FROM quant.simulation_positions WHERE account_name = 'default';

INSERT INTO quant.simulation_positions (
    account_name, symbol, shares, avg_price, 
    current_price, market_value, cost, profit, profit_rate
)
SELECT 
    'default' as account_name,
    symbol,
    SUM(CASE WHEN action = 'BUY' THEN shares 
             WHEN action = 'SELL' THEN -shares END) as shares,
    SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
    SUM(CASE WHEN action = 'BUY' THEN shares END) as avg_price,
    k.close as current_price,
    (SUM(CASE WHEN action = 'BUY' THEN shares 
              WHEN action = 'SELL' THEN -shares END) * k.close) as market_value,
    (SUM(CASE WHEN action = 'BUY' THEN shares 
              WHEN action = 'SELL' THEN -shares END) * 
     SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
     SUM(CASE WHEN action = 'BUY' THEN shares END)) as cost,
    (SUM(CASE WHEN action = 'BUY' THEN shares 
              WHEN action = 'SELL' THEN -shares END) * 
     (k.close - SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
                 SUM(CASE WHEN action = 'BUY' THEN shares END))) as profit,
    ((k.close - SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
                 SUM(CASE WHEN action = 'BUY' THEN shares END)) /
     (SUM(CASE WHEN action = 'BUY' THEN shares * filled_price END) / 
      SUM(CASE WHEN action = 'BUY' THEN shares END))) as profit_rate
FROM quant.simulation_trades t
LEFT JOIN LATERAL (
    SELECT close FROM quant.daily_klines 
    WHERE symbol = t.symbol 
    ORDER BY trade_date DESC LIMIT 1
) k ON true
WHERE t.account_name = 'default'
GROUP BY t.symbol, k.close
HAVING SUM(CASE WHEN action = 'BUY' THEN shares 
                WHEN action = 'SELL' THEN -shares END) != 0;

-- 3. 重新计算账户总资产
UPDATE quant.simulation_account
SET 
    total_value = (
        SELECT cash + COALESCE(SUM(market_value), 0)
        FROM quant.simulation_positions
        WHERE account_name = 'default'
    ),
    cumulative_return = (
        (SELECT cash + COALESCE(SUM(market_value), 0)
         FROM quant.simulation_positions
         WHERE account_name = 'default') / 100002.17 - 1
    )
WHERE account_name = 'default';
```

---

## ✅ 修复后的预期结果

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| simulation_positions 数量 | 4只 | 8只（去除做空的300342） |
| total_value | ¥59,791 | ¥110,719 |
| cumulative_return | -40.21% | +10.72% |
| 300342持仓 | -600股 | 0股 |

---

## 📋 待办清单

- [ ] 修改 `simulation_trader.py` 的持仓计算逻辑
- [ ] 添加 `_get_real_positions_from_trades()` 方法
- [ ] 修改 `_calculate_total_value()` 方法
- [ ] 修改 `_save_account_to_db()` 方法
- [ ] 修改 `_load_account_from_db()` 方法
- [ ] 执行SQL清理脏数据
- [ ] 重建持仓表
- [ ] 重新计算账户总资产
- [ ] 测试修复后的逻辑
- [ ] 定位300342重复卖出的BUG

---

**报告生成**: Claude (Kiro)
**生成时间**: 2026-06-29 12:30
