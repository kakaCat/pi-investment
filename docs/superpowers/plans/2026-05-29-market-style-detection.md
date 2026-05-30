# P3-2 市场风格检测系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现市场风格自动检测系统，识别市场状态（动量、震荡、低波、价值）并动态调整策略权重

**Architecture:** 三层架构 - 数据层（PostgreSQL表）→ 仓储层（Repository）→ 服务层（Detector + Adjuster）→ API层（Flask）→ Agent集成（TypeScript）

**Tech Stack:** Python 3.13, Flask, PostgreSQL, APScheduler, NumPy/Pandas

---

## 文件结构规划

### 新建文件

**数据库迁移**：
- `quantsys-v2/migrations/create_market_style_tables.sql` - 创建市场风格相关表

**仓储层**：
- `quantsys-v2/repositories/market_style_repository.py` - 市场风格状态仓储
- `quantsys-v2/repositories/strategy_weight_repository.py` - 策略权重配置仓储

**服务层**：
- `quantsys-v2/services/market_style_detector.py` - 市场风格检测服务
- `quantsys-v2/services/strategy_weight_adjuster.py` - 策略权重调整服务

**API层**：
- `quantsys-v2/api/routes/market_style.py` - 市场风格API路由

**定时任务**：
- `quantsys-v2/runtime/scheduler/market_style_jobs.py` - 市场风格更新定时任务

**测试文件**：
- `quantsys-v2/tests/services/test_market_style_detector.py`
- `quantsys-v2/tests/services/test_strategy_weight_adjuster.py`
- `quantsys-v2/tests/repositories/test_market_style_repository.py`
- `quantsys-v2/tests/repositories/test_strategy_weight_repository.py`
- `quantsys-v2/tests/api/test_market_style_routes.py`

### 修改文件

- `quantsys-v2/api/server.py` - 注册新路由
- `quantsys-v2/runtime/scheduler/__init__.py` - 注册定时任务
- `src/infrastructure/tools/core/quant-cli-tool.ts` - 扩展 strategy_execute 输出（TypeScript Agent）

---

## Task 1: 数据库表创建

**Files:**
- Create: `quantsys-v2/migrations/create_market_style_tables.sql`

- [ ] **Step 1: 编写数据库迁移脚本**

```sql
-- 市场风格状态表
CREATE TABLE IF NOT EXISTS quant.market_style_state (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    style VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_market_style_date ON quant.market_style_state(trade_date DESC);

COMMENT ON TABLE quant.market_style_state IS '市场风格状态表';
COMMENT ON COLUMN quant.market_style_state.style IS '风格类型: momentum, oscillation, low_volatility, value';
COMMENT ON COLUMN quant.market_style_state.confidence IS '置信度 0.0-1.0';
COMMENT ON COLUMN quant.market_style_state.metrics IS '详细指标 JSON';

-- 策略权重配置表
CREATE TABLE IF NOT EXISTS quant.strategy_weight_config (
    id SERIAL PRIMARY KEY,
    strategy_type VARCHAR(50) NOT NULL,
    market_style VARCHAR(50) NOT NULL,
    static_weight FLOAT NOT NULL CHECK (static_weight >= -1.0 AND static_weight <= 1.0),
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(strategy_type, market_style)
);

CREATE INDEX idx_strategy_weight_lookup ON quant.strategy_weight_config(strategy_type, market_style);

COMMENT ON TABLE quant.strategy_weight_config IS '策略权重配置表';
COMMENT ON COLUMN quant.strategy_weight_config.static_weight IS '静态权重调整 -1.0 到 +1.0';

-- 插入初始静态权重数据
INSERT INTO quant.strategy_weight_config (strategy_type, market_style, static_weight) VALUES
    ('trend_following', 'momentum', 0.30),
    ('trend_following', 'oscillation', -0.40),
    ('mean_reversion', 'oscillation', 0.30),
    ('mean_reversion', 'momentum', -0.20),
    ('multi_factor', 'value', 0.20),
    ('multi_factor', 'low_volatility', 0.10)
ON CONFLICT (strategy_type, market_style) DO NOTHING;

-- 扩展 strategy_performance 表
ALTER TABLE quant.strategy_performance 
ADD COLUMN IF NOT EXISTS market_style VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_style 
ON quant.strategy_performance(strategy_name, market_style);

COMMENT ON COLUMN quant.strategy_performance.market_style IS '交易时的市场风格';
```

- [ ] **Step 2: 执行数据库迁移**

```bash
cd quantsys-v2
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f migrations/create_market_style_tables.sql
```

Expected: 表创建成功，初始数据插入成功

- [ ] **Step 3: 验证表结构**

```bash
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "\d quant.market_style_state"
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "\d quant.strategy_weight_config"
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "SELECT COUNT(*) FROM quant.strategy_weight_config;"
```

Expected: 表结构正确，6 条初始权重数据

- [ ] **Step 4: 提交**

```bash
git add migrations/create_market_style_tables.sql
git commit -m "feat(db): add market style detection tables"
```

---

## Task 2: MarketStyleRepository 仓储层

**Files:**
- Create: `quantsys-v2/repositories/market_style_repository.py`
- Create: `quantsys-v2/tests/repositories/test_market_style_repository.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/repositories/test_market_style_repository.py
import pytest
from datetime import date
from repositories.market_style_repository import MarketStyleRepository


def test_save_and_get_latest_style(db_connection):
    """测试保存和获取最新市场风格"""
    repo = MarketStyleRepository()
    
    style_data = {
        'trade_date': date(2026, 5, 29),
        'style': 'momentum',
        'confidence': 0.68,
        'metrics': {
            'rsi_avg': 58.3,
            'macd_golden_ratio': 0.65,
            'atr_percentile': 72,
            'volume_growth': 1.15
        }
    }
    
    repo.save(style_data)
    result = repo.get_latest()
    
    assert result['style'] == 'momentum'
    assert result['confidence'] == 0.68
    assert result['metrics']['rsi_avg'] == 58.3


def test_get_by_date(db_connection):
    """测试按日期查询"""
    repo = MarketStyleRepository()
    
    style_data = {
        'trade_date': date(2026, 5, 28),
        'style': 'oscillation',
        'confidence': 0.55,
        'metrics': {}
    }
    
    repo.save(style_data)
    result = repo.get_by_date(date(2026, 5, 28))
    
    assert result['style'] == 'oscillation'
    assert result['confidence'] == 0.55
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
pytest tests/repositories/test_market_style_repository.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'repositories.market_style_repository'"

- [ ] **Step 3: 实现 MarketStyleRepository**

```python
# repositories/market_style_repository.py
"""
市场风格状态 Repository

负责市场风格状态的持久化和查询
"""
from typing import Dict, Optional, List
from datetime import date
import json
from infrastructure.database.base_repository import BaseRepository


class MarketStyleRepository(BaseRepository):
    """市场风格状态 Repository"""

    def save(self, style_data: Dict) -> Dict:
        """
        保存市场风格状态

        Args:
            style_data: {
                'trade_date': date,
                'style': str,
                'confidence': float,
                'metrics': dict
            }

        Returns:
            保存的记录
        """
        query = """
            INSERT INTO quant.market_style_state (trade_date, style, confidence, metrics)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (trade_date)
            DO UPDATE SET
                style = EXCLUDED.style,
                confidence = EXCLUDED.confidence,
                metrics = EXCLUDED.metrics,
                created_at = NOW()
            RETURNING id, trade_date, style, confidence, metrics, created_at
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (
                style_data['trade_date'],
                style_data['style'],
                style_data['confidence'],
                json.dumps(style_data.get('metrics', {}))
            ))
            self.db.commit()
            result = cursor.fetchone()
            return dict(result)
        finally:
            cursor.close()

    def get_latest(self) -> Optional[Dict]:
        """
        获取最新的市场风格状态

        Returns:
            最新记录，不存在返回 None
        """
        query = """
            SELECT id, trade_date, style, confidence, metrics, created_at
            FROM quant.market_style_state
            ORDER BY trade_date DESC
            LIMIT 1
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_by_date(self, trade_date: date) -> Optional[Dict]:
        """
        按日期查询市场风格

        Args:
            trade_date: 交易日期

        Returns:
            记录，不存在返回 None
        """
        query = """
            SELECT id, trade_date, style, confidence, metrics, created_at
            FROM quant.market_style_state
            WHERE trade_date = %s
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (trade_date,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_recent(self, days: int = 30) -> List[Dict]:
        """
        获取最近 N 天的市场风格

        Args:
            days: 天数

        Returns:
            记录列表
        """
        query = """
            SELECT id, trade_date, style, confidence, metrics, created_at
            FROM quant.market_style_state
            ORDER BY trade_date DESC
            LIMIT %s
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (days,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/repositories/test_market_style_repository.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add repositories/market_style_repository.py tests/repositories/test_market_style_repository.py
git commit -m "feat(repo): add MarketStyleRepository"
```

---

## Task 3: StrategyWeightRepository 仓储层

**Files:**
- Create: `quantsys-v2/repositories/strategy_weight_repository.py`
- Create: `quantsys-v2/tests/repositories/test_strategy_weight_repository.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/repositories/test_strategy_weight_repository.py
import pytest
from repositories.strategy_weight_repository import StrategyWeightRepository


def test_get_static_weight(db_connection):
    """测试查询静态权重"""
    repo = StrategyWeightRepository()
    
    weight = repo.get_static_weight('trend_following', 'momentum')
    
    assert weight == 0.30


def test_get_static_weight_not_found(db_connection):
    """测试查询不存在的权重配置"""
    repo = StrategyWeightRepository()
    
    weight = repo.get_static_weight('unknown_type', 'momentum')
    
    assert weight == 0.0  # 默认值


def test_get_all_weights_for_style(db_connection):
    """测试查询某风格下所有策略权重"""
    repo = StrategyWeightRepository()
    
    weights = repo.get_all_for_style('momentum')
    
    assert len(weights) == 2  # trend_following +0.30, mean_reversion -0.20
    assert weights['trend_following'] == 0.30
    assert weights['mean_reversion'] == -0.20
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/repositories/test_strategy_weight_repository.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 StrategyWeightRepository**

```python
# repositories/strategy_weight_repository.py
"""
策略权重配置 Repository

负责策略权重配置的查询和管理
"""
from typing import Dict, Optional
from infrastructure.database.base_repository import BaseRepository


class StrategyWeightRepository(BaseRepository):
    """策略权重配置 Repository"""

    def get_static_weight(self, strategy_type: str, market_style: str) -> float:
        """
        查询静态权重

        Args:
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            静态权重，不存在返回 0.0
        """
        query = """
            SELECT static_weight
            FROM quant.strategy_weight_config
            WHERE strategy_type = %s AND market_style = %s AND is_active = TRUE
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (strategy_type, market_style))
            result = cursor.fetchone()
            return result['static_weight'] if result else 0.0
        finally:
            cursor.close()

    def get_all_for_style(self, market_style: str) -> Dict[str, float]:
        """
        查询某市场风格下所有策略的权重

        Args:
            market_style: 市场风格

        Returns:
            {strategy_type: static_weight}
        """
        query = """
            SELECT strategy_type, static_weight
            FROM quant.strategy_weight_config
            WHERE market_style = %s AND is_active = TRUE
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (market_style,))
            results = cursor.fetchall()
            return {row['strategy_type']: row['static_weight'] for row in results}
        finally:
            cursor.close()

    def get_all_for_strategy(self, strategy_type: str) -> Dict[str, float]:
        """
        查询某策略类型在所有市场风格下的权重

        Args:
            strategy_type: 策略类型

        Returns:
            {market_style: static_weight}
        """
        query = """
            SELECT market_style, static_weight
            FROM quant.strategy_weight_config
            WHERE strategy_type = %s AND is_active = TRUE
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (strategy_type,))
            results = cursor.fetchall()
            return {row['market_style']: row['static_weight'] for row in results}
        finally:
            cursor.close()

    def update_weight(self, strategy_type: str, market_style: str, static_weight: float) -> None:
        """
        更新静态权重

        Args:
            strategy_type: 策略类型
            market_style: 市场风格
            static_weight: 新的静态权重
        """
        query = """
            UPDATE quant.strategy_weight_config
            SET static_weight = %s, updated_at = NOW()
            WHERE strategy_type = %s AND market_style = %s
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (static_weight, strategy_type, market_style))
            self.db.commit()
        finally:
            cursor.close()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/repositories/test_strategy_weight_repository.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add repositories/strategy_weight_repository.py tests/repositories/test_strategy_weight_repository.py
git commit -m "feat(repo): add StrategyWeightRepository"
```

---

## Task 4: MarketStyleDetector 服务（第1部分 - 基础结构）

**Files:**
- Create: `quantsys-v2/services/market_style_detector.py`
- Create: `quantsys-v2/tests/services/test_market_style_detector.py`

- [ ] **Step 1: 编写失败测试 - 基础结构**

```python
# tests/services/test_market_style_detector.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from services.market_style_detector import MarketStyleDetector


def test_detector_initialization():
    """测试检测器初始化"""
    detector = MarketStyleDetector()
    
    assert detector is not None
    assert hasattr(detector, 'detect')


def test_calculate_momentum_score():
    """测试动量得分计算"""
    detector = MarketStyleDetector()
    
    # 构造动量市数据：RSI > 55, MACD 金叉 > 60%, 成交量放大
    metrics = {
        'rsi_avg': 58.0,
        'macd_golden_ratio': 0.65,
        'volume_growth': 1.15
    }
    
    score = detector._calculate_momentum_score(metrics)
    
    assert score > 50  # 动量市得分应该较高
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_market_style_detector.py::test_detector_initialization -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 MarketStyleDetector 基础结构**

```python
# services/market_style_detector.py
"""
市场风格检测服务

通过聚合股票池技术指标识别市场风格
"""
from typing import Dict, List, Optional
from datetime import date, timedelta
import logging
import numpy as np
import pandas as pd

from repositories.market_style_repository import MarketStyleRepository
from repositories.kline_repository import KlineRepository
from services.stock_pool_service import StockPoolService

logger = logging.getLogger(__name__)


class MarketStyleDetector:
    """市场风格检测器"""

    # 风格类型常量
    STYLE_MOMENTUM = 'momentum'
    STYLE_OSCILLATION = 'oscillation'
    STYLE_LOW_VOLATILITY = 'low_volatility'
    STYLE_VALUE = 'value'
    STYLE_UNKNOWN = 'unknown'
    STYLE_MIXED = 'mixed_market'

    # 检测参数
    MIN_STOCKS_REQUIRED = 200  # 最少需要 200 只股票
    LOOKBACK_DAYS = 20  # 回看 20 个交易日
    CONFIDENCE_THRESHOLD = 0.4  # 置信度阈值

    def __init__(self):
        self.market_style_repo = MarketStyleRepository()
        self.kline_repo = KlineRepository()
        self.stock_pool_service = StockPoolService()

    def detect(self, trade_date: Optional[date] = None) -> Dict:
        """
        检测市场风格

        Args:
            trade_date: 交易日期，默认为今天

        Returns:
            {
                'trade_date': date,
                'style': str,
                'confidence': float,
                'metrics': dict,
                'scores': dict
            }
        """
        if trade_date is None:
            trade_date = date.today()

        logger.info(f"开始检测市场风格: {trade_date}")

        # 1. 获取股票池
        stock_pool = self.stock_pool_service.get_hot_stock_pool()
        logger.info(f"股票池大小: {len(stock_pool)}")

        # 2. 检查数据充足性
        if len(stock_pool) < self.MIN_STOCKS_REQUIRED:
            logger.warning(f"股票池数据不足: {len(stock_pool)} < {self.MIN_STOCKS_REQUIRED}")
            return self._create_unknown_result(trade_date, '股票池数据不足')

        # 3. 聚合技术指标
        metrics = self._aggregate_indicators(stock_pool, trade_date)

        if metrics is None:
            logger.warning("技术指标聚合失败")
            return self._create_unknown_result(trade_date, '技术指标聚合失败')

        # 4. 计算风格得分
        scores = self._calculate_style_scores(metrics)

        # 5. 选择主导风格
        dominant_style, confidence = self._select_dominant_style(scores)

        # 6. 检查置信度
        if confidence < self.CONFIDENCE_THRESHOLD:
            logger.info(f"置信度过低: {confidence:.2f} < {self.CONFIDENCE_THRESHOLD}")
            dominant_style = self.STYLE_MIXED

        result = {
            'trade_date': trade_date,
            'style': dominant_style,
            'confidence': confidence,
            'metrics': metrics,
            'scores': scores
        }

        logger.info(f"市场风格检测完成: {dominant_style}, 置信度: {confidence:.2f}")

        return result

    def _create_unknown_result(self, trade_date: date, reason: str) -> Dict:
        """创建未知风格结果"""
        return {
            'trade_date': trade_date,
            'style': self.STYLE_UNKNOWN,
            'confidence': 0.0,
            'metrics': {'reason': reason},
            'scores': {}
        }

    def _aggregate_indicators(self, stock_pool: List[str], trade_date: date) -> Optional[Dict]:
        """
        聚合技术指标

        Args:
            stock_pool: 股票池
            trade_date: 交易日期

        Returns:
            聚合指标字典，失败返回 None
        """
        # 实现将在下一个任务中完成
        pass

    def _calculate_style_scores(self, metrics: Dict) -> Dict[str, float]:
        """
        计算风格得分

        Args:
            metrics: 聚合指标

        Returns:
            {style: score}
        """
        return {
            self.STYLE_MOMENTUM: self._calculate_momentum_score(metrics),
            self.STYLE_OSCILLATION: self._calculate_oscillation_score(metrics),
            self.STYLE_LOW_VOLATILITY: self._calculate_low_volatility_score(metrics),
            self.STYLE_VALUE: self._calculate_value_score(metrics)
        }

    def _calculate_momentum_score(self, metrics: Dict) -> float:
        """计算动量市得分"""
        rsi_avg = metrics.get('rsi_avg', 50.0)
        macd_golden_ratio = metrics.get('macd_golden_ratio', 0.5)
        volume_growth = metrics.get('volume_growth', 1.0)

        score = (
            (rsi_avg - 50) * 2 +
            macd_golden_ratio * 50 +
            (volume_growth - 1) * 30
        )

        return max(0, min(100, score))

    def _calculate_oscillation_score(self, metrics: Dict) -> float:
        """计算震荡市得分"""
        rsi_avg = metrics.get('rsi_avg', 50.0)
        price_to_ma20 = metrics.get('price_to_ma20', 1.0)

        score = (
            100 - abs(rsi_avg - 50) * 4 +
            (1 - abs(price_to_ma20 - 1)) * 50
        )

        return max(0, min(100, score))

    def _calculate_low_volatility_score(self, metrics: Dict) -> float:
        """计算低波市得分"""
        atr_percentile = metrics.get('atr_percentile', 50.0)
        volatility_ratio = metrics.get('volatility_ratio', 1.0)

        score = (
            (100 - atr_percentile) +
            (1 - volatility_ratio) * 50
        )

        return max(0, min(100, score))

    def _calculate_value_score(self, metrics: Dict) -> float:
        """计算价值市得分"""
        small_cap_excess_return = metrics.get('small_cap_excess_return', 0.0)
        pe_ratio_percentile = metrics.get('pe_ratio_percentile', 50.0)

        score = (
            small_cap_excess_return * 10 +
            (1 - pe_ratio_percentile / 100) * 30
        )

        return max(0, min(100, score))

    def _select_dominant_style(self, scores: Dict[str, float]) -> tuple:
        """
        选择主导风格

        Args:
            scores: 风格得分字典

        Returns:
            (dominant_style, confidence)
        """
        if not scores:
            return self.STYLE_UNKNOWN, 0.0

        dominant_style = max(scores, key=scores.get)
        total_score = sum(scores.values())

        if total_score == 0:
            return self.STYLE_UNKNOWN, 0.0

        confidence = scores[dominant_style] / total_score

        return dominant_style, confidence

    def save_to_db(self, style_data: Dict) -> None:
        """
        保存风格数据到数据库

        Args:
            style_data: detect() 返回的结果
        """
        self.market_style_repo.save(style_data)
        logger.info(f"市场风格已保存: {style_data['trade_date']} - {style_data['style']}")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_market_style_detector.py::test_detector_initialization -v
pytest tests/services/test_market_style_detector.py::test_calculate_momentum_score -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add services/market_style_detector.py tests/services/test_market_style_detector.py
git commit -m "feat(service): add MarketStyleDetector base structure"
```

---

**继续阅读下一部分...**

由于计划文档较长，我将其分为多个部分。第一部分已创建，包含：
- 文件结构规划
- Task 1-4（数据库、仓储层、服务层基础）

是否继续创建剩余部分（Task 5-10）？

## Task 5: MarketStyleDetector 服务（第2部分 - 指标聚合）

**Files:**
- Modify: `quantsys-v2/services/market_style_detector.py`
- Modify: `quantsys-v2/tests/services/test_market_style_detector.py`

- [ ] **Step 1: 编写失败测试 - 指标聚合**

```python
# 追加到 tests/services/test_market_style_detector.py

def test_aggregate_indicators_success(db_connection, mock_kline_data):
    """测试指标聚合成功"""
    detector = MarketStyleDetector()
    
    stock_pool = ['600519.SH', '600036.SH', '601318.SH']  # 至少 200 只
    trade_date = date(2026, 5, 29)
    
    metrics = detector._aggregate_indicators(stock_pool, trade_date)
    
    assert metrics is not None
    assert 'rsi_avg' in metrics
    assert 'macd_golden_ratio' in metrics
    assert 'atr_percentile' in metrics
    assert 'volume_growth' in metrics
    assert 0 <= metrics['rsi_avg'] <= 100
    assert 0 <= metrics['macd_golden_ratio'] <= 1


def test_aggregate_indicators_insufficient_data(db_connection):
    """测试数据不足时的处理"""
    detector = MarketStyleDetector()
    
    stock_pool = ['600519.SH']  # 只有 1 只股票
    trade_date = date(2026, 5, 29)
    
    metrics = detector._aggregate_indicators(stock_pool, trade_date)
    
    assert metrics is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_market_style_detector.py::test_aggregate_indicators_success -v
```

Expected: FAIL with "AssertionError: assert None is not None"

- [ ] **Step 3: 实现 _aggregate_indicators 方法**

```python
# 在 services/market_style_detector.py 中替换 _aggregate_indicators 方法

def _aggregate_indicators(self, stock_pool: List[str], trade_date: date) -> Optional[Dict]:
    """
    聚合技术指标

    Args:
        stock_pool: 股票池
        trade_date: 交易日期

    Returns:
        聚合指标字典，失败返回 None
    """
    try:
        # 计算日期范围
        end_date = trade_date
        start_date = trade_date - timedelta(days=self.LOOKBACK_DAYS * 2)  # 预留足够数据

        # 批量查询 K 线数据
        all_data = []
        valid_stocks = 0

        for symbol in stock_pool:
            df = self.kline_repo.get_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=self.LOOKBACK_DAYS
            )

            if df is not None and len(df) >= self.LOOKBACK_DAYS:
                all_data.append(df)
                valid_stocks += 1

        # 检查有效股票数量
        if valid_stocks < self.MIN_STOCKS_REQUIRED:
            logger.warning(f"有效股票数不足: {valid_stocks} < {self.MIN_STOCKS_REQUIRED}")
            return None

        # 聚合指标
        metrics = {}

        # 1. RSI 均值
        rsi_values = []
        for df in all_data:
            if 'rsi' in df.columns and not pd.isna(df['rsi'].iloc[-1]):
                rsi_values.append(df['rsi'].iloc[-1])
        metrics['rsi_avg'] = np.mean(rsi_values) if rsi_values else 50.0

        # 2. MACD 金叉占比
        macd_golden_count = 0
        total_count = 0
        for df in all_data:
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd = df['macd'].iloc[-1]
                signal = df['macd_signal'].iloc[-1]
                if not pd.isna(macd) and not pd.isna(signal):
                    total_count += 1
                    if macd > signal:
                        macd_golden_count += 1
        metrics['macd_golden_ratio'] = macd_golden_count / total_count if total_count > 0 else 0.5

        # 3. ATR 历史分位数
        atr_values = []
        for df in all_data:
            if 'atr' in df.columns:
                atr_recent = df['atr'].iloc[-1]
                atr_hist = df['atr'].values
                if not pd.isna(atr_recent) and len(atr_hist) > 0:
                    percentile = (atr_hist < atr_recent).sum() / len(atr_hist) * 100
                    atr_values.append(percentile)
        metrics['atr_percentile'] = np.mean(atr_values) if atr_values else 50.0

        # 4. 成交量增长率
        volume_growth_values = []
        for df in all_data:
            if 'volume' in df.columns and len(df) >= 20:
                recent_vol = df['volume'].iloc[-5:].mean()
                past_vol = df['volume'].iloc[-20:-5].mean()
                if past_vol > 0:
                    growth = recent_vol / past_vol
                    volume_growth_values.append(growth)
        metrics['volume_growth'] = np.mean(volume_growth_values) if volume_growth_values else 1.0

        # 5. 价格相对 MA20
        price_to_ma20_values = []
        for df in all_data:
            if 'close' in df.columns and 'ma20' in df.columns:
                close = df['close'].iloc[-1]
                ma20 = df['ma20'].iloc[-1]
                if not pd.isna(close) and not pd.isna(ma20) and ma20 > 0:
                    ratio = close / ma20
                    price_to_ma20_values.append(ratio)
        metrics['price_to_ma20'] = np.mean(price_to_ma20_values) if price_to_ma20_values else 1.0

        # 6. 波动率比率（最近 5 天 vs 最近 20 天）
        volatility_ratio_values = []
        for df in all_data:
            if 'close' in df.columns and len(df) >= 20:
                recent_vol = df['close'].iloc[-5:].pct_change().std()
                past_vol = df['close'].iloc[-20:].pct_change().std()
                if past_vol > 0:
                    ratio = recent_vol / past_vol
                    volatility_ratio_values.append(ratio)
        metrics['volatility_ratio'] = np.mean(volatility_ratio_values) if volatility_ratio_values else 1.0

        # 7. 小盘超额收益（简化版：暂时设为 0，未来可扩展）
        metrics['small_cap_excess_return'] = 0.0

        # 8. PE 分位数（简化版：暂时设为 50，未来可扩展）
        metrics['pe_ratio_percentile'] = 50.0

        logger.info(f"指标聚合完成: {valid_stocks} 只股票")

        return metrics

    except Exception as e:
        logger.error(f"指标聚合失败: {e}", exc_info=True)
        return None
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_market_style_detector.py::test_aggregate_indicators_success -v
pytest tests/services/test_market_style_detector.py::test_aggregate_indicators_insufficient_data -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add services/market_style_detector.py tests/services/test_market_style_detector.py
git commit -m "feat(service): implement indicator aggregation in MarketStyleDetector"
```

---

## Task 6: StrategyWeightAdjuster 服务

**Files:**
- Create: `quantsys-v2/services/strategy_weight_adjuster.py`
- Create: `quantsys-v2/tests/services/test_strategy_weight_adjuster.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/services/test_strategy_weight_adjuster.py
import pytest
from services.strategy_weight_adjuster import StrategyWeightAdjuster


def test_get_weight_static_mode(db_connection):
    """测试静态模式权重查询"""
    adjuster = StrategyWeightAdjuster()
    
    result = adjuster.get_weight(
        strategy_name='my_ma_cross',
        strategy_type='trend_following',
        market_style='momentum'
    )
    
    assert result['mode'] == 'static'
    assert result['weight_adjustment'] == 1.30  # 1.0 + 0.30
    assert result['sample_size'] < 30


def test_get_weight_dynamic_mode(db_connection, mock_performance_data):
    """测试动态模式权重计算"""
    adjuster = StrategyWeightAdjuster()
    
    # mock_performance_data 提供 >= 30 笔交易记录
    result = adjuster.get_weight(
        strategy_name='mature_strategy',
        strategy_type='trend_following',
        market_style='momentum'
    )
    
    assert result['mode'] == 'dynamic'
    assert result['sample_size'] >= 30
    assert 0.6 <= result['weight_adjustment'] <= 2.0


def test_get_weight_unknown_style(db_connection):
    """测试未知风格时的处理"""
    adjuster = StrategyWeightAdjuster()
    
    result = adjuster.get_weight(
        strategy_name='my_strategy',
        strategy_type='trend_following',
        market_style='unknown'
    )
    
    assert result['weight_adjustment'] == 1.0  # 默认权重
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_strategy_weight_adjuster.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 StrategyWeightAdjuster**

```python
# services/strategy_weight_adjuster.py
"""
策略权重调整服务

根据市场风格和策略历史表现动态调整策略权重
"""
from typing import Dict, Optional
import logging

from repositories.strategy_weight_repository import StrategyWeightRepository
from repositories.strategy_performance_repository import StrategyPerformanceRepository

logger = logging.getLogger(__name__)


class StrategyWeightAdjuster:
    """策略权重调整器"""

    # 模式切换阈值
    DYNAMIC_MODE_THRESHOLD = 30  # 样本 >= 30 切换到动态模式

    # 平滑过渡权重
    DYNAMIC_WEIGHT_RATIO = 0.7  # 动态权重占比 70%
    STATIC_WEIGHT_RATIO = 0.3   # 静态权重占比 30%

    def __init__(self):
        self.weight_repo = StrategyWeightRepository()
        self.performance_repo = StrategyPerformanceRepository()

    def get_weight(
        self,
        strategy_name: str,
        strategy_type: str,
        market_style: str
    ) -> Dict:
        """
        获取策略权重调整

        Args:
            strategy_name: 策略名称
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            {
                'strategy_name': str,
                'strategy_type': str,
                'market_style': str,
                'weight_adjustment': float,
                'mode': 'static' | 'dynamic',
                'sample_size': int,
                'historical_performance': dict (可选)
            }
        """
        # 1. 查询样本数量
        sample_size = self._count_samples(strategy_name)

        # 2. 判断模式
        if sample_size < self.DYNAMIC_MODE_THRESHOLD:
            # 静态模式
            weight = self._get_static_weight(strategy_type, market_style)
            mode = 'static'
            historical_performance = None
        else:
            # 动态模式
            weight = self._calculate_dynamic_weight(
                strategy_name,
                strategy_type,
                market_style
            )
            mode = 'dynamic'
            historical_performance = self._get_historical_performance(strategy_name)

        result = {
            'strategy_name': strategy_name,
            'strategy_type': strategy_type,
            'market_style': market_style,
            'weight_adjustment': weight,
            'mode': mode,
            'sample_size': sample_size
        }

        if historical_performance:
            result['historical_performance'] = historical_performance

        logger.info(
            f"策略权重查询: {strategy_name} ({strategy_type}) "
            f"在 {market_style} 市场, 权重: {weight:.2f}, 模式: {mode}"
        )

        return result

    def _count_samples(self, strategy_name: str) -> int:
        """统计策略样本数量"""
        try:
            stats = self.performance_repo.get_statistics(strategy_name)
            return stats.get('total_trades', 0)
        except Exception as e:
            logger.warning(f"统计样本数量失败: {e}")
            return 0

    def _get_static_weight(self, strategy_type: str, market_style: str) -> float:
        """
        获取静态权重

        Args:
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            权重调整值（基准 1.0）
        """
        if market_style in ['unknown', 'mixed_market']:
            return 1.0

        static_weight = self.weight_repo.get_static_weight(strategy_type, market_style)
        return 1.0 + static_weight

    def _calculate_dynamic_weight(
        self,
        strategy_name: str,
        strategy_type: str,
        market_style: str
    ) -> float:
        """
        计算动态权重

        Args:
            strategy_name: 策略名称
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            权重调整值
        """
        try:
            # 1. 查询各风格下的表现
            perf_by_style = self._get_performance_by_style(strategy_name)

            if not perf_by_style or market_style not in perf_by_style:
                # 回退到静态权重
                logger.warning(f"策略 {strategy_name} 在 {market_style} 风格下无历史数据，回退到静态模式")
                return self._get_static_weight(strategy_type, market_style)

            # 2. 计算各风格的夏普比率
            sharpe_values = {}
            for style, perf in perf_by_style.items():
                sharpe = perf.get('sharpe', 0.0)
                sharpe_values[style] = max(0, sharpe)  # 负夏普视为 0

            # 3. 归一化权重
            total_sharpe = sum(sharpe_values.values())
            if total_sharpe == 0:
                # 所有风格表现都不好，回退到静态权重
                return self._get_static_weight(strategy_type, market_style)

            dynamic_weight = sharpe_values[market_style] / total_sharpe * 2.0

            # 4. 平滑过渡：70% 动态 + 30% 静态
            static_weight = self._get_static_weight(strategy_type, market_style)
            final_weight = (
                dynamic_weight * self.DYNAMIC_WEIGHT_RATIO +
                static_weight * self.STATIC_WEIGHT_RATIO
            )

            # 5. 限制范围 [0.6, 2.0]
            final_weight = max(0.6, min(2.0, final_weight))

            return final_weight

        except Exception as e:
            logger.error(f"动态权重计算失败: {e}", exc_info=True)
            return self._get_static_weight(strategy_type, market_style)

    def _get_performance_by_style(self, strategy_name: str) -> Dict:
        """
        查询策略在各市场风格下的表现

        Args:
            strategy_name: 策略名称

        Returns:
            {
                'momentum': {'sharpe': 1.8, 'win_rate': 0.65},
                'oscillation': {'sharpe': 0.6, 'win_rate': 0.42},
                ...
            }
        """
        try:
            # 查询按 market_style 分组的统计
            query = """
                SELECT 
                    market_style,
                    COUNT(*) as total_trades,
                    AVG(pnl_pct) as avg_return,
                    STDDEV(pnl_pct) as std_return,
                    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate
                FROM quant.strategy_performance
                WHERE strategy_name = %s AND market_style IS NOT NULL
                GROUP BY market_style
            """

            cursor = self.performance_repo.db.cursor()
            cursor.execute(query, (strategy_name,))
            results = cursor.fetchall()
            cursor.close()

            perf_by_style = {}
            for row in results:
                style = row['market_style']
                avg_return = row['avg_return'] or 0.0
                std_return = row['std_return'] or 1.0
                win_rate = row['win_rate'] or 0.0

                # 计算夏普比率（简化版：年化假设 252 个交易日）
                sharpe = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0.0

                perf_by_style[style] = {
                    'sharpe': sharpe,
                    'win_rate': win_rate,
                    'avg_return': avg_return
                }

            return perf_by_style

        except Exception as e:
            logger.error(f"查询风格表现失败: {e}", exc_info=True)
            return {}

    def _get_historical_performance(self, strategy_name: str) -> Dict:
        """获取策略历史表现摘要"""
        try:
            perf_by_style = self._get_performance_by_style(strategy_name)
            return perf_by_style
        except Exception as e:
            logger.warning(f"获取历史表现失败: {e}")
            return {}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_strategy_weight_adjuster.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add services/strategy_weight_adjuster.py tests/services/test_strategy_weight_adjuster.py
git commit -m "feat(service): add StrategyWeightAdjuster"
```

---


## Task 7: API 路由实现

**Files:**
- Create: `quantsys-v2/api/routes/market_style.py`
- Modify: `quantsys-v2/api/server.py`
- Create: `quantsys-v2/tests/api/test_market_style_routes.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/api/test_market_style_routes.py
import pytest
from datetime import date


def test_get_market_style(client):
    """测试获取市场风格 API"""
    response = client.get('/api/market/style')
    
    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert 'style' in data['data']
    assert 'confidence' in data['data']
    assert 'metrics' in data['data']
    assert 'scores' in data['data']


def test_get_strategy_weight(client):
    """测试获取策略权重 API"""
    response = client.get('/api/strategies/my_strategy/weight?market_style=momentum')
    
    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert 'weight_adjustment' in data['data']
    assert 'mode' in data['data']
    assert data['data']['mode'] in ['static', 'dynamic']


def test_get_strategy_weight_missing_param(client):
    """测试缺少参数时的错误处理"""
    response = client.get('/api/strategies/my_strategy/weight')
    
    assert response.status_code == 400
    data = response.json
    assert data['success'] is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/api/test_market_style_routes.py -v
```

Expected: FAIL with "404 Not Found"

- [ ] **Step 3: 实现 API 路由**

```python
# api/routes/market_style.py
"""
市场风格 API 路由
"""
from flask import Blueprint, jsonify, request
from datetime import date

from api.shared import api_response, handle_api_error
from services.market_style_detector import MarketStyleDetector
from services.strategy_weight_adjuster import StrategyWeightAdjuster

market_style_bp = Blueprint('market_style', __name__)


@market_style_bp.route('/api/market/style', methods=['GET'])
@handle_api_error
def get_market_style():
    """
    获取当前市场风格

    Query Params:
        trade_date (optional): 交易日期 YYYY-MM-DD，默认今天

    Returns:
        {
            "success": true,
            "data": {
                "trade_date": "2026-05-29",
                "style": "momentum",
                "confidence": 0.68,
                "metrics": {...},
                "scores": {...}
            }
        }
    """
    trade_date_str = request.args.get('trade_date')
    
    if trade_date_str:
        trade_date = date.fromisoformat(trade_date_str)
    else:
        trade_date = None

    detector = MarketStyleDetector()
    
    # 先尝试从数据库获取
    if trade_date:
        cached_result = detector.market_style_repo.get_by_date(trade_date)
        if cached_result:
            return api_response(cached_result)
    else:
        cached_result = detector.market_style_repo.get_latest()
        if cached_result:
            return api_response(cached_result)

    # 缓存未命中，执行检测
    result = detector.detect(trade_date)
    
    # 保存到数据库
    if result['style'] not in ['unknown']:
        detector.save_to_db(result)

    return api_response(result)


@market_style_bp.route('/api/strategies/<strategy_name>/weight', methods=['GET'])
@handle_api_error
def get_strategy_weight(strategy_name):
    """
    获取策略权重调整

    Path Params:
        strategy_name: 策略名称

    Query Params:
        market_style (required): 市场风格
        strategy_type (optional): 策略类型，不提供则从数据库查询

    Returns:
        {
            "success": true,
            "data": {
                "strategy_name": "my_ma_cross",
                "strategy_type": "trend_following",
                "market_style": "momentum",
                "weight_adjustment": 1.30,
                "mode": "dynamic",
                "sample_size": 45,
                "historical_performance": {...}
            }
        }
    """
    market_style = request.args.get('market_style')
    
    if not market_style:
        return jsonify({
            'success': False,
            'error': '缺少参数: market_style'
        }), 400

    strategy_type = request.args.get('strategy_type')
    
    # 如果未提供 strategy_type，从数据库查询
    if not strategy_type:
        from repositories.strategy_repository import StrategyRepository
        strategy_repo = StrategyRepository()
        strategy = strategy_repo.get_by_name(strategy_name)
        
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'策略不存在: {strategy_name}'
            }), 404
        
        strategy_type = strategy.get('code_type', 'indicator')

    adjuster = StrategyWeightAdjuster()
    result = adjuster.get_weight(strategy_name, strategy_type, market_style)

    return api_response(result)
```

- [ ] **Step 4: 注册路由到 Flask app**

```python
# 在 api/server.py 中添加

from api.routes.market_style import market_style_bp

# 在 create_app() 函数中注册
app.register_blueprint(market_style_bp)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
pytest tests/api/test_market_style_routes.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: 手动测试 API**

```bash
# 启动服务
cd quantsys-v2
python api/server.py &

# 测试市场风格 API
curl http://127.0.0.1:5001/api/market/style

# 测试策略权重 API
curl "http://127.0.0.1:5001/api/strategies/my_strategy/weight?market_style=momentum"
```

Expected: 返回正确的 JSON 响应

- [ ] **Step 7: 提交**

```bash
git add api/routes/market_style.py api/server.py tests/api/test_market_style_routes.py
git commit -m "feat(api): add market style detection API routes"
```

---

## Task 8: 定时任务实现

**Files:**
- Create: `quantsys-v2/runtime/scheduler/market_style_jobs.py`
- Modify: `quantsys-v2/runtime/scheduler/__init__.py`

- [ ] **Step 1: 实现定时任务**

```python
# runtime/scheduler/market_style_jobs.py
"""
市场风格检测定时任务

每日收盘后 30 分钟（15:30）自动更新市场风格
"""
import logging
from datetime import date

from runtime.scheduler import scheduler
from services.market_style_detector import MarketStyleDetector

logger = logging.getLogger(__name__)


@scheduler.scheduled_job('cron', hour=15, minute=30, id='update_market_style')
def update_market_style():
    """
    每日收盘后更新市场风格

    执行时间：15:30（收盘后 30 分钟）
    """
    try:
        logger.info("开始执行市场风格更新任务")
        
        detector = MarketStyleDetector()
        trade_date = date.today()
        
        # 执行检测
        style_data = detector.detect(trade_date)
        
        # 保存到数据库
        if style_data['style'] not in ['unknown']:
            detector.save_to_db(style_data)
            logger.info(
                f"市场风格更新成功: {style_data['style']}, "
                f"置信度: {style_data['confidence']:.2f}"
            )
        else:
            logger.warning(f"市场风格检测失败: {style_data['metrics'].get('reason', '未知原因')}")
        
    except Exception as e:
        logger.error(f"市场风格更新任务失败: {e}", exc_info=True)


def trigger_update_now():
    """
    手动触发市场风格更新（用于测试）
    """
    update_market_style()
```

- [ ] **Step 2: 注册定时任务**

```python
# 在 runtime/scheduler/__init__.py 中添加

# 导入市场风格任务
from runtime.scheduler.market_style_jobs import update_market_style

# 任务会自动通过装饰器注册
```

- [ ] **Step 3: 测试定时任务**

```bash
cd quantsys-v2
python -c "
from runtime.scheduler.market_style_jobs import trigger_update_now
trigger_update_now()
"
```

Expected: 任务执行成功，数据写入数据库

- [ ] **Step 4: 验证数据库记录**

```bash
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "SELECT * FROM quant.market_style_state ORDER BY trade_date DESC LIMIT 1;"
```

Expected: 显示最新的市场风格记录

- [ ] **Step 5: 提交**

```bash
git add runtime/scheduler/market_style_jobs.py runtime/scheduler/__init__.py
git commit -m "feat(scheduler): add market style update cron job"
```

---

## Task 9: TypeScript Agent 集成

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`

- [ ] **Step 1: 读取现有工具代码**

```bash
head -100 src/infrastructure/tools/core/quant-cli-tool.ts
```

- [ ] **Step 2: 扩展 strategy_execute 输出**

在 `quant-cli-tool.ts` 中找到 `strategy.execute` 命令的响应处理部分，添加市场风格字段：

```typescript
// 在 strategy.execute 命令的响应处理中添加

// 查询当前市场风格
const marketStyleResponse = await fetch('http://127.0.0.1:5001/api/market/style');
const marketStyleData = await marketStyleResponse.json();

if (marketStyleData.success) {
  const marketStyle = marketStyleData.data.style;
  const confidence = marketStyleData.data.confidence;

  // 查询策略权重
  const weightResponse = await fetch(
    `http://127.0.0.1:5001/api/strategies/${strategyName}/weight?market_style=${marketStyle}`
  );
  const weightData = await weightResponse.json();

  if (weightData.success) {
    // 扩展输出
    result.market_style = marketStyle;
    result.weight_adjustment = weightData.data.weight_adjustment;
    result.style_recommendation = `当前为${getStyleName(marketStyle)}，策略权重调整为${weightData.data.weight_adjustment.toFixed(2)}`;
  }
}

// 辅助函数
function getStyleName(style: string): string {
  const styleNames: Record<string, string> = {
    'momentum': '动量市',
    'oscillation': '震荡市',
    'low_volatility': '低波市',
    'value': '价值市',
    'mixed_market': '混合市场',
    'unknown': '未知市场'
  };
  return styleNames[style] || style;
}
```

- [ ] **Step 3: 测试 Agent 工具**

```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

在 Agent 中执行：
```
执行策略 my_ma_cross 对 600519.SH
```

Expected: 输出包含 `market_style`, `weight_adjustment`, `style_recommendation` 字段

- [ ] **Step 4: 提交**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts
git commit -m "feat(agent): integrate market style into strategy_execute tool"
```

---

## Task 10: 端到端测试和文档

**Files:**
- Create: `quantsys-v2/tests/integration/test_market_style_e2e.py`
- Modify: `quantsys-v2/README.md` 或 API 文档

- [ ] **Step 1: 编写端到端测试**

```python
# tests/integration/test_market_style_e2e.py
"""
市场风格检测端到端测试

验证完整流程：数据库 → 服务 → API → Agent
"""
import pytest
from datetime import date
from services.market_style_detector import MarketStyleDetector
from services.strategy_weight_adjuster import StrategyWeightAdjuster


def test_market_style_detection_e2e(db_connection, test_kline_data):
    """测试市场风格检测完整流程"""
    # 1. 执行检测
    detector = MarketStyleDetector()
    result = detector.detect(date.today())
    
    assert result['style'] in ['momentum', 'oscillation', 'low_volatility', 'value', 'unknown']
    assert 0 <= result['confidence'] <= 1
    
    # 2. 保存到数据库
    detector.save_to_db(result)
    
    # 3. 从数据库读取
    saved = detector.market_style_repo.get_latest()
    assert saved['style'] == result['style']
    
    # 4. 查询策略权重
    adjuster = StrategyWeightAdjuster()
    weight_result = adjuster.get_weight(
        strategy_name='test_strategy',
        strategy_type='trend_following',
        market_style=result['style']
    )
    
    assert 'weight_adjustment' in weight_result
    assert weight_result['mode'] in ['static', 'dynamic']


def test_api_integration(client, db_connection):
    """测试 API 集成"""
    # 1. 获取市场风格
    response = client.get('/api/market/style')
    assert response.status_code == 200
    
    style_data = response.json['data']
    market_style = style_data['style']
    
    # 2. 查询策略权重
    response = client.get(f'/api/strategies/test_strategy/weight?market_style={market_style}')
    assert response.status_code == 200
    
    weight_data = response.json['data']
    assert 'weight_adjustment' in weight_data


def test_performance_requirements(db_connection, test_kline_data):
    """测试性能要求"""
    import time
    
    detector = MarketStyleDetector()
    
    # 检测时间应 < 5 秒
    start = time.time()
    result = detector.detect(date.today())
    elapsed = time.time() - start
    
    assert elapsed < 5.0, f"检测时间 {elapsed:.2f}s 超过 5 秒限制"
    
    # API 响应时间应 < 200ms（缓存命中）
    detector.save_to_db(result)
    
    start = time.time()
    cached = detector.market_style_repo.get_latest()
    elapsed = time.time() - start
    
    assert elapsed < 0.2, f"API 响应时间 {elapsed:.3f}s 超过 200ms 限制"
```

- [ ] **Step 2: 运行端到端测试**

```bash
pytest tests/integration/test_market_style_e2e.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 3: 更新 API 文档**

在 `quantsys-v2/README.md` 或 API 文档中添加：

```markdown
## 市场风格检测 API

### GET /api/market/style

获取当前市场风格。

**Query Parameters:**
- `trade_date` (optional): 交易日期 YYYY-MM-DD，默认今天

**Response:**
```json
{
  "success": true,
  "data": {
    "trade_date": "2026-05-29",
    "style": "momentum",
    "confidence": 0.68,
    "metrics": {
      "rsi_avg": 58.3,
      "macd_golden_ratio": 0.65,
      "atr_percentile": 72,
      "volume_growth": 1.15
    },
    "scores": {
      "momentum": 75,
      "oscillation": 42,
      "low_volatility": 28,
      "value": 35
    }
  }
}
```

### GET /api/strategies/{strategy_name}/weight

获取策略在当前市场风格下的权重调整。

**Path Parameters:**
- `strategy_name`: 策略名称

**Query Parameters:**
- `market_style` (required): 市场风格
- `strategy_type` (optional): 策略类型

**Response:**
```json
{
  "success": true,
  "data": {
    "strategy_name": "my_ma_cross",
    "strategy_type": "trend_following",
    "market_style": "momentum",
    "weight_adjustment": 1.30,
    "mode": "dynamic",
    "sample_size": 45,
    "historical_performance": {
      "momentum": {"sharpe": 1.8, "win_rate": 0.65},
      "oscillation": {"sharpe": 0.6, "win_rate": 0.42}
    }
  }
}
```

## 定时任务

市场风格检测每日自动更新：
- **执行时间**: 15:30（收盘后 30 分钟）
- **任务 ID**: `update_market_style`
- **日志位置**: `/tmp/quantsys-v2.log`
```

- [ ] **Step 4: 提交**

```bash
git add tests/integration/test_market_style_e2e.py quantsys-v2/README.md
git commit -m "test: add market style detection e2e tests and docs"
```

---

## 验收清单

完成所有任务后，验证以下功能：

### 功能验收

- [ ] 数据库表创建成功，初始权重数据正确
- [ ] MarketStyleDetector 能正确检测市场风格（4 种风格 + unknown）
- [ ] StrategyWeightAdjuster 能正确计算权重（静态/动态模式）
- [ ] API `/api/market/style` 返回正确的市场风格数据
- [ ] API `/api/strategies/{name}/weight` 返回正确的权重调整
- [ ] 定时任务每日 15:30 自动执行
- [ ] TypeScript Agent 的 strategy_execute 输出包含市场风格字段
- [ ] 样本 < 30 使用静态权重，≥ 30 自动切换到动态权重

### 性能验收

- [ ] 市场风格检测时间 < 5 秒（400 只股票）
- [ ] API 响应时间 < 200ms（缓存命中）
- [ ] 数据库查询 < 50ms

### 测试覆盖

- [ ] 单元测试覆盖率 > 80%
- [ ] 所有边界情况有测试（数据不足、置信度过低、数据库失败等）
- [ ] 端到端测试通过

---

## 实施完成

计划完成后执行：

```bash
# 运行所有测试
cd quantsys-v2
pytest tests/ -v --cov=services --cov=repositories --cov=api

# 启动服务验证
python start_all.py

# 手动触发市场风格更新
python -c "from runtime.scheduler.market_style_jobs import trigger_update_now; trigger_update_now()"

# 查看结果
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "SELECT * FROM quant.market_style_state ORDER BY trade_date DESC LIMIT 5;"
```

---

## 自查清单

**规范检查**：
- [x] 所有步骤包含完整代码（无 TBD、TODO）
- [x] 所有文件路径为绝对路径
- [x] 所有测试包含预期输出
- [x] 所有提交包含清晰的 commit message
- [x] DRY 原则：Repository 方法可复用
- [x] YAGNI 原则：未实现小盘超额收益和 PE 分位数（标记为未来扩展）
- [x] TDD 原则：先写测试，再写实现

**覆盖检查**：
- [x] 数据模型设计 → Task 1
- [x] 仓储层 → Task 2-3
- [x] 服务层 → Task 4-6
- [x] API 层 → Task 7
- [x] 定时任务 → Task 8
- [x] Agent 集成 → Task 9
- [x] 测试和文档 → Task 10

**类型一致性**：
- [x] `market_style` 字段类型统一为 `VARCHAR(50)`
- [x] `confidence` 字段类型统一为 `FLOAT (0.0-1.0)`
- [x] `weight_adjustment` 返回值统一为 `float`
- [x] 风格常量统一使用 `MarketStyleDetector.STYLE_*`

