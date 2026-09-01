"""风控 API - FastAPI 版（从 Flask risk.py 迁移，响应契约保持一致）

注意：Flask update_stop_loss_rule 有误用未定义变量 rule_dict 的 bug（应为 rule），
此处使用正确的 rule（Flask 作者的本意），故更新已存在规则时 FastAPI 正常而 Flask 会
NameError（既有 bug，无法 parity，属故意修正）。
/api/risk/metrics 与 /api/risk/stress-test 在 analysis.py（P6c 迁移），不在本文件。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error, sanitize_for_json,
    portfolio_repo, kline_repo, risk_repo,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Risk - 风控"])


def _normalize_stop_loss_type(stop_loss_type):
    type_mapping = {
        'price': 'fixed_price', 'percent': 'fixed_percent', 'trailing': 'trailing_stop',
        'fixed_price': 'fixed_price', 'fixed_percent': 'fixed_percent', 'trailing_stop': 'trailing_stop',
    }
    return type_mapping.get(stop_loss_type, 'fixed_percent')


def _format_rule(rule):
    return {
        'id': rule.get('id'), 'symbol': rule.get('symbol'), 'name': rule.get('name'),
        'type': rule.get('type'), 'stopLossPercent': rule.get('stop_loss_percent'),
        'triggerPercent': rule.get('stop_loss_percent'), 'trailingPercent': rule.get('trailing_percent'),
        'atrMultiplier': rule.get('atr_multiplier'), 'status': rule.get('status'),
        'createdAt': rule.get('created_at'), 'updatedAt': rule.get('updated_at'),
    }


@router.post('/api/risk/check')
def risk_check(payload: Optional[Dict[str, Any]] = Body(None)):
    """风险检查"""
    try:
        data = payload or {}
        symbols = data.get('symbols')
        holdings = portfolio_repo.get_all_holdings()
        if symbols:
            holdings = [h for h in holdings if h['symbol'] in symbols]
        account_value = float(data.get('account_value', 0)) if data.get('account_value') else None

        holdings_stats = portfolio_repo.get_holdings_stats()
        sector_concentration_map = {}
        if holdings_stats and account_value and account_value > 0:
            sector_dist = holdings_stats.get('sector_distribution', [])
            for sector_info in sector_dist:
                sector_name = sector_info.get('sector', '未知')
                sector_invested = sector_info.get('invested', 0) or 0
                sector_ratio = sector_invested / account_value
                if sector_ratio > 0.5:
                    sector_concentration_map[sector_name] = sector_ratio

        checks = []
        for h in holdings:
            symbol = h['symbol']
            position_value = h.get('total_invested', 0) or (h.get('quantity', 0) * h.get('avg_cost', 0))
            item_checks = []
            current_price = 0
            try:
                latest_kline = kline_repo.get_latest_daily_kline(symbol)
                if latest_kline is not None and not latest_kline.is_empty():
                    kline_row = latest_kline.to_dicts()[0]
                    current_price = float(kline_row.get('close', 0))
            except Exception:
                pass
            if account_value and account_value > 0:
                concentration = (position_value / account_value) * 100
                if concentration > 30:
                    item_checks.append({
                        'type': 'concentration', 'level': 'high',
                        'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 30%', 'suggestion': '建议分散持仓'})
            holding_sector = h.get('sector', '未知')
            if holding_sector in sector_concentration_map:
                sector_ratio = sector_concentration_map[holding_sector]
                item_checks.append({
                    'type': 'sector_concentration', 'level': 'high',
                    'message': f'{symbol} 所属行业 "{holding_sector}" 集中度 {sector_ratio*100:.1f}% > 50%',
                    'suggestion': '建议分散行业配置'})
            risk_metrics = risk_repo.get_latest_risk_metrics(symbol)
            var_95 = volatility = max_drawdown = 0
            if risk_metrics:
                var_95 = risk_metrics.get('var_95', 0) or 0
                volatility = risk_metrics.get('volatility', 0) or 0
                max_drawdown = risk_metrics.get('max_drawdown', 0) or 0
                if var_95 < -0.05:
                    item_checks.append({
                        'type': 'var', 'level': 'medium',
                        'message': f'{symbol} VaR 95% = {var_95:.3f}', 'suggestion': '建议设置止损'})
            checks.append({
                'symbol': symbol, 'position_value': position_value, 'current_price': current_price,
                'var_95': var_95, 'volatility': volatility, 'max_drawdown': max_drawdown, 'checks': item_checks})
        return sanitize_for_json({
            'total_holdings': len(holdings), 'checks': checks,
            'risk_level': 'high' if len(checks) > 3 else 'low'})
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ============ 止损规则 ============

@router.get('/api/risk/stop-loss/rules')
def get_stop_loss_rules(symbol: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    """获取止损规则列表"""
    try:
        from adapters.outbound.repositories import RiskORMRepository
        repo = RiskORMRepository()
        rules = repo.list_stop_loss_rules(symbol=symbol, status=status)
        rules_list = [_format_rule(rule) for rule in rules]
        return {'success': True, 'rules': rules_list, 'count': len(rules_list)}
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/risk/stop-loss/rules/batch')
def batch_create_stop_loss_rules(payload: Optional[Dict[str, Any]] = Body(None)):
    """批量创建止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository
        body = payload or {}
        rules_data = body.get('rules', [])
        if not rules_data:
            return error_response({'success': False, 'error': '缺少rules参数'}, 400)
        repo = RiskORMRepository()
        created = []
        for idx, item in enumerate(rules_data):
            trigger_value = item.get('stopLossPercent') or item.get('triggerPercent')
            stop_loss_type = item.get('stopLossType') or item.get('type', 'fixed_percent')
            rule_id = str(int(datetime.now().timestamp() * 1000) + idx)
            rule_data = {
                'id': rule_id, 'symbol': item['symbol'],
                'name': item.get('name', f"{item['symbol']}止损"),
                'type': _normalize_stop_loss_type(stop_loss_type),
                'stop_loss_percent': trigger_value, 'trailing_percent': item.get('trailingPercent'),
                'atr_multiplier': item.get('atrMultiplier'), 'status': 'active',
            }
            repo.create_stop_loss_rule(rule_data)
            created.append(rule_id)
        return {'success': True, 'created': len(created), 'rule_ids': created}
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/risk/stop-loss/rules')
def create_stop_loss_rule(payload: Optional[Dict[str, Any]] = Body(None)):
    """创建止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository
        body = payload or {}
        if not body.get('symbol'):
            return error_response({'success': False, 'error': '缺少symbol参数'}, 400)
        trigger_value = body.get('stopLossPercent') or body.get('triggerPercent')
        stop_loss_type = body.get('stopLossType') or body.get('type', 'fixed_percent')
        rule_id = str(int(datetime.now().timestamp() * 1000))
        repo = RiskORMRepository()
        rule_data = {
            'id': rule_id, 'symbol': body['symbol'],
            'name': body.get('name', f"{body['symbol']}止损"),
            'type': _normalize_stop_loss_type(stop_loss_type),
            'stop_loss_percent': trigger_value, 'trailing_percent': body.get('trailingPercent'),
            'atr_multiplier': body.get('atrMultiplier'), 'status': 'active',
        }
        repo.create_stop_loss_rule(rule_data)
        rule = repo.get_stop_loss_rule(rule_id)
        if rule:
            return {'success': True, 'rule': _format_rule(rule)}
        return error_response({'success': False, 'error': '创建规则失败'}, 500)
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.put('/api/risk/stop-loss/rules/{rule_id}')
def update_stop_loss_rule(rule_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    """更新止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository
        body = payload or {}
        repo = RiskORMRepository()
        update_params = {}
        if 'name' in body:
            update_params['name'] = body['name']
        if 'stopLossType' in body:
            update_params['type'] = _normalize_stop_loss_type(body['stopLossType'])
        elif 'type' in body:
            update_params['type'] = _normalize_stop_loss_type(body['type'])
        if 'triggerPercent' in body:
            update_params['stop_loss_percent'] = body['triggerPercent']
        elif 'stopLossPercent' in body:
            update_params['stop_loss_percent'] = body['stopLossPercent']
        if 'trailingPercent' in body:
            update_params['trailing_percent'] = body['trailingPercent']
        if 'atrMultiplier' in body:
            update_params['atr_multiplier'] = body['atrMultiplier']
        if 'status' in body:
            update_params['status'] = body['status']
        success = repo.update_stop_loss_rule(rule_id, update_params)
        if not success:
            return error_response({'success': False, 'error': '规则不存在'}, 404)
        rule = repo.get_stop_loss_rule(rule_id)
        if rule:
            return {'success': True, 'rule': _format_rule(rule)}
        return error_response({'success': False, 'error': '更新后无法获取规则'}, 500)
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ 单票风控（trade-check / position-size / stop-loss，agent 迁移批次） ============

@router.post('/api/stock/{symbol}/risk/trade-check')
@handle_api_error
def check_trade_risk_v2(symbol: str, payload: Optional[Dict[str, Any]] = Body(None)):
    """交易风控检查 - 替代旧 quant_cli risk.trade_check"""
    try:
        from application.services.risk_service import RiskService

        data = payload or {}
        action = data.get('action', 'buy')
        price = data.get('price', 0)
        shares = data.get('shares', 0)
        if not price or not shares:
            return error_response({'success': False, 'error': 'price and shares required'}, 400)

        risk_service = RiskService()
        result = risk_service.check_trade_risk(symbol, action, float(price), int(shares))

        if not result.get('success'):
            return error_response({'success': False, 'error': result.get('error')}, 400)
        return api_response(result.get('data'))
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/stock/{symbol}/risk/position-size')
@handle_api_error
def calculate_position_size_v2(symbol: str, payload: Optional[Dict[str, Any]] = Body(None)):
    """Kelly仓位计算 - 替代旧 quant_cli risk.position_size"""
    try:
        from application.services.risk_service import RiskService

        data = payload or {}
        price = data.get('price', 0)
        account_value = data.get('account_value', 100000)  # 默认账户价值
        risk_percent = data.get('risk_percent', 2.0)  # 默认风险百分比

        if not price:
            return error_response({'success': False, 'error': 'price required'}, 400)

        risk_service = RiskService()
        result = risk_service.calculate_position_size(symbol, float(account_value), float(risk_percent))

        if not result.get('success'):
            return error_response({'success': False, 'error': result.get('error')}, 400)
        return api_response(result.get('data'))
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/stock/{symbol}/risk/stop-loss')
@handle_api_error
def calculate_stop_loss_v2(symbol: str, payload: Optional[Dict[str, Any]] = Body(None)):
    """止损价计算 - 替代旧 quant_cli risk.stop_loss"""
    try:
        from application.services.risk_service import RiskService

        data = payload or {}
        entry_price = data.get('entry_price', 0)
        method = data.get('method', 'percentage')  # 默认使用百分比方法

        if not entry_price:
            return error_response({'success': False, 'error': 'entry_price required'}, 400)

        risk_service = RiskService()
        result = risk_service.calculate_stop_loss(symbol, float(entry_price), method)

        if not result.get('success'):
            return error_response({'success': False, 'error': result.get('error')}, 400)
        return api_response(result.get('data'))
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/risk/stop-loss/rules/{rule_id}')
def delete_stop_loss_rule(rule_id: str):
    """删除止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository
        repo = RiskORMRepository()
        success = repo.delete_stop_loss_rule(rule_id)
        if not success:
            return error_response({'success': False, 'error': '规则不存在'}, 404)
        return {'success': True, 'message': '规则已删除'}
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/risk/trade-verify')
@router.post('/api/risk/trade-verify')
@handle_api_error
def trade_verify(
    account_name: Optional[str] = Query('agent_virtual'),
    date: Optional[str] = Query(None),
    payload: Optional[Dict[str, Any]] = Body(None),
):
    """每日交易对账（E-2 修复：后端权威实现，2026-09-01）。

    GET/POST 双支持：client.verifyTrades 契约为 POST（Flask 时代遗留），
    浏览器/调试用 GET。POST 时 body 参数优先于 query。

    背景：本路由在 Flask→FastAPI 迁移中丢失（404），TradeVerifyTool 曾用本地
    对账替代（2026-08-23）。本端点把对账逻辑收回服务端：
      1. 当日重复成交检测（同标的+同方向+同价+同量+同分钟）
      2. 关键字段缺失/非法值（price/quantity <= 0）
      3. 持仓勾稽（全量历史 买入-卖出 净额 vs 当前持仓；迁移缺腿降级为提示）

    返回与 TradeVerifyTool 本地产出同构：{date, total_orders, matched,
    mismatched, anomalies[], history_gaps[]?}
    """
    from collections import defaultdict

    from infrastructure.persistence.orm import get_session
    from infrastructure.persistence.orm.models.simulation import (
        SimulationTrade, SimulationPosition,
    )

    # POST body 参数优先于 query（client.verifyTrades 契约）
    if payload:
        account_name = payload.get('account_name', account_name)
        date = payload.get('date', date)
    target_date = date or datetime.now().strftime('%Y-%m-%d')
    session = get_session()
    try:
        all_trades = (
            session.query(SimulationTrade)
            .filter(SimulationTrade.account_name == account_name)
            .order_by(SimulationTrade.id.asc())
            .all()
        )
        positions = (
            session.query(SimulationPosition)
            .filter(SimulationPosition.account_name == account_name)
            .all()
        )
    finally:
        session.close()

    def _td(t) -> str:
        v = getattr(t, 'trade_date', None) or getattr(t, 'created_at', None)
        return str(v)[:10] if v else ''

    day_trades = [t for t in all_trades if _td(t) == target_date]

    anomalies: List[Dict[str, Any]] = []

    # 1. 重复成交检测
    seen: Dict[str, int] = defaultdict(int)
    for t in day_trades:
        minute = str(getattr(t, 'created_at', '') or '')[:16]
        key = f"{t.symbol}|{t.action}|{t.price}|{t.shares}|{minute}"
        seen[key] += 1
        if seen[key] > 1:
            anomalies.append({
                'type': 'duplicate_trade',
                'detail': f"疑似重复成交: {t.symbol} {t.action} {t.shares}股@{t.price}（第{seen[key]}次）",
                'trade_id': getattr(t, 'id', None),
            })

    # 2. 关键字段缺失/非法值
    for t in day_trades:
        missing = [f for f in ('symbol', 'action', 'price', 'shares')
                   if getattr(t, f, None) is None]
        if missing:
            anomalies.append({
                'type': 'missing_fields',
                'detail': f"成交记录缺字段 {'/'.join(missing)}: id={getattr(t, 'id', '?')}",
                'trade_id': getattr(t, 'id', None),
            })
        price = float(getattr(t, 'price', 0) or 0)
        qty = int(getattr(t, 'shares', 0) or 0)
        if price <= 0 or qty <= 0:
            anomalies.append({
                'type': 'invalid_value',
                'detail': f"成交价格/数量非法: {t.symbol} @{t.price} x{t.shares}",
                'trade_id': getattr(t, 'id', None),
            })

    # 3. 持仓勾稽（迁移缺腿降级为 history_gaps 提示，不算异常）
    def _sym(s) -> str:
        return str(s or '').split('.')[0]

    pos_map = {_sym(p.symbol): int(getattr(p, 'shares_total', 0) or 0) for p in positions}
    net_map: Dict[str, int] = defaultdict(int)
    has_buy = set()
    for t in all_trades:
        sym = _sym(t.symbol)
        q = int(getattr(t, 'shares', 0) or 0)
        if str(getattr(t, 'action', '')).lower() == 'buy':
            net_map[sym] += q
            has_buy.add(sym)
        else:
            net_map[sym] -= q

    history_gaps: List[Dict[str, Any]] = []
    for sym, net in net_map.items():
        held = pos_map.get(sym, 0)
        if held > 0 and held != net and abs(held - net) >= 100:
            if sym not in has_buy:
                history_gaps.append({
                    'symbol': sym, 'net_trades': net,
                    'note': '迁移持仓（可见历史无买入腿），不参与勾稽',
                })
            else:
                anomalies.append({
                    'type': 'position_mismatch',
                    'detail': f"持仓勾稽不符 {sym}: 账面 {held} vs 成交净额 {net}",
                    'symbol': sym,
                })
        elif held == 0 and net != 0:
            history_gaps.append({
                'symbol': sym, 'net_trades': net,
                'note': '历史迁移缺腿（买入/卖出记录不全），不参与勾稽',
            })

    bad = {'duplicate_trade', 'missing_fields', 'invalid_value'}
    result: Dict[str, Any] = {
        'date': target_date,
        'total_orders': len(day_trades),
        'matched': len(day_trades) - sum(1 for a in anomalies if a['type'] in bad),
        'mismatched': len(anomalies),
        'anomalies': anomalies,
        'note': '服务端对账（/api/risk/trade-verify，E-2 修复 2026-09-01）',
    }
    if history_gaps:
        result['history_gaps'] = history_gaps
    return api_response(result)
