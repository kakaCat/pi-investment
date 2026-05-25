# 机会雷达实时扫描功能设计文档

**日期**: 2026-05-24  
**作者**: AI Assistant  
**状态**: Draft

## 项目概述

重构"机会雷达"页面的后端扫描逻辑，从基于历史信号表查询改为实时计算模式，支持用户自定义技术指标和基本面条件的动态筛选。

### 目标

- 实时扫描股票池（自选股 + 热门股票池约400只）
- 根据用户勾选的技术指标和基本面条件动态计算评分
- 提供技术面、基本面、资金面三维评分
- 响应时间控制在 5-6 秒内

## 问题分析

### 现有实现的问题

1. **技术面和基本面筛选条件未实现**
   - 位置: `api/server.py:1101-1102`
   - 问题: 接收了 `technical` 和 `fundamental` 参数但未使用
   - 影响: 前端勾选的筛选条件（RSI超卖、MACD金叉、PE<30等）完全无效

2. **数据来源错误**
   - 位置: `api/server.py:1130-1134`
   - 问题: 从已有信号表查询最近7天信号，而非实时计算
   - 影响: 如果信号表为空，扫描结果为空；无法根据用户选择的指标动态筛选

3. **股票范围限制**
   - 位置: `api/server.py:1117`
   - 问题: 无自选股时只扫描200只股票
   - 影响: 无法覆盖全市场热门股票

4. **评分计算简化**
   - 位置: `api/server.py:128-129`
   - 问题: 综合评分直接用 `confidence * 100`，技术面/基本面/资金面评分从可能为空的 `indicators` JSON读取
   - 影响: 评分不准确，无法反映真实的技术/基本面状况

5. **风险等级筛选逻辑错误**
   - 位置: `api/server.py:1146`
   - 问题: 使用 `==` 精确匹配，应该用 `<=` 最大风险等级筛选
   - 影响: 用户选择"中风险"时，低风险机会被过滤掉

## 设计决策

### 1. 扫描范围
**决策**: 自选股 + 热门股票池（沪深300 + 创业板50 + 科创50）

**理由**:
- 自选股是用户关注的核心标的
- 热门股票池覆盖市场主流标的（约400只）
- 避免全市场扫描（5000+只）导致性能问题

### 2. 数据窗口
**决策**: 使用120天K线数据

**理由**:
- 满足常用技术指标计算需求（MA60、MACD等）
- 平衡数据量和计算精度
- 与现有因子计算逻辑一致

### 3. 基本面数据来源
**决策**: 从数据库读取，没有则跳过

**理由**:
- 避免实时调用外部API导致超时
- 基本面数据更新频率低（季度级别）
- 没有数据时使用中性评分（50分）

### 4. 综合评分算法
**决策**: 加权平均（技术面50% + 基本面30% + 资金面20%）

**理由**:
- 技术面权重最高，符合短期交易逻辑
- 基本面作为辅助参考
- 资金面反映市场情绪

### 5. 性能优化策略
**决策**: 批量查询 + 并行计算（10线程）

**理由**:
- 批量查询减少数据库往返次数
- 并行计算充分利用多核CPU
- 10线程平衡性能和资源消耗

### 6. 资金面数据
**决策**: 使用成交量指标替代真实资金流数据

**理由**:
- 真实资金流数据需要Level-2行情（成本高）
- 成交量指标可以反映资金活跃度
- 与现有数据源兼容

### 7. 热门股票池定义
**决策**: 沪深300 + 创业板50 + 科创50

**理由**:
- 覆盖主板、创业板、科创板三大市场
- 约400只股票，扫描时间可控
- 流动性好，适合短期交易

## 整体架构

### 模块划分

```
┌─────────────────────────────────────────────────────────────┐
│                    /api/signals/scan                        │
│                   (Flask API Endpoint)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  扫描协调器 (Scan Coordinator)               │
│  - 解析用户筛选条件                                          │
│  - 获取股票列表（自选股 + 热门股票池）                       │
│  - 调用评分引擎                                              │
│  - 应用筛选和排序                                            │
└────────────┬───────────────────────────┬────────────────────┘
             │                           │
             ▼                           ▼
┌────────────────────────┐  ┌───────────────────────────────┐
│  股票列表获取器         │  │    评分引擎                    │
│  (Stock List Fetcher)  │  │  (Scoring Engine)             │
│                        │  │                               │
│  - 查询自选股          │  │  - 批量查询K线数据             │
│  - 查询热门股票池      │  │  - 并行计算技术指标            │
│  - 去重合并            │  │  - 查询基本面数据              │
│                        │  │  - 计算三维评分                │
└────────────────────────┘  └───────────┬───────────────────┘
                                        │
                                        ▼
                            ┌───────────────────────────┐
                            │   筛选器 (Filter)          │
                            │  - 风险等级筛选            │
                            │  - 评分阈值筛选            │
                            │  - 排序（按综合评分）      │
                            └───────────────────────────┘
```

### 数据流

1. **输入**: 用户筛选条件（技术指标、基本面条件、风险等级）
2. **股票列表获取**: 自选股 + 热门股票池（去重）
3. **批量数据查询**: 一次性查询所有股票的120天K线数据
4. **并行评分**: 10个线程并行处理每只股票
5. **筛选和排序**: 应用风险等级筛选，按综合评分降序排序
6. **输出**: Opportunity 对象列表

## 评分算法

### 技术面评分（0-100分）

基于用户勾选的技术指标，每个满足的条件加分：

| 条件 | 判断逻辑 | 分值 |
|------|---------|------|
| RSI超卖 | RSI < 30 | +25 |
| MACD金叉 | MACD > Signal 且前一天 MACD < Signal | +25 |
| 突破布林带上轨 | 收盘价 > 布林带上轨 | +25 |
| 成交量放大 | 今日成交量 / 5日均量 > 2 | +25 |

**特殊情况**: 如果用户没有勾选任何技术指标，则技术面评分为 50 分（中性）。

### 基本面评分（0-100分）

基于数据库中的基本面数据，每个满足的条件加分：

| 条件 | 判断逻辑 | 分值 |
|------|---------|------|
| 低估值 | PE < 30 | +25 |
| 高盈利能力 | ROE > 15% | +25 |
| 高毛利率 | 毛利率 > 30% | +25 |
| 低负债 | 负债率 < 50% | +25 |

**特殊情况**: 如果数据库中没有基本面数据，则基本面评分为 50 分（中性）。

### 资金面评分（0-100分）

基于成交量指标（替代真实资金流数据）：

| 条件 | 判断逻辑 | 分值 |
|------|---------|------|
| 成交量放大 | 今日成交量 / 5日均量 > 1.5 | +25 |
| 量能连续递增 | 成交量连续3天递增 | +25 |
| 超过长期均量 | 今日成交量 > 20日均量 | +25 |
| 量能趋势向上 | 5日均量 > 20日均量 | +25 |

### 综合评分

```
综合评分 = 技术面评分 × 0.5 + 基本面评分 × 0.3 + 资金面评分 × 0.2
```

### 置信度和风险等级

- **置信度** = 综合评分 / 100（0-1之间）
- **风险等级**:
  - 综合评分 >= 70: 低风险
  - 综合评分 >= 50: 中风险
  - 综合评分 < 50: 高风险

## 技术实现

### 1. 新增服务类

#### StockPoolService

**文件**: `quantsys-v2/services/stock_pool_service.py`

```python
class StockPoolService:
    """热门股票池服务"""
    
    def __init__(self, stock_repo: StockRepository):
        self.stock_repo = stock_repo
    
    def get_hot_stocks(self) -> List[str]:
        """获取热门股票池（沪深300 + 创业板50 + 科创50）
        
        策略：
        1. 优先从数据库 index_components 表查询
        2. 如果数据库为空，使用硬编码的指数成分股列表
        
        Returns:
            股票代码列表
        """
        try:
            # 尝试从数据库查询
            components = self.stock_repo.get_index_components([
                '000300.SH',  # 沪深300
                '399006.SZ',  # 创业板指
                '000688.SH'   # 科创50
            ])
            
            if components:
                return components
            
            # 降级：使用硬编码列表（需要定期更新）
            logger.warning("数据库中无指数成分股数据，使用硬编码列表")
            return self._get_fallback_hot_stocks()
        
        except Exception as e:
            logger.error(f"获取热门股票池失败: {e}")
            return self._get_fallback_hot_stocks()
    
    def _get_fallback_hot_stocks(self) -> List[str]:
        """降级方案：硬编码的热门股票列表
        
        注意：此列表需要定期更新（建议每季度）
        """
        # 示例：部分沪深300成分股
        return [
            '600519.SH',  # 贵州茅台
            '600036.SH',  # 招商银行
            '601318.SH',  # 中国平安
            # ... 更多股票
        ]
```

#### OpportunityScoringService

**文件**: `quantsys-v2/services/opportunity_scoring_service.py`

```python
class OpportunityScoringService:
    """机会评分引擎"""
    
    def __init__(
        self,
        kline_repo: KlineRepository,
        stock_repo: StockRepository,
        factor_registry: FactorRegistry
    ):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_registry = factor_registry
    
    def score_stocks(
        self, 
        symbols: List[str],
        filters: Dict
    ) -> List[Dict]:
        """批量评分股票
        
        Args:
            symbols: 股票代码列表
            filters: 筛选条件 {
                'technical': ['rsi_oversold', 'macd_golden_cross', ...],
                'fundamental': ['pe_low', 'roe_high', ...]
            }
        
        Returns:
            Opportunity 对象列表
        """
        # 1. 批量查询 K 线（120天）
        klines_map = self._batch_fetch_klines(symbols, days=120)
        
        # 2. 使用 ThreadPoolExecutor 并行处理每只股票
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    self._score_single_stock, 
                    symbol, 
                    klines_map.get(symbol, []), 
                    filters
                )
                for symbol in symbols
            ]
            results = [f.result() for f in futures if f.result() is not None]
        
        return results
    
    def _score_single_stock(
        self, 
        symbol: str, 
        klines: List[Dict], 
        filters: Dict
    ) -> Optional[Dict]:
        """评分单只股票
        
        Returns:
            Opportunity 对象，如果计算失败返回 None
        """
        try:
            # 1. 检查数据充足性
            if len(klines) < 30:
                logger.warning(f"{symbol}: K线数据不足 ({len(klines)}天)")
                return None
            
            # 2. 使用 FactorRegistry 计算技术指标
            factors = self.factor_registry.calculate_factors(klines)
            
            # 3. 查询基本面数据
            fundamental = self.stock_repo.get_fundamental(symbol)
            
            # 4. 计算三维评分
            tech_score = self._calculate_technical_score(factors, filters['technical'])
            fund_score = self._calculate_fundamental_score(fundamental, filters['fundamental'])
            capital_score = self._calculate_capital_score(factors)
            
            # 5. 计算综合评分
            total_score = tech_score * 0.5 + fund_score * 0.3 + capital_score * 0.2
            
            # 6. 生成 Opportunity 对象
            return {
                'symbol': symbol,
                'name': self.stock_repo.get_name(symbol),
                'score': round(total_score),
                'technical_score': round(tech_score),
                'fundamental_score': round(fund_score),
                'capital_score': round(capital_score),
                'confidence': total_score / 100,
                'risk_level': self._calculate_risk_level(total_score),
                'signal_type': 'buy',  # 默认买入信号
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"{symbol}: 评分失败 - {e}")
            return None
    
    def _calculate_technical_score(
        self, 
        factors: Dict, 
        conditions: List[str]
    ) -> float:
        """计算技术面评分"""
        if not conditions:
            return 50.0  # 中性评分
        
        score = 0.0
        for condition in conditions:
            if condition == 'rsi_oversold' and factors.get('rsi', 100) < 30:
                score += 25
            elif condition == 'macd_golden_cross':
                # 检查 MACD 金叉
                if self._is_macd_golden_cross(factors):
                    score += 25
            elif condition == 'bollinger_breakout':
                # 检查突破布林带上轨
                if factors.get('close', 0) > factors.get('boll_upper', float('inf')):
                    score += 25
            elif condition == 'volume_surge':
                # 检查成交量放大
                if factors.get('volume_ratio_5d', 0) > 2:
                    score += 25
        
        return min(score, 100.0)
    
    def _calculate_fundamental_score(
        self, 
        fundamental: Optional[Dict], 
        conditions: List[str]
    ) -> float:
        """计算基本面评分"""
        if not fundamental:
            return 50.0  # 中性评分
        
        score = 0.0
        for condition in conditions:
            if condition == 'pe_low' and fundamental.get('pe', float('inf')) < 30:
                score += 25
            elif condition == 'roe_high' and fundamental.get('roe', 0) > 15:
                score += 25
            elif condition == 'gross_margin_high' and fundamental.get('gross_margin', 0) > 30:
                score += 25
            elif condition == 'debt_ratio_low' and fundamental.get('debt_ratio', 100) < 50:
                score += 25
        
        return min(score, 100.0)
    
    def _calculate_capital_score(self, factors: Dict) -> float:
        """计算资金面评分（基于成交量指标）"""
        score = 0.0
        
        # 成交量放大 > 1.5倍
        if factors.get('volume_ratio_5d', 0) > 1.5:
            score += 25
        
        # 成交量连续3天递增
        if self._is_volume_increasing(factors, days=3):
            score += 25
        
        # 今日成交量 > 20日均量
        if factors.get('volume', 0) > factors.get('volume_ma20', float('inf')):
            score += 25
        
        # 5日均量 > 20日均量
        if factors.get('volume_ma5', 0) > factors.get('volume_ma20', float('inf')):
            score += 25
        
        return min(score, 100.0)
    
    def _calculate_risk_level(self, score: float) -> str:
        """计算风险等级"""
        if score >= 70:
            return 'low'
        elif score >= 50:
            return 'medium'
        else:
            return 'high'
    
    def _is_macd_golden_cross(self, factors: Dict) -> bool:
        """判断MACD金叉
        
        金叉条件：
        1. 当前 MACD > Signal
        2. 前一天 MACD < Signal
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        macd_prev = factors.get('macd_prev', 0)
        signal_prev = factors.get('macd_signal_prev', 0)
        
        return macd > signal and macd_prev < signal_prev
    
    def _is_volume_increasing(self, factors: Dict, days: int = 3) -> bool:
        """判断成交量连续递增
        
        Args:
            factors: 因子字典（需包含最近N天的成交量数据）
            days: 连续递增天数
        
        Returns:
            True 如果成交量连续递增
        """
        volumes = factors.get('volume_history', [])
        if len(volumes) < days:
            return False
        
        # 检查最近N天是否连续递增
        for i in range(len(volumes) - days + 1, len(volumes)):
            if volumes[i] <= volumes[i - 1]:
                return False
        
        return True
    
    def _batch_fetch_klines(self, symbols: List[str], days: int) -> Dict[str, List[Dict]]:
        """批量查询K线数据
        
        Args:
            symbols: 股票代码列表
            days: 查询天数
        
        Returns:
            {symbol: [kline_data]}
        """
        return self.kline_repo.batch_get_recent_klines(symbols, days)
```

### 2. 修改现有端点

**文件**: `quantsys-v2/api/server.py`

修改 `scan_signals` 函数（第1086行）：

```python
@app.route('/api/signals/scan', methods=['POST'])
def scan_signals():
    """扫描交易机会（实时计算模式）"""
    try:
        data = request.get_json()
        
        # 解析筛选条件
        technical_filters = data.get('technical', [])
        fundamental_filters = data.get('fundamental', [])
        risk_level = data.get('riskLevel', 'high')
        
        # 1. 获取股票列表
        watchlist = data.get('watchlist', [])
        hot_stocks = stock_pool_service.get_hot_stocks()
        symbols = list(set(watchlist + hot_stocks))  # 去重
        
        # 2. 调用评分引擎
        opportunities = scoring_service.score_stocks(
            symbols=symbols,
            filters={
                'technical': technical_filters,
                'fundamental': fundamental_filters
            }
        )
        
        # 3. 应用风险等级筛选
        risk_level_map = {'low': 1, 'medium': 2, 'high': 3}
        max_risk = risk_level_map.get(risk_level, 3)
        filtered = [
            opp for opp in opportunities
            if risk_level_map.get(opp['risk_level'], 3) <= max_risk
        ]
        
        # 4. 排序（按综合评分降序）
        sorted_opps = sorted(filtered, key=lambda x: x['score'], reverse=True)
        
        return jsonify({
            'opportunities': sorted_opps,
            'total': len(sorted_opps),
            'scanned': len(symbols)
        })
    
    except Exception as e:
        logger.error(f"扫描失败: {e}")
        return jsonify({'error': str(e)}), 500
```

### 3. 并行计算实现

使用 Python 标准库 `concurrent.futures.ThreadPoolExecutor`：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {
        executor.submit(process_func, item): item 
        for item in items
    }
    
    for future in as_completed(futures):
        try:
            result = future.result(timeout=5)  # 单个任务超时5秒
            results.append(result)
        except Exception as e:
            logger.error(f"任务失败: {e}")
```

## 错误处理和性能优化

### 错误处理

1. **单只股票计算失败**
   - 捕获异常，记录日志，跳过该股票
   - 不影响其他股票的计算
   - 在响应中返回成功处理的股票数量

2. **K 线数据不足**
   - 如果某只股票 K 线数据 < 30 天，跳过该股票
   - 记录警告日志

3. **数据库查询超时**
   - 设置查询超时时间（30秒）
   - 超时返回 500 错误，提示用户稍后重试

4. **并发限制**
   - 限制最多 10 个并发线程
   - 避免过多线程导致数据库连接耗尽

### 性能优化

1. **批量查询优化**
   - 一次性查询所有股票的 K 线数据
   - 使用 `WHERE symbol IN (...)` 批量查询
   - 减少数据库往返次数

2. **指标计算缓存**
   - `FactorRegistry` 已有缓存机制（`FactorCache`）
   - 相同股票的重复计算会命中缓存

3. **响应时间预估**
   - 400 只股票，每只 50ms 计算时间
   - 10 个并发线程：400 / 10 * 50ms = 2 秒
   - 加上数据库查询时间（约 2-3 秒）
   - **总响应时间：5-6 秒**

4. **超时保护**
   - 设置整体扫描超时时间（15秒）
   - 超时返回已计算完成的结果
   - 避免长时间阻塞用户请求

### 日志和监控

记录以下信息便于后续分析：

- 每次扫描的股票数量
- 扫描总耗时
- 成功/失败股票数量
- 异常股票的代码和错误信息
- 数据库查询耗时
- 并行计算耗时

示例日志：

```
[INFO] 扫描开始: 股票数=420, 技术条件=['rsi_oversold', 'macd_golden_cross']
[INFO] 数据查询完成: 耗时=2.3s
[INFO] 并行计算完成: 耗时=2.1s, 成功=415, 失败=5
[WARN] 600001.SH: K线数据不足 (15天)
[ERROR] 600002.SH: 评分失败 - division by zero
[INFO] 扫描完成: 总耗时=5.2s, 返回结果=380
```

## 预期性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 扫描股票数 | 400-500 | 自选股 + 热门股票池 |
| 响应时间 | 5-6秒 | P50 |
| 响应时间 | <10秒 | P95 |
| 成功率 | >95% | 单股票计算成功率 |
| 并发线程数 | 10 | 平衡性能和资源 |
| 数据窗口 | 120天 | K线数据 |

## 后续优化方向

1. **缓存优化**
   - 热门股票池缓存（1小时）
   - K线数据缓存（5分钟）

2. **增量计算**
   - 只计算最新一天的指标
   - 历史指标从缓存读取

3. **异步任务**
   - 扫描改为异步任务
   - 前端轮询获取结果

4. **分布式计算**
   - 使用 Celery 分布式任务队列
   - 支持更大规模的股票池扫描
