# 策略丰富度提升计划 (8.5 → 9.5)

**目标**: 将策略丰富度从8.5分提升到9.5分  
**时间**: 3-4个月  
**难度**: ⭐⭐⭐⭐ (困难)

---

## 📊 当前状态

### 现有策略 (35个)
- ✅ 技术指标策略 (18个): MA Cross, RSI, MACD, Bollinger等
- ✅ 基本面策略 (5个): PE/PB估值、ROE质量
- ✅ 机器学习策略 (3个): XGBoost、LightGBM
- ✅ 高级策略 (9个): 配对交易、网格交易、海龟交易

### 缺失策略
- ❌ 期权策略 (0个)
- ❌ 高频策略 (0个)
- ❌ 跨品种策略 (0个)

---

## 🎯 提升目标

### 新增策略类型

1. **期权策略** (10个) - 预计+0.3分
2. **高频策略** (8个) - 预计+0.4分
3. **跨品种策略** (7个) - 预计+0.3分

**总计**: 新增25个策略，从35个增加到60个

---

## 📋 实施计划

### Phase 1: 期权策略 (4-6周)

#### 1.1 基础期权策略 (2周)

**策略1: Delta中性策略**
```python
# quantsys-v2/quant/engine/options/delta_neutral_strategy.py

class DeltaNeutralStrategy(StrategyBase):
    """
    Delta中性策略：通过期权和标的资产对冲，保持Delta=0
    
    原理：
    - 买入/卖出期权
    - 同时持有标的资产对冲Delta
    - 赚取Gamma、Vega、Theta收益
    """
    
    def __init__(self):
        self.target_delta = 0  # 目标Delta
        self.rebalance_threshold = 0.1  # 再平衡阈值
    
    def calculate_portfolio_delta(self, positions):
        """计算组合Delta"""
        total_delta = 0
        for pos in positions:
            if pos.type == 'option':
                total_delta += pos.quantity * pos.delta
            else:  # 标的资产
                total_delta += pos.quantity
        return total_delta
    
    def rebalance(self, portfolio_delta, stock_price):
        """再平衡组合"""
        if abs(portfolio_delta) > self.rebalance_threshold:
            # 计算需要调整的标的数量
            hedge_quantity = -portfolio_delta
            return {
                'action': 'buy' if hedge_quantity > 0 else 'sell',
                'quantity': abs(hedge_quantity),
                'reason': f'Delta rebalance: {portfolio_delta:.2f}'
            }
        return None
    
    def generate_signal(self, klines, options_data):
        """生成交易信号"""
        # 1. 选择期权（ATM或略OTM）
        # 2. 计算期权Delta
        # 3. 计算对冲比例
        # 4. 生成交易信号
        pass
```

**策略2: 波动率套利策略**
```python
# quantsys-v2/quant/engine/options/volatility_arbitrage_strategy.py

class VolatilityArbitrageStrategy(StrategyBase):
    """
    波动率套利：隐含波动率vs历史波动率
    
    原理：
    - IV > HV: 卖出期权（做空波动率）
    - IV < HV: 买入期权（做多波动率）
    - Delta对冲保持中性
    """
    
    def calculate_historical_volatility(self, klines, window=20):
        """计算历史波动率"""
        returns = np.diff(np.log([k['close'] for k in klines]))
        hv = np.std(returns[-window:]) * np.sqrt(252)
        return hv
    
    def calculate_implied_volatility(self, option_price, S, K, T, r):
        """计算隐含波动率（牛顿法）"""
        from scipy.optimize import brentq
        
        def objective(sigma):
            return self.black_scholes(S, K, T, r, sigma) - option_price
        
        try:
            iv = brentq(objective, 0.01, 5.0)
            return iv
        except:
            return None
    
    def black_scholes(self, S, K, T, r, sigma):
        """Black-Scholes期权定价"""
        from scipy.stats import norm
        
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        call_price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        return call_price
    
    def generate_signal(self, klines, options_data):
        """生成交易信号"""
        hv = self.calculate_historical_volatility(klines)
        
        signals = []
        for option in options_data:
            iv = self.calculate_implied_volatility(
                option['price'], option['S'], option['K'], 
                option['T'], option['r']
            )
            
            if iv is None:
                continue
            
            # IV vs HV差异
            iv_hv_spread = iv - hv
            
            if iv_hv_spread > 0.05:  # IV高估
                signals.append({
                    'action': 'sell',
                    'symbol': option['symbol'],
                    'reason': f'IV={iv:.2%} > HV={hv:.2%}',
                    'delta_hedge': True
                })
            elif iv_hv_spread < -0.05:  # IV低估
                signals.append({
                    'action': 'buy',
                    'symbol': option['symbol'],
                    'reason': f'IV={iv:.2%} < HV={hv:.2%}',
                    'delta_hedge': True
                })
        
        return signals
```

**策略3: Gamma Scalping策略**
```python
# quantsys-v2/quant/engine/options/gamma_scalping_strategy.py

class GammaScalpingStrategy(StrategyBase):
    """
    Gamma Scalping：利用Gamma赚取价格波动收益
    
    原理：
    - 持有正Gamma头寸（买入期权）
    - 价格上涨时卖出标的，价格下跌时买入标的
    - 赚取波动收益，对冲Theta损失
    """
    
    def __init__(self):
        self.rebalance_threshold = 0.5  # 价格变动0.5%时再平衡
        self.last_hedge_price = None
    
    def calculate_gamma_pnl(self, gamma, price_move):
        """计算Gamma收益"""
        # Gamma P&L = 0.5 * Gamma * (ΔS)^2
        return 0.5 * gamma * (price_move ** 2)
    
    def should_rebalance(self, current_price):
        """判断是否需要再平衡"""
        if self.last_hedge_price is None:
            return True
        
        price_change_pct = abs(current_price - self.last_hedge_price) / self.last_hedge_price
        return price_change_pct >= self.rebalance_threshold / 100
    
    def generate_signal(self, klines, options_position):
        """生成交易信号"""
        current_price = klines[-1]['close']
        
        if not self.should_rebalance(current_price):
            return None
        
        # 计算当前Delta
        portfolio_delta = options_position['delta'] * options_position['quantity']
        
        # 对冲Delta
        hedge_quantity = -portfolio_delta
        
        self.last_hedge_price = current_price
        
        return {
            'action': 'buy' if hedge_quantity > 0 else 'sell',
            'quantity': abs(hedge_quantity),
            'price': current_price,
            'reason': f'Gamma scalping at {current_price:.2f}'
        }
```

#### 1.2 高级期权策略 (2周)

**策略4: Iron Condor策略**
```python
# quantsys-v2/quant/engine/options/iron_condor_strategy.py

class IronCondorStrategy(StrategyBase):
    """
    铁鹰式策略：卖出OTM看涨和看跌期权，同时买入更OTM的期权保护
    
    结构：
    - 卖出OTM Call (K3)
    - 买入更OTM Call (K4)
    - 卖出OTM Put (K2)
    - 买入更OTM Put (K1)
    
    适用场景：低波动率市场，预期价格在区间内波动
    """
    
    def __init__(self):
        self.profit_target = 0.5  # 50%最大收益时平仓
        self.stop_loss = 2.0  # 200%最大收益时止损
    
    def construct_iron_condor(self, S, options_chain):
        """构建铁鹰式组合"""
        # 选择期权
        # K1 < K2 < S < K3 < K4
        # 通常：K2 = S * 0.95, K3 = S * 1.05
        
        K1 = S * 0.90  # 买入Put
        K2 = S * 0.95  # 卖出Put
        K3 = S * 1.05  # 卖出Call
        K4 = S * 1.10  # 买入Call
        
        return {
            'long_put': {'strike': K1, 'quantity': 1},
            'short_put': {'strike': K2, 'quantity': -1},
            'short_call': {'strike': K3, 'quantity': -1},
            'long_call': {'strike': K4, 'quantity': 1}
        }
    
    def calculate_pnl(self, S_current, iron_condor, entry_premium):
        """计算当前盈亏"""
        # 计算每个期权的内在价值
        pnl = entry_premium  # 初始收到的权利金
        
        for leg, details in iron_condor.items():
            K = details['strike']
            qty = details['quantity']
            
            if 'call' in leg:
                intrinsic = max(0, S_current - K)
            else:  # put
                intrinsic = max(0, K - S_current)
            
            pnl -= intrinsic * qty
        
        return pnl
    
    def generate_signal(self, klines, options_chain):
        """生成交易信号"""
        S = klines[-1]['close']
        hv = self.calculate_historical_volatility(klines)
        
        # 只在低波动率环境下建仓
        if hv < 0.20:  # 历史波动率<20%
            iron_condor = self.construct_iron_condor(S, options_chain)
            return {
                'action': 'open_iron_condor',
                'structure': iron_condor,
                'reason': f'Low volatility: HV={hv:.2%}'
            }
        
        return None
```

**策略5: Calendar Spread策略**
```python
# quantsys-v2/quant/engine/options/calendar_spread_strategy.py

class CalendarSpreadStrategy(StrategyBase):
    """
    日历价差策略：卖出近月期权，买入远月期权
    
    原理：
    - 近月期权Theta衰减快
    - 远月期权Theta衰减慢
    - 赚取时间价值差异
    """
    
    def __init__(self):
        self.near_term_days = 30  # 近月期权到期天数
        self.far_term_days = 60   # 远月期权到期天数
    
    def select_options(self, S, options_chain):
        """选择期权"""
        # 选择ATM期权
        K = round(S / 5) * 5  # 四舍五入到最近的行权价
        
        near_term = self.find_option(options_chain, K, self.near_term_days)
        far_term = self.find_option(options_chain, K, self.far_term_days)
        
        return {
            'short': near_term,
            'long': far_term,
            'strike': K
        }
    
    def calculate_theta_decay(self, option, days_to_expiry):
        """计算Theta衰减"""
        # Theta ≈ -S * σ * φ(d1) / (2√T)
        # 简化计算
        theta_per_day = option['price'] * 0.01 * (30 / days_to_expiry)
        return theta_per_day
    
    def generate_signal(self, klines, options_chain):
        """生成交易信号"""
        S = klines[-1]['close']
        
        options = self.select_options(S, options_chain)
        
        # 计算Theta差异
        near_theta = self.calculate_theta_decay(options['short'], self.near_term_days)
        far_theta = self.calculate_theta_decay(options['long'], self.far_term_days)
        
        theta_advantage = near_theta - far_theta
        
        if theta_advantage > 0.5:  # Theta优势明显
            return {
                'action': 'open_calendar_spread',
                'short': options['short'],
                'long': options['long'],
                'theta_advantage': theta_advantage,
                'reason': f'Theta advantage: {theta_advantage:.2f}'
            }
        
        return None
```

#### 1.3 Greeks管理策略 (2周)

**策略6-10**: Vega交易、Theta收割、Rho对冲、Charm管理、Vanna交易

---

### Phase 2: 高频策略 (6-8周)

#### 2.1 基础设施准备 (2周)

**高频数据接入**
```python
# quantsys-v2/quant/adapters/hft_adapter.py

class HFTDataAdapter:
    """
    高频数据适配器
    
    功能：
    - Tick级数据接入
    - 订单簿数据（Level 2）
    - 逐笔成交数据
    """
    
    def __init__(self):
        self.ws_client = None
        self.tick_buffer = deque(maxlen=10000)
        self.orderbook_buffer = {}
    
    async def subscribe_tick_data(self, symbols):
        """订阅Tick数据"""
        import websocket
        
        self.ws_client = websocket.WebSocketApp(
            "wss://api.exchange.com/tick",
            on_message=self.on_tick_message,
            on_error=self.on_error
        )
        
        # 订阅消息
        subscribe_msg = {
            'action': 'subscribe',
            'symbols': symbols,
            'type': 'tick'
        }
        self.ws_client.send(json.dumps(subscribe_msg))
    
    def on_tick_message(self, ws, message):
        """处理Tick消息"""
        tick = json.loads(message)
        self.tick_buffer.append({
            'symbol': tick['symbol'],
            'price': tick['price'],
            'volume': tick['volume'],
            'timestamp': tick['timestamp'],
            'bid': tick['bid'],
            'ask': tick['ask']
        })
    
    async def subscribe_orderbook(self, symbols, depth=10):
        """订阅订单簿数据"""
        # Level 2数据：买卖盘口深度
        pass
    
    def get_latest_tick(self, symbol):
        """获取最新Tick"""
        for tick in reversed(self.tick_buffer):
            if tick['symbol'] == symbol:
                return tick
        return None
    
    def get_orderbook(self, symbol):
        """获取订单簿"""
        return self.orderbook_buffer.get(symbol)
```

**低延迟执行引擎**
```python
# quantsys-v2/quant/engine/hft_execution_engine.py

class HFTExecutionEngine:
    """
    高频执行引擎
    
    特性：
    - 微秒级延迟
    - 智能路由
    - 订单拆分
    """
    
    def __init__(self):
        self.order_queue = asyncio.Queue()
        self.execution_latency = []
    
    async def execute_order(self, order):
        """执行订单"""
        start_time = time.perf_counter()
        
        # 1. 订单验证
        if not self.validate_order(order):
            return {'status': 'rejected', 'reason': 'validation_failed'}
        
        # 2. 智能路由（选择最优交易所）
        exchange = self.select_best_exchange(order)
        
        # 3. 订单拆分（大单拆分为小单）
        child_orders = self.split_order(order)
        
        # 4. 并发执行
        results = await asyncio.gather(*[
            self.send_order(exchange, child_order)
            for child_order in child_orders
        ])
        
        # 5. 记录延迟
        latency = (time.perf_counter() - start_time) * 1000000  # 微秒
        self.execution_latency.append(latency)
        
        return {
            'status': 'filled',
            'latency_us': latency,
            'results': results
        }
    
    def select_best_exchange(self, order):
        """选择最优交易所"""
        # 考虑因素：
        # - 流动性
        # - 手续费
        # - 延迟
        pass
    
    def split_order(self, order, max_size=1000):
        """订单拆分"""
        quantity = order['quantity']
        num_splits = math.ceil(quantity / max_size)
        
        child_orders = []
        for i in range(num_splits):
            child_qty = min(max_size, quantity - i * max_size)
            child_orders.append({
                **order,
                'quantity': child_qty,
                'parent_id': order['id'],
                'child_id': f"{order['id']}-{i}"
            })
        
        return child_orders
```

#### 2.2 高频策略实现 (4-6周)

**策略1: 做市策略**
```python
# quantsys-v2/quant/engine/hft/market_making_strategy.py

class MarketMakingStrategy:
    """
    做市策略：提供流动性赚取买卖价差
    
    原理：
    - 同时挂买单和卖单
    - 赚取Bid-Ask Spread
    - 管理库存风险
    """
    
    def __init__(self):
        self.spread_bps = 5  # 5个基点价差
        self.max_inventory = 10000  # 最大库存
        self.inventory = 0
    
    def calculate_quotes(self, mid_price, volatility):
        """计算报价"""
        # 基础价差
        base_spread = mid_price * self.spread_bps / 10000
        
        # 波动率调整
        vol_adjustment = volatility * mid_price * 0.1
        
        # 库存调整（库存过多时降低卖价，提高买价）
        inventory_skew = (self.inventory / self.max_inventory) * base_spread
        
        bid = mid_price - base_spread/2 - vol_adjustment - inventory_skew
        ask = mid_price + base_spread/2 + vol_adjustment - inventory_skew
        
        return {'bid': bid, 'ask': ask}
    
    async def run(self, symbol):
        """运行做市策略"""
        while True:
            # 1. 获取市场数据
            tick = await self.get_latest_tick(symbol)
            mid_price = (tick['bid'] + tick['ask']) / 2
            volatility = self.calculate_short_term_volatility()
            
            # 2. 计算报价
            quotes = self.calculate_quotes(mid_price, volatility)
            
            # 3. 撤销旧订单
            await self.cancel_all_orders(symbol)
            
            # 4. 提交新订单
            await self.place_order(symbol, 'buy', quotes['bid'], 100)
            await self.place_order(symbol, 'sell', quotes['ask'], 100)
            
            # 5. 等待下一个Tick
            await asyncio.sleep(0.1)  # 100ms
```

**策略2: 统计套利（配对交易高频版）**
**策略3: 动量点火策略**
**策略4: 订单簿失衡策略**
**策略5-8**: 其他高频策略

---

### Phase 3: 跨品种策略 (4-6周)

#### 3.1 数据基础设施 (2周)

**多品种数据管理**
```python
# quantsys-v2/repositories/multi_asset_repository.py

class MultiAssetRepository:
    """
    多品种数据仓库
    
    支持：
    - 股票
    - 期货
    - 期权
    - 债券
    - 外汇
    """
    
    def get_correlated_assets(self, symbol, asset_class='all'):
        """获取相关品种"""
        query = """
            SELECT 
                a2.symbol,
                a2.asset_class,
                c.correlation,
                c.updated_at
            FROM asset_correlations c
            JOIN assets a1 ON c.asset1_id = a1.id
            JOIN assets a2 ON c.asset2_id = a2.id
            WHERE a1.symbol = %s
            AND c.correlation > 0.7
            ORDER BY c.correlation DESC
        """
        
        if asset_class != 'all':
            query += " AND a2.asset_class = %s"
            params = (symbol, asset_class)
        else:
            params = (symbol,)
        
        return self.db.execute(query, params)
```

#### 3.2 跨品种策略实现 (2-4周)

**策略1: 股指期货对冲策略**
```python
# quantsys-v2/quant/engine/cross_asset/index_futures_hedge_strategy.py

class IndexFuturesHedgeStrategy:
    """
    股指期货对冲策略
    
    原理：
    - 持有股票组合
    - 用股指期货对冲系统性风险
    - 赚取Alpha收益
    """
    
    def calculate_hedge_ratio(self, portfolio_beta, portfolio_value, futures_price, multiplier):
        """计算对冲比例"""
        # 对冲合约数 = (组合价值 * Beta) / (期货价格 * 合约乘数)
        contracts = (portfolio_value * portfolio_beta) / (futures_price * multiplier)
        return round(contracts)
    
    def generate_signal(self, portfolio, futures_data):
        """生成对冲信号"""
        # 1. 计算组合Beta
        portfolio_beta = self.calculate_portfolio_beta(portfolio)
        
        # 2. 计算对冲比例
        hedge_contracts = self.calculate_hedge_ratio(
            portfolio_beta,
            portfolio['value'],
            futures_data['price'],
            futures_data['multiplier']
        )
        
        # 3. 当前持仓
        current_contracts = portfolio.get('futures_position', 0)
        
        # 4. 调整信号
        adjustment = hedge_contracts - current_contracts
        
        if abs(adjustment) > 0:
            return {
                'action': 'sell' if adjustment < 0 else 'buy',
                'symbol': futures_data['symbol'],
                'quantity': abs(adjustment),
                'reason': f'Hedge adjustment: Beta={portfolio_beta:.2f}'
            }
        
        return None
```

**策略2-7**: 商品期货套利、跨市场套利、可转债套利、ETF套利、跨境套利、利率期限套利

---

## 📊 实施时间表

| 阶段 | 任务 | 时间 | 人力 |
|------|------|------|------|
| Phase 1 | 期权策略 (10个) | 4-6周 | 2人 |
| Phase 2 | 高频策略 (8个) | 6-8周 | 3人 |
| Phase 3 | 跨品种策略 (7个) | 4-6周 | 2人 |
| **总计** | **25个新策略** | **14-20周** | **2-3人** |

---

## 💰 成本估算

### 人力成本
- 量化研究员 x2: ¥80,000/月 x 5个月 = ¥800,000
- 高频开发工程师 x1: ¥100,000/月 x 2个月 = ¥200,000
- **总计**: ¥1,000,000

### 基础设施成本
- 高频数据订阅: ¥50,000/月 x 5个月 = ¥250,000
- 低延迟服务器: ¥30,000/月 x 5个月 = ¥150,000
- 期权数据接口: ¥20,000/月 x 5个月 = ¥100,000
- **总计**: ¥500,000

### 总成本: ¥1,500,000

---

## 🎯 预期收益

### 评分提升
- 策略丰富度: 8.5 → 9.5 (+1.0分)
- 综合评分: 9.08 → 9.28 (+0.20分)

### 业务收益
- 策略容量提升: 35个 → 60个 (+71%)
- 覆盖品种: 股票 → 股票+期权+期货+跨品种
- 预期年化收益提升: +5-10%

---

## ⚠️ 风险与挑战

### 技术风险
1. **高频策略延迟**: 需要微秒级执行，技术难度高
2. **期权定价复杂**: Greeks计算、隐含波动率求解
3. **跨品种数据同步**: 多市场数据一致性

### 市场风险
1. **期权流动性**: 部分期权合约流动性差
2. **高频竞争**: 高频市场竞争激烈，利润空间小
3. **跨品种相关性**: 相关性可能突变

### 合规风险
1. **高频监管**: 部分高频策略可能受监管限制
2. **跨境交易**: 跨境套利涉及外汇管制
3. **期权资格**: 期权交易需要特殊资格

---

## ✅ 成功标准

1. **策略数量**: 新增25个策略，总计60个
2. **测试覆盖**: 每个策略测试覆盖率>90%
3. **回测表现**: 每个策略夏普比率>1.5
4. **实盘验证**: 至少5个策略通过实盘验证
5. **评分达标**: 策略丰富度评分达到9.5分

---

**文档版本**: v1.0  
**创建日期**: 2026-05-21  
**负责人**: 量化研究团队
