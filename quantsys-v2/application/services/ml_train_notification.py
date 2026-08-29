"""
模型训练通知服务

功能：
1. 训练完成后发送飞书通知
2. 训练失败告警
3. 性能监控告警（准确率过低）

Author: System
Date: 2026-08-20
"""
import structlog
from typing import Dict, Any
import requests
from datetime import datetime

from infrastructure.config.settings import get_settings

logger = structlog.get_logger(__name__)


def send_feishu_notification(
    webhook_url: str,
    title: str,
    content: str,
    msg_type: str = "interactive"
) -> bool:
    """
    发送飞书消息
    
    Args:
        webhook_url: 飞书机器人webhook地址
        title: 消息标题
        content: 消息内容（支持markdown）
        msg_type: 消息类型（text/interactive）
    
    Returns:
        是否发送成功
    """
    try:
        if msg_type == "interactive":
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": "blue"  # blue/green/red/orange
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": content
                        }
                    ]
                }
            }
        else:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": f"{title}\n\n{content}"
                }
            }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"飞书通知发送成功: {title}")
            return True
        else:
            logger.error(f"飞书通知发送失败: {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"飞书通知发送异常: {e}")
        return False


def notify_train_success(result: Dict[str, Any], webhook_url: str = None) -> bool:
    """
    训练成功通知
    
    Args:
        result: 训练结果
        webhook_url: 飞书webhook（可从环境变量读取）
    """
    if not webhook_url:
        webhook_url = get_settings().external.feishu_webhook_model_train
        if not webhook_url:
            logger.warning("未配置飞书webhook，跳过通知")
            return False
    
    version = result.get("version")
    train_acc = result.get("train_accuracy")
    test_acc = result.get("test_accuracy")
    symbols_count = result.get("symbols_trained")
    auto_switched = result.get("auto_switched", False)
    
    # 构建消息
    title = "✅ 模型训练成功"
    
    content = f"""
**模型版本**: {version}
**训练样本**: {symbols_count} 只股票
**训练准确率**: {train_acc:.2%}
**测试准确率**: {test_acc:.2%}
**自动切换**: {'✅ 已切换' if auto_switched else '⊙ 未切换（性能提升不足）'}

**训练时间**: {result.get('timestamp', datetime.now().isoformat())}
"""
    
    # 性能警告
    if test_acc < 0.52:
        title = "⚠️ 模型训练成功（性能低）"
        content += f"\n⚠️ **警告**: 测试准确率低于52%，建议检查特征质量"
    
    return send_feishu_notification(webhook_url, title, content)


def notify_train_failure(result: Dict[str, Any], webhook_url: str = None) -> bool:
    """
    训练失败告警
    
    Args:
        result: 训练结果
        webhook_url: 飞书webhook
    """
    if not webhook_url:
        webhook_url = get_settings().external.feishu_webhook_model_train
        if not webhook_url:
            return False
    
    error = result.get("error", "未知错误")
    
    title = "❌ 模型训练失败"
    content = f"""
**错误信息**: {error}

**失败时间**: {result.get('timestamp', datetime.now().isoformat())}

**建议检查**:
- 数据可用性（因子数据是否充足）
- 后端日志（/tmp/quantsys-v2.log）
- 数据库连接
"""
    
    return send_feishu_notification(webhook_url, title, content)


def notify_train_skipped(result: Dict[str, Any], webhook_url: str = None) -> bool:
    """
    训练跳过通知（可选，避免打扰）
    
    Args:
        result: 训练结果
        webhook_url: 飞书webhook
    """
    if not webhook_url:
        webhook_url = get_settings().external.feishu_webhook_model_train
        if not webhook_url:
            return False
    
    # 跳过通知默认不发送，避免过多打扰
    # 如需启用，取消下面的注释
    # reason = result.get("reason", "未知原因")
    # title = "⊙ 模型训练跳过"
    # content = f"**原因**: {reason}\n\n**时间**: {result.get('timestamp')}"
    # return send_feishu_notification(webhook_url, title, content)
    
    return True


def notify_train_result(result: Dict[str, Any], webhook_url: str = None) -> bool:
    """
    根据训练结果自动选择通知类型
    
    Args:
        result: 训练结果字典
        webhook_url: 飞书webhook（可选）
    
    Returns:
        是否发送成功
    """
    status = result.get("status")
    
    if status == "success":
        return notify_train_success(result, webhook_url)
    elif status == "failed":
        return notify_train_failure(result, webhook_url)
    elif status == "skipped":
        return notify_train_skipped(result, webhook_url)
    else:
        logger.warning(f"未知训练状态: {status}")
        return False


# ==================== 性能监控告警 ====================

def check_model_performance_alert(webhook_url: str = None) -> bool:
    """
    检查当前模型性能，低于阈值时告警
    
    Args:
        webhook_url: 飞书webhook
    
    Returns:
        是否需要告警
    """
    if not webhook_url:
        webhook_url = get_settings().external.feishu_webhook_model_train
        if not webhook_url:
            return False
    
    try:
        from infrastructure.services.service_factory import ServiceFactory

        model_type = "lightgbm"

        # 通过接口访问
        ml_model_repo = ServiceFactory.get_ml_model_repository()
        ml_metadata_repo = ServiceFactory.get_ml_model_metadata_repository()

        latest_version = ml_model_repo.resolve_latest_version(model_type)

        if not latest_version:
            return False

        model = ml_metadata_repo.get_training_record(model_type, latest_version)

        if not model:
            return False

        metrics = model.get('metrics', {})
        test_acc = metrics.get('test_accuracy', 0)
        train_date = model.get('train_date')

        # 阈值：测试准确率 < 0.50
        if test_acc < 0.50:
            title = "🚨 模型性能告警"
            content = f"""
**当前模型**: {latest_version}
**测试准确率**: {test_acc:.2%} (阈值: 50%)
**训练日期**: {train_date}

**建议**: 立即重新训练模型
"""
            send_feishu_notification(webhook_url, title, content)
            return True

        return False
        
    except Exception as e:
        logger.error(f"性能检查失败: {e}")
        return False


if __name__ == '__main__':
    # 测试通知
    test_result = {
        "status": "success",
        "version": "20260820_030015",
        "train_accuracy": 0.6234,
        "test_accuracy": 0.5812,
        "symbols_trained": 480,
        "auto_switched": True,
        "timestamp": datetime.now().isoformat()
    }
    
    # 需要配置环境变量 FEISHU_WEBHOOK_MODEL_TRAIN
    notify_train_result(test_result)
