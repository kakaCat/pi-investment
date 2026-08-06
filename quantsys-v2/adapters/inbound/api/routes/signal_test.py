"""
信号测试日志 API 路由

POST  /api/signal-test/record         — 记录信号到测试表
POST  /api/signal-test/verify         — 回扫验证 pending 信号
GET   /api/signal-test/stats          — 获取验证统计
GET   /api/signal-test/performance    — 获取策略表现统计（纸面+实盘）
POST  /api/signal-test/run-strategy   — 对单只股票运行策略并记录信号
"""

from flask import Blueprint, jsonify, request
from datetime import date, datetime

from adapters.inbound.api.shared import handle_api_error, ds
from application.services.signal_test_log import SignalTestLog
from adapters.outbound.repositories import StrategyPerformanceORMRepository

signal_test_bp = Blueprint('signal_test', __name__)
_test_log = SignalTestLog()
_perf_repo = StrategyPerformanceORMRepository()


@signal_test_bp.route('/api/signal-test/record', methods=['POST'])
@handle_api_error
def record_signal():
    """记录单条信号到测试表"""
    data = request.get_json(silent=True) or {}
    required = ['symbol', 'strategy_name', 'action']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'success': False, 'error': f'缺少必需字段: {missing}'}), 400

    record_id = _test_log.record_signal(data)
    return jsonify({'success': True, 'id': record_id})


@signal_test_bp.route('/api/signal-test/record-batch', methods=['POST'])
@handle_api_error
def record_batch():
    """批量记录信号"""
    data = request.get_json(silent=True) or {}
    signals = data.get('signals', [])
    if not signals:
        return jsonify({'success': False, 'error': 'signals 不能为空'}), 400

    count = _test_log.record_batch(signals)
    return jsonify({'success': True, 'recorded': count})


@signal_test_bp.route('/api/signal-test/verify', methods=['POST'])
@handle_api_error
def verify_signals():
    """回扫验证 pending 信号"""
    data = request.get_json(silent=True) or {}
    days_after = data.get('days_after', 5)
    result = _test_log.verify_pending(days_after=days_after)
    return jsonify({'success': True, **result})


@signal_test_bp.route('/api/signal-test/records', methods=['GET'])
@handle_api_error
def get_records():
    """获取信号记录列表（分页）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    strategy = request.args.get('strategy')
    action = request.args.get('action')
    symbol = request.args.get('symbol')
    status = request.args.get('status')
    result = _test_log.get_records(
        page=page, page_size=page_size,
        strategy_name=strategy, action=action,
        symbol=symbol, status=status
    )
    return jsonify({'success': True, **result})


@signal_test_bp.route('/api/signal-test/stats', methods=['GET'])
@handle_api_error
def get_stats():
    """获取信号验证统计"""
    strategy_name = request.args.get('strategy')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result = _test_log.get_stats(strategy_name, start_date, end_date)
    return jsonify({'success': True, **result})


@signal_test_bp.route('/api/signal-test/run-strategy', methods=['POST'])
@handle_api_error
def run_strategy_and_record():
    """
    对指定股票运行多因子波段策略，记录信号。

    请求体:
    {
        "symbol": "000001",
        "strategy": "multi_factor_swing",   // 可选，默认 multi_factor_swing
        "days": 120,                         // K线天数，默认120
    }
    """
    data = request.get_json(silent=True) or {}
    symbol = data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'success': False, 'error': 'symbol 不能为空'}), 400

    strategy_name = data.get('strategy', 'multi_factor_swing')
    days = int(data.get('days', 120))

    # ── 1. 获取 K 线数据 ──
    try:
        from datetime import timedelta
        from adapters.outbound.repositories import KlineORMRepository
        kline_repo = KlineORMRepository()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')  # 多取一些冗余
        klines = kline_repo.get_daily_klines(symbol, start_date, end_date)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'{symbol} 获取K线失败: {e}'
        }), 500

    # get_daily_klines 返回 polars DataFrame：bool(df) 抛 TypeError、
    # klines[-1] 取出 1 行 DataFrame 再 .get 抛 AttributeError——先转 dict 列表
    if hasattr(klines, 'to_dicts'):
        klines = klines.to_dicts()

    if not klines or len(klines) < 30:
        return jsonify({
            'success': False,
            'error': f'{symbol} K线数据不足 ({len(klines) if klines else 0}条)'
        }), 400

    # ── 2. 获取实时价格 ──
    # 用最新K线的收盘价作为 signal_price
    signal_price = float(klines[-1].get('close', 0))
    signal_date = klines[-1].get('trade_date', klines[-1].get('date',
                            datetime.now().strftime('%Y-%m-%d')))

    # ── 3. 获取股票名称 ──
    stock_info = {}
    try:
        from adapters.outbound.repositories import StockORMRepository
        stock_repo = StockORMRepository()
        stock_info = stock_repo.get_by_symbol(symbol) or {}
    except Exception:
        pass
    stock_name = stock_info.get('name', '')

    # ── 4. 获取资金流数据（新增）──
    fund_flow_data = None
    try:
        import sys
        from pathlib import Path
        _V2_ROOT = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        ff_result = get_stock_fund_flow(symbol, days=10)
        if ff_result and isinstance(ff_result, dict):
            fund_flow_data = ff_result.get('data', [])
            if not fund_flow_data and isinstance(ff_result, list):
                fund_flow_data = ff_result
    except Exception:
        pass  # 资金流数据获取失败不影响主流程

    # ── 5. 运行策略 ──
    from domain.quantlib.engine.strategy_factory import StrategyFactory
    if not StrategyFactory._registry:
        StrategyFactory.auto_discover()

    try:
        strategy = StrategyFactory.create(strategy_name)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    try:
        raw_signal = strategy.generate_signal(klines, fund_flow_data=fund_flow_data)
    except Exception as e:
        return jsonify({'success': False, 'error': f'策略执行失败: {e}'}), 500

    # ── 5. 补充信号元数据 ──
    signal = {
        'symbol': symbol,
        'name': stock_name,
        'strategy_name': strategy.name if strategy.name != 'MultiFactorSwingStrategy'
                        else 'multi_factor_swing',
        'signal_date': signal_date,
        'action': raw_signal.get('action', 'hold'),
        'confidence': raw_signal.get('confidence', 0),
        'signal_price': signal_price,
        'entry_price': raw_signal.get('entry_price', signal_price),
        'stop_loss': raw_signal.get('stop_loss_price'),
        'reason': raw_signal.get('reason', ''),
        'details': raw_signal.get('details', {}),
    }

    # ── 7. 记录到测试表 ──
    record_id = None
    if signal['action'] in ('buy', 'sell') and signal['confidence'] > 0.5:
        record_id = _test_log.record_signal(signal)

    return jsonify({
        'success': True,
        'signal': {
            **signal,
            'record_id': record_id,
        },
    })


@signal_test_bp.route('/api/signal-test/performance', methods=['GET'])
@handle_api_error
def get_performance():
    """
    获取策略表现统计（纸面测试 + 实盘）

    查询参数:
        strategy (required): 策略名称
        symbol (optional): 股票代码
        start_date (optional): 开始日期 (YYYY-MM-DD)
        end_date (optional): 结束日期 (YYYY-MM-DD)

    返回:
        {
            "success": true,
            "data": {
                "strategy_name": "ma_cross",
                "symbol": "000001.SH" or null,
                "paper": {
                    "total_trades": 10,
                    "verified_trades": 8,
                    "pending_trades": 2,
                    "avg_pnl_pct": 3.5,
                    "win_rate": 62.5,
                    "max_pnl_pct": 15.2,
                    "min_pnl_pct": -5.3
                },
                "live": {
                    "total_trades": 5,
                    "win_trades": 3,
                    "loss_trades": 2,
                    "avg_pnl_pct": 4.2,
                    "win_rate": 60.0,
                    "avg_holding_days": 5.2
                },
                "combined": {
                    "total_trades": 15,
                    "avg_pnl_pct": 3.8,
                    "win_rate": 61.5
                },
                "date_range": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-05-29"
                }
            }
        }
    """
    # 验证必需参数
    strategy_name = request.args.get('strategy')
    if not strategy_name:
        return jsonify({
            'success': False,
            'error': '缺少必需参数: strategy'
        }), 400

    symbol = request.args.get('symbol')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # 获取纸面测试统计
    paper_stats = _get_paper_stats(strategy_name, symbol, start_date, end_date)

    # 获取实盘统计
    live_stats = _perf_repo.get_statistics(
        strategy_name=strategy_name,
        symbol=symbol,
        source='live'
    )

    # 如果没有实盘数据，返回空统计
    if not live_stats:
        live_stats = {
            'total_trades': 0,
            'win_trades': 0,
            'loss_trades': 0,
            'avg_pnl_pct': 0.0,
            'win_rate': 0.0,
            'avg_holding_days': 0.0
        }

    # 计算综合统计
    combined_stats = _calculate_combined_stats(paper_stats, live_stats)

    result = {
        'strategy_name': strategy_name,
        'symbol': symbol,
        'paper': paper_stats,
        'live': live_stats,
        'combined': combined_stats
    }

    # 添加日期范围信息
    if start_date and end_date:
        result['date_range'] = {
            'start_date': start_date,
            'end_date': end_date
        }

    return jsonify({
        'success': True,
        'data': result
    })


def _get_paper_stats(strategy_name: str, symbol: str = None, start_date: str = None, end_date: str = None):
    """获取纸面测试统计"""
    conn = _test_log._get_conn()
    cursor = conn.cursor()

    # 构建查询条件
    conditions = ["strategy_name = %s"]
    params = [strategy_name]

    if symbol:
        conditions.append("symbol = %s")
        params.append(symbol)

    if start_date:
        conditions.append("signal_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("signal_date <= %s")
        params.append(end_date)

    where_clause = " AND ".join(conditions)

    # 查询统计数据
    query = f"""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END) as verified_trades,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_trades,
            AVG(CASE WHEN status = 'verified' THEN pnl_pct ELSE NULL END) as avg_pnl_pct,
            MAX(CASE WHEN status = 'verified' THEN pnl_pct ELSE NULL END) as max_pnl_pct,
            MIN(CASE WHEN status = 'verified' THEN pnl_pct ELSE NULL END) as min_pnl_pct,
            SUM(CASE WHEN status = 'verified' AND pnl_pct > 0 THEN 1 ELSE 0 END) as win_trades
        FROM {_test_log.TABLE_NAME}
        WHERE {where_clause}
    """

    cursor.execute(query, tuple(params))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result or result[0] == 0:
        return {
            'total_trades': 0,
            'verified_trades': 0,
            'pending_trades': 0,
            'avg_pnl_pct': 0.0,
            'win_rate': 0.0,
            'max_pnl_pct': 0.0,
            'min_pnl_pct': 0.0
        }

    total_trades = result[0]
    verified_trades = result[1]
    pending_trades = result[2]
    avg_pnl_pct = float(result[3]) if result[3] is not None else 0.0
    max_pnl_pct = float(result[4]) if result[4] is not None else 0.0
    min_pnl_pct = float(result[5]) if result[5] is not None else 0.0
    win_trades = result[6]

    win_rate = (win_trades / verified_trades * 100) if verified_trades > 0 else 0.0

    return {
        'total_trades': total_trades,
        'verified_trades': verified_trades,
        'pending_trades': pending_trades,
        'avg_pnl_pct': avg_pnl_pct,
        'win_rate': win_rate,
        'max_pnl_pct': max_pnl_pct,
        'min_pnl_pct': min_pnl_pct
    }


def _calculate_combined_stats(paper_stats: dict, live_stats: dict):
    """计算综合统计"""
    # 综合交易数
    total_trades = paper_stats['verified_trades'] + live_stats['total_trades']

    if total_trades == 0:
        return {
            'total_trades': 0,
            'avg_pnl_pct': 0.0,
            'win_rate': 0.0
        }

    # 加权平均盈亏
    paper_weight = paper_stats['verified_trades']
    live_weight = live_stats['total_trades']

    if paper_weight + live_weight > 0:
        avg_pnl_pct = (
            paper_stats['avg_pnl_pct'] * paper_weight +
            live_stats['avg_pnl_pct'] * live_weight
        ) / (paper_weight + live_weight)
    else:
        avg_pnl_pct = 0.0

    # 综合胜率
    paper_win_trades = paper_stats['verified_trades'] * paper_stats['win_rate'] / 100
    live_win_trades = live_stats.get('win_trades', 0)
    total_win_trades = paper_win_trades + live_win_trades

    win_rate = (total_win_trades / total_trades * 100) if total_trades > 0 else 0.0

    return {
        'total_trades': total_trades,
        'avg_pnl_pct': avg_pnl_pct,
        'win_rate': win_rate
    }
