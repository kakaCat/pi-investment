"""
Pydantic models for QuantSys V2 API

所有API请求和响应的数据模型定义
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# ==================== 通用模型 ====================

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    db_connected: bool
    db_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PlatformStatusResponse(BaseModel):
    """平台状态响应"""
    status: str
    holdings_count: int
    balance: Optional[Dict[str, Any]] = None
    recent_signals: int


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str


# ==================== 股票相关模型 ====================

class StockInfo(BaseModel):
    """股票信息"""
    symbol: str
    name: str
    market: str = ""
    industry: str = ""


class StockSearchRequest(BaseModel):
    """股票搜索请求"""
    q: str = Field(..., min_length=1, description="搜索关键词")
    page: int = Field(default=1, ge=1, description="页码")
    pageSize: int = Field(default=20, ge=1, le=100, description="每页数量")


class StockSearchResponse(BaseModel):
    """股票搜索响应"""
    query: str
    total: int
    page: int
    pageSize: int
    stocks: List[StockInfo]


class StockListResponse(BaseModel):
    """股票列表响应"""
    count: int
    stocks: List[StockInfo]


class StockResolveRequest(BaseModel):
    """股票代码解析请求"""
    code: str = Field(..., min_length=1, description="股票代码")


class StockResolveResponse(BaseModel):
    """股票代码解析响应"""
    found: bool
    symbol: str
    name: Optional[str] = None
    market: Optional[str] = None
    industry: Optional[str] = None


class StockAddRequest(BaseModel):
    """添加股票请求"""
    symbol: str
    name: str
    market: Optional[str] = None
    industry: Optional[str] = None


class StockAddResponse(BaseModel):
    """添加股票响应"""
    success: bool
    symbol: str


class DataStatusResponse(BaseModel):
    """数据状态响应"""
    symbol: str
    has_klines: bool
    kline_count: int
    date_range: Optional[Dict[str, str]] = None
    has_factors: bool
    factor_count: int


# ==================== K线相关模型 ====================

class KlineData(BaseModel):
    """K线数据"""
    symbol: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None


class KlineResponse(BaseModel):
    """K线响应"""
    symbol: str
    count: int
    klines: List[Dict[str, Any]]


# ==================== 因子相关模型 ====================

class FactorResponse(BaseModel):
    """因子响应"""
    symbol: str
    stock_name: str
    market: str
    current_price: Optional[float] = None
    factors: Dict[str, Any]
    signals_count: int


class StockCompareRequest(BaseModel):
    """股票对比请求"""
    symbols: List[str] = Field(..., min_length=1, max_length=5, description="股票代码列表（最多5个）")


class StockComparisonItem(BaseModel):
    """股票对比项"""
    symbol: str
    name: str
    market: str
    current_price: Optional[float] = None
    factors: Dict[str, Any]


class StockCompareResponse(BaseModel):
    """股票对比响应"""
    comparisons: List[StockComparisonItem]
    count: int


class TechnicalIndicatorsResponse(BaseModel):
    """技术指标响应"""
    symbol: str
    factors: Dict[str, Any]
    data_days: int


# ==================== 信号相关模型 ====================

class SignalData(BaseModel):
    """信号数据"""
    signal_id: Optional[int] = None
    symbol: str
    signal_type: str
    signal_date: str
    confidence: Optional[float] = None
    price: Optional[float] = None
    factors: Optional[Dict[str, Any]] = None


class SignalsResponse(BaseModel):
    """信号列表响应"""
    signals: List[Dict[str, Any]]
    count: int
    date: str = ""
    source: str = "database"


class SignalsHistoryResponse(BaseModel):
    """信号历史响应"""
    success: bool
    data: List[Dict[str, Any]]
    stats: Dict[str, Any]


class SignalScanRequest(BaseModel):
    """信号扫描请求"""
    stocks: List[str] = Field(..., min_length=1, description="股票代码列表")


class SignalScanResult(BaseModel):
    """信号扫描结果"""
    symbol: str
    latest_signal: Dict[str, Any]
    signal_count: int


class SignalScanResponse(BaseModel):
    """信号扫描响应"""
    success: bool
    results: List[SignalScanResult]
    count: int


# ==================== 回测相关模型 ====================

class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field(..., description="股票代码")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    initial_capital: float = Field(..., gt=0, description="初始资金")
    ma_short: Optional[int] = Field(default=5, ge=2, description="短期均线周期")
    ma_long: Optional[int] = Field(default=20, ge=5, description="长期均线周期")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="其他策略参数")


class TradeRecord(BaseModel):
    """交易记录"""
    date: str
    action: str
    price: float
    shares: Optional[float] = None
    value: Optional[float] = None


class BacktestResponse(BaseModel):
    """回测响应"""
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    total_trades: int
    trades: List[TradeRecord]
    message: Optional[str] = None


class BacktestResultsResponse(BaseModel):
    """回测结果列表响应"""
    count: int
    results: List[Dict[str, Any]]


# ==================== 风险相关模型 ====================

class RiskCheckRequest(BaseModel):
    """风险检查请求"""
    symbols: Optional[List[str]] = None
    account_value: Optional[float] = Field(default=None, gt=0, description="账户总价值")


class RiskCheckItem(BaseModel):
    """风险检查项"""
    type: str
    level: str
    message: str
    suggestion: str


class RiskCheckResult(BaseModel):
    """风险检查结果"""
    symbol: str
    position_value: float
    checks: List[RiskCheckItem]


class RiskCheckResponse(BaseModel):
    """风险检查响应"""
    total_holdings: int
    checks: List[RiskCheckResult]
    risk_level: str


# ==================== 报告相关模型 ====================

class DailyReportResponse(BaseModel):
    """每日报告响应"""
    date: Optional[str] = None
    risk_summary: Dict[str, Any]
    signals: List[Dict[str, Any]]
    signal_count: int


# ==================== 数据更新相关模型 ====================

class DataUpdateRequest(BaseModel):
    """数据更新请求"""
    source: Literal["portfolio", "watchlist", "hs300", "all"] = Field(..., description="数据源")
    days: int = Field(default=730, gt=0, description="获取最近N天数据")
    async_mode: bool = Field(default=False, alias="async", description="是否异步执行")
    force: bool = Field(default=False, description="强制全量加载（忽略days参数）")


class DataUpdateResponse(BaseModel):
    """数据更新响应（同步）"""
    success: bool
    source: str
    total: int
    succeeded: int
    failed: int
    details: List[Dict[str, str]]


class DataUpdateAsyncResponse(BaseModel):
    """数据更新响应（异步）"""
    success: bool
    job_id: str
    message: str


class DataUpdateJobResponse(BaseModel):
    """数据更新任务状态响应"""
    job_id: str
    source: str
    days: int
    force: bool
    status: str
    created_at: str
    result: Optional[DataUpdateResponse] = None
    error: Optional[str] = None


class ComputeFactorsRequest(BaseModel):
    """计算因子请求"""
    symbol: str = Field(..., description="股票代码")


class ComputeFactorsResponse(BaseModel):
    """计算因子响应"""
    success: bool
    symbol: str
    date: str
    factor_count: int
    factors: Dict[str, Any]


# ==================== 性能相关模型 ====================

class StrategyPerformanceResponse(BaseModel):
    """策略表现响应"""
    strategy_id: str
    backtest_count: int
    stats: Dict[str, Any]
    recent_results: List[Dict[str, Any]]


# ==================== 执行相关模型 ====================

class ExecutionRecord(BaseModel):
    """执行记录"""
    execution_id: Optional[int] = None
    signal_id: int
    symbol: str
    signal_type: str
    status: str
    open_date: str
    open_price: float
    quantity: float
    close_date: Optional[str] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExecutionListResponse(BaseModel):
    """执行记录列表响应"""
    executions: List[Dict[str, Any]]
    count: int


class ExecutionStatsResponse(BaseModel):
    """执行统计响应"""
    total_executions: int
    open_positions: int
    closed_positions: int
    cancelled: int
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None


class DailyExecutionStatsResponse(BaseModel):
    """每日执行统计响应"""
    daily_stats: List[Dict[str, Any]]
    count: int


class ExecutionCreateRequest(BaseModel):
    """创建执行记录请求"""
    signal_id: int
    symbol: str
    signal_type: str
    open_date: str
    open_price: float
    quantity: float
    status: str = "open"


class ExecutionCreateResponse(BaseModel):
    """创建执行记录响应"""
    id: int
    message: str


class ExecutionCloseRequest(BaseModel):
    """平仓请求"""
    close_date: str = Field(..., description="平仓日期")
    close_price: float = Field(..., gt=0, description="平仓价格")


class ExecutionCloseResponse(BaseModel):
    """平仓响应"""
    message: str
    execution: Dict[str, Any]


class ExecutionStatusUpdateRequest(BaseModel):
    """更新执行状态请求"""
    status: str = Field(..., description="新状态")


class ExecutionSummaryResponse(BaseModel):
    """执行综合摘要响应"""
    total_signals: int
    executed_signals: int
    execution_rate: float
    open_positions: int
    closed_positions: int
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None


# ==================== ML相关模型 ====================

class MLTrainRequest(BaseModel):
    """ML训练请求"""
    model_type: str = Field(default="xgboost", description="模型类型")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    test_size: float = Field(default=0.2, ge=0.1, le=0.5, description="测试集比例")
    symbols: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None


class MLTrainResponse(BaseModel):
    """ML训练响应"""
    success: bool
    model_path: str
    training_results: Dict[str, Any]
    samples_trained: int
    symbols_count: int


class MLPredictRequest(BaseModel):
    """ML预测请求"""
    model_type: str = Field(default="xgboost", description="模型类型")
    symbols: List[str] = Field(..., min_length=1, description="股票代码列表")
    version: str = Field(default="latest", description="模型版本")


class MLPredictResponse(BaseModel):
    """ML预测响应"""
    success: bool
    predictions: List[Dict[str, Any]]
    count: int


class MLModelInfoResponse(BaseModel):
    """ML模型信息响应"""
    model_type: str
    version: str
    created_at: Optional[str] = None
    feature_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class MLFeatureImportanceResponse(BaseModel):
    """ML特征重要性响应"""
    feature_importance: List[Dict[str, Any]]
    count: int
