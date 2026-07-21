"""
pipeline routes.
"""
import json
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
from typing import List

from flask import Blueprint, jsonify, request, Response
from typing import Dict, List, Optional, Any, Tuple, Union

import os

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

pipeline_bp = Blueprint('pipeline', __name__)

# ═══════════════════════════════════════════════════════════════
# Background executors
# ═══════════════════════════════════════════════════════════════


def _execute_pipeline_stages_with_error_handling(run_id: str, symbols: List[str], stages: List[str], task_type: Optional[str] = None, days: int = 730):
    """包装器函数：捕获所有异常并确保任务锁释放"""
    try:
        _execute_pipeline_stages(run_id, symbols, stages, task_type, days)
    except Exception as e:
        # 记录详细异常信息
        import traceback
        error_msg = f"Pipeline execution failed for {run_id}: {str(e)}"
        error_trace = traceback.format_exc()

        logger.error(error_msg)
        logger.error(error_trace)

        # 更新任务状态为失败
        try:
            _update_pipeline_run(run_id, {
                'status': 'failed',
                'endTime': datetime.now().isoformat(),
                'error': error_msg,
                'logs': [
                    f"[{datetime.now().isoformat()}] ❌ 严重错误: {error_msg}",
                    f"[{datetime.now().isoformat()}] Traceback: {error_trace[:500]}..."
                ]
            })
        except Exception as update_err:
            logger.error(f"Failed to update pipeline run status: {update_err}")

        # 确保释放任务锁
        if task_type:
            try:
                release_task(task_type)
                logger.info(f"Released task lock for {task_type} after error")
            except Exception as release_err:
                logger.error(f"Failed to release task lock: {release_err}")


def _execute_pipeline_stages(run_id: str, symbols: List[str], stages: List[str], task_type: Optional[str] = None, days: int = 730):
    """执行流水线阶段 - 内部实现"""
    # 防御性解析: symbols 可能以字符串形式传入(逗号分隔)
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(',') if s.strip()]
    if not symbols:
        symbols = ['000001.SZ']
    start_time = datetime.now()
    stage_defs = [
        {'key': 'data_update', 'name': '数据更新'},
        {'key': 'factors', 'name': '因子计算'},
        {'key': 'signals', 'name': '信号扫描'},
        {'key': 'risk', 'name': '风控检查'},
    ]
    stage_results = []
    logs: List[str] = [f"[{start_time.isoformat()}] 流水线运行开始: {run_id}, days={days}"]
    all_success = True

    for sd in stage_defs:
        if sd['key'] not in stages:
            continue
        stage_start = datetime.now()
        logs.append(f"[{stage_start.isoformat()}] 阶段开始: {sd['name']}")
        try:
            if sd['key'] == 'data_update':
                # 清除代理环境变量（akshare需要直连）
                import os as _os
                for _key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
                    _os.environ.pop(_key, None)

                # 强制重新加载模块以获取最新代码
                import importlib
                import domain.brokers.adapters.akshare_broker
                importlib.reload(domain.brokers.adapters.akshare_broker)
                from domain.brokers.adapters.akshare_broker import AkshareBroker

                broker = AkshareBroker()
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                end_date = datetime.now().strftime('%Y-%m-%d')
                updated = 0
                failed_syms = []
                for sym in symbols:
                    try:
                        # 下载K线数据
                        logger.info(f"[DATA_UPDATE][{run_id}] Fetching {sym} from {start_date} to {end_date}")
                        result = broker.get_history(sym, start_date, end_date, 'daily')
                        logger.info(f"[DATA_UPDATE][{run_id}] Result for {sym}: success={result.success}, count={len(result.data) if result.success and result.data else 0}")
                        if result.success and result.data:
                            # 转换为数据库格式
                            klines = []
                            # 统一使用不带后缀的股票代码
                            clean_symbol = sym.split('.')[0] if '.' in sym else sym
                            for candle in result.data:
                                klines.append({
                                    'symbol': clean_symbol,  # 使用不带后缀的代码
                                    'trade_date': candle.timestamp.strftime('%Y-%m-%d') if hasattr(candle.timestamp, 'strftime') else str(candle.timestamp)[:10],
                                    'open': candle.open,
                                    'high': candle.high,
                                    'low': candle.low,
                                    'close': candle.close,
                                    'volume': candle.volume,
                                    'amount': candle.turnover if candle.turnover else 0,
                                    'turnover_rate': 0,
                                })
                            if klines:
                                ds.kline.save_daily_klines(klines)
                                updated += 1
                        else:
                            failed_syms.append(f"{sym}({result.error})")
                    except Exception as sym_err:
                        failed_syms.append(f"{sym}({str(sym_err)})")
                stage_results.append({
                    'name': sd['key'], 'status': 'completed',
                    'duration': (datetime.now() - stage_start).total_seconds(),
                    'symbols_count': len(symbols), 'symbols_updated': updated,
                })
                if failed_syms:
                    logs.append(f"[{datetime.now().isoformat()}] {sd['name']}完成: {updated}/{len(symbols)} 只股票, 失败: {', '.join(failed_syms[:5])}")
                else:
                    logs.append(f"[{datetime.now().isoformat()}] {sd['name']}完成: {updated}/{len(symbols)} 只股票")
            elif sd['key'] == 'factors':
                from domain.quantlib.stages.factor_stage import FactorStage
                factor_count = 0
                for sym in symbols:
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                    klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
                    if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 20:
                        try:
                            klines = klines_df.to_dicts()
                            stage = FactorStage(name="factors")
                            result = stage.process({'symbol': sym, 'klines': klines})
                            factors = result.get('factors', {})
                            latest_date = klines[-1]['trade_date']
                            ds.factor.save_factors(sym, str(latest_date), factors)
                            factor_count += len(factors)
                        except Exception:
                            pass
                stage_results.append({
                    'name': sd['key'], 'status': 'completed',
                    'duration': (datetime.now() - stage_start).total_seconds(),
                    'symbols_processed': len(symbols), 'factors_computed': factor_count,
                })
                logs.append(f"[{datetime.now().isoformat()}] {sd['name']}完成: {factor_count} 个因子")
            elif sd['key'] == 'signals':
                signal_count = sum(
                    len(ds.signal.get_signals_by_symbol(sym, '2024-01-01', datetime.now().strftime('%Y-%m-%d')))
                    for sym in symbols
                )
                stage_results.append({
                    'name': sd['key'], 'status': 'completed',
                    'duration': (datetime.now() - stage_start).total_seconds(),
                    'signal_count': signal_count,
                })
                logs.append(f"[{datetime.now().isoformat()}] {sd['name']}完成: {signal_count} 个信号")
            elif sd['key'] == 'risk':
                risk_checks = sum(1 for sym in symbols if ds.risk.get_latest_risk_metrics(sym))
                stage_results.append({
                    'name': sd['key'], 'status': 'completed',
                    'duration': (datetime.now() - stage_start).total_seconds(),
                    'checks_performed': risk_checks,
                })
                logs.append(f"[{datetime.now().isoformat()}] {sd['name']}完成: {risk_checks} 只股票")
        except Exception as e:
            stage_results.append({'name': sd['key'], 'status': 'failed', 'error': str(e)})
            logs.append(f"[{datetime.now().isoformat()}] {sd['name']}失败: {str(e)}")
            all_success = False

    end_time = datetime.now()
    duration = round((end_time - start_time).total_seconds(), 1)
    failed = [s for s in stage_results if s.get('status') == 'failed']
    status = 'completed' if not failed else ('failed' if not all_success else 'partial_failure')
    logs.append(f"[{end_time.isoformat()}] 流水线完成: {status}, 总耗时 {duration}s")

    _update_pipeline_run(run_id, {
        'status': status, 'endTime': end_time.isoformat(), 'duration': duration,
        'stages': stage_results, 'logs': logs,
        'signalCount': sum(s.get('signal_count', 0) for s in stage_results),
        'factorCount': sum(s.get('factors_computed', 0) for s in stage_results),
    })
    if task_type:
        release_task(task_type)


def _execute_factor_compute(run_id: str, symbols: List[str], force: bool = False):
    start_time = datetime.now()
    logs: List[str] = [f"[{start_time.isoformat()}] 因子计算开始: {run_id}"]
    factor_count = processed = 0
    try:
        from domain.quantlib.stages.factor_stage import FactorStage
        stage = FactorStage(name="factors")
        for sym in symbols:
            try:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
                klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
                if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 20:
                    klines = klines_df.to_dicts()
                    result = stage.process({'symbol': sym, 'klines': klines})
                    factors = result.get('factors', {})
                    if factors:
                        latest_date = klines[-1]['trade_date']
                        ds.factor.save_factors(sym, str(latest_date), factors)
                        factor_count += len(factors)
                        processed += 1
                        logs.append(f"[{datetime.now().isoformat()}] {sym}: {len(factors)} 个因子已保存")
            except Exception as e:
                logs.append(f"[{datetime.now().isoformat()}] {sym} 因子计算失败: {e}")
        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 1)
        logs.append(f"[{end_time.isoformat()}] 因子计算完成: {processed}/{len(symbols)} 只股票, {factor_count} 个因子, 耗时 {duration}s")
        _update_pipeline_run(run_id, {
            'status': 'completed', 'endTime': end_time.isoformat(), 'duration': duration,
            'logs': logs, 'factorCount': factor_count, 'symbolsProcessed': processed,
        })
    except Exception as e:
        end_time = datetime.now()
        _update_pipeline_run(run_id, {
            'status': 'failed', 'endTime': end_time.isoformat(),
            'duration': round((end_time - start_time).total_seconds(), 1),
            'logs': logs + [f"[{end_time.isoformat()}] 因子计算失败: {e}"], 'error': str(e),
        })
    finally:
        release_task('factor_compute')


def _execute_signal_generate(run_id: str, symbols: List[str], date: Optional[str] = None):
    start_time = datetime.now()
    logs: List[str] = [f"[{start_time.isoformat()}] 信号生成开始: {run_id}"]
    signal_count = 0
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant' / 'scripts'))
        from generate_signals import SignalGenerator
        db = Database(connect=True)
        generator = SignalGenerator(db)
        if not date:
            date = generator.get_latest_date()
            logs.append(f"[{datetime.now().isoformat()}] 使用最新数据日期: {date}")
        signals, _factors = generator.generate_signals(symbols=symbols if symbols else None, date=date)
        if signals:
            generator.persist_signals_to_database(signals)
            signal_count = len(signals)
            logs.append(f"[{datetime.now().isoformat()}] {signal_count} 个信号已保存到数据库")
        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 1)
        logs.append(f"[{end_time.isoformat()}] 信号生成完成: {signal_count} 个信号, 耗时 {duration}s")
        _update_pipeline_run(run_id, {
            'status': 'completed', 'endTime': end_time.isoformat(), 'duration': duration,
            'logs': logs, 'signalCount': signal_count,
        })
    except Exception as e:
        end_time = datetime.now()
        _update_pipeline_run(run_id, {
            'status': 'failed', 'endTime': end_time.isoformat(),
            'duration': round((end_time - start_time).total_seconds(), 1),
            'logs': logs + [f"[{end_time.isoformat()}] 信号生成失败: {e}"], 'error': str(e),
        })
    finally:
        release_task('signal_generate')


def _execute_ml_train(
    run_id: str, days: int = 180, future_days: int = 5, threshold: float = 0.05,
    model: str = "xgboost", tune: bool = False, trials: int = 20, cv_splits: int = 5,
    use_feature_engineering: bool = True,
):
    start_time = datetime.now()
    logs: List[str] = [f"[{start_time.isoformat()}] ML训练开始: {run_id}"]
    logs.append(f"[{start_time.isoformat()}] 参数: days={days}, future_days={future_days}, model={model}, tune={tune}")
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant' / 'scripts'))
        from ml_retrain import MLRetrainer
        db_path = os.environ.get("QUANT_DB_PATH", str(_V2_ROOT.parent / 'quant' / '.pi-invest' / 'stock-db' / 'stocks.db'))
        model_dir = str(_V2_ROOT.parent / 'quant' / 'quantsys' / 'ml' / 'models')
        trainer = MLRetrainer(db_path=db_path, model_dir=model_dir)
        logs.append(f"[{datetime.now().isoformat()}] 加载训练数据...")
        features_df, labels_df = trainer.load_training_data(
            days=days, future_days=future_days, return_threshold=threshold)
        logs.append(f"[{datetime.now().isoformat()}] 训练数据: {len(features_df)} 样本")
        # 只记录类别分布的统计信息，不记录完整的样本级别数据
        label_counts = labels_df['label'].value_counts().to_dict()
        logs.append(f"[{datetime.now().isoformat()}] 类别分布: {len(label_counts)} 个类别, 样本数={len(labels_df)}")
        logs.append(f"[{datetime.now().isoformat()}] 准备特征...")
        X, y, feature_names = trainer.prepare_features(
            features_df, labels_df, use_feature_engineering=use_feature_engineering)
        logs.append(f"[{datetime.now().isoformat()}] 特征矩阵: {X.shape[0]} 样本, {X.shape[1]} 特征")
        metrics = trainer.train_model(
            X, y, model_type=model, tune_hyperparams=tune,
            n_trials=trials, cv_splits=cv_splits)
        trainer.save_training_report(metrics, feature_names, start_time, datetime.now())
        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 1)
        logs.append(f"[{end_time.isoformat()}] ML训练完成, 耗时 {duration}s")
        logs.append(f"[{end_time.isoformat()}] 测试集准确率: {metrics.get('test_metrics', {}).get('accuracy', 'N/A')}")
        _update_pipeline_run(run_id, {
            'status': 'completed', 'endTime': end_time.isoformat(), 'duration': duration,
            'logs': logs, 'metrics': sanitize_for_json(metrics), 'modelType': model,
        })
    except Exception as e:
        end_time = datetime.now()
        _update_pipeline_run(run_id, {
            'status': 'failed', 'endTime': end_time.isoformat(),
            'duration': round((end_time - start_time).total_seconds(), 1),
            'logs': logs + [f"[{end_time.isoformat()}] ML训练失败: {e}"], 'error': str(e),
        })
    finally:
        release_task('ml_train')


def _execute_calibration(
    run_id: str, forward_days: int = 5, return_threshold: float = 0.02,
    max_symbols: int = 500, lookback_days: int = 180,
):
    start_time = datetime.now()
    logs: List[str] = [f"[{start_time.isoformat()}] 置信度校准开始: {run_id}"]
    logs.append(f"[{start_time.isoformat()}] 参数: forward_days={forward_days}, max_symbols={max_symbols}, lookback_days={lookback_days}")
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        output_path = str(_V2_ROOT.parent / 'quant' / '.pi-invest' / 'quant' / 'confidence_config.json')
        config = run_calibration(
            forward_days=forward_days, return_threshold=return_threshold,
            max_symbols=max_symbols, lookback_days=lookback_days, output_path=output_path,
        )
        factor_count = len(config.get('factors', {}))
        total_weight = sum(c.get('weight', 0) for c in config.get('factors', {}).values())
        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 1)
        logs.append(f"[{end_time.isoformat()}] 校准完成: {factor_count} 个因子, 总权重={total_weight:.2f}, 耗时 {duration}s")
        _update_pipeline_run(run_id, {
            'status': 'completed', 'endTime': end_time.isoformat(), 'duration': duration,
            'logs': logs, 'factorCount': factor_count, 'totalWeight': total_weight, 'configPath': output_path,
        })
    except Exception as e:
        end_time = datetime.now()
        _update_pipeline_run(run_id, {
            'status': 'failed', 'endTime': end_time.isoformat(),
            'duration': round((end_time - start_time).total_seconds(), 1),
            'logs': logs + [f"[{end_time.isoformat()}] 校准失败: {e}"], 'error': str(e),
        })
    finally:
        release_task('calibrate')


def _execute_signal_generate_v2(run_id: str, strategy_id: int, symbols: List[str]):
    """
    异步执行信号生成（>= 50 stocks）

    Args:
        run_id: 运行ID
        strategy_id: 策略ID
        symbols: 股票代码列表
    """
    start_time = datetime.now()
    logs: List[str] = [f"[{start_time.isoformat()}] 信号生成开始: {run_id}"]
    logs.append(f"[{start_time.isoformat()}] 策略ID={strategy_id}, 股票数={len(symbols)}")

    try:
        from application.services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()

        # 获取策略名
        try:
            strategy_row = service.strategy_repo.get_by_id(strategy_id)
            strategy_name = strategy_row.get('strategy_name') if strategy_row else f'Strategy#{strategy_id}'
        except Exception:
            strategy_name = f'Strategy#{strategy_id}'

        logs.append(f"[{datetime.now().isoformat()}] 策略: {strategy_name}")

        signals = []
        errors = []
        buy = sell = hold = 0

        # 批量生成信号
        for i, symbol in enumerate(symbols, 1):
            try:
                signal = service.generate_signal(
                    strategy_id=strategy_id,
                    symbol=symbol
                )

                if signal:
                    signal_type = signal.get('signal_type', 'hold')
                    if signal_type == 'buy':
                        buy += 1
                    elif signal_type == 'sell':
                        sell += 1
                    else:
                        hold += 1

                    signals.append(signal)
                else:
                    hold += 1

                # 每处理 10 个股票记录一次进度
                if i % 10 == 0:
                    logs.append(f"[{datetime.now().isoformat()}] 进度: {i}/{len(symbols)}")

            except Exception as e:
                logger.warning(f"信号生成失败: {symbol} — {e}")
                hold += 1
                errors.append({'symbol': symbol, 'error': str(e)})

        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 1)

        logs.append(f"[{end_time.isoformat()}] 信号生成完成, 耗时 {duration}s")
        logs.append(f"[{end_time.isoformat()}] 结果: buy={buy}, sell={sell}, hold={hold}, errors={len(errors)}")

        # 更新运行记录
        _update_pipeline_run(run_id, {
            'status': 'completed',
            'endTime': end_time.isoformat(),
            'duration': duration,
            'logs': logs,
            'results': {
                'strategy_id': strategy_id,
                'strategy_name': strategy_name,
                'total': len(symbols),
                'buy': buy,
                'sell': sell,
                'hold': hold,
                'signals': signals[:100],  # 只保存前 100 个信号，避免记录过大
                'errors': errors[:50],  # 只保存前 50 个错误
            }
        })

    except Exception as e:
        end_time = datetime.now()
        logs.append(f"[{end_time.isoformat()}] 信号生成失败: {e}")

        _update_pipeline_run(run_id, {
            'status': 'failed',
            'endTime': end_time.isoformat(),
            'duration': round((end_time - start_time).total_seconds(), 1),
            'logs': logs,
            'error': str(e),
        })


# ═══════════════════════════════════════════════════════════════
# Tasks / Pipeline 管理端点
# ═══════════════════════════════════════════════════════════════


@pipeline_bp.route('/api/tasks/running', methods=['GET'])
def get_running_tasks():
    return api_response({'running_tasks': get_running_tasks_snapshot(), 'count': len(get_running_tasks_snapshot())})


@pipeline_bp.route('/api/pipeline/statistics', methods=['GET'])
@handle_api_error
def get_pipeline_statistics():
    runs = _load_pipeline_runs()
    today = datetime.now().strftime('%Y-%m-%d')
    running = sum(1 for r in runs if r.get('status') == 'running')
    completed_today = sum(1 for r in runs if r.get('status') == 'completed' and (r.get('endTime', '')[:10] == today))
    failed = sum(1 for r in runs if r.get('status') == 'failed')
    durations = [r.get('duration', 0) for r in runs if r.get('duration')]
    return api_response({
        'running_tasks': running, 'completed_today': completed_today, 'failed_tasks': failed,
        'avg_duration': round(sum(durations) / len(durations), 1) if durations else 0,
    })


@pipeline_bp.route('/api/pipeline/tasks/list', methods=['GET'])
@handle_api_error
def get_pipeline_tasks():
    return api_response({
        'items': [
            {'type': 'data_update', 'name': '数据更新', 'description': 'Update market data'},
            {'type': 'factors', 'name': '因子计算', 'description': 'Compute factors'},
            {'type': 'signals', 'name': '信号扫描', 'description': 'Scan for signals'},
            {'type': 'risk', 'name': '风控检查', 'description': 'Risk assessment'},
            {'type': 'calibrate', 'name': '置信度校准', 'description': 'Confidence calibration'},
            {'type': 'ml_train', 'name': 'ML训练', 'description': 'ML model training'},
        ],
    })


@pipeline_bp.route('/api/pipeline/runs/list', methods=['GET'])
@pipeline_bp.route('/api/pipeline/runs', methods=['GET'])  # 添加别名路由
@handle_api_error
def get_pipeline_runs():
    """获取流水线运行历史，支持过滤和分页"""
    page = max(1, request.args.get('page', 1, type=int))
    page_size = min(request.args.get('page_size', 20, type=int), 100)

    # 支持按 run_id 和 status 过滤
    run_id_filter = request.args.get('run_id')
    status_filter = request.args.get('status')

    runs = _load_pipeline_runs()

    # 应用过滤器
    if run_id_filter:
        runs = [r for r in runs if r.get('runId') == run_id_filter or r.get('run_id') == run_id_filter]
    if status_filter:
        runs = [r for r in runs if r.get('status') == status_filter]

    # 按时间倒序排列
    runs.sort(key=lambda x: x.get('startTime', ''), reverse=True)

    total = len(runs)
    start = (page - 1) * page_size
    return api_response({'runs': runs[start:start + page_size], 'total': total, 'page': page, 'page_size': page_size})


@pipeline_bp.route('/api/pipeline/history', methods=['GET'])
@handle_api_error
def pipeline_history_alias():
    return get_pipeline_runs()


@pipeline_bp.route('/api/pipeline/run', methods=['POST'])
@handle_api_error
def create_pipeline_run():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400
    pipeline_data = convert_keys_to_snake(data)
    symbols = pipeline_data.get('symbols', [])
    stages = pipeline_data.get('stages', ['data_update', 'factors', 'signals', 'risk'])
    if not symbols:
        symbols = [s['symbol'] for s in ds.stock.get_all(limit=100)]
    if not symbols:
        return jsonify({'success': False, 'error': 'No symbols provided and no stocks in database'}), 400
    run_id = f"#P-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('pipeline', run_id):
        existing = get_running_tasks_snapshot().get('pipeline', '?')
        return jsonify({'success': False, 'error': f'流水线已在运行中 (run_id={existing})'}), 409
    start_time = datetime.now()
    run = {
        'runId': run_id, 'startTime': start_time.isoformat(), 'status': 'running',
        'stockCount': len(symbols), 'model': pipeline_data.get('model', 'xgboost'),
        'config': {
            'stockRange': ','.join(symbols[:5]) + ('...' if len(symbols) > 5 else ''),
            'days': pipeline_data.get('days', 365), 'model': pipeline_data.get('model', 'xgboost'),
            'threshold': pipeline_data.get('threshold', 0.65),
        },
        'stages': [{'name': s, 'status': 'pending', 'progress': 0, 'detail': ''} for s in stages],
        'logs': [
            f"[{start_time.isoformat()}] 开始运行流水线 {run_id}",
            f"[{start_time.isoformat()}] 配置: 股票数={len(symbols)}, 模型={pipeline_data.get('model', 'xgboost')}",
        ],
    }
    runs = _load_pipeline_runs()
    runs.insert(0, run)
    _save_pipeline_runs(runs)
    threading.Thread(target=_execute_pipeline_stages, args=(run_id, symbols, stages, 'pipeline'), daemon=True).start()
    return jsonify({'success': True, 'data': run}), 202


@pipeline_bp.route('/api/pipeline/trigger', methods=['POST'])
@handle_api_error
def trigger_pipeline():
    return create_pipeline_run()


@pipeline_bp.route('/api/pipeline/<run_id>', methods=['GET'])
@handle_api_error
def get_pipeline_run_detail(run_id):
    run = _get_pipeline_run(run_id)
    if not run:
        return jsonify({'success': False, 'error': 'Pipeline run not found'}), 404
    return api_response(run)


@pipeline_bp.route('/api/pipeline/<run_id>/logs', methods=['GET'])
@handle_api_error
def get_pipeline_run_logs(run_id):
    run = _get_pipeline_run(run_id)
    if not run:
        return jsonify({'success': False, 'error': 'Pipeline run not found'}), 404
    return api_response({'logs': run.get('logs', [])})


# ═══════════════════════════════════════════════════════════════
# CLI 桥接端点
# ═══════════════════════════════════════════════════════════════


@pipeline_bp.route('/api/cli/calibrate', methods=['POST'])
@handle_api_error
def cli_calibrate():
    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)
    run_id = f"#C-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('calibrate', run_id):
        existing = get_running_tasks_snapshot().get('calibrate', '?')
        return jsonify({'success': False, 'error': f'校准已在运行中 (run_id={existing})'}), 409
    now = datetime.now()
    run_record = {
        'runId': run_id, 'run_id': run_id, 'status': 'running', 'taskType': 'calibrate',
        'startTime': now.isoformat(), 'symbols': ['ALL'],
        'params': {
            'forward_days': params.get('forward_days', 5),
            'return_threshold': params.get('return_threshold', 0.02),
            'max_symbols': params.get('max_symbols', 500),
            'lookback_days': params.get('lookback_days', 180),
        },
        'logs': [f'[{now.isoformat()}] 置信度校准触发: {run_id}'],
    }
    runs = _load_pipeline_runs()
    runs.append(run_record)
    _save_pipeline_runs(runs)
    threading.Thread(target=_execute_calibration, args=(run_id,), kwargs={
        'forward_days': params.get('forward_days', 5),
        'return_threshold': params.get('return_threshold', 0.02),
        'max_symbols': params.get('max_symbols', 500),
        'lookback_days': params.get('lookback_days', 180),
    }, daemon=True).start()
    return api_response({'success': True, 'run_id': run_id, 'status': 'running', 'message': f'置信度校准已触发，run_id={run_id}'}), 202


@pipeline_bp.route('/api/cli/factor-compute', methods=['POST'])
@handle_api_error
def cli_factor_compute():
    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)
    symbols_raw = params.get('symbols', '')
    if isinstance(symbols_raw, str) and symbols_raw.strip():
        symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    elif isinstance(symbols_raw, list):
        symbols = symbols_raw
    else:
        symbols = [s['symbol'] for s in ds.stock.get_all(limit=100)]
    if not symbols:
        return jsonify({'success': False, 'error': '请提供 symbols 参数'}), 400
    run_id = f"#F-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('factor_compute', run_id):
        existing = get_running_tasks_snapshot().get('factor_compute', '?')
        return jsonify({'success': False, 'error': f'因子计算已在运行中 (run_id={existing})'}), 409
    now = datetime.now()
    run_record = {
        'runId': run_id, 'run_id': run_id, 'status': 'running', 'taskType': 'factor_compute',
        'startTime': now.isoformat(), 'symbols': symbols,
        'params': {'force': params.get('force', False)},
        'logs': [f'[{now.isoformat()}] 因子计算触发: {run_id}, {len(symbols)} 只股票'],
    }
    runs = _load_pipeline_runs()
    runs.append(run_record)
    _save_pipeline_runs(runs)
    threading.Thread(target=_execute_factor_compute, args=(run_id, symbols, params.get('force', False)), daemon=True).start()
    return api_response({'success': True, 'run_id': run_id, 'status': 'running', 'symbol_count': len(symbols), 'message': f'因子计算已触发，run_id={run_id}'}), 202


@pipeline_bp.route('/api/cli/ml-train', methods=['POST'])
@handle_api_error
def cli_ml_train():
    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)
    run_id = f"#M-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('ml_train', run_id):
        existing = get_running_tasks_snapshot().get('ml_train', '?')
        return jsonify({'success': False, 'error': f'ML训练已在运行中 (run_id={existing})'}), 409
    now = datetime.now()
    run_record = {
        'runId': run_id, 'run_id': run_id, 'status': 'running', 'taskType': 'ml_train',
        'startTime': now.isoformat(),
        'params': {
            'days': params.get('days', 180), 'future_days': params.get('future_days', 5),
            'threshold': params.get('threshold', 0.05), 'model': params.get('model', 'xgboost'),
            'tune': params.get('tune', False), 'trials': params.get('trials', 20),
            'cv_splits': params.get('cv_splits', 5),
            'use_feature_engineering': params.get('use_feature_engineering', True),
        },
        'logs': [f'[{now.isoformat()}] ML训练触发: {run_id}'],
    }
    runs = _load_pipeline_runs()
    runs.append(run_record)
    _save_pipeline_runs(runs)
    threading.Thread(target=_execute_ml_train, args=(run_id,), kwargs={
        'days': params.get('days', 180), 'future_days': params.get('future_days', 5),
        'threshold': params.get('threshold', 0.05), 'model': params.get('model', 'xgboost'),
        'tune': params.get('tune', False), 'trials': params.get('trials', 20),
        'cv_splits': params.get('cv_splits', 5),
        'use_feature_engineering': params.get('use_feature_engineering', True),
    }, daemon=True).start()
    return api_response({'success': True, 'run_id': run_id, 'status': 'running', 'message': f'ML训练已触发，run_id={run_id}'}), 202


@pipeline_bp.route('/api/cli/ml-predict', methods=['POST'])
@handle_api_error
def cli_ml_predict():
    """使用 v2 ML 模型对单只股票进行预测"""
    symbol_raw = request.args.get('symbol') or (request.get_json(silent=True) or {}).get('symbol')
    if not symbol_raw:
        return jsonify({'success': False, 'error': '缺少参数: symbol'}), 400
    symbol = str(symbol_raw).replace('.SH', '').replace('.SZ', '')
    
    from datetime import datetime as _dt, timedelta as _td
    from application.services.ml_pipeline.feature_engineering import FeatureEngineer
    from application.services.ml_pipeline.predictor import MLPredictor
    from adapters.inbound.api.ml_routes import _resolve_latest_version, _strip_suffix, _normalize_kline
    
    model_type = 'xgboost'
    version = _resolve_latest_version(model_type)
    if not version:
        return jsonify({'success': False, 'error': f'没有可用的 {model_type} 模型，请先训练'}), 200
    
    end_date = _dt.now().strftime('%Y-%m-%d')
    start_date = (_dt.now() - _td(days=180)).strftime('%Y-%m-%d')
    
    try:
        rows = ds.kline.get_daily_klines(symbol, start_date, end_date)
    except Exception as e:
        # Surface the real failure (DB connection, polars parsing, etc.) instead
        # of masking it as "no data". A fetch failure is a 500, not a 400.
        logger.error(f"获取 {symbol} K线失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'获取 {symbol} K线数据失败: {e}'}), 500
    
    if not rows:
        return jsonify({'success': False, 'error': f'{symbol} 无K线数据'}), 400
    
    klines_dict = {symbol: [_normalize_kline(r) for r in rows]}
    
    engineer = FeatureEngineer()
    features_df = engineer.extract_features(klines_dict)
    if features_df.empty:
        return jsonify({'success': False, 'error': '无法提取特征'}), 400
    
    _, X = engineer.prepare_features(features_df, handle_missing='fill', fit_scaler=True)
    
    predictor = MLPredictor(model_type=model_type)
    predictor.load_model(version=version)
    
    prediction = predictor.predict(X)
    # prediction is a DataFrame with signal columns
    signal_col = [c for c in prediction.columns if 'signal' in c.lower() or 'pred' in c.lower()]
    prob_col = [c for c in prediction.columns if 'prob' in c.lower() or 'conf' in c.lower()]
    
    signal_val = str(prediction.iloc[0][signal_col[0]]) if signal_col else str(prediction.iloc[0].iloc[0]) if len(prediction.columns) > 0 else 'hold'
    prob_val = float(prediction.iloc[0][prob_col[0]]) if prob_col else 0.5
    
    return api_response({
        'symbol': symbol,
        'signal': signal_val,
        'confidence': round(prob_val, 4),
        'model_type': model_type,
        'version': version,
    })


@pipeline_bp.route('/api/cli/signal-generate', methods=['POST'])
@handle_api_error
def cli_signal_generate():
    """
    使用指定策略对指定股票生成最新信号（支持同步/异步模式）。

    同步模式（< 50 stocks）：流式返回 NDJSON
    异步模式（>= 50 stocks）：后台任务，返回 run_id

    入参：
    {
        "strategy_id": 53,
        "symbols": ["600000", "000425", "000858"]   # 可选，默认从 portfolio 读取
    }

    同步返回（NDJSON stream）：
    {"type": "signal", "data": {"symbol": "600000", "signal_type": "buy", ...}}
    {"type": "error", "data": {"symbol": "000001", "error": "..."}}
    {"type": "summary", "data": {"total": 3, "buy": 1, "sell": 1, "hold": 1}}

    异步返回（202）：
    {
        "success": true,
        "run_id": "signal_20260527_123456",
        "status": "running",
        "message": "后台任务已启动，run_id=signal_20260527_123456"
    }
    """
    data = request.get_json(silent=True) or {}
    data = convert_keys_to_snake(data)

    strategy_id = data.get('strategy_id')
    if not strategy_id:
        return jsonify({'success': False, 'error': '缺少参数: strategy_id'}), 400

    symbols_raw = data.get('symbols', [])
    if isinstance(symbols_raw, str) and symbols_raw.strip():
        symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    elif isinstance(symbols_raw, list):
        symbols = [str(s).strip() for s in symbols_raw if s]
    else:
        # 默认：从 portfolio 读取持仓股
        symbols = []
        try:
            portfolio_path = _PROJECT_ROOT_PATH / '.pi-invest' / 'portfolio.json'
            if portfolio_path.exists():
                with open(portfolio_path) as f:
                    pf = json.load(f)
                symbols = [pos['symbol'] for pos in pf.get('positions', [])]
        except Exception as e:
            logger.warning(f"读取 portfolio 失败: {e}")

    if not symbols:
        return jsonify({'success': False, 'error': '未指定 symbols 且 portfolio 为空'}), 400

    try:
        strategy_id_int = int(strategy_id)
    except (ValueError, TypeError):
        # 内置策略请使用 /api/strategies/execute 接口
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()
        builtin = repo.get_builtin_by_type(str(strategy_id).lower())
        if builtin:
            return jsonify({
                'success': False,
                'error': f"'{strategy_id}' 是内置策略（类型: {builtin['category']}），请使用 /api/strategies/execute 接口",
                'hint': f"POST /api/strategies/execute with {{'symbol':'...', 'strategyName':'{builtin['strategy_type']}'}}"
            }), 400
        return jsonify({'success': False, 'error': f'无效的 strategy_id: {strategy_id}'}), 400

    # 模式选择：< 50 stocks = sync, >= 50 = async
    SYNC_THRESHOLD = 50
    if len(symbols) < SYNC_THRESHOLD:
        # 同步模式：检测 Accept header 决定返回格式
        from application.services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()

        # 获取策略名
        try:
            strategy_row = service.strategy_repo.get_by_id(strategy_id_int)
            strategy_name = strategy_row.get('strategy_name') if strategy_row else f'Strategy#{strategy_id_int}'
        except Exception:
            strategy_name = f'Strategy#{strategy_id_int}'

        # 检测客户端期望的响应格式
        accept_header = request.headers.get('Accept', '')
        prefer_json = 'application/json' in accept_header and 'application/x-ndjson' not in accept_header

        if prefer_json:
            # 返回标准 JSON（用于 TS 工具调用）
            signals = []
            buy = sell = hold = 0

            for symbol in symbols:
                try:
                    signal = service.generate_signal(
                        strategy_id=strategy_id_int,
                        symbol=symbol
                    )

                    if signal:
                        signal_type = signal.get('signal_type', 'hold')
                        if signal_type == 'buy':
                            buy += 1
                        elif signal_type == 'sell':
                            sell += 1
                        else:
                            hold += 1
                        signals.append({'type': 'signal', 'data': signal})
                    else:
                        hold += 1

                except Exception as e:
                    logger.warning(f"信号生成失败: {symbol} — {e}")
                    hold += 1
                    signals.append({
                        'type': 'error',
                        'data': {'symbol': symbol, 'error': str(e)}
                    })

            # 返回标准 JSON
            return jsonify({
                'success': True,
                'signals': signals,
                'summary': {
                    'strategy_id': strategy_id_int,
                    'strategy_name': strategy_name,
                    'total': len(symbols),
                    'buy': buy,
                    'sell': sell,
                    'hold': hold,
                    'generated_at': datetime.now().isoformat()
                }
            })

        else:
            # 返回 NDJSON stream（默认行为，用于 CLI）
            def generate():
                """生成器：逐个生成信号"""
                buy = sell = hold = 0

                for symbol in symbols:
                    try:
                        signal = service.generate_signal(
                            strategy_id=strategy_id_int,
                            symbol=symbol
                        )

                        if signal:
                            signal_type = signal.get('signal_type', 'hold')
                            if signal_type == 'buy':
                                buy += 1
                            elif signal_type == 'sell':
                                sell += 1
                            else:
                                hold += 1

                            # 输出信号行
                            yield json.dumps({'type': 'signal', 'data': signal}, ensure_ascii=False) + '\n'
                        else:
                            # 无信号视为 hold
                            hold += 1

                    except Exception as e:
                        logger.warning(f"信号生成失败: {symbol} — {e}")
                        hold += 1
                        # 输出错误行
                        yield json.dumps({
                            'type': 'error',
                            'data': {'symbol': symbol, 'error': str(e)}
                        }, ensure_ascii=False) + '\n'

                # 输出汇总行
                yield json.dumps({
                    'type': 'summary',
                    'data': {
                        'strategy_id': strategy_id_int,
                        'strategy_name': strategy_name,
                        'total': len(symbols),
                        'buy': buy,
                        'sell': sell,
                        'hold': hold,
                        'generated_at': datetime.now().isoformat()
                    }
                }, ensure_ascii=False) + '\n'

            return Response(generate(), mimetype='application/x-ndjson')

    else:
        # 异步模式：后台任务
        run_id = f"signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        now = datetime.now()

        run_record = {
            'runId': run_id,
            'run_id': run_id,
            'status': 'running',
            'taskType': 'signal_generate',
            'startTime': now.isoformat(),
            'params': {
                'strategy_id': strategy_id_int,
                'symbols': symbols,
                'count': len(symbols)
            },
            'logs': [f'[{now.isoformat()}] 信号生成触发: {run_id}, {len(symbols)} stocks'],
        }

        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)

        # 启动后台线程
        threading.Thread(
            target=_execute_signal_generate_v2,
            args=(run_id, strategy_id_int, symbols),
            daemon=True
        ).start()

        return jsonify({
            'success': True,
            'run_id': run_id,
            'status': 'running',
            'message': f'后台任务已启动，run_id={run_id}'
        }), 202


# ═══════════════════════════════════════════════════════════════
# 数据更新端点
# ═══════════════════════════════════════════════════════════════


@pipeline_bp.route('/api/stocks/data-full-status', methods=['GET'])
@handle_api_error
def data_full_status():
    try:
        pipeline_runs = _load_pipeline_runs()
        latest_runs = sorted(pipeline_runs, key=lambda r: r.get('startTime', ''), reverse=True)[:5]

        # 截断过大的日志，防止响应体积过大
        MAX_LOG_LENGTH = 500  # 每条日志最大字符数
        MAX_LOGS = 20  # 最多返回的日志条数
        for run in latest_runs:
            if 'logs' in run and isinstance(run['logs'], list):
                # 截断每条日志
                run['logs'] = [
                    log[:MAX_LOG_LENGTH] + '...(truncated)' if len(log) > MAX_LOG_LENGTH else log
                    for log in run['logs'][:MAX_LOGS]
                ]
                if len(run.get('logs', [])) > MAX_LOGS:
                    run['logs'].append(f'... ({len(run["logs"]) - MAX_LOGS} more logs omitted)')

        cache_stats = ds.get_cache_stats() if hasattr(ds, 'get_cache_stats') else {}
        return api_response({
            'success': True,
            'pipeline': {'total_runs': len(pipeline_runs), 'latest_runs': latest_runs},
            'cache': cache_stats,
            'db': {'provider': getattr(getattr(ds, '_stock_db', None), 'provider', 'unknown')},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@pipeline_bp.route('/api/stocks/data-status', methods=['GET'])
@handle_api_error
def data_status():
    symbol = request.args.get('symbol', '000001.SZ')
    try:
        result = ds.check_data_integrity(symbol)
        return jsonify(sanitize_for_json(result))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pipeline_bp.route('/api/stocks/data-update-klines', methods=['POST'])
@handle_api_error
def data_update_klines():
    try:
        data = request.get_json(silent=True) or {}
        symbols_raw = data.get('symbols', [])
        days = data.get('days', 730)  # 默认 730 天，与 v1 保持一致

        # 支持字符串(逗号分隔)和列表两种格式
        if isinstance(symbols_raw, str) and symbols_raw.strip():
            symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
        elif isinstance(symbols_raw, list):
            symbols = symbols_raw
        else:
            symbols = []

        # 验证 days 参数
        if not isinstance(days, int) or days < 1:
            return jsonify({'success': False, 'error': 'days 参数必须是大于 0 的整数'}), 400

        run_id = f"#D-{str(uuid.uuid4())[:8].upper()}"
        if not acquire_task('data_update', run_id):
            existing = get_running_tasks_snapshot().get('data_update', '?')
            return jsonify({'success': False, 'error': f'数据更新已在运行中 (run_id={existing})'}), 409
        now = datetime.now().isoformat()
        run_record = {
            'runId': run_id, 'run_id': run_id, 'status': 'running', 'startTime': now,
            'symbols': symbols if symbols else ['ALL'], 'stages': ['data_update'],
            'stages_list': ['data_update'], 'logs': [f'[{now}] K线数据更新触发: {run_id}, days={days}'],
            'signalCount': 0, 'factorCount': 0, 'days': days,
        }
        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)
        threading.Thread(
            target=_execute_pipeline_stages_with_error_handling,
            args=(run_id, symbols if symbols else ['000001.SZ'], ['data_update'], 'data_update'),
            kwargs={'days': days},
            daemon=True,
        ).start()
        return api_response({'success': True, 'run_id': run_id, 'symbols': symbols if symbols else 'ALL', 'days': days, 'message': f'K线更新已触发，run_id={run_id}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# NOTE: /api/data/update route is handled by jobs_bp (api/routes/jobs.py).
# The duplicate route here was dead code (jobs_bp registers first).
# Removed 2026-06-01 to avoid confusion.
