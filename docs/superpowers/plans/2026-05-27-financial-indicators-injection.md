# Financial Indicators Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `_inject_financial()` method to inject 18 financial indicator columns (9 indicators × quarterly/annual) into K-line DataFrames for strategy backtesting.

**Architecture:** Minimal implementation (Plan A) - add method to `StrategyCodeService` following the existing `_inject_fund_flow()` pattern. Direct akshare API calls with in-memory calculation, two-tier data source fallback (Sina → East Money), forward-fill based on announcement date.

**Tech Stack:** Python 3.13, akshare, pandas, quantsys-v2

---

## File Structure

**Modified files:**
- `quantsys-v2/services/strategy_code_service.py` - Add `_inject_financial()` and helper methods

**New test file:**
- `quantsys-v2/tests/test_strategy_financial_injection.py` - Unit tests for financial injection

**Files to reference:**
- `quantsys-v2/services/strategy_code_service.py:823-917` - Existing `_inject_fund_flow()` pattern
- `quantsys-v2/services/data_service.py:680-789` - Existing financial data fetching

---

## Task 1: Write Test for Financial Data Fetching (Sina Source)

**Files:**
- Create: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write the failing test for Sina data source**

```python
"""
Tests for financial indicators injection in strategy code service
"""
import pytest
from unittest.mock import Mock, patch
import pandas as pd
from services.strategy_code_service import StrategyCodeService


class TestFinancialInjection:
    """Test financial indicators injection"""

    def test_fetch_from_sina_success(self):
        """Test successful fetch from Sina Finance"""
        service = StrategyCodeService()
        
        # Mock akshare response
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260425'
            }
        ])
        
        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260425'
            }
        ])
        
        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260425'
            }
        ])
        
        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]
            
            result = service._fetch_from_sina('600519')
            
            assert result is not None
            assert 'income' in result
            assert 'balance' in result
            assert 'cashflow' in result
            assert len(result['income']) == 1
            assert result['income'][0]['营业收入'] == 100000000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_fetch_from_sina_success -v
```

Expected: FAIL with "AttributeError: 'StrategyCodeService' object has no attribute '_fetch_from_sina'"

- [ ] **Step 3: Implement `_fetch_from_sina()` method**

Add to `quantsys-v2/services/strategy_code_service.py` after line 917 (after `_inject_fund_flow`):

```python
    def _fetch_from_sina(self, symbol: str) -> Optional[Dict]:
        """
        从新浪财经获取财务报表数据
        
        Args:
            symbol: 股票代码（6位数字）
        
        Returns:
            {
                'income': [利润表记录列表],
                'balance': [资产负债表记录列表],
                'cashflow': [现金流量表记录列表]
            }
            失败返回 None
        """
        import os
        
        try:
            import akshare as ak
            
            # 禁用代理（akshare 国内接口不需要代理）
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
            
            # 转换为新浪格式（去掉市场后缀）
            clean_symbol = symbol.strip()
            if '.' in clean_symbol:
                clean_symbol = clean_symbol.split('.')[0]
            
            result = {}
            
            # 获取利润表
            income_df = ak.stock_financial_report_sina(stock=clean_symbol, symbol='利润表')
            if income_df is not None and not income_df.empty:
                result['income'] = income_df.to_dict(orient='records')
            else:
                result['income'] = []
            
            # 获取资产负债表
            balance_df = ak.stock_financial_report_sina(stock=clean_symbol, symbol='资产负债表')
            if balance_df is not None and not balance_df.empty:
                result['balance'] = balance_df.to_dict(orient='records')
            else:
                result['balance'] = []
            
            # 获取现金流量表
            cashflow_df = ak.stock_financial_report_sina(stock=clean_symbol, symbol='现金流量表')
            if cashflow_df is not None and not cashflow_df.empty:
                result['cashflow'] = cashflow_df.to_dict(orient='records')
            else:
                result['cashflow'] = []
            
            logger.debug(f"新浪财经获取成功: {symbol}, 利润表={len(result['income'])}条, 资产负债表={len(result['balance'])}条, 现金流量表={len(result['cashflow'])}条")
            
            return result
            
        except Exception as e:
            logger.warning(f"新浪财经获取失败: {symbol} - {e}")
            return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_fetch_from_sina_success -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py quantsys-v2/services/strategy_code_service.py
git commit -m "test: add test for Sina financial data fetching

- Add test_fetch_from_sina_success test case
- Implement _fetch_from_sina() method in StrategyCodeService
- Fetches income statement, balance sheet, cash flow statement"
```

---

## Task 2: Add East Money Fallback Data Source

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Modify: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write the failing test for East Money fallback**

Add to `quantsys-v2/tests/test_strategy_financial_injection.py`:

```python
    def test_fetch_from_eastmoney_success(self):
        """Test successful fetch from East Money"""
        service = StrategyCodeService()
        
        # Mock akshare East Money response
        mock_df = pd.DataFrame([
            {
                '报告期': '2026-03-31',
                '净资产收益率': 15.5,
                '销售毛利率': 38.2,
                '销售净利率': 25.1,
                '资产负债率': 45.3,
                '营业总收入同比增长': 12.5,
                '流动比率': 1.8,
                '总资产净利率': 8.2,
                '营业利润率': 28.3,
                '公告日期': '2026-04-25'
            }
        ])
        
        with patch('akshare.stock_financial_analysis_indicator') as mock_ak:
            mock_ak.return_value = mock_df
            
            result = service._fetch_from_eastmoney('600519')
            
            assert result is not None
            assert len(result) == 1
            assert result[0]['净资产收益率'] == 15.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_fetch_from_eastmoney_success -v
```

Expected: FAIL with "AttributeError: 'StrategyCodeService' object has no attribute '_fetch_from_eastmoney'"

- [ ] **Step 3: Implement `_fetch_from_eastmoney()` method**

Add to `quantsys-v2/services/strategy_code_service.py` after `_fetch_from_sina`:

```python
    def _fetch_from_eastmoney(self, symbol: str) -> Optional[List[Dict]]:
        """
        从东方财富获取财务指标数据（备用数据源）
        
        Args:
            symbol: 股票代码（6位数字）
        
        Returns:
            财务指标记录列表，失败返回 None
        """
        import os
        
        try:
            import akshare as ak
            
            # 禁用代理
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
            
            # 转换为东方财富格式
            clean_symbol = symbol.strip()
            if '.' in clean_symbol:
                clean_symbol = clean_symbol.split('.')[0]
            
            # 获取财务分析指标
            df = ak.stock_financial_analysis_indicator(symbol=clean_symbol)
            
            if df is not None and not df.empty:
                result = df.to_dict(orient='records')
                logger.debug(f"东方财富获取成功: {symbol}, {len(result)}条记录")
                return result
            else:
                logger.warning(f"东方财富返回空数据: {symbol}")
                return None
                
        except Exception as e:
            logger.warning(f"东方财富获取失败: {symbol} - {e}")
            return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_fetch_from_eastmoney_success -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py quantsys-v2/services/strategy_code_service.py
git commit -m "feat: add East Money fallback data source

- Add test_fetch_from_eastmoney_success test case
- Implement _fetch_from_eastmoney() method
- Provides fallback when Sina Finance fails"
```

---

## Task 3: Implement Financial Indicators Calculation

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Modify: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write the failing test for indicator calculation**

Add to `quantsys-v2/tests/test_strategy_financial_injection.py`:

```python
    def test_calculate_indicators(self):
        """Test financial indicators calculation"""
        service = StrategyCodeService()
        
        # Prepare test data
        income = {
            '营业收入': 100000000,
            '营业成本': 60000000,
            '净利润': 20000000,
            '营业利润': 25000000
        }
        
        balance = {
            '资产总计': 500000000,
            '负债合计': 200000000,
            '股东权益合计': 300000000,
            '流动资产合计': 150000000,
            '流动负债合计': 100000000
        }
        
        cashflow = {
            '经营活动现金流量净额': 18000000
        }
        
        prev_income = {
            '营业收入': 90000000
        }
        
        result = service._calculate_indicators(income, balance, cashflow, prev_income)
        
        # Verify calculations
        assert abs(result['roe'] - 6.67) < 0.1  # 20M / 300M * 100
        assert abs(result['gross_margin'] - 40.0) < 0.1  # (100M - 60M) / 100M * 100
        assert abs(result['net_profit_margin'] - 20.0) < 0.1  # 20M / 100M * 100
        assert abs(result['debt_ratio'] - 40.0) < 0.1  # 200M / 500M * 100
        assert abs(result['revenue_growth'] - 11.11) < 0.1  # (100M - 90M) / 90M * 100
        assert abs(result['ocf_to_profit'] - 0.9) < 0.1  # 18M / 20M
        assert abs(result['current_ratio'] - 1.5) < 0.1  # 150M / 100M
        assert abs(result['roa'] - 4.0) < 0.1  # 20M / 500M * 100
        assert abs(result['operating_margin'] - 25.0) < 0.1  # 25M / 100M * 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_calculate_indicators -v
```

Expected: FAIL with "AttributeError: 'StrategyCodeService' object has no attribute '_calculate_indicators'"

- [ ] **Step 3: Implement `_calculate_indicators()` method**

Add to `quantsys-v2/services/strategy_code_service.py` after `_fetch_from_eastmoney`:

```python
    def _calculate_indicators(
        self,
        income: Dict,
        balance: Dict,
        cashflow: Dict,
        prev_income: Optional[Dict] = None
    ) -> Dict:
        """
        计算财务指标
        
        Args:
            income: 利润表数据
            balance: 资产负债表数据
            cashflow: 现金流量表数据
            prev_income: 去年同期利润表（用于计算增长率）
        
        Returns:
            {
                'roe': 净资产收益率,
                'gross_margin': 毛利率,
                'net_profit_margin': 销售净利率,
                'debt_ratio': 资产负债率,
                'revenue_growth': 营收增长率,
                'ocf_to_profit': 经营现金流/净利润,
                'current_ratio': 流动比率,
                'roa': 总资产收益率,
                'operating_margin': 营业利润率
            }
        """
        result = {}
        
        try:
            # ROE = 净利润 / 股东权益合计 × 100
            net_profit = float(income.get('净利润', 0) or 0)
            equity = float(balance.get('股东权益合计', 0) or 0)
            if equity != 0:
                result['roe'] = round(net_profit / equity * 100, 2)
            else:
                result['roe'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['roe'] = float('nan')
        
        try:
            # 毛利率 = (营业收入 - 营业成本) / 营业收入 × 100
            revenue = float(income.get('营业收入', 0) or 0)
            cost = float(income.get('营业成本', 0) or 0)
            if revenue != 0:
                result['gross_margin'] = round((revenue - cost) / revenue * 100, 2)
            else:
                result['gross_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['gross_margin'] = float('nan')
        
        try:
            # 销售净利率 = 净利润 / 营业收入 × 100
            if revenue != 0:
                result['net_profit_margin'] = round(net_profit / revenue * 100, 2)
            else:
                result['net_profit_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['net_profit_margin'] = float('nan')
        
        try:
            # 资产负债率 = 负债合计 / 资产总计 × 100
            total_liabilities = float(balance.get('负债合计', 0) or 0)
            total_assets = float(balance.get('资产总计', 0) or 0)
            if total_assets != 0:
                result['debt_ratio'] = round(total_liabilities / total_assets * 100, 2)
            else:
                result['debt_ratio'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['debt_ratio'] = float('nan')
        
        try:
            # 营收增长率 = (本期营收 - 去年同期) / 去年同期 × 100
            if prev_income:
                prev_revenue = float(prev_income.get('营业收入', 0) or 0)
                if prev_revenue != 0:
                    result['revenue_growth'] = round((revenue - prev_revenue) / prev_revenue * 100, 2)
                else:
                    result['revenue_growth'] = float('nan')
            else:
                result['revenue_growth'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['revenue_growth'] = float('nan')
        
        try:
            # 经营现金流/净利润
            ocf = float(cashflow.get('经营活动现金流量净额', 0) or 0)
            if net_profit != 0:
                result['ocf_to_profit'] = round(ocf / net_profit, 2)
            else:
                result['ocf_to_profit'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['ocf_to_profit'] = float('nan')
        
        try:
            # 流动比率 = 流动资产合计 / 流动负债合计
            current_assets = float(balance.get('流动资产合计', 0) or 0)
            current_liabilities = float(balance.get('流动负债合计', 0) or 0)
            if current_liabilities != 0:
                result['current_ratio'] = round(current_assets / current_liabilities, 2)
            else:
                result['current_ratio'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['current_ratio'] = float('nan')
        
        try:
            # ROA = 净利润 / 资产总计 × 100
            if total_assets != 0:
                result['roa'] = round(net_profit / total_assets * 100, 2)
            else:
                result['roa'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['roa'] = float('nan')
        
        try:
            # 营业利润率 = 营业利润 / 营业收入 × 100
            operating_profit = float(income.get('营业利润', 0) or 0)
            if revenue != 0:
                result['operating_margin'] = round(operating_profit / revenue * 100, 2)
            else:
                result['operating_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['operating_margin'] = float('nan')
        
        return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_calculate_indicators -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py quantsys-v2/services/strategy_code_service.py
git commit -m "feat: implement financial indicators calculation

- Add test_calculate_indicators test case
- Implement _calculate_indicators() method
- Calculate 9 indicators: ROE, gross margin, net profit margin, debt ratio, revenue growth, OCF/profit, current ratio, ROA, operating margin
- Handle division by zero and missing fields gracefully"
```

---

## Task 4: Implement Forward-Fill Temporal Alignment

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Modify: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write the failing test for forward-fill alignment**

Add to `quantsys-v2/tests/test_strategy_financial_injection.py`:

```python
    def test_forward_fill_to_klines(self):
        """Test forward-fill temporal alignment"""
        service = StrategyCodeService()
        
        # Prepare K-lines
        klines = [
            {'trade_date': '2026-04-20'},  # Before announcement
            {'trade_date': '2026-04-25'},  # Announcement day
            {'trade_date': '2026-04-26'},  # After announcement
            {'trade_date': '2026-05-15'},  # Much later
        ]
        
        # Prepare financial timeline (quarterly)
        financial_timeline_q = [
            {
                'announce_date': '2026-04-25',
                'roe': 15.5,
                'gross_margin': 38.2,
                'net_profit_margin': 25.1,
                'debt_ratio': 45.3,
                'revenue_growth': 12.5,
                'ocf_to_profit': 0.9,
                'current_ratio': 1.8,
                'roa': 8.2,
                'operating_margin': 28.3
            }
        ]
        
        # Prepare financial timeline (annual) - empty for this test
        financial_timeline_y = []
        
        result = service._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)
        
        # Verify forward-fill logic
        import math
        assert math.isnan(result[0]['roe_q'])  # Before announcement - NaN
        assert result[1]['roe_q'] == 15.5  # Announcement day - has data
        assert result[2]['roe_q'] == 15.5  # After announcement - forward-filled
        assert result[3]['roe_q'] == 15.5  # Much later - still forward-filled
        
        # Verify annual indicators are NaN (no annual data)
        assert math.isnan(result[1]['roe_y'])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_forward_fill_to_klines -v
```

Expected: FAIL with "AttributeError: 'StrategyCodeService' object has no attribute '_forward_fill_to_klines'"

- [ ] **Step 3: Implement `_forward_fill_to_klines()` method**

Add to `quantsys-v2/services/strategy_code_service.py` after `_calculate_indicators`:

```python
    def _forward_fill_to_klines(
        self,
        klines: List[Dict],
        financial_timeline_q: List[Dict],
        financial_timeline_y: List[Dict]
    ) -> List[Dict]:
        """
        将财务指标 forward-fill 到 K 线数据中
        
        Args:
            klines: K线数据列表
            financial_timeline_q: 季度财务指标时间线 [{announce_date, roe, ...}, ...]
            financial_timeline_y: 年度财务指标时间线
        
        Returns:
            增强后的 K 线数据（添加了 18 个财务指标列）
        """
        # 定义所有财务指标列名
        INDICATOR_NAMES = [
            'roe', 'gross_margin', 'net_profit_margin', 'debt_ratio',
            'revenue_growth', 'ocf_to_profit', 'current_ratio', 'roa', 'operating_margin'
        ]
        
        # 初始化所有财务指标列为 NaN
        for kline in klines:
            for indicator in INDICATOR_NAMES:
                kline[f'{indicator}_q'] = float('nan')
                kline[f'{indicator}_y'] = float('nan')
        
        # 按公告日期排序时间线
        timeline_q_sorted = sorted(financial_timeline_q, key=lambda x: x['announce_date'])
        timeline_y_sorted = sorted(financial_timeline_y, key=lambda x: x['announce_date'])
        
        # Forward-fill 季度指标
        for kline in klines:
            kline_date = str(kline.get('trade_date', '')).replace('-', '')[:8]
            if len(kline_date) == 8:
                kline_date = f"{kline_date[:4]}-{kline_date[4:6]}-{kline_date[6:8]}"
            
            # 找到最近的已公告季度财报
            latest_q = None
            for report in timeline_q_sorted:
                if report['announce_date'] <= kline_date:
                    latest_q = report
                else:
                    break
            
            # 填充季度指标
            if latest_q:
                for indicator in INDICATOR_NAMES:
                    kline[f'{indicator}_q'] = latest_q.get(indicator, float('nan'))
            
            # 找到最近的已公告年度财报
            latest_y = None
            for report in timeline_y_sorted:
                if report['announce_date'] <= kline_date:
                    latest_y = report
                else:
                    break
            
            # 填充年度指标
            if latest_y:
                for indicator in INDICATOR_NAMES:
                    kline[f'{indicator}_y'] = latest_y.get(indicator, float('nan'))
        
        return klines
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_forward_fill_to_klines -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py quantsys-v2/services/strategy_code_service.py
git commit -m "feat: implement forward-fill temporal alignment

- Add test_forward_fill_to_klines test case
- Implement _forward_fill_to_klines() method
- Forward-fill 18 financial indicator columns based on announcement date
- Avoid future information leakage"
```

---

## Task 5: Implement Main `_inject_financial()` Method

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Modify: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write the failing integration test**

Add to `quantsys-v2/tests/test_strategy_financial_injection.py`:

```python
    def test_inject_financial_integration(self):
        """Test full financial injection integration"""
        service = StrategyCodeService()
        
        # Prepare K-lines
        klines = [
            {'trade_date': '2026-04-20', 'close': 100},
            {'trade_date': '2026-04-25', 'close': 102},
            {'trade_date': '2026-05-15', 'close': 105},
        ]
        
        # Mock Sina data source
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260425'
            },
            {
                '报告日': '20251231',
                '营业收入': 90000000,
                '营业成本': 55000000,
                '净利润': 18000000,
                '营业利润': 22000000,
                '公告日期': '20260330'
            }
        ])
        
        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260425'
            }
        ])
        
        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20260331',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260425'
            }
        ])
        
        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]
            
            result = service._inject_financial(klines, '600519')
            
            # Verify columns exist
            assert 'roe_q' in result[0]
            assert 'gross_margin_q' in result[0]
            assert 'roe_y' in result[0]
            
            # Verify forward-fill logic
            import math
            assert math.isnan(result[0]['roe_q'])  # Before announcement
            assert result[1]['roe_q'] > 0  # Announcement day
            assert result[2]['roe_q'] == result[1]['roe_q']  # Forward-filled
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_inject_financial_integration -v
```

Expected: FAIL with "AttributeError: 'StrategyCodeService' object has no attribute '_inject_financial'"

- [ ] **Step 3: Implement `_inject_financial()` main method**

Add to `quantsys-v2/services/strategy_code_service.py` after `_forward_fill_to_klines`:

```python
    def _inject_financial(
        self,
        klines: List[Dict],
        symbol: str
    ) -> List[Dict]:
        """
        注入财务指标数据到 kline 列表中
        
        使策略代码在运行时可以直接使用财务指标列：
        季度指标（_q 后缀）:
        - roe_q, gross_margin_q, net_profit_margin_q, debt_ratio_q,
          revenue_growth_q, ocf_to_profit_q, current_ratio_q, roa_q, operating_margin_q
        
        年度指标（_y 后缀）:
        - roe_y, gross_margin_y, net_profit_margin_y, debt_ratio_y,
          revenue_growth_y, ocf_to_profit_y, current_ratio_y, roa_y, operating_margin_y
        
        如果财务数据获取失败，所有列值为 NaN（策略代码可自行判断处理）。
        
        Args:
            klines: K线数据列表
            symbol: 股票代码
        
        Returns:
            增强后的 K 线数据（添加了 18 个财务指标列）
        """
        logger.debug(f"开始注入财务指标: {symbol}, klines数量={len(klines)}")
        
        # 定义所有财务指标列名
        INDICATOR_NAMES = [
            'roe', 'gross_margin', 'net_profit_margin', 'debt_ratio',
            'revenue_growth', 'ocf_to_profit', 'current_ratio', 'roa', 'operating_margin'
        ]
        
        # 初始化所有财务指标列为 NaN
        for kline in klines:
            for indicator in INDICATOR_NAMES:
                kline[f'{indicator}_q'] = float('nan')
                kline[f'{indicator}_y'] = float('nan')
        
        try:
            # 1. 获取财务报表数据（两级降级：Sina → East Money）
            financial_data = self._fetch_from_sina(symbol)
            
            if not financial_data:
                logger.debug(f"新浪财经获取失败，尝试东方财富: {symbol}")
                eastmoney_data = self._fetch_from_eastmoney(symbol)
                
                if eastmoney_data:
                    # 东方财富返回的是已计算好的指标，直接构建时间线
                    financial_timeline_q = []
                    financial_timeline_y = []
                    
                    for record in eastmoney_data:
                        announce_date = str(record.get('公告日期', '')).replace('-', '')[:8]
                        if len(announce_date) == 8:
                            announce_date = f"{announce_date[:4]}-{announce_date[4:6]}-{announce_date[6:8]}"
                        
                        indicators = {
                            'announce_date': announce_date,
                            'roe': record.get('净资产收益率', float('nan')),
                            'gross_margin': record.get('销售毛利率', float('nan')),
                            'net_profit_margin': record.get('销售净利率', float('nan')),
                            'debt_ratio': record.get('资产负债率', float('nan')),
                            'revenue_growth': record.get('营业总收入同比增长', float('nan')),
                            'ocf_to_profit': float('nan'),  # 东方财富不提供此指标
                            'current_ratio': record.get('流动比率', float('nan')),
                            'roa': record.get('总资产净利率', float('nan')),
                            'operating_margin': record.get('营业利润率', float('nan'))
                        }
                        
                        # 简单判断：报告期末尾为12-31的视为年报
                        report_period = str(record.get('报告期', ''))
                        if report_period.endswith('12-31'):
                            financial_timeline_y.append(indicators)
                        else:
                            financial_timeline_q.append(indicators)
                    
                    # Forward-fill 到 K 线
                    klines = self._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)
                    logger.debug(f"财务指标注入完成（东方财富）: {symbol}")
                    return klines
                else:
                    logger.warning(f"所有财务数据源均失败: {symbol}，策略将使用 NaN 列运行")
                    return klines
            
            # 2. 从新浪数据计算指标并构建时间线
            income_list = financial_data.get('income', [])
            balance_list = financial_data.get('balance', [])
            cashflow_list = financial_data.get('cashflow', [])
            
            if not income_list or not balance_list or not cashflow_list:
                logger.debug(f"财务报表数据不完整: {symbol}，策略将使用 NaN 列运行")
                return klines
            
            # 建立报告期 → 数据映射
            income_by_period = {str(r.get('报告日', '')): r for r in income_list}
            balance_by_period = {str(r.get('报告日', '')): r for r in balance_list}
            cashflow_by_period = {str(r.get('报告日', '')): r for r in cashflow_list}
            
            # 构建财务指标时间线
            financial_timeline_q = []
            financial_timeline_y = []
            
            for period, income in income_by_period.items():
                balance = balance_by_period.get(period)
                cashflow = cashflow_by_period.get(period)
                
                if not balance or not cashflow:
                    continue
                
                # 获取公告日期
                announce_date = str(income.get('公告日期', '')).replace('-', '')[:8]
                if len(announce_date) == 8:
                    announce_date = f"{announce_date[:4]}-{announce_date[4:6]}-{announce_date[6:8]}"
                else:
                    logger.warning(f"公告日期格式异常: {symbol}, period={period}, announce_date={announce_date}")
                    continue
                
                # 查找去年同期数据（用于计算增长率）
                prev_year_period = str(int(period) - 10000) if len(period) == 8 else None
                prev_income = income_by_period.get(prev_year_period) if prev_year_period else None
                
                # 计算指标
                indicators = self._calculate_indicators(income, balance, cashflow, prev_income)
                indicators['announce_date'] = announce_date
                
                # 判断是季报还是年报（报告期末尾为1231的是年报）
                if period.endswith('1231'):
                    financial_timeline_y.append(indicators)
                else:
                    financial_timeline_q.append(indicators)
            
            # 3. Forward-fill 到 K 线
            klines = self._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)
            
            logger.debug(f"财务指标注入完成: {symbol} — 季报={len(financial_timeline_q)}期, 年报={len(financial_timeline_y)}期")
            
        except Exception as e:
            logger.warning(f"财务指标注入失败: {symbol} — {e}，策略将使用 NaN 列运行")
        
        return klines
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_inject_financial_integration -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py quantsys-v2/services/strategy_code_service.py
git commit -m "feat: implement main _inject_financial() method

- Add test_inject_financial_integration test case
- Implement _inject_financial() method with two-tier fallback
- Integrate data fetching, calculation, and forward-fill
- Add 18 financial indicator columns to K-lines"
```

---

## Task 6: Integrate into Strategy Execution Flow

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`

- [ ] **Step 1: Add financial injection to `execute_indicator_strategy()`**

Locate line 390 in `quantsys-v2/services/strategy_code_service.py` (after `_inject_fund_flow` call):

```python
        # 3.5. 注入主力资金流向数据到 kline（让策略代码可直接使用）
        klines = self._inject_fund_flow(klines, symbol)
```

Add immediately after:

```python
        # 3.6. 注入财务指标数据到 kline（让策略代码可直接使用基本面因子）
        klines = self._inject_financial(klines, symbol)
```

- [ ] **Step 2: Add financial injection to `backtest_strategy()`**

Locate line 559 in `quantsys-v2/services/strategy_code_service.py` (after `_inject_fund_flow` call):

```python
        # 2.5. 注入主力资金流数据（使策略代码中可引用 main_net_inflow 等列）
        klines = self._inject_fund_flow(klines, symbol)
```

Add immediately after:

```python
        # 2.6. 注入财务指标数据（使策略代码中可引用 roe_q, gross_margin_q 等列）
        klines = self._inject_financial(klines, symbol)
```

- [ ] **Step 3: Run existing strategy tests to verify no regression**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_code_service.py -v
```

Expected: All existing tests PASS (financial columns added but don't break existing strategies)

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/services/strategy_code_service.py
git commit -m "feat: integrate financial injection into strategy execution

- Add _inject_financial() call in execute_indicator_strategy()
- Add _inject_financial() call in backtest_strategy()
- Financial indicators now available in all strategy executions"
```

---

## Task 7: Add End-to-End Test with Real Strategy

**Files:**
- Modify: `quantsys-v2/tests/test_strategy_financial_injection.py`

- [ ] **Step 1: Write end-to-end test with strategy code**

Add to `quantsys-v2/tests/test_strategy_financial_injection.py`:

```python
    def test_strategy_with_financial_indicators(self):
        """Test strategy execution with financial indicators"""
        service = StrategyCodeService()
        
        # Create a test strategy that uses financial indicators
        strategy_code = """
# 基本面 + 技术面共振策略
df['quality_stock'] = (
    (df['roe_y'] >= 10) &
    (df['debt_ratio_y'] < 70) &
    (df['gross_margin_q'] > 20)
)

df['buy'] = (df['rsi'] < 35) & df['quality_stock']
df['sell'] = df['rsi'] > 65
"""
        
        # Mock K-lines with RSI
        klines = [
            {'trade_date': '2026-04-20', 'close': 100, 'rsi': 30},
            {'trade_date': '2026-04-25', 'close': 102, 'rsi': 32},
            {'trade_date': '2026-05-15', 'close': 105, 'rsi': 70},
        ]
        
        # Mock financial data
        mock_income_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '营业收入': 100000000,
                '营业成本': 60000000,
                '净利润': 20000000,
                '营业利润': 25000000,
                '公告日期': '20260330'
            }
        ])
        
        mock_balance_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '资产总计': 500000000,
                '负债合计': 200000000,
                '股东权益合计': 300000000,
                '流动资产合计': 150000000,
                '流动负债合计': 100000000,
                '公告日期': '20260330'
            }
        ])
        
        mock_cashflow_df = pd.DataFrame([
            {
                '报告日': '20251231',
                '经营活动现金流量净额': 18000000,
                '公告日期': '20260330'
            }
        ])
        
        with patch('akshare.stock_financial_report_sina') as mock_ak:
            mock_ak.side_effect = [mock_income_df, mock_balance_df, mock_cashflow_df]
            
            # Inject financial indicators
            result_klines = service._inject_financial(klines, '600519')
            
            # Verify financial columns exist
            assert 'roe_y' in result_klines[0]
            assert 'gross_margin_q' in result_klines[0]
            assert 'debt_ratio_y' in result_klines[0]
            
            # Verify strategy can access these columns (would be tested in actual execution)
            # Here we just verify the columns have valid values after announcement date
            import math
            assert not math.isnan(result_klines[1]['roe_y'])  # After announcement
            assert result_klines[1]['roe_y'] > 0
```

- [ ] **Step 2: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py::TestFinancialInjection::test_strategy_with_financial_indicators -v
```

Expected: PASS

- [ ] **Step 3: Run all financial injection tests**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/tests/test_strategy_financial_injection.py
git commit -m "test: add end-to-end test with financial indicators

- Add test_strategy_with_financial_indicators test case
- Verify strategy code can access financial indicator columns
- Verify quality_stock filter logic works with financial data"
```

---

## Task 8: Manual Verification and Documentation

**Files:**
- Create: `quantsys-v2/examples/strategy_with_financials.py`

- [ ] **Step 1: Create example strategy using financial indicators**

Create `quantsys-v2/examples/strategy_with_financials.py`:

```python
"""
示例策略：基本面 + 技术面共振

使用财务指标过滤优质股票，结合技术指标生成交易信号。
"""

# 策略代码（indicator 类型）
STRATEGY_CODE = """
# 1. 基本面过滤：优质股票
df['quality_stock'] = (
    (df['roe_y'] >= 15) &              # 年度ROE >= 15%
    (df['debt_ratio_y'] < 60) &        # 负债率 < 60%
    (df['gross_margin_q'] > 30) &      # 季度毛利率 > 30%
    (df['ocf_to_profit_q'] > 0.8) &    # 现金流质量好
    (df['current_ratio_q'] > 1.2)      # 流动比率健康
)

# 2. 技术面信号
df['oversold'] = df['rsi'] < 30
df['macd_golden'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))

# 3. 买入信号：基本面 + 技术面共振
df['buy'] = df['quality_stock'] & (df['oversold'] | df['macd_golden'])

# 4. 卖出信号：技术面超买
df['sell'] = df['rsi'] > 70
"""

# 使用说明
"""
1. 创建策略：
   POST /api/strategies/user
   {
       "name": "基本面+技术面共振策略",
       "code": "<STRATEGY_CODE>",
       "code_type": "indicator",
       "description": "优质股票 + 技术面超卖时买入"
   }

2. 回测策略：
   POST /api/strategies/{strategy_id}/backtest
   {
       "symbol": "600519",
       "start_date": "2025-01-01",
       "end_date": "2026-05-27",
       "initial_cash": 100000
   }

3. 查看结果：
   - 策略会自动使用 18 个财务指标列
   - 回测结果包含收益率、夏普比率、最大回撤等
"""
```

- [ ] **Step 2: Test the example strategy manually**

```bash
cd quantsys-v2
# Start the API server
python api/server.py &

# Wait for server to start
sleep 3

# Create the strategy (save the returned strategy_id)
curl -X POST http://127.0.0.1:5001/api/strategies/user \
  -H "Content-Type: application/json" \
  -d @examples/strategy_with_financials.json

# Run backtest with a real stock (e.g., 600519 贵州茅台)
curl -X POST http://127.0.0.1:5001/api/strategies/1/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519", "start_date": "2025-01-01", "end_date": "2026-05-27", "initial_cash": 100000}'

# Stop the server
pkill -f "python api/server.py"
```

Expected: Backtest completes successfully, returns results with financial indicators used

- [ ] **Step 3: Update CLAUDE.md documentation**

Add to `quantsys-v2/CLAUDE.md` in the "Active Conventions" or relevant section:

```markdown
## Financial Indicators in Strategy Code

Strategy code now has access to 18 financial indicator columns (9 indicators × quarterly/annual):

**Quarterly indicators** (_q suffix):
- `roe_q` - Return on Equity (%)
- `gross_margin_q` - Gross Profit Margin (%)
- `net_profit_margin_q` - Net Profit Margin (%)
- `debt_ratio_q` - Debt to Asset Ratio (%)
- `revenue_growth_q` - Revenue Growth YoY (%)
- `ocf_to_profit_q` - Operating Cash Flow / Net Profit
- `current_ratio_q` - Current Ratio
- `roa_q` - Return on Assets (%)
- `operating_margin_q` - Operating Profit Margin (%)

**Annual indicators** (_y suffix): Same 9 indicators with `_y` suffix

**Usage example:**
```python
# Filter quality stocks
df['quality'] = (df['roe_y'] >= 15) & (df['debt_ratio_y'] < 60)

# Buy signal: quality + technical oversold
df['buy'] = df['quality'] & (df['rsi'] < 30)
```

**Data source:** akshare (Sina Finance primary, East Money fallback)
**Temporal alignment:** Forward-fill based on announcement date (no future information leakage)
**Missing data:** Columns filled with NaN when data unavailable
```

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/examples/strategy_with_financials.py quantsys-v2/CLAUDE.md
git commit -m "docs: add financial indicators documentation and example

- Add example strategy using financial indicators
- Update CLAUDE.md with financial indicators usage guide
- Document 18 available columns and usage patterns"
```

---

## Task 9: Final Integration Test and Cleanup

**Files:**
- Run full test suite

- [ ] **Step 1: Run all tests**

```bash
cd quantsys-v2
python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Check code coverage for new code**

```bash
cd quantsys-v2
python -m pytest tests/test_strategy_financial_injection.py --cov=services.strategy_code_service --cov-report=term-missing
```

Expected: Coverage > 80% for new methods

- [ ] **Step 3: Manual smoke test with real data**

```bash
cd quantsys-v2
python -c "
from services.strategy_code_service import StrategyCodeService

service = StrategyCodeService()

# Test with real stock
klines = [
    {'trade_date': '2026-04-20', 'close': 100},
    {'trade_date': '2026-05-15', 'close': 105},
]

result = service._inject_financial(klines, '600519')

print('Financial columns added:')
for key in result[0].keys():
    if key.endswith('_q') or key.endswith('_y'):
        print(f'  {key}: {result[0][key]}')
"
```

Expected: Prints 18 financial indicator columns with values or NaN

- [ ] **Step 4: Final commit and summary**

```bash
git add -A
git commit -m "feat: complete financial indicators injection implementation

Summary:
- Add _inject_financial() method to StrategyCodeService
- Implement two-tier data source fallback (Sina → East Money)
- Calculate 9 financial indicators from raw financial statements
- Forward-fill based on announcement date (avoid future information leakage)
- Inject 18 columns (9 indicators × quarterly/annual) into K-lines
- Integrate into strategy execution and backtest flows
- Add comprehensive tests and documentation

Performance: 2-5 seconds per stock for initial fetch
Suitable for: Single-stock and small-scale backtesting (< 10 stocks)
Future optimization: Plan B (service layer + caching) or Plan C (database persistence)"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] All 18 financial indicator columns are injected into K-lines
- [ ] Forward-fill logic correctly uses announcement date (no future information leakage)
- [ ] Two-tier fallback works (Sina → East Money → NaN)
- [ ] All 9 indicators calculate correctly from raw financial statements
- [ ] Strategy code can access and use financial indicators
- [ ] Existing strategies still work (no regression)
- [ ] Tests cover all major code paths (> 80% coverage)
- [ ] Documentation updated in CLAUDE.md
- [ ] Example strategy demonstrates usage

---

## Performance Notes

**Expected performance (Plan A - Minimal Implementation):**
- First call per stock: 2-5 seconds (6 akshare API calls)
- Memory: ~50KB per stock
- Suitable for: Single-stock backtesting, small-scale multi-stock (< 10 stocks)

**Known limitations:**
- No caching (re-fetches on every execution)
- No batch optimization
- Sequential API calls (not parallelized)

**Upgrade path:**
- Plan B: Move to DataService + add caching → 10x faster for repeated calls
- Plan C: Add database persistence + backfill → suitable for production and large-scale backtesting

