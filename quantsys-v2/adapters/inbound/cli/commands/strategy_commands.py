"""
Strategy Commands

策略管理相关命令

实现了9个策略管理CLI命令：
1. strategy.create - 创建用户自定义策略（支持文件路径或直接代码）
2. strategy.backtest - 单资产回测（15个指标）
3. strategy.backtest_portfolio - 多资产组合回测（带风险归因）
4. strategy.run - 运行策略生成实时信号
5. strategy.optimize - 优化策略参数（RSI、MA交叉、布林带）
6. strategy.list - 列出所有策略
7. strategy.get - 获取策略详情
8. strategy.update - 更新策略（代码、参数、状态）
9. strategy.delete - 删除策略

所有命令继承自 Command 基类，直接调用 StrategyCodeService 服务层。
支持完整的参数验证、错误处理和类型转换。
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from ..command_base import Command, CommandResult
from application.services.strategy_code_service import StrategyCodeService


class StrategyCreateCommand(Command):
    """创建策略命令"""

    @property
    def name(self) -> str:
        return "strategy.create"

    @property
    def description(self) -> str:
        return "创建用户自定义策略"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('name'):
            return "策略名称不能为空"
        if not kwargs.get('code'):
            return "策略代码不能为空"
        # type 参数可选，默认为 'indicator'
        code_type = kwargs.get('type', 'indicator')
        valid_types = ('indicator', 'script', 'trend_following', 'mean_reversion', 'multi_factor')
        if code_type not in valid_types:
            return f"策略类型必须是以下之一: {', '.join(valid_types)}"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行创建策略命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 解析参数
            name = kwargs.get('name')
            code_input = kwargs.get('code')
            code_type = kwargs.get('type', 'indicator')
            params_str = kwargs.get('params')
            description = kwargs.get('description', '')

            # 读取代码（支持文件路径或直接代码）
            if code_input.endswith('.py'):
                if not os.path.exists(code_input):
                    return CommandResult(
                        success=False,
                        error=f"代码文件不存在: {code_input}"
                    )
                with open(code_input, 'r', encoding='utf-8') as f:
                    code = f.read()
            else:
                code = code_input

            # 解析参数（如果提供）
            params = None
            if params_str:
                try:
                    params = json.loads(params_str)
                except json.JSONDecodeError as e:
                    return CommandResult(
                        success=False,
                        error=f"参数JSON格式错误: {str(e)}"
                    )

            # 调用服务
            service = StrategyCodeService()
            result = service.create_strategy(
                name=name,
                code=code,
                code_type=code_type,
                params=params,
                description=description
            )

            return CommandResult(success=True, data=result)

        except Exception as e:
            return CommandResult(
                success=False,
                error=f"创建策略失败: {str(e)}"
            )


class StrategyBacktestCommand(Command):
    """回测策略命令"""

    @property
    def name(self) -> str:
        return "strategy.backtest"

    @property
    def description(self) -> str:
        return "回测策略"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('strategy_id'):
            return "策略ID不能为空"
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        if not kwargs.get('start'):
            return "开始日期不能为空"
        if not kwargs.get('end'):
            return "结束日期不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行回测命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            strategy_id = int(kwargs.get('strategy_id'))
            symbol = kwargs.get('symbol')
            start_date = kwargs.get('start')
            end_date = kwargs.get('end')
            initial_cash = float(kwargs.get('initial_cash', 1000000))

            # 调用服务
            service = StrategyCodeService()
            result = service.backtest_strategy(
                strategy_id=strategy_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash
            )

            return CommandResult(success=True, data=result)

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"回测失败: {str(e)}"
            )


class StrategyRunCommand(Command):
    """运行策略命令"""

    @property
    def name(self) -> str:
        return "strategy.run"

    @property
    def description(self) -> str:
        return "运行策略生成实时信号"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('strategy_id'):
            return "策略ID不能为空"
        if not kwargs.get('symbol'):
            return "股票代码不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行运行策略命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            strategy_id = int(kwargs.get('strategy_id'))
            symbol = kwargs.get('symbol')
            limit = int(kwargs.get('limit', 100))

            # 调用服务
            service = StrategyCodeService()
            result = service.run_strategy(
                strategy_id=strategy_id,
                symbol=symbol,
                limit=limit
            )

            return CommandResult(success=True, data=result)

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"运行策略失败: {str(e)}"
            )


class StrategyListCommand(Command):
    """列出策略命令"""

    @property
    def name(self) -> str:
        return "strategy.list"

    @property
    def description(self) -> str:
        return "列出所有策略"

    def execute(self, **kwargs) -> CommandResult:
        """执行列出策略命令"""
        try:
            code_type = kwargs.get('type')
            active_only = kwargs.get('active_only', False)

            # 转换字符串为布尔值
            if isinstance(active_only, str):
                active_only = active_only.lower() in ('true', '1', 'yes')

            # 调用服务
            service = StrategyCodeService()
            strategies = service.list_strategies(
                code_type=code_type,
                active_only=active_only
            )

            return CommandResult(
                success=True,
                data={
                    'total': len(strategies),
                    'strategies': strategies
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                error=f"列出策略失败: {str(e)}"
            )


class StrategyGetCommand(Command):
    """获取策略详情命令"""

    @property
    def name(self) -> str:
        return "strategy.get"

    @property
    def description(self) -> str:
        return "获取策略详情"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "策略ID不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行获取策略详情命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            strategy_id = int(kwargs.get('id'))

            # 调用服务
            service = StrategyCodeService()
            strategy = service.get_strategy(strategy_id)

            if not strategy:
                return CommandResult(
                    success=False,
                    error=f"策略不存在: {strategy_id}"
                )

            return CommandResult(success=True, data=strategy)

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"获取策略失败: {str(e)}"
            )


class StrategyUpdateCommand(Command):
    """更新策略命令"""

    @property
    def name(self) -> str:
        return "strategy.update"

    @property
    def description(self) -> str:
        return "更新策略"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "策略ID不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行更新策略命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            strategy_id = int(kwargs.get('id'))
            code_input = kwargs.get('code')
            params_str = kwargs.get('params')
            active_str = kwargs.get('active')
            name = kwargs.get('name')
            description = kwargs.get('description')
            code_type = kwargs.get('type')

            # 验证 code_type（如果提供）
            valid_types = ('indicator', 'script', 'trend_following', 'mean_reversion', 'multi_factor')
            if code_type and code_type not in valid_types:
                return CommandResult(
                    success=False,
                    error=f"策略类型必须是以下之一: {', '.join(valid_types)}"
                )

            # 读取代码（如果提供）
            code = None
            if code_input:
                if code_input.endswith('.py'):
                    if not os.path.exists(code_input):
                        return CommandResult(
                            success=False,
                            error=f"代码文件不存在: {code_input}"
                        )
                    with open(code_input, 'r', encoding='utf-8') as f:
                        code = f.read()
                else:
                    code = code_input

            # 解析参数（如果提供）
            params = None
            if params_str:
                try:
                    params = json.loads(params_str)
                except json.JSONDecodeError as e:
                    return CommandResult(
                        success=False,
                        error=f"参数JSON格式错误: {str(e)}"
                    )

            # 解析active状态（如果提供）
            is_active = None
            if active_str is not None:
                if isinstance(active_str, str):
                    is_active = active_str.lower() in ('true', '1', 'yes')
                else:
                    is_active = bool(active_str)

            # 调用服务
            service = StrategyCodeService()
            result = service.update_strategy(
                strategy_id=strategy_id,
                name=name,
                code=code,
                code_type=code_type,
                description=description,
                params=params,
                is_active=is_active
            )

            return CommandResult(success=True, data=result)

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"更新策略失败: {str(e)}"
            )


class StrategyDeleteCommand(Command):
    """删除策略命令"""

    @property
    def name(self) -> str:
        return "strategy.delete"

    @property
    def description(self) -> str:
        return "删除策略"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('id'):
            return "策略ID不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行删除策略命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            strategy_id = int(kwargs.get('id'))

            # 调用服务
            service = StrategyCodeService()
            success = service.delete_strategy(strategy_id)

            if success:
                return CommandResult(
                    success=True,
                    data={
                        'success': True,
                        'message': f'策略 {strategy_id} 已删除'
                    }
                )
            else:
                return CommandResult(
                    success=False,
                    error=f"删除策略失败: 策略 {strategy_id} 不存在"
                )

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"删除策略失败: {str(e)}"
            )


class StrategyBacktestPortfolioCommand(Command):
    """组合回测命令（带风险归因）"""

    @property
    def name(self) -> str:
        return "strategy.backtest_portfolio"

    @property
    def description(self) -> str:
        return "多资产组合回测（带风险归因）"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('strategy_ids'):
            return "策略ID列表不能为空"
        if not kwargs.get('symbols'):
            return "股票代码列表不能为空"
        if not kwargs.get('weights'):
            return "权重列表不能为空"
        if not kwargs.get('start'):
            return "开始日期不能为空"
        if not kwargs.get('end'):
            return "结束日期不能为空"
        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行组合回测命令"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            # 解析列表参数（支持逗号分隔或JSON）
            strategy_ids_str = kwargs.get('strategy_ids')
            symbols_str = kwargs.get('symbols')
            weights_str = kwargs.get('weights')

            # 解析策略ID列表
            if strategy_ids_str.startswith('['):
                strategy_ids = json.loads(strategy_ids_str)
            else:
                strategy_ids = [int(x.strip()) for x in strategy_ids_str.split(',')]

            # 解析股票代码列表
            if symbols_str.startswith('['):
                symbols = json.loads(symbols_str)
            else:
                symbols = [x.strip() for x in symbols_str.split(',')]

            # 解析权重列表
            if weights_str.startswith('['):
                weights = json.loads(weights_str)
            else:
                weights = [float(x.strip()) for x in weights_str.split(',')]

            # 验证长度一致
            if len(strategy_ids) != len(symbols) or len(symbols) != len(weights):
                return CommandResult(
                    success=False,
                    error=f"策略、股票、权重数量必须一致: {len(strategy_ids)}, {len(symbols)}, {len(weights)}"
                )

            # 验证权重和为1
            import numpy as np
            if not np.isclose(sum(weights), 1.0, atol=0.01):
                return CommandResult(
                    success=False,
                    error=f"权重必须和为1，当前为 {sum(weights)}"
                )

            start_date = kwargs.get('start')
            end_date = kwargs.get('end')
            initial_cash = float(kwargs.get('initial_cash', 1000000))
            enable_attribution = kwargs.get('enable_attribution', 'true').lower() in ('true', '1', 'yes')

            # 调用服务
            service = StrategyCodeService()
            result = service.backtest_portfolio(
                strategy_ids=strategy_ids,
                symbols=symbols,
                weights=weights,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                enable_attribution=enable_attribution
            )

            return CommandResult(success=True, data=result)

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except json.JSONDecodeError as e:
            return CommandResult(
                success=False,
                error=f"JSON格式错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"组合回测失败: {str(e)}"
            )


class StrategyOptimizeCommand(Command):
    """优化策略参数命令（v2 重写 - 调用真实回测 API）"""

    @property
    def name(self) -> str:
        return "strategy.optimize"

    @property
    def description(self) -> str:
        return "优化策略参数（真实回测）"

    def validate_params(self, **kwargs) -> str:
        if not kwargs.get('strategy_id'):
            return "策略ID不能为空（strategy_id）"

        if not kwargs.get('symbol'):
            return "股票代码不能为空（symbol）"

        if not kwargs.get('param_ranges'):
            return "参数范围不能为空（param_ranges）"

        return None

    def execute(self, **kwargs) -> CommandResult:
        """执行优化策略参数命令（调用 v2 API）"""
        # 验证参数
        error = self.validate_params(**kwargs)
        if error:
            return CommandResult(success=False, error=error)

        try:
            from adapters.inbound.cli.http_client import HTTPClient

            # 解析 param_ranges JSON
            param_ranges_str = kwargs.get('param_ranges')
            try:
                param_ranges = json.loads(param_ranges_str)
            except json.JSONDecodeError as e:
                return CommandResult(
                    success=False,
                    error=f"参数范围 JSON 格式错误: {str(e)}"
                )

            # 准备 API 请求参数（使用 camelCase）
            payload = {
                'strategyId': int(kwargs.get('strategy_id')),
                'symbol': kwargs.get('symbol'),
                'startDate': kwargs.get('start_date', '2024-01-01'),
                'endDate': kwargs.get('end_date', '2024-12-31'),
                'paramRanges': param_ranges,
                'initialCash': float(kwargs.get('initial_cash', 1000000)),
            }

            # 可选参数
            if kwargs.get('sort_by'):
                payload['sortBy'] = kwargs.get('sort_by')

            # 调用 v2 API
            client = HTTPClient()
            response = client.post('/api/strategies/optimize', json=payload)

            if response.get('success'):
                return CommandResult(success=True, data=response.get('results'))
            else:
                return CommandResult(
                    success=False,
                    error=response.get('error', '优化失败')
                )

        except ValueError as e:
            return CommandResult(
                success=False,
                error=f"参数错误: {str(e)}"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"优化失败: {str(e)}"
            )


def get_all_commands():
    """获取所有策略命令类"""
    return [
        StrategyCreateCommand,
        StrategyBacktestCommand,
        StrategyBacktestPortfolioCommand,
        StrategyRunCommand,
        StrategyListCommand,
        StrategyGetCommand,
        StrategyUpdateCommand,
        StrategyDeleteCommand,
        StrategyOptimizeCommand,
    ]
