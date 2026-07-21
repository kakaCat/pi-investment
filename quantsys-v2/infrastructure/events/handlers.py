"""
事件处理器 - 连接事件总线和WebSocket
"""
from infrastructure.events.event_bus import event_bus
from adapters.inbound.api.websocket import get_connection_manager
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def on_quote_update(data: dict):
    """
    行情更新事件处理

    Args:
        data: 包含 symbol, price, volume, timestamp 等字段
    """
    symbol = data.get("symbol")
    logger.info(f"行情更新: {symbol}, 价格: {data.get('price')}")

    try:
        manager = get_connection_manager()
        # 广播给WebSocket客户端
        manager.broadcast(symbol, {
            "type": "quote",
            "symbol": symbol,
            "price": data.get("price"),
            "volume": data.get("volume"),
            "change": data.get("change"),
            "change_pct": data.get("change_pct"),
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"行情更新处理失败: {e}", exc_info=True)


async def on_signal_generated(data: dict):
    """
    信号生成事件处理

    Args:
        data: 包含 symbol, signal, strategy, confidence 等字段
    """
    symbol = data.get("symbol")
    signal = data.get("signal")
    logger.info(f"信号生成: {symbol}, 信号: {signal}, 策略: {data.get('strategy')}")

    try:
        manager = get_connection_manager()
        # 广播给WebSocket客户端
        manager.broadcast(symbol, {
            "type": "signal",
            "symbol": symbol,
            "signal": signal,
            "strategy": data.get("strategy"),
            "confidence": data.get("confidence"),
            "price": data.get("price"),
            "reason": data.get("reason"),
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        })

        # 如果是高置信度信号，也发送全局广播
        if data.get("confidence", 0) >= 0.8:
            manager.broadcast_to_all({
                "type": "high_confidence_signal",
                "symbol": symbol,
                "signal": signal,
                "confidence": data.get("confidence"),
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"信号生成处理失败: {e}", exc_info=True)


async def on_risk_alert(data: dict):
    """
    风险告警事件处理

    Args:
        data: 包含 symbol, risk_type, level, message 等字段
    """
    symbol = data.get("symbol")
    risk_type = data.get("risk_type")
    level = data.get("level", "medium")
    logger.warning(f"风险告警: {symbol}, 类型: {risk_type}, 级别: {level}")

    try:
        manager = get_connection_manager()

        # 发送给订阅该股票的客户端
        if symbol:
            manager.broadcast(symbol, {
                "type": "risk_alert",
                "symbol": symbol,
                "risk_type": risk_type,
                "level": level,
                "message": data.get("message"),
                "value": data.get("value"),
                "threshold": data.get("threshold"),
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            })

        # 高风险告警发送全局广播
        if level in ["high", "critical"]:
            manager.broadcast_to_all({
                "type": "risk_alert",
                "symbol": symbol,
                "risk_type": risk_type,
                "level": level,
                "message": data.get("message"),
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"风险告警处理失败: {e}", exc_info=True)


async def on_trade_executed(data: dict):
    """
    交易执行事件处理

    Args:
        data: 包含 symbol, action, price, quantity 等字段
    """
    symbol = data.get("symbol")
    action = data.get("action")
    logger.info(f"交易执行: {symbol}, 操作: {action}, 价格: {data.get('price')}")

    try:
        manager = get_connection_manager()
        manager.broadcast(symbol, {
            "type": "trade_executed",
            "symbol": symbol,
            "action": action,
            "price": data.get("price"),
            "quantity": data.get("quantity"),
            "status": data.get("status"),
            "execution_id": data.get("execution_id"),
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"交易执行处理失败: {e}", exc_info=True)


async def on_backtest_completed(data: dict):
    """
    回测完成事件处理

    Args:
        data: 包含 backtest_id, strategy, results 等字段
    """
    backtest_id = data.get("backtest_id")
    strategy = data.get("strategy")
    logger.info(f"回测完成: ID={backtest_id}, 策略={strategy}")

    try:
        manager = get_connection_manager()
        manager.broadcast_to_all({
            "type": "backtest_completed",
            "backtest_id": backtest_id,
            "strategy": strategy,
            "symbol": data.get("symbol"),
            "total_return": data.get("total_return"),
            "sharpe_ratio": data.get("sharpe_ratio"),
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"回测完成处理失败: {e}", exc_info=True)


async def on_data_updated(data: dict):
    """
    数据更新事件处理

    Args:
        data: 包含 source, symbols, status 等字段
    """
    source = data.get("source")
    status = data.get("status")
    logger.info(f"数据更新: 来源={source}, 状态={status}")

    try:
        manager = get_connection_manager()
        manager.broadcast_to_all({
            "type": "data_updated",
            "source": source,
            "status": status,
            "symbols_count": data.get("symbols_count"),
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        })
    except RuntimeError as e:
        logger.warning(f"WebSocket管理器未初始化: {e}")
    except Exception as e:
        logger.error(f"数据更新处理失败: {e}", exc_info=True)


def register_handlers():
    """注册所有事件处理器"""
    event_bus.subscribe("quote_update", on_quote_update)
    event_bus.subscribe("signal_generated", on_signal_generated)
    event_bus.subscribe("risk_alert", on_risk_alert)
    event_bus.subscribe("trade_executed", on_trade_executed)
    event_bus.subscribe("backtest_completed", on_backtest_completed)
    event_bus.subscribe("data_updated", on_data_updated)
    logger.info("事件处理器注册完成")


# 自动注册处理器
register_handlers()
