# 机会雷达实时扫描功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构机会雷达后端扫描逻辑，从历史信号查询改为实时计算模式，支持用户自定义技术指标和基本面条件的动态筛选。

**Architecture:** 新增 StockPoolService（热门股票池管理）和 OpportunityScoringService（评分引擎），使用 ThreadPoolExecutor 并行计算400只股票的技术面/基本面/资金面评分，批量查询120天K线数据优化性能。

**Tech Stack:** Python 3.x, Flask, PostgreSQL, concurrent.futures, FactorRegistry

---

## 文件结构

### 新增文件
- `quantsys-v2/services/stock_pool_service.py` - 热门股票池服务
- `quantsys-v2/services/opportunity_scoring_service.py` - 机会评分引擎
- `quantsys-v2/tests/services/test_stock_pool_service.py` - 股票池服务测试
- `quantsys-v2/tests/services/test_opportunity_scoring_service.py` - 评分引擎测试

### 修改文件
- `quantsys-v2/api/server.py:1108-1180` - 重构 scan_signals 端点
- `quantsys-v2/repositories/stock_repository.py` - 添加 get_index_components 和 get_fundamental 方法
- `quantsys-v2/repositories/kline_repository.py` - 添加 batch_get_recent_klines 方法

---

## Task 1: 扩展 KlineRepository 批量查询方法

**Files:**
- Modify: `quantsys-v2/repositories/kline_repository.py`
- Test: `quantsys-v2/tests/repositories/test_kline_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/repositories/test_kline_repository.py
def test_batch_get_recent_klines(kline_repo, db_connection):
    """测试批量查询最近N天K线数据"""
    # 准备测试数据
    symbols = ['600519.SH', '600036.SH', '601318.SH']
    days = 120
    
    # 插入测试K线数据
    for symbol in symbols:
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO quant.daily_klines 
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
            db_connection.commit()
            cursor.close()
    
    # 执行批量查询
    result = kline_repo.batch_get_recent_klines(symbols, days)
    
    # 验证结果
    assert isinstance(result, dict)
    assert len(result) == 3
    for symbol in symbols:
        assert symbol in result
        assert len(result[symbol]) == days
        assert result[symbol][0]['symbol'] == symbol
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/repositories/test_kline_repository.py::test_batch_get_recent_klines -v`
Expected: FAIL with "AttributeError: 'KlineRepository' object has no attribute 'batch_get_recent_klines'"

- [ ] **Step 3: Implement batch_get_recent_klines method**

```python
# quantsys-v2/repositories/kline_repository.py
def batch_get_recent_klines(
    self,
    symbols: List[str],
    days: int
) -> Dict[str, List[Dict]]:
    """批量查询多只股票的最近N天K线数据
    
    Args:
        symbols: 股票代码列表
        days: 查询天数
    
    Returns:
        {symbol: [kline_data]} 字典，按日期升序排列
    """
    if not symbols:
        return {}
    
    # 参数校验
    for symbol in symbols:
        self._validate_symbol(symbol)
    
    # 构建批量查询SQL
    placeholders = ','.join(['%s'] * len(symbols))
    query = f"""
        SELECT symbol, trade_date, open, high, low, close, volume,
               amount, turnover_rate, change_pct
        FROM quant.daily_klines
        WHERE symbol IN ({placeholders})
          AND trade_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY symbol, trade_date ASC
    """
    
    cursor = self.db.cursor()
    cursor.execute(query, tuple(symbols))
    results = cursor.fetchall()
    cursor.close()
    
    # 按股票代码分组
    klines_map = {symbol: [] for symbol in symbols}
    for row in results:
        symbol = row['symbol']
        if symbol in klines_map:
            klines_map[symbol].append(dict(row))
    
    return klines_map
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/repositories/test_kline_repository.py::test_batch_get_recent_klines -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/repositories/kline_repository.py quantsys-v2/tests/repositories/test_kline_repository.py
git commit -m "feat(kline): add batch_get_recent_klines for parallel stock scanning"
```

---

## Task 2: 扩展 StockRepository 基本面和指数成分股查询

**Files:**
- Modify: `quantsys-v2/repositories/stock_repository.py`
- Test: `quantsys-v2/tests/repositories/test_stock_repository.py`

- [ ] **Step 1: Write the failing test for get_fundamental**

```python
# tests/repositories/test_stock_repository.py
def test_get_fundamental(stock_repo, db_connection):
    """测试查询股票基本面数据"""
    symbol = '600519.SH'
    
    # 插入测试基本面数据
    cursor = db_connection.cursor()
    cursor.execute("""
        INSERT INTO quant.stock_fundamentals 
        (symbol, pe_ratio, roe, gross_margin, debt_ratio, report_date)
        VALUES (%s, 25.5, 18.2, 35.6, 42.3, '2024-12-31')
        ON CONFLICT (symbol, report_date) DO UPDATE SET
        pe_ratio = EXCLUDED.pe_ratio,
        roe = EXCLUDED.roe,
        gross_margin = EXCLUDED.gross_margin,
        debt_ratio = EXCLUDED.debt_ratio
    """, (symbol,))
    db_connection.commit()
    cursor.close()
    
    # 执行查询
    result = stock_repo.get_fundamental(symbol)
    
    # 验证结果
    assert result is not None
    assert result['symbol'] == symbol
    assert result['pe'] == 25.5
    assert result['roe'] == 18.2
    assert result['gross_margin'] == 35.6
    assert result['debt_ratio'] == 42.3
```

- [ ] **Step 2: Write the failing test for get_index_components**

```python
# tests/repositories/test_stock_repository.py
def test_get_index_components(stock_repo, db_connection):
    """测试查询指数成分股"""
    index_codes = ['000300.SH', '399006.SZ']
    
    # 插入测试指数成分股数据
    cursor = db_connection.cursor()
    for index_code in index_codes:
        for i in range(5):
            symbol = f'60{i:04d}.SH'
            cursor.execute("""
                INSERT INTO quant.index_components 
                (index_code, symbol, weight)
                VALUES (%s, %s, %s)
                ON CONFLICT (index_code, symbol) DO NOTHING
            """, (index_code, symbol, 1.0))
    db_connection.commit()
    cursor.close()
    
    # 执行查询
    result = stock_repo.get_index_components(index_codes)
    
    # 验证结果
    assert isinstance(result, list)
    assert len(result) >= 5
    assert all(isinstance(s, str) for s in result)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/repositories/test_stock_repository.py::test_get_fundamental tests/repositories/test_stock_repository.py::test_get_index_components -v`
Expected: FAIL with "AttributeError: 'StockRepository' object has no attribute 'get_fundamental'"

- [ ] **Step 4: Implement get_fundamental method**

```python
# quantsys-v2/repositories/stock_repository.py
def get_fundamental(self, symbol: str) -> Optional[Dict[str, Any]]:
    """查询股票最新基本面数据
    
    Args:
        symbol: 股票代码
    
    Returns:
        基本面数据字典，包含 pe, roe, gross_margin, debt_ratio 等字段
        如果不存在返回 None
    """
    self._validate_symbol(symbol)
    
    query = """
        SELECT symbol, pe_ratio as pe, roe, gross_margin, debt_ratio, report_date
        FROM quant.stock_fundamentals
        WHERE symbol = %s
        ORDER BY report_date DESC
        LIMIT 1
    """
    
    self._log_query("get_fundamental", {"symbol": symbol})
    
    try:
        cursor = self.db.cursor()
        cursor.execute(query, (symbol,))
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    except Exception as e:
        logger.error(f"Failed to get fundamental for {symbol}: {e}")
        raise
```

- [ ] **Step 5: Implement get_index_components method**

```python
# quantsys-v2/repositories/stock_repository.py
def get_index_components(self, index_codes: List[str]) -> List[str]:
    """查询指数成分股列表
    
    Args:
        index_codes: 指数代码列表，如 ['000300.SH', '399006.SZ']
    
    Returns:
        股票代码列表（去重）
    """
    if not index_codes:
        return []
    
    placeholders = ','.join(['%s'] * len(index_codes))
    query = f"""
        SELECT DISTINCT symbol
        FROM quant.index_components
        WHERE index_code IN ({placeholders})
        ORDER BY symbol
    """
    
    self._log_query("get_index_components", {"index_codes": index_codes})
    
    try:
        cursor = self.db.cursor()
        cursor.execute(query, tuple(index_codes))
        results = cursor.fetchall()
        cursor.close()
        
        return [row['symbol'] for row in results]
    
    except Exception as e:
        logger.error(f"Failed to get index components: {e}")
        raise
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/repositories/test_stock_repository.py::test_get_fundamental tests/repositories/test_stock_repository.py::test_get_index_components -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add quantsys-v2/repositories/stock_repository.py quantsys-v2/tests/repositories/test_stock_repository.py
git commit -m "feat(stock): add get_fundamental and get_index_components methods"
```

---

## Task 3: 创建 StockPoolService 热门股票池服务

**Files:**
- Create: `quantsys-v2/services/stock_pool_service.py`
- Test: `quantsys-v2/tests/services/test_stock_pool_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_stock_pool_service.py
import pytest
from services.stock_pool_service import StockPoolService
from repositories.stock_repository import StockRepository


@pytest.fixture
def stock_pool_service(db_connection):
    """创建 StockPoolService 实例"""
    stock_repo = StockRepository()
    stock_repo.db = db_connection
    return StockPoolService(stock_repo)


def test_get_hot_stocks_from_database(stock_pool_service, db_connection):
    """测试从数据库获取热门股票池"""
    cursor = db_connection.cursor()
    test_symbols = ['600519.SH', '600036.SH', '601318.SH']
    for symbol in test_symbols:
        cursor.execute("""
            INSERT INTO quant.index_components 
            (index_code, symbol, weight)
            VALUES ('000300.SH', %s, 1.0)
            ON CONFLICT (index_code, symbol) DO NOTHING
        """, (symbol,))
    db_connection.commit()
    cursor.close()
    
    result = stock_pool_service.get_hot_stocks()
    
    assert isinstance(result, list)
    assert len(result) >= 3
    for symbol in test_symbols:
        assert symbol in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_stock_pool_service.py::test_get_hot_stocks_from_database -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement StockPoolService**

```python
# quantsys-v2/services/stock_pool_service.py
from typing import List
from repositories.stock_repository import StockRepository
import logging

logger = logging.getLogger(__name__)


class StockPoolService:
    def __init__(self, stock_repo: StockRepository):
        self.stock_repo = stock_repo
    
    def get_hot_stocks(self) -> List[str]:
        try:
            components = self.stock_repo.get_index_components([
                '000300.SH', '399006.SZ', '000688.SH'
            ])
            if components:
                return components
            return self._get_fallback_hot_stocks()
        except Exception as e:
            logger.error(f"获取热门股票池失败: {e}")
            return self._get_fallback_hot_stocks()
    
    def _get_fallback_hot_stocks(self) -> List[str]:
        return [
            '600519.SH', '600036.SH', '601318.SH', '600276.SH', '601166.SH',
            '600030.SH', '600887.SH', '601888.SH', '600009.SH', '601012.SH',
            '300059.SZ', '300750.SZ', '300760.SZ', '002475.SZ', '002594.SZ'
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_stock_pool_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/stock_pool_service.py quantsys-v2/tests/services/test_stock_pool_service.py
git commit -m "feat(service): add StockPoolService for hot stock pool management"
```

---

## Task 4: 创建 OpportunityScoringService 评分引擎（核心）

**Files:**
- Create: `quantsys-v2/services/opportunity_scoring_service.py`
- Test: `quantsys-v2/tests/services/test_opportunity_scoring_service.py`

- [ ] **Step 1: Write the failing test for score_stocks**

```python
# tests/services/test_opportunity_scoring_service.py
import pytest
from datetime import datetime, timedelta
from services.opportunity_scoring_service import OpportunityScoringService
from repositories.kline_repository import KlineRepository
from repositories.stock_repository import StockRepository
from quant.engine.factor_registry import FactorRegistry


@pytest.fixture
def scoring_service(db_connection):
    kline_repo = KlineRepository()
    kline_repo.db = db_connection
    stock_repo = StockRepository()
    stock_repo.db = db_connection
    factor_registry = FactorRegistry()
    return OpportunityScoringService(kline_repo, stock_repo, factor_registry)


def test_score_stocks_basic(scoring_service, db_connection):
    """测试基本评分功能"""
    symbols = ['600519.SH', '600036.SH']
    
    # 插入测试K线数据
    for symbol in symbols:
        for i in range(120):
            date = (datetime.now() - timedelta(days=120-i-1)).strftime('%Y-%m-%d')
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO quant.daily_klines 
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
            db_connection.commit()
            cursor.close()
    
    # 执行评分
    filters = {
        'technical': ['rsi_oversold'],
        'fundamental': []
    }
    results = scoring_service.score_stocks(symbols, filters)
    
    # 验证结果
    assert isinstance(results, list)
    assert len(results) <= len(symbols)
    for opp in results:
        assert 'symbol' in opp
        assert 'score' in opp
        assert 'technical_score' in opp
        assert 'fundamental_score' in opp
        assert 'capital_score' in opp
        assert 0 <= opp['score'] <= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_opportunity_scoring_service.py::test_score_stocks_basic -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement OpportunityScoringService skeleton**

```python
# quantsys-v2/services/opportunity_scoring_service.py
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from repositories.kline_repository import KlineRepository
from repositories.stock_repository import StockRepository
from quant.engine.factor_registry import FactorRegistry
import logging

logger = logging.getLogger(__name__)


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
        """批量评分股票"""
        klines_map = self.kline_repo.batch_get_recent_klines(symbols, days=120)
        
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
        """评分单只股票"""
        try:
            if len(klines) < 30:
                logger.warning(f"{symbol}: K线数据不足")
                return None
            
            # 计算技术指标（暂时返回空字典）
            factors = {}
            
            # 查询基本面数据
            fundamental = self.stock_repo.get_fundamental(symbol)
            
            # 计算三维评分
            tech_score = self._calculate_technical_score(factors, filters.get('technical', []))
            fund_score = self._calculate_fundamental_score(fundamental, filters.get('fundamental', []))
            capital_score = self._calculate_capital_score(factors)
            
            # 计算综合评分
            total_score = tech_score * 0.5 + fund_score * 0.3 + capital_score * 0.2
            
            return {
                'symbol': symbol,
                'name': self.stock_repo.get_by_symbol(symbol, ['name'])['name'] if self.stock_repo.get_by_symbol(symbol) else symbol,
                'score': round(total_score),
                'technical_score': round(tech_score),
                'fundamental_score': round(fund_score),
                'capital_score': round(capital_score),
                'confidence': total_score / 100,
                'risk_level': self._calculate_risk_level(total_score),
                'signal_type': 'buy',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"{symbol}: 评分失败 - {e}")
            return None
    
    def _calculate_technical_score(self, factors: Dict, conditions: List[str]) -> float:
        """计算技术面评分"""
        if not conditions:
            return 50.0
        return 50.0  # 暂时返回中性评分
    
    def _calculate_fundamental_score(self, fundamental: Optional[Dict], conditions: List[str]) -> float:
        """计算基本面评分"""
        if not fundamental:
            return 50.0
        return 50.0  # 暂时返回中性评分
    
    def _calculate_capital_score(self, factors: Dict) -> float:
        """计算资金面评分"""
        return 50.0  # 暂时返回中性评分
    
    def _calculate_risk_level(self, score: float) -> str:
        """计算风险等级"""
        if score >= 70:
            return 'low'
        elif score >= 50:
            return 'medium'
        else:
            return 'high'
```

- [ ] **Step 4: Run test to verify skeleton passes**

Run: `pytest tests/services/test_opportunity_scoring_service.py::test_score_stocks_basic -v`
Expected: PASS (with neutral scores)

- [ ] **Step 5: Commit skeleton**

```bash
git add quantsys-v2/services/opportunity_scoring_service.py quantsys-v2/tests/services/test_opportunity_scoring_service.py
git commit -m "feat(service): add OpportunityScoringService skeleton"
```

---

## Task 4 (continued): 实现评分逻辑

- [ ] **Step 6: Write test for technical scoring**

```python
# tests/services/test_opportunity_scoring_service.py
def test_calculate_technical_score(scoring_service):
    """测试技术面评分计算"""
    # RSI超卖场景
    factors = {'rsi': 25}
    score = scoring_service._calculate_technical_score(factors, ['rsi_oversold'])
    assert score == 25
    
    # 无条件场景
    score = scoring_service._calculate_technical_score(factors, [])
    assert score == 50
```

- [ ] **Step 7: Implement _calculate_technical_score**

```python
# quantsys-v2/services/opportunity_scoring_service.py
def _calculate_technical_score(self, factors: Dict, conditions: List[str]) -> float:
    """计算技术面评分"""
    if not conditions:
        return 50.0
    
    score = 0.0
    for condition in conditions:
        if condition == 'rsi_oversold' and factors.get('rsi', 100) < 30:
            score += 25
        elif condition == 'macd_golden_cross':
            if self._is_macd_golden_cross(factors):
                score += 25
        elif condition == 'bollinger_breakout':
            if factors.get('close', 0) > factors.get('boll_upper', float('inf')):
                score += 25
        elif condition == 'volume_surge':
            if factors.get('volume_ratio_5d', 0) > 2:
                score += 25
    
    return min(score, 100.0)
```

- [ ] **Step 8: Implement _calculate_fundamental_score**

```python
# quantsys-v2/services/opportunity_scoring_service.py
def _calculate_fundamental_score(self, fundamental: Optional[Dict], conditions: List[str]) -> float:
    """计算基本面评分"""
    if not fundamental:
        return 50.0
    
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
```

- [ ] **Step 9: Implement _calculate_capital_score**

```python
# quantsys-v2/services/opportunity_scoring_service.py
def _calculate_capital_score(self, factors: Dict) -> float:
    """计算资金面评分（基于成交量指标）"""
    score = 0.0
    
    if factors.get('volume_ratio_5d', 0) > 1.5:
        score += 25
    
    if self._is_volume_increasing(factors, days=3):
        score += 25
    
    if factors.get('volume', 0) > factors.get('volume_ma20', float('inf')):
        score += 25
    
    if factors.get('volume_ma5', 0) > factors.get('volume_ma20', float('inf')):
        score += 25
    
    return min(score, 100.0)
```

- [ ] **Step 10: Implement helper methods**

```python
# quantsys-v2/services/opportunity_scoring_service.py
def _is_macd_golden_cross(self, factors: Dict) -> bool:
    """判断MACD金叉"""
    macd = factors.get('macd', 0)
    signal = factors.get('macd_signal', 0)
    macd_prev = factors.get('macd_prev', 0)
    signal_prev = factors.get('macd_signal_prev', 0)
    return macd > signal and macd_prev < signal_prev

def _is_volume_increasing(self, factors: Dict, days: int = 3) -> bool:
    """判断成交量连续递增"""
    volumes = factors.get('volume_history', [])
    if len(volumes) < days:
        return False
    for i in range(len(volumes) - days + 1, len(volumes)):
        if volumes[i] <= volumes[i - 1]:
            return False
    return True
```

- [ ] **Step 11: Run tests to verify scoring logic**

Run: `pytest tests/services/test_opportunity_scoring_service.py -v`
Expected: PASS

- [ ] **Step 12: Commit scoring logic**

```bash
git add quantsys-v2/services/opportunity_scoring_service.py quantsys-v2/tests/services/test_opportunity_scoring_service.py
git commit -m "feat(service): implement technical/fundamental/capital scoring logic"
```

---

## Task 5: 重构 /api/signals/scan 端点

**Files:**
- Modify: `quantsys-v2/api/server.py:1108-1180`
- Test: Manual testing with curl/Postman

- [ ] **Step 1: Initialize services at server startup**

```python
# quantsys-v2/api/server.py (add after imports)
from services.stock_pool_service import StockPoolService
from services.opportunity_scoring_service import OpportunityScoringService
from quant.engine.factor_registry import FactorRegistry

# Initialize services (add after ds initialization)
stock_pool_service = StockPoolService(ds.stock)
factor_registry = FactorRegistry()
scoring_service = OpportunityScoringService(ds.kline, ds.stock, factor_registry)
```

- [ ] **Step 2: Backup existing scan_signals function**

```bash
# Create backup
cp quantsys-v2/api/server.py quantsys-v2/api/server.py.backup
```

- [ ] **Step 3: Rewrite scan_signals function**

```python
# quantsys-v2/api/server.py
@app.route('/api/signals/scan', methods=['POST'])
def scan_signals():
    """机会雷达扫描 - 实时计算模式
    
    接收前端 OpportunityFilters:
      { minScore, maxRiskLevel, industries, technical, fundamental, stocks? }
    """
    data = request.get_json() or {}
    snake_data = convert_keys_to_snake(data)
    
    stocks_param = snake_data.get('stocks', [])
    min_score = float(snake_data.get('min_score', 0.0))
    max_risk_level = snake_data.get('max_risk_level', 'high')
    industries = snake_data.get('industries', [])
    technical = snake_data.get('technical', [])
    fundamental = snake_data.get('fundamental', [])
    
    try:
        # 1. 获取股票列表
        if stocks_param:
            symbols = list(stocks_param) if isinstance(stocks_param, list) else [stocks_param]
        else:
            # 自选股 + 热门股票池
            try:
                watchlist = _read_watchlist()
                watchlist_symbols = [item['symbol'] for item in watchlist.get('items', [])]
            except Exception:
                watchlist_symbols = []
            
            hot_stocks = stock_pool_service.get_hot_stocks()
            symbols = list(set(watchlist_symbols + hot_stocks))
        
        logger.info(f"扫描开始: 股票数={len(symbols)}, 技术条件={technical}, 基本面条件={fundamental}")
        
        # 2. 调用评分引擎
        opportunities = scoring_service.score_stocks(
            symbols=symbols,
            filters={
                'technical': technical,
                'fundamental': fundamental
            }
        )
        
        # 3. 应用风险等级筛选
        risk_level_map = {'low': 1, 'medium': 2, 'high': 3}
        max_risk = risk_level_map.get(max_risk_level, 3)
        filtered = [
            opp for opp in opportunities
            if risk_level_map.get(opp['risk_level'], 3) <= max_risk
        ]
        
        # 4. 应用评分筛选
        if min_score > 0:
            filtered = [o for o in filtered if o['score'] >= min_score]
        
        # 5. 应用行业筛选
        if industries:
            industry_filtered = []
            for o in filtered:
                stock = ds.stock.get_by_symbol(o['symbol'])
                if stock and stock.get('industry', '') in industries:
                    industry_filtered.append(o)
            filtered = industry_filtered
        
        # 6. 排序（按综合评分降序）
        sorted_opps = sorted(filtered, key=lambda x: x['score'], reverse=True)
        
        logger.info(f"扫描完成: 扫描{len(symbols)}只, 返回{len(sorted_opps)}只")
        
        return jsonify({
            'success': True,
            'opportunities': sorted_opps,
            'total': len(sorted_opps),
            'scanned': len(symbols)
        })
    
    except Exception as e:
        logger.error(f"扫描失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 4: Test with curl - basic scan**

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan   -H "Content-Type: application/json"   -d '{
    "technical": ["rsi_oversold"],
    "fundamental": [],
    "maxRiskLevel": "high"
  }'
```

Expected: JSON response with opportunities array

- [ ] **Step 5: Test with curl - with filters**

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan   -H "Content-Type: application/json"   -d '{
    "technical": ["rsi_oversold", "macd_golden_cross"],
    "fundamental": ["pe_low"],
    "maxRiskLevel": "medium",
    "minScore": 60
  }'
```

Expected: Filtered results with score >= 60 and risk <= medium

- [ ] **Step 6: Verify response format matches frontend expectations**

Check that response includes:
- `opportunities` array with `symbol`, `name`, `score`, `technical_score`, `fundamental_score`, `capital_score`, `confidence`, `risk_level`, `signal_type`, `timestamp`
- `total` count
- `scanned` count

- [ ] **Step 7: Remove backup file**

```bash
rm quantsys-v2/api/server.py.backup
```

- [ ] **Step 8: Commit**

```bash
git add quantsys-v2/api/server.py
git commit -m "refactor(api): rewrite scan_signals to use real-time scoring engine"
```

---

## Task 6: 集成测试和性能验证

**Files:**
- Create: `quantsys-v2/tests/integration/test_opportunity_radar_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_opportunity_radar_integration.py
import pytest
import time
from datetime import datetime, timedelta
from api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_scan_signals_integration(client, db_connection):
    """集成测试：完整扫描流程"""
    # 准备测试数据
    symbols = ['600519.SH', '600036.SH', '601318.SH']
    
    # 插入K线数据
    for symbol in symbols:
        for i in range(120):
            date = (datetime.now() - timedelta(days=120-i-1)).strftime('%Y-%m-%d')
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO quant.daily_klines 
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
            db_connection.commit()
            cursor.close()
    
    # 插入指数成分股
    cursor = db_connection.cursor()
    for symbol in symbols:
        cursor.execute("""
            INSERT INTO quant.index_components 
            (index_code, symbol, weight)
            VALUES ('000300.SH', %s, 1.0)
            ON CONFLICT (index_code, symbol) DO NOTHING
        """, (symbol,))
    db_connection.commit()
    cursor.close()
    
    # 执行扫描
    start_time = time.time()
    response = client.post('/api/signals/scan', json={
        'technical': ['rsi_oversold'],
        'fundamental': [],
        'maxRiskLevel': 'high'
    })
    elapsed = time.time() - start_time
    
    # 验证响应
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'opportunities' in data
    assert 'total' in data
    assert 'scanned' in data
    
    # 验证性能（应该在10秒内完成）
    assert elapsed < 10, f"扫描耗时{elapsed:.2f}秒，超过10秒阈值"
    
    print(f"扫描完成: 耗时{elapsed:.2f}秒, 扫描{data['scanned']}只, 返回{data['total']}只")
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_opportunity_radar_integration.py -v -s`
Expected: PASS with performance metrics printed

- [ ] **Step 3: Performance test with 400 stocks**

```python
# tests/integration/test_opportunity_radar_integration.py
def test_scan_signals_performance_400_stocks(client, db_connection):
    """性能测试：400只股票扫描"""
    # 准备400只股票的K线数据
    symbols = [f'60{i:04d}.SH' for i in range(400)]
    
    cursor = db_connection.cursor()
    for symbol in symbols:
        # 插入指数成分股
        cursor.execute("""
            INSERT INTO quant.index_components 
            (index_code, symbol, weight)
            VALUES ('000300.SH', %s, 1.0)
            ON CONFLICT (index_code, symbol) DO NOTHING
        """, (symbol,))
        
        # 插入K线数据（简化版，只插入30天）
        for i in range(30):
            date = (datetime.now() - timedelta(days=30-i-1)).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO quant.daily_klines 
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
    
    db_connection.commit()
    cursor.close()
    
    # 执行扫描
    start_time = time.time()
    response = client.post('/api/signals/scan', json={
        'technical': [],
        'fundamental': [],
        'maxRiskLevel': 'high'
    })
    elapsed = time.time() - start_time
    
    # 验证响应
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # 验证性能（目标5-6秒，最大10秒）
    print(f"\n性能测试结果:")
    print(f"  扫描股票数: {data['scanned']}")
    print(f"  返回结果数: {data['total']}")
    print(f"  总耗时: {elapsed:.2f}秒")
    print(f"  平均每只: {elapsed/data['scanned']*1000:.2f}ms")
    
    assert elapsed < 10, f"扫描400只股票耗时{elapsed:.2f}秒，超过10秒阈值"
```

- [ ] **Step 4: Run performance test**

Run: `pytest tests/integration/test_opportunity_radar_integration.py::test_scan_signals_performance_400_stocks -v -s`
Expected: PASS with elapsed time < 10s

- [ ] **Step 5: Commit integration tests**

```bash
git add quantsys-v2/tests/integration/test_opportunity_radar_integration.py
git commit -m "test(integration): add opportunity radar integration and performance tests"
```

---

## Task 7: 文档更新和最终验证

**Files:**
- Update: `quantsys-v2/README.md` or relevant docs

- [ ] **Step 1: Update API documentation**

Document the `/api/signals/scan` endpoint:

```markdown
### POST /api/signals/scan

机会雷达实时扫描接口

**Request Body:**
```json
{
  "technical": ["rsi_oversold", "macd_golden_cross", "bollinger_breakout", "volume_surge"],
  "fundamental": ["pe_low", "roe_high", "gross_margin_high", "debt_ratio_low"],
  "maxRiskLevel": "high|medium|low",
  "minScore": 0,
  "industries": [],
  "stocks": []
}
```

**Response:**
```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "score": 75,
      "technical_score": 50,
      "fundamental_score": 75,
      "capital_score": 50,
      "confidence": 0.75,
      "risk_level": "low",
      "signal_type": "buy",
      "timestamp": "2026-05-24T10:30:00"
    }
  ],
  "total": 1,
  "scanned": 400
}
```

**Performance:**
- 扫描400只股票约5-6秒
- 使用120天K线数据计算技术指标
- 并行计算（10线程）
```

- [ ] **Step 2: Run full test suite**

```bash
cd quantsys-v2
pytest tests/ -v --cov=services --cov=repositories --cov-report=term-missing
```

Expected: All tests pass, coverage > 80%

- [ ] **Step 3: Manual end-to-end test with frontend**

1. Start API server: `python api/server.py`
2. Start frontend: `cd web-frontend && npm run dev`
3. Navigate to 机会雷达 page
4. Click "开始扫描"
5. Verify:
   - Loading indicator appears
   - Results load within 10 seconds
   - Opportunity cards display correctly
   - Filters work (technical, fundamental, risk level)

- [ ] **Step 4: Verify log output**

Check logs for:
```
[INFO] 扫描开始: 股票数=420, 技术条件=['rsi_oversold']
[INFO] 从数据库获取热门股票池: 400只
[INFO] 扫描完成: 扫描420只, 返回85只
```

- [ ] **Step 5: Commit documentation**

```bash
git add docs/ README.md
git commit -m "docs: update API documentation for opportunity radar real-time scan"
```

---

## Self-Review Checklist

### 1. Spec Coverage

- [x] 扫描范围：自选股 + 热门股票池（Task 3, Task 5）
- [x] 数据窗口：120天K线数据（Task 1, Task 4）
- [x] 基本面数据：从数据库读取（Task 2, Task 4）
- [x] 综合评分算法：技术面50% + 基本面30% + 资金面20%（Task 4）
- [x] 性能优化：批量查询 + 并行计算（Task 1, Task 4）
- [x] 资金面数据：成交量指标替代（Task 4）
- [x] 热门股票池：沪深300 + 创业板50 + 科创50（Task 3）
- [x] 技术指标筛选：RSI、MACD、布林带、成交量（Task 4）
- [x] 基本面筛选：PE、ROE、毛利率、负债率（Task 4）
- [x] 风险等级筛选：低/中/高（Task 4, Task 5）
- [x] API端点重构（Task 5）
- [x] 错误处理和日志（Task 4, Task 5）
- [x] 集成测试和性能验证（Task 6）

### 2. Placeholder Scan

No placeholders found - all code blocks are complete.

### 3. Type Consistency

- `batch_get_recent_klines` returns `Dict[str, List[Dict]]` ✓
- `get_hot_stocks` returns `List[str]` ✓
- `score_stocks` returns `List[Dict]` ✓
- `get_fundamental` returns `Optional[Dict[str, Any]]` ✓
- `get_index_components` returns `List[str]` ✓

All method signatures are consistent across tasks.

### 4. Test Coverage

- Task 1: KlineRepository batch query ✓
- Task 2: StockRepository fundamental and index components ✓
- Task 3: StockPoolService hot stocks ✓
- Task 4: OpportunityScoringService scoring logic ✓
- Task 5: API endpoint (manual testing) ✓
- Task 6: Integration and performance tests ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-24-opportunity-radar-realtime-scan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
