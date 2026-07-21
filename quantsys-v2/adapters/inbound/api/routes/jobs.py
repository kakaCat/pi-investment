"""
jobs routes.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request
from typing import Dict, List, Optional, Any, Tuple, Union

import threading

logger = logging.getLogger(__name__)

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

# 从 health.py 导入共享的 Job 基础设施
from adapters.inbound.api.routes.health import (
    _jobs,
    _jobs_lock,
    _audit_job,
    _execute_job_by_type,
    _JOB_TYPES,
)

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs (generic, all types) with pagination."""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)

    with _jobs_lock:
        jobs = list(_jobs.values())
        jobs.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        total = len(jobs)

        start = (page - 1) * page_size
        end = start + page_size
        jobs = jobs[start:end]

    return jsonify(sanitize_for_json({
        'success': True,
        'jobs': jobs,
        'count': total
    }))


@jobs_bp.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """Get a single job by id."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404
    return jsonify({'success': True, 'data': sanitize_for_json(job)})


@jobs_bp.route('/api/jobs/<job_type>/run', methods=['POST'])
def run_job_by_type(job_type):
    """Create and run a job of the given type."""
    if job_type not in _JOB_TYPES:
        return jsonify({
            'success': False,
            'error': f'Unsupported job type: {job_type}. Must be one of: {", ".join(sorted(_JOB_TYPES))}'
        }), 400

    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)

    with _jobs_lock:
        for j in _jobs.values():
            if j.get('type') == job_type and j.get('status') in ('pending', 'running', 'queued'):
                return jsonify({
                    'success': False,
                    'error': f'Active job already exists for type: {job_type}'
                }), 409

    job_id = str(uuid.uuid4())
    job = {
        'id': job_id,
        'type': job_type,
        'params': params,
        'status': 'queued',
        'createdAt': datetime.now().isoformat(),
    }

    with _jobs_lock:
        _jobs[job_id] = job

    _audit_job('run', job)

    def _run_job():
        try:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'completed'
                    _jobs[job_id]['result'] = result
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'failed'
                    _jobs[job_id]['error'] = str(e)
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()

    thread = threading.Thread(target=_run_job, daemon=True)
    thread.start()

    _audit_job('run', job)
    return jsonify({'success': True, 'data': sanitize_for_json(job)}), 202


@jobs_bp.route('/api/jobs/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Retry a failed job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404

    if job['status'] not in ('failed', 'cancelled'):
        return jsonify({
            'success': False,
            'error': f'Only failed or cancelled jobs can be retried. Current status: {job["status"]}'
        }), 400

    job_type = job.get('type', 'data_update')
    params = job.get('params', None)

    if not params:
        params = {
            'source': job.get('source', 'watchlist'),
            'days': job.get('days', 730),
            'force': job.get('force', False),
        }

    new_job_id = str(uuid.uuid4())
    new_job = {
        'id': new_job_id,
        'type': job_type,
        'params': params,
        'status': 'queued',
        'createdAt': datetime.now().isoformat(),
        'retryOf': job_id,
    }

    with _jobs_lock:
        _jobs[new_job_id] = new_job

    _audit_job('retry', new_job)

    def _retry():
        try:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'completed'
                    _jobs[new_job_id]['result'] = result
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'failed'
                    _jobs[new_job_id]['error'] = str(e)
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()

    thread = threading.Thread(target=_retry, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'job_id': new_job_id,
        'message': f'Job retried: {new_job_id}'
    })


@jobs_bp.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a pending or running job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404

    if job['status'] not in ('pending', 'running', 'queued'):
        return jsonify({
            'success': False,
            'error': f'Only pending or running jobs can be cancelled. Current status: {job["status"]}'
        }), 400

    with _jobs_lock:
        _jobs[job_id]['status'] = 'cancelled'
        _jobs[job_id]['cancelledAt'] = datetime.now().isoformat()

    _audit_job('cancel', job)

    return jsonify({'success': True, 'message': f'Job cancelled: {job_id}'})


# -- 资金流注入辅助函数 --
_FUND_FLOW_COLUMN_MAP = {
    '主力净流入-净额': 'main_net_inflow',
    '主力净流入-净占比': 'main_net_pct',
    '超大单净流入-净额': 'super_large_net',
    '大单净流入-净额': 'large_net',
    '超大单净流入-净占比': 'super_large_pct',
    '大单净流入-净占比': 'large_pct',
}


def _inject_fund_flow_to_klines(klines: List[dict], symbol: str) -> List[dict]:
    """
    将主力资金流向数据合并到 klines 列表中。
    如果获取失败，所有资金流列填充 0。
    """
    # 初始化所有资金流列为 0
    for k in klines:
        for alias in _FUND_FLOW_COLUMN_MAP.values():
            k[alias] = 0.0

    try:
        days = len(klines)
        fund_data = get_stock_fund_flow(symbol, days=days)

        if not fund_data or not isinstance(fund_data, dict):
            return klines

        fund_rows = fund_data.get('data', [])
        if not fund_rows:
            return klines

        # 建立 日期→资金流 映射
        fund_by_date: Dict[str, dict] = {}
        for row in fund_rows:
            date_str = str(row.get('日期', '')).replace('-', '')
            fund_by_date[date_str] = row

        # 按日期合并
        for k in klines:
            kdate = str(k.get('trade_date', k.get('date', ''))).replace('-', '')
            if kdate in fund_by_date:
                frow = fund_by_date[kdate]
                for cn_name, alias in _FUND_FLOW_COLUMN_MAP.items():
                    val = frow.get(cn_name)
                    if val is not None:
                        try:
                            k[alias] = float(val)
                        except (ValueError, TypeError):
                            pass
    except Exception:
        pass  # 数据源不可用时静默降级

    return klines


def _extract_fund_flow_factors(klines: List[dict]) -> dict:
    """
    从合并后的 klines 最后一条提取主力资金流因子。
    返回可合并到 factors 字典的键值对。
    """
    if not klines:
        return {}

    last = klines[-1]

    # 最近 3/5 日主力净流入累计
    inflow_sum_3d = 0.0
    inflow_sum_5d = 0.0
    for k in klines[-3:]:
        inflow_sum_3d += float(k.get('main_net_inflow', 0) or 0)
    for k in klines[-5:]:
        inflow_sum_5d += float(k.get('main_net_inflow', 0) or 0)

    # 最近 N 日主力净流入为正的天数
    pos_days_3 = sum(1 for k in klines[-3:] if float(k.get('main_net_inflow', 0) or 0) > 0)
    pos_days_5 = sum(1 for k in klines[-5:] if float(k.get('main_net_inflow', 0) or 0) > 0)

    return {
        # 最新一日
        'main_net_inflow': float(last.get('main_net_inflow', 0) or 0),
        'main_net_pct': float(last.get('main_net_pct', 0) or 0),
        'super_large_net': float(last.get('super_large_net', 0) or 0),
        'large_net': float(last.get('large_net', 0) or 0),
        'super_large_pct': float(last.get('super_large_pct', 0) or 0),
        'large_pct': float(last.get('large_pct', 0) or 0),
        # 趋势因子
        'fund_inflow_3d_sum': inflow_sum_3d,
        'fund_inflow_5d_sum': inflow_sum_5d,
        'fund_inflow_pos_days_3': pos_days_3,
        'fund_inflow_pos_days_5': pos_days_5,
    }


@jobs_bp.route('/api/compute/factors', methods=['POST'])
def compute_factors():
    """计算因子（支持单个symbol或批量symbols）"""
    data = request.get_json() or {}
    symbol = data.get('symbol')
    symbols = data.get('symbols', [])
    requested_factors = data.get('factors', [])
    include_fundamental = data.get('include_fundamental', False)

    # Auto-detect: if fscore or earnings_quality is in the requested factors,
    # enable fundamental factor computation automatically
    if not include_fundamental and requested_factors:
        fundamental_names = {'fscore', 'earnings_quality'}
        if fundamental_names & set(requested_factors):
            include_fundamental = True

    all_symbols = list(symbols) if symbols else []
    if symbol and symbol not in all_symbols:
        all_symbols.append(symbol)

    if not all_symbols:
        return jsonify({'error': '缺少symbol或symbols参数'}), 400

    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

        from domain.quantlib.stages.factor_stage import FactorStage

        results = []
        for sym in all_symbols:
            klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
            if klines_df is None or klines_df.is_empty():
                results.append({'symbol': sym, 'error': 'No kline data'})
                continue

            # Convert DataFrame to list of dicts for compatibility with existing code
            klines = klines_df.to_dicts()

            # -- 注入主力资金流数据到 klines --
            klines = _inject_fund_flow_to_klines(klines, sym)

            # -- 准备财务数据（如果需要基本面因子） --
            financial_data = None
            if include_fundamental:
                financial_data = _fetch_financial_data(sym)

            stage = FactorStage(
                name="factors",
                factor_names=requested_factors if requested_factors else None
            )
            stage_input = {
                'symbol': sym,
                'klines': klines
            }
            if financial_data:
                stage_input['financial_data'] = financial_data
            if requested_factors:
                stage_input['requested_factors'] = requested_factors

            result = stage.process(stage_input)
            factors = result.get('factors', {})

            # -- 附加主力资金流因子（从最后一条 kline 提取） --
            fund_factors = _extract_fund_flow_factors(klines)
            factors.update(fund_factors)

            last_row = klines[-1]
            latest_date = last_row.get('trade_date') or last_row.get('date') or ''
            ds.factor.save_factors(sym, str(latest_date), factors)

            results.append({
                'symbol': sym,
                'date': str(latest_date),
                'factor_count': len(factors),
                'factors': factors
            })

        return jsonify(sanitize_for_json({
            'success': True,
            'results': results,
            'count': len(results)
        }))
    except Exception as e:
        logger.exception(f"compute_factors failed: {e}")
        return jsonify({'error': str(e)}), 500


def _fetch_financial_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取财务数据用于基本面因子计算。

    使用 ds.get_financial_statements 获取原始财报数据（Sina 格式），
    解析出 FSCORE 和盈利质量计算所需的指标。

    返回 current 和 previous 两期数据，用于同比比较。
    至少需要 2 期数据；不足则返回 None。
    """
    try:
        raw = ds.get_financial_statements(symbol, statement_type='all', periods=8)
    except Exception as e:
        logger.warning(f"Failed to fetch financial statements for {symbol}: {e}")
        return None

    if not raw or 'error' in raw:
        logger.warning(f"No financial data for {symbol}: {raw.get('error', 'unknown') if isinstance(raw, dict) else 'empty'}")
        return None

    income_records = raw.get('income_statement', [])
    balance_records = raw.get('balance_sheet', [])
    cashflow_records = raw.get('cash_flow', [])

    if not income_records or not balance_records:
        logger.warning(f"Incomplete financial data for {symbol}: income={bool(income_records)}, balance={bool(balance_records)}")
        return None

    # Parse records into simplified metric dicts
    try:
        periods_data = _parse_financial_periods(income_records, balance_records, cashflow_records)
    except Exception as e:
        logger.warning(f"Failed to parse financial periods for {symbol}: {e}")
        return None
    if len(periods_data) < 2:
        logger.warning(f"Insufficient financial periods for {symbol}: {len(periods_data)}")
        return None

    current = periods_data[0]
    previous = periods_data[1]

    def _v(d: dict, key: str) -> Optional[float]:
        return d.get(key)

    return {
        'current': {
            'roa':             _v(current, 'roa'),
            'operating_cf':    _v(current, 'operating_cf'),
            'net_income':      _v(current, 'net_income'),
            'long_term_debt':  _v(current, 'long_term_debt'),
            'total_assets':    _v(current, 'total_assets'),
            'current_ratio':   _v(current, 'current_ratio'),
            'total_shares':    _v(current, 'total_shares'),
            'gross_margin':    _v(current, 'gross_margin'),
            'revenue':         _v(current, 'revenue'),
            'total_liabilities': _v(current, 'total_liabilities'),
            'roe':             _v(current, 'roe'),
        },
        'previous': {
            'roa':             _v(previous, 'roa'),
            'long_term_debt':  _v(previous, 'long_term_debt'),
            'total_assets':    _v(previous, 'total_assets'),
            'current_ratio':   _v(previous, 'current_ratio'),
            'total_shares':    _v(previous, 'total_shares'),
            'gross_margin':    _v(previous, 'gross_margin'),
            'revenue':         _v(previous, 'revenue'),
        }
    }


def _parse_financial_periods(
    income_records: List[dict],
    balance_records: List[dict],
    cashflow_records: List[dict],
) -> List[dict]:
    """
    Parse raw Sina financial report records into simplified metric dicts.
    Returns list of period dicts sorted by report date (most recent first).

    Each period dict contains:
        roa, operating_cf, net_income, long_term_debt, total_assets,
        current_ratio, total_shares, gross_margin, revenue,
        total_liabilities, roe
    """
    # Merge income + balance + cashflow by report date
    periods: Dict[str, dict] = {}  # report_date -> merged dict

    for rec in income_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date:
                periods.setdefault(date, {})['report_date'] = date

                # Income statement fields
                revenue = _pick_num(rec, ['营业总收入', '营业收入'])
                cost   = _pick_num(rec, ['营业成本'])  # COGS for gross margin, NOT 营业总成本 (total costs)
                net_income = _pick_num(rec, ['净利润'])

                if date in periods:
                    p = periods[date]
                    p['revenue']    = revenue
                    p['net_income'] = net_income
                    if revenue and cost and revenue != 0:
                        p['gross_margin'] = (revenue - cost) / revenue

    for rec in balance_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date:
                periods.setdefault(date, {})['report_date'] = date

                total_assets      = _pick_num(rec, ['资产总计', '总资产'])
                total_liabilities  = _pick_num(rec, ['负债合计', '总负债'])
                current_assets    = _pick_num(rec, ['流动资产合计'])
                current_liab      = _pick_num(rec, ['流动负债合计'])
                noncurrent_liab   = _pick_num(rec, ['非流动负债合计'])
                total_equity      = _pick_num(rec, ['所有者权益(或股东权益)合计', '所有者权益合计', '股东权益合计', '归属于母公司股东权益合计'])

                p = periods[date]
                p['total_assets']      = total_assets
                p['total_liabilities']  = total_liabilities
                p['long_term_debt']    = noncurrent_liab  # proxy
                if current_assets and current_liab and current_liab != 0:
                    p['current_ratio'] = current_assets / current_liab
                if net_income := p.get('net_income'):
                    if total_assets and total_assets != 0:
                        p['roa'] = net_income / total_assets
                    if total_equity and total_equity != 0:
                        p['roe'] = net_income / total_equity

    for rec in cashflow_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date and date in periods:
                op_cf = _pick_num(rec, ['经营活动产生的现金流量净额', '经营活动现金流量净额'])
                periods[date]['operating_cf'] = op_cf

    # Sort by date descending, filter incomplete periods, return as list
    result = []
    for date in sorted(periods.keys(), reverse=True):
        p = periods[date]
        # Need at minimum: roa, operating_cf, net_income, long_term_debt, total_assets,
        #   current_ratio, gross_margin, revenue, total_liabilities, roe
        required = ['roa', 'operating_cf', 'net_income', 'long_term_debt',
                     'total_assets', 'current_ratio', 'gross_margin', 'revenue',
                     'total_liabilities', 'roe']
        if all(p.get(k) is not None for k in required):
            # total_shares: use a placeholder (we can't easily get from Sina)
            # The FSCORE criterion will default to 0 if shares == 0
            if 'total_shares' not in p:
                p['total_shares'] = 0  # placeholder
            result.append(p)

    return result


def _report_date(rec: dict) -> Optional[str]:
    """Extract report date from a Sina financial record."""
    for col in ('报告日', '报表日', '截止日期', 'date', '报告期'):
        val = rec.get(col)
        if val is not None:
            s = str(val)[:10]
            return s
    return None


def _pick_num(rec: dict, candidates: List[str]) -> Optional[float]:
    """Pick the first non-None numeric value from a list of candidate column names."""
    for col in candidates:
        val = rec.get(col)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None
