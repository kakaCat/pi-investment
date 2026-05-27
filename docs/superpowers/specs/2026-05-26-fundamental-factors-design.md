# 基本面因子模块设计文档

**日期**: 2026-05-26  
**作者**: Claude  
**状态**: 设计阶段

## 1. 概述

### 1.1 目标

在 `quantlib/factors/` 模块中新增三个基本面因子计算器:

- **ValueFactors (估值因子)**: PE分位数、PB分位数、股息率
- **QualityFactors (质量因子)**: ROE、FCF/净利润、毛利率变化率
- **GrowthFactors (成长因子)**: 营收增速(YoY)、利润增速(YoY)

### 1.2 设计原则

1. **职责分离**: 基本面因子独立于技术因子,创建新的基类 `FundamentalFactorCalculator`
2. **数据驱动**: 基于历史财务报表数据计算因子,支持分位数和同比增速
3. **模块化**: 遵循项目现有的因子模块化架构
4. **可扩展**: 便于后续添加更多基本面因子
5. **批量优化**: 支持批量查询和并行计算

### 1.3 技术栈

- **数据库**: PostgreSQL (新增3张财务报表历史表)
- **数据源**: AkShare (通过 `AkShareAdapter` 获取财务数据)
- **计算框架**: 继承 `BaseCalculator`,复用验证和格式化逻辑
- **并行处理**: ThreadPoolExecutor (批量计算)
- **缓存**: Redis (可选,提升性能)

## 2. 数据库设计

### 2.1 利润表历史数据表

```sql
CREATE TABLE quant.income_statements (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,  -- 'Q' (季度) 或 'Y' (年度)
    
    -- 收入相关
    revenue DOUBLE PRECISION,              -- 营业总收入
    operating_revenue DOUBLE PRECISION,    -- 营业收入
    
    -- 成本相关
    operating_cost DOUBLE PRECISION,       -- 营业成本
    gross_profit DOUBLE PRECISION,         -- 毛利润
    gross_margin DOUBLE PRECISION,         -- 毛利率 (%)
    
    -- 利润相关
    operating_profit DOUBLE PRECISION,     -- 营业利润
    total_profit DOUBLE PRECISION,         -- 利润总额
    net_profit DOUBLE PRECISION,           -- 净利润
    net_profit_parent DOUBLE PRECISION,    -- 归属母公司净利润
    
    -- 每股指标
    eps DOUBLE PRECISION,                  -- 基本每股收益
    eps_diluted DOUBLE PRECISION,          -- 稀释每股收益
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX idx_income_statements_symbol ON quant.income_statements(symbol);
CREATE INDEX idx_income_statements_report_date ON quant.income_statements(report_date);
CREATE INDEX idx_income_statements_period_type ON quant.income_statements(period_type);
```

### 2.2 资产负债表历史数据表

```sql
CREATE TABLE quant.balance_sheets (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,  -- 'Q' (季度) 或 'Y' (年度)
    
    -- 资产
    total_assets DOUBLE PRECISION,         -- 资产总计
    current_assets DOUBLE PRECISION,       -- 流动资产
    non_current_assets DOUBLE PRECISION,   -- 非流动资产
    
    -- 负债
    total_liabilities DOUBLE PRECISION,    -- 负债合计
    current_liabilities DOUBLE PRECISION,  -- 流动负债
    non_current_liabilities DOUBLE PRECISION, -- 非流动负债
    
    -- 权益
    total_equity DOUBLE PRECISION,         -- 股东权益合计
    parent_equity DOUBLE PRECISION,        -- 归属母公司股东权益
    
    -- 比率
    debt_ratio DOUBLE PRECISION,           -- 资产负债率 (%)
    current_ratio DOUBLE PRECISION,        -- 流动比率
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX idx_balance_sheets_symbol ON quant.balance_sheets(symbol);
CREATE INDEX idx_balance_sheets_report_date ON quant.balance_sheets(report_date);
CREATE INDEX idx_balance_sheets_period_type ON quant.balance_sheets(period_type);
```

### 2.3 现金流量表历史数据表

```sql
CREATE TABLE quant.cash_flows (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,  -- 'Q' (季度) 或 'Y' (年度)
    
    -- 经营活动现金流
    operating_cash_flow DOUBLE PRECISION,  -- 经营活动现金流量净额
    
    -- 投资活动现金流
    investing_cash_flow DOUBLE PRECISION,  -- 投资活动现金流量净额
    capex DOUBLE PRECISION,                -- 资本支出 (购建固定资产支付的现金)
    
    -- 筹资活动现金流
    financing_cash_flow DOUBLE PRECISION,  -- 筹资活动现金流量净额
    dividends_paid DOUBLE PRECISION,       -- 支付股利
    
    -- 自由现金流 (计算字段)
    free_cash_flow DOUBLE PRECISION,       -- FCF = 经营现金流 - 资本支出
    
    -- 现金及现金等价物
    cash_end DOUBLE PRECISION,             -- 期末现金及现金等价物余额
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX idx_cash_flows_symbol ON quant.cash_flows(symbol);
CREATE INDEX idx_cash_flows_report_date ON quant.cash_flows(report_date);
CREATE INDEX idx_cash_flows_period_type ON quant.cash_flows(period_type);
```

### 2.4 数据迁移脚本

创建迁移脚本: `quantsys-v2/migrations/add_financial_tables.sql`

**Why**: 需要版本化的数据库变更,便于回滚和追踪  
**How to apply**: 在实施阶段通过数据库迁移工具执行

## 3. Repository层设计

### 3.1 FinancialRepository

位置: `quantsys-v2/repositories/financial_repository.py`

负责财务报表数据的CRUD操作和批量查询,遵循项目的通用查询方法模式。

**核心方法:**

```python
class FinancialRepository(BaseRepository):
    """财务报表数据仓储"""
    
    # ========== 利润表 ==========
    
    def save_income_statement(self, data: Dict[str, Any]) -> None:
        """
        保存单条利润表数据 (INSERT ON CONFLICT UPDATE)
        
        Args:
            data: 包含 symbol, report_date, period_type 及财务字段的字典
        """
        
    def batch_save_income_statements(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量保存利润表数据
        
        Returns:
            插入/更新的行数
        """
        
    def get_income_statements(
        self, 
        symbol: str, 
        period_type: str = None,  # 'Q' or 'Y' or None (both)
        start_date: str = None,
        end_date: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        查询利润表历史数据
        
        通过参数控制筛选条件,避免为每个调用方写专用方法
        """
        
    def batch_get_latest_income_statements(
        self, 
        symbols: List[str],
        period_type: str = 'Y'
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量查询最新利润表数据
        
        优化: 单次SQL查询,避免N+1问题
        
        Returns:
            {symbol: data} 字典
        """
    
    # ========== 资产负债表 ==========
    
    def save_balance_sheet(self, data: Dict[str, Any]) -> None:
        """保存单条资产负债表数据"""
        
    def batch_save_balance_sheets(self, data_list: List[Dict[str, Any]]) -> int:
        """批量保存资产负债表数据"""
        
    def get_balance_sheets(
        self, 
        symbol: str,
        period_type: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """查询资产负债表历史数据"""
        
    def batch_get_latest_balance_sheets(
        self, 
        symbols: List[str],
        period_type: str = 'Y'
    ) -> Dict[str, Dict[str, Any]]:
        """批量查询最新资产负债表数据"""
    
    # ========== 现金流量表 ==========
    
    def save_cash_flow(self, data: Dict[str, Any]) -> None:
        """保存单条现金流量表数据"""
        
    def batch_save_cash_flows(self, data_list: List[Dict[str, Any]]) -> int:
        """批量保存现金流量表数据"""
        
    def get_cash_flows(
        self, 
        symbol: str,
        period_type: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """查询现金流量表历史数据"""
        
    def batch_get_latest_cash_flows(
        self, 
        symbols: List[str],
        period_type: str = 'Y'
    ) -> Dict[str, Dict[str, Any]]:
        """批量查询最新现金流量表数据"""
    
    # ========== 综合查询 ==========
    
    def get_complete_financials(
        self,
        symbol: str,
        period_type: str = 'Y',
        limit: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        查询完整财务数据 (三张表)
        
        Returns:
            {
                'income_statements': [...],
                'balance_sheets': [...],
                'cash_flows': [...]
            }
        """
```

**Why**: 遵循项目的Repository模式,提供通用查询方法而非为每个调用方写专用方法  
**How to apply**: 所有财务数据访问都通过此Repository,Service层不直接访问数据库

## 4. 因子计算器设计

### 4.1 FundamentalFactorCalculator 基类

位置: `quantsys-v2/quantlib/factors/fundamental_base.py`

```python
from typing import Optional, List, Dict, Any
import numpy as np
from quantlib.core.base_calculator import BaseCalculator
from quantlib.core.exceptions import DataValidationError, InsufficientDataError


class FundamentalFactorCalculator(BaseCalculator):
    """
    基本面因子计算器基类
    
    提供:
    - 财务数据验证
    - 分位数计算
    - 同比增速计算
    - 统一结果格式化
    
    所有基本面因子应继承此类
    """
    
    def __init__(self, precision: int = 4):
        super().__init__(precision)
    
    # ========== 数据验证 ==========
    
    def _validate_financial_data(
        self, 
        data: List[Dict[str, Any]], 
        min_length: Optional[int] = None,
        required_fields: List[str] = None
    ) -> None:
        """
        验证财务数据格式和内容
        
        Raises:
            DataValidationError: 数据格式无效
            InsufficientDataError: 数据长度不足
        """
        
    def _validate_period_type(self, period_type: str) -> None:
        """
        验证期间类型
        
        Args:
            period_type: 'Q' (季度) 或 'Y' (年度)
        """
        
    # ========== 分位数计算 ==========
    
    def _calculate_percentile(
        self, 
        current_value: float,
        historical_values: List[float],
        method: str = 'rank'
    ) -> float:
        """
        计算当前值在历史数据中的分位数
        
        Args:
            current_value: 当前值
            historical_values: 历史值列表 (包含当前值)
            method: 计算方法
                - 'rank': 排名法 (适合离散数据)
                - 'linear': 线性插值法 (适合连续数据)
        
        Returns:
            分位数 (0-100)
        """
        
    # ========== 增速计算 ==========
    
    def _calculate_yoy_growth(
        self,
        current_value: float,
        previous_value: float
    ) -> Optional[float]:
        """
        计算同比增速 (Year-over-Year Growth)
        
        Returns:
            增速百分比,如果previous_value为0或None返回None
        """
        
    def _calculate_qoq_growth(
        self,
        current_value: float,
        previous_value: float
    ) -> Optional[float]:
        """
        计算环比增速 (Quarter-over-Quarter Growth)
        
        Returns:
            增速百分比
        """
        
    def _calculate_cagr(
        self,
        start_value: float,
        end_value: float,
        periods: int
    ) -> Optional[float]:
        """
        计算复合年增长率 (CAGR)
        
        Args:
            start_value: 起始值
            end_value: 结束值
            periods: 期间数 (年数)
        
        Returns:
            CAGR百分比
        """
        
    # ========== 数据提取 ==========
    
    def _extract_field_series(
        self,
        data: List[Dict[str, Any]],
        field: str
    ) -> np.ndarray:
        """从财务数据列表中提取指定字段的时间序列"""
        
    def _get_latest_value(
        self,
        data: List[Dict[str, Any]],
        field: str,
        default: Any = None
    ) -> Any:
        """获取最新的字段值"""
        
    def _get_yoy_previous_value(
        self,
        data: List[Dict[str, Any]],
        field: str,
        period_type: str
    ) -> Optional[float]:
        """
        获取同比对应期的值
        
        - 年度: 上一年同期
        - 季度: 去年同季度
        """
```

**Why**: 基本面因子和技术因子是两个独立的领域,应该有独立的基类  
**How to apply**: 所有基本面因子计算器继承此类,复用通用计算逻辑

### 4.2 ValueFactors (估值因子)

位置: `quantsys-v2/quantlib/factors/value.py`

```python
class ValueFactors(FundamentalFactorCalculator):
    """
    估值因子计算器
    
    提供:
    - PE分位数 (3年、5年)
    - PB分位数 (3年、5年)
    - 股息率及历史平均
    """
    
    def get_supported_methods(self) -> List[str]:
        return [
            'pe_percentile_3y',      # PE 3年分位数
            'pe_percentile_5y',      # PE 5年分位数
            'pb_percentile_3y',      # PB 3年分位数
            'pb_percentile_5y',      # PB 5年分位数
            'dividend_yield',        # 当前股息率
            'dividend_yield_avg_3y', # 3年平均股息率
        ]
    
    def calculate(
        self,
        symbol: str,
        current_pe: float,
        current_pb: float,
        historical_data: Dict[str, List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, float]:
        """
        计算估值因子
        
        Args:
            symbol: 股票代码
            current_pe: 当前PE
            current_pb: 当前PB
            historical_data: 历史财务数据
                {
                    'income_statements': [...],  # 至少5年年度数据
                    'balance_sheets': [...],
                    'cash_flows': [...]
                }
        
        Returns:
            {
                'pe_percentile_3y': 65.5,
                'pe_percentile_5y': 72.3,
                'pb_percentile_3y': 45.2,
                'pb_percentile_5y': 50.1,
                'dividend_yield': 2.5,
                'dividend_yield_avg_3y': 2.3
            }
        """
```

**计算逻辑:**

1. **PE分位数**: 从 `quant.stocks` 表获取历史PE快照,计算当前PE在过去3年/5年的分位数
2. **PB分位数**: 同PE分位数
3. **股息率**: 从 `cash_flows` 表获取最近一年的 `dividends_paid`,除以当前市值
4. **3年平均股息率**: 计算过去3年股息率的平均值

### 4.3 QualityFactors (质量因子)

位置: `quantsys-v2/quantlib/factors/quality.py`

```python
class QualityFactors(FundamentalFactorCalculator):
    """
    质量因子计算器
    
    提供:
    - ROE (最新值、TTM)
    - FCF/净利润比率
    - 毛利率变化率 (季度、年度)
    """
    
    def get_supported_methods(self) -> List[str]:
        return [
            'roe_latest',            # 最新ROE
            'roe_ttm',               # TTM ROE (过去4个季度)
            'fcf_to_net_profit',     # FCF/净利润
            'gross_margin_change_qoq', # 毛利率环比变化
            'gross_margin_change_yoy', # 毛利率同比变化
        ]
    
    def calculate(
        self,
        symbol: str,
        historical_data: Dict[str, List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, float]:
        """
        计算质量因子
        
        Args:
            symbol: 股票代码
            historical_data: 历史财务数据
                - 需要至少2年的季度数据 (计算TTM和同比)
        
        Returns:
            {
                'roe_latest': 18.5,
                'roe_ttm': 17.8,
                'fcf_to_net_profit': 0.85,
                'gross_margin_change_qoq': 1.2,
                'gross_margin_change_yoy': 3.5
            }
        """
```

**计算逻辑:**

1. **ROE最新值**: 从 `balance_sheets` 获取最新的 `parent_equity`,从 `income_statements` 获取最新的 `net_profit_parent`,计算 ROE = 净利润 / 股东权益
2. **ROE TTM**: 取最近4个季度的净利润之和,除以最新的股东权益
3. **FCF/净利润**: 从 `cash_flows` 获取 `free_cash_flow` 和 `income_statements` 的 `net_profit`,计算比率
4. **毛利率变化率**: 从 `income_statements` 获取 `gross_margin`,计算环比(QoQ)和同比(YoY)变化

### 4.4 GrowthFactors (成长因子)

位置: `quantsys-v2/quantlib/factors/growth.py`

```python
class GrowthFactors(FundamentalFactorCalculator):
    """
    成长因子计算器
    
    提供:
    - 营收增速 (季度YoY、年度YoY、3年CAGR)
    - 利润增速 (季度YoY、年度YoY、3年CAGR)
    """
    
    def get_supported_methods(self) -> List[str]:
        return [
            'revenue_growth_yoy_q',    # 营收季度同比增速
            'revenue_growth_yoy_y',    # 营收年度同比增速
            'revenue_cagr_3y',         # 营收3年复合增长率
            'net_profit_growth_yoy_q', # 净利润季度同比增速
            'net_profit_growth_yoy_y', # 净利润年度同比增速
            'net_profit_cagr_3y',      # 净利润3年复合增长率
        ]
    
    def calculate(
        self,
        symbol: str,
        historical_data: Dict[str, List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, float]:
        """
        计算成长因子
        
        Args:
            symbol: 股票代码
            historical_data: 历史财务数据
                - 季度数据: 至少2年 (8个季度)
                - 年度数据: 至少4年
        
        Returns:
            {
                'revenue_growth_yoy_q': 15.5,
                'revenue_growth_yoy_y': 12.3,
                'revenue_cagr_3y': 18.2,
                'net_profit_growth_yoy_q': 22.1,
                'net_profit_growth_yoy_y': 18.5,
                'net_profit_cagr_3y': 25.3
            }
        """
```

**计算逻辑:**

1. **季度同比增速**: 最新季度值 vs 去年同季度值,计算增长率
2. **年度同比增速**: 最新年度值 vs 上一年度值,计算增长率
3. **3年CAGR**: 使用3年前和当前的年度值,计算复合年增长率

**Why**: 三个因子类分别负责不同维度的基本面分析,职责清晰  
**How to apply**: 根据需要选择性计算某一类或全部因子

## 5. 数据同步服务

### 5.1 FinancialDataSyncService

位置: `quantsys-v2/services/financial_data_sync_service.py`

负责从akshare获取财务报表数据并同步到数据库。

```python
class FinancialDataSyncService:
    """
    财务数据同步服务
    
    职责:
    1. 从akshare获取财务报表数据
    2. 数据清洗和转换
    3. 批量写入数据库
    4. 增量更新策略
    """
    
    def __init__(
        self,
        financial_repo: FinancialRepository,
        akshare_adapter: AkShareAdapter
    ):
        self.financial_repo = financial_repo
        self.akshare_adapter = akshare_adapter
    
    def sync_stock_financials(
        self,
        symbol: str,
        years: int = 5,
        include_quarterly: bool = True
    ) -> Dict[str, int]:
        """
        同步单只股票的财务数据
        
        Args:
            symbol: 股票代码
            years: 获取最近N年的数据
            include_quarterly: 是否包含季度数据
        
        Returns:
            {
                'income_statements': 20,  # 插入/更新的行数
                'balance_sheets': 20,
                'cash_flows': 20
            }
        """
        
    def batch_sync_financials(
        self,
        symbols: List[str],
        years: int = 5,
        include_quarterly: bool = True,
        max_workers: int = 5
    ) -> Dict[str, Any]:
        """
        批量同步多只股票的财务数据 (并行)
        
        Returns:
            {
                'success': 150,
                'failed': 5,
                'total': 155,
                'errors': [...]
            }
        """
        
    def incremental_sync(
        self,
        symbols: List[str] = None,
        days_threshold: int = 7
    ) -> Dict[str, Any]:
        """
        增量更新财务数据
        
        只更新距离上次更新超过N天的股票
        """
```

**数据转换流程:**

1. 调用 `akshare_adapter.get_financial_data()` 获取原始数据
2. 解析并映射字段 (akshare字段 → 数据库字段)
3. 计算衍生字段 (如毛利率、FCF)
4. 数据质量检查 (去重、空值处理、合理性检查)
5. 批量写入数据库

**Why**: 集中管理数据同步逻辑,避免在多处重复实现  
**How to apply**: 通过API/CLI/定时任务调用此服务同步数据

### 5.2 API端点

在 `quantsys-v2/api/routes/data.py` 中添加:

```python
@router.post("/data/sync-financials")
def sync_financials(request: SyncFinancialsRequest):
    """
    同步财务报表数据
    
    Request:
        {
            "symbols": ["600519.SH", "000001.SZ"],  # 可选,None表示全部
            "years": 5,                              # 获取最近N年
            "include_quarterly": true,               # 是否包含季度数据
            "mode": "full"                           # "full" 或 "incremental"
        }
    
    Response:
        {
            "success": true,
            "synced": 150,
            "failed": 5,
            "errors": [...]
        }
    """
```

### 5.3 CLI命令

在 `quantsys-v2/cli/commands/data.py` 中添加:

```bash
# 同步单只股票
python cli/main.py data sync-financials --symbol 600519.SH --years 5

# 批量同步
python cli/main.py data sync-financials --symbols 600519.SH,000001.SZ --years 5

# 增量更新所有股票
python cli/main.py data sync-financials --mode incremental --days 7

# 同步沪深300成分股
python cli/main.py data sync-financials --index hs300 --years 5
```

## 6. 因子计算服务

### 6.1 FundamentalFactorService

位置: `quantsys-v2/services/fundamental_factor_service.py`

统一的基本面因子计算服务,供API/CLI/Scheduler调用。

```python
class FundamentalFactorService:
    """
    基本面因子计算服务
    
    职责:
    1. 协调数据获取和因子计算
    2. 批量计算优化
    3. 结果缓存
    """
    
    def __init__(
        self,
        financial_repo: FinancialRepository,
        stock_repo: StockRepository,
        cache_service = None
    ):
        self.financial_repo = financial_repo
        self.stock_repo = stock_repo
        self.cache_service = cache_service
        
        # 初始化因子计算器
        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()
        self.growth_factors = GrowthFactors()
    
    def calculate_all_factors(
        self,
        symbol: str,
        factor_types: List[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        计算单只股票的所有基本面因子
        
        Args:
            symbol: 股票代码
            factor_types: 要计算的因子类型 ['value', 'quality', 'growth'],None表示全部
            use_cache: 是否使用缓存
        
        Returns:
            {
                'symbol': '600519.SH',
                'name': '贵州茅台',
                'timestamp': '2026-05-26T10:00:00',
                'value_factors': {...},
                'quality_factors': {...},
                'growth_factors': {...},
                'errors': []
            }
        """
        
    def batch_calculate_factors(
        self,
        symbols: List[str],
        factor_types: List[str] = None,
        max_workers: int = 10
    ) -> List[Dict[str, Any]]:
        """
        批量计算基本面因子 (并行)
        
        优化:
        - 批量查询财务数据 (避免N+1)
        - 并行计算
        - 失败容错
        """
```

**Why**: Service层协调Repository和Calculator,提供统一的业务接口  
**How to apply**: API/CLI通过此Service计算因子,不直接调用Calculator

### 6.2 API端点

在 `quantsys-v2/api/routes/factors.py` 中添加:

```python
@router.post("/factors/fundamental")
def calculate_fundamental_factors(request: FundamentalFactorRequest):
    """
    计算基本面因子
    
    Request:
        {
            "symbols": ["600519.SH", "000001.SZ"],
            "factor_types": ["value", "quality", "growth"],
            "use_cache": true
        }
    
    Response:
        {
            "success": true,
            "factors": [...],
            "failed": ["000002.SZ"],
            "errors": [...]
        }
    """

@router.get("/factors/fundamental/{symbol}")
def get_fundamental_factors(symbol: str, factor_types: str = None):
    """获取单只股票的基本面因子"""
```

### 6.3 CLI命令

```bash
# 计算单只股票的基本面因子
python cli/main.py factor fundamental --symbol 600519.SH

# 计算指定类型的因子
python cli/main.py factor fundamental --symbol 600519.SH --types value,quality

# 批量计算
python cli/main.py factor fundamental --symbols 600519.SH,000001.SZ

# 计算并保存到文件
python cli/main.py factor fundamental --symbol 600519.SH --output factors.json
```

### 6.4 集成到OpportunityScoringService

扩展现有的机会评分服务,使用新的基本面因子:

```python
class OpportunityScoringService:
    
    def __init__(
        self,
        kline_repo: KlineRepository,
        stock_repo: StockRepository,
        factor_adapter,
        fundamental_factor_service: FundamentalFactorService  # 新增
    ):
        self.fundamental_factor_service = fundamental_factor_service
    
    def _calculate_fundamental_score(
        self,
        symbol: str,
        fundamental: Optional[Dict],
        conditions: List[str]
    ) -> float:
        """
        计算基本面评分 (增强版)
        
        新增条件:
        - 'pe_low_percentile': PE处于历史低位 (< 30分位)
        - 'pb_low_percentile': PB处于历史低位 (< 30分位)
        - 'roe_high': ROE > 15%
        - 'roe_stable': ROE稳定 (近3年标准差 < 5)
        - 'fcf_positive': FCF/净利润 > 0.8
        - 'gross_margin_improving': 毛利率改善 (YoY > 0)
        - 'revenue_growth_high': 营收增速 > 15%
        - 'profit_growth_high': 利润增速 > 20%
        """
        
        # 获取基本面因子
        try:
            factors = self.fundamental_factor_service.calculate_all_factors(symbol)
        except Exception as e:
            logger.warning(f"{symbol}: 基本面因子计算失败 - {e}")
            return 50.0
        
        score = 0.0
        
        for condition in conditions:
            if condition == 'pe_low_percentile':
                if factors['value_factors'].get('pe_percentile_3y', 100) < 30:
                    score += 20
            elif condition == 'roe_high':
                if factors['quality_factors'].get('roe_ttm', 0) > 15:
                    score += 20
            # ... 其他条件
        
        return min(score, 100.0)
```

**Why**: 增强现有评分系统,使用更精确的基本面因子  
**How to apply**: 在 `/api/signals/scan` 端点中使用新的评分逻辑

## 7. 测试策略

### 7.1 单元测试

```python
# tests/test_fundamental_factors.py

class TestFundamentalFactorCalculator:
    """基类测试"""
    
    def test_calculate_percentile(self):
        """测试分位数计算"""
        
    def test_calculate_yoy_growth(self):
        """测试同比增速计算"""
        
    def test_calculate_cagr(self):
        """测试复合增长率计算"""

class TestValueFactors:
    """估值因子测试"""
    
    def test_pe_percentile_calculation(self):
        """测试PE分位数计算 - 使用mock数据"""
        
    def test_insufficient_data_handling(self):
        """测试数据不足的处理"""

class TestQualityFactors:
    """质量因子测试"""
    
    def test_roe_ttm_calculation(self):
        """测试TTM ROE计算"""
        
    def test_fcf_to_net_profit_calculation(self):
        """测试FCF/净利润计算"""

class TestGrowthFactors:
    """成长因子测试"""
    
    def test_revenue_growth_yoy(self):
        """测试营收同比增速"""
        
    def test_cagr_calculation(self):
        """测试CAGR计算"""

# tests/test_financial_repository.py

class TestFinancialRepository:
    """Repository层测试 - 使用test数据库"""
    
    def test_save_income_statement(self):
        """测试保存利润表"""
        
    def test_batch_get_latest_income_statements(self):
        """测试批量获取最新数据"""

# tests/test_financial_data_sync_service.py

class TestFinancialDataSyncService:
    """数据同步服务测试"""
    
    @patch('quantlib.adapters.akshare_adapter.AkShareAdapter')
    def test_sync_stock_financials(self, mock_adapter):
        """测试单股票同步 - mock akshare"""
        
    def test_batch_sync_with_failures(self):
        """测试批量同步时的失败处理"""
```

### 7.2 集成测试

```python
# tests/integration/test_fundamental_factor_flow.py

class TestFundamentalFactorFlow:
    """端到端测试"""
    
    def test_sync_and_calculate_flow(self):
        """
        测试完整流程:
        1. 同步财务数据
        2. 计算基本面因子
        3. 验证结果
        """
```

**测试覆盖率目标**: > 80%

**Why**: 确保因子计算的正确性和数据同步的可靠性  
**How to apply**: 在实施阶段编写测试,CI/CD中自动运行

## 8. 错误处理

### 8.1 自定义异常

在 `quantsys-v2/quantlib/core/exceptions.py` 中新增:

```python
class FinancialDataError(Exception):
    """财务数据相关错误基类"""
    pass

class InsufficientFinancialDataError(FinancialDataError):
    """财务数据不足错误"""
    
    def __init__(self, symbol: str, required_periods: int, actual_periods: int):
        self.symbol = symbol
        self.required_periods = required_periods
        self.actual_periods = actual_periods
        super().__init__(
            f"{symbol}: 需要至少{required_periods}期数据,实际只有{actual_periods}期"
        )

class FinancialDataSyncError(FinancialDataError):
    """财务数据同步错误"""
    
    def __init__(self, symbol: str, table_type: str, reason: str):
        self.symbol = symbol
        self.table_type = table_type
        self.reason = reason
        super().__init__(
            f"{symbol}: {table_type}同步失败 - {reason}"
        )

class InvalidFinancialDataError(FinancialDataError):
    """无效的财务数据"""
    
    def __init__(self, symbol: str, field: str, value: Any, reason: str):
        super().__init__(
            f"{symbol}: 字段{field}的值{value}无效 - {reason}"
        )
```

### 8.2 错误处理策略

**原则**: 失败容错,部分成功优于全部失败

```python
class FundamentalFactorService:
    
    def calculate_all_factors(self, symbol: str, factor_types: List[str] = None) -> Dict[str, Any]:
        """计算所有基本面因子 (带错误处理)"""
        
        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'errors': []
        }
        
        try:
            # 获取股票信息
            stock_info = self.stock_repo.get_by_symbol(symbol, ['name'])
            if not stock_info:
                raise ValueError(f"股票{symbol}不存在")
            result['name'] = stock_info['name']
            
            # 准备历史数据
            historical_data = self._prepare_historical_data(symbol)
            
            # 计算各类因子 - 独立失败
            factor_types = factor_types or ['value', 'quality', 'growth']
            
            if 'value' in factor_types:
                try:
                    result['value_factors'] = self.calculate_value_factors(symbol, historical_data)
                except InsufficientFinancialDataError as e:
                    logger.warning(str(e))
                    result['errors'].append({'type': 'value_factors', 'error': str(e)})
                    result['value_factors'] = None
            
            # ... 其他因子类型
            
            return result
            
        except Exception as e:
            logger.error(f"{symbol}: 因子计算失败 - {e}", exc_info=True)
            result['errors'].append({'type': 'fatal', 'error': str(e)})
            return result
```

**Why**: 单个因子计算失败不应影响其他因子,提供部分结果比完全失败更有价值  
**How to apply**: 在Service层捕获异常,记录错误但继续执行

### 8.3 数据质量监控

创建 `FinancialDataQualityMonitor` 用于监控数据质量:

```python
class FinancialDataQualityMonitor:
    """财务数据质量监控"""
    
    def check_data_completeness(self, symbol: str) -> Dict[str, Any]:
        """
        检查数据完整性
        
        Returns:
            {
                'symbol': '600519.SH',
                'income_statements': {
                    'yearly_count': 5,
                    'quarterly_count': 20,
                    'latest_date': '2025-12-31',
                    'missing_periods': []
                },
                'quality_score': 95  # 0-100
            }
        """
        
    def check_data_consistency(self, symbol: str) -> List[Dict[str, Any]]:
        """
        检查数据一致性
        
        检查项:
        - 资产 = 负债 + 权益
        - 毛利润 = 营收 - 营业成本
        - FCF = 经营现金流 - 资本支出
        
        Returns:
            不一致项列表
        """
        
    def check_outliers(self, symbol: str) -> List[Dict[str, Any]]:
        """
        检查异常值
        
        - ROE突变 (> 50%变化)
        - 营收/利润突变
        - 负债率异常 (> 100%)
        
        Returns:
            异常项列表
        """
```

**Why**: 财务数据质量直接影响因子计算结果,需要主动监控  
**How to apply**: 在数据同步后运行质量检查,记录问题数据

## 9. 性能优化

### 9.1 缓存策略

使用Redis缓存因子计算结果:

```python
class FundamentalFactorService:
    
    def __init__(self, financial_repo, stock_repo, cache_service=None):
        self.cache_service = cache_service
        
        # 缓存TTL配置
        self.cache_ttl = {
            'value_factors': 3600 * 24,      # 1天
            'quality_factors': 3600 * 24,    # 1天
            'growth_factors': 3600 * 24,     # 1天
            'historical_data': 3600 * 24 * 7 # 7天
        }
    
    def calculate_all_factors(self, symbol: str, use_cache: bool = True) -> Dict[str, Any]:
        """计算因子 (带缓存)"""
        
        if use_cache and self.cache_service:
            cache_key = f"fundamental_factors:{symbol}"
            cached = self.cache_service.get(cache_key)
            if cached:
                logger.debug(f"{symbol}: 使用缓存的因子数据")
                return cached
        
        # 计算因子
        result = self._do_calculate_all_factors(symbol)
        
        # 写入缓存
        if use_cache and self.cache_service:
            self.cache_service.set(cache_key, result, ttl=self.cache_ttl['value_factors'])
        
        return result
```

### 9.2 批量查询优化

Repository层使用批量查询避免N+1问题:

```python
def batch_get_latest_income_statements(
    self, 
    symbols: List[str],
    period_type: str = 'Y'
) -> Dict[str, Dict[str, Any]]:
    """批量查询最新利润表数据 - 单次SQL"""
    
    query = """
        SELECT DISTINCT ON (symbol) *
        FROM quant.income_statements
        WHERE symbol = ANY(%s) AND period_type = %s
        ORDER BY symbol, report_date DESC
    """
    
    cursor.execute(query, (symbols, period_type))
    rows = cursor.fetchall()
    
    return {row['symbol']: self._to_domain_object(row) for row in rows}
```

### 9.3 并行计算

批量计算时使用线程池并行处理:

```python
def batch_calculate_factors(
    self,
    symbols: List[str],
    factor_types: List[str] = None,
    max_workers: int = 10
) -> List[Dict[str, Any]]:
    """批量计算 (并行)"""
    
    # 批量查询财务数据 (避免N+1)
    historical_data_map = self._batch_prepare_historical_data(symbols)
    
    # 并行计算
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                self._calculate_single_stock,
                symbol,
                historical_data_map.get(symbol),
                factor_types
            ): symbol
            for symbol in symbols
        }
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                symbol = futures[future]
                logger.error(f"{symbol}: 计算失败 - {e}")
    
    return results
```

**Why**: 财务数据查询和因子计算是CPU密集型操作,需要优化性能  
**How to apply**: 在Service层实现缓存和批量优化,对调用方透明

## 10. 实施计划

### 10.1 阶段划分

**阶段1: 数据层 (3-4天)**
- 创建数据库表和迁移脚本
- 实现 FinancialRepository
- 实现 FinancialDataSyncService
- 单元测试

**阶段2: 计算层 (3-4天)**
- 实现 FundamentalFactorCalculator 基类
- 实现 ValueFactors, QualityFactors, GrowthFactors
- 单元测试

**阶段3: 服务层 (2-3天)**
- 实现 FundamentalFactorService
- 集成到 OpportunityScoringService
- 单元测试和集成测试

**阶段4: API/CLI (2天)**
- 添加API端点
- 添加CLI命令
- API测试

**阶段5: 优化和监控 (2天)**
- 实现缓存
- 实现数据质量监控
- 性能测试

**总计: 12-15天**

### 10.2 依赖关系

```
数据库表 → FinancialRepository → FinancialDataSyncService
                ↓
         FundamentalFactorCalculator (基类)
                ↓
    ValueFactors, QualityFactors, GrowthFactors
                ↓
         FundamentalFactorService
                ↓
         API/CLI + OpportunityScoringService
```

### 10.3 风险和缓解

**风险1: AkShare数据质量问题**
- 缓解: 实现数据质量检查,记录异常数据,提供手动修正接口

**风险2: 历史数据缺失**
- 缓解: 优雅降级,数据不足时返回部分因子或None

**风险3: 性能问题**
- 缓解: 实现缓存,批量查询优化,异步计算

**风险4: 财务数据更新频率**
- 缓解: 实现增量更新策略,定时任务自动同步

### 10.4 验收标准

1. **功能完整性**
   - 三个因子类全部实现,支持所有声明的方法
   - 数据同步服务支持单股票、批量、增量更新
   - API/CLI命令可用

2. **数据质量**
   - 财务数据同步成功率 > 95%
   - 因子计算成功率 > 90% (有数据的股票)

3. **性能**
   - 单股票因子计算 < 500ms (无缓存)
   - 批量计算100只股票 < 10s (并行)
   - 缓存命中率 > 80%

4. **测试覆盖率**
   - 单元测试覆盖率 > 80%
   - 核心计算逻辑覆盖率 > 95%

5. **文档**
   - API文档完整
   - CLI帮助文档完整
   - 代码注释清晰

## 11. 总结

本设计文档详细描述了基本面因子模块的完整实现方案,包括:

1. **数据库设计**: 3张财务报表历史表,支持季度和年度数据
2. **Repository层**: 通用查询方法,批量优化
3. **因子计算器**: 独立的基类和三个因子类,职责清晰
4. **数据同步服务**: 从akshare获取数据,支持批量和增量更新
5. **因子计算服务**: 统一的业务接口,支持缓存和并行计算
6. **API/CLI**: 完整的对外接口
7. **测试和错误处理**: 完善的测试策略和错误处理机制
8. **性能优化**: 缓存、批量查询、并行计算

该设计遵循项目现有架构,职责分离清晰,易于扩展和维护。

