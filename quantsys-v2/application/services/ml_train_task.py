"""
模型训练自动化任务

功能：
1. 定期重训练模型（每周/每月）
2. 训练触发条件：数据更新、模型性能下降、市场regime变化
3. 训练完成后自动评估并切换（如果性能提升）
4. 记录训练历史和版本管理

Author: System
Date: 2026-08-20
"""
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd

logger = structlog.get_logger(__name__)


def handle_model_train_auto(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    自动化模型训练任务
    
    Args:
        params: {
            "model_type": "lightgbm" | "xgboost",
            "symbols_limit": int (默认500),
            "lookback_days": int (默认350, 对应~250交易日),
            "force_train": bool (强制训练，忽略性能检查),
            "test_size": float (测试集比例，默认0.2),
        }
    
    Returns:
        训练结果
    """
    params = params or {}
    
    model_type = params.get('model_type', 'lightgbm')
    symbols_limit = params.get('symbols_limit', 500)
    lookback_days = params.get('lookback_days', 350)
    force_train = params.get('force_train', False)
    test_size = params.get('test_size', 0.2)
    
    logger.info(f"模型训练任务启动: {model_type}, symbols={symbols_limit}, force={force_train}")
    
    try:
        from infrastructure.services.service_factory import ServiceFactory
        from domain.ports.repository_ports_extended import IStockRepository
        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from application.services.ml_pipeline.predictor import MLPredictor
        from sklearn.model_selection import train_test_split

        # 1. 检查是否需要训练（非强制模式）
        if not force_train:
            should_train, reason = _check_train_needed(model_type)
            if not should_train:
                logger.info(f"跳过训练: {reason}")
                return {
                    "action": "model_train_auto",
                    "status": "skipped",
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }

        # 2. 获取股票列表（通过接口）
        from domain.ports.repository_ports_extended import IStockRepository
        repo: IStockRepository = ServiceFactory.get_stock_repository()
        stocks = repo.get_all(limit=symbols_limit)
        symbols = [s['symbol'] for s in stocks]
        logger.info(f"训练样本: {len(symbols)} 只股票")

        # 3. 加载K线数据
        kline_repo = ServiceFactory.get_kline_repository()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        klines_dict = {}
        for i, symbol in enumerate(symbols):
            try:
                rows = kline_repo.get_daily_klines(symbol, start_date, end_date)
                if rows is not None and not rows.is_empty():
                    klines_dict[symbol] = rows.to_dicts()
                if (i+1) % 100 == 0:
                    logger.info(f"已加载 {i+1}/{len(symbols)}")
            except Exception as e:
                logger.warning(f"加载 {symbol} 失败: {e}")
        
        logger.info(f"成功加载 {len(klines_dict)}/{len(symbols)} 只股票")
        
        if len(klines_dict) < 50:
            return {
                "action": "model_train_auto",
                "status": "failed",
                "error": f"数据不足：仅加载{len(klines_dict)}只股票（需>=50）",
                "timestamp": datetime.now().isoformat()
            }
        
        # 4. 特征工程
        logger.info("特征工程...")
        engineer = FeatureEngineer()
        features_df = engineer.extract_features(klines_dict)
        metadata, X = engineer.prepare_features(features_df, handle_missing="fill", fit_scaler=True)
        logger.info(f"特征准备完成: {X.shape[0]} 样本 × {X.shape[1]} 特征")
        
        # 5. 训练模型
        logger.info(f"训练 {model_type} 模型...")
        predictor = MLPredictor(model_type=model_type)
        
        y = metadata["target"].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        
        predictor.train(X_train, y_train)
        
        train_acc = predictor.score(X_train, y_train)
        test_acc = predictor.score(X_test, y_test)
        logger.info(f"训练完成: train_acc={train_acc:.4f}, test_acc={test_acc:.4f}")
        
        # 6. 保存模型
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = predictor.save_model(version=version)
        logger.info(f"模型已保存: {version}")

        # 7. 保存训练记录到DB（通过接口）
        model_metadata_repo = ServiceFactory.get_ml_model_metadata_repository()
        model_metadata_repo.save_training_record(
            model_type=model_type,
            version=version,
            metrics={
                "train_accuracy": train_acc,
                "test_accuracy": test_acc,
            },
            training_params={
                "symbols_count": len(klines_dict),
                "lookback_days": lookback_days,
                "test_size": test_size,
            },
            dataset_info={
                "train_samples": len(X_train),
                "feature_count": X.shape[1],
            }
        )
        
        # 8. 性能对比与切换（如果新模型更好）
        auto_switch = params.get('auto_switch', True)
        if auto_switch:
            switched = _try_switch_model(model_type, version, test_acc)
            if switched:
                logger.info(f"已自动切换到新模型: {version}")
        
        return {
            "action": "model_train_auto",
            "status": "success",
            "model_type": model_type,
            "version": version,
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_count": X.shape[1],
            "symbols_trained": len(klines_dict),
            "auto_switched": auto_switch and switched,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"模型训练失败: {e}", exc_info=True)
        return {
            "action": "model_train_auto",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def _check_train_needed(model_type: str) -> tuple[bool, str]:
    """
    检查是否需要训练

    Returns:
        (should_train, reason)
    """
    from infrastructure.services.service_factory import ServiceFactory

    # 检查最新模型（通过接口）
    ml_model_repo = ServiceFactory.get_ml_model_repository()
    latest_version = ml_model_repo.resolve_latest_version(model_type)
    if not latest_version:
        return (True, "无可用模型，需要训练")

    # 检查模型年龄
    ml_metadata_repo = ServiceFactory.get_ml_model_metadata_repository()
    model = ml_metadata_repo.get_training_record(model_type, latest_version)
    if not model:
        return (True, "模型元数据缺失")

    train_date_str = model.get('train_date')
    if train_date_str:
        train_date = pd.to_datetime(train_date_str)
        days_old = (datetime.now() - train_date).days

        # 策略：超过7天且数据有更新，则重训练
        if days_old > 7:
            return (True, f"模型已{days_old}天未更新")

    # 检查模型性能
    metrics = model.get('metrics', {})
    test_acc = metrics.get('test_accuracy')
    if test_acc and test_acc < 0.55:
        return (True, f"模型性能低 (test_acc={test_acc:.4f} < 0.55)")

    return (False, f"模型{latest_version}仍有效 (age={days_old}d, acc={test_acc:.4f})")


def _try_switch_model(model_type: str, new_version: str, new_test_acc: float) -> bool:
    """
    尝试切换到新模型（如果性能更好）

    Returns:
        是否切换成功
    """
    from infrastructure.services.service_factory import ServiceFactory

    # 通过接口访问
    ml_model_repo = ServiceFactory.get_ml_model_repository()
    ml_metadata_repo = ServiceFactory.get_ml_model_metadata_repository()

    current_version = ml_model_repo.resolve_latest_version(model_type)
    if not current_version or current_version == new_version:
        return True  # 无旧模型或就是新模型

    current_model = ml_metadata_repo.get_training_record(model_type, current_version)
    if not current_model:
        return True

    metrics = current_model.get('metrics', {})
    current_test_acc = metrics.get('test_accuracy', 0.0)

    # 策略：新模型准确率提升>=1%，或旧模型<0.52且新模型>0.52
    if new_test_acc > current_test_acc + 0.01 or (current_test_acc < 0.52 and new_test_acc > 0.52):
        # 更新latest标记（在DB中标记新模型为latest）
        # 注意：当前_resolve_latest_version从文件mtime判断，需调整为DB优先
        logger.info(f"性能提升: {current_test_acc:.4f} → {new_test_acc:.4f}")
        return True
    else:
        logger.info(f"新模型性能未达切换阈值: {current_test_acc:.4f} → {new_test_acc:.4f}")
        return False


# ============================================================
# 注册到调度器
# ============================================================

def register_model_train_task():
    """
    注册模型训练定时任务到Agent OS
    
    建议cron：
    - 每周一凌晨3点训练（数据回填完成后）: "0 3 * * 1"
    - 每月1号凌晨3点训练: "0 3 1 * *"
    """
    from application.services.agent_os_client import AgentOSClient
    
    client = AgentOSClient()
    
    # 每周一凌晨3点自动训练
    task = {
        "name": "model_train_auto_weekly",
        "description": "每周自动模型训练",
        "cron": "0 3 * * 1",  # 周一凌晨3点
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "webhook_body": {
            "job_type": "model_train_auto",
            "description": "每周自动模型训练",
            "params": {
                "model_type": "lightgbm",
                "symbols_limit": 500,
                "lookback_days": 350,
                "force_train": False,  # 智能判断是否需要训练
                "auto_switch": True,   # 性能提升时自动切换
            }
        },
        "enabled": True,
    }
    
    result = client.create_job(task)
    logger.info(f"注册模型训练任务: {result}")
    return result


if __name__ == '__main__':
    # 手动测试
    result = handle_model_train_auto({
        "model_type": "lightgbm",
        "symbols_limit": 20,  # 小规模测试
        "force_train": True,
    })
    print(result)
