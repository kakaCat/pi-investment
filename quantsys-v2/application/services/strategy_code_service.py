"""
策略代码服务

负责用户自定义策略的完整生命周期管理：
- 创建、验证、存储策略
- 执行策略生成信号
- 回测策略
- 管理策略状态
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from domain.ports import IKlineRepository, IStrategyRepository
import json
import structlog
import numpy as np
import pandas as pd
from domain.ports.datasource_ports import IDataProviderManager, IFundFlowDataSource

try:
    import talib
except ImportError:
    talib = None

from domain.backtest.engine.indicator_strategy_executor import IndicatorStrategyExecutor
from domain.backtest.engine.script_strategy_executor import ScriptStrategyExecutor
from domain.backtest.engine.code_validator import CodeValidator
from domain.backtest.engine.param_parser import ParamParser
from infrastructure.quantlib.core.config import CHART_KLINE_LIMIT, CHART_KLINE_MAX_LIMIT
from domain.risk.attribution import RiskAttributionCalculator

# 🆕 导入因子计算器（11个类，132个因子）
from domain.factors.library.momentum import MomentumFactors
from domain.factors.library.trend import TrendFactors
from domain.factors.library.volatility import VolatilityFactors
from domain.factors.library.volume import VolumeFactors
from domain.factors.library.moving_average import MovingAverageFactors
from domain.factors.library.reversal import ReversalFactors

# 导入需要 TA-Lib 的因子（可选）
try:
    from domain.factors.library.advanced import AdvancedFactors
    from domain.factors.library.cycle import CycleFactors
    from domain.factors.library.pattern_recognition import PatternRecognitionFactors
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib 未安装，高级因子、周期因子、形态识别因子将不可用")

# 导入其他因子
try:
    from domain.factors.library.other import OtherFactors
    OTHER_FACTORS_AVAILABLE = True
except ImportError as e:
    OTHER_FACTORS_AVAILABLE = False
    logger.warning(f"其他因子导入失败: {e}")
from application.services.sentiment_service import SentimentService

logger = structlog.get_logger(__name__)


def _is_empty_df_or_list(data) -> bool:
    """
    检查数据是否为空（兼容 Polars DataFrame 和 list）

    Args:
        data: Polars DataFrame, pandas DataFrame, list 或其他数据结构

    Returns:
        bool: 数据是否为空
    """
    if data is None:
        return True
    try:
        import polars as pl
        if isinstance(data, pl.DataFrame):
            return data.is_empty()
    except (ImportError, AttributeError):
        pass

    # 对于 list 或其他序列类型
    try:
        return len(data) == 0
    except:
        return not bool(data)


def _get_length(data) -> int:
    """
    获取数据长度（兼容 Polars DataFrame 和 list）

    Args:
        data: Polars DataFrame, pandas DataFrame, list 或其他数据结构

    Returns:
        int: 数据长度
    """
    if data is None:
        return 0
    try:
        return len(data)
    except:
        return 0


class StrategyCodeService:
    """策略代码服务

    P2-3: 支持依赖注入
    """

    def __init__(self, strategy_repo=None, kline_repo=None):
        """初始化策略代码服务

        Args:
            strategy_repo: 策略仓库（可选，用于依赖注入）
            kline_repo: K线仓库（可选，用于依赖注入）
        """
        self.strategy_repo = strategy_repo
        self.kline_repo = kline_repo
        self.indicator_executor = IndicatorStrategyExecutor()
        self.script_executor = ScriptStrategyExecutor()
        self.code_validator = CodeValidator()
        self.param_parser = ParamParser()
        self.attribution_calculator = RiskAttributionCalculator()

        # 数据提供者管理器
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()

        # 初始化资金流服务
        fund_flow_source = FundFlowDataSource()
        self.sentiment_service = SentimentService(fund_flow_source)

        # 🆕 初始化因子计算器
        # 核心因子（6个类别，58个因子）- 始终可用
        self.momentum_factors = MomentumFactors()
        self.trend_factors = TrendFactors()
        self.volatility_factors = VolatilityFactors()
        self.volume_factors = VolumeFactors()
        self.ma_factors = MovingAverageFactors()
        self.reversal_factors = ReversalFactors()

        # 可选因子（4个类别，70个因子）- 需要 TA-Lib
        if TALIB_AVAILABLE:
            self.advanced_factors = AdvancedFactors()
            self.cycle_factors = CycleFactors()
            self.pattern_factors = PatternRecognitionFactors()
        else:
            self.advanced_factors = None
            self.cycle_factors = None
            self.pattern_factors = None

        if OTHER_FACTORS_AVAILABLE:
            self.other_factors = OtherFactors()
        else:
            self.other_factors = None

        # 统计可用因子数量
        base_factors = 58  # 6个核心类
        talib_factors = 47 if TALIB_AVAILABLE else 0  # 高级17 + 周期6 + 形态24
        other_factors = 23 if OTHER_FACTORS_AVAILABLE else 0  # 其他23
        total_factors = base_factors + talib_factors + other_factors

        logger.info(f"因子计算器初始化完成（{total_factors}个因子可用）")

    # ==================== 策略管理 ====================

    def create_strategy(
        self,
        name: str,
        code: str,
        code_type: str,
        params: Optional[Dict] = None,
        description: str = "",
        category: str = "custom",
        is_public: bool = False
    ) -> Dict:
        """
        创建用户自定义策略

        Args:
            name: 策略名称
            code: 策略代码字符串
            code_type: 策略类型 ('indicator' | 'script')
            params: 参数覆盖（可选）
            description: 策略描述
            category: 分类（可选）
            is_public: 是否公开（可选）

        Returns:
            {
                'strategy_id': 123,
                'name': '双均线策略',
                'code_type': 'indicator',
                'validation': {
                    'status': 'valid',
                    'syntax_ok': True,
                    'has_buy_signal': True,
                    'has_sell_signal': True,
                    'params_parsed': [...],
                    'risk_config': {...}
                }
            }
        """
        logger.info(f"创建策略: {name}, 类型: {code_type}")

        # 1. 验证代码类型
        valid_types = ('indicator', 'script', 'trend_following', 'mean_reversion', 'multi_factor')
        if code_type not in valid_types:
            raise ValueError(f"无效的策略类型: {code_type}，必须是以下之一: {', '.join(valid_types)}")

        # 2. 验证代码
        validation_result = self.validate_code(code, code_type)

        if not validation_result['valid']:
            # 验证失败，仍然保存但标记为 invalid
            strategy = self.strategy_repo.create_user_strategy({
                'name': name,
                'code_content': code,
                'code_type': code_type,
                'description': description,
                'category': category,
                'is_public': is_public,
                'validation_status': 'invalid',
                'is_active': False
            })

            # 更新验证错误
            self.strategy_repo.update_validation_status(
                strategy_id=strategy['id'],
                status='invalid',
                errors=validation_result.get('error', '未知错误')
            )

            return {
                'strategy_id': strategy['id'],
                'name': name,
                'code_type': code_type,
                'validation': validation_result
            }

        # 3. 验证成功，保存策略
        strategy = self.strategy_repo.create_user_strategy({
            'name': name,
            'code_content': code,
            'code_type': code_type,
            'description': description or validation_result.get('metadata', {}).get('description', ''),
            'parsed_params': validation_result.get('params', []),
            'risk_config': validation_result.get('risk_config', {}),
            'metadata': validation_result.get('metadata', {}),
            'category': category,
            'is_public': is_public,
            'validation_status': 'valid',
            'is_active': True
        })

        logger.info(f"策略创建成功: ID={strategy['id']}")

        return {
            'strategy_id': strategy['id'],
            'name': name,
            'code_type': code_type,
            'validation': validation_result
        }

    def validate_code(self, code: str, code_type: str) -> Dict:
        """
        验证策略代码

        Args:
            code: 策略代码
            code_type: 策略类型

        Returns:
            {
                'valid': True/False,
                'error': '错误信息',
                'syntax_ok': True,
                'has_buy_signal': True,
                'has_sell_signal': True,
                'params': [...],
                'risk_config': {...},
                'metadata': {...}
            }
        """
        try:
            # 1. 基础安全验证
            self.code_validator.validate(code, code_type)

            # 2. 根据类型进行特定验证
            if code_type == 'indicator':
                result = self._validate_indicator_code(code)
            elif code_type == 'script':
                result = self._validate_script_code(code)
            elif code_type in ('trend_following', 'mean_reversion', 'multi_factor'):
                result = self._validate_template_code(code, code_type)
            else:
                raise ValueError(f"未知的策略类型: {code_type}")

            result['valid'] = True
            return result

        except Exception as e:
            logger.error(f"代码验证失败: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'syntax_ok': False
            }

    def list_strategies(
        self,
        code_type: Optional[str] = None,
        active_only: bool = False
    ) -> List[Dict]:
        """
        列出策略

        Args:
            code_type: 策略类型筛选
            active_only: 是否只返回启用的策略

        Returns:
            策略列表
        """
        if code_type:
            strategies = self.strategy_repo.get_user_strategies(
                code_type=code_type,
                active_only=active_only
            )
        else:
            strategies = self.strategy_repo.get_all(active_only=active_only)

        return strategies

    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """获取策略详情"""
        return self.strategy_repo.get_by_id(strategy_id)

    def _normalize_notebook(self, notebook: Dict) -> Dict:
        """统一策略记事本字段名，兼容 API 入参的 snake_case。"""
        return {
            'pros': notebook.get('pros', ''),
            'cons': notebook.get('cons', ''),
            'observations': notebook.get('observations', ''),
            'nextSteps': notebook.get('nextSteps', notebook.get('next_steps', '')),
        }

    def _coerce_metadata(self, metadata: Any) -> Dict:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        return metadata if isinstance(metadata, dict) else {}

    def update_strategy(
        self,
        strategy_id: int,
        code: Optional[str] = None,
        code_type: Optional[str] = None,
        params: Optional[Dict] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
        category: Optional[str] = None,
        favorite_count: Optional[int] = None,
        is_active: Optional[bool] = None,
        notebook: Optional[Dict] = None,
        strategy_profile: Optional[Dict] = None
    ) -> Dict:
        """
        更新策略

        Args:
            strategy_id: 策略ID
            code: 新的策略代码（可选）
            code_type: 策略类型 ('indicator' | 'script')（可选）
            params: 新的参数（可选）
            name: 策略名称（可选）
            description: 策略描述（可选）
            is_public: 是否公开（可选）
            category: 分类（可选）
            favorite_count: 收藏数（可选）
            is_active: 是否启用（可选）
            notebook: 策略记事本（可选）

        Returns:
            更新后的策略
        """
        strategy = self.strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"策略不存在: {strategy_id}")

        update_data = {}

        # 验证并更新 code_type
        if code_type is not None:
            if code_type not in ('indicator', 'script'):
                raise ValueError(f"无效的策略类型: {code_type}，必须是 'indicator' 或 'script'")
            update_data['code_type'] = code_type

        # 更新基础字段
        if name is not None:
            update_data['strategy_name'] = name
        if description is not None:
            update_data['description'] = description
        if is_public is not None:
            update_data['is_public'] = is_public
        if category is not None:
            update_data['category'] = category
        if favorite_count is not None:
            update_data['favorite_count'] = favorite_count
        if notebook is not None:
            metadata = self._coerce_metadata(strategy.get('metadata') or {})
            update_data['metadata'] = {**metadata, 'notebook': self._normalize_notebook(notebook)}

        # 更新代码
        if code is not None:
            # 使用新的 code_type 或现有的 code_type
            current_code_type = code_type if code_type is not None else strategy['code_type']
            validation_result = self.validate_code(code, current_code_type)
            if not validation_result['valid']:
                raise ValueError(f"代码验证失败: {validation_result.get('error')}")

            update_data['code_content'] = code
            update_data['parsed_params'] = validation_result.get('params', [])
            update_data['risk_config'] = validation_result.get('risk_config', {})
            existing_metadata = self._coerce_metadata(strategy.get('metadata') or {})
            validation_metadata = self._coerce_metadata(validation_result.get('metadata') or {})
            update_data['metadata'] = {**existing_metadata, **validation_metadata}
            update_data['validation_status'] = 'valid'

        # 更新参数
        if params is not None:
            update_data['parsed_params'] = params

        # 更新策略画像
        if strategy_profile is not None:
            existing_profile = self._coerce_metadata(strategy.get('strategy_profile') or {})
            update_data['strategy_profile'] = {**existing_profile, **strategy_profile}

        # 更新状态
        if is_active is not None:
            update_data['is_active'] = is_active

        return self.strategy_repo.update(strategy_id, update_data)

    def delete_strategy(self, strategy_id: int) -> bool:
        """删除策略"""
        return self.strategy_repo.delete(strategy_id)

    # ==================== 辅助验证方法 ====================

    def _validate_indicator_code(self, code: str) -> Dict:
        """验证 IndicatorStrategy 代码"""
        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 提取元数据
        import re
        metadata = {}
        match = re.search(r'my_indicator_name\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['name'] = match.group(1)
        match = re.search(r'my_indicator_description\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['description'] = match.group(1)

        # 检查必需的信号生成
        has_buy = "df['buy']" in code or 'df["buy"]' in code
        has_sell = "df['sell']" in code or 'df["sell"]' in code

        return {
            'syntax_ok': True,
            'has_buy_signal': has_buy,
            'has_sell_signal': has_sell,
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    def _validate_script_code(self, code: str) -> Dict:
        """验证 ScriptStrategy 代码"""
        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 检查必需的函数
        has_on_init = 'def on_init(ctx)' in code or 'def on_init (ctx)' in code
        has_on_bar = 'def on_bar(ctx, bar)' in code or 'def on_bar (ctx, bar)' in code

        if not has_on_init:
            raise ValueError("ScriptStrategy 必须定义 on_init(ctx) 函数")
        if not has_on_bar:
            raise ValueError("ScriptStrategy 必须定义 on_bar(ctx, bar) 函数")

        # 提取元数据
        import re
        metadata = {}
        match = re.search(r'strategy_name\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['name'] = match.group(1)
        match = re.search(r'strategy_description\s*=\s*["\'](.+?)["\']', code)
        if match:
            metadata['description'] = match.group(1)

        return {
            'syntax_ok': True,
            'has_on_init': has_on_init,
            'has_on_bar': has_on_bar,
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    def _validate_template_code(self, code: str, code_type: str) -> Dict:
        """验证模板策略代码（trend_following, mean_reversion, multi_factor）"""
        # 解析参数和配置
        params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 提取元数据
        import re
        metadata = {}
        metadata['template_type'] = code_type

        # 检查必需的信号生成
        has_buy = "df['buy']" in code or 'df["buy"]' in code
        has_sell = "df['sell']" in code or 'df["sell"]' in code

        return {
            'syntax_ok': True,
            'has_buy_signal': has_buy,
            'has_sell_signal': has_sell,
            'params': params,
            'risk_config': risk_config,
            'metadata': metadata
        }

    # ==================== 策略执行 ====================

    def generate_signal(
        self,
        strategy_id: int,
        symbol: str,
        date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        生成交易信号

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            date: 信号日期（可选，默认今天）

        Returns:
            信号字典或 None（无信号）
            {
                'symbol': '600000',
                'strategy_id': 1,
                'strategy_name': '策略名称',
                'signal_type': 'buy' | 'sell' | 'hold',
                'confidence': 0.85,
                'signal_date': '2026-05-27',
                'price': 1680.0,
                'created_at': '2026-05-27T12:00:00'
            }
        """
        from datetime import datetime, timedelta

        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"生成信号: strategy_id={strategy_id}, symbol={symbol}, date={date}")

        # 1. 获取策略
        strategy = self.strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"策略不存在: {strategy_id}")

        # 2. 获取最近的K线数据（用于信号生成，需要足够的历史数据）
        end_date = date
        start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')

        klines = self._get_klines(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if _is_empty_df_or_list(klines) or _get_length(klines) < 20:
            logger.warning(f"K线数据不足: {symbol}, 数量={_get_length(klines)}")
            return None

        # 3. 注入数据
        klines = self._inject_fund_flow(klines, symbol)
        klines = self._inject_financial(klines, symbol)
        klines = self._inject_technical_indicators(klines)

        # 4. 执行策略获取信号
        try:
            if strategy['code_type'] == 'indicator':
                result = self.indicator_executor.execute(
                    code=strategy['code_content'],
                    klines=klines,
                    params=strategy.get('parsed_params')
                )
                df = result.signals
            elif strategy['code_type'] == 'script':
                result = self.script_executor.execute(
                    code=strategy['code_content'],
                    klines=klines,
                    params=strategy.get('parsed_params')
                )
                # 对于 script 类型，从交易记录提取最新信号
                trades = result.get('trades', [])
                if trades:
                    latest_trade = trades[-1]
                    return {
                        'symbol': symbol,
                        'strategy_id': strategy_id,
                        'strategy_name': strategy.get('strategy_name', f'strategy_{strategy_id}'),
                        'signal_type': latest_trade['action'],
                        'confidence': 0.8,
                        'signal_date': date,
                        'price': float(latest_trade['price']),
                        'created_at': datetime.now().isoformat()
                    }
                else:
                    return None
            else:
                raise ValueError(f"未知的策略类型: {strategy['code_type']}")

            # 5. 获取最后一行的信号（indicator 类型）
            from infrastructure.utils.dataframe_utils import is_dataframe_empty
            if is_dataframe_empty(df):
                return None

            last_row = df.iloc[-1]

            # 6. 判断信号类型
            signal_type = 'hold'
            confidence = 0.0

            if 'buy' in df.columns and last_row.get('buy', False):
                signal_type = 'buy'
                confidence = last_row.get('confidence', 0.7)
            elif 'sell' in df.columns and last_row.get('sell', False):
                signal_type = 'sell'
                confidence = last_row.get('confidence', 0.7)

            if signal_type == 'hold':
                return None

            return {
                'symbol': symbol,
                'strategy_id': strategy_id,
                'strategy_name': strategy.get('strategy_name', f'strategy_{strategy_id}'),
                'signal_type': signal_type,
                'confidence': float(confidence),
                'signal_date': date,
                'price': float(last_row.get('close', 0)),
                'created_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"信号生成失败: {e}", exc_info=True)
            return None

    def run_strategy(
        self,
        strategy_id: int,
        symbol: str,
        limit: int = 100,
        chart_limit: Optional[int] = None,
        period: Optional[str] = None
    ) -> Dict:
        """
        运行策略生成实时信号

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            limit: K线数量
            period: K线周期（可选），None=日线, '1min'/'5min'/'15min'/'30min'/'60min'=分钟线

        Returns:
            {
                'symbol': '600000',
                'latest_signal': 'buy',
                'confidence': 0.8,
                'price': 1680.0,
                'date': '2026-05-22',
                'indicators': {...}
            }
        """
        # 1. 获取策略
        strategy = self.strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"策略不存在: {strategy_id}")

        # 2. 运行时重新验证当前代码（而非依赖存储的 validation_status）
        validation = self.validate_code(strategy['code_content'], strategy['code_type'])
        if not validation['valid']:
            raise ValueError(f"代码验证失败: {validation.get('error', '未知错误')}")

        # 3. 获取最新 K 线数据
        klines = self._get_klines(symbol=symbol, limit=limit, period=period)
        if _is_empty_df_or_list(klines):
            raise ValueError(f"未找到股票 {symbol} 的K线数据")

        # 🔧 统一转换为 List[Dict]（polars DataFrame 转为 dicts，下游注入方法只支持 list-of-dict 格式）
        try:
            import polars as pl
            if isinstance(klines, pl.DataFrame):
                klines = klines.to_dicts()
        except ImportError:
            pass

        # 保存原始 K 线列名（注入资金流前），用于后续指示器过滤
        original_kline_cols = set(klines[0].keys()) if klines else set()

        # 3.5. 注入主力资金流向数据到 kline（让策略代码可直接使用）
        klines = self._inject_fund_flow(klines, symbol)

        # 3.6. 注入财务指标数据到 kline（让策略代码可直接使用基本面因子）
        klines = self._inject_financial(klines, symbol)

        # 3.7. 注入技术指标数据到 kline（让策略代码可直接使用技术因子）
        klines = self._inject_technical_indicators(klines)

        # 4. 执行策略
        if strategy['code_type'] == 'indicator':
            result = self.indicator_executor.execute(
                code=strategy['code_content'],
                klines=klines,
                params=strategy.get('parsed_params')
            )

            # 提取最新信号
            df = result.signals
            latest_buy = df['buy'].iloc[-1]
            latest_sell = df['sell'].iloc[-1]

            if latest_buy:
                signal = 'buy'
            elif latest_sell:
                signal = 'sell'
            else:
                signal = 'hold'

            # 原始K线列名（不含资金流注入列），用于过滤指标输出
            kline_cols = original_kline_cols
            signal_cols = {'buy', 'sell'}

            # 准备K线数据（使用配置的图表限制）
            if chart_limit is None:
                chart_limit = CHART_KLINE_LIMIT
            else:
                # 限制在合理范围内
                chart_limit = min(chart_limit, CHART_KLINE_MAX_LIMIT)

            chart_limit = min(chart_limit, len(df))
            kline_data = []
            for i in range(len(df) - chart_limit, len(df)):
                try:
                    row = df.iloc[i]
                    # 验证并转换数据，确保数值有效
                    close_val = float(row.get('close', 0))
                    if close_val <= 0:
                        logger.warning(f"索引 {i} 处收盘价无效: {close_val}，跳过")
                        continue

                    kline_data.append({
                        'date': str(row.get('trade_date', row.get('date', i))),
                        'open': float(row.get('open', close_val)),
                        'high': float(row.get('high', close_val)),
                        'low': float(row.get('low', close_val)),
                        'close': close_val,
                        'volume': float(row.get('volume', 0))
                    })
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"索引 {i} 处K线数据格式错误: {e}，跳过")
                    continue

            # 优化指标序列生成（使用pandas向量化）
            indicator_cols = [col for col in df.columns
                              if col not in kline_cols and col not in signal_cols]
            indicator_df = df[indicator_cols].iloc[-chart_limit:]
            indicator_series = {
                col: indicator_df[col].fillna(value=np.nan).replace({np.nan: None}).tolist()
                for col in indicator_cols
            }
            signal_df = df[list(signal_cols)].iloc[-chart_limit:]
            signal_series = {
                col: signal_df[col].fillna(value=False).astype(bool).tolist()
                for col in signal_cols
                if col in signal_df.columns
            }

            response = {
                'symbol': symbol,
                'latest_signal': signal,
                'confidence': 0.8,
                'price': float(df['close'].iloc[-1]),
                'date': str(df['trade_date'].iloc[-1]) if 'trade_date' in df.columns else str(klines[-1].get('trade_date', '')),
                'indicators': {
                    col: float(df[col].iloc[-1]) if not df[col].iloc[-1] is None else None
                    for col in df.columns
                    if col not in kline_cols and col not in signal_cols
                },
                'kline_data': kline_data,  # 添加K线数据
                'indicator_series': indicator_series,  # 添加指标序列数据（用于在K线图上叠加）
                'signal_series': signal_series  # 添加买卖信号序列（用于在K线图上标注）
            }

        elif strategy['code_type'] == 'script':
            result = self.script_executor.execute(
                code=strategy['code_content'],
                klines=klines,
                params=strategy.get('parsed_params')
            )

            # 从交易记录提取最新信号
            trades = result['trades']
            if trades:
                latest_trade = trades[-1]
                response = {
                    'symbol': symbol,
                    'latest_signal': latest_trade['action'],
                    'confidence': 0.8,
                    'price': latest_trade['price'],
                    'date': latest_trade.get('date', ''),
                    'reason': latest_trade.get('reason', '')
                }
            else:
                response = {
                    'symbol': symbol,
                    'latest_signal': 'hold',
                    'confidence': 0.0,
                    'price': klines[-1]['close'],
                    'date': str(klines[-1].get('trade_date', ''))
                }
        else:
            raise ValueError(f"未知的策略类型: {strategy['code_type']}")

        # 4. 更新最后执行时间
        self.strategy_repo.update_last_executed(strategy_id)

        return response

    def backtest_strategy(
        self,
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_cash: float = 1000000,
        params_override: Optional[Dict] = None,
        period: Optional[str] = None
    ) -> Dict:
        """
        回测策略

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            initial_cash: 初始资金
            params_override: 参数覆盖（用于网格搜索优化）。如果不传，使用策略存储的默认参数。
            period: K线周期（可选），None=日线, '5min'=5分钟线（启用T+1约束）

        Returns:
            {
                'total_return': 0.15,
                'sharpe_ratio': 1.8,
                'max_drawdown': -0.12,
                'win_rate': 0.65,
                'total_trades': 45,
                'trades': [...],
                'equity_curve': [...]
            }
        """
        logger.info(f"开始回测: 策略ID={strategy_id}, 股票={symbol}, 日期={start_date}~{end_date}, period={period}")

        # 1. 获取策略
        strategy = self.strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"策略不存在: {strategy_id}")

        # 2. 运行时重新验证当前代码（而非依赖存储的 validation_status）
        validation = self.validate_code(strategy['code_content'], strategy['code_type'])
        if not validation['valid']:
            raise ValueError(f"代码验证失败: {validation.get('error', '未知错误')}")

        # 3. 获取 K 线数据（支持分钟线）
        klines = self._get_klines(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        min_bars = 20 if not period else 100  # 分钟线需要更多bar来暖机
        # 检测是否为空（支持 Polars DataFrame 和 list）
        try:
            import polars as pl
            is_polars = isinstance(klines, pl.DataFrame)
            if is_polars:
                klines_empty = klines.is_empty()
                klines_len = len(klines)
            else:
                klines_empty = _is_empty_df_or_list(klines)
                klines_len = _get_length(klines)
        except ImportError:
            klines_empty = _is_empty_df_or_list(klines)
            klines_len = _get_length(klines)

        if klines_empty or klines_len < min_bars:
            raise ValueError(f"K线数据不足，至少需要{min_bars}条，实际{klines_len}条")

        # 🔧 统一转换为 List[Dict]（polars DataFrame 转为 dicts，下游注入方法只支持 list-of-dict 格式）
        if is_polars:
            klines = klines.to_dicts()

        logger.info(f"获取到 {len(klines)} 条K线数据")

        # 2.5. 注入主力资金流数据（使策略代码中可引用 main_net_inflow 等列）
        klines = self._inject_fund_flow(klines, symbol)

        # 2.6. 注入财务指标数据（使策略代码中可引用 roe_q, gross_margin_q 等列）
        klines = self._inject_financial(klines, symbol)

        # 2.7. 注入技术指标数据（使策略代码中可引用 rsi, macd, bollinger 等列）
        klines = self._inject_technical_indicators(klines)

        # 2.8. 注入市场过滤器（沪深300 200MA，使策略代码中可引用 csi300_close, csi300_ma200, market_bear）
        # 从已验证的策略配置中读取 bear_filter_enabled（默认 True，即启用过滤器）
        bear_filter_enabled = validation.get('risk_config', {}).get('bear_filter_enabled', True)
        klines = self._inject_market_filter(klines, bear_filter_enabled=bear_filter_enabled)

        # 3. 根据策略类型执行回测
        if strategy['code_type'] == 'indicator':
            backtest_result = self._backtest_indicator_strategy(
                strategy=strategy,
                klines=klines,
                initial_cash=initial_cash,
                params_override=params_override,
                period=period
            )
            logger.info(f"INDICATOR_BT: signals_df rows before backtest, period={period}")
        elif strategy['code_type'] == 'script':
            backtest_result = self._backtest_script_strategy(
                strategy=strategy,
                klines=klines,
                initial_cash=initial_cash,
                params_override=params_override
            )
        else:
            raise ValueError(f"未知的策略类型: {strategy['code_type']}")

        # 4. 更新最后执行时间
        self.strategy_repo.update_last_executed(strategy_id)

        logger.info(f"回测完成: 总收益率={backtest_result['total_return']}, 夏普比率={backtest_result['sharpe_ratio']}")

        return backtest_result

    # ==================== 回测辅助方法 ====================

    def _backtest_indicator_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        initial_cash: float,
        params_override: Optional[Dict] = None,
        period: Optional[str] = None
    ) -> Dict:
        """回测 IndicatorStrategy"""
        # 1. 执行策略生成信号（参数覆盖优先于存储参数）
        effective_params = params_override if params_override is not None else strategy.get('parsed_params')
        result = self.indicator_executor.execute(
            code=strategy['code_content'],
            klines=klines,
            params=effective_params
        )

        # 2. 从信号运行回测
        logger.info(f"INDICATOR_BT: signals_df shape={result.signals.shape}, period={period}")
        return self._run_backtest_from_signals(
            signals_df=result.signals,
            risk_config=result.risk_config,
            initial_cash=initial_cash,
            period=period
        )

    def _backtest_script_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        initial_cash: float,
        params_override: Optional[Dict] = None
    ) -> Dict:
        """回测 ScriptStrategy"""
        # 1. 执行策略（直接得到交易记录，参数覆盖优先于存储参数）
        effective_params = params_override if params_override is not None else strategy.get('parsed_params')
        result = self.script_executor.execute(
            code=strategy['code_content'],
            klines=klines,
            params=effective_params,
            initial_cash=initial_cash
        )

        # 2. 计算回测指标
        return self._calculate_metrics_from_trades(
            trades=result['trades'],
            equity_curve=result['equity_curve'],
            initial_cash=initial_cash
        )

    def _run_backtest_from_signals(
        self,
        signals_df,
        risk_config: Dict,
        initial_cash: float,
        period: Optional[str] = None
    ) -> Dict:
        """从信号DataFrame运行回测
        
        委托给 StrategyBacktestService 的统一回测引擎，支持：
        - 分批买入/卖出（buy_tier1/2/3, sell_tier1/2/3）
        - 自定义成交价（buy_tier{N}_price, sell_tier{N}_price）
        - 分钟K线 T+1 约束
        - 向后兼容旧 buy/sell 格式
        """
        from application.services.strategy_backtest_service import StrategyBacktestService
        
        backtest_service = StrategyBacktestService()
        result = backtest_service.run_backtest_from_signals(
            signals_df=signals_df,
            initial_cash=initial_cash,
            period=period
        )
        return result

    def _calculate_metrics_from_trades(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        initial_cash: float
    ) -> Dict:
        """
        从交易记录计算回测指标

        返回指标包括：
        - 基础指标：总收益率、年化收益率、夏普比率、最大回撤
        - 交易指标：胜率、盈亏比、平均持仓天数、交易频率
        - 风险指标：波动率、下行波动率、Calmar比率、Sortino比率
        - 高级指标：最大连续盈利/亏损次数、盈利因子
        """
        if not equity_curve:
            return {
                'total_return': 0,
                'annual_return': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'calmar_ratio': 0,
                'max_drawdown': 0,
                'volatility': 0,
                'downside_volatility': 0,
                'win_rate': 0,
                'profit_loss_ratio': 0,
                'avg_holding_days': 0,
                'trade_frequency': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'profit_factor': 0,
                'total_trades': 0,
                'trades': [],
                'equity_curve': []
            }

        # 提取权益序列
        equities = [e['equity'] for e in equity_curve]
        dates = [e['date'] for e in equity_curve]

        # 计算日收益率
        returns = np.diff(equities) / equities[:-1]

        # ==================== 基础指标 ====================

        # 总收益率
        final_equity = equity_curve[-1]['equity']
        total_return = (final_equity - initial_cash) / initial_cash

        # 年化收益率（假设252个交易日）
        n_days = len(equity_curve)
        n_years = n_days / 252
        annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(equities)

        # ==================== 风险指标 ====================

        # 波动率（年化）
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0

        # 下行波动率（只考虑负收益）
        negative_returns = returns[returns < 0]
        downside_volatility = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0

        # 夏普比率（假设无风险利率为0）
        sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 0 and np.std(returns) > 0 else 0

        # Sortino比率（使用下行波动率）
        sortino_ratio = (np.mean(returns) / np.std(negative_returns) * np.sqrt(252)) if len(negative_returns) > 0 and np.std(negative_returns) > 0 else 0

        # Calmar比率（年化收益率 / 最大回撤）
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # ==================== 交易指标 ====================

        # 胜率
        win_rate = self._calculate_win_rate(trades)

        # 盈亏比、平均持仓天数、连续盈亏
        trade_metrics = self._calculate_trade_metrics(trades, dates)
        profit_loss_ratio = trade_metrics['profit_loss_ratio']
        avg_holding_days = trade_metrics['avg_holding_days']
        max_consecutive_wins = trade_metrics['max_consecutive_wins']
        max_consecutive_losses = trade_metrics['max_consecutive_losses']
        profit_factor = trade_metrics['profit_factor']

        # 交易频率（每年交易次数）
        n_trades = len([t for t in trades if t['action'] == 'buy'])
        trade_frequency = n_trades / n_years if n_years > 0 else 0

        # 配对买卖交易，生成结构化的交易记录
        paired_trades = self._pair_trades(trades)

        return {
            # 基础指标
            'total_return': round(float(total_return), 4),
            'annual_return': round(float(annual_return), 4),
            'sharpe_ratio': round(float(sharpe_ratio), 2),
            'sortino_ratio': round(float(sortino_ratio), 2),
            'calmar_ratio': round(float(calmar_ratio), 2),
            'max_drawdown': round(float(max_drawdown), 4),

            # 风险指标
            'volatility': round(float(volatility), 4),
            'downside_volatility': round(float(downside_volatility), 4),

            # 交易指标
            'win_rate': round(float(win_rate), 2),
            'profit_loss_ratio': round(float(profit_loss_ratio), 2),
            'avg_holding_days': round(float(avg_holding_days), 1),
            'trade_frequency': round(float(trade_frequency), 1),
            'max_consecutive_wins': int(max_consecutive_wins),
            'max_consecutive_losses': int(max_consecutive_losses),
            'profit_factor': round(float(profit_factor), 2),

            # 元数据
            'total_trades': len(paired_trades),
            'trades': paired_trades,
            'equity_curve': equity_curve
        }

    def _calculate_max_drawdown(self, equities: List[float]) -> float:
        """计算最大回撤"""
        peak = equities[0]
        max_dd = 0

        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (equity - peak) / peak
            if dd < max_dd:
                max_dd = dd

        return max_dd

    def _pair_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        将买卖动作配对成完整的交易记录

        Args:
            trades: 原始交易列表，包含 action='buy'/'sell' 的记录

        Returns:
            配对后的交易列表，每条记录包含：
            - entry_date: 买入日期
            - entry_price: 买入价格
            - exit_date: 卖出日期
            - exit_price: 卖出价格
            - return: 收益率
            - pnl: 盈亏金额
            - size: 交易数量
        """
        buy_trades = [t for t in trades if t['action'] == 'buy']
        sell_trades = [t for t in trades if t['action'] == 'sell']

        paired = []
        n_pairs = min(len(buy_trades), len(sell_trades))

        for i in range(n_pairs):
            buy = buy_trades[i]
            sell = sell_trades[i]

            entry_price = buy['price']
            exit_price = sell['price']
            size = buy['size']

            pnl = (exit_price - entry_price) * size
            return_pct = (exit_price / entry_price - 1) if entry_price > 0 else 0

            paired.append({
                'entry_date': buy['date'],
                'entry_price': float(entry_price),
                'exit_date': sell['date'],
                'exit_price': float(exit_price),
                'size': float(size),
                'return': round(float(return_pct), 4),
                'pnl': round(float(pnl), 2),
                'exit_reason': sell.get('reason', 'Unknown')
            })

        return paired

    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """计算胜率"""
        if len(trades) < 2:
            return 0

        buy_trades = [t for t in trades if t['action'] == 'buy']
        sell_trades = [t for t in trades if t['action'] == 'sell']

        wins = 0
        total = min(len(buy_trades), len(sell_trades))

        for i in range(total):
            if sell_trades[i]['price'] > buy_trades[i]['price']:
                wins += 1

        return wins / total if total > 0 else 0

    def _calculate_trade_metrics(self, trades: List[Dict], dates: List[str]) -> Dict:
        """
        计算交易相关指标

        Returns:
            {
                'profit_loss_ratio': 盈亏比（平均盈利/平均亏损）,
                'avg_holding_days': 平均持仓天数,
                'max_consecutive_wins': 最大连续盈利次数,
                'max_consecutive_losses': 最大连续亏损次数,
                'profit_factor': 盈利因子（总盈利/总亏损）
            }
        """
        if len(trades) < 2:
            return {
                'profit_loss_ratio': 0,
                'avg_holding_days': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'profit_factor': 0
            }

        buy_trades = [t for t in trades if t['action'] == 'buy']
        sell_trades = [t for t in trades if t['action'] == 'sell']

        # 配对买卖交易
        n_pairs = min(len(buy_trades), len(sell_trades))

        profits = []
        losses = []
        holding_days_list = []
        consecutive_results = []  # True=盈利, False=亏损

        for i in range(n_pairs):
            buy_price = buy_trades[i]['price']
            sell_price = sell_trades[i]['price']
            pnl = sell_price - buy_price

            # 盈亏分类
            if pnl > 0:
                profits.append(pnl)
                consecutive_results.append(True)
            else:
                losses.append(abs(pnl))
                consecutive_results.append(False)

            # 持仓天数（简化计算：假设日期是连续的）
            try:
                buy_date = buy_trades[i].get('date', '')
                sell_date = sell_trades[i].get('date', '')
                if buy_date and sell_date:
                    # 在 dates 列表中找到索引
                    buy_idx = dates.index(str(buy_date)) if str(buy_date) in dates else -1
                    sell_idx = dates.index(str(sell_date)) if str(sell_date) in dates else -1
                    if buy_idx >= 0 and sell_idx >= 0:
                        holding_days_list.append(sell_idx - buy_idx)
            except (ValueError, IndexError):
                pass

        # 盈亏比
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

        # 平均持仓天数
        avg_holding_days = np.mean(holding_days_list) if holding_days_list else 0

        # 最大连续盈利/亏损次数
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for is_win in consecutive_results:
            if is_win:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        # 盈利因子
        total_profit = sum(profits) if profits else 0
        total_loss = sum(losses) if losses else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        return {
            'profit_loss_ratio': profit_loss_ratio,
            'avg_holding_days': avg_holding_days,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'profit_factor': profit_factor
        }

    def _get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        period: Optional[str] = None
    ) -> List[Dict]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 数量限制（可选）
            period: K线周期（可选），None=日线, '5min'/'15min'/'30min'/'60min'=分钟线

        Returns:
            K线数据列表，分钟线会自动归一化字段名（trade_datetime→trade_date）
        """

        try:
            if period and period in ('1min', '5min', '15min', '30min', '60min'):
                # 分钟K线：从 minute_klines 表获取（仅存储5min，其他周期聚合）
                if start_date and end_date:
                    start_ts = f"{start_date} 00:00:00" if ' ' not in str(start_date) else start_date
                    end_ts = f"{end_date} 23:59:59" if ' ' not in str(end_date) else end_date
                    klines = self.kline_repo.get_minute_klines(
                        symbol=symbol,
                        start_time=start_ts,
                        end_time=end_ts
                    )
                elif limit:
                    klines = self.kline_repo.get_latest_minute_klines(symbol=symbol, limit=limit)
                else:
                    raise ValueError("分钟K线必须指定 start_date/end_date 或 limit")

                # 归一化字段名：trade_datetime → trade_date
                for k in klines:
                    if 'trade_datetime' in k:
                        k['trade_date'] = str(k['trade_datetime'])

                # 聚合到目标周期（1min→5min/15min/30min/60min）
                if period in ('5min', '15min', '30min', '60min') and klines:
                    klines = self._aggregate_minute_klines(klines, period)

                logger.info(f"获取分钟K线 ({period}): {symbol}, {len(klines)} bars")
                return klines
            else:
                # 日K线
                if start_date and end_date:
                    return self.kline_repo.get_range(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif limit:
                    return self.kline_repo.get_latest(
                        symbol=symbol,
                        limit=limit
                    )
                else:
                    raise ValueError("必须指定 start_date/end_date 或 limit")
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            raise

    def _aggregate_minute_klines(
        self,
        klines: List[Dict],
        target_period: str
    ) -> List[Dict]:
        """
        从1分钟K线聚合到5分钟/15分钟/30分钟K线

        Args:
            klines: 1分钟K线列表（按trade_datetime升序）
            target_period: 目标周期 '5min' / '15min' / '30min'

        Returns:
            聚合后的K线列表

        聚合规则：
        - 5min: 5个1min bar → 1个5min bar
        - 15min: 15个1min bar → 1个15min bar
        - 30min: 30个1min bar → 1个30min bar
        - Open = 第一个bar的open, High = max of highs
        - Low = min of lows, Close = 最后一个bar的close
        - Volume = sum of volumes
        - 尊重交易时段边界（午休11:30-13:00, 收盘15:00）
        """
        if _is_empty_df_or_list(klines):
            return klines

        period_map = {'5min': 5, '15min': 15, '30min': 30, '60min': 60}
        bars_per_group = period_map.get(target_period, 15)

        result = []
        current_group = []

        for k in klines:
            dt_str = k.get('trade_date', k.get('trade_datetime', ''))

            # 提取时间部分用于检测交易时段边界
            if ' ' in str(dt_str):
                time_part = str(dt_str).split(' ')[1][:8]
            else:
                time_part = str(dt_str)[-8:]

            # 检测是否应该开始新分组
            should_flush = False
            if current_group:
                prev_dt = str(current_group[-1].get('trade_date', ''))
                prev_time = prev_dt.split(' ')[1][:8] if ' ' in prev_dt else prev_dt[-8:]

                # 跨午休边界（前一根在11:xx, 当前在13:xx）
                if prev_time < '12:00:00' and time_part >= '13:00:00':
                    should_flush = True
                # 跨交易日边界
                elif ' ' in str(dt_str) and ' ' in prev_dt:
                    if str(dt_str).split(' ')[0] != prev_dt.split(' ')[0]:
                        should_flush = True

            # 分组满了也flush
            if len(current_group) >= bars_per_group:
                should_flush = True

            if should_flush and current_group:
                result.append(self._create_aggregated_bar(current_group, target_period))
                current_group = []

            current_group.append(k)

        # 处理最后一组
        if current_group:
            result.append(self._create_aggregated_bar(current_group, target_period))

        logger.debug(f"聚合 {target_period}: {len(klines)}条 1min → {len(result)}条 {target_period}")
        return result

    def _create_aggregated_bar(
        self,
        group: List[Dict],
        period: str
    ) -> Dict:
        """从一组5min bar创建聚合bar"""
        opens = [float(k.get('open') or 0) for k in group]
        highs = [float(k.get('high') or 0) for k in group]
        lows = [float(k.get('low') or 0) for k in group]
        closes = [float(k.get('close') or 0) for k in group]
        volumes = [float(k.get('volume') or 0) for k in group]
        amounts = [float(k.get('amount') or 0) for k in group]

        result = {
            'open': opens[0],
            'high': max(highs),
            'low': min(lows),
            'close': closes[-1],
            'volume': sum(volumes),
            'trade_date': str(group[0].get('trade_date', '')),  # 使用第一根bar的时间
        }

        # 保留额外列（资金流、财务等），使用最后一根bar的值
        skip_cols = {'open', 'high', 'low', 'close', 'volume', 'trade_date', 'trade_datetime'}
        for key in group[-1]:
            if key not in skip_cols:
                result[key] = group[-1][key]

        return result

    def _inject_fund_flow(
        self,
        klines: List[Dict],
        symbol: str
    ) -> List[Dict]:
        """
        注入主力资金流向数据到 kline 列表中

        使策略代码在运行时可以直接使用资金流因子列：
        - main_net_inflow: 主力净流入-净额（元）
        - main_net_pct: 主力净流入-净占比（%）
        - super_large_net: 超大单净流入-净额（元）
        - super_large_pct: 超大单净流入-净占比（%）
        - large_net: 大单净流入-净额（元）
        - large_pct: 大单净流入-净占比（%）

        如果资金流获取失败，所有列值为 NaN（策略代码可自行判断处理）。
        """
        import sys
        import os

        # 字段名映射：中文 → 英文
        COLUMN_MAP = {
            '主力净流入-净额': 'main_net_inflow',
            '主力净流入-净占比': 'main_net_pct',
            '超大单净流入-净额': 'super_large_net',
            '超大单净流入-净占比': 'super_large_pct',
            '大单净流入-净额': 'large_net',
            '大单净流入-净占比': 'large_pct',
        }

        # 初始化所有资金流列为 NaN
        for k in klines:
            for eng_col in COLUMN_MAP.values():
                k[eng_col] = float('nan')

        logger.debug(f"资金流列初始化完成: {symbol}, klines数量={len(klines)}, 列={list(COLUMN_MAP.values())}")

        try:
            # 动态导入（避免对旧 quant 模块的硬依赖）
            quant_path = os.path.join(os.path.dirname(__file__), '..', '..', 'quant')
            quant_path = os.path.abspath(quant_path)
            if quant_path not in sys.path:
                sys.path.insert(0, quant_path)
            # 获取最近 N 天资金流
            # 从最早 K 线日期到今天的天数 + 缓冲，确保覆盖整个回测周期
            from datetime import date as dt_date
            days = max(len(klines), 30)
            if not _is_empty_df_or_list(klines):
                first_date_str = str(klines[0].get('trade_date', klines[0].get('date', ''))).strip()
                first_date_clean = first_date_str.replace('-', '')[:8]
                if len(first_date_clean) == 8:
                    try:
                        first_dt = dt_date(int(first_date_clean[:4]), int(first_date_clean[4:6]), int(first_date_clean[6:8]))
                        days = max((dt_date.today() - first_dt).days + 30, len(klines), 30)
                    except ValueError:
                        pass
            fund_data = self.sentiment_service.get_stock_fund_flow(symbol, days=days)

            if 'error' in fund_data or not fund_data.get('data'):
                logger.debug(f"资金流数据不可用: {symbol} - {fund_data.get('error', 'no data')}")
                return klines

            # 建立 日期→资金流 映射表
            fund_by_date = {}
            for record in fund_data['data']:
                date_str = record.get('日期', '')
                if not date_str:
                    continue
                # 统一日期格式为 YYYY-MM-DD
                normalized_date = str(date_str).strip().replace('-', '')[:8]
                if len(normalized_date) == 8:
                    normalized_date = f"{normalized_date[:4]}-{normalized_date[4:6]}-{normalized_date[6:8]}"
                fund_by_date[normalized_date] = record

            # 匹配 kline 日期与资金流日期
            matched = 0
            for k in klines:
                kline_date = str(k.get('trade_date', k.get('date', ''))).strip()
                # 统一格式
                kline_date_clean = kline_date.replace('-', '')[:8]
                if len(kline_date_clean) == 8:
                    kline_date_clean = f"{kline_date_clean[:4]}-{kline_date_clean[4:6]}-{kline_date_clean[6:8]}"

                fund_record = fund_by_date.get(kline_date_clean)
                if fund_record:
                    for cn_col, eng_col in COLUMN_MAP.items():
                        val = fund_record.get(cn_col)
                        if val is not None:
                            try:
                                k[eng_col] = float(val)
                            except (ValueError, TypeError):
                                pass
                    matched += 1

            logger.debug(f"资金流注入: {symbol} — {matched}/{len(klines)} 天匹配 ({fund_data.get('source', 'unknown')})")

        except ImportError:
            logger.debug(f"资金流模块不可用: {symbol}，跳过注入")
        except Exception as e:
            logger.warning(f"资金流注入失败: {symbol} — {e}，策略将使用 NaN 列运行")

        return klines

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
            income_df = self.provider_manager.call_akshare('stock_financial_report_sina', stock=clean_symbol, symbol='利润表')
            if income_df is not None and not income_df.empty:
                result['income'] = income_df.to_dict(orient='records')
            else:
                result['income'] = []

            # 获取资产负债表
            balance_df = self.provider_manager.call_akshare('stock_financial_report_sina', stock=clean_symbol, symbol='资产负债表')
            if balance_df is not None and not balance_df.empty:
                result['balance'] = balance_df.to_dict(orient='records')
            else:
                result['balance'] = []

            # 获取现金流量表
            cashflow_df = self.provider_manager.call_akshare('stock_financial_report_sina', stock=clean_symbol, symbol='现金流量表')
            if cashflow_df is not None and not cashflow_df.empty:
                result['cashflow'] = cashflow_df.to_dict(orient='records')
            else:
                result['cashflow'] = []

            logger.debug(f"新浪财经获取成功: {symbol}, 利润表={len(result['income'])}条, 资产负债表={len(result['balance'])}条, 现金流量表={len(result['cashflow'])}条")

            return result

        except Exception as e:
            # 检查是否是特殊股票（ST、退市等）
            error_msg = str(e).lower()
            if 'st' in symbol.lower() or any(keyword in error_msg for keyword in ['退市', 'delisted', '暂停', '终止']):
                logger.info(f"特殊股票跳过: {symbol} - 可能是ST股或已退市")
            else:
                logger.warning(f"新浪财经获取失败: {symbol} - {e}")
            return None

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
            df = self.provider_manager.call_akshare('stock_financial_analysis_indicator', symbol=clean_symbol)

            if df is not None and not df.empty:
                result = df.to_dict(orient='records')
                logger.debug(f"东方财富获取成功: {symbol}, {len(result)}条记录")
                return result
            else:
                logger.debug(f"东方财富返回空数据: {symbol}")
                return None

        except Exception as e:
            # 检查是否是特殊股票（ST、退市等）
            error_msg = str(e).lower()
            if 'st' in symbol.lower() or any(keyword in error_msg for keyword in ['退市', 'delisted', '暂停', '终止']):
                logger.info(f"特殊股票跳过: {symbol} - 可能是ST股或已退市")
            else:
                logger.debug(f"东方财富获取失败: {symbol} - {e}")
            return None

    def _calculate_indicators(
        self,
        income: Dict,
        balance: Dict,
        cashflow: Dict,
        prev_income: Optional[Dict] = None
    ) -> Dict:
        """
        从财务报表计算9个财务指标

        Args:
            income: 利润表数据
            balance: 资产负债表数据
            cashflow: 现金流量表数据
            prev_income: 去年同期利润表数据（用于计算增长率）

        Returns:
            {
                'roe': 净资产收益率 (%),
                'gross_margin': 毛利率 (%),
                'net_profit_margin': 销售净利率 (%),
                'debt_ratio': 资产负债率 (%),
                'revenue_growth': 营收增长率 (%),
                'ocf_to_profit': 经营现金流/净利润,
                'current_ratio': 流动比率,
                'roa': 总资产收益率 (%),
                'operating_margin': 营业利润率 (%)
            }
        """
        result = {}

        # 1. ROE (净资产收益率) = 净利润 / 股东权益合计 × 100
        try:
            net_profit = income.get('净利润')
            equity = balance.get('股东权益合计')
            if net_profit is not None and equity is not None and equity != 0:
                result['roe'] = round(float(net_profit) / float(equity) * 100, 2)
            else:
                result['roe'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['roe'] = float('nan')

        # 2. Gross Margin (毛利率) = (营业收入 - 营业成本) / 营业收入 × 100
        try:
            revenue = income.get('营业收入')
            cost = income.get('营业成本')
            if revenue is not None and cost is not None and revenue != 0:
                result['gross_margin'] = round((float(revenue) - float(cost)) / float(revenue) * 100, 2)
            else:
                result['gross_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['gross_margin'] = float('nan')

        # 3. Net Profit Margin (销售净利率) = 净利润 / 营业收入 × 100
        try:
            net_profit = income.get('净利润')
            revenue = income.get('营业收入')
            if net_profit is not None and revenue is not None and revenue != 0:
                result['net_profit_margin'] = round(float(net_profit) / float(revenue) * 100, 2)
            else:
                result['net_profit_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['net_profit_margin'] = float('nan')

        # 4. Debt Ratio (资产负债率) = 负债合计 / 资产总计 × 100
        try:
            liabilities = balance.get('负债合计')
            assets = balance.get('资产总计')
            if liabilities is not None and assets is not None and assets != 0:
                result['debt_ratio'] = round(float(liabilities) / float(assets) * 100, 2)
            else:
                result['debt_ratio'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['debt_ratio'] = float('nan')

        # 5. Revenue Growth (营收增长率) = (本期营收 - 去年同期) / 去年同期 × 100
        try:
            current_revenue = income.get('营业收入')
            prev_revenue = prev_income.get('营业收入') if prev_income else None
            if current_revenue is not None and prev_revenue is not None and prev_revenue != 0:
                result['revenue_growth'] = round((float(current_revenue) - float(prev_revenue)) / float(prev_revenue) * 100, 2)
            else:
                result['revenue_growth'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError, AttributeError):
            result['revenue_growth'] = float('nan')

        # 6. OCF to Profit (经营现金流/净利润) = 经营活动现金流量净额 / 净利润
        try:
            ocf = cashflow.get('经营活动现金流量净额')
            net_profit = income.get('净利润')
            if ocf is not None and net_profit is not None and net_profit != 0:
                result['ocf_to_profit'] = round(float(ocf) / float(net_profit), 2)
            else:
                result['ocf_to_profit'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['ocf_to_profit'] = float('nan')

        # 7. Current Ratio (流动比率) = 流动资产合计 / 流动负债合计
        try:
            current_assets = balance.get('流动资产合计')
            current_liabilities = balance.get('流动负债合计')
            if current_assets is not None and current_liabilities is not None and current_liabilities != 0:
                result['current_ratio'] = round(float(current_assets) / float(current_liabilities), 2)
            else:
                result['current_ratio'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['current_ratio'] = float('nan')

        # 8. ROA (总资产收益率) = 净利润 / 资产总计 × 100
        try:
            net_profit = income.get('净利润')
            assets = balance.get('资产总计')
            if net_profit is not None and assets is not None and assets != 0:
                result['roa'] = round(float(net_profit) / float(assets) * 100, 2)
            else:
                result['roa'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['roa'] = float('nan')

        # 9. Operating Margin (营业利润率) = 营业利润 / 营业收入 × 100
        try:
            operating_profit = income.get('营业利润')
            revenue = income.get('营业收入')
            if operating_profit is not None and revenue is not None and revenue != 0:
                result['operating_margin'] = round(float(operating_profit) / float(revenue) * 100, 2)
            else:
                result['operating_margin'] = float('nan')
        except (ValueError, TypeError, ZeroDivisionError):
            result['operating_margin'] = float('nan')

        return result

    def _forward_fill_to_klines(
        self,
        klines: List[Dict],
        financial_timeline_q: List[Dict],
        financial_timeline_y: List[Dict]
    ) -> List[Dict]:
        """
        将财务指标按公告日期前向填充到K线数据

        Args:
            klines: K线数据列表，每个元素包含 trade_date
            financial_timeline_q: 季度财务指标时间线，每个元素包含 announce_date 和 9 个指标
            financial_timeline_y: 年度财务指标时间线，每个元素包含 announce_date 和 9 个指标

        Returns:
            K线数据列表，每个元素新增 18 个字段：
            - roe_q, gross_margin_q, net_profit_margin_q, debt_ratio_q, revenue_growth_q,
              ocf_to_profit_q, current_ratio_q, roa_q, operating_margin_q
            - roe_y, gross_margin_y, net_profit_margin_y, debt_ratio_y, revenue_growth_y,
              ocf_to_profit_y, current_ratio_y, roa_y, operating_margin_y
        """
        # 定义 9 个指标名称
        indicator_names = [
            'roe', 'gross_margin', 'net_profit_margin', 'debt_ratio', 'revenue_growth',
            'ocf_to_profit', 'current_ratio', 'roa', 'operating_margin'
        ]

        # 初始化所有 K-line 的 18 个字段为 NaN
        for kline in klines:
            for indicator in indicator_names:
                kline[f'{indicator}_q'] = float('nan')
                kline[f'{indicator}_y'] = float('nan')

        # 按公告日期排序时间线（从早到晚）
        financial_timeline_q_sorted = sorted(
            financial_timeline_q,
            key=lambda x: self._normalize_date(x.get('announce_date', ''))
        )
        financial_timeline_y_sorted = sorted(
            financial_timeline_y,
            key=lambda x: self._normalize_date(x.get('announce_date', ''))
        )

        # 对每个 K-line，找到最近的已公告财务数据
        for kline in klines:
            kline_date = self._normalize_date(kline.get('trade_date', ''))

            # 处理季度数据
            latest_q = None
            for report in financial_timeline_q_sorted:
                announce_date = self._normalize_date(report.get('announce_date', ''))
                if announce_date <= kline_date:
                    latest_q = report
                else:
                    break  # 时间线已排序，后续报告都晚于 K-line 日期

            if latest_q:
                for indicator in indicator_names:
                    value = latest_q.get(indicator)
                    kline[f'{indicator}_q'] = value if value is not None else float('nan')

            # 处理年度数据
            latest_y = None
            for report in financial_timeline_y_sorted:
                announce_date = self._normalize_date(report.get('announce_date', ''))
                if announce_date <= kline_date:
                    latest_y = report
                else:
                    break

            if latest_y:
                for indicator in indicator_names:
                    value = latest_y.get(indicator)
                    kline[f'{indicator}_y'] = value if value is not None else float('nan')

        return klines

    def _normalize_date(self, date_input) -> str:
        """
        标准化日期格式为 YYYY-MM-DD

        Args:
            date_input: 日期输入，可以是字符串 ('YYYY-MM-DD' 或 'YYYYMMDD') 或 datetime.date 对象

        Returns:
            标准化后的日期字符串 'YYYY-MM-DD'
        """
        if not date_input:
            return ''

        # 处理 datetime.date 或 datetime.datetime 对象
        from datetime import date, datetime
        if isinstance(date_input, (date, datetime)):
            return date_input.strftime('%Y-%m-%d')

        # 处理字符串
        date_str = str(date_input)

        # 移除所有非数字字符
        date_digits = ''.join(c for c in date_str if c.isdigit())

        # 如果是 8 位数字，转换为 YYYY-MM-DD
        if len(date_digits) == 8:
            return f'{date_digits[0:4]}-{date_digits[4:6]}-{date_digits[6:8]}'

        # 否则返回原字符串
        return date_str

    def _inject_financial(self, klines: List[Dict], symbol: str) -> List[Dict]:
        """
        将财务指标注入到K线数据中（主方法）

        两层降级策略：
        1. 优先使用 Sina Finance（获取原始报表 + 自行计算指标）
        2. 降级到 East Money（使用预计算指标）

        Args:
            klines: K线数据列表，每个元素包含 trade_date
            symbol: 股票代码（如 '600000'）

        Returns:
            K线数据列表，每个元素新增 18 个财务指标字段：
            - 季度指标（_q 后缀）：roe_q, gross_margin_q, net_profit_margin_q, debt_ratio_q,
              revenue_growth_q, ocf_to_profit_q, current_ratio_q, roa_q, operating_margin_q
            - 年度指标（_y 后缀）：roe_y, gross_margin_y, net_profit_margin_y, debt_ratio_y,
              revenue_growth_y, ocf_to_profit_y, current_ratio_y, roa_y, operating_margin_y

        注意：
        - 如果两个数据源都失败，返回的 K-line 中所有财务指标字段为 NaN
        - 财务指标按公告日期前向填充（公告日当天及之后可见）
        """
        logger.info(f"开始注入财务指标: symbol={symbol}, klines_count={len(klines)}")

        # 定义 9 个指标名称
        indicator_names = [
            'roe', 'gross_margin', 'net_profit_margin', 'debt_ratio', 'revenue_growth',
            'ocf_to_profit', 'current_ratio', 'roa', 'operating_margin'
        ]

        # 1. 初始化所有 18 个字段为 NaN
        for kline in klines:
            for indicator in indicator_names:
                kline[f'{indicator}_q'] = float('nan')
                kline[f'{indicator}_y'] = float('nan')

        # 2. 尝试从 Sina Finance 获取数据
        sina_data = self._fetch_from_sina(symbol)

        if sina_data:
            logger.info(f"使用 Sina Finance 数据源: symbol={symbol}")
            try:
                # 3. 从 Sina 原始报表计算指标
                financial_timeline_q = []  # 季度指标时间线
                financial_timeline_y = []  # 年度指标时间线

                # 按报告日期排序（从早到晚）
                income_sorted = sorted(
                    sina_data['income'],
                    key=lambda x: self._normalize_date(x.get('报告日', ''))
                )
                balance_sorted = sorted(
                    sina_data['balance'],
                    key=lambda x: self._normalize_date(x.get('报告日', ''))
                )
                cashflow_sorted = sorted(
                    sina_data['cashflow'],
                    key=lambda x: self._normalize_date(x.get('报告日', ''))
                )

                # 构建报告日期到数据的映射
                income_map = {self._normalize_date(x.get('报告日', '')): x for x in income_sorted}
                balance_map = {self._normalize_date(x.get('报告日', '')): x for x in balance_sorted}
                cashflow_map = {self._normalize_date(x.get('报告日', '')): x for x in cashflow_sorted}

                # 获取所有报告日期（取并集）
                all_report_dates = sorted(set(income_map.keys()) | set(balance_map.keys()) | set(cashflow_map.keys()))

                # 对每个报告日期计算指标
                for i, report_date in enumerate(all_report_dates):
                    income = income_map.get(report_date)
                    balance = balance_map.get(report_date)
                    cashflow = cashflow_map.get(report_date)

                    # 如果三张表都缺失，跳过
                    if not income and not balance and not cashflow:
                        continue

                    # 获取上一期利润表（用于计算同比增长）
                    prev_income = None
                    if i > 0:
                        prev_report_date = all_report_dates[i - 1]
                        prev_income = income_map.get(prev_report_date)

                    # 计算指标
                    indicators = self._calculate_indicators(
                        income or {},
                        balance or {},
                        cashflow or {},
                        prev_income
                    )

                    # 获取公告日期（优先从利润表，其次资产负债表，最后现金流量表）
                    announce_date = None
                    if income and '公告日期' in income:
                        announce_date = self._normalize_date(income['公告日期'])
                    elif balance and '公告日期' in balance:
                        announce_date = self._normalize_date(balance['公告日期'])
                    elif cashflow and '公告日期' in cashflow:
                        announce_date = self._normalize_date(cashflow['公告日期'])

                    if not announce_date:
                        logger.warning(f"报告日期 {report_date} 缺少公告日期，跳过")
                        continue

                    # 判断是季度报告还是年度报告（报告日期的月份）
                    report_month = report_date[5:7] if len(report_date) >= 7 else ''

                    # 构建时间线记录
                    timeline_record = {
                        'announce_date': announce_date,
                        **indicators
                    }

                    if report_month == '12':
                        # 年度报告（12月31日）
                        financial_timeline_y.append(timeline_record)
                    else:
                        # 季度报告（3月31日、6月30日、9月30日）
                        financial_timeline_q.append(timeline_record)

                # 4. 前向填充到 K-line
                klines = self._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)
                logger.info(f"Sina Finance 数据注入成功: symbol={symbol}")
                return klines

            except Exception as e:
                logger.error(f"Sina Finance 数据处理失败: symbol={symbol}, error={e}")
                # 继续尝试 East Money

        # 5. 降级到 East Money
        logger.info(f"尝试 East Money 数据源: symbol={symbol}")
        eastmoney_data = self._fetch_from_eastmoney(symbol)

        if eastmoney_data:
            logger.info(f"使用 East Money 数据源: symbol={symbol}")
            try:
                # 6. East Money 数据已包含预计算指标，直接构建时间线
                financial_timeline_q = []
                financial_timeline_y = []

                # East Money 指标名称映射
                eastmoney_mapping = {
                    'roe': '净资产收益率',
                    'gross_margin': '销售毛利率',
                    'net_profit_margin': '销售净利率',
                    'debt_ratio': '资产负债率',
                    'revenue_growth': '营业总收入同比增长',
                    'ocf_to_profit': None,  # East Money 不提供此指标
                    'current_ratio': '流动比率',
                    'roa': '总资产净利率',
                    'operating_margin': '营业利润率'
                }

                for record in eastmoney_data:
                    # 获取公告日期
                    announce_date = self._normalize_date(record.get('公告日期', ''))
                    if not announce_date:
                        continue

                    # 获取报告期
                    report_date = self._normalize_date(record.get('报告期', ''))
                    if not report_date:
                        continue

                    # 构建指标字典
                    indicators = {}
                    for our_name, em_name in eastmoney_mapping.items():
                        if em_name and em_name in record:
                            indicators[our_name] = record[em_name]
                        else:
                            indicators[our_name] = float('nan')

                    # 判断是季度报告还是年度报告
                    report_month = report_date[5:7] if len(report_date) >= 7 else ''

                    timeline_record = {
                        'announce_date': announce_date,
                        **indicators
                    }

                    if report_month == '12':
                        financial_timeline_y.append(timeline_record)
                    else:
                        financial_timeline_q.append(timeline_record)

                # 7. 前向填充到 K-line
                klines = self._forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y)
                logger.info(f"East Money 数据注入成功: symbol={symbol}")
                return klines

            except Exception as e:
                logger.error(f"East Money 数据处理失败: symbol={symbol}, error={e}")

        # 8. 两个数据源都失败，返回初始化的 K-line（所有指标为 NaN）
        logger.warning(f"所有数据源失败，财务指标保持 NaN: symbol={symbol}")
        return klines

    def _inject_technical_indicators(self, klines: List[Dict]) -> List[Dict]:
        """
        将技术指标注入到K线数据中（增强版 - 使用因子库）

        🆕 使用因子库计算所有128个因子：
        - 动量因子 (16个): RSI、MACD、ROC、Momentum等
        - 趋势因子 (9个): ADX、趋势强度等
        - 波动率因子 (10个): ATR、波动率等
        - 成交量因子 (8个): 成交量指标
        - 移动平均因子 (11个): MA系列
        - 反转因子 (4个): 反转指标
        - 高级因子 (17个): 高级技术指标
        - 周期因子 (6个): 周期性指标
        - 形态识别 (24个): K线形态识别
        - 其他因子 (23个): 其他技术指标

        保持向后兼容：原有13个因子名称不变

        Args:
            klines: K线数据列表

        Returns:
            K线数据列表，包含所有因子字段
        """
        logger.info(f"开始注入技术指标（增强版）: klines_count={len(klines)}")

        if _is_empty_df_or_list(klines) or _get_length(klines) < 2:
            logger.warning("K线数据不足，跳过技术指标计算")
            return klines

        try:
            # 转换为 DataFrame
            df = pd.DataFrame(klines)

            # 验证必需列
            required_cols = ['close', 'high', 'low', 'open', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"缺少必需列 {missing_cols}，跳过技术指标计算")
                return klines

            # 转换为数值类型
            for col in required_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # ============================================================
            # 使用因子库计算所有因子
            # ============================================================

            # 1. 动量因子 (16个)
            df = self._inject_momentum_factors(df, klines)

            # 2. 趋势因子 (9个)
            df = self._inject_trend_factors(df, klines)

            # 3. 波动率因子 (10个)
            df = self._inject_volatility_factors(df, klines)

            # 4. 成交量因子 (8个)
            df = self._inject_volume_factors(df, klines)

            # 5. 移动平均线因子 (11个)
            df = self._inject_ma_factors(df, klines)

            # 6. 反转因子 (4个)
            df = self._inject_reversal_factors(df, klines)

            # 7. 高级因子 (17个)
            df = self._inject_advanced_factors(df, klines)

            # 8. 周期因子 (6个)
            df = self._inject_cycle_factors(df, klines)

            # 9. 形态识别 (24个)
            df = self._inject_pattern_factors(df, klines)

            # 10. 其他因子 (23个)
            df = self._inject_other_factors(df, klines)

            # ============================================================
            # 保持向后兼容：确保原有13个因子名称存在
            # ============================================================
            self._ensure_backward_compatibility(df)

            logger.info(f"技术指标注入完成: 新增 {len([c for c in df.columns if c not in klines[0].keys()])} 个因子列")

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"注入技术指标失败: {e}", exc_info=True)
            return klines

    def _inject_momentum_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入动量因子 - TA-Lib逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        close = df['close'].values.astype(np.float64)
        try:
            # 使用字典收集所有新列，然后一次性合并
            new_cols = {}

            # RSI (6/14/24)
            new_cols['rsi6'] = talib.RSI(close, timeperiod=6)
            new_cols['rsi14'] = talib.RSI(close, timeperiod=14)
            new_cols['rsi24'] = talib.RSI(close, timeperiod=24)

            # MACD
            macd, macd_signal, macd_hist = talib.MACD(close)
            new_cols['macd'] = macd
            new_cols['macd_signal'] = macd_signal
            new_cols['macd_histogram'] = macd_hist

            # ROC (5/10/20)
            new_cols['roc_5'] = talib.ROC(close, timeperiod=5)
            new_cols['roc_10'] = talib.ROC(close, timeperiod=10)
            new_cols['roc_20'] = talib.ROC(close, timeperiod=20)

            # Momentum
            new_cols['momentum_5'] = talib.MOM(close, timeperiod=5)
            new_cols['momentum_10'] = talib.MOM(close, timeperiod=10)
            new_cols['momentum_20'] = talib.MOM(close, timeperiod=20)

            # 6-month momentum: close / close.shift(120) - 1
            new_cols['momentum_6m'] = df['close'] / df['close'].shift(120) - 1

            # 52-week high proximity
            new_cols['momentum_52w_high'] = df['close'] / df['close'].rolling(250).max() - 1

            # Acceleration: 2-day diff of 5-day momentum (depends on momentum_5)
            new_cols['acceleration'] = pd.Series(new_cols['momentum_5']).diff(2).values

            # 批量合并所有新列（避免 DataFrame 碎片化）
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

            logger.debug(f"动量因子注入完成: rsi14 min={df['rsi14'].min():.1f} max={df['rsi14'].max():.1f} last={df['rsi14'].iloc[-1]:.1f}")
        except Exception as e:
            logger.warning(f"计算动量因子失败: {e}")
            nan_cols = ['rsi6', 'rsi14', 'rsi24', 'macd', 'macd_signal', 'macd_histogram',
                        'roc_5', 'roc_10', 'roc_20', 'momentum_5', 'momentum_10', 'momentum_20',
                        'momentum_6m', 'momentum_52w_high', 'acceleration']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_trend_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入趋势因子 - TA-Lib逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        try:
            new_cols = {}

            # ADX
            new_cols['adx'] = talib.ADX(high, low, close, timeperiod=14)

            # ±DI
            new_cols['di_plus'] = talib.PLUS_DI(high, low, close, timeperiod=14)
            new_cols['di_minus'] = talib.MINUS_DI(high, low, close, timeperiod=14)

            # DMI
            new_cols['dmi'] = pd.Series(new_cols['di_plus']).fillna(0).values - pd.Series(new_cols['di_minus']).fillna(0).values

            # CCI
            new_cols['cci'] = talib.CCI(high, low, close, timeperiod=14)

            # Aroon
            aroon_down, aroon_up = talib.AROON(high, low, timeperiod=14)
            new_cols['aroon_up'] = aroon_up
            new_cols['aroon_down'] = aroon_down

            # SAR
            new_cols['sar'] = talib.SAR(high, low, acceleration=0.02, maximum=0.2)

            # 批量合并
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        except Exception as e:
            logger.warning(f"计算趋势因子失败: {e}")
            nan_cols = ['adx', 'di_plus', 'di_minus', 'dmi', 'cci', 'aroon_up', 'aroon_down', 'sar']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_volatility_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入波动率因子 - TA-Lib逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        try:
            new_cols = {}

            # Bollinger Bands (20,2)
            upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
            new_cols['bollinger_upper'] = upper
            new_cols['bollinger_middle'] = middle
            new_cols['bollinger_lower'] = lower

            # ATR (14/20)
            new_cols['atr14'] = talib.ATR(high, low, close, timeperiod=14)
            new_cols['atr20'] = talib.ATR(high, low, close, timeperiod=20)

            # Keltner Channels
            ema20 = talib.EMA(close, timeperiod=20)
            atr10 = talib.ATR(high, low, close, timeperiod=10)
            new_cols['keltner_middle'] = ema20
            new_cols['keltner_upper'] = ema20 + 2 * atr10
            new_cols['keltner_lower'] = ema20 - 2 * atr10

            # Volatility: 20-day std of returns
            returns = df['close'].pct_change()
            new_cols['volatility_20'] = returns.rolling(20).std().values

            # 批量合并
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        except Exception as e:
            logger.warning(f"计算波动率因子失败: {e}")
            nan_cols = ['bollinger_upper', 'bollinger_middle', 'bollinger_lower',
                        'atr14', 'atr20', 'keltner_upper', 'keltner_middle',
                        'keltner_lower', 'volatility_20']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_volume_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入成交量因子 - TA-Lib逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        volume = df['volume'].values.astype(np.float64)
        try:
            new_cols = {}

            # OBV
            new_cols['obv'] = talib.OBV(close, volume)

            # MFI
            new_cols['mfi14'] = talib.MFI(high, low, close, volume, timeperiod=14)

            # VWAP
            typical = (high + low + close) / 3
            cum_pv = np.cumsum(typical * volume)
            cum_vol = np.cumsum(volume)
            new_cols['vwap'] = cum_pv / np.where(cum_vol > 0, cum_vol, 1)

            # Volume MAs
            new_cols['volume_ma5'] = df['volume'].rolling(5).mean().values
            new_cols['volume_ma10'] = df['volume'].rolling(10).mean().values

            # Volume ratio
            volume_ma5_series = pd.Series(new_cols['volume_ma5'])
            new_cols['volume_ratio'] = df['volume'].values / volume_ma5_series.replace(0, np.nan).values

            # 批量合并
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        except Exception as e:
            logger.warning(f"计算成交量因子失败: {e}")
            nan_cols = ['obv', 'mfi14', 'vwap', 'volume_ma5', 'volume_ma10', 'volume_ratio']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_ma_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入移动平均线因子 - pandas rolling逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        close = df['close'].values.astype(np.float64)
        try:
            new_cols = {}

            # SMA
            for period in [5, 10, 20, 60, 120]:
                new_cols[f'ma{period}'] = df['close'].rolling(period).mean().values

            # EMA
            new_cols['ema5'] = talib.EMA(close, timeperiod=5)
            new_cols['ema10'] = talib.EMA(close, timeperiod=10)
            new_cols['ema20'] = talib.EMA(close, timeperiod=20)

            # 批量合并
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        except Exception as e:
            logger.warning(f"计算均线因子失败: {e}")
            nan_cols = ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ema5', 'ema10', 'ema20']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_reversal_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入反转因子 - 逐行序列（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        try:
            new_cols = {}

            # 1-day reversal
            new_cols['reversal_1d'] = df['close'].pct_change().values

            # 5-day reversal
            new_cols['reversal_5d'] = df['close'].pct_change(5).values

            # overnight return
            new_cols['overnight_return'] = ((df['open'] - df['close'].shift(1)) / df['close'].shift(1)).values

            # 批量合并
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        except Exception as e:
            logger.warning(f"计算反转因子失败: {e}")
            nan_cols = ['reversal_1d', 'reversal_5d', 'overnight_return']
            df = pd.concat([df, pd.DataFrame({col: np.nan for col in nan_cols}, index=df.index)], axis=1)
        return df

    def _inject_advanced_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入高级因子 (17个) - 需要 TA-Lib（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        if self.advanced_factors is None:
            logger.debug("高级因子不可用（TA-Lib 未安装）")
            return df
        try:
            supported_methods = self.advanced_factors.get_supported_methods()
            logger.debug(f"计算高级因子: {len(supported_methods)}个")

            new_cols = {}
            for method in supported_methods:
                try:
                    if hasattr(self.advanced_factors, method):
                        result = getattr(self.advanced_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            new_cols[method] = result['value']
                        else:
                            new_cols[method] = result
                    else:
                        logger.warning(f"高级因子方法不存在: {method}")
                        new_cols[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算高级因子 {method} 失败: {e}")
                    new_cols[method] = np.nan

            # 批量合并所有高级因子
            if new_cols:
                df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
            return df
        except Exception as e:
            logger.error(f"注入高级因子失败: {e}")
            return df

    def _inject_cycle_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入周期因子 (6个) - 需要 TA-Lib（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        if self.cycle_factors is None:
            logger.debug("周期因子不可用（TA-Lib 未安装）")
            return df
        try:
            supported_methods = self.cycle_factors.get_supported_methods()
            logger.debug(f"计算周期因子: {len(supported_methods)}个")

            new_cols = {}
            for method in supported_methods:
                try:
                    if hasattr(self.cycle_factors, method):
                        result = getattr(self.cycle_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            new_cols[method] = result['value']
                        else:
                            new_cols[method] = result
                    else:
                        logger.warning(f"周期因子方法不存在: {method}")
                        new_cols[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算周期因子 {method} 失败: {e}")
                    new_cols[method] = np.nan

            # 批量合并所有周期因子
            if new_cols:
                df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
            return df
        except Exception as e:
            logger.error(f"注入周期因子失败: {e}")
            return df

    def _inject_pattern_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入形态识别因子 (24个) - 需要 TA-Lib（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        if self.pattern_factors is None:
            logger.debug("形态识别因子不可用（TA-Lib 未安装）")
            return df
        try:
            supported_methods = self.pattern_factors.get_supported_methods()
            logger.debug(f"计算形态识别因子: {len(supported_methods)}个")

            new_cols = {}
            for method in supported_methods:
                try:
                    if hasattr(self.pattern_factors, method):
                        result = getattr(self.pattern_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            new_cols[method] = result['value']
                        else:
                            new_cols[method] = result
                    else:
                        logger.warning(f"形态识别因子方法不存在: {method}")
                        new_cols[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算形态识别因子 {method} 失败: {e}")
                    new_cols[method] = np.nan

            # 批量合并所有形态识别因子
            if new_cols:
                df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
            return df
        except Exception as e:
            logger.error(f"注入形态识别因子失败: {e}")
            return df

    def _inject_other_factors(self, df: pd.DataFrame, klines: List[Dict]) -> pd.DataFrame:
        """注入其他因子 (23个)（优化：使用 pd.concat 避免 DataFrame 碎片化）"""
        if self.other_factors is None:
            logger.debug("其他因子不可用")
            return df
        try:
            supported_methods = self.other_factors.get_supported_methods()
            logger.debug(f"计算其他因子: {len(supported_methods)}个")

            new_cols = {}
            for method in supported_methods:
                try:
                    if hasattr(self.other_factors, method):
                        result = getattr(self.other_factors, method)(klines)
                        if isinstance(result, dict) and 'value' in result:
                            new_cols[method] = result['value']
                        else:
                            new_cols[method] = result
                    else:
                        logger.warning(f"其他因子方法不存在: {method}")
                        new_cols[method] = np.nan
                except Exception as e:
                    logger.warning(f"计算其他因子 {method} 失败: {e}")
                    new_cols[method] = np.nan

            # 批量合并所有其他因子
            if new_cols:
                df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
            return df
        except Exception as e:
            logger.error(f"注入其他因子失败: {e}")
            return df

    def _ensure_backward_compatibility(self, df: pd.DataFrame) -> None:
        """
        确保向后兼容

        原有13个因子名称必须存在:
        - rsi, macd, macd_signal, macd_hist
        - bollinger_upper, bollinger_middle, bollinger_lower
        - ma5, ma10, ma20, ma60
        - atr
        """
        # RSI映射 (如果因子库叫 rsi14，映射到 rsi)
        if 'rsi14' in df.columns and 'rsi' not in df.columns:
            df['rsi'] = df['rsi14']

        # MACD映射 (macd_histogram → macd_hist)
        if 'macd_histogram' in df.columns and 'macd_hist' not in df.columns:
            df['macd_hist'] = df['macd_histogram']

        # 如果没有MACD，添加NaN列
        if 'macd' not in df.columns:
            df['macd'] = np.nan
            df['macd_signal'] = np.nan
            df['macd_hist'] = np.nan

        # 布林带映射
        if 'bollinger_upper' not in df.columns:
            df['bollinger_upper'] = np.nan
            df['bollinger_middle'] = np.nan
            df['bollinger_lower'] = np.nan

        # MA映射
        for period in [5, 10, 20, 60]:
            col_name = f'ma{period}'
            if col_name not in df.columns:
                df[col_name] = np.nan

        # ATR映射 (atr14 → atr)
        if 'atr14' in df.columns and 'atr' not in df.columns:
            df['atr'] = df['atr14']
        elif 'atr' not in df.columns:
            df['atr'] = np.nan

        logger.debug("向后兼容性检查完成")

    def backtest_portfolio(
        self,
        strategy_ids: List[int],
        symbols: List[str],
        weights: List[float],
        start_date: str,
        end_date: str,
        initial_cash: float = 1000000,
        enable_attribution: bool = True
    ) -> Dict:
        """
        多资产组合回测（带风险归因）

        Args:
            strategy_ids: 策略ID列表（每个资产一个策略）
            symbols: 股票代码列表
            weights: 资产权重列表（必须和为1）
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            enable_attribution: 是否启用风险归因

        Returns:
            {
                'total_return': 总收益率,
                'sharpe_ratio': 夏普比率,
                'max_drawdown': 最大回撤,
                ...其他指标,
                'attribution': {  # 仅当 enable_attribution=True 时
                    'portfolio_volatility': 组合波动率,
                    'contributions': {
                        'symbol1': {
                            'weight': 权重,
                            'volatility': 波动率,
                            'percentage_contribution': 风险贡献百分比,
                            ...
                        },
                        ...
                    }
                }
            }
        """
        logger.info(f"开始组合回测: {len(symbols)}个资产, 日期={start_date}~{end_date}")

        # 验证输入
        if len(strategy_ids) != len(symbols) or len(symbols) != len(weights):
            raise ValueError(f"策略、股票、权重数量必须一致: {len(strategy_ids)}, {len(symbols)}, {len(weights)}")

        if not np.isclose(sum(weights), 1.0, atol=0.01):
            raise ValueError(f"权重必须和为1，当前为 {sum(weights)}")

        # 为每个资产运行回测
        asset_results = []
        asset_returns_matrix = []

        for strategy_id, symbol, weight in zip(strategy_ids, symbols, weights):
            logger.info(f"回测资产: {symbol}, 权重={weight}")

            # 单资产回测
            result = self.backtest_strategy(
                strategy_id=strategy_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash * weight  # 按权重分配资金
            )

            asset_results.append({
                'symbol': symbol,
                'weight': weight,
                'result': result
            })

            # 提取收益率序列（用于归因）
            equity_curve = result['equity_curve']
            equities = [e['equity'] for e in equity_curve]
            returns = np.diff(equities) / equities[:-1]
            asset_returns_matrix.append(returns)

        # 计算组合权益曲线
        portfolio_equity_curve = self._calculate_portfolio_equity(asset_results, initial_cash)

        # 计算组合指标
        portfolio_metrics = self._calculate_metrics_from_trades(
            trades=[],  # 组合层面没有单独的交易记录
            equity_curve=portfolio_equity_curve,
            initial_cash=initial_cash
        )

        # 风险归因（如果启用）
        attribution_result = None
        if enable_attribution and len(asset_returns_matrix) > 1:
            try:
                # 确保所有资产的收益率序列长度一致
                min_length = min(len(r) for r in asset_returns_matrix)
                returns_matrix = np.array([r[:min_length] for r in asset_returns_matrix]).T

                # 计算风险归因
                attribution = self.attribution_calculator.calculate(
                    returns=returns_matrix,
                    weights=weights,
                    asset_names=symbols
                )

                attribution_result = attribution['value']
                logger.info(f"风险归因计算完成: 组合波动率={attribution_result['portfolio_volatility']:.4f}")

            except Exception as e:
                logger.error(f"风险归因计算失败: {e}")
                attribution_result = {'error': str(e)}

        # 组装结果
        result = {
            **portfolio_metrics,
            'assets': asset_results,
            'portfolio_equity_curve': portfolio_equity_curve
        }

        if attribution_result:
            result['attribution'] = attribution_result

        logger.info(f"组合回测完成: 总收益率={result['total_return']}, 夏普比率={result['sharpe_ratio']}")

        return result

    def _calculate_portfolio_equity(
        self,
        asset_results: List[Dict],
        initial_cash: float
    ) -> List[Dict]:
        """
        计算组合权益曲线

        Args:
            asset_results: 各资产回测结果列表
            initial_cash: 初始资金

        Returns:
            组合权益曲线
        """
        # 获取所有日期（取交集，确保所有资产都有数据）
        all_dates = None
        for asset in asset_results:
            equity_curve = asset['result']['equity_curve']
            dates = set(e['date'] for e in equity_curve)
            if all_dates is None:
                all_dates = dates
            else:
                all_dates = all_dates.intersection(dates)

        all_dates = sorted(all_dates)

        # 构建日期到权益的映射
        date_to_equity = {}
        for date in all_dates:
            total_equity = 0
            total_cash = 0

            for asset in asset_results:
                equity_curve = asset['result']['equity_curve']
                # 找到该日期的权益
                for e in equity_curve:
                    if e['date'] == date:
                        total_equity += e['equity']
                        total_cash += e['cash']
                        break

            date_to_equity[date] = {
                'date': date,
                'equity': total_equity,
                'cash': total_cash,
                'position': total_equity - total_cash
            }

        # 转换为列表
        portfolio_equity_curve = [date_to_equity[date] for date in all_dates]

        return portfolio_equity_curve

    def _inject_market_filter(self, klines: List[Dict], bear_filter_enabled: bool = True) -> List[Dict]:
        """
        注入个股自身 200MA 趋势过滤器（替代全局沪深300 200MA 一刀切）

        核心逻辑：
        - 用每只股票自身的 close 计算自身 200MA
        - market_bear = close < own_200MA（个股自身趋势走熊）
        - 这样创业板/科创板股票在自身趋势向上时不会被 CSI300 错杀

        同时注入沪深300 200MA 作为参考列（csi300_close, csi300_ma200），
        策略代码可自行决定是否使用大盘数据。

        Args:
            klines: K线数据列表（需包含 close 字段）
            bear_filter_enabled: 是否启用熊市过滤器（默认 True）。
                策略可通过 @strategy bear_filter_enabled false 关闭。
                超卖反弹策略（mean-reversion）通常在筑底期买入，此时价格必低于 200MA，
                因此应关闭此过滤器。

        Returns:
            K线数据列表，每个元素新增: ma200, market_bear, csi300_close, csi300_ma200
        """
        import json
        import os

        df = pd.DataFrame(klines)

        # ──────────────────────────────────────────────
        # 第一优先级：个股自身 200MA → market_bear
        # ──────────────────────────────────────────────
        if len(df) >= 200:
            df['ma200'] = df['close'].rolling(window=200, min_periods=200).mean()
            # 个股熊市：收盘价 ≤ 自身200MA
            df['market_bear'] = df['close'] <= df['ma200']
            # 前 199 根 bar 没有足够数据，默认允许交易（非熊市）
            df['market_bear'] = df['market_bear'].fillna(value=False)
            bear_count = int(df['market_bear'].sum())
            total = len(df)
            logger.info(
                f"个股200MA过滤器注入: {bear_count}/{total} 根bar标记为个股熊市 "
                f"({bear_count/max(total,1)*100:.1f}%)"
            )
        else:
            df['ma200'] = np.nan
            df['market_bear'] = False
            logger.debug(f"K线数据不足(仅{len(df)}根bar)，跳过个股200MA过滤器")

        # ──────────────────────────────────────────────
        # 尊重策略级别的过滤器开关
        # ──────────────────────────────────────────────
        if not bear_filter_enabled:
            df['market_bear'] = False
            logger.info(f"bear_filter_enabled=False，200MA过滤器已由策略声明关闭")
        # ──────────────────────────────────────────────
        # 第二优先级：沪深300 200MA 作为参考列
        # （策略代码可通过 csi300_close/csi300_ma200 自行使用）
        # ──────────────────────────────────────────────
        df['csi300_close'] = np.nan
        df['csi300_ma200'] = np.nan

        csi300_paths = [
            '/tmp/csi300_data.json',
            os.path.join(os.path.dirname(__file__), '../../.pi-invest/csi300_data.json'),
        ]
        csi300 = None
        for path in csi300_paths:
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        csi300 = json.load(f)
                    break
                except Exception:
                    continue

        if csi300 is not None and len(csi300.get('closes', [])) >= 200:
            csi_dates = csi300['dates']
            csi_closes = csi300['closes']
            csi_close_map = {d: c for d, c in zip(csi_dates, csi_closes)}

            csi_ma_arr = np.convolve(np.array(csi_closes), np.ones(200) / 200, mode='valid')
            csi_ma200_map = {csi_dates[199 + i]: float(val) for i, val in enumerate(csi_ma_arr)}

            matched = 0
            for idx, row in df.iterrows():
                date_str = str(row.get('trade_date', row.get('date', ''))).strip()
                date_clean = date_str.replace('-', '')[:8]
                if len(date_clean) == 8:
                    date_clean = f"{date_clean[:4]}-{date_clean[4:6]}-{date_clean[6:8]}"
                if date_clean in csi_close_map:
                    df.at[idx, 'csi300_close'] = csi_close_map[date_clean]
                    matched += 1
                if date_clean in csi_ma200_map:
                    df.at[idx, 'csi300_ma200'] = csi_ma200_map[date_clean]

            logger.debug(f"沪深300参考数据注入: {matched}/{len(klines)} 天匹配")
        else:
            logger.debug("CSI300数据文件不可用，跳过CSI300参考列注入")

        return df.to_dict('records')
