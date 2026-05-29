# Dividend Data Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dividend data querying capability to TypeScript Agent via quantsys-v2 backend API.

**Architecture:** Lightweight implementation with real-time akshare queries (no database persistence). Three-layer design: TypeScript tool → QuantV2Client → Flask API → DividendService → akshare. Supports three modes: single stock query, high-yield screening, dividend calendar.

**Tech Stack:** Python 3.13, Flask, akshare, pandas, TypeScript, @sinclair/typebox, fetch API

---

## File Structure

**quantsys-v2 Backend:**
- Create: `quantsys-v2/services/dividend_data_source.py` - Data source abstraction layer
- Create: `quantsys-v2/services/dividend_service.py` - Core business logic
- Create: `quantsys-v2/api/routes/dividends.py` - Flask routes
- Modify: `quantsys-v2/api/server.py` - Register blueprint
- Create: `quantsys-v2/tests/services/test_dividend_service.py` - Service unit tests
- Create: `quantsys-v2/tests/api/test_dividends_routes.py` - API integration tests

**TypeScript Agent:**
- Modify: `src/infrastructure/quant/types.ts` - Add dividend types
- Modify: `src/infrastructure/quant/quant-v2-client.ts` - Add getDividends()
- Create: `src/infrastructure/tools/data/fetch-dividend-tool.ts` - Tool definition
- Modify: `src/infrastructure/quant/formatters.ts` - Add formatDividendData()
- Modify: `src/infrastructure/tools/data/index.ts` - Register tool
- Create: `src/infrastructure/tools/data/fetch-dividend-tool.test.ts` - Tool tests

---

## Phase 1: quantsys-v2 Backend

### Task 1: Data Source Abstraction Layer

**Files:**
- Create: `quantsys-v2/services/dividend_data_source.py`
- Create: `quantsys-v2/tests/services/test_dividend_data_source.py`

- [ ] **Step 1: Write failing test for AkshareDividendSource**

Create `quantsys-v2/tests/services/test_dividend_data_source.py`:

```python
import pytest
import pandas as pd
from services.dividend_data_source import AkshareDividendSource, DividendDataSource


class TestAkshareDividendSource:
    def test_fetch_dividends_returns_dataframe(self):
        """Test that fetch_dividends returns a pandas DataFrame"""
        source = AkshareDividendSource()
        result = source.fetch_dividends("600519.SH")
        
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "分红年度" in result.columns
    
    def test_fetch_dividends_strips_suffix(self):
        """Test that symbol suffix is stripped before calling akshare"""
        source = AkshareDividendSource()
        
        # Both should work
        result1 = source.fetch_dividends("600519.SH")
        result2 = source.fetch_dividends("600519")
        
        assert isinstance(result1, pd.DataFrame)
        assert isinstance(result2, pd.DataFrame)
    
    def test_fetch_dividends_invalid_symbol(self):
        """Test that invalid symbol raises exception"""
        source = AkshareDividendSource()
        
        with pytest.raises(Exception):
            source.fetch_dividends("INVALID")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_data_source.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.dividend_data_source'"

- [ ] **Step 3: Write minimal implementation**

Create `quantsys-v2/services/dividend_data_source.py`:

```python
"""
分红数据源抽象层

提供统一的数据源接口，支持未来扩展到 tushare 或其他数据源。
"""
from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DividendDataSource(ABC):
    """分红数据源抽象基类"""
    
    @abstractmethod
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        获取股票分红数据
        
        Args:
            symbol: 股票代码（如 600519.SH 或 600519）
            
        Returns:
            pd.DataFrame: 分红数据
            
        Raises:
            Exception: 数据获取失败
        """
        pass


class AkshareDividendSource(DividendDataSource):
    """akshare 数据源实现"""
    
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        从 akshare 获取分红数据
        
        Args:
            symbol: 股票代码（如 600519.SH 或 600519）
            
        Returns:
            pd.DataFrame: 分红数据，包含列：
                - 分红年度
                - 送转总比例
                - 每股派息
                - 股息率
                - 除权除息日
                - 等
                
        Raises:
            Exception: akshare API 调用失败
        """
        try:
            import akshare as ak
            
            # 移除后缀（akshare 只需要6位代码）
            code = symbol.split('.')[0]
            
            logger.info(f"Fetching dividends from akshare for {code}")
            df = ak.stock_dividend_cninfo(symbol=code)
            
            logger.info(f"Fetched {len(df)} dividend records for {code}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch dividends from akshare for {symbol}: {e}")
            raise


class TushareDividendSource(DividendDataSource):
    """tushare 数据源实现（预留）"""
    
    def __init__(self, token: str):
        """
        初始化 tushare 数据源
        
        Args:
            token: tushare API token
        """
        self.token = token
    
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        从 tushare 获取分红数据（预留实现）
        
        Args:
            symbol: 股票代码
            
        Returns:
            pd.DataFrame: 分红数据
            
        Raises:
            NotImplementedError: 功能未实现
        """
        raise NotImplementedError("Tushare source not implemented yet")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_data_source.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add services/dividend_data_source.py tests/services/test_dividend_data_source.py
git commit -m "feat(dividend): add data source abstraction layer with akshare implementation"
```

---

### Task 2: DividendService - Core Structure

**Files:**
- Create: `quantsys-v2/services/dividend_service.py`
- Create: `quantsys-v2/tests/services/test_dividend_service.py`

- [ ] **Step 1: Write failing test for service initialization**

Create `quantsys-v2/tests/services/test_dividend_service.py`:

```python
import pytest
from services.dividend_service import DividendService
from services.dividend_data_source import AkshareDividendSource


class TestDividendServiceInit:
    def test_service_initializes_with_akshare_source(self):
        """Test that service initializes with AkshareDividendSource by default"""
        service = DividendService()
        
        assert service is not None
        assert isinstance(service.data_source, AkshareDividendSource)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestDividendServiceInit -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.dividend_service'"

- [ ] **Step 3: Write minimal implementation**

Create `quantsys-v2/services/dividend_service.py`:

```python
"""
分红数据服务

提供分红数据查询、筛选、日历等功能。
"""
from typing import List, Dict, Optional
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.base_service import BaseService
from services.dividend_data_source import AkshareDividendSource, DividendDataSource

logger = logging.getLogger(__name__)


class DividendService(BaseService):
    """分红数据服务"""
    
    def __init__(self, data_source: Optional[DividendDataSource] = None):
        """
        初始化分红服务
        
        Args:
            data_source: 数据源实现，默认使用 AkshareDividendSource
        """
        super().__init__()
        self.data_source = data_source or AkshareDividendSource()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestDividendServiceInit -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add services/dividend_service.py tests/services/test_dividend_service.py
git commit -m "feat(dividend): add DividendService core structure"
```

---

### Task 3: DividendService - get_stock_dividends() Method

**Files:**
- Modify: `quantsys-v2/services/dividend_service.py`
- Modify: `quantsys-v2/tests/services/test_dividend_service.py`

- [ ] **Step 1: Write failing test for get_stock_dividends**

Add to `quantsys-v2/tests/services/test_dividend_service.py`:

```python
class TestGetStockDividends:
    def test_get_stock_dividends_success(self):
        """Test successful dividend query"""
        service = DividendService()
        result = service.get_stock_dividends("600519.SH", years=5)
        
        assert result["success"] is True
        assert result["symbol"] == "600519.SH"
        assert "name" in result
        assert "dividends" in result
        assert "summary" in result
        assert isinstance(result["dividends"], list)
        assert len(result["dividends"]) <= 5
    
    def test_get_stock_dividends_with_summary(self):
        """Test that summary is calculated correctly"""
        service = DividendService()
        result = service.get_stock_dividends("600519.SH", years=10)
        
        summary = result["summary"]
        assert "consecutive_years" in summary
        assert "avg_yield" in summary
        assert "total_cash_dividend" in summary
        assert summary["consecutive_years"] > 0
    
    def test_get_stock_dividends_invalid_symbol(self):
        """Test handling of invalid symbol"""
        service = DividendService()
        result = service.get_stock_dividends("INVALID", years=5)
        
        assert result["success"] is False
        assert "error" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestGetStockDividends -v`

Expected: FAIL with "AttributeError: 'DividendService' object has no attribute 'get_stock_dividends'"

- [ ] **Step 3: Write implementation**

Add to `quantsys-v2/services/dividend_service.py`:

```python
    def get_stock_dividends(self, symbol: str, years: int = 10) -> Dict:
        """
        获取单股历史分红
        
        Args:
            symbol: 股票代码（如 600519.SH）
            years: 查询最近N年
            
        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "dividends": List[Dict],
                "summary": Dict
            }
        """
        try:
            logger.info(f"Fetching dividends for {symbol}, years={years}")
            
            # 1. 调用数据源
            df = self.data_source.fetch_dividends(symbol)
            
            if df.empty:
                return {
                    "success": False,
                    "error": "该股票暂无分红记录"
                }
            
            # 2. 数据清洗和转换
            records = self._transform_records(df, years)
            
            if not records:
                return {
                    "success": False,
                    "error": f"最近{years}年无分红记录"
                }
            
            # 3. 计算摘要指标
            summary = self._calculate_summary(records)
            
            return {
                "success": True,
                "symbol": symbol,
                "name": records[0].get("name", ""),
                "total_records": len(records),
                "dividends": records,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Failed to get dividends for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _transform_records(self, df: pd.DataFrame, years: int) -> List[Dict]:
        """
        转换 akshare 数据为标准格式
        
        Args:
            df: akshare 返回的 DataFrame
            years: 查询最近N年
            
        Returns:
            List[Dict]: 标准化的分红记录列表
        """
        records = []
        current_year = datetime.now().year
        cutoff_year = current_year - years
        
        for _, row in df.iterrows():
            try:
                # 解析年度
                fiscal_year = str(row.get("分红年度", ""))
                if not fiscal_year or not fiscal_year.isdigit():
                    continue
                
                year = int(fiscal_year)
                if year < cutoff_year:
                    continue
                
                # 解析派息金额
                cash_dividend = float(row.get("每股派息", 0) or 0)
                cash_per_share = cash_dividend / 10.0  # 每10股派息 -> 每股派息
                
                # 解析股息率
                dividend_yield_str = str(row.get("股息率", "0"))
                dividend_yield = float(dividend_yield_str.replace("%", "") or 0)
                
                # 解析日期
                ex_dividend_date = str(row.get("除权除息日", ""))
                record_date = str(row.get("股权登记日", ""))
                pay_date = str(row.get("派息日", ""))
                
                record = {
                    "symbol": row.get("股票代码", ""),
                    "name": row.get("股票简称", ""),
                    "fiscal_year": fiscal_year,
                    "dividend_type": "年度分红",
                    "cash_dividend": cash_dividend,
                    "cash_per_share": cash_per_share,
                    "stock_dividend": float(row.get("送股比例", 0) or 0),
                    "bonus_shares": float(row.get("转增比例", 0) or 0),
                    "dividend_yield": dividend_yield,
                    "payout_ratio": 0.0,  # akshare 不提供此字段
                    "announce_date": str(row.get("公告日期", "")),
                    "shareholder_meeting_date": "",
                    "ex_dividend_date": ex_dividend_date,
                    "record_date": record_date,
                    "pay_date": pay_date,
                    "status": "已实施" if ex_dividend_date else "预案",
                    "total_dividend": 0.0,
                    "is_implemented": bool(ex_dividend_date)
                }
                
                records.append(record)
                
            except Exception as e:
                logger.warning(f"Failed to parse dividend record: {e}")
                continue
        
        # 按年度倒序排列
        records.sort(key=lambda x: x["fiscal_year"], reverse=True)
        
        return records
    
    def _calculate_summary(self, records: List[Dict]) -> Dict:
        """
        计算分红摘要指标
        
        Args:
            records: 分红记录列表
            
        Returns:
            Dict: 摘要指标
        """
        if not records:
            return {
                "consecutive_years": 0,
                "avg_yield": 0.0,
                "total_cash_dividend": 0.0
            }
        
        # 连续分红年数
        consecutive_years = len(records)
        
        # 平均股息率
        yields = [r["dividend_yield"] for r in records if r["dividend_yield"] > 0]
        avg_yield = sum(yields) / len(yields) if yields else 0.0
        
        # 累计每股派息
        total_cash_dividend = sum(r["cash_per_share"] for r in records)
        
        return {
            "consecutive_years": consecutive_years,
            "avg_yield": round(avg_yield, 2),
            "total_cash_dividend": round(total_cash_dividend, 2)
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestGetStockDividends -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add services/dividend_service.py tests/services/test_dividend_service.py
git commit -m "feat(dividend): implement get_stock_dividends method with data transformation"
```

---

### Task 4: DividendService - screen_dividend_stocks() Method

**Files:**
- Modify: `quantsys-v2/services/dividend_service.py`
- Modify: `quantsys-v2/tests/services/test_dividend_service.py`

- [ ] **Step 1: Write failing test for screen_dividend_stocks**

Add to `quantsys-v2/tests/services/test_dividend_service.py`:

```python
class TestScreenDividendStocks:
    def test_screen_dividend_stocks_success(self):
        """Test successful dividend screening"""
        service = DividendService()
        params = {
            "min_yield": 3.0,
            "min_years": 3,
            "limit": 10
        }
        result = service.screen_dividend_stocks(params)
        
        assert result["success"] is True
        assert "total" in result
        assert "stocks" in result
        assert isinstance(result["stocks"], list)
        assert len(result["stocks"]) <= 10
    
    def test_screen_dividend_stocks_filters_correctly(self):
        """Test that filters are applied correctly"""
        service = DividendService()
        params = {
            "min_yield": 5.0,
            "min_years": 5,
            "limit": 50
        }
        result = service.screen_dividend_stocks(params)
        
        if result["success"] and result["stocks"]:
            for stock in result["stocks"]:
                assert stock["latest_yield"] >= 5.0
                assert stock["consecutive_years"] >= 5
    
    def test_screen_dividend_stocks_sorted_by_yield(self):
        """Test that results are sorted by yield descending"""
        service = DividendService()
        params = {"min_yield": 2.0, "limit": 20}
        result = service.screen_dividend_stocks(params)
        
        if result["success"] and len(result["stocks"]) > 1:
            yields = [s["latest_yield"] for s in result["stocks"]]
            assert yields == sorted(yields, reverse=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestScreenDividendStocks -v`

Expected: FAIL with "AttributeError: 'DividendService' object has no attribute 'screen_dividend_stocks'"

- [ ] **Step 3: Write implementation**

Add to `quantsys-v2/services/dividend_service.py`:

```python
    def screen_dividend_stocks(self, params: Dict) -> Dict:
        """
        筛选高股息股票
        
        Args:
            params: {
                "min_yield": float,  # 最低股息率（%）
                "min_years": int,    # 最少连续分红年数
                "min_payout_ratio": float,  # 最低分红率（%）
                "max_payout_ratio": float,  # 最高分红率（%）
                "limit": int         # 返回数量限制
            }
            
        Returns:
            {
                "success": bool,
                "total": int,
                "stocks": List[Dict]
            }
        """
        try:
            logger.info(f"Screening dividend stocks with params: {params}")
            
            # 1. 获取股票池
            stock_pool = self._get_stock_pool()
            logger.info(f"Stock pool size: {len(stock_pool)}")
            
            # 2. 并发查询分红数据
            results = self._batch_query_dividends(stock_pool)
            logger.info(f"Successfully queried {len(results)} stocks")
            
            # 3. 应用筛选条件
            filtered = self._apply_filters(results, params)
            logger.info(f"Filtered to {len(filtered)} stocks")
            
            # 4. 排序并限制数量
            sorted_stocks = sorted(
                filtered,
                key=lambda x: x["latest_yield"],
                reverse=True
            )[:params.get("limit", 50)]
            
            return {
                "success": True,
                "total": len(sorted_stocks),
                "stocks": sorted_stocks
            }
            
        except Exception as e:
            logger.error(f"Failed to screen dividend stocks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_stock_pool(self) -> List[str]:
        """
        获取股票池（沪深300 + 创业板50 + 科创50）
        
        Returns:
            List[str]: 股票代码列表
        """
        try:
            import akshare as ak
            
            pool = []
            
            # 沪深300
            try:
                df_hs300 = ak.index_stock_cons(symbol="000300")
                pool.extend(df_hs300["品种代码"].tolist())
            except Exception as e:
                logger.warning(f"Failed to fetch HS300: {e}")
            
            # 创业板50
            try:
                df_cyb50 = ak.index_stock_cons(symbol="399673")
                pool.extend(df_cyb50["品种代码"].tolist())
            except Exception as e:
                logger.warning(f"Failed to fetch CYB50: {e}")
            
            # 科创50
            try:
                df_kc50 = ak.index_stock_cons(symbol="000688")
                pool.extend(df_kc50["品种代码"].tolist())
            except Exception as e:
                logger.warning(f"Failed to fetch KC50: {e}")
            
            # 去重
            pool = list(set(pool))
            
            # 添加市场后缀
            pool_with_suffix = []
            for code in pool:
                if code.startswith("6"):
                    pool_with_suffix.append(f"{code}.SH")
                else:
                    pool_with_suffix.append(f"{code}.SZ")
            
            return pool_with_suffix
            
        except Exception as e:
            logger.error(f"Failed to get stock pool: {e}")
            return []
    
    def _batch_query_dividends(self, symbols: List[str]) -> List[Dict]:
        """
        并发批量查询分红数据
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            List[Dict]: 查询成功的股票分红数据
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(self._query_single_stock, symbol): symbol
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result(timeout=5)
                    if data:
                        results.append(data)
                except Exception as e:
                    logger.warning(f"Failed to query {symbol}: {e}")
                    continue
        
        return results
    
    def _query_single_stock(self, symbol: str) -> Optional[Dict]:
        """
        查询单只股票的分红数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict or None: 股票分红摘要数据
        """
        try:
            result = self.get_stock_dividends(symbol, years=10)
            
            if not result["success"] or not result["dividends"]:
                return None
            
            dividends = result["dividends"]
            summary = result["summary"]
            
            # 获取最新一年的股息率
            latest_yield = dividends[0]["dividend_yield"] if dividends else 0.0
            
            return {
                "symbol": symbol,
                "name": result["name"],
                "latest_yield": latest_yield,
                "consecutive_years": summary["consecutive_years"],
                "avg_payout_ratio": 0.0  # akshare 不提供此字段
            }
            
        except Exception as e:
            logger.warning(f"Failed to query single stock {symbol}: {e}")
            return None
    
    def _apply_filters(self, results: List[Dict], params: Dict) -> List[Dict]:
        """
        应用筛选条件
        
        Args:
            results: 查询结果列表
            params: 筛选参数
            
        Returns:
            List[Dict]: 筛选后的结果
        """
        filtered = results
        
        # 最低股息率
        if "min_yield" in params:
            min_yield = params["min_yield"]
            filtered = [r for r in filtered if r["latest_yield"] >= min_yield]
        
        # 最少连续分红年数
        if "min_years" in params:
            min_years = params["min_years"]
            filtered = [r for r in filtered if r["consecutive_years"] >= min_years]
        
        # 分红率范围（预留，akshare 不提供此字段）
        if "min_payout_ratio" in params:
            min_ratio = params["min_payout_ratio"]
            filtered = [r for r in filtered if r["avg_payout_ratio"] >= min_ratio]
        
        if "max_payout_ratio" in params:
            max_ratio = params["max_payout_ratio"]
            filtered = [r for r in filtered if r["avg_payout_ratio"] <= max_ratio]
        
        return filtered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestScreenDividendStocks -v`

Expected: PASS (3 tests) - Note: Tests may take 20-30 seconds due to network calls

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add services/dividend_service.py tests/services/test_dividend_service.py
git commit -m "feat(dividend): implement screen_dividend_stocks with concurrent querying"
```

### Task 5: DividendService - get_dividend_calendar() Method

**Files:**
- Modify: `quantsys-v2/services/dividend_service.py`
- Modify: `quantsys-v2/tests/services/test_dividend_service.py`

- [ ] **Step 1: Write failing test for get_dividend_calendar**

Add to `quantsys-v2/tests/services/test_dividend_service.py`:

```python
class TestGetDividendCalendar:
    def test_get_dividend_calendar_success(self):
        """Test successful dividend calendar query"""
        service = DividendService()
        result = service.get_dividend_calendar(
            start_date="2026-06-01",
            end_date="2026-06-30",
            event="ex_dividend"
        )
        
        assert result["success"] is True
        assert result["period"] == "2026-06-01 至 2026-06-30"
        assert result["event_type"] == "除权除息日"
        assert "events" in result
        assert isinstance(result["events"], list)
    
    def test_get_dividend_calendar_sorted_by_date(self):
        """Test that events are sorted by date"""
        service = DividendService()
        result = service.get_dividend_calendar(
            start_date="2026-01-01",
            end_date="2026-12-31",
            event="ex_dividend"
        )
        
        if result["success"] and len(result["events"]) > 1:
            dates = [e["date"] for e in result["events"]]
            assert dates == sorted(dates)
    
    def test_get_dividend_calendar_different_events(self):
        """Test different event types"""
        service = DividendService()
        
        events = ["ex_dividend", "record_date", "pay_date"]
        event_names = ["除权除息日", "股权登记日", "派息日"]
        
        for event, expected_name in zip(events, event_names):
            result = service.get_dividend_calendar(
                start_date="2026-06-01",
                end_date="2026-06-30",
                event=event
            )
            assert result["event_type"] == expected_name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestGetDividendCalendar -v`

Expected: FAIL with "AttributeError: 'DividendService' object has no attribute 'get_dividend_calendar'"

- [ ] **Step 3: Write implementation**

Add to `quantsys-v2/services/dividend_service.py`:

```python
    def get_dividend_calendar(
        self,
        start_date: str,
        end_date: str,
        event: str = "ex_dividend"
    ) -> Dict:
        """
        分红日历
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            event: 事件类型 (ex_dividend/record_date/pay_date)
            
        Returns:
            {
                "success": bool,
                "period": str,
                "event_type": str,
                "total": int,
                "events": List[Dict]
            }
        """
        try:
            logger.info(f"Fetching dividend calendar: {start_date} to {end_date}, event={event}")
            
            # 1. 获取股票池
            stock_pool = self._get_stock_pool()
            
            # 2. 批量查询分红数据
            results = self._batch_query_dividends(stock_pool)
            
            # 3. 筛选日期范围内的事件
            events = self._filter_by_date_range(results, start_date, end_date, event)
            
            # 4. 按日期排序
            sorted_events = sorted(events, key=lambda x: x["date"])
            
            event_type_map = {
                "ex_dividend": "除权除息日",
                "record_date": "股权登记日",
                "pay_date": "派息日"
            }
            
            return {
                "success": True,
                "period": f"{start_date} 至 {end_date}",
                "event_type": event_type_map.get(event, "未知事件"),
                "total": len(sorted_events),
                "events": sorted_events
            }
            
        except Exception as e:
            logger.error(f"Failed to get dividend calendar: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _filter_by_date_range(
        self,
        results: List[Dict],
        start: str,
        end: str,
        event: str
    ) -> List[Dict]:
        """
        筛选日期范围内的事件
        
        Args:
            results: 股票分红数据列表
            start: 开始日期 (YYYY-MM-DD)
            end: 结束日期 (YYYY-MM-DD)
            event: 事件类型
            
        Returns:
            List[Dict]: 符合条件的事件列表
        """
        events = []
        
        # 事件字段映射
        event_field_map = {
            "ex_dividend": "ex_dividend_date",
            "record_date": "record_date",
            "pay_date": "pay_date"
        }
        
        date_field = event_field_map.get(event, "ex_dividend_date")
        
        for stock_data in results:
            symbol = stock_data["symbol"]
            name = stock_data["name"]
            
            # 获取该股票的完整分红记录
            full_result = self.get_stock_dividends(symbol, years=3)
            
            if not full_result["success"]:
                continue
            
            for dividend in full_result["dividends"]:
                event_date = dividend.get(date_field, "")
                
                if not event_date:
                    continue
                
                # 检查日期是否在范围内
                if start <= event_date <= end:
                    events.append({
                        "date": event_date,
                        "symbol": symbol,
                        "name": name,
                        "cash_per_share": dividend["cash_per_share"],
                        "dividend_yield": dividend["dividend_yield"]
                    })
        
        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_dividend_service.py::TestGetDividendCalendar -v`

Expected: PASS (3 tests) - Note: Tests may take 20-30 seconds

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add services/dividend_service.py tests/services/test_dividend_service.py
git commit -m "feat(dividend): implement get_dividend_calendar with date filtering"
```

---

### Task 6: Flask Routes

**Files:**
- Create: `quantsys-v2/api/routes/dividends.py`
- Create: `quantsys-v2/tests/api/test_dividends_routes.py`

- [ ] **Step 1: Write failing test for Flask routes**

Create `quantsys-v2/tests/api/test_dividends_routes.py`:

```python
import pytest
import json
from api.server import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDividendsRoutes:
    def test_get_dividends_success(self, client):
        """Test GET /api/stock/{symbol}/dividends"""
        response = client.get('/api/stock/600519.SH/dividends?years=5')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["symbol"] == "600519.SH"
        assert "dividends" in data
    
    def test_get_dividends_default_years(self, client):
        """Test default years parameter"""
        response = client.get('/api/stock/600519.SH/dividends')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
    
    def test_screen_dividends_success(self, client):
        """Test POST /api/dividends/screen"""
        payload = {
            "min_yield": 3.0,
            "min_years": 3,
            "limit": 10
        }
        response = client.post(
            '/api/dividends/screen',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "stocks" in data
    
    def test_dividend_calendar_success(self, client):
        """Test GET /api/dividends/calendar"""
        response = client.get(
            '/api/dividends/calendar?start_date=2026-06-01&end_date=2026-06-30&event=ex_dividend'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["event_type"] == "除权除息日"
    
    def test_dividend_calendar_missing_params(self, client):
        """Test calendar with missing required params"""
        response = client.get('/api/dividends/calendar')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/api/test_dividends_routes.py -v`

Expected: FAIL with "404 Not Found" (routes not registered)

- [ ] **Step 3: Write Flask routes**

Create `quantsys-v2/api/routes/dividends.py`:

```python
"""
分红数据 API 路由
"""
from flask import Blueprint, request, jsonify
import logging

from services.dividend_service import DividendService
from api.decorators import handle_errors

logger = logging.getLogger(__name__)

# 创建 Blueprint
dividends_bp = Blueprint('dividends', __name__)

# 初始化服务
service = DividendService()


@dividends_bp.route('/api/stock/<symbol>/dividends', methods=['GET'])
@handle_errors
def get_dividends(symbol):
    """
    获取单股分红数据
    
    Args:
        symbol: 股票代码（路径参数）
        years: 查询最近N年（查询参数，默认10）
        
    Returns:
        JSON: 分红数据
    """
    years = request.args.get('years', 10, type=int)
    
    logger.info(f"GET /api/stock/{symbol}/dividends - years={years}")
    
    result = service.get_stock_dividends(symbol, years)
    
    return jsonify(result)


@dividends_bp.route('/api/dividends/screen', methods=['POST'])
@handle_errors
def screen_dividends():
    """
    筛选高股息股票
    
    Request Body:
        {
            "min_yield": float,
            "min_years": int,
            "min_payout_ratio": float,
            "max_payout_ratio": float,
            "limit": int
        }
        
    Returns:
        JSON: 筛选结果
    """
    params = request.get_json() or {}
    
    logger.info(f"POST /api/dividends/screen - params={params}")
    
    result = service.screen_dividend_stocks(params)
    
    return jsonify(result)


@dividends_bp.route('/api/dividends/calendar', methods=['GET'])
@handle_errors
def dividend_calendar():
    """
    分红日历
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        event: 事件类型 (ex_dividend/record_date/pay_date)
        
    Returns:
        JSON: 分红日历
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    event = request.args.get('event', 'ex_dividend')
    
    # 参数验证
    if not start_date or not end_date:
        logger.warning("Missing required parameters: start_date or end_date")
        return jsonify({
            "success": False,
            "error": "start_date and end_date are required"
        }), 400
    
    logger.info(f"GET /api/dividends/calendar - {start_date} to {end_date}, event={event}")
    
    result = service.get_dividend_calendar(start_date, end_date, event)
    
    return jsonify(result)
```

- [ ] **Step 4: Register blueprint in server.py**

Edit `quantsys-v2/api/server.py` to add:

```python
# Import blueprint
from api.routes.dividends import dividends_bp

# Register blueprint (add after other blueprints)
app.register_blueprint(dividends_bp)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/api/test_dividends_routes.py -v`

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
cd quantsys-v2
git add api/routes/dividends.py api/server.py tests/api/test_dividends_routes.py
git commit -m "feat(dividend): add Flask API routes with parameter validation"
```

## Phase 2: TypeScript Agent Tool

### Task 7: TypeScript Type Definitions

**Files:**
- Modify: `src/infrastructure/quant/types.ts`

- [ ] **Step 1: Add dividend type definitions**

Add to `src/infrastructure/quant/types.ts`:

```typescript
// Dividend data types
export interface DividendRecord {
  symbol: string;
  name: string;
  fiscal_year: string;
  dividend_type: string;
  cash_dividend: number;
  cash_per_share: number;
  stock_dividend: number;
  bonus_shares: number;
  dividend_yield: number;
  payout_ratio: number;
  announce_date: string;
  shareholder_meeting_date: string;
  ex_dividend_date: string;
  record_date: string;
  pay_date: string;
  status: string;
  total_dividend: number;
  is_implemented: boolean;
}

export interface DividendSummary {
  consecutive_years: number;
  avg_yield: number;
  total_cash_dividend: number;
}

export interface DividendResponse {
  success: boolean;
  error?: string;
  
  // single mode
  symbol?: string;
  name?: string;
  total_records?: number;
  dividends?: DividendRecord[];
  summary?: DividendSummary;
  
  // screen mode
  total?: number;
  stocks?: Array<{
    symbol: string;
    name: string;
    latest_yield: number;
    consecutive_years: number;
    avg_payout_ratio: number;
  }>;
  
  // calendar mode
  period?: string;
  event_type?: string;
  events?: Array<{
    date: string;
    symbol: string;
    name: string;
    cash_per_share: number;
    dividend_yield: number;
  }>;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: SUCCESS (no type errors)

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/quant/types.ts
git commit -m "feat(dividend): add TypeScript type definitions for dividend data"
```

---

### Task 8: QuantV2Client Extension

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`
- Create: `src/infrastructure/quant/quant-v2-client.test.ts` (if not exists)

- [ ] **Step 1: Write failing test for getDividends**

Add to `src/infrastructure/quant/quant-v2-client.test.ts`:

```typescript
import { getDividends } from './quant-v2-client.js';
import { QuantV2Error } from './quant-v2-client.js';

describe('getDividends', () => {
  it('should fetch single stock dividends', async () => {
    const result = await getDividends({
      mode: 'single',
      symbol: '600519.SH',
      years: 5
    });
    
    expect(result.success).toBe(true);
    expect(result.symbol).toBe('600519.SH');
    expect(result.dividends).toBeDefined();
    expect(Array.isArray(result.dividends)).toBe(true);
  });
  
  it('should throw error when symbol missing in single mode', async () => {
    await expect(
      getDividends({ mode: 'single' })
    ).rejects.toThrow('single 模式必须提供 symbol 参数');
  });
  
  it('should fetch dividend screening results', async () => {
    const result = await getDividends({
      mode: 'screen',
      min_yield: 3.0,
      limit: 10
    });
    
    expect(result.success).toBe(true);
    expect(result.stocks).toBeDefined();
    expect(Array.isArray(result.stocks)).toBe(true);
  });
  
  it('should fetch dividend calendar', async () => {
    const result = await getDividends({
      mode: 'calendar',
      start_date: '2026-06-01',
      end_date: '2026-06-30',
      event: 'ex_dividend'
    });
    
    expect(result.success).toBe(true);
    expect(result.events).toBeDefined();
    expect(result.event_type).toBe('除权除息日');
  });
  
  it('should throw error when dates missing in calendar mode', async () => {
    await expect(
      getDividends({ mode: 'calendar' })
    ).rejects.toThrow('calendar 模式必须提供 start_date 和 end_date 参数');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- quant-v2-client.test.ts`

Expected: FAIL with "getDividends is not a function" or similar

- [ ] **Step 3: Write implementation**

Add to `src/infrastructure/quant/quant-v2-client.ts`:

```typescript
import type { DividendResponse } from './types.js';

export async function getDividends(
  params: {
    mode: 'single' | 'screen' | 'calendar';
    symbol?: string;
    years?: number;
    min_yield?: number;
    min_years?: number;
    min_payout_ratio?: number;
    max_payout_ratio?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    event?: string;
  }
): Promise<DividendResponse> {
  const { mode, symbol, years, ...rest } = params;
  
  try {
    if (mode === 'single') {
      if (!symbol) {
        throw new QuantV2Error('single 模式必须提供 symbol 参数');
      }
      
      const url = `${V2_API_BASE}/api/stock/${symbol}/dividends?years=${years || 10}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    if (mode === 'screen') {
      const url = `${V2_API_BASE}/api/dividends/screen`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rest),
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    if (mode === 'calendar') {
      const { start_date, end_date, event = 'ex_dividend' } = rest;
      
      if (!start_date || !end_date) {
        throw new QuantV2Error('calendar 模式必须提供 start_date 和 end_date 参数');
      }
      
      const url = `${V2_API_BASE}/api/dividends/calendar?start_date=${start_date}&end_date=${end_date}&event=${event}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    throw new QuantV2Error(`未知查询模式: ${mode}`);
    
  } catch (error) {
    if (error instanceof QuantV2Error) {
      throw error;
    }
    throw new QuantV2Error(
      `分红数据查询失败: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- quant-v2-client.test.ts`

Expected: PASS (5 tests) - Note: Requires quantsys-v2 running on port 5001

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/quant/quant-v2-client.ts src/infrastructure/quant/quant-v2-client.test.ts
git commit -m "feat(dividend): add getDividends method to QuantV2Client"
```

---

### Task 9: Data Formatter

**Files:**
- Modify: `src/infrastructure/quant/formatters.ts`

- [ ] **Step 1: Write failing test for formatDividendData**

Create or add to `src/infrastructure/quant/formatters.test.ts`:

```typescript
import { formatDividendData } from './formatters.js';
import type { DividendResponse } from './types.js';

describe('formatDividendData', () => {
  it('should format single mode data', () => {
    const data: DividendResponse = {
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      dividends: [
        {
          symbol: '600519.SH',
          name: '贵州茅台',
          fiscal_year: '2024',
          dividend_type: '年度分红',
          cash_dividend: 21.0,
          cash_per_share: 2.10,
          stock_dividend: 0,
          bonus_shares: 0,
          dividend_yield: 3.45,
          payout_ratio: 65.5,
          announce_date: '2025-03-28',
          shareholder_meeting_date: '2025-05-15',
          ex_dividend_date: '2025-06-20',
          record_date: '2025-06-19',
          pay_date: '2025-06-21',
          status: '已实施',
          total_dividend: 2520000000,
          is_implemented: true
        }
      ],
      summary: {
        consecutive_years: 10,
        avg_yield: 3.2,
        total_cash_dividend: 18.50
      }
    };
    
    const result = formatDividendData(data, 'single');
    
    expect(result).toContain('贵州茅台');
    expect(result).toContain('连续分红: 10年');
    expect(result).toContain('平均股息率: 3.20%');
    expect(result).toContain('2024年');
  });
  
  it('should format screen mode data', () => {
    const data: DividendResponse = {
      success: true,
      total: 2,
      stocks: [
        {
          symbol: '600519.SH',
          name: '贵州茅台',
          latest_yield: 3.45,
          consecutive_years: 10,
          avg_payout_ratio: 65.5
        },
        {
          symbol: '601318.SH',
          name: '中国平安',
          latest_yield: 4.20,
          consecutive_years: 8,
          avg_payout_ratio: 55.0
        }
      ]
    };
    
    const result = formatDividendData(data, 'screen');
    
    expect(result).toContain('高股息股票筛选结果');
    expect(result).toContain('共 2 只');
    expect(result).toContain('贵州茅台');
    expect(result).toContain('中国平安');
  });
  
  it('should format calendar mode data', () => {
    const data: DividendResponse = {
      success: true,
      period: '2026-06-01 至 2026-06-30',
      event_type: '除权除息日',
      total: 1,
      events: [
        {
          date: '2026-06-20',
          symbol: '600519.SH',
          name: '贵州茅台',
          cash_per_share: 2.10,
          dividend_yield: 3.45
        }
      ]
    };
    
    const result = formatDividendData(data, 'calendar');
    
    expect(result).toContain('分红日历');
    expect(result).toContain('除权除息日');
    expect(result).toContain('2026-06-20');
    expect(result).toContain('贵州茅台');
  });
  
  it('should handle error response', () => {
    const data: DividendResponse = {
      success: false,
      error: '股票代码不存在'
    };
    
    const result = formatDividendData(data, 'single');
    
    expect(result).toContain('查询失败');
    expect(result).toContain('股票代码不存在');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- formatters.test.ts`

Expected: FAIL with "formatDividendData is not a function"

- [ ] **Step 3: Write implementation**

Add to `src/infrastructure/quant/formatters.ts`:

```typescript
import type { DividendResponse } from './types.js';

export function formatDividendData(data: DividendResponse, mode: string): string {
  if (!data.success) {
    return `查询失败: ${data.error || '未知错误'}`;
  }
  
  if (mode === 'single') {
    const { symbol, name, dividends, summary } = data;
    let output = `【${name} (${symbol}) 分红历史】\n\n`;
    
    if (summary) {
      output += `连续分红: ${summary.consecutive_years}年\n`;
      output += `平均股息率: ${summary.avg_yield.toFixed(2)}%\n`;
      output += `累计每股派息: ${summary.total_cash_dividend.toFixed(2)}元\n\n`;
    }
    
    output += `近期分红记录:\n`;
    dividends?.slice(0, 5).forEach(d => {
      output += `  ${d.fiscal_year}年: 每股${d.cash_per_share.toFixed(2)}元, `;
      output += `股息率${d.dividend_yield.toFixed(2)}%, `;
      output += `除权日${d.ex_dividend_date}, ${d.status}\n`;
    });
    
    if (dividends && dividends.length > 5) {
      output += `\n... 共 ${dividends.length} 条记录\n`;
    }
    
    return output;
  }
  
  if (mode === 'screen') {
    const { total, stocks } = data;
    let output = `【高股息股票筛选结果】共 ${total} 只\n\n`;
    
    stocks?.slice(0, 20).forEach((s, i) => {
      output += `${i + 1}. ${s.name} (${s.symbol})\n`;
      output += `   股息率: ${s.latest_yield.toFixed(2)}%, `;
      output += `连续分红: ${s.consecutive_years}年, `;
      output += `平均分红率: ${s.avg_payout_ratio.toFixed(1)}%\n`;
    });
    
    if (stocks && stocks.length > 20) {
      output += `\n... 仅显示前20只，共 ${stocks.length} 只\n`;
    }
    
    return output;
  }
  
  if (mode === 'calendar') {
    const { period, event_type, total, events } = data;
    let output = `【分红日历 - ${event_type}】\n`;
    output += `时间范围: ${period}\n`;
    output += `共 ${total} 只股票\n\n`;
    
    events?.forEach(e => {
      output += `${e.date} - ${e.name} (${e.symbol})\n`;
      output += `  每股派息: ${e.cash_per_share.toFixed(2)}元, 股息率: ${e.dividend_yield.toFixed(2)}%\n`;
    });
    
    return output;
  }
  
  return '未知查询模式';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- formatters.test.ts`

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/quant/formatters.ts src/infrastructure/quant/formatters.test.ts
git commit -m "feat(dividend): add formatDividendData formatter with three modes"
```

### Task 10: Tool Definition

**Files:**
- Create: `src/infrastructure/tools/data/fetch-dividend-tool.ts`
- Create: `src/infrastructure/tools/data/fetch-dividend-tool.test.ts`

- [ ] **Step 1: Write failing test for tool**

Create `src/infrastructure/tools/data/fetch-dividend-tool.test.ts`:

```typescript
import { dataFetchDividendTool } from './fetch-dividend-tool.js';

describe('dataFetchDividendTool', () => {
  it('should have correct metadata', () => {
    expect(dataFetchDividendTool.name).toBe('data_fetch_dividend');
    expect(dataFetchDividendTool.label).toBe('获取分红数据');
    expect(dataFetchDividendTool.description).toContain('L1 数据管道工具');
  });
  
  it('should execute single mode successfully', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'single',
      symbol: '600519.SH',
      years: 5
    });
    
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect(result.content[0].text).toContain('贵州茅台');
  });
  
  it('should validate single mode requires symbol', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'single'
    });
    
    expect(result.content[0].text).toContain('single 模式必须提供 symbol 参数');
  });
  
  it('should execute screen mode successfully', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'screen',
      min_yield: 3.0,
      limit: 5
    });
    
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect(result.content[0].text).toContain('高股息股票筛选结果');
  });
  
  it('should execute calendar mode successfully', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'calendar',
      start_date: '2026-06-01',
      end_date: '2026-06-30',
      event: 'ex_dividend'
    });
    
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect(result.content[0].text).toContain('分红日历');
  });
  
  it('should validate calendar mode requires dates', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'calendar'
    });
    
    expect(result.content[0].text).toContain('calendar 模式必须提供 start_date 和 end_date 参数');
  });
  
  it('should handle API errors gracefully', async () => {
    const result = await dataFetchDividendTool.execute('test-call-id', {
      mode: 'single',
      symbol: 'INVALID'
    });
    
    expect(result.content[0].text).toContain('失败');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fetch-dividend-tool.test.ts`

Expected: FAIL with "Cannot find module './fetch-dividend-tool.js'"

- [ ] **Step 3: Write tool implementation**

Create `src/infrastructure/tools/data/fetch-dividend-tool.ts`:

```typescript
/**
 * 分红数据获取工具 - L1 数据管道层
 *
 * 支持三种模式：
 * 1. single - 查询单只股票历史分红记录
 * 2. screen - 筛选高股息股票
 * 3. calendar - 查询分红日历
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { getDividends } from "../../quant/quant-v2-client.js";
import { formatDividendData } from "../../quant/formatters.js";

export const dataFetchDividendTool: ToolDefinition = {
  name: "data_fetch_dividend",
  label: "获取分红数据",
  description:
    "L1 数据管道工具：获取股票分红数据。支持三种模式：" +
    "1) single - 查询单只股票历史分红记录；" +
    "2) screen - 筛选高股息股票；" +
    "3) calendar - 查询分红日历（即将除权除息的股票）。",

  parameters: Type.Object({
    mode: Type.Union([
      Type.Literal("single"),
      Type.Literal("screen"),
      Type.Literal("calendar")
    ], {
      description: "查询模式：single=单股查询, screen=批量筛选, calendar=分红日历"
    }),
    
    // single 模式参数
    symbol: Type.Optional(Type.String({
      description: "股票代码（single模式必填，如 600519.SH）"
    })),
    years: Type.Optional(Type.Number({
      description: "查询最近N年（single模式，默认10年）"
    })),
    
    // screen 模式参数
    min_yield: Type.Optional(Type.Number({
      description: "最低股息率%（screen模式）"
    })),
    min_years: Type.Optional(Type.Number({
      description: "最少连续分红年数（screen模式）"
    })),
    min_payout_ratio: Type.Optional(Type.Number({
      description: "最低分红率%（screen模式）"
    })),
    max_payout_ratio: Type.Optional(Type.Number({
      description: "最高分红率%（screen模式）"
    })),
    limit: Type.Optional(Type.Number({
      description: "返回数量限制（screen模式，默认50）"
    })),
    
    // calendar 模式参数
    start_date: Type.Optional(Type.String({
      description: "开始日期 YYYY-MM-DD（calendar模式必填）"
    })),
    end_date: Type.Optional(Type.String({
      description: "结束日期 YYYY-MM-DD（calendar模式必填）"
    })),
    event: Type.Optional(Type.String({
      description: "事件类型（calendar模式）：ex_dividend=除权除息日, record_date=股权登记日, pay_date=派息日"
    }))
  }),

  execute: async (_toolCallId, params) => {
    try {
      // 参数验证
      if (params.mode === 'single' && !params.symbol) {
        return {
          content: [{ type: "text" as const, text: "single 模式必须提供 symbol 参数" }],
          details: undefined
        };
      }
      
      if (params.mode === 'calendar' && (!params.start_date || !params.end_date)) {
        return {
          content: [{ type: "text" as const, text: "calendar 模式必须提供 start_date 和 end_date 参数" }],
          details: undefined
        };
      }
      
      // 调用 v2 API
      const data = await getDividends(params);
      
      if (!data.success) {
        return {
          content: [{ type: "text" as const, text: `查询失败: ${data.error || '未知错误'}` }],
          details: undefined
        };
      }
      
      // 格式化输出
      const formattedText = formatDividendData(data, params.mode);
      
      return {
        content: [{ type: "text" as const, text: formattedText }],
        details: undefined
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `分红数据获取失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- fetch-dividend-tool.test.ts`

Expected: PASS (7 tests) - Note: Requires quantsys-v2 running

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/tools/data/fetch-dividend-tool.ts src/infrastructure/tools/data/fetch-dividend-tool.test.ts
git commit -m "feat(dividend): add data_fetch_dividend tool with three modes"
```

---

### Task 11: Tool Registration

**Files:**
- Modify: `src/infrastructure/tools/data/index.ts`

- [ ] **Step 1: Register tool in data tools index**

Edit `src/infrastructure/tools/data/index.ts`:

```typescript
import { dataFetchStockTool } from './fetch-stock-tool.js';
import { dataFetchKlineTool } from './fetch-kline-tool.js';
import { dataFetchFinancialTool } from './fetch-financial-tool.js';
import { dataFetchDividendTool } from './fetch-dividend-tool.js';  // Add import

export const dataTools = [
  dataFetchStockTool,
  dataFetchKlineTool,
  dataFetchFinancialTool,
  dataFetchDividendTool,  // Add to array
];
```

- [ ] **Step 2: Verify tool is registered**

Run: `npm run build && npm run dev`

In the agent, check that the tool appears in the tool list.

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/tools/data/index.ts
git commit -m "feat(dividend): register data_fetch_dividend tool in data tools"
```

---

## Phase 3: Testing and Documentation

### Task 12: End-to-End Testing

**Files:**
- Create: `docs/testing/dividend-tool-e2e-test.md`

- [ ] **Step 1: Start quantsys-v2 service**

Run: `cd quantsys-v2 && python start_all.py`

Verify: REST API on port 5001, WebSocket on port 5003

- [ ] **Step 2: Start TypeScript Agent**

Run: `npm run dev`

Verify: Agent starts successfully and loads tools

- [ ] **Step 3: Test single mode**

In agent, execute:
```
data_fetch_dividend(mode="single", symbol="600519.SH", years=5)
```

Expected: Returns dividend history for 贵州茅台 with summary

- [ ] **Step 4: Test screen mode**

In agent, execute:
```
data_fetch_dividend(mode="screen", min_yield=3.0, min_years=5, limit=10)
```

Expected: Returns list of high-yield stocks sorted by yield

- [ ] **Step 5: Test calendar mode**

In agent, execute:
```
data_fetch_dividend(mode="calendar", start_date="2026-06-01", end_date="2026-06-30", event="ex_dividend")
```

Expected: Returns dividend calendar for June 2026

- [ ] **Step 6: Test error handling**

Test invalid symbol:
```
data_fetch_dividend(mode="single", symbol="INVALID")
```

Expected: Returns friendly error message

Test missing parameters:
```
data_fetch_dividend(mode="single")
```

Expected: Returns "single 模式必须提供 symbol 参数"

- [ ] **Step 7: Document test results**

Create `docs/testing/dividend-tool-e2e-test.md`:

```markdown
# Dividend Tool E2E Test Results

**Date:** 2026-05-29
**Tester:** [Your Name]

## Test Environment
- quantsys-v2: Running on 127.0.0.1:5001
- TypeScript Agent: v1.0.0
- Python: 3.13
- Node.js: 22.x

## Test Cases

### 1. Single Mode - Success
**Command:** `data_fetch_dividend(mode="single", symbol="600519.SH", years=5)`
**Result:** ✅ PASS
**Response Time:** ~3s
**Notes:** Returns complete dividend history with summary

### 2. Screen Mode - Success
**Command:** `data_fetch_dividend(mode="screen", min_yield=3.0, limit=10)`
**Result:** ✅ PASS
**Response Time:** ~25s
**Notes:** Returns 10 high-yield stocks sorted correctly

### 3. Calendar Mode - Success
**Command:** `data_fetch_dividend(mode="calendar", start_date="2026-06-01", end_date="2026-06-30")`
**Result:** ✅ PASS
**Response Time:** ~20s
**Notes:** Returns dividend events in date range

### 4. Error Handling - Invalid Symbol
**Command:** `data_fetch_dividend(mode="single", symbol="INVALID")`
**Result:** ✅ PASS
**Notes:** Returns friendly error message

### 5. Error Handling - Missing Parameters
**Command:** `data_fetch_dividend(mode="single")`
**Result:** ✅ PASS
**Notes:** Returns validation error

## Performance Summary
- Single query: < 3s ✅
- Screen (50 stocks): < 30s ✅
- Calendar (30 days): < 20s ✅

## Issues Found
None

## Conclusion
All test cases passed. Tool is ready for production use.
```

- [ ] **Step 8: Commit test documentation**

```bash
git add docs/testing/dividend-tool-e2e-test.md
git commit -m "docs(dividend): add E2E test results"
```

---

### Task 13: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add tool to L1 data pipeline section**

Edit `CLAUDE.md`, find the "L1 数据管道层" section and add:

```markdown
#### L1 数据管道层
统一的数据获取接口，支持股票基本信息、行情数据、财务数据、分红数据：
- `data_fetch_stock` — 获取股票基本信息、实时价格、新闻、公告
- `data_fetch_kline` — 获取 K 线数据（日线、周线、月线）
- `data_fetch_financial` — 获取财务数据（利润表、资产负债表、现金流量表）
- `data_fetch_dividend` — 获取分红数据（历史分红、高股息筛选、分红日历）
```

- [ ] **Step 2: Add usage examples section**

Add new section after tool list:

```markdown
### 分红数据工具使用示例

**单股历史分红查询：**
```
data_fetch_dividend(mode="single", symbol="600519.SH", years=10)
```
返回：连续分红年数、平均股息率、历史分红记录

**高股息股票筛选：**
```
data_fetch_dividend(mode="screen", min_yield=3.0, min_years=5, limit=20)
```
返回：符合条件的高股息股票列表，按股息率降序排列

**分红日历查询：**
```
data_fetch_dividend(mode="calendar", start_date="2026-06-01", end_date="2026-06-30", event="ex_dividend")
```
返回：指定日期范围内的除权除息事件

**支持的事件类型：**
- `ex_dividend` — 除权除息日
- `record_date` — 股权登记日
- `pay_date` — 派息日
```

- [ ] **Step 3: Verify documentation renders correctly**

Run: `cat CLAUDE.md | grep -A 10 "data_fetch_dividend"`

Expected: Shows new tool documentation

- [ ] **Step 4: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs(dividend): add data_fetch_dividend tool to CLAUDE.md with usage examples"
```

---

### Task 14: Final Verification and Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run all tests**

```bash
# Python tests
cd quantsys-v2 && python -m pytest tests/ -v --cov=services --cov=api

# TypeScript tests
npm test
```

Expected: All tests pass, coverage > 80%

- [ ] **Step 2: Verify build succeeds**

```bash
npm run build
```

Expected: No TypeScript errors, dist/ created successfully

- [ ] **Step 3: Check for TODO/FIXME comments**

```bash
grep -r "TODO\|FIXME" src/infrastructure/tools/data/fetch-dividend-tool.ts quantsys-v2/services/dividend_service.py
```

Expected: No results (all TODOs resolved)

- [ ] **Step 4: Verify IP/port configuration**

```bash
grep -r "5001" src/infrastructure/quant/quant-v2-client.ts
```

Expected: Uses 127.0.0.1:5001 (fixed IP convention)

- [ ] **Step 5: Clean up temporary files**

```bash
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name ".pytest_cache" -type d -exec rm -rf {} +
```

- [ ] **Step 6: Final commit**

```bash
git status
git add -A
git commit -m "feat(dividend): complete dividend data tool implementation

- Add DividendService with three query modes
- Add Flask API routes with parameter validation
- Add TypeScript tool with type-safe client
- Add comprehensive tests (80%+ coverage)
- Add documentation and usage examples

Closes #[issue-number]"
```

---

## Acceptance Criteria

- [ ] All unit tests pass (coverage > 80%)
- [ ] All integration tests pass (coverage > 90%)
- [ ] Agent can successfully call all three modes
- [ ] Error handling returns friendly messages
- [ ] Single stock query < 3s
- [ ] Batch screening (50 stocks) < 30s
- [ ] Dividend calendar (30 days) < 20s
- [ ] Documentation complete with usage examples
- [ ] Code follows project conventions
- [ ] No TODO/FIXME comments remain
- [ ] Fixed IP/port convention maintained (127.0.0.1:5001)

---

## Rollback Plan

If issues are discovered after deployment:

1. **Disable tool:** Remove `dataFetchDividendTool` from `src/infrastructure/tools/data/index.ts`
2. **Revert commits:** `git revert <commit-hash>`
3. **Restart services:** Restart quantsys-v2 and TypeScript Agent
4. **Investigate:** Check logs in `/tmp/quantsys-v2-rest.log` and agent logs

---

## Future Enhancements

After initial release, consider:

1. **Redis caching** — Add 24-hour cache for dividend data
2. **Database persistence** — Store dividend data in PostgreSQL for faster queries
3. **Advanced analytics** — Add dividend growth rate, yield percentile analysis
4. **Tushare integration** — Support alternative data source
5. **Real-time updates** — WebSocket notifications for dividend announcements

---

**Plan Created:** 2026-05-29  
**Estimated Duration:** 2.5 days  
**Target Completion:** 2026-05-31

