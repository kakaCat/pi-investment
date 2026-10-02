"""模型训练任务处理器

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401
from application.services.scheduler_tasks_training_guard import _check_train_needed, _release_thread_session  # noqa: F401

def handle_model_train(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """模型训练任务

    2026-09-05 修复（w-8366e526）：此前为"框架就绪，需要完整ML pipeline"假实现
    （默认 xgboost、不训练不落库）。现委托下方 handle_model_train_auto 唯一真实实现
    （lightgbm 全流程：特征工程 → 训练 → 保存 → 元数据落库 → 性能对比自动切换）。
    保留 model_type 透传，但默认改为 lightgbm（xgboost 为 2026-05 旧模型，不可信）。
    """
    params = params or {}
    if 'model_type' not in params:
        params = {**params, 'model_type': 'lightgbm'}
    return handle_model_train_auto(params)


def handle_model_train_auto(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    自动化模型训练任务
    
    Args:
        params: {
            "model_type": "lightgbm" | "xgboost",
            "symbols_limit": int (默认500),
            "lookback_days": int (默认350),
            "force_train": bool (强制训练，忽略性能检查),
            "test_size": float (测试集比例，默认0.2),
            "auto_switch": bool (性能提升时自动切换，默认True),
        }
    """
    params = params or {}
    
    model_type = params.get('model_type', 'lightgbm')
    symbols_limit = params.get('symbols_limit', 500)
    lookback_days = params.get('lookback_days', 350)
    force_train = params.get('force_train', False)
    test_size = params.get('test_size', 0.2)
    auto_switch = params.get('auto_switch', True)
    
    logger.info(f"模型训练任务启动: {model_type}, symbols={symbols_limit}, force={force_train}")
    
    try:
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository
        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from application.services.ml_pipeline.predictor import MLPredictor
        from adapters.shared.ml_helpers import _get_model_repo
        from sklearn.model_selection import train_test_split
        
        # 1. 检查是否需要训练（非强制模式）
        if not force_train:
            should_train, reason = _check_train_needed(model_type)
            if not should_train:
                result_dict = {
                    "action": "model_train_auto",
                    "status": "skipped",
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 2026-09-14（REQ-a458a6 t5）：skipped 不再单发飞书 —— 门控未到期时
                # 每个周期有 6/7 天是 skipped，逐条推送等于噪声（实证：09-06~09-13
                # 每日一条“跳过原因”）。完整 reason 仍落在 scheduler_runs/result；
                # success / failed 保持即时推送。
                logger.info(f"跳过训练（不推送飞书，reason 见 runs）: {reason}")

                return result_dict
        
        # 2. 获取股票列表
        repo = StockORMRepository()
        stocks = repo.get_all(limit=symbols_limit)
        symbols = [s['symbol'] for s in stocks]
        logger.info(f"训练样本: {len(symbols)} 只股票")
        
        # 3. 加载K线和因子数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        # 加载K线（用于计算target）
        klines_dict = {}
        for i, symbol in enumerate(symbols):
            try:
                rows = KlineORMRepository().get_daily_klines(symbol, start_date, end_date)
                if rows is not None and not rows.is_empty():
                    klines_dict[symbol] = [dict(r) for r in rows.to_dicts()]
                if (i+1) % 100 == 0:
                    logger.info(f"已加载K线 {i+1}/{len(symbols)}")
            except Exception as e:
                logger.warning(f"加载K线 {symbol} 失败: {e}")
        
        logger.info(f"成功加载K线 {len(klines_dict)}/{len(symbols)} 只股票")
        
        if len(klines_dict) < 50:
            return {
                "action": "model_train_auto",
                "status": "failed",
                "error": f"数据不足：仅加载{len(klines_dict)}只股票（需>=50）",
                "timestamp": datetime.now().isoformat()
            }
        
        # 4. 加载因子数据并构建训练集（参考ml_async.py）
        logger.info("加载因子数据...")
        import pandas as pd
        all_rows = []
        
        for i, symbol in enumerate(klines_dict.keys()):
            try:
                factors_data = FactorORMRepository().get_factors_range(symbol, start_date, end_date)
                if factors_data is None or factors_data.is_empty():
                    continue
                
                # 构建因子字典（按日期）
                by_date = {}
                for fv in factors_data.iter_rows(named=True):
                    d = str(fv.get("factor_date") or fv.get("date", ""))
                    if not d:
                        continue
                    by_date.setdefault(d, {})[fv["factor_name"]] = float(fv.get("factor_value", 0) or 0)
                
                # 构建收盘价字典
                close_map = {}
                for k in klines_dict[symbol]:
                    d = str(k.get("date", k.get("trade_date", "")))
                    close_map[d] = float(k.get("close", 0))
                
                # 生成训练样本（当日因子 → 次日涨跌标签）
                sorted_dates = sorted(by_date.keys())
                for j in range(len(sorted_dates) - 1):
                    cur_date = sorted_dates[j]
                    next_date = sorted_dates[j + 1]
                    cur_close = close_map.get(cur_date, 0)
                    next_close = close_map.get(next_date, 0)
                    if cur_close <= 0:
                        continue
                    
                    row = dict(by_date[cur_date])
                    row["__target"] = 1 if next_close > cur_close else 0
                    row["__symbol"] = symbol
                    row["__date"] = cur_date
                    all_rows.append(row)
                
                if (i+1) % 100 == 0:
                    logger.info(f"已处理因子 {i+1}/{len(klines_dict)}")
                    
            except Exception as e:
                logger.warning(f"处理因子 {symbol} 失败: {e}")
        
        logger.info(f"生成训练样本: {len(all_rows)} 条")
        
        if len(all_rows) < 100:
            return {
                "action": "model_train_auto",
                "status": "failed",
                "error": f"有效样本不足：仅{len(all_rows)}条（需>=100）",
                "timestamp": datetime.now().isoformat()
            }
        
        # 5. 特征工程
        logger.info("特征工程...")
        X = pd.DataFrame(all_rows)
        y = X.pop("__target")
        X = X.drop(columns=["__symbol", "__date"], errors="ignore")
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=X.columns)
        logger.info(f"特征准备完成: {X.shape[0]} 样本 × {X.shape[1]} 特征")
        
        # 6. 训练模型
        logger.info(f"训练 {model_type} 模型...")
        from application.services.ml_pipeline.trainer import MLTrainer
        from sklearn.model_selection import train_test_split
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        
        trainer = MLTrainer(model_type=model_type)
        results = trainer.train(X, y, test_size=test_size, params={})
        
        
        train_acc = results.get("train_accuracy", 0)
        test_acc = results.get("test_accuracy", 0)
        logger.info(f"训练完成: train_acc={train_acc:.4f}, test_acc={test_acc:.4f}")
        
        # 7. 保存模型
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            model_path = trainer.save_model(version=version)
            if model_path is None:
                model_path = version
        except Exception as e:
            logger.warning(f"模型文件保存失败: {e}")
            model_path = version  # 兜底：避免下方 create 引用未定义变量
        logger.info(f"模型已保存: {version}")
        
        # 7. 保存训练记录到DB（用 MlModelORMRepository.save_model 真实 upsert；
        #    BaseORMRepository.create(dict) 静默吞 dict → 元数据永不落库，勿再用）
        model_repo = _get_model_repo()
        try:
            model_repo.save_model({
                "model_type": model_type,
                "version": version,
                "model_path": str(model_path),
                "train_accuracy": train_acc,
                "test_accuracy": test_acc,
                "train_samples": len(X_train),
                "feature_count": X.shape[1],
                "training_params": json.dumps({
                    "symbols_count": len(klines_dict),
                    "lookback_days": lookback_days,
                    "test_size": test_size,
                }, ensure_ascii=False),
                "training_report": json.dumps(results, ensure_ascii=False, default=str),
                "status": "ready",
            })
            logger.info(f"训练元数据已落库: {model_type}/{version}")
        except Exception as e:
            logger.warning(f"训练元数据落库失败: {e}")
        
        # 8. 性能对比（记录，不自动切换，需人工确认）
        switched = False
        if auto_switch:
            switched = _try_switch_model(model_type, version, test_acc)
            if switched:
                logger.info(f"已自动切换到新模型: {version}")
        
        result_dict = {
            "action": "model_train_auto",
            "status": "success",
            "model_type": model_type,
            "version": version,
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "train_samples": len(all_rows),
            "test_samples": int(len(all_rows) * test_size),
            "feature_count": X.shape[1],
            "symbols_trained": len(klines_dict),
            "auto_switched": switched,
            "timestamp": datetime.now().isoformat()
        }
        
        # 发送通知
        try:
            from application.notification.notification_factory import get_notification_facade
            get_notification_facade().send_ml_train_notification(result_dict)
        except Exception as e:
            logger.warning(f"发送通知失败: {e}")
        
        return result_dict

    except Exception as e:
        logger.error(f"模型训练失败: {e}", exc_info=True)
        result_dict = {
            "action": "model_train_auto",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            from application.notification.notification_factory import get_notification_facade
            get_notification_facade().send_ml_train_notification(result_dict)
        except Exception as e_notify:
            logger.warning(f"发送通知失败: {e_notify}")
        
        return result_dict

    finally:
        # 训练全程归还会话（2026-09-13，w-32314d00，事件 a6780ec3）：本函数跑在
        # asyncio.to_thread 的池化线程上，训练动辄数分钟且中途有大量读操作（autobegin 事务），
        # 不释放就会一直占连接。此前只在 _check_train_needed 内做了一个检查点
        # （提前 return 的分支覆盖不到），这里补统一的出口释放。
        _release_thread_session()


def _try_switch_model(model_type: str, new_version: str, new_test_acc: float) -> bool:
    """尝试切换到新模型（如果性能更好）"""
    from adapters.shared.ml_helpers import _get_model_repo, _resolve_latest_version
    
    current_version = _resolve_latest_version(model_type)
    if not current_version or current_version == new_version:
        return True
    
    repo = _get_model_repo()
    current_model = repo.get_by_type_version(model_type, current_version)
    if not current_model:
        return True
    
    current_test_acc = current_model.get('test_accuracy', 0.0)
    
    # 策略：新模型准确率提升>=1%
    if new_test_acc > current_test_acc + 0.01:
        logger.info(f"性能提升: {current_test_acc:.4f} → {new_test_acc:.4f}")
        return True
    else:
        logger.info(f"新模型性能未达切换阈值")
        return False


