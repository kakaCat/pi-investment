"""
Portfolio optimization API routes
"""
from flask import Blueprint, request, jsonify
from adapters.inbound.api.shared import api_response, handle_api_error
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)
from domain.quantlib.portfolio.markowitz import MarkowitzOptimizer
from domain.quantlib.portfolio.black_litterman import BlackLittermanOptimizer
from domain.quantlib.portfolio.risk_parity import RiskParityOptimizer
import numpy as np

portfolio_bp = Blueprint('portfolio', __name__)


def _convert_numpy_to_list(obj):
    """递归转换 numpy 数组为 Python 列表，以支持 JSON 序列化"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _convert_numpy_to_list(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_to_list(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    else:
        return obj


@portfolio_bp.route('/api/portfolio/markowitz/optimize', methods=['POST'])
@handle_api_error
def markowitz_optimize():
    """Markowitz 均值方差优化"""
    data = request.get_json()

    expected_returns = data.get('expected_returns')
    cov_matrix = data.get('covariance_matrix')
    objective = data.get('method', 'max_sharpe')
    target_return = data.get('target_return')
    risk_free_rate = data.get('risk_free_rate', 0.0)
    lower_bound = data.get('lower_bound', 0.0)
    upper_bound = data.get('upper_bound', 1.0)
    allow_short = data.get('allow_short', False)

    if not expected_returns or not cov_matrix:
        return api_response(None, success=False, message="expected_returns and covariance_matrix are required")

    # 转换为 numpy 数组
    expected_returns = np.array(expected_returns)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = MarkowitzOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective=objective,
        target_return=target_return,
        risk_free_rate=risk_free_rate,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        allow_short=allow_short
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/black-litterman/optimize', methods=['POST'])
@handle_api_error
def black_litterman_optimize():
    """Black-Litterman 模型优化"""
    data = request.get_json()

    market_weights = data.get('market_weights')
    cov_matrix = data.get('covariance_matrix')
    views = data.get('views')
    risk_aversion = data.get('risk_aversion', 2.5)
    tau = data.get('tau', 0.025)
    risk_free_rate = data.get('risk_free_rate', 0.0)

    if not market_weights or not cov_matrix:
        return api_response(None, success=False, message="market_weights and covariance_matrix are required")

    # 转换为 numpy 数组
    market_weights = np.array(market_weights)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = BlackLittermanOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        market_weights=market_weights,
        cov_matrix=cov_matrix,
        views=views,
        risk_aversion=risk_aversion,
        tau=tau,
        risk_free_rate=risk_free_rate
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/risk-parity/optimize', methods=['POST'])
@handle_api_error
def risk_parity_optimize():
    """Risk Parity 风险平价优化"""
    data = request.get_json()

    cov_matrix = data.get('covariance_matrix')
    target_risk = data.get('target_risk')
    target_volatility = data.get('target_volatility')
    lower_bound = data.get('lower_bound', 0.0)
    upper_bound = data.get('upper_bound', 1.0)
    risk_free_rate = data.get('risk_free_rate', 0.0)

    if not cov_matrix:
        return api_response(None, success=False, message="covariance_matrix is required")

    # 转换为 numpy 数组
    cov_matrix = np.array(cov_matrix)
    if target_risk:
        target_risk = np.array(target_risk)

    # 创建优化器
    optimizer = RiskParityOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        cov_matrix=cov_matrix,
        target_risk=target_risk,
        target_volatility=target_volatility,
        lower_bound=lower_bound,
        upper_bound=upper_bound
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/risk-parity/risk-decomposition', methods=['POST'])
@handle_api_error
def risk_parity_decomposition():
    """Risk Parity 风险分解"""
    data = request.get_json()

    weights = data.get('weights')
    cov_matrix = data.get('covariance_matrix')

    if not weights or not cov_matrix:
        return api_response(None, success=False, message="weights and covariance_matrix are required")

    # 转换为 numpy 数组
    weights = np.array(weights)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = RiskParityOptimizer()

    # 计算风险分解
    result = optimizer.calculate_risk_decomposition(
        weights=weights,
        cov_matrix=cov_matrix
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio', methods=['GET'])
@handle_api_error
def get_portfolio():
    """
    获取当前持仓

    Response:
    {
        "success": true,
        "data": {
            "holdings": [...],
            "total_value": 100000.0,
            "total_cost": 90000.0,
            "total_pnl": 10000.0,
            "total_pnl_pct": 0.1111,
            "cash": 50000.0,
            "last_updated": "2026-06-24T15:00:00"
        }
    }
    """
    from pathlib import Path
    import json
    from datetime import datetime

    try:
        # 读取 .pi-invest/portfolio.json
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            # 返回空持仓
            return api_response({
                'holdings': [],
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'cash': 0,
                'last_updated': datetime.now().isoformat()
            })

        # 读取并返回持仓数据
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        return api_response(portfolio_data)

    except Exception as e:
        return api_response(None, success=False, message=f"读取持仓失败: {str(e)}")


@portfolio_bp.route('/api/portfolio/holdings', methods=['GET'])
@handle_api_error
def get_holdings():
    """获取持仓列表"""
    from pathlib import Path
    import json

    try:
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            return api_response([])

        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        return api_response(portfolio_data.get('holdings', []))

    except Exception as e:
        return api_response(None, success=False, message=f"读取持仓失败: {str(e)}")


@portfolio_bp.route('/api/portfolio/stats', methods=['GET'])
@handle_api_error
def get_portfolio_stats():
    """获取持仓统计"""
    from pathlib import Path
    import json

    try:
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            return api_response({
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'position_count': 0,
                'cash': 0
            })

        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        stats = {
            'total_value': portfolio_data.get('total_value', 0),
            'total_cost': portfolio_data.get('total_cost', 0),
            'total_pnl': portfolio_data.get('total_pnl', 0),
            'total_pnl_pct': portfolio_data.get('total_pnl_pct', 0),
            'position_count': len(portfolio_data.get('holdings', [])),
            'cash': portfolio_data.get('cash', 0)
        }

        return api_response(stats)

    except Exception as e:
        return api_response(None, success=False, message=f"读取统计失败: {str(e)}")


# ── 交易时段检测 ───────────────────────────────────────────────
import pytz

CN_TZ = pytz.timezone('Asia/Shanghai')

# A股交易日历（2025-2026 已知节假日休市）
CHINA_HOLIDAYS = {
    date(2025,1,1), date(2025,1,28), date(2025,1,29), date(2025,1,30),
    date(2025,1,31), date(2025,2,3), date(2025,2,4), date(2025,4,4),
    date(2025,4,5), date(2025,4,6), date(2025,5,1), date(2025,5,2),
    date(2025,5,3), date(2025,5,4), date(2025,5,5), date(2025,5,30),
    date(2025,5,31), date(2025,6,1), date(2025,6,2), date(2025,9,21),
    date(2025,9,22), date(2025,10,1), date(2025,10,2), date(2025,10,3),
    date(2025,10,4), date(2025,10,5), date(2025,10,6), date(2025,10,7),
    date(2025,10,8),
    date(2026,1,1), date(2026,1,2), date(2026,1,3),
    date(2026,2,16), date(2026,2,17), date(2026,2,18), date(2026,2,19),
    date(2026,2,20), date(2026,4,3), date(2026,4,4), date(2026,4,5),
    date(2026,4,6), date(2026,5,1), date(2026,5,2), date(2026,5,3),
    date(2026,5,4), date(2026,5,5), date(2026,5,21), date(2026,5,22),
    date(2026,5,23), date(2026,5,24), date(2026,9,25), date(2026,9,26),
    date(2026,9,27), date(2026,10,1), date(2026,10,2), date(2026,10,3),
    date(2026,10,4), date(2026,10,5), date(2026,10,6), date(2026,10,7),
    date(2026,10,8),
}


def is_trading_time():
    """判断当前是否在 A 股交易时段（9:30-11:30, 13:00-15:00, 工作日非节假日）"""
    now = datetime.now(CN_TZ)
    if now.weekday() >= 5:
        return False
    if now.date() in CHINA_HOLIDAYS:
        return False
    t = now.time()
    return (datetime.strptime('09:30','%H:%M').time() <= t <= datetime.strptime('11:30','%H:%M').time() or
            datetime.strptime('13:00','%H:%M').time() <= t <= datetime.strptime('15:00','%H:%M').time())


def next_trading_session():
    """返回最近的下一个交易时段开始时间（北京时间）"""
    from datetime import timedelta
    now = datetime.now(CN_TZ)
    t = now.time()
    today = now.date()
    morning = datetime.strptime('09:30','%H:%M').time()
    afternoon = datetime.strptime('13:00','%H:%M').time()

    # 跳过节假日/周末
    while today in CHINA_HOLIDAYS or today.weekday() >= 5:
        today += timedelta(days=1)

    if t < morning:
        return datetime.combine(today, morning)
    elif t < afternoon:
        return datetime.combine(today, afternoon)
    elif t < datetime.strptime('15:00','%H:%M').time():
        return datetime.combine(today, afternoon)  # still in afternoon session
    else:
        tmr = today + timedelta(days=1)
        while tmr in CHINA_HOLIDAYS or tmr.weekday() >= 5:
            tmr += timedelta(days=1)
        return datetime.combine(tmr, morning)


@portfolio_bp.route('/api/portfolio/trade', methods=['POST'])
def execute_trade():
    """执行虚拟仓交易（买入/卖出）"""
    import psycopg2
    import os
    from datetime import datetime as dt
    
    try:
        data = request.get_json() or {}
        action = data.get('action')
        symbol = data.get('symbol')
        amount = data.get('amount')
        shares = data.get('shares')
        reason = data.get('reason', '')
        
        if not action or not symbol:
            return jsonify({'success': False, 'error': '缺少 action 或 symbol 参数'}), 400
        if action not in ('buy', 'sell'):
            return jsonify({'success': False, 'error': 'action 必须是 buy 或 sell'}), 400
        
        # 获取价格（直接调用 quote API）
        price = None
        clean = symbol.replace('.SH','').replace('.SZ','')
        try:
            import urllib.request as ur, json as jm
            req = ur.Request(f"http://127.0.0.1:5001/api/stock/{clean}/quote")
            with ur.urlopen(req, timeout=5) as resp:
                d = jm.loads(resp.read())
                if d.get('success') and d.get('data'):
                    price = float(d['data'].get('price') or d['data'].get('currentPrice') or 0)
        except Exception as e:
            logger.warning(f"获取价格失败: {e}")
        if not price:
            return jsonify({'success': False, 'error': f'无法获取 {symbol} 价格'}), 500
        
        # 股数和金额
        if shares and int(shares) > 0:
            qty = int(shares)
            amt = qty * price
        elif amount and float(amount) > 0:
            amt = float(amount)
            qty = int(amt / price / 100) * 100
            amt = qty * price
        else:
            return jsonify({'success': False, 'error': '需要 amount 或 shares'}), 400
        if qty <= 0:
            return jsonify({'success': False, 'error': f'金额不足1手，价格={price}'}), 400
        
        comm = max(5.0, amt * 0.00025)
        stamp = amt * 0.001 if action == 'sell' else 0.0
        today = date.today()
        now_cn = datetime.now(CN_TZ)
        in_session = is_trading_time()

        # 数据库
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', '127.0.0.1'),
            port=os.environ.get('PGPORT', '5432'),
            dbname=os.environ.get('PGDATABASE', 'quant_investment'),
            user=os.environ.get('PGUSER', os.environ.get('USER', 'mac')),
            password=os.environ.get('PGPASSWORD', '')
        )
        cur = conn.cursor()

        # ── 非交易时段 → 创建挂单 ──
        if not in_session:
            nxt = next_trading_session()
            act = 'BUY' if action == 'buy' else 'SELL'
            cur.execute(
                "INSERT INTO quant.simulation_trades (account_name,symbol,action,price,filled_price,shares,amount,commission,stamp_duty,trade_date,created_at,execution_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                ('default', symbol, act, price, price, qty, amt, comm, stamp, today, dt.now(), 'pending'))
            oid = cur.fetchone()[0]
            conn.commit(); cur.close(); conn.close()
            return jsonify({
                'success': True,
                'warning': f'⚠️ 当前非交易时段（北京时间 {now_cn.strftime("%H:%M")}），已创建挂单，预计 {nxt.strftime("%m-%d %H:%M")} 执行',
                'data': {
                    'order_id': oid, 'execution_status': 'pending',
                    'action': action, 'symbol': symbol, 'price': price,
                    'shares': qty, 'amount': amt, 'commission': comm,
                    'next_session': nxt.isoformat(), 'reason': reason
                }
            })

        # ── 交易时段 → 直接执行 ──
        # 获取或创建账户
        cur.execute("SELECT cash FROM quant.simulation_account WHERE account_name=%s", ('default',))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO quant.simulation_account (account_name, cash, total_value, peak_value) VALUES (%s,%s,%s,%s) RETURNING cash",
                ('default', 147070.15, 147070.15, 147070.15))
            cash = float(cur.fetchone()[0])
        else:
            cash = float(row[0])

        if action == 'buy':
            cost = amt + comm
            if cash < cost:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({'success': False, 'error': f'资金不足: 需¥{cost:.2f} 有¥{cash:.2f}'}), 400
            new_cash = cash - cost
            cur.execute("UPDATE quant.simulation_account SET cash=%s, total_value=%s, updated_at=%s WHERE account_name=%s",
                       (new_cash, new_cash, dt.now(), 'default'))
            cur.execute("SELECT shares, avg_price FROM quant.simulation_positions WHERE account_name=%s AND symbol=%s",
                       ('default', symbol))
            pr = cur.fetchone()
            if pr:
                os_ = int(pr[0]); oa = float(pr[1])
                na = (oa * os_ + amt) / (os_ + qty); ns = os_ + qty
                cur.execute("UPDATE quant.simulation_positions SET shares=%s,avg_price=%s,market_value=%s,cost=%s,updated_at=%s WHERE account_name=%s AND symbol=%s",
                           (ns, na, ns*price, amt, dt.now(), 'default', symbol))
            else:
                cur.execute("INSERT INTO quant.simulation_positions (account_name,symbol,shares,avg_price,current_price,market_value,cost,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                           ('default', symbol, qty, price, price, amt, amt, dt.now()))
            cur.execute("INSERT INTO quant.simulation_trades (account_name,symbol,action,price,filled_price,shares,amount,commission,stamp_duty,trade_date,created_at,execution_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                       ('default', symbol, 'BUY', price, price, qty, amt, comm, 0, today, dt.now(), 'executed'))
            tid = cur.fetchone()[0]
            conn.commit(); cur.close(); conn.close()
            return jsonify({'success': True, 'data': {'trade_id': tid, 'action': 'buy', 'symbol': symbol,
                'price': price, 'shares': qty, 'amount': amt, 'commission': comm, 'reason': reason}})

        else:  # sell
            cur.execute("SELECT shares FROM quant.simulation_positions WHERE account_name=%s AND symbol=%s", ('default', symbol))
            pr = cur.fetchone()
            if not pr or int(pr[0]) <= 0:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({'success': False, 'error': f'无{symbol}持仓'}), 400
            held = int(pr[0])
            if qty > held:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({'success': False, 'error': f'持仓不足: 需{qty} 有{held}'}), 400
            net = amt - comm - stamp
            new_cash = cash + net
            cur.execute("UPDATE quant.simulation_account SET cash=%s, total_value=%s, updated_at=%s WHERE account_name=%s",
                       (new_cash, new_cash, dt.now(), 'default'))
            rem = held - qty
            if rem > 0:
                cur.execute("UPDATE quant.simulation_positions SET shares=%s,market_value=%s,updated_at=%s WHERE account_name=%s AND symbol=%s",
                           (rem, rem*price, dt.now(), 'default', symbol))
            else:
                cur.execute("DELETE FROM quant.simulation_positions WHERE account_name=%s AND symbol=%s", ('default', symbol))
            cur.execute("INSERT INTO quant.simulation_trades (account_name,symbol,action,price,filled_price,shares,amount,commission,stamp_duty,trade_date,created_at,execution_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                       ('default', symbol, 'SELL', price, price, qty, amt, comm, stamp, today, dt.now(), 'executed'))
            tid = cur.fetchone()[0]
            conn.commit(); cur.close(); conn.close()
            return jsonify({'success': True, 'data': {'trade_id': tid, 'action': 'sell', 'symbol': symbol,
                'price': price, 'shares': qty, 'amount': amt, 'commission': comm, 'stamp_duty': stamp, 'reason': reason}})

    except Exception as e:
        logger.error(f"交易失败: {e}", exc_info=True)
        try: conn.rollback()
        except: pass
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass
        return jsonify({'success': False, 'error': str(e)}), 500


# ── 挂单管理 ─────────────────────────────────────────────────────

@portfolio_bp.route('/api/portfolio/pending-orders', methods=['GET'])
def list_pending_orders():
    """列出所有挂单（execution_status='pending'）"""
    import psycopg2, os
    try:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', '127.0.0.1'),
            port=os.environ.get('PGPORT', '5432'),
            dbname=os.environ.get('PGDATABASE', 'quant_investment'),
            user=os.environ.get('PGUSER', os.environ.get('USER', 'mac')),
            password=os.environ.get('PGPASSWORD', '')
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT id,symbol,action,price,shares,amount,commission,trade_date,created_at "
            "FROM quant.simulation_trades WHERE execution_status='pending' ORDER BY created_at")
        rows = cur.fetchall()
        orders = [{
            'order_id': r[0], 'symbol': r[1], 'action': r[2], 'price': float(r[3]),
            'shares': r[4], 'amount': float(r[5]), 'commission': float(r[6]),
            'trade_date': str(r[7]), 'created_at': str(r[8])
        } for r in rows]
        cur.close(); conn.close()
        return jsonify({'success': True, 'pending_orders': orders, 'count': len(orders)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/api/portfolio/pending-orders/execute', methods=['POST'])
def execute_pending_orders():
    """执行挂单（仅交易时段可用）
    Body: {"order_ids": [1,2,3]} 或 {"order_ids": "all"}
    """
    import psycopg2, os
    if not is_trading_time():
        nxt = next_trading_session()
        return jsonify({'success': False, 'error': f'仅交易时段可执行挂单，下一时段: {nxt.strftime("%m-%d %H:%M")}'}), 400

    try:
        data = request.get_json() or {}
        order_ids = data.get('order_ids')
        if not order_ids:
            return jsonify({'success': False, 'error': '需要 order_ids 参数（"all" 或 [id1,id2]）'}), 400

        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', '127.0.0.1'),
            port=os.environ.get('PGPORT', '5432'),
            dbname=os.environ.get('PGDATABASE', 'quant_investment'),
            user=os.environ.get('PGUSER', os.environ.get('USER', 'mac')),
            password=os.environ.get('PGPASSWORD', '')
        )
        cur = conn.cursor()

        if order_ids == 'all':
            cur.execute("SELECT id,symbol,action,price,shares,amount,commission,stamp_duty FROM quant.simulation_trades WHERE execution_status='pending'")
        else:
            cur.execute("SELECT id,symbol,action,price,shares,amount,commission,stamp_duty FROM quant.simulation_trades WHERE execution_status='pending' AND id = ANY(%s)", (order_ids,))
        pending = cur.fetchall()

        if not pending:
            cur.close(); conn.close()
            return jsonify({'success': True, 'message': '无待执行的挂单', 'executed': 0})

        results = []
        for (oid, sym, act, prc, sh, am, comm, stamp) in pending:
            try:
                # 重新获取最新价格（可能已变化）
                cl = sym.replace('.SH','').replace('.SZ','')
                import urllib.request as ur, json as jm
                req = ur.Request(f"http://127.0.0.1:5001/api/stock/{cl}/quote")
                with ur.urlopen(req, timeout=5) as resp:
                    d = jm.loads(resp.read())
                    if d.get('success') and d.get('data'):
                        lp = float(d['data'].get('price') or prc)
                    else:
                        lp = float(prc)
            except:
                lp = float(prc)

            # 标记为已执行
            cur.execute("UPDATE quant.simulation_trades SET execution_status='executed', filled_price=%s, trade_time=%s WHERE id=%s",
                       (lp, dt.now(), oid))
            results.append({'order_id': oid, 'symbol': sym, 'action': act,
                          'price': float(prc), 'executed_price': lp, 'shares': sh, 'amount': float(am)})

        conn.commit(); cur.close(); conn.close()
        return jsonify({'success': True, 'executed': len(results), 'orders': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/api/portfolio/pending-orders/<int:order_id>/cancel', methods=['POST'])
def cancel_pending_order(order_id):
    """取消挂单"""
    import psycopg2, os
    try:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', '127.0.0.1'),
            port=os.environ.get('PGPORT', '5432'),
            dbname=os.environ.get('PGDATABASE', 'quant_investment'),
            user=os.environ.get('PGUSER', os.environ.get('USER', 'mac')),
            password=os.environ.get('PGPASSWORD', '')
        )
        cur = conn.cursor()
        cur.execute("UPDATE quant.simulation_trades SET execution_status='cancelled' WHERE id=%s AND execution_status='pending' RETURNING id", (order_id,))
        row = cur.fetchone()
        conn.commit(); cur.close(); conn.close()
        if row:
            return jsonify({'success': True, 'message': f'挂单 #{order_id} 已取消'})
        return jsonify({'success': False, 'error': f'挂单 #{order_id} 不存在或已执行'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/api/portfolio/optimize', methods=['POST'])
@handle_api_error
def optimize_portfolio():
    """
    组合优化
    
    使用 cvxpy 进行科学的组合权重优化
    
    Request:
    {
        "symbols": ["600000.SH", "600519.SH", "000858.SZ"],
        "expected_returns": [0.10, 0.15, 0.08],  // 可选，不提供则自动估计
        "method": "mean_variance",  // mean_variance, min_variance, max_sharpe, risk_parity
        "risk_aversion": 1.0,  // 风险厌恶系数
        "risk_free_rate": 0.02,  // 无风险利率
        "constraints": {
            "long_only": true,
            "max_weight": 0.3,
            "min_weight": 0.05
        },
        "start_date": "2024-01-01",  // 用于估计参数
        "end_date": "2024-12-31"
    }
    
    Response:
    {
        "success": true,
        "data": {
            "weights": {
                "600000.SH": 0.35,
                "600519.SH": 0.40,
                "000858.SZ": 0.25
            },
            "expected_return": 0.125,
            "risk": 0.18,
            "sharpe": 0.58,
            "method": "mean_variance"
        }
    }
    """
    from application.services.portfolio_optimization_service import PortfolioOptimizationService
    import numpy as np
    
    data = request.get_json() or {}
    
    # 参数验证
    symbols = data.get('symbols')
    if not symbols:
        return jsonify({
            'success': False,
            'error': 'symbols 参数不能为空'
        }), 400
    
    method = data.get('method', 'mean_variance')
    if method not in ['mean_variance', 'min_variance', 'max_sharpe', 'risk_parity']:
        return jsonify({
            'success': False,
            'error': f'不支持的优化方法: {method}'
        }), 400
    
    try:
        # 获取或估计参数
        expected_returns = data.get('expected_returns')
        cov_matrix = data.get('cov_matrix')
        
        # 如果没有提供，从历史数据估计
        if expected_returns is None or cov_matrix is None:
            # TODO: 从历史数据估计收益率和协方差
            # 这里暂时使用示例数据
            n = len(symbols)
            expected_returns = np.random.uniform(0.05, 0.15, n)
            cov_matrix = np.eye(n) * 0.04
        else:
            expected_returns = np.array(expected_returns)
            cov_matrix = np.array(cov_matrix)
        
        # 其他参数
        risk_aversion = data.get('risk_aversion', 1.0)
        risk_free_rate = data.get('risk_free_rate', 0.02)
        constraints = data.get('constraints', {})
        
        # 创建优化服务
        service = PortfolioOptimizationService()
        
        # 根据方法选择优化算法
        if method == 'mean_variance':
            result = service.mean_variance_optimization(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                risk_aversion=risk_aversion,
                constraints=constraints
            )
        elif method == 'min_variance':
            result = service.minimum_variance(
                cov_matrix=cov_matrix,
                constraints=constraints
            )
        elif method == 'max_sharpe':
            result = service.maximum_sharpe(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                risk_free_rate=risk_free_rate,
                constraints=constraints
            )
        elif method == 'risk_parity':
            result = service.risk_parity(
                cov_matrix=cov_matrix,
                constraints=constraints
            )
        
        # 转换权重数组为字典
        weights_dict = {
            symbol: float(weight)
            for symbol, weight in zip(symbols, result['weights'])
        }
        
        # 构建响应
        response_data = {
            'weights': weights_dict,
            'method': method
        }
        
        # 添加其他指标
        if 'expected_return' in result:
            response_data['expected_return'] = float(result['expected_return'])
        if 'risk' in result:
            response_data['risk'] = float(result['risk'])
        if 'sharpe' in result:
            response_data['sharpe'] = float(result['sharpe'])
        if 'risk_contributions' in result:
            response_data['risk_contributions'] = {
                symbol: float(contrib)
                for symbol, contrib in zip(symbols, result['risk_contributions'])
            }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"组合优化失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
