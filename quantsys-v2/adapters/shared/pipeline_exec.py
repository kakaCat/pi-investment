"""Pipeline 后台执行函数（框架无关）— 从 adapters/inbound/api/routes/pipeline.py 解耦而来

Flask 与 FastAPI 两个 API 层共享同一实现。注意：_execute_calibration 调用的
run_calibration 在原 Flask 代码中即未定义（latent bug），原样保留（parity）。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from adapters.shared import ds
from adapters.shared.stores import _update_pipeline_run, _load_pipeline_runs, _save_pipeline_runs, _get_pipeline_run
from adapters.shared.tasks import release_task

logger = logging.getLogger(__name__)


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
                release_task(task_type, run_id)
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
                # 直接使用 AkshareBroker 从数据源获取K线数据
                from domain.brokers.adapters.akshare_broker import AkshareBroker

                broker = AkshareBroker()
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                end_date = datetime.now().strftime('%Y-%m-%d')
                updated = 0
                failed_syms = []

                for sym in symbols:
                    try:
                        logger.info(f"[DATA_UPDATE][{run_id}] Fetching {sym} from {start_date} to {end_date}")

                        # 从数据源获取数据
                        result = broker.get_history(sym, start_date, end_date, 'daily')

                        if result.success and result.data:
                            logger.info(f"[DATA_UPDATE][{run_id}] Got {len(result.data)} records for {sym}")

                            # 转换为数据库格式并保存
                            klines = []
                            clean_symbol = sym.split('.')[0] if '.' in sym else sym
                            for candle in result.data:
                                klines.append({
                                    'symbol': clean_symbol,
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
                                saved_count = ds.kline.save_klines(klines)
                                if saved_count > 0:
                                    updated += 1
                                    logger.info(f"[DATA_UPDATE][{run_id}] Saved {saved_count} records for {sym}")
                                else:
                                    failed_syms.append(f"{sym}(save failed)")
                        else:
                            error_msg = result.error if hasattr(result, 'error') else 'no data'
                            logger.warning(f"[DATA_UPDATE][{run_id}] No data for {sym}: {error_msg}")
                            failed_syms.append(f"{sym}({error_msg})")

                    except Exception as sym_err:
                        logger.error(f"[DATA_UPDATE][{run_id}] Failed to update {sym}: {sym_err}")
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
        release_task(task_type, run_id)


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
        release_task('factor_compute', run_id)


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
        release_task('signal_generate', run_id)


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
        release_task('ml_train', run_id)


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
        release_task('calibrate', run_id)


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
