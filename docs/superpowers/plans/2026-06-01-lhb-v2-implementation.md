# 龙虎榜 V2 功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 quantsys-v2 中实现龙虎榜查询功能，支持单股查询和日期汇总，替代依赖 v1 的旧实现

**Architecture:** 复用 DividendService 模式，采用 DataSource + Service + API Route 三层架构，实时查询 akshare API

**Tech Stack:** Python 3.13, Flask, akshare, pandas, lxml, pytest

---

## 文件结构

**新增文件**:
- `quantsys-v2/services/lhb_data_source.py` - 数据源抽象层 + akshare 实现
- `quantsys-v2/services/lhb_service.py` - 业务逻辑服务层
- `quantsys-v2/tests/services/test_lhb_service.py` - 服务层单元测试
- `quantsys-v2/tests/api/test_lhb_routes.py` - API 路由集成测试

**修改文件**:
- `quantsys-v2/api/routes/sentiment.py:77-90` - 更新 lhb 路由实现
- `quantsys-v2/requirements.txt` - 添加 lxml 依赖

---

## Task 1: 添加 lxml 依赖

**Files:**
- Modify: `quantsys-v2/requirements.txt`

- [ ] **Step 1: 添加 lxml 依赖到 requirements.txt**

```bash
cd quantsys-v2
echo "lxml>=4.9.0" >> requirements.txt
```

- [ ] **Step 2: 安装依赖**

Run: `pip install lxml`
Expected: Successfully installed lxml-4.x.x

- [ ] **Step 3: 验证安装**

Run: `python -c "import lxml; print(lxml.__version__)"`
Expected: 输出版本号（如 4.9.3）

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add lxml for akshare lhb API support"
```

---


## Task 2: 实现数据源层 - LhbDataSource 抽象类

**Files:**
- Create: `quantsys-v2/services/lhb_data_source.py`

- [ ] **Step 1: 创建文件并写入抽象基类**

```python
"""
龙虎榜数据源抽象层

提供统一的数据源接口，支持未来扩展到 tushare 或其他数据源。
"""
from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class LhbDataSource(ABC):
    """龙虎榜数据源抽象基类"""

    @abstractmethod
    def fetch_stock_lhb(self, symbol: str) -> pd.DataFrame:
        """
        获取个股龙虎榜统计

        Args:
            symbol: 股票代码或名称（如 600737 或 中粮糖业）

        Returns:
            pd.DataFrame: 龙虎榜记录

        Raises:
            Exception: 数据获取失败
        """
        pass

    @abstractmethod
    def fetch_daily_lhb(self, date: str) -> pd.DataFrame:
        """
        获取某日全市场龙虎榜

        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）

        Returns:
            pd.DataFrame: 当日所有上榜股票

        Raises:
            Exception: 数据获取失败
        """
        pass
```

- [ ] **Step 2: 验证文件创建**

Run: `ls -la quantsys-v2/services/lhb_data_source.py`
Expected: 文件存在

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/services/lhb_data_source.py
git commit -m "feat(lhb): add LhbDataSource abstract base class"
```

---


## Task 3: 实现 AkshareLhbSource - 个股查询

**Files:**
- Modify: `quantsys-v2/services/lhb_data_source.py`

- [ ] **Step 1: 添加 AkshareLhbSource 类和 fetch_stock_lhb 方法**

```python
class AkshareLhbSource(LhbDataSource):
    """akshare 数据源实现"""

    def __init__(self, timeout: int = 30):
        """
        初始化 akshare 数据源

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout

    def fetch_stock_lhb(self, symbol: str) -> pd.DataFrame:
        """
        从 akshare 获取个股龙虎榜统计

        Args:
            symbol: 股票代码（如 600737 或 600737.SH）

        Returns:
            pd.DataFrame: 龙虎榜记录

        Raises:
            Exception: akshare API 调用失败
        """
        import akshare as ak

        # 移除后缀（akshare 只需要6位代码）
        code = symbol.split('.')[0]

        logger.info(f"Fetching LHB data from akshare for {code}")

        try:
            # 先获取股票名称
            stock_info_df = ak.stock_individual_info_em(symbol=code)
            if stock_info_df.empty:
                raise Exception(f"股票代码 {code} 不存在")
            
            # 提取股票名称
            stock_name = stock_info_df[stock_info_df['item'] == '股票简称']['value'].values[0]
            
            # 使用股票名称查询龙虎榜
            df = ak.stock_lhb_stock_statistic_em(symbol=stock_name)
            
            logger.info(f"Fetched {len(df)} LHB records for {code} ({stock_name})")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch LHB data for {code}: {e}")
            raise

    def fetch_daily_lhb(self, date: str) -> pd.DataFrame:
        """占位符，下一个任务实现"""
        pass
```

- [ ] **Step 2: 验证语法**

Run: `python -m py_compile quantsys-v2/services/lhb_data_source.py`
Expected: 无输出（编译成功）

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/services/lhb_data_source.py
git commit -m "feat(lhb): implement AkshareLhbSource.fetch_stock_lhb"
```

---


## Task 4: 实现 AkshareLhbSource - 日期汇总查询

**Files:**
- Modify: `quantsys-v2/services/lhb_data_source.py`

- [ ] **Step 1: 实现 fetch_daily_lhb 方法**

替换占位符为完整实现：

```python
    def fetch_daily_lhb(self, date: str) -> pd.DataFrame:
        """
        从 akshare 获取某日全市场龙虎榜

        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）

        Returns:
            pd.DataFrame: 当日所有上榜股票

        Raises:
            Exception: akshare API 调用失败
        """
        import akshare as ak

        logger.info(f"Fetching daily LHB data from akshare for {date}")

        try:
            df = ak.stock_lhb_detail_daily_sina(date=date)
            
            logger.info(f"Fetched {len(df)} stocks from daily LHB for {date}")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch daily LHB data for {date}: {e}")
            raise
```

- [ ] **Step 2: 验证语法**

Run: `python -m py_compile quantsys-v2/services/lhb_data_source.py`
Expected: 无输出（编译成功）

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/services/lhb_data_source.py
git commit -m "feat(lhb): implement AkshareLhbSource.fetch_daily_lhb"
```

---


## Task 5: 实现服务层 - LhbService 基础结构

**Files:**
- Create: `quantsys-v2/services/lhb_service.py`

- [ ] **Step 1: 创建 LhbService 类和构造函数**

```python
"""
龙虎榜数据服务

提供龙虎榜数据查询、筛选、格式化等功能。
"""
from typing import List, Dict, Optional
import pandas as pd
import logging
from datetime import datetime, timedelta

from services.base_service import ServiceBase
from services.lhb_data_source import LhbDataSource, AkshareLhbSource

logger = logging.getLogger(__name__)


class LhbService(ServiceBase):
    """龙虎榜数据服务"""

    def __init__(self, data_source: Optional[LhbDataSource] = None):
        """
        初始化龙虎榜服务

        Args:
            data_source: 数据源实现，默认使用 AkshareLhbSource
        """
        super().__init__()
        self.data_source = data_source or AkshareLhbSource()

    def get_stock_lhb(self, symbol: str, days: int = 30) -> Dict:
        """占位符，下一个任务实现"""
        pass

    def get_daily_lhb(self, date: str) -> Dict:
        """占位符，后续任务实现"""
        pass

    def _format_date(self, date: str) -> str:
        """格式化日期：YYYYMMDD → YYYY-MM-DD"""
        return f"{date[:4]}-{date[4:6]}-{date[6:]}"
```

- [ ] **Step 2: 验证语法**

Run: `python -m py_compile quantsys-v2/services/lhb_service.py`
Expected: 无输出（编译成功）

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/services/lhb_service.py
git commit -m "feat(lhb): add LhbService base structure"
```

---


## Task 6: 实现 LhbService.get_stock_lhb - 个股查询

**Files:**
- Modify: `quantsys-v2/services/lhb_service.py`

- [ ] **Step 1: 实现 get_stock_lhb 方法**

替换占位符为完整实现：

```python
    def get_stock_lhb(self, symbol: str, days: int = 30) -> Dict:
        """
        获取个股龙虎榜记录

        Args:
            symbol: 股票代码（如 600737.SH 或 600737）
            days: 查询最近N天（用于过滤，默认 30）

        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "records": List[Dict]
            }
        """
        try:
            logger.info(f"Fetching LHB for {symbol}, days={days}")

            # 1. 调用数据源
            df = self.data_source.fetch_stock_lhb(symbol)

            if df.empty:
                return {
                    "success": False,
                    "error": "该股票近期无龙虎榜记录"
                }

            # 2. 数据转换和清洗
            records = self._transform_stock_records(df, days)

            if not records:
                return {
                    "success": False,
                    "error": f"最近{days}天无龙虎榜记录"
                }

            # 3. 返回结果
            return {
                "success": True,
                "symbol": symbol,
                "name": records[0].get("name", "") if records else "",
                "total_records": len(records),
                "records": records
            }

        except Exception as e:
            logger.error(f"Failed to get LHB for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
```

- [ ] **Step 2: 添加 _transform_stock_records 辅助方法**

```python
    def _transform_stock_records(self, df: pd.DataFrame, days: int) -> List[Dict]:
        """
        转换个股龙虎榜数据为标准格式

        Args:
            df: akshare 返回的 DataFrame
            days: 过滤最近N天

        Returns:
            List[Dict]: 标准化的龙虎榜记录列表
        """
        records = []
        
        # 过滤最近 N 天
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for _, row in df.iterrows():
            try:
                # 解析日期
                trade_date_str = str(row.get('上榜日', ''))
                if not trade_date_str:
                    continue
                
                trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
                if trade_date < cutoff_date:
                    continue
                
                # 构建记录
                record = {
                    "date": trade_date_str,
                    "name": str(row.get('股票简称', '')),
                    "reason": str(row.get('解读', '')),
                    "close_price": float(row.get('收盘价', 0)),
                    "change_pct": float(row.get('涨跌幅', 0)),
                    "net_buy": float(row.get('龙虎榜净买额', 0)),
                    "buy_amount": float(row.get('龙虎榜买入额', 0)),
                    "sell_amount": float(row.get('龙虎榜卖出额', 0)),
                    "turnover": float(row.get('龙虎榜成交额', 0))
                }
                
                records.append(record)
                
            except Exception as e:
                logger.warning(f"Failed to parse record: {e}")
                continue
        
        return records
```

- [ ] **Step 3: 验证语法**

Run: `python -m py_compile quantsys-v2/services/lhb_service.py`
Expected: 无输出（编译成功）

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/services/lhb_service.py
git commit -m "feat(lhb): implement LhbService.get_stock_lhb"
```

---


## Task 7: 实现 LhbService.get_daily_lhb - 日期汇总查询

**Files:**
- Modify: `quantsys-v2/services/lhb_service.py`

- [ ] **Step 1: 实现 get_daily_lhb 方法**

替换占位符为完整实现：

```python
    def get_daily_lhb(self, date: str) -> Dict:
        """
        获取某日全市场龙虎榜

        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）

        Returns:
            {
                "success": bool,
                "date": str,
                "total_stocks": int,
                "stocks": List[Dict]
            }
        """
        try:
            logger.info(f"Fetching daily LHB for {date}")

            # 1. 调用数据源
            df = self.data_source.fetch_daily_lhb(date)

            if df.empty:
                return {
                    "success": False,
                    "error": f"{date} 无龙虎榜数据"
                }

            # 2. 数据转换
            stocks = self._transform_daily_records(df)

            # 3. 返回结果
            return {
                "success": True,
                "date": self._format_date(date),
                "total_stocks": len(stocks),
                "stocks": stocks
            }

        except Exception as e:
            logger.error(f"Failed to get daily LHB for {date}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
```

- [ ] **Step 2: 添加 _transform_daily_records 辅助方法**

```python
    def _transform_daily_records(self, df: pd.DataFrame) -> List[Dict]:
        """
        转换日期汇总数据为标准格式

        Args:
            df: akshare 返回的 DataFrame

        Returns:
            List[Dict]: 标准化的股票列表
        """
        stocks = []
        
        for _, row in df.iterrows():
            try:
                stock = {
                    "symbol": str(row.get('代码', '')),
                    "name": str(row.get('名称', '')),
                    "reason": str(row.get('解读', '')),
                    "close_price": float(row.get('收盘价', 0)),
                    "change_pct": float(row.get('涨跌幅', 0)),
                    "net_buy": float(row.get('龙虎榜净买额', 0)),
                    "buy_amount": float(row.get('龙虎榜买入额', 0)),
                    "sell_amount": float(row.get('龙虎榜卖出额', 0)),
                    "turnover": float(row.get('龙虎榜成交额', 0))
                }
                
                stocks.append(stock)
                
            except Exception as e:
                logger.warning(f"Failed to parse daily record: {e}")
                continue
        
        return stocks
```

- [ ] **Step 3: 验证语法**

Run: `python -m py_compile quantsys-v2/services/lhb_service.py`
Expected: 无输出（编译成功）

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/services/lhb_service.py
git commit -m "feat(lhb): implement LhbService.get_daily_lhb"
```

---


## Task 8: 更新 API 路由 - 个股查询端点

**Files:**
- Modify: `quantsys-v2/api/routes/sentiment.py:77-90`

- [ ] **Step 1: 在文件顶部添加 LhbService 导入**

在 `sentiment.py` 的导入区域添加：

```python
from services.lhb_service import LhbService
```

在文件顶部初始化服务（与其他服务一起）：

```python
lhb_service = LhbService()
```

- [ ] **Step 2: 更新 get_stock_lhb 路由函数**

替换现有的 `get_stock_lhb` 函数（第77-90行）：

```python
@sentiment_bp.route('/api/stock/<symbol>/lhb', methods=['GET'])
@handle_api_error
def get_stock_lhb(symbol):
    """
    龙虎榜 - 个股查询
    
    Query Params:
        days: 查询最近N天（默认 30）
    
    Example:
        GET /api/stock/600737/lhb?days=30
    """
    days = request.args.get('days', 30, type=int)
    result = lhb_service.get_stock_lhb(symbol, days)
    return api_response(result)
```

- [ ] **Step 3: 移除旧的 v1 依赖代码**

确保删除了以下代码：
- `sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))`
- `from quantsys.cli.sentiment_query import get_lhb`

- [ ] **Step 4: 验证语法**

Run: `python -m py_compile quantsys-v2/api/routes/sentiment.py`
Expected: 无输出（编译成功）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/api/routes/sentiment.py
git commit -m "feat(lhb): update stock lhb route to use LhbService"
```

---


## Task 9: 添加 API 路由 - 日期汇总端点

**Files:**
- Modify: `quantsys-v2/api/routes/sentiment.py`

- [ ] **Step 1: 在 sentiment.py 末尾添加新路由**

在 `get_stock_lhb` 函数后添加：

```python
@sentiment_bp.route('/api/lhb/daily', methods=['GET'])
@handle_api_error
def get_daily_lhb():
    """
    龙虎榜 - 日期汇总
    
    Query Params:
        date: 日期（格式 YYYYMMDD，必填）
    
    Example:
        GET /api/lhb/daily?date=20260531
    """
    date = request.args.get('date')
    if not date:
        return jsonify({
            'success': False,
            'error': '缺少必填参数: date（格式 YYYYMMDD）'
        }), 400
    
    result = lhb_service.get_daily_lhb(date)
    return api_response(result)
```

- [ ] **Step 2: 验证语法**

Run: `python -m py_compile quantsys-v2/api/routes/sentiment.py`
Expected: 无输出（编译成功）

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/api/routes/sentiment.py
git commit -m "feat(lhb): add daily lhb route endpoint"
```

---


## Task 10: 手动测试 - 启动服务并验证端点

**Files:**
- Test: `quantsys-v2/api/server.py`

- [ ] **Step 1: 启动 quantsys-v2 服务**

Run: `cd quantsys-v2 && python api/server.py`
Expected: 服务启动在 http://127.0.0.1:5001

- [ ] **Step 2: 测试个股查询端点**

Run: `curl "http://127.0.0.1:5001/api/stock/600737/lhb?days=30"`
Expected: 返回 JSON，包含 `{"success": true, "symbol": "600737", "records": [...]}`

- [ ] **Step 3: 测试日期汇总端点**

Run: `curl "http://127.0.0.1:5001/api/lhb/daily?date=20260531"`
Expected: 返回 JSON，包含 `{"success": true, "date": "2026-05-31", "stocks": [...]}`

- [ ] **Step 4: 测试错误处理 - 缺少日期参数**

Run: `curl "http://127.0.0.1:5001/api/lhb/daily"`
Expected: 返回 400 错误，`{"success": false, "error": "缺少必填参数: date（格式 YYYYMMDD）"}`

- [ ] **Step 5: 测试错误处理 - 无效股票代码**

Run: `curl "http://127.0.0.1:5001/api/stock/999999/lhb?days=30"`
Expected: 返回 `{"success": false, "error": "股票代码 999999 不存在"}`

- [ ] **Step 6: 停止服务**

按 Ctrl+C 停止服务

---


## Task 11: 编写单元测试 - LhbService

**Files:**
- Create: `quantsys-v2/tests/services/test_lhb_service.py`

- [ ] **Step 1: 创建测试文件并写入测试用例**

```python
"""
LhbService 单元测试
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from services.lhb_service import LhbService


class TestLhbService:
    """LhbService 测试类"""

    def test_get_stock_lhb_success(self):
        """测试个股查询成功"""
        # Mock 数据源
        mock_data_source = Mock()
        mock_df = pd.DataFrame({
            '上榜日': ['2026-05-31', '2026-05-30'],
            '股票简称': ['中粮糖业', '中粮糖业'],
            '解读': ['日涨幅偏离值达7%', '日振幅值达15%'],
            '收盘价': [10.50, 10.20],
            '涨跌幅': [8.5, 5.2],
            '龙虎榜净买额': [5000.0, 3000.0],
            '龙虎榜买入额': [8000.0, 5000.0],
            '龙虎榜卖出额': [3000.0, 2000.0],
            '龙虎榜成交额': [11000.0, 7000.0]
        })
        mock_data_source.fetch_stock_lhb.return_value = mock_df

        # 创建服务
        service = LhbService(data_source=mock_data_source)

        # 调用方法
        result = service.get_stock_lhb('600737', days=30)

        # 验证结果
        assert result['success'] is True
        assert result['symbol'] == '600737'
        assert result['name'] == '中粮糖业'
        assert result['total_records'] == 2
        assert len(result['records']) == 2
        assert result['records'][0]['date'] == '2026-05-31'
        assert result['records'][0]['close_price'] == 10.50

    def test_get_stock_lhb_no_data(self):
        """测试个股无数据"""
        # Mock 数据源返回空 DataFrame
        mock_data_source = Mock()
        mock_data_source.fetch_stock_lhb.return_value = pd.DataFrame()

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is False
        assert '无龙虎榜记录' in result['error']

    def test_get_stock_lhb_exception(self):
        """测试个股查询异常"""
        # Mock 数据源抛出异常
        mock_data_source = Mock()
        mock_data_source.fetch_stock_lhb.side_effect = Exception('网络错误')

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is False
        assert '网络错误' in result['error']

    def test_get_daily_lhb_success(self):
        """测试日期汇总成功"""
        # Mock 数据源
        mock_data_source = Mock()
        mock_df = pd.DataFrame({
            '代码': ['600737', '600519'],
            '名称': ['中粮糖业', '贵州茅台'],
            '解读': ['日涨幅偏离值达7%', '日振幅值达15%'],
            '收盘价': [10.50, 1800.0],
            '涨跌幅': [8.5, 3.2],
            '龙虎榜净买额': [5000.0, 20000.0],
            '龙虎榜买入额': [8000.0, 30000.0],
            '龙虎榜卖出额': [3000.0, 10000.0],
            '龙虎榜成交额': [11000.0, 40000.0]
        })
        mock_data_source.fetch_daily_lhb.return_value = mock_df

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is True
        assert result['date'] == '2026-05-31'
        assert result['total_stocks'] == 2
        assert len(result['stocks']) == 2
        assert result['stocks'][0]['symbol'] == '600737'

    def test_get_daily_lhb_no_data(self):
        """测试日期无数据"""
        mock_data_source = Mock()
        mock_data_source.fetch_daily_lhb.return_value = pd.DataFrame()

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is False
        assert '无龙虎榜数据' in result['error']

    def test_format_date(self):
        """测试日期格式化"""
        service = LhbService()
        assert service._format_date('20260531') == '2026-05-31'
        assert service._format_date('20261225') == '2026-12-25'
```

- [ ] **Step 2: 运行测试**

Run: `cd quantsys-v2 && pytest tests/services/test_lhb_service.py -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/tests/services/test_lhb_service.py
git commit -m "test(lhb): add LhbService unit tests"
```

---


## Task 12: 编写集成测试 - API 路由

**Files:**
- Create: `quantsys-v2/tests/api/test_lhb_routes.py`

- [ ] **Step 1: 创建测试文件并写入测试用例**

```python
"""
LHB API 路由集成测试
"""
import pytest
from unittest.mock import patch, Mock


def test_api_stock_lhb_success(client):
    """测试个股查询端点成功"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': True,
            'symbol': '600737',
            'name': '中粮糖业',
            'total_records': 2,
            'records': [
                {
                    'date': '2026-05-31',
                    'reason': '日涨幅偏离值达7%',
                    'close_price': 10.50,
                    'change_pct': 8.5,
                    'net_buy': 5000.0
                }
            ]
        }

        response = client.get('/api/stock/600737/lhb?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['symbol'] == '600737'
        assert data['name'] == '中粮糖业'


def test_api_stock_lhb_no_data(client):
    """测试个股无数据"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': False,
            'error': '该股票近期无龙虎榜记录'
        }

        response = client.get('/api/stock/999999/lhb?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert '无龙虎榜记录' in data['error']


def test_api_daily_lhb_success(client):
    """测试日期汇总端点成功"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_daily_lhb.return_value = {
            'success': True,
            'date': '2026-05-31',
            'total_stocks': 2,
            'stocks': [
                {
                    'symbol': '600737',
                    'name': '中粮糖业',
                    'reason': '日涨幅偏离值达7%',
                    'close_price': 10.50,
                    'change_pct': 8.5
                }
            ]
        }

        response = client.get('/api/lhb/daily?date=20260531')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['date'] == '2026-05-31'
        assert data['total_stocks'] == 2


def test_api_daily_lhb_missing_date(client):
    """测试缺少日期参数"""
    response = client.get('/api/lhb/daily')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert '缺少必填参数' in data['error']
```

- [ ] **Step 2: 运行测试**

Run: `cd quantsys-v2 && pytest tests/api/test_lhb_routes.py -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add quantsys-v2/tests/api/test_lhb_routes.py
git commit -m "test(lhb): add API route integration tests"
```

---

## Task 13: 端到端测试 - TypeScript Agent

**Files:**
- Test: TypeScript Agent 工具调用

- [ ] **Step 1: 确保 quantsys-v2 服务运行**

Run: `cd quantsys-v2 && python api/server.py`
Expected: 服务启动在 http://127.0.0.1:5001

- [ ] **Step 2: 启动 TypeScript Agent**

Run: `npm run dev`
Expected: Agent TUI 启动

- [ ] **Step 3: 测试个股查询**

在 Agent 中输入:
```
quant_cli({ command: "sentiment.lhb", params: { symbol: "600737" } })
```

Expected: 返回龙虎榜数据，包含上榜日期、原因、价格、涨跌幅等

- [ ] **Step 4: 测试日期汇总**

在 Agent 中输入:
```
quant_cli({ command: "sentiment.lhb", params: { date: "20260531" } })
```

Expected: 返回当日所有上榜股票列表

- [ ] **Step 5: 验证完成**

确认两种查询模式都正常工作，数据格式正确

---

## 验证清单

完成所有任务后，验证以下内容：

- [ ] lxml 依赖已添加到 requirements.txt 并安装成功
- [ ] LhbDataSource 抽象类和 AkshareLhbSource 实现完成
- [ ] LhbService 两个查询方法（个股、日期汇总）实现完成
- [ ] API 路由更新完成，移除 v1 依赖
- [ ] 单元测试全部通过（LhbService）
- [ ] 集成测试全部通过（API 路由）
- [ ] 手动测试验证端点正常工作
- [ ] TypeScript Agent 可以正常调用 sentiment.lhb 命令
- [ ] 所有代码已提交到 git

---

## 执行选项

**计划已完成并保存到 `docs/superpowers/plans/2026-06-01-lhb-v2-implementation.md`**

两种执行方式：

**1. Subagent-Driven（推荐）** - 每个任务派发一个新的 subagent，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans skill 批量执行，设置检查点进行审查

你希望使用哪种方式？
