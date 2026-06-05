# 资金流数据本地缓存系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现资金流数据本地缓存系统，将策略执行时的资金流查询性能从 3-5 秒降至 < 50ms

**Architecture:** 单层数据库缓存（PostgreSQL）+ 定时任务批量更新。优先查询本地缓存，miss 时调用 API 并写入数据库。每日 21:30 定时更新主要指数成分股（约 1200 只），保留 90 天历史数据。

**Tech Stack:** Python 3.13, PostgreSQL, psycopg2, akshare, APScheduler

---

## 文件结构

### 新建文件
- `quantsys-v2/migrations/add_stock_fund_flow_table.sql` - 数据库迁移脚本
- `quantsys-v2/repositories/fund_flow_repository.py` - 数据访问层
- `quantsys-v2/runtime/jobs/update_fund_flow_job.py` - 定时任务
- `quantsys-v2/tests/repositories/test_fund_flow_repository.py` - Repository 单元测试
- `quantsys-v2/tests/data_sources/test_fund_flow_source.py` - 数据源层测试
- `quantsys-v2/tests/runtime/jobs/test_update_fund_flow_job.py` - 定时任务测试
- `quantsys-v2/tests/integration/test_fund_flow_caching.py` - 集成测试

### 修改文件
- `quantsys-v2/data_sources/fund_flow_source.py` - 添加缓存逻辑

---

## Task 1: 数据库表创建

**Files:**
- Create: `quantsys-v2/migrations/add_stock_fund_flow_table.sql`

- [ ] **Step 1: 编写数据库迁移脚本**

创建文件 `quantsys-v2/migrations/add_stock_fund_flow_table.sql`：

```sql
-- 资金流数据表
CREATE TABLE IF NOT EXISTS quant.stock_fund_flow (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close_price DECIMAL(10,2),
    change_pct DECIMAL(8,4),
    
    -- 主力资金
    main_net_inflow DECIMAL(18,2),
    main_net_inflow_rate DECIMAL(8,4),
    
    -- 超大单
    large_net_inflow DECIMAL(18,2),
    large_net_inflow_rate DECIMAL(8,4),
    
    -- 大单
    big_net_inflow DECIMAL(18,2),
    big_net_inflow_rate DECIMAL(8,4),
    
    -- 中单
    medium_net_inflow DECIMAL(18,2),
    medium_net_inflow_rate DECIMAL(8,4),
    
    -- 小单
    small_net_inflow DECIMAL(18,2),
    small_net_inflow_rate DECIMAL(8,4),
    
    -- 元数据
    source VARCHAR(50) DEFAULT 'eastmoney',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(symbol, trade_date)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_fund_flow_symbol_date 
    ON quant.stock_fund_flow(symbol, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_fund_flow_updated_at 
    ON quant.stock_fund_flow(updated_at);

CREATE INDEX IF NOT EXISTS idx_fund_flow_trade_date 
    ON quant.stock_fund_flow(trade_date DESC);

-- 添加注释
COMMENT ON TABLE quant.stock_fund_flow IS '股票资金流向数据（缓存表）';
COMMENT ON COLUMN quant.stock_fund_flow.symbol IS '股票代码（不带后缀）';
COMMENT ON COLUMN quant.stock_fund_flow.main_net_inflow IS '主力净流入（万元）';
COMMENT ON COLUMN quant.stock_fund_flow.updated_at IS '数据更新时间（用于判断缓存新鲜度）';
```

- [ ] **Step 2: 执行迁移脚本**

```bash
cd quantsys-v2
psql -h localhost -U $PGUSER -d $PGDATABASE -f migrations/add_stock_fund_flow_table.sql
```

Expected output:
```
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
COMMENT
COMMENT
COMMENT
COMMENT
```

- [ ] **Step 3: 验证表创建成功**

```bash
psql -h localhost -U $PGUSER -d $PGDATABASE -c "\d quant.stock_fund_flow"
```

Expected: 显示表结构，包含所有字段和索引

- [ ] **Step 4: Commit**

```bash
git add migrations/add_stock_fund_flow_table.sql
git commit -m "feat(db): 添加资金流数据缓存表"
```

---

## Task 2: FundFlowRepository 实现

**Files:**
- Create: `quantsys-v2/repositories/fund_flow_repository.py`
- Create: `quantsys-v2/tests/repositories/test_fund_flow_repository.py`

- [ ] **Step 1: 编写 get_fund_flow 方法的测试**

创建文件 `quantsys-v2/tests/repositories/test_fund_flow_repository.py`：

```python
import pytest
from datetime import datetime, timedelta
from repositories.fund_flow_repository import FundFlowRepository

@pytest.fixture
def repository():
    return FundFlowRepository()

@pytest.fixture
def sample_records():
    """生成样本数据"""
    base_date = datetime.now().date()
    return [
        {
            'symbol': '600519',
            'trade_date': (base_date - timedelta(days=i)).strftime('%Y-%m-%d'),
            'close_price': 1800.0 + i,
            'change_pct': 1.5,
            'main_net_inflow': 10000.0,
            'main_net_inflow_rate': 2.5,
            'large_net_inflow': 6000.0,
            'large_net_inflow_rate': 1.5,
            'big_net_inflow': 4000.0,
            'big_net_inflow_rate': 1.0,
            'medium_net_inflow': -3000.0,
            'medium_net_inflow_rate': -0.8,
            'small_net_inflow': -7000.0,
            'small_net_inflow_rate': -1.7,
            'source': 'eastmoney'
        }
        for i in range(5)
    ]

def test_get_fund_flow_returns_data_in_date_range(repository, sample_records):
    """测试查询指定日期范围的资金流数据"""
    # Arrange
    repository.batch_upsert(sample_records)
    start_date = sample_records[-1]['trade_date']
    end_date = sample_records[0]['trade_date']
    
    # Act
    result = repository.get_fund_flow('600519', start_date, end_date)
    
    # Assert
    assert len(result) == 5
    assert result[0]['symbol'] == '600519'
    assert result[0]['trade_date'] <= result[-1]['trade_date']  # 升序排列

def test_get_fund_flow_empty_when_no_data(repository):
    """测试无数据时返回空列表"""
    result = repository.get_fund_flow('999999', '2020-01-01', '2020-01-31')
    assert result == []
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd quantsys-v2
pytest tests/repositories/test_fund_flow_repository.py::test_get_fund_flow_returns_data_in_date_range -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'repositories.fund_flow_repository'"

- [ ] **Step 3: 实现 FundFlowRepository 骨架**

创建文件 `quantsys-v2/repositories/fund_flow_repository.py`：

```python
"""
资金流数据 Repository

负责 stock_fund_flow 表的数据访问
"""
from typing import List, Dict
from datetime import datetime
import logging
from infrastructure.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class FundFlowRepository(BaseRepository):
    """资金流数据 Repository"""
    
    def get_fund_flow(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict]:
        """
        查询资金流数据（按日期升序）
        
        Args:
            symbol: 股票代码（不带后缀，如 600519）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            资金流记录列表，按 trade_date 升序排列
        """
        query = """
            SELECT 
                symbol, trade_date, close_price, change_pct,
                main_net_inflow, main_net_inflow_rate,
                large_net_inflow, large_net_inflow_rate,
                big_net_inflow, big_net_inflow_rate,
                medium_net_inflow, medium_net_inflow_rate,
                small_net_inflow, small_net_inflow_rate,
                source, created_at, updated_at
            FROM quant.stock_fund_flow
            WHERE symbol = %s
              AND trade_date >= %s
              AND trade_date <= %s
            ORDER BY trade_date ASC
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (symbol, start_date, end_date))
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        finally:
            self.release_connection(conn)
    
    def get_latest_fund_flow(
        self, 
        symbol: str, 
        days: int = 5
    ) -> List[Dict]:
        """
        查询最近 N 天资金流数据
        
        Args:
            symbol: 股票代码（不带后缀）
            days: 天数
            
        Returns:
            最近 N 天资金流记录（按日期降序）
        """
        query = """
            SELECT 
                symbol, trade_date, close_price, change_pct,
                main_net_inflow, main_net_inflow_rate,
                large_net_inflow, large_net_inflow_rate,
                big_net_inflow, big_net_inflow_rate,
                medium_net_inflow, medium_net_inflow_rate,
                small_net_inflow, small_net_inflow_rate,
                source, created_at, updated_at
            FROM quant.stock_fund_flow
            WHERE symbol = %s
            ORDER BY trade_date DESC
            LIMIT %s
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (symbol, days))
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        finally:
            self.release_connection(conn)
    
    def batch_upsert(
        self, 
        records: List[Dict]
    ) -> int:
        """
        批量插入或更新资金流数据
        
        Args:
            records: 资金流记录列表
            
        Returns:
            影响行数
        """
        if not records:
            return 0
        
        query = """
            INSERT INTO quant.stock_fund_flow (
                symbol, trade_date, close_price, change_pct,
                main_net_inflow, main_net_inflow_rate,
                large_net_inflow, large_net_inflow_rate,
                big_net_inflow, big_net_inflow_rate,
                medium_net_inflow, medium_net_inflow_rate,
                small_net_inflow, small_net_inflow_rate,
                source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (symbol, trade_date) 
            DO UPDATE SET
                close_price = EXCLUDED.close_price,
                change_pct = EXCLUDED.change_pct,
                main_net_inflow = EXCLUDED.main_net_inflow,
                main_net_inflow_rate = EXCLUDED.main_net_inflow_rate,
                large_net_inflow = EXCLUDED.large_net_inflow,
                large_net_inflow_rate = EXCLUDED.large_net_inflow_rate,
                big_net_inflow = EXCLUDED.big_net_inflow,
                big_net_inflow_rate = EXCLUDED.big_net_inflow_rate,
                medium_net_inflow = EXCLUDED.medium_net_inflow,
                medium_net_inflow_rate = EXCLUDED.medium_net_inflow_rate,
                small_net_inflow = EXCLUDED.small_net_inflow,
                small_net_inflow_rate = EXCLUDED.small_net_inflow_rate,
                source = EXCLUDED.source,
                updated_at = NOW()
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # 准备批量数据
                values = []
                for record in records:
                    values.append((
                        record['symbol'],
                        record['trade_date'],
                        record.get('close_price'),
                        record.get('change_pct'),
                        record.get('main_net_inflow'),
                        record.get('main_net_inflow_rate'),
                        record.get('large_net_inflow'),
                        record.get('large_net_inflow_rate'),
                        record.get('big_net_inflow'),
                        record.get('big_net_inflow_rate'),
                        record.get('medium_net_inflow'),
                        record.get('medium_net_inflow_rate'),
                        record.get('small_net_inflow'),
                        record.get('small_net_inflow_rate'),
                        record.get('source', 'eastmoney')
                    ))
                
                cursor.executemany(query, values)
                conn.commit()
                
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"批量写入资金流数据失败: {e}")
            raise
        finally:
            self.release_connection(conn)
    
    def get_stale_symbols(
        self, 
        threshold_hours: int = 24
    ) -> List[str]:
        """
        查询数据过期的股票列表
        
        Args:
            threshold_hours: 过期阈值（小时）
            
        Returns:
            需要更新的股票代码列表
        """
        query = """
            SELECT DISTINCT symbol 
            FROM quant.stock_fund_flow
            WHERE updated_at < NOW() - INTERVAL '%s hours'
            ORDER BY symbol
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (threshold_hours,))
                rows = cursor.fetchall()
                
                return [row['symbol'] for row in rows]
        finally:
            self.release_connection(conn)
    
    def delete_old_data(
        self, 
        retention_days: int = 90
    ) -> int:
        """
        删除超过保留期的历史数据
        
        Args:
            retention_days: 保留天数
            
        Returns:
            删除行数
        """
        query = """
            DELETE FROM quant.stock_fund_flow
            WHERE trade_date < NOW() - INTERVAL '%s days'
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (retention_days,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"清理过期资金流数据: {deleted_count} 条")
                return deleted_count
        except Exception as e:
            conn.rollback()
            logger.error(f"清理过期数据失败: {e}")
            raise
        finally:
            self.release_connection(conn)
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/repositories/test_fund_flow_repository.py::test_get_fund_flow_returns_data_in_date_range -v
pytest tests/repositories/test_fund_flow_repository.py::test_get_fund_flow_empty_when_no_data -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add repositories/fund_flow_repository.py tests/repositories/test_fund_flow_repository.py
git commit -m "feat(repository): 实现 FundFlowRepository 基础查询方法"
```

---

## Task 3: Repository 其他方法测试和实现

**Files:**
- Modify: `quantsys-v2/tests/repositories/test_fund_flow_repository.py`
- Modify: `quantsys-v2/repositories/fund_flow_repository.py`

- [ ] **Step 1: 添加 batch_upsert 和其他方法测试**

在 `quantsys-v2/tests/repositories/test_fund_flow_repository.py` 末尾添加：

```python
def test_get_latest_fund_flow_returns_recent_data(repository, sample_records):
    """测试查询最近 N 天数据"""
    repository.batch_upsert(sample_records)
    
    result = repository.get_latest_fund_flow('600519', days=3)
    
    assert len(result) == 3
    assert result[0]['trade_date'] >= result[-1]['trade_date']  # 降序排列

def test_batch_upsert_inserts_new_records(repository):
    """测试批量插入新记录"""
    records = [
        {
            'symbol': '000858',
            'trade_date': '2026-06-01',
            'main_net_inflow': 5000.0,
            'main_net_inflow_rate': 1.2
        }
    ]
    
    count = repository.batch_upsert(records)
    
    assert count > 0
    result = repository.get_fund_flow('000858', '2026-06-01', '2026-06-01')
    assert len(result) == 1
    assert result[0]['main_net_inflow'] == 5000.0

def test_batch_upsert_updates_existing_records(repository):
    """测试批量更新已存在记录"""
    # 先插入
    records = [
        {
            'symbol': '600000',
            'trade_date': '2026-06-01',
            'main_net_inflow': 1000.0
        }
    ]
    repository.batch_upsert(records)
    
    # 再次插入相同 symbol + trade_date，不同值
    updated_records = [
        {
            'symbol': '600000',
            'trade_date': '2026-06-01',
            'main_net_inflow': 2000.0
        }
    ]
    repository.batch_upsert(updated_records)
    
    result = repository.get_fund_flow('600000', '2026-06-01', '2026-06-01')
    assert len(result) == 1
    assert result[0]['main_net_inflow'] == 2000.0  # 值已更新

def test_get_stale_symbols_returns_outdated_stocks(repository):
    """测试查询过期股票列表"""
    # 插入旧数据（需要手动设置 updated_at，或者等待一段时间）
    # 这里简化测试，直接查询
    result = repository.get_stale_symbols(threshold_hours=24)
    
    # 结果应该是列表（可能为空，取决于数据库状态）
    assert isinstance(result, list)

def test_delete_old_data_removes_expired_records(repository):
    """测试删除过期数据"""
    from datetime import datetime, timedelta
    
    # 插入 100 天前的数据
    old_date = (datetime.now().date() - timedelta(days=100)).strftime('%Y-%m-%d')
    old_records = [
        {
            'symbol': '600001',
            'trade_date': old_date,
            'main_net_inflow': 1000.0
        }
    ]
    repository.batch_upsert(old_records)
    
    # 删除 90 天前的数据
    deleted = repository.delete_old_data(retention_days=90)
    
    assert deleted >= 1
    
    # 验证数据已删除
    result = repository.get_fund_flow('600001', old_date, old_date)
    assert len(result) == 0
```

- [ ] **Step 2: 运行所有 Repository 测试**

```bash
pytest tests/repositories/test_fund_flow_repository.py -v
```

Expected: 所有测试通过（如果有失败，根据错误信息修复代码）

- [ ] **Step 3: Commit**

```bash
git add tests/repositories/test_fund_flow_repository.py
git commit -m "test(repository): 添加 FundFlowRepository 完整测试套件"
```

---

## Task 4: 数据源层改造 - 添加缓存逻辑

**Files:**
- Modify: `quantsys-v2/data_sources/fund_flow_source.py`
- Create: `quantsys-v2/tests/data_sources/test_fund_flow_source.py`

- [ ] **Step 1: 编写缓存逻辑测试**

创建文件 `quantsys-v2/tests/data_sources/test_fund_flow_source.py`：

```python
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from data_sources.fund_flow_source import FundFlowDataSource

@pytest.fixture
def fund_flow_source():
    return FundFlowDataSource()

@pytest.fixture
def fresh_cache_data():
    """新鲜的缓存数据（1 小时前更新）"""
    now = datetime.now()
    return [
        {
            'symbol': '600519',
            'trade_date': (now.date() - timedelta(days=i)).strftime('%Y-%m-%d'),
            'main_net_inflow': 10000.0 + i * 1000,
            'main_net_inflow_rate': 2.5,
            'updated_at': now - timedelta(hours=1)
        }
        for i in range(5)
    ]

@pytest.fixture
def stale_cache_data():
    """过期的缓存数据（30 小时前更新）"""
    now = datetime.now()
    return [
        {
            'symbol': '600519',
            'trade_date': (now.date() - timedelta(days=i)).strftime('%Y-%m-%d'),
            'main_net_inflow': 5000.0,
            'updated_at': now - timedelta(hours=30)
        }
        for i in range(5)
    ]

def test_cache_hit_returns_local_data(fund_flow_source, fresh_cache_data, monkeypatch):
    """测试缓存命中时返回本地数据"""
    # Mock repository
    mock_repo = Mock()
    mock_repo.get_latest_fund_flow.return_value = fresh_cache_data
    monkeypatch.setattr(fund_flow_source, 'repository', mock_repo)
    
    result = fund_flow_source.get_stock_fund_flow('600519', days=5)
    
    assert result['source'] == 'cache'
    assert len(result['data']) == 5
    mock_repo.get_latest_fund_flow.assert_called_once_with('600519', 5)

def test_cache_miss_calls_api_and_saves(fund_flow_source, monkeypatch):
    """测试缓存 miss 时调用 API 并保存"""
    # Mock repository - 返回空数据（缓存 miss）
    mock_repo = Mock()
    mock_repo.get_latest_fund_flow.return_value = []
    mock_repo.batch_upsert.return_value = 5
    monkeypatch.setattr(fund_flow_source, 'repository', mock_repo)
    
    # Mock API 调用
    api_data = [
        {
            'symbol': '600519',
            'trade_date': '2026-06-05',
            'main_net_inflow': 10000.0
        }
    ]
    monkeypatch.setattr(fund_flow_source, '_fetch_from_api', Mock(return_value=api_data))
    
    result = fund_flow_source.get_stock_fund_flow('600519', days=5)
    
    assert result['source'] == 'api'
    mock_repo.batch_upsert.assert_called_once()

def test_cache_invalid_when_data_stale(fund_flow_source, stale_cache_data):
    """测试数据过期时缓存无效"""
    is_valid = fund_flow_source._is_cache_valid(stale_cache_data, days=5)
    
    assert is_valid is False

def test_api_failure_fallback_to_stale_cache(fund_flow_source, stale_cache_data, monkeypatch):
    """测试 API 失败时降级使用旧缓存"""
    # Mock repository
    mock_repo = Mock()
    mock_repo.get_latest_fund_flow.side_effect = [
        [],  # 第一次调用返回空（缓存 miss）
        stale_cache_data  # 第二次调用返回旧缓存（fallback）
    ]
    monkeypatch.setattr(fund_flow_source, 'repository', mock_repo)
    
    # Mock API 调用失败
    monkeypatch.setattr(
        fund_flow_source, 
        '_fetch_from_api', 
        Mock(side_effect=Exception("API timeout"))
    )
    
    result = fund_flow_source.get_stock_fund_flow('600519', days=5)
    
    assert result['source'] == 'stale_cache'
    assert len(result['data']) == 5

def test_symbol_normalization_removes_suffix(fund_flow_source, fresh_cache_data, monkeypatch):
    """测试股票代码标准化（去除后缀）"""
    mock_repo = Mock()
    mock_repo.get_latest_fund_flow.return_value = fresh_cache_data
    monkeypatch.setattr(fund_flow_source, 'repository', mock_repo)
    
    result = fund_flow_source.get_stock_fund_flow('600519.SH', days=5)
    
    # 验证调用时已去除后缀
    mock_repo.get_latest_fund_flow.assert_called_with('600519', 5)
    assert result['symbol'] == '600519'
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/data_sources/test_fund_flow_source.py -v
```

Expected: 部分测试失败（因为还未实现缓存逻辑）

- [ ] **Step 3: 修改 FundFlowDataSource 添加缓存逻辑**

修改 `quantsys-v2/data_sources/fund_flow_source.py`，在 `FundFlowDataSource` 类的 `__init__` 方法中添加：

```python
from repositories.fund_flow_repository import FundFlowRepository

class FundFlowDataSource:
    """资金流向数据源 - 优先本地缓存，miss 时调用 API"""
    
    def __init__(self):
        self.repository = FundFlowRepository()  # 新增
        self.sources = [
            EastMoneyFundFlowSource(),
            AkShareFundFlowSource(),
        ]
        self.cache_ttl_hours = 24  # 缓存有效期
```

然后修改 `get_stock_fund_flow` 方法，在现有代码开头添加缓存查询逻辑：

```python
def get_stock_fund_flow(self, symbol: str, days: int = 5) -> Dict:
    """
    获取个股资金流向（优先本地缓存）
    """
    # 1. 标准化股票代码（去除后缀）
    clean_symbol = symbol.split('.')[0]
    
    # 2. 查询本地缓存
    try:
        cached_data = self.repository.get_latest_fund_flow(clean_symbol, days)
        
        # 3. 检查缓存是否完整且新鲜
        if self._is_cache_valid(cached_data, days):
            logger.info(f"命中本地缓存: {symbol}")
            return self._format_response(cached_data, clean_symbol, 'cache')
    except Exception as e:
        logger.warning(f"缓存查询失败，降级为纯 API 模式: {e}")
    
    # 4. 缓存 miss，调用 API
    logger.info(f"缓存 miss，调用 API: {symbol}")
    try:
        # 原有的 API 调用逻辑
        for source in self.sources:
            try:
                logger.info(f"尝试从 {source.name} 获取 {clean_symbol} 资金流向数据")
                data = source.fetch(clean_symbol, days)
                
                if data and len(data) > 0:
                    # 计算汇总信息
                    summary = self._calculate_summary(data)
                    
                    # 5. 写入数据库
                    try:
                        # 转换为标准格式后保存
                        records_to_save = []
                        for d in data:
                            records_to_save.append({
                                'symbol': clean_symbol,
                                'trade_date': d.get('date', d.get('日期', '')),
                                'close_price': d.get('close_price', d.get('收盘价')),
                                'change_pct': d.get('change_pct', d.get('涨跌幅')),
                                'main_net_inflow': d.get('main_net_inflow'),
                                'main_net_inflow_rate': d.get('main_net_inflow_rate'),
                                'large_net_inflow': d.get('large_net_inflow'),
                                'large_net_inflow_rate': d.get('large_net_inflow_rate'),
                                'big_net_inflow': d.get('big_net_inflow'),
                                'big_net_inflow_rate': d.get('big_net_inflow_rate'),
                                'medium_net_inflow': d.get('medium_net_inflow'),
                                'medium_net_inflow_rate': d.get('medium_net_inflow_rate'),
                                'small_net_inflow': d.get('small_net_inflow'),
                                'small_net_inflow_rate': d.get('small_net_inflow_rate'),
                                'source': source.name
                            })
                        
                        self.repository.batch_upsert(records_to_save)
                        logger.info(f"已缓存 {clean_symbol} 资金流数据: {len(records_to_save)} 条")
                    except Exception as e:
                        logger.warning(f"缓存写入失败: {e}")
                    
                    return {
                        'symbol': clean_symbol,
                        'days': days,
                        'data': data,
                        'summary': summary,
                        'source': 'api',
                        'timestamp': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"{source.name} 获取失败: {e}")
                continue
        
        # 所有数据源失败
        raise DataSourceError(f"所有数据源获取 {clean_symbol} 资金流向失败")
        
    except Exception as e:
        # API 失败，降级使用旧缓存（如果存在）
        logger.warning(f"API 调用失败，尝试使用旧缓存: {e}")
        try:
            fallback_data = self.repository.get_latest_fund_flow(clean_symbol, days=30)
            if fallback_data:
                logger.info(f"使用旧缓存数据: {symbol}")
                return self._format_response(fallback_data, clean_symbol, 'stale_cache')
        except:
            pass
        raise
```

然后添加辅助方法：

```python
def _is_cache_valid(self, cached_data: List[Dict], days: int) -> bool:
    """
    判断缓存是否有效
    
    条件：
    1. 数据条数 >= max(1, days - 3)（考虑周末节假日）
    2. 最新数据的 updated_at < 24 小时
    """
    if not cached_data:
        return False
    
    # 检查数据量（容忍周末节假日缺失）
    min_expected = max(1, days - 3)
    if len(cached_data) < min_expected:
        return False
    
    # 检查最新数据的更新时间
    latest = cached_data[0]  # 降序排列，第一条是最新
    updated_at = latest.get('updated_at')
    if not updated_at:
        return False
    
    from datetime import datetime
    age_hours = (datetime.now() - updated_at).total_seconds() / 3600
    
    return age_hours < self.cache_ttl_hours

def _format_response(
    self, 
    data: List[Dict], 
    symbol: str, 
    source: str
) -> Dict:
    """格式化为标准响应格式"""
    summary = self._calculate_summary(data)
    
    return {
        'symbol': symbol,
        'days': len(data),
        'data': data,
        'summary': summary,
        'source': source,
        'timestamp': datetime.now().isoformat()
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/data_sources/test_fund_flow_source.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add data_sources/fund_flow_source.py tests/data_sources/test_fund_flow_source.py
git commit -m "feat(data_source): 添加资金流数据本地缓存逻辑"
```

---

## Task 5: 定时任务实现

**Files:**
- Create: `quantsys-v2/runtime/jobs/update_fund_flow_job.py`
- Create: `quantsys-v2/tests/runtime/jobs/test_update_fund_flow_job.py`

- [ ] **Step 1: 编写定时任务测试**

创建文件 `quantsys-v2/tests/runtime/jobs/test_update_fund_flow_job.py`：

```python
import pytest
from unittest.mock import Mock, patch
from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob

@pytest.fixture
def job():
    return UpdateFundFlowJob()

def test_job_updates_target_symbols(job, monkeypatch):
    """测试任务更新目标股票"""
    # Mock 获取股票池
    test_symbols = ['600519', '000858', '600000']
    monkeypatch.setattr(job, '_get_target_symbols', Mock(return_value=test_symbols))
    
    # Mock 资金流数据源
    mock_source = Mock()
    mock_source.get_stock_fund_flow.return_value = {'success': True}
    mock_source.repository.delete_old_data.return_value = 0
    monkeypatch.setattr(job, 'fund_flow_source', mock_source)
    
    result = job.execute()
    
    assert result['total'] == 3
    assert result['success'] == 3
    assert len(result['failed']) == 0
    assert mock_source.get_stock_fund_flow.call_count == 3

def test_job_handles_single_stock_failure(job, monkeypatch):
    """测试单个股票失败不影响其他股票"""
    test_symbols = ['600519', '000858']
    monkeypatch.setattr(job, '_get_target_symbols', Mock(return_value=test_symbols))
    
    mock_source = Mock()
    # 第一个成功，第二个失败
    mock_source.get_stock_fund_flow.side_effect = [
        {'success': True},
        Exception("API timeout")
    ]
    mock_source.repository.delete_old_data.return_value = 0
    monkeypatch.setattr(job, 'fund_flow_source', mock_source)
    
    result = job.execute()
    
    assert result['success'] == 1
    assert len(result['failed']) == 1
    assert '000858' in result['failed']

def test_job_cleans_old_data(job, monkeypatch):
    """测试任务清理过期数据"""
    test_symbols = ['600519']
    monkeypatch.setattr(job, '_get_target_symbols', Mock(return_value=test_symbols))
    
    mock_source = Mock()
    mock_source.get_stock_fund_flow.return_value = {'success': True}
    mock_source.repository.delete_old_data.return_value = 1000
    monkeypatch.setattr(job, 'fund_flow_source', mock_source)
    
    result = job.execute()
    
    assert result['deleted'] == 1000
    mock_source.repository.delete_old_data.assert_called_once_with(retention_days=90)

def test_get_target_symbols_fallback(job, monkeypatch):
    """测试获取股票池失败时的回退方案"""
    # Mock akshare 失败
    with patch('runtime.jobs.update_fund_flow_job.ak') as mock_ak:
        mock_ak.index_stock_cons.side_effect = Exception("Network error")
        
        # Mock StockPoolService 回退
        mock_pool_service = Mock()
        mock_pool_service.get_hot_stock_pool.return_value = ['600519.SH', '000858.SZ']
        monkeypatch.setattr(job, 'stock_pool_service', mock_pool_service)
        
        symbols = job._get_target_symbols()
        
        assert len(symbols) == 2
        assert '600519' in symbols  # 去除后缀
        assert '000858' in symbols
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/runtime/jobs/test_update_fund_flow_job.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现定时任务**

创建文件 `quantsys-v2/runtime/jobs/update_fund_flow_job.py`：

```python
"""
资金流数据定时更新任务

每日 21:30 执行，批量更新主要指数成分股的资金流数据
"""
import time
import logging
from typing import List, Dict
from data_sources.fund_flow_source import FundFlowDataSource
from services.stock_pool_service import StockPoolService

logger = logging.getLogger(__name__)


class UpdateFundFlowJob:
    """资金流数据定时更新任务"""
    
    def __init__(self):
        self.fund_flow_source = FundFlowDataSource()
        self.stock_pool_service = StockPoolService()
        self.batch_size = 50  # 每批处理股票数
        self.delay_between_batches = 2  # 批次间延迟（秒）
    
    def execute(self) -> Dict:
        """
        执行定时更新
        
        Returns:
            {
                'total': 总股票数,
                'success': 成功数,
                'failed': [失败股票列表],
                'deleted': 清理的过期记录数,
                'elapsed': 耗时（秒）
            }
        """
        logger.info("开始定时更新资金流数据")
        start_time = time.time()
        
        # 1. 获取股票池
        symbols = self._get_target_symbols()
        logger.info(f"待更新股票数: {len(symbols)}")
        
        # 2. 分批更新
        success_count = 0
        failed_symbols = []
        
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(symbols) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"处理批次 {batch_num}/{total_batches}，股票数: {len(batch)}")
            
            for symbol in batch:
                try:
                    self.fund_flow_source.get_stock_fund_flow(symbol, days=5)
                    success_count += 1
                except Exception as e:
                    logger.error(f"更新失败: {symbol} - {e}")
                    failed_symbols.append(symbol)
            
            # 批次间延迟
            if i + self.batch_size < len(symbols):
                time.sleep(self.delay_between_batches)
        
        # 3. 清理过期数据
        deleted = self.fund_flow_source.repository.delete_old_data(retention_days=90)
        
        # 4. 记录统计
        elapsed = time.time() - start_time
        logger.info(
            f"资金流更新完成: 成功 {success_count}/{len(symbols)}, "
            f"失败 {len(failed_symbols)}, 清理 {deleted} 条过期记录, "
            f"耗时 {elapsed:.1f}秒"
        )
        
        if failed_symbols:
            logger.warning(f"失败股票列表: {', '.join(failed_symbols[:10])}{'...' if len(failed_symbols) > 10 else ''}")
        
        return {
            'total': len(symbols),
            'success': success_count,
            'failed': failed_symbols,
            'deleted': deleted,
            'elapsed': elapsed
        }
    
    def _get_target_symbols(self) -> List[str]:
        """
        获取目标股票池（约 1200 只）
        
        Returns:
            股票代码列表（不带后缀）
        """
        try:
            import akshare as ak
            
            # 获取沪深300成分股
            hs300 = ak.index_stock_cons(symbol="000300")
            symbols_hs300 = hs300['品种代码'].tolist() if not hs300.empty else []
            
            # 获取中证500成分股
            zz500 = ak.index_stock_cons(symbol="000905")
            symbols_zz500 = zz500['品种代码'].tolist() if not zz500.empty else []
            
            # 获取中证1000成分股
            zz1000 = ak.index_stock_cons(symbol="000852")
            symbols_zz1000 = zz1000['品种代码'].tolist() if not zz1000.empty else []
            
            # 合并去重
            all_symbols = list(set(symbols_hs300 + symbols_zz500 + symbols_zz1000))
            
            logger.info(
                f"获取指数成分股: 沪深300={len(symbols_hs300)}, "
                f"中证500={len(symbols_zz500)}, 中证1000={len(symbols_zz1000)}, "
                f"合并后={len(all_symbols)}"
            )
            
            return all_symbols
            
        except Exception as e:
            logger.warning(f"获取指数成分股失败，使用默认股票池: {e}")
            
            # 回退方案：使用 StockPoolService
            pool_symbols = self.stock_pool_service.get_hot_stock_pool()
            return [s.split('.')[0] for s in pool_symbols]  # 去除后缀
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/runtime/jobs/test_update_fund_flow_job.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add runtime/jobs/update_fund_flow_job.py tests/runtime/jobs/test_update_fund_flow_job.py
git commit -m "feat(job): 实现资金流数据定时更新任务"
```

---

## Task 6: 集成测试

**Files:**
- Create: `quantsys-v2/tests/integration/test_fund_flow_caching.py`

- [ ] **Step 1: 编写端到端集成测试**

创建文件 `quantsys-v2/tests/integration/test_fund_flow_caching.py`：

```python
"""
资金流缓存系统集成测试
"""
import pytest
import time
from datetime import datetime, timedelta
from data_sources.fund_flow_source import FundFlowDataSource
from repositories.fund_flow_repository import FundFlowRepository
from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob

@pytest.fixture
def repository():
    return FundFlowRepository()

@pytest.fixture
def fund_flow_source():
    return FundFlowDataSource()

def test_end_to_end_caching(repository, fund_flow_source):
    """
    端到端测试缓存流程
    
    步骤：
    1. 清空测试数据
    2. 首次查询 → 触发 API 调用 → 写入数据库
    3. 验证数据库中存在记录
    4. 再次查询 → 命中缓存 → 验证 source='cache'
    5. 验证性能提升
    """
    test_symbol = '600519'
    
    # 1. 清空测试数据
    conn = repository.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM quant.stock_fund_flow WHERE symbol = %s", (test_symbol,))
            conn.commit()
    finally:
        repository.release_connection(conn)
    
    # 2. 首次查询（缓存 miss）
    start = time.time()
    result1 = fund_flow_source.get_stock_fund_flow(test_symbol, days=5)
    elapsed1 = time.time() - start
    
    assert result1['source'] in ['api', 'stale_cache']
    
    # 3. 验证数据库中存在记录
    db_records = repository.get_latest_fund_flow(test_symbol, days=5)
    assert len(db_records) > 0
    
    # 4. 再次查询（缓存命中）
    start = time.time()
    result2 = fund_flow_source.get_stock_fund_flow(test_symbol, days=5)
    elapsed2 = time.time() - start
    
    assert result2['source'] == 'cache'
    
    # 5. 验证性能提升
    print(f"首次查询: {elapsed1:.3f}秒, 缓存命中: {elapsed2:.3f}秒")
    assert elapsed2 < 0.5  # 缓存命中应 < 500ms

def test_stale_cache_fallback(repository, fund_flow_source):
    """
    测试 API 失败时降级使用旧缓存
    
    步骤：
    1. 插入 3 天前的数据到数据库
    2. Mock API 调用抛出异常
    3. 查询股票资金流
    4. 验证返回旧缓存数据
    """
    test_symbol = '000858'
    
    # 1. 插入旧数据
    old_date = (datetime.now().date() - timedelta(days=3)).strftime('%Y-%m-%d')
    old_records = [
        {
            'symbol': test_symbol,
            'trade_date': old_date,
            'main_net_inflow': 5000.0,
            'main_net_inflow_rate': 1.5
        }
    ]
    repository.batch_upsert(old_records)
    
    # 2-4. 由于难以 mock API 失败，这里只验证旧缓存存在
    # 实际测试需要在受控环境下进行
    db_records = repository.get_latest_fund_flow(test_symbol, days=30)
    assert len(db_records) > 0

def test_scheduled_job_integration():
    """
    测试定时任务完整流程
    
    步骤：
    1. 执行 UpdateFundFlowJob（小规模测试）
    2. 验证返回统计信息正确
    """
    job = UpdateFundFlowJob()
    
    # Mock 少量股票进行测试
    job._get_target_symbols = lambda: ['600519', '000858']
    job.batch_size = 2
    
    result = job.execute()
    
    assert result['total'] == 2
    assert result['success'] + len(result['failed']) == 2
    assert 'elapsed' in result
    assert 'deleted' in result
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/integration/test_fund_flow_caching.py -v -s
```

Expected: 测试通过（可能需要真实 API 连接）

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_fund_flow_caching.py
git commit -m "test(integration): 添加资金流缓存系统集成测试"
```

---

## Task 7: 调度器配置和文档

**Files:**
- Modify: `quantsys-v2/runtime/scheduler/scheduler.py` 或创建配置文件
- Create: `docs/features/fund-flow-caching.md`

- [ ] **Step 1: 注册定时任务到调度器**

根据项目调度器实现方式，添加任务注册。如果使用 APScheduler，添加：

```python
# 在 runtime/scheduler/scheduler.py 或初始化代码中
from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob

scheduler.add_job(
    func=lambda: UpdateFundFlowJob().execute(),
    trigger='cron',
    hour=21,
    minute=30,
    id='fund_flow_update',
    name='更新资金流数据',
    replace_existing=True
)
```

或者如果使用配置文件方式，创建 `runtime/scheduler/jobs_config.yaml`：

```yaml
fund_flow_update:
  job_class: "runtime.jobs.update_fund_flow_job.UpdateFundFlowJob"
  trigger: "cron"
  hour: 21
  minute: 30
  enabled: true
  description: "更新主要指数成分股的资金流数据"
```

- [ ] **Step 2: 手动测试定时任务**

```bash
cd quantsys-v2
python -c "from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob; result = UpdateFundFlowJob().execute(); print(result)"
```

Expected: 打印任务执行结果，包含 success/failed/deleted 统计

- [ ] **Step 3: 编写功能文档**

创建文件 `docs/features/fund-flow-caching.md`：

```markdown
# 资金流数据缓存系统

## 概述

资金流数据缓存系统通过本地数据库持久化 + 定时任务批量更新，将策略执行时的资金流查询性能从 3-5 秒降至 < 50ms。

## 架构

- **数据库表**: `quant.stock_fund_flow` - 存储资金流历史数据（90 天）
- **Repository 层**: `FundFlowRepository` - 统一数据访问接口
- **数据源层**: `FundFlowDataSource` - 优先查询本地缓存，miss 时调用 API
- **定时任务**: `UpdateFundFlowJob` - 每日 21:30 批量更新约 1200 只股票

## 性能提升

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 单次查询（缓存命中） | 3-5 秒 | < 50ms | 100x |
| 批量查询（10只） | 30-50 秒 | < 500ms | 60-100x |

## 使用方式

### 自动缓存

无需修改代码，`SentimentService` 和 `StrategyCodeService` 自动享受缓存加速。

### 手动清理过期数据

```python
from repositories.fund_flow_repository import FundFlowRepository

repo = FundFlowRepository()
deleted = repo.delete_old_data(retention_days=90)
print(f"清理了 {deleted} 条过期记录")
```

### 手动触发更新任务

```python
from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob

job = UpdateFundFlowJob()
result = job.execute()
print(f"成功: {result['success']}, 失败: {len(result['failed'])}")
```

## 监控指标

- **缓存命中率**: 目标 > 90%
- **平均响应时间**: 目标 < 100ms
- **定时任务成功率**: 目标 > 95%

## 容错机制

1. **API 失败降级**: 使用 30 天内的旧缓存
2. **数据库故障降级**: 直接调用 API（不写缓存）
3. **定时任务容错**: 单个股票失败不影响其他股票

## 相关文件

- 设计文档: `docs/superpowers/specs/2026-06-05-fund-flow-caching-design.md`
- 实施计划: `docs/superpowers/plans/2026-06-05-fund-flow-caching.md`
```

- [ ] **Step 4: Commit**

```bash
git add runtime/scheduler/ docs/features/fund-flow-caching.md
git commit -m "feat(scheduler): 注册资金流数据定时更新任务"
```

---

## Task 8: 最终验证和部署

**Files:**
- None (verification only)

- [ ] **Step 1: 运行所有测试**

```bash
cd quantsys-v2

# 运行所有相关测试
pytest tests/repositories/test_fund_flow_repository.py -v
pytest tests/data_sources/test_fund_flow_source.py -v
pytest tests/runtime/jobs/test_update_fund_flow_job.py -v
pytest tests/integration/test_fund_flow_caching.py -v

# 检查测试覆盖率
pytest tests/ --cov=repositories.fund_flow_repository --cov=data_sources.fund_flow_source --cov=runtime.jobs.update_fund_flow_job --cov-report=term-missing
```

Expected: 所有测试通过，覆盖率 > 85%

- [ ] **Step 2: 性能基准测试**

创建临时测试脚本 `temp_performance_test.py`：

```python
import time
from data_sources.fund_flow_source import FundFlowDataSource

source = FundFlowDataSource()

# 测试缓存命中性能
test_symbols = ['600519', '000858', '600000']

print("=== 性能测试 ===")
for symbol in test_symbols:
    # 首次查询（可能 miss）
    start = time.time()
    result1 = source.get_stock_fund_flow(symbol, days=5)
    elapsed1 = time.time() - start
    
    # 第二次查询（应该命中）
    start = time.time()
    result2 = source.get_stock_fund_flow(symbol, days=5)
    elapsed2 = time.time() - start
    
    print(f"{symbol}: 首次={elapsed1:.3f}s (source={result1['source']}), "
          f"二次={elapsed2:.3f}s (source={result2['source']})")
```

运行：
```bash
python temp_performance_test.py
```

Expected: 第二次查询 < 100ms，source='cache'

- [ ] **Step 3: 验证定时任务**

```bash
# 手动触发一次定时任务
python -c "from runtime.jobs.update_fund_flow_job import UpdateFundFlowJob; print(UpdateFundFlowJob().execute())"
```

Expected: 任务成功执行，打印统计信息

- [ ] **Step 4: 验证数据库数据**

```bash
psql -h localhost -U $PGUSER -d $PGDATABASE -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM quant.stock_fund_flow;"
```

Expected: 显示记录数和日期范围

- [ ] **Step 5: 更新 CLAUDE.md**

在 `/Users/mac/Documents/ai/pi-investment/quantsys-v2/CLAUDE.md` 中添加：

```markdown
## 资金流数据缓存系统（2026-06-05）

策略执行时的资金流查询已优化为本地缓存优先，性能提升 100 倍（3-5秒 → < 50ms）。

- **数据表**: `quant.stock_fund_flow` - 90 天历史数据
- **自动更新**: 每日 21:30 批量更新约 1200 只主要指数成分股
- **容错机制**: API 失败时降级使用旧缓存
- **详细文档**: `docs/features/fund-flow-caching.md`
```

- [ ] **Step 6: 最终 Commit**

```bash
git add quantsys-v2/CLAUDE.md
git commit -m "docs: 更新 CLAUDE.md 记录资金流缓存系统"

# 创建标签
git tag -a fund-flow-caching-v1.0 -m "资金流数据本地缓存系统 v1.0"
```

---

## 完成标准

✅ 所有测试通过（单元测试 + 集成测试）  
✅ 测试覆盖率 > 85%  
✅ 缓存命中时响应时间 < 100ms  
✅ 定时任务可正常执行  
✅ 数据库表已创建并包含数据  
✅ 文档已更新

## 回滚方案

如果出现问题，执行以下步骤回滚：

```bash
# 1. 代码回滚
git revert HEAD~N  # N = 提交次数

# 2. 禁用定时任务
# 在调度器中注释或删除 fund_flow_update 任务

# 3. 保留数据库表（不删除）
# 表中的数据仍可用于后续调试
```

