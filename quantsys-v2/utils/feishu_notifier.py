"""
飞书通知器 - V13/V14 策略通知接口

提供简洁的飞书通知接口，支持：
- 文本消息
- 调仓通知
- 风险预警
- 验证通知
- 周报
- 总结报告
"""
import os
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书通知器

    简化版通知接口，专为 V13/V14 策略设计。
    """

    def __init__(self, webhook_url: str, timeout: int = 10):
        """初始化飞书通知器

        Args:
            webhook_url: 飞书机器人 Webhook URL
            timeout: 请求超时时间（秒）
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")

    def send_text(self, text: str) -> bool:
        """发送文本消息

        Args:
            text: 消息内容

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.warning("Feishu webhook not configured, skipping")
            return False

        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        return self._send(payload)

    def send_card(self, title: str, content: str, urgency: str = "normal") -> bool:
        """发送卡片消息

        Args:
            title: 卡片标题
            content: 卡片内容（支持 Markdown）
            urgency: 紧急程度 normal/high/critical

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.warning("Feishu webhook not configured, skipping")
            return False

        color_map = {
            "normal": "blue",
            "high": "orange",
            "critical": "red",
            "success": "green"
        }
        color = color_map.get(urgency, "blue")

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content}
                    }
                ]
            }
        }
        return self._send(payload)

    def send_rebalance_notification(self, data: Dict[str, Any]) -> bool:
        """发送调仓通知

        Args:
            data: 调仓数据，包含：
                - date: 调仓日期
                - positions: 持仓数量
                - top_stocks: 优质股票列表 [(symbol, score, weight, reason), ...]
                - buy_trades: 买入交易 [(symbol, quantity, price), ...]
                - sell_trades: 卖出交易 [(symbol, quantity, price), ...]

        Returns:
            是否发送成功
        """
        date = data.get('date', 'N/A')
        positions = data.get('positions', 0)
        top_stocks = data.get('top_stocks', [])
        buy_trades = data.get('buy_trades', [])
        sell_trades = data.get('sell_trades', [])

        # 构建内容
        content_parts = [
            f"**📅 日期**: {date}",
            f"**📊 持仓数**: {positions}",
            ""
        ]

        # 优质股票
        if top_stocks:
            content_parts.append("**🎯 优质股票**")
            for stock in top_stocks[:5]:  # 最多显示5个
                if isinstance(stock, (list, tuple)) and len(stock) >= 4:
                    symbol, score, weight, reason = stock[:4]
                    content_parts.append(f"• {symbol}: 得分={score:.4f}, 权重={weight:.2%} {reason}")
                elif isinstance(stock, dict):
                    symbol = stock.get('symbol', 'N/A')
                    score = stock.get('score', 0)
                    content_parts.append(f"• {symbol}: 得分={score:.4f}")
            content_parts.append("")

        # 买入交易
        if buy_trades:
            content_parts.append("**🟢 买入**")
            for trade in buy_trades:
                if isinstance(trade, (list, tuple)) and len(trade) >= 3:
                    symbol, quantity, price = trade[:3]
                    content_parts.append(f"• {symbol}: {quantity}股 @ ¥{price:.2f}")
            content_parts.append("")

        # 卖出交易
        if sell_trades:
            content_parts.append("**🔴 卖出**")
            for trade in sell_trades:
                if isinstance(trade, (list, tuple)) and len(trade) >= 3:
                    symbol, quantity, price = trade[:3]
                    content_parts.append(f"• {symbol}: {quantity}股 @ ¥{price:.2f}")

        content = "\n".join(content_parts)
        title = f"📊 调仓通知 - {date}"

        return self.send_card(title, content, urgency="normal")

    def send_risk_alert(self, data: Dict[str, Any]) -> bool:
        """发送风险预警

        Args:
            data: 风险数据，包含：
                - trigger: 触发原因
                - losing_stocks: 亏损股票列表

        Returns:
            是否发送成功
        """
        trigger = data.get('trigger', '未知风险')
        losing_stocks = data.get('losing_stocks', [])

        content_parts = [
            f"**⚠️ 触发原因**: {trigger}",
            ""
        ]

        if losing_stocks:
            content_parts.append("**📉 亏损股票**")
            for stock in losing_stocks:
                content_parts.append(f"• {stock}")

        content = "\n".join(content_parts)
        title = f"🚨 风险预警 - {trigger}"

        return self.send_card(title, content, urgency="critical")

    def send_verification_notification(self, data: Dict[str, Any]) -> bool:
        """发送验证通知

        Args:
            data: 验证数据

        Returns:
            是否发送成功
        """
        rebalance_date = data.get('rebalance_date', 'N/A')
        verify_date = data.get('verify_date', 'N/A')
        predictions = data.get('predictions', [])
        period_return = data.get('period_return', 0)
        index_return = data.get('index_return', 0)

        content_parts = [
            f"**📅 调仓日**: {rebalance_date}",
            f"**📅 验证日**: {verify_date}",
            f"**📈 期间收益**: {period_return:.2%}",
            f"**📊 指数收益**: {index_return:.2%}",
            ""
        ]

        if predictions:
            content_parts.append("**🎯 预测验证**")
            for pred in predictions[:5]:
                if isinstance(pred, (list, tuple)) and len(pred) >= 3:
                    symbol, predicted, actual = pred[:3]
                    content_parts.append(f"• {symbol}: 预测={predicted:.2%}, 实际={actual:.2%}")

        content = "\n".join(content_parts)
        title = f"✅ 验证通知 - {rebalance_date}"

        return self.send_card(title, content, urgency="normal")

    def send_weekly_report(self, data: Dict[str, Any]) -> bool:
        """发送周报

        Args:
            data: 周报数据

        Returns:
            是否发送成功
        """
        week = data.get('week', 'N/A')
        weekly_return = data.get('weekly_return', 0)
        max_drawdown = data.get('max_drawdown', 0)
        win_rate = data.get('win_rate', 0)
        trade_count = data.get('trade_count', 0)
        win_count = data.get('win_count', 0)

        content = f"""**📈 本周表现**
• 周收益率: {weekly_return:.2%}
• 最大回撤: {max_drawdown:.2%}
• 交易胜率: {win_rate:.2%}
• 交易次数: {trade_count}
• 盈利次数: {win_count}"""

        title = f"📊 投资周报 - 第{week}周"
        return self.send_card(title, content, urgency="normal")

    def send_final_summary(self, data: Dict[str, Any]) -> bool:
        """发送总结报告

        Args:
            data: 总结数据

        Returns:
            是否发送成功
        """
        start_date = data.get('start_date', 'N/A')
        end_date = data.get('end_date', 'N/A')
        cumulative_return = data.get('cumulative_return', 0)
        prediction_accuracy = data.get('prediction_accuracy', 0)
        conclusion = data.get('conclusion', 'N/A')
        suggestion = data.get('suggestion', 'N/A')

        content = f"""**📅 观察期**: {start_date} ~ {end_date}
**📈 累计收益**: {cumulative_return:.2%}
**🎯 预测准确率**: {prediction_accuracy:.2%}

**📝 结论**: {conclusion}

**💡 建议**:
{suggestion}"""

        title = "📋 观察期总结报告"
        return self.send_card(title, content, urgency="normal")

    def _send(self, payload: Dict[str, Any]) -> bool:
        """发送消息到飞书

        Args:
            payload: 消息载荷

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.warning("Feishu webhook not configured")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )

            result = response.json()

            if result.get('code') == 0 or result.get('StatusCode') == 0:
                logger.info("Feishu notification sent successfully")
                return True
            else:
                logger.error(f"Feishu notification failed: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Feishu notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Feishu notification: {e}")
            return False


def create_notifier_from_config(config: Dict[str, Any]) -> Optional[FeishuNotifier]:
    """从配置创建飞书通知器

    Args:
        config: 配置字典，可能包含：
            - feishu_webhook_url: 飞书 Webhook URL
            - feishu: {"webhook_url": "..."}

    Returns:
        FeishuNotifier 实例，如果未配置则返回 None
    """
    # 尝试从不同路径获取 webhook URL
    webhook_url = None

    # 直接在顶层
    if 'feishu_webhook_url' in config:
        webhook_url = config['feishu_webhook_url']
    # 在 feishu 子字典中
    elif 'feishu' in config and isinstance(config['feishu'], dict):
        webhook_url = config['feishu'].get('webhook_url')

    # 从环境变量获取
    if not webhook_url:
        webhook_url = os.getenv('FEISHU_WEBHOOK_URL')

    if not webhook_url:
        logger.warning("Feishu webhook URL not found in config or environment")
        return None

    return FeishuNotifier(webhook_url)
