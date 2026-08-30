"""
QuantSys V2 CLI - Command Pattern Implementation

使用Command模式，CLI通过HTTP调用API。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import argparse
from typing import Optional

from adapters.inbound.cli.http_client import HTTPClient
from adapters.inbound.cli.command_registry import auto_discover_commands
from adapters.inbound.cli.formatters import get_formatter
from infrastructure.config import get_config


def create_parser() -> argparse.ArgumentParser:
    """创建CLI参数解析器"""
    config = get_config()
    
    parser = argparse.ArgumentParser(
        prog='qsv2',
        description='QuantSys V2 统一命令行工具 (Command Pattern)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  qsv2 stock search --q 平安银行
  qsv2 stock info --symbol 000001.SZ
  qsv2 market overview
  qsv2 kline query --symbol 000001.SZ --limit 20
  qsv2 signal latest --limit 10

格式选项:
  --format json    JSON格式（默认）
  --format table   表格格式
  --format compact 简洁格式
        """
    )

    # 全局选项
    parser.add_argument(
        '--api-url',
        default=config.app.quantsys_api_url,
        help=f'API服务地址 (默认: {config.app.quantsys_api_url})'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='请求超时时间（秒，默认30）'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'table', 'compact'],
        default='json',
        help='输出格式 (默认: json)'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        default=True,
        help='美化输出（JSON格式）'
    )

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # ==================== stock.* ====================
    stock_parser = subparsers.add_parser('stock', help='股票查询')
    stock_subs = stock_parser.add_subparsers(dest='action', help='股票操作')

    # stock search
    search_parser = stock_subs.add_parser('search', help='搜索股票')
    search_parser.add_argument('--q', required=True, help='搜索关键词')
    search_parser.add_argument('--limit', type=int, default=20, help='返回数量')

    # stock info
    info_parser = stock_subs.add_parser('info', help='股票信息')
    info_parser.add_argument('--symbol', required=True, help='股票代码')

    # stock list
    list_parser = stock_subs.add_parser('list', help='股票列表')
    list_parser.add_argument('--market', help='市场筛选')
    list_parser.add_argument('--limit', type=int, default=50, help='返回数量')

    # stock quote
    quote_parser = stock_subs.add_parser('quote', help='实时行情')
    quote_parser.add_argument('--symbol', required=True, help='股票代码')

    # stock analysis
    analysis_parser = stock_subs.add_parser('analysis', help='综合分析')
    analysis_parser.add_argument('--symbol', required=True, help='股票代码')

    # ==================== market.* ====================
    market_parser = subparsers.add_parser('market', help='市场查询')
    market_subs = market_parser.add_subparsers(dest='action', help='市场操作')

    # market overview
    market_subs.add_parser('overview', help='市场概览')

    # market index
    index_parser = market_subs.add_parser('index', help='指数行情')
    index_parser.add_argument('--symbol', required=True, help='指数代码')

    # market sector
    market_subs.add_parser('sector', help='板块列表')

    # market status
    market_subs.add_parser('status', help='市场状态')

    # ==================== kline.* ====================
    kline_parser = subparsers.add_parser('kline', help='K线查询')
    kline_subs = kline_parser.add_subparsers(dest='action', help='K线操作')

    # kline query
    kline_query = kline_subs.add_parser('query', help='查询K线')
    kline_query.add_argument('--symbol', required=True, help='股票代码')
    kline_query.add_argument('--start', help='开始日期 (YYYY-MM-DD)')
    kline_query.add_argument('--end', help='结束日期 (YYYY-MM-DD)')
    kline_query.add_argument('--limit', type=int, default=100, help='返回数量')

    # kline latest
    kline_latest = kline_subs.add_parser('latest', help='最新K线')
    kline_latest.add_argument('--symbol', required=True, help='股票代码')
    kline_latest.add_argument('--limit', type=int, default=20, help='返回数量')

    # kline stats
    kline_stats = kline_subs.add_parser('stats', help='K线统计')
    kline_stats.add_argument('--symbol', required=True, help='股票代码')
    kline_stats.add_argument('--start', required=True, help='开始日期')
    kline_stats.add_argument('--end', required=True, help='结束日期')

    # ==================== factor.* ====================
    factor_parser = subparsers.add_parser('factor', help='因子查询')
    factor_subs = factor_parser.add_subparsers(dest='action', help='因子操作')

    # factor latest
    factor_latest = factor_subs.add_parser('latest', help='最新因子')
    factor_latest.add_argument('--symbol', required=True, help='股票代码')

    # factor history
    factor_history = factor_subs.add_parser('history', help='因子历史')
    factor_history.add_argument('--symbol', required=True, help='股票代码')
    factor_history.add_argument('--factor', required=True, help='因子名称')
    factor_history.add_argument('--start', help='开始日期')
    factor_history.add_argument('--end', help='结束日期')

    # factor list
    factor_list = factor_subs.add_parser('list', help='因子列表')
    factor_list.add_argument('--symbol', help='股票代码')

    # factor calculate
    factor_calc = factor_subs.add_parser('calculate', help='计算因子')
    factor_calc.add_argument('--symbol', required=True, help='股票代码')
    factor_calc.add_argument('--factors', required=True, help='因子列表（逗号分隔）')
    factor_calc.add_argument('--start', help='开始日期')
    factor_calc.add_argument('--end', help='结束日期')

    # ==================== signal.* ====================
    signal_parser = subparsers.add_parser('signal', help='信号查询')
    signal_subs = signal_parser.add_subparsers(dest='action', help='信号操作')

    # signal query
    signal_query = signal_subs.add_parser('query', help='查询信号')
    signal_query.add_argument('--date', help='日期 (YYYY-MM-DD)')
    signal_query.add_argument('--type', help='信号类型 (buy/sell)')
    signal_query.add_argument('--limit', type=int, default=20, help='返回数量')

    # signal latest
    signal_latest = signal_subs.add_parser('latest', help='最新信号')
    signal_latest.add_argument('--limit', type=int, default=10, help='返回数量')

    # signal stats
    signal_stats = signal_subs.add_parser('stats', help='信号统计')
    signal_stats.add_argument('--start', required=True, help='开始日期')
    signal_stats.add_argument('--end', required=True, help='结束日期')

    # ==================== strategy.* ====================
    strategy_parser = subparsers.add_parser('strategy', help='策略管理')
    strategy_subs = strategy_parser.add_subparsers(dest='action', help='策略操作')

    # strategy create
    strategy_create = strategy_subs.add_parser('create', help='创建用户自定义策略')
    strategy_create.add_argument('--name', required=True, help='策略名称')
    strategy_create.add_argument('--code', '--code-file', dest='code', required=True, help='策略代码或代码文件路径')
    strategy_create.add_argument('--type', default='indicator', choices=['indicator', 'script'], help='策略类型（默认: indicator）')
    strategy_create.add_argument('--description', default='', help='策略描述')
    strategy_create.add_argument('--params', help='策略参数JSON')

    # strategy backtest
    strategy_backtest = strategy_subs.add_parser('backtest', help='回测策略')
    strategy_backtest.add_argument('--strategy-id', '--id', dest='strategy_id', required=True, help='策略ID')
    strategy_backtest.add_argument('--symbol', required=True, help='股票代码')
    strategy_backtest.add_argument('--start', required=True, help='开始日期')
    strategy_backtest.add_argument('--end', required=True, help='结束日期')
    strategy_backtest.add_argument('--initial-cash', type=float, default=1000000, help='初始资金')

    # strategy run
    strategy_run = strategy_subs.add_parser('run', help='运行策略生成实时信号')
    strategy_run.add_argument('--strategy-id', '--id', dest='strategy_id', required=True, help='策略ID')
    strategy_run.add_argument('--symbol', required=True, help='股票代码')
    strategy_run.add_argument('--limit', type=int, default=100, help='K线数量')

    # strategy list
    strategy_list = strategy_subs.add_parser('list', help='列出所有策略')
    strategy_list.add_argument('--type', choices=['indicator', 'script'], help='策略类型')
    strategy_list.add_argument('--active-only', action='store_true', help='仅显示启用策略')

    # strategy get
    strategy_get = strategy_subs.add_parser('get', help='获取策略详情')
    strategy_get.add_argument('--id', required=True, help='策略ID')

    # strategy update
    strategy_update = strategy_subs.add_parser('update', help='更新策略')
    strategy_update.add_argument('--id', required=True, help='策略ID')
    strategy_update.add_argument('--name', help='策略名称')
    strategy_update.add_argument('--code', '--code-file', dest='code', help='策略代码或代码文件路径')
    strategy_update.add_argument('--type', choices=['indicator', 'script'], help='策略类型')
    strategy_update.add_argument('--description', help='策略描述')
    strategy_update.add_argument('--params', help='策略参数JSON')
    strategy_update.add_argument('--active', help='是否启用 true/false')

    # strategy delete
    strategy_delete = strategy_subs.add_parser('delete', help='删除策略')
    strategy_delete.add_argument('--id', required=True, help='策略ID')

    # strategy optimize (v2 重写)
    strategy_optimize = strategy_subs.add_parser('optimize', help='优化策略参数（真实回测）')
    strategy_optimize.add_argument('--strategy-id', dest='strategy_id', required=True, type=int, help='策略ID')
    strategy_optimize.add_argument('--symbol', required=True, help='股票代码')
    strategy_optimize.add_argument('--start-date', dest='start_date', default='2025-01-01', help='开始日期（默认: 2025-01-01）')
    strategy_optimize.add_argument('--end-date', dest='end_date', default='2025-12-31', help='结束日期（默认: 2025-12-31）')
    strategy_optimize.add_argument('--metric', choices=['sharpe', 'return', 'win_rate', 'calmar'], default='sharpe', help='评估指标（默认: sharpe）')
    strategy_optimize.add_argument('--param-grid', dest='param_grid', required=True, help='参数网格JSON，如 \'{"rsi_low": [25, 30], "rsi_high": [70, 75]}\'')
    strategy_optimize.add_argument('--initial-capital', dest='initial_capital', type=float, default=1000000, help='初始资金（默认: 1000000）')
    strategy_optimize.add_argument('--max-combinations', dest='max_combinations', type=int, help='最大参数组合数（默认: 50）')

    # ==================== indicators.* ====================
    indicators_parser = subparsers.add_parser('indicators', help='指标管理')
    indicators_subs = indicators_parser.add_subparsers(dest='action', help='指标操作')

    # indicators list
    indicators_list = indicators_subs.add_parser('list', help='列出所有指标')
    indicators_list.add_argument('--active', type=lambda x: x.lower() in ('true', '1', 'yes'), help='仅显示启用指标 (true/false)')
    indicators_list.add_argument('--page', type=int, help='页码')
    indicators_list.add_argument('--limit', type=int, help='每页数量')

    # indicators create
    indicators_create = indicators_subs.add_parser('create', help='创建新指标')
    indicators_create.add_argument('--name', required=True, help='指标名称')
    indicators_create.add_argument('--code', required=True, help='指标代码或代码文件路径 (.py)')
    indicators_create.add_argument('--description', help='指标描述')
    indicators_create.add_argument('--params', help='指标参数JSON')
    indicators_create.add_argument('--active', type=lambda x: x.lower() in ('true', '1', 'yes'), help='是否启用 (true/false)')

    # indicators update
    indicators_update = indicators_subs.add_parser('update', help='更新指标')
    indicators_update.add_argument('--indicator-id', '--id', dest='indicator_id', required=True, help='指标ID')
    indicators_update.add_argument('--name', help='指标名称')
    indicators_update.add_argument('--code', help='指标代码或代码文件路径 (.py)')
    indicators_update.add_argument('--description', help='指标描述')
    indicators_update.add_argument('--params', help='指标参数JSON')
    indicators_update.add_argument('--active', help='是否启用 (true/false)')

    # indicators run
    indicators_run = indicators_subs.add_parser('run', help='运行指标计算')
    indicators_run.add_argument('--indicator-id', '--id', dest='indicator_id', required=True, help='指标ID')
    indicators_run.add_argument('--symbol', required=True, help='股票代码')
    indicators_run.add_argument('--start-date', dest='start_date', help='开始日期 (YYYY-MM-DD)')
    indicators_run.add_argument('--end-date', dest='end_date', help='结束日期 (YYYY-MM-DD)')
    indicators_run.add_argument('--params', help='运行时参数JSON')

    # indicators backtest
    indicators_backtest = indicators_subs.add_parser('backtest', help='回测指标策略')
    indicators_backtest.add_argument('--indicator-id', '--id', dest='indicator_id', required=True, help='指标ID')
    indicators_backtest.add_argument('--symbol', required=True, help='股票代码')
    indicators_backtest.add_argument('--start-date', dest='start_date', required=True, help='开始日期 (YYYY-MM-DD)')
    indicators_backtest.add_argument('--end-date', dest='end_date', help='结束日期 (YYYY-MM-DD)')
    indicators_backtest.add_argument('--initial-capital', dest='initial_capital', type=float, help='初始资金')
    indicators_backtest.add_argument('--params', help='回测参数JSON')

    return parser


def run():
    """运行CLI"""
    parser = create_parser()
    args = parser.parse_args()

    # 显示帮助
    if not args.command:
        parser.print_help()
        return 0

    # 创建HTTP客户端
    client = HTTPClient(
        base_url=args.api_url,
        timeout=args.timeout
    )

    # 自动发现并注册命令（在健康检查之前，因为有些命令不需要API）
    registry = auto_discover_commands(client)

    # 构建命令名称
    command_name = f"{args.command}.{args.action}"

    # 获取命令
    command = registry.get(command_name)
    if not command:
        print(f"错误: 未知命令 '{command_name}'", file=sys.stderr)
        return 1

    # 健康检查（仅对需要HTTP的命令）
    from adapters.inbound.cli.command_base import HTTPCommand
    if isinstance(command, HTTPCommand):
        if not client.health_check():
            print(f"错误: 无法连接到API服务 ({args.api_url})", file=sys.stderr)
            print("请确保API服务已启动", file=sys.stderr)
            return 1

    try:
        # 准备参数
        params = vars(args).copy()
        # 移除非命令参数
        for key in ['command', 'action', 'api_url', 'timeout', 'format', 'pretty']:
            params.pop(key, None)

        # 特殊处理：factors参数转为列表
        if 'factors' in params and params['factors']:
            params['factors'] = [f.strip() for f in params['factors'].split(',')]

        # 执行命令
        result = command.execute(**params)

        # 格式化输出
        formatter = get_formatter(args.format, pretty=args.pretty)

        if result.success:
            output = formatter.format(result.data)
            print(output)
            return 0
        else:
            print(f"错误: {result.error}", file=sys.stderr)
            if result.warnings:
                for warning in result.warnings:
                    print(f"警告: {warning}", file=sys.stderr)
            return 1

    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"错误: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        client.close()


if __name__ == '__main__':
    sys.exit(run())
