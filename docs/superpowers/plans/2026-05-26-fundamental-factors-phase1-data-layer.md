# 基本面因子模块实施计划 - 阶段1: 数据层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建财务报表历史数据表和FinancialRepository,实现数据的存储和查询

**Architecture:** 3张PostgreSQL表(利润表、资产负债表、现金流量表) + Repository层提供CRUD和批量查询接口

**Tech Stack:** PostgreSQL, psycopg2, Python 3.13

---

## 文件结构

**新建文件:**
- `quantsys-v2/migrations/add_financial_tables.sql` - 数据库迁移脚本
- `quantsys-v2/repositories/financial_repository.py` - 财务数据仓储
- `quantsys-v2/tests/test_financial_repository.py` - Repository单元测试

**修改文件:**
- 无

---

## Task 1: 创建数据库迁移脚本

**Files:**
- Create: `quantsys-v2/migrations/add_financial_tables.sql`

- [ ] **Step 1: 创建迁移脚本文件**

```sql
-- 基本面因子模块 - 财务报表历史数据表
-- 创建日期: 2026-05-26

-- 1. 利润表历史数据表
CREATE TABLE IF NOT EXISTS quant.income_statements (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,  -- 'Q' (季度) 或 'Y' (年度)
    
    -- 收入相关
    revenue DOUBLE PRECISION,
    operating_revenue DOUBLE PRECISION,
    
    -- 成本相关
    operating_cost DOUBLE PRECISION,
    gross_profit DOUBLE PRECISION,
    gross_margin DOUBLE PRECISION,
    
    -- 利润相关
    operating_profit DOUBLE PRECISION,
    total_profit DOUBLE PRECISION,
    net_profit DOUBLE PRECISION,
    net_profit_parent DOUBLE PRECISION,
    
    -- 每股指标
    eps DOUBLE PRECISION,
    eps_diluted DOUBLE PRECISION,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_income_statements_symbol ON quant.income_statements(symbol);
CREATE INDEX IF NOT EXISTS idx_income_statements_report_date ON quant.income_statements(report_date);
CREATE INDEX IF NOT EXISTS idx_income_statements_period_type ON quant.income_statements(period_type);

-- 2. 资产负债表历史数据表
CREATE TABLE IF NOT EXISTS quant.balance_sheets (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,
    
    -- 资产
    total_assets DOUBLE PRECISION,
    current_assets DOUBLE PRECISION,
    non_current_assets DOUBLE PRECISION,
    
    -- 负债
    total_liabilities DOUBLE PRECISION,
    current_liabilities DOUBLE PRECISION,
    non_current_liabilities DOUBLE PRECISION,
    
    -- 权益
    total_equity DOUBLE PRECISION,
    parent_equity DOUBLE PRECISION,
    
    -- 比率
    debt_ratio DOUBLE PRECISION,
    current_ratio DOUBLE PRECISION,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_balance_sheets_symbol ON quant.balance_sheets(symbol);
CREATE INDEX IF NOT EXISTS idx_balance_sheets_report_date ON quant.balance_sheets(report_date);
CREATE INDEX IF NOT EXISTS idx_balance_sheets_period_type ON quant.balance_sheets(period_type);

-- 3. 现金流量表历史数据表
CREATE TABLE IF NOT EXISTS quant.cash_flows (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,
    
    -- 经营活动现金流
    operating_cash_flow DOUBLE PRECISION,
    
    -- 投资活动现金流
    investing_cash_flow DOUBLE PRECISION,
    capex DOUBLE PRECISION,
    
    -- 筹资活动现金流
    financing_cash_flow DOUBLE PRECISION,
    dividends_paid DOUBLE PRECISION,
    
    -- 自由现金流
    free_cash_flow DOUBLE PRECISION,
    
    -- 现金及现金等价物
    cash_end DOUBLE PRECISION,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_symbol ON quant.cash_flows(symbol);
CREATE INDEX IF NOT EXISTS idx_cash_flows_report_date ON quant.cash_flows(report_date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_period_type ON quant.cash_flows(period_type);
```

- [ ] **Step 2: 执行迁移脚本**

Run:
```bash
psql -h 127.0.0.1 -p 5432 -U mac -d quant_investment -f quantsys-v2/migrations/add_financial_tables.sql
```

Expected: 输出 "CREATE TABLE" 和 "CREATE INDEX" 成功消息

- [ ] **Step 3: 验证表创建成功**

Run:
```bash
psql -h 127.0.0.1 -p 5432 -U mac -d quant_investment -c "\dt quant.income_statements"
psql -h 127.0.0.1 -p 5432 -U mac -d quant_investment -c "\dt quant.balance_sheets"
psql -h 127.0.0.1 -p 5432 -U mac -d quant_investment -c "\dt quant.cash_flows"
```

Expected: 显示3张表的信息

- [ ] **Step 4: 提交**

```bash
git add quantsys-v2/migrations/add_financial_tables.sql
git commit -m "feat: add financial tables migration script

- income_statements: 利润表历史数据
- balance_sheets: 资产负债表历史数据
- cash_flows: 现金流量表历史数据"
```

---

## Task 2: 实现FinancialRepository - 利润表操作

**Files:**
- Create: `quantsys-v2/repositories/financial_repository.py`
- Create: `quantsys-v2/tests/test_financial_repository.py`

- [ ] **Step 1: 编写利润表保存测试**

```python
# tests/test_financial_repository.py
import pytest
from datetime import date
from repositories.financial_repository import FinancialRepository
from infrastructure.database.connection import get_db_connection


@pytest.fixture
def financial_repo():
    """创建FinancialRepository实例"""
    db = get_db_connection()
    repo = FinancialRepository(db)
    yield repo
    db.close()


@pytest.fixture
def sample_income_statement():
    """示例利润表数据"""
    return {
        'symbol': '600519.SH',
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'revenue': 120000000000.0,
        'operating_revenue': 118000000000.0,
        'operating_cost': 30000000000.0,
        'gross_profit': 88000000000.0,
        'gross_margin': 73.33,
        'operating_profit': 70000000000.0,
        'total_profit': 72000000000.0,
        'net_profit': 60000000000.0,
        'net_profit_parent': 59000000000.0,
        'eps': 50.0,
        'eps_diluted': 49.5
    }


class TestFinancialRepositoryIncomeStatements:
    """利润表操作测试"""
    
    def test_save_income_statement(self, financial_repo, sample_income_statement):
        """测试保存单条利润表数据"""
        # 保存数据
        financial_repo.save_income_statement(sample_income_statement)
        
        # 查询验证
        result = financial_repo.get_income_statements(
            symbol='600519.SH',
            period_type='Y',
            limit=1
        )
        
        assert len(result) == 1
        assert result[0]['symbol'] == '600519.SH'
        assert result[0]['revenue'] == 120000000000.0
        assert result[0]['gross_margin'] == 73.33
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py::TestFinancialRepositoryIncomeStatements::test_save_income_statement -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'repositories.financial_repository'"

- [ ] **Step 3: 实现FinancialRepository基础结构**

```python
# repositories/financial_repository.py
"""
财务报表数据仓储

职责:
1. 封装财务报表数据的数据库操作
2. 提供通用查询方法
3. 参数校验和数据转换
"""
from typing import Dict, Any, List, Optional
from infrastructure.database.base_repository import BaseRepository
import logging

logger = logging.getLogger(__name__)


class FinancialRepository(BaseRepository):
    """
    财务报表数据仓储
    
    提供利润表、资产负债表、现金流量表的CRUD操作
    """
    
    # ========== 利润表操作 ==========
    
    def save_income_statement(self, data: Dict[str, Any]) -> None:
        """
        保存单条利润表数据 (INSERT ON CONFLICT UPDATE)
        
        Args:
            data: 包含 symbol, report_date, period_type 及财务字段的字典
        """
        # 参数校验
        required_fields = ['symbol', 'report_date', 'period_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # 构建SQL
        fields = list(data.keys())
        placeholders = ', '.join(['%s'] * len(fields))
        field_str = ', '.join(fields)
        
        # ON CONFLICT UPDATE子句
        update_fields = [f for f in fields if f not in ['symbol', 'report_date', 'period_type']]
        update_str = ', '.join([f"{f} = EXCLUDED.{f}" for f in update_fields])
        
        query = f"""
            INSERT INTO quant.income_statements ({field_str})
            VALUES ({placeholders})
            ON CONFLICT (symbol, report_date, period_type)
            DO UPDATE SET {update_str}, updated_at = NOW()
        """
        
        # 执行插入
        self._log_query("save_income_statement", {"symbol": data['symbol']})
        
        if not self.db:
            raise RuntimeError("Database connection not initialized")
        
        try:
            cursor = self.db.cursor()
            values = [data[f] for f in fields]
            cursor.execute(query, values)
            self.db.commit()
            cursor.close()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save income statement: {e}")
            raise
    
    def get_income_statements(
        self,
        symbol: str,
        period_type: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        查询利润表历史数据
        
        Args:
            symbol: 股票代码
            period_type: 'Q' or 'Y' or None (both)
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
        
        Returns:
            利润表数据列表 (按report_date倒序)
        """
        # 构建SQL
        query = "SELECT * FROM quant.income_statements WHERE symbol = %s"
        params = [symbol]
        
        if period_type:
            query += " AND period_type = %s"
            params.append(period_type)
        
        if start_date:
            query += " AND report_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND report_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY report_date DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        # 执行查询
        self._log_query("get_income_statements", {
            "symbol": symbol,
            "period_type": period_type,
            "limit": limit
        })
        
        if not self.db:
            raise RuntimeError("Database connection not initialized")
        
        try:
            cursor = self.db.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            return [self._to_domain_object(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get income statements: {e}")
            raise
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py::TestFinancialRepositoryIncomeStatements::test_save_income_statement -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add repositories/financial_repository.py tests/test_financial_repository.py
git commit -m "feat: implement FinancialRepository income statement operations

- save_income_statement: INSERT ON CONFLICT UPDATE
- get_income_statements: 查询历史数据,支持筛选条件"
```

---

## Task 3: 实现FinancialRepository - 批量查询优化

**Files:**
- Modify: `quantsys-v2/repositories/financial_repository.py`
- Modify: `quantsys-v2/tests/test_financial_repository.py`

- [ ] **Step 1: 编写批量查询测试**

```python
# tests/test_financial_repository.py (追加)

def test_batch_get_latest_income_statements(self, financial_repo):
    """测试批量查询最新利润表数据"""
    # 准备测试数据 - 插入多只股票的数据
    symbols = ['600519.SH', '000001.SZ', '600036.SH']
    for symbol in symbols:
        data = {
            'symbol': symbol,
            'report_date': date(2025, 12, 31),
            'period_type': 'Y',
            'revenue': 100000000000.0,
            'net_profit': 50000000000.0
        }
        financial_repo.save_income_statement(data)
    
    # 批量查询
    result = financial_repo.batch_get_latest_income_statements(
        symbols=symbols,
        period_type='Y'
    )
    
    assert len(result) == 3
    assert '600519.SH' in result
    assert '000001.SZ' in result
    assert '600036.SH' in result
    assert result['600519.SH']['revenue'] == 100000000000.0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py::TestFinancialRepositoryIncomeStatements::test_batch_get_latest_income_statements -v`

Expected: FAIL with "AttributeError: 'FinancialRepository' object has no attribute 'batch_get_latest_income_statements'"

- [ ] **Step 3: 实现批量查询方法**

```python
# repositories/financial_repository.py (追加到FinancialRepository类)

def batch_get_latest_income_statements(
    self,
    symbols: List[str],
    period_type: str = 'Y'
) -> Dict[str, Dict[str, Any]]:
    """
    批量查询最新利润表数据
    
    优化: 单次SQL查询,避免N+1问题
    
    Args:
        symbols: 股票代码列表
        period_type: 'Q' or 'Y'
    
    Returns:
        {symbol: data} 字典
    """
    if not symbols:
        return {}
    
    # 使用DISTINCT ON查询每只股票的最新数据
    query = """
        SELECT DISTINCT ON (symbol) *
        FROM quant.income_statements
        WHERE symbol = ANY(%s) AND period_type = %s
        ORDER BY symbol, report_date DESC
    """
    
    self._log_query("batch_get_latest_income_statements", {
        "symbols_count": len(symbols),
        "period_type": period_type
    })
    
    if not self.db:
        raise RuntimeError("Database connection not initialized")
    
    try:
        cursor = self.db.cursor()
        cursor.execute(query, (symbols, period_type))
        rows = cursor.fetchall()
        cursor.close()
        
        # 转换为字典
        result = {}
        for row in rows:
            obj = self._to_domain_object(row)
            result[obj['symbol']] = obj
        
        return result
    except Exception as e:
        logger.error(f"Failed to batch get latest income statements: {e}")
        raise
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py::TestFinancialRepositoryIncomeStatements::test_batch_get_latest_income_statements -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd quantsys-v2
git add repositories/financial_repository.py tests/test_financial_repository.py
git commit -m "feat: add batch query for income statements

- batch_get_latest_income_statements: 单次SQL查询,避免N+1问题
- 使用DISTINCT ON优化查询性能"
```

---

## Task 4: 实现FinancialRepository - 资产负债表和现金流量表操作

**Files:**
- Modify: `quantsys-v2/repositories/financial_repository.py`
- Modify: `quantsys-v2/tests/test_financial_repository.py`

- [ ] **Step 1: 编写资产负债表测试**

```python
# tests/test_financial_repository.py (追加)

@pytest.fixture
def sample_balance_sheet():
    """示例资产负债表数据"""
    return {
        'symbol': '600519.SH',
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'total_assets': 300000000000.0,
        'current_assets': 150000000000.0,
        'non_current_assets': 150000000000.0,
        'total_liabilities': 100000000000.0,
        'current_liabilities': 50000000000.0,
        'non_current_liabilities': 50000000000.0,
        'total_equity': 200000000000.0,
        'parent_equity': 195000000000.0,
        'debt_ratio': 33.33,
        'current_ratio': 3.0
    }


class TestFinancialRepositoryBalanceSheets:
    """资产负债表操作测试"""
    
    def test_save_balance_sheet(self, financial_repo, sample_balance_sheet):
        """测试保存资产负债表"""
        financial_repo.save_balance_sheet(sample_balance_sheet)
        
        result = financial_repo.get_balance_sheets(
            symbol='600519.SH',
            period_type='Y',
            limit=1
        )
        
        assert len(result) == 1
        assert result[0]['total_assets'] == 300000000000.0
        assert result[0]['debt_ratio'] == 33.33
```

- [ ] **Step 2: 编写现金流量表测试**

```python
# tests/test_financial_repository.py (追加)

@pytest.fixture
def sample_cash_flow():
    """示例现金流量表数据"""
    return {
        'symbol': '600519.SH',
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'operating_cash_flow': 70000000000.0,
        'investing_cash_flow': -20000000000.0,
        'capex': 15000000000.0,
        'financing_cash_flow': -10000000000.0,
        'dividends_paid': 30000000000.0,
        'free_cash_flow': 55000000000.0,
        'cash_end': 100000000000.0
    }


class TestFinancialRepositoryCashFlows:
    """现金流量表操作测试"""
    
    def test_save_cash_flow(self, financial_repo, sample_cash_flow):
        """测试保存现金流量表"""
        financial_repo.save_cash_flow(sample_cash_flow)
        
        result = financial_repo.get_cash_flows(
            symbol='600519.SH',
            period_type='Y',
            limit=1
        )
        
        assert len(result) == 1
        assert result[0]['operating_cash_flow'] == 70000000000.0
        assert result[0]['free_cash_flow'] == 55000000000.0
```

- [ ] **Step 3: 运行测试验证失败**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py::TestFinancialRepositoryBalanceSheets -v`

Expected: FAIL with "AttributeError: 'FinancialRepository' object has no attribute 'save_balance_sheet'"

- [ ] **Step 4: 实现资产负债表和现金流量表操作**

```python
# repositories/financial_repository.py (追加到FinancialRepository类)

# ========== 资产负债表操作 ==========

def save_balance_sheet(self, data: Dict[str, Any]) -> None:
    """保存单条资产负债表数据 (INSERT ON CONFLICT UPDATE)"""
    required_fields = ['symbol', 'report_date', 'period_type']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    fields = list(data.keys())
    placeholders = ', '.join(['%s'] * len(fields))
    field_str = ', '.join(fields)
    
    update_fields = [f for f in fields if f not in ['symbol', 'report_date', 'period_type']]
    update_str = ', '.join([f"{f} = EXCLUDED.{f}" for f in update_fields])
    
    query = f"""
        INSERT INTO quant.balance_sheets ({field_str})
        VALUES ({placeholders})
        ON CONFLICT (symbol, report_date, period_type)
        DO UPDATE SET {update_str}, updated_at = NOW()
    """
    
    self._log_query("save_balance_sheet", {"symbol": data['symbol']})
    
    if not self.db:
        raise RuntimeError("Database connection not initialized")
    
    try:
        cursor = self.db.cursor()
        values = [data[f] for f in fields]
        cursor.execute(query, values)
        self.db.commit()
        cursor.close()
    except Exception as e:
        self.db.rollback()
        logger.error(f"Failed to save balance sheet: {e}")
        raise

def get_balance_sheets(
    self,
    symbol: str,
    period_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """查询资产负债表历史数据"""
    query = "SELECT * FROM quant.balance_sheets WHERE symbol = %s"
    params = [symbol]
    
    if period_type:
        query += " AND period_type = %s"
        params.append(period_type)
    
    if start_date:
        query += " AND report_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND report_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY report_date DESC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    self._log_query("get_balance_sheets", {"symbol": symbol})
    
    if not self.db:
        raise RuntimeError("Database connection not initialized")
    
    try:
        cursor = self.db.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        
        return [self._to_domain_object(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get balance sheets: {e}")
        raise

# ========== 现金流量表操作 ==========

def save_cash_flow(self, data: Dict[str, Any]) -> None:
    """保存单条现金流量表数据 (INSERT ON CONFLICT UPDATE)"""
    required_fields = ['symbol', 'report_date', 'period_type']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    fields = list(data.keys())
    placeholders = ', '.join(['%s'] * len(fields))
    field_str = ', '.join(fields)
    
    update_fields = [f for f in fields if f not in ['symbol', 'report_date', 'period_type']]
    update_str = ', '.join([f"{f} = EXCLUDED.{f}" for f in update_fields])
    
    query = f"""
        INSERT INTO quant.cash_flows ({field_str})
        VALUES ({placeholders})
        ON CONFLICT (symbol, report_date, period_type)
        DO UPDATE SET {update_str}, updated_at = NOW()
    """
    
    self._log_query("save_cash_flow", {"symbol": data['symbol']})
    
    if not self.db:
        raise RuntimeError("Database connection not initialized")
    
    try:
        cursor = self.db.cursor()
        values = [data[f] for f in fields]
        cursor.execute(query, values)
        self.db.commit()
        cursor.close()
    except Exception as e:
        self.db.rollback()
        logger.error(f"Failed to save cash flow: {e}")
        raise

def get_cash_flows(
    self,
    symbol: str,
    period_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """查询现金流量表历史数据"""
    query = "SELECT * FROM quant.cash_flows WHERE symbol = %s"
    params = [symbol]
    
    if period_type:
        query += " AND period_type = %s"
        params.append(period_type)
    
    if start_date:
        query += " AND report_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND report_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY report_date DESC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    self._log_query("get_cash_flows", {"symbol": symbol})
    
    if not self.db:
        raise RuntimeError("Database connection not initialized")
    
    try:
        cursor = self.db.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        
        return [self._to_domain_object(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get cash flows: {e}")
        raise
```

- [ ] **Step 5: 运行所有测试验证通过**

Run: `cd quantsys-v2 && pytest tests/test_financial_repository.py -v`

Expected: 所有测试PASS

- [ ] **Step 6: 提交**

```bash
cd quantsys-v2
git add repositories/financial_repository.py tests/test_financial_repository.py
git commit -m "feat: add balance sheet and cash flow operations

- save_balance_sheet/get_balance_sheets: 资产负债表操作
- save_cash_flow/get_cash_flows: 现金流量表操作
- 统一的INSERT ON CONFLICT UPDATE模式"
```

---

## 阶段1完成检查

- [ ] 所有测试通过: `cd quantsys-v2 && pytest tests/test_financial_repository.py -v`
- [ ] 数据库表已创建并可查询
- [ ] FinancialRepository实现了3张表的CRUD操作
- [ ] 批量查询方法已实现并测试通过
- [ ] 所有代码已提交到git

**下一阶段:** 阶段2 - 计算层 (FundamentalFactorCalculator基类和三个因子类)
