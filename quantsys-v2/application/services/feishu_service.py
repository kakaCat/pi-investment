"""
飞书通知服务
支持文本、卡片、交互式消息推送
"""
import json
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime
from infrastructure.config.settings import get_settings

logger = structlog.get_logger(__name__)


class FeishuNotificationService:
    """飞书通知服务

    功能：
    1. 发送文本消息
    2. 发送富文本卡片
    3. 发送交互式卡片
    4. 发送每日/周报
    5. 发送告警通知
    """

    def __init__(self, webhook_url: str = None, bot_token: str = None):
        """初始化飞书服务

        Args:
            webhook_url: 飞书机器人 Webhook URL
            bot_token: 飞书机器人 Token（用于高级功能）
        """
        config = get_settings()
        self.webhook_url = webhook_url or config.external.feishu_webhook_url
        self.bot_token = bot_token or getattr(config.external, 'feishu_bot_token', None)

        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")

    def send_text(
        self,
        text: str,
        mention_all: bool = False,
        mention_users: List[str] = None
    ) -> bool:
        """发送文本消息

        Args:
            text: 消息内容
            mention_all: 是否 @所有人
            mention_users: 要 @的用户ID列表

        Returns:
            是否发送成功

        2026-09-11（w-23c70356）：改为经 NotificationFacade 统一投递。
            原实现直接 requests.post 飞书 webhook，绕过 DDD 通知域（违反 CLAUDE.md
            「所有通知必须经 NotificationFacade」铁律），也拿不到「Agent OS 优先、
            飞书降级」的策略路由。注意：mention_users 门面暂不支持，只透传 mention_all。
        """
        try:
            # 统一入口：application/notification/legacy_adapters.py 的桥接层
            # （内部转 NotificationFacade，2026-09-11 w-23c70356 起真正被启用）
            from application.notification.legacy_adapters import get_legacy_feishu_service

            return bool(get_legacy_feishu_service().send_text(text, mention_all=mention_all))
        except Exception as e:  # noqa: BLE001
            logger.error(f"legacy adapter send_text failed: {e}")
            return False

    def send_card(
        self,
        title: str,
        content: str,
        urgency: str = "normal",
        actions: List[Dict] = None,
        extra_elements: List[Dict] = None
    ) -> bool:
        """发送卡片消息

        Args:
            title: 卡片标题
            content: 卡片内容（支持 Markdown）
            urgency: 紧急程度 normal/high/critical
            actions: 操作按钮列表
            extra_elements: 额外的卡片元素

        Returns:
            是否发送成功

        2026-09-11（w-23c70356）：改为经 NotificationFacade 统一投递（同 send_text）。
            本类所有报表/告警方法（send_daily_report/send_weekly_report/send_alert/
            send_premarket_report）最终都汇聚到本方法，因此一并收敛到 DDD 通知域。
            差异说明：extra_elements 门面不支持，会忽略并记 debug 日志。
        """
        try:
            from application.notification.legacy_adapters import get_legacy_feishu_service

            return bool(get_legacy_feishu_service().send_card(
                title=title,
                content=content,
                urgency=urgency,
                actions=actions,
                extra_elements=extra_elements
            ))
        except Exception as e:  # noqa: BLE001
            logger.error(f"legacy adapter send_card failed: {e}")
            return False

    def send_daily_report(self, report_data: Dict[str, Any]) -> bool:
        """发送每日投资报告

        Args:
            report_data: 报告数据字典

        Returns:
            是否发送成功
        """
        date = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))

        # 构建报告内容
        content = f"""**📈 市场表现**
上证指数: {report_data.get('sh_index_change', 'N/A')}
深证成指: {report_data.get('sz_index_change', 'N/A')}
北向资金: {report_data.get('north_flow', 'N/A')}亿元

**💰 持仓收益**
今日收益: {report_data.get('daily_pnl', 'N/A')}
总收益率: {report_data.get('total_return', 'N/A')}
持仓股票: {report_data.get('position_count', 0)}只

**📊 交易信号**
新增信号: {report_data.get('new_signals', 0)}个
优质机会: {report_data.get('opportunities', 0)}个
"""

        # 如果有风险提示
        if report_data.get('risk_alerts'):
            content += f"\n**⚠️ 风险提示**\n"
            for alert in report_data['risk_alerts']:
                content += f"• {alert}\n"

        actions = [
            {
                "label": "查看详情",
                "type": "primary",
                "url": report_data.get('detail_url', '#')
            },
            {
                "label": "查看信号",
                "url": report_data.get('signals_url', '#')
            }
        ]

        return self.send_card(
            title=f"📊 每日投资报告 - {date}",
            content=content,
            urgency="normal",
            actions=actions
        )

    def send_weekly_report(self, report_data: Dict[str, Any]) -> bool:
        """发送每周投资报告

        Args:
            report_data: 周报数据

        Returns:
            是否发送成功
        """
        week = report_data.get('week', 'N/A')

        content = f"""**📈 本周表现**
周收益率: {report_data.get('weekly_return', 'N/A')}
最大回撤: {report_data.get('max_drawdown', 'N/A')}
交易胜率: {report_data.get('win_rate', 'N/A')}
累计收益: {report_data.get('cumulative_return', 'N/A')}

**🎯 策略表现**
{self._format_strategy_performance(report_data.get('strategies', []))}

**🔮 下周展望**
{self._format_outlook(report_data.get('outlook', {}))}
"""

        actions = [
            {
                "label": "查看详情",
                "type": "primary",
                "url": report_data.get('detail_url', '#')
            },
            {
                "label": "导出报告",
                "url": report_data.get('export_url', '#')
            }
        ]

        return self.send_card(
            title=f"📊 投资周报 - 第{week}周",
            content=content,
            urgency="normal",
            actions=actions
        )

    def send_alert(
        self,
        alert_type: str,
        symbol: str,
        message: str,
        data: Dict[str, Any] = None,
        actions: List[Dict] = None,
        mention: bool = False
    ) -> bool:
        """发送告警通知

        Args:
            alert_type: 告警类型 stop_loss/take_profit/signal/risk
            symbol: 股票代码
            message: 告警消息
            data: 额外数据
            actions: 操作按钮
            mention: 是否 @用户

        Returns:
            是否发送成功
        """
        emoji_map = {
            "stop_loss": "🚨",
            "take_profit": "🎉",
            "signal": "💡",
            "risk": "⚠️",
            "market_alert": "📢"
        }
        emoji = emoji_map.get(alert_type, "ℹ️")

        title = f"{emoji} {alert_type.upper().replace('_', ' ')} - {symbol}"

        # 构建内容
        content = message

        if data:
            content += "\n\n**详细信息**\n"
            for key, value in data.items():
                content += f"• {key}: {value}\n"

        # 默认操作按钮
        if actions is None:
            actions = [
                {"label": "查看详情", "type": "default"}
            ]

        urgency = "critical" if alert_type == "stop_loss" else "high"

        result = self.send_card(
            title=title,
            content=content,
            urgency=urgency,
            actions=actions
        )

        # 如果需要提及用户，再发一条文本
        if mention and result:
            self.send_text(f"请注意查看告警: {title}", mention_all=True)

        return result

    def send_premarket_report(self, report_data: Dict[str, Any]) -> bool:
        """发送盘前准备报告

        Args:
            report_data: 盘前数据

        Returns:
            是否发送成功
        """
        date = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))

        content = f"""**✅ 数据检查**
数据完整性: {report_data.get('data_integrity', '正常')}
股票池更新: {report_data.get('pool_updated', '完成')}

**💡 今日机会**
{self._format_opportunities(report_data.get('opportunities', []))}

**📋 今日关注**
{self._format_watchlist(report_data.get('watchlist', []))}
"""

        actions = [
            {"label": "查看机会", "type": "primary"},
            {"label": "查看持仓"},
            {"label": "开始盯盘"}
        ]

        return self.send_card(
            title=f"📋 盘前准备报告 - {date}",
            content=content,
            urgency="normal",
            actions=actions
        )

    def _format_strategy_performance(self, strategies: List[Dict]) -> str:
        """格式化策略表现"""
        if not strategies:
            return "无策略数据"

        lines = []
        for strategy in strategies[:3]:  # 只显示前3个
            name = strategy.get('name', 'Unknown')
            return_rate = strategy.get('return', 'N/A')
            lines.append(f"• {name}: {return_rate}")

        return '\n'.join(lines)

    def _format_outlook(self, outlook: Dict) -> str:
        """格式化展望内容"""
        if not outlook:
            return "暂无展望"

        lines = []
        if outlook.get('market_view'):
            lines.append(f"• 市场观点: {outlook['market_view']}")
        if outlook.get('recommendations'):
            lines.append(f"• 操作建议: {outlook['recommendations']}")
        if outlook.get('focus_sectors'):
            lines.append(f"• 关注板块: {outlook['focus_sectors']}")

        return '\n'.join(lines) if lines else "暂无展望"

    def _format_opportunities(self, opportunities: List[Dict]) -> str:
        """格式化机会列表"""
        if not opportunities:
            return "暂无机会"

        lines = []
        for opp in opportunities[:5]:  # 最多显示5个
            symbol = opp.get('symbol', 'N/A')
            reason = opp.get('reason', 'N/A')
            lines.append(f"• {symbol}: {reason}")

        return '\n'.join(lines)

    def _format_watchlist(self, watchlist: List[str]) -> str:
        """格式化关注列表"""
        if not watchlist:
            return "暂无关注"

        return ', '.join(watchlist[:10])  # 最多显示10个

    # 2026-09-11（w-23c70356）：原 _send()（直接 requests.post 飞书 webhook）已删除——
    # 该类所有对外方法现已统一经 NotificationFacade 投递，裸 webhook 通道不应保留为可用路径。
    # 需要底层发送能力时请用 infrastructure/notification/channels/feishu_channel.py（DDD 基础设施层）。


# 全局单例
_feishu_instance: Optional[FeishuNotificationService] = None


def get_feishu_service() -> FeishuNotificationService:
    """获取飞书服务单例"""
    global _feishu_instance
    if _feishu_instance is None:
        _feishu_instance = FeishuNotificationService()
    return _feishu_instance


def send_feishu_notification(
    message_type: str,
    **kwargs
) -> bool:
    """便捷的飞书通知函数

    Args:
        message_type: 消息类型 text/card/alert/daily_report/weekly_report
        **kwargs: 对应类型的参数

    Returns:
        是否发送成功
    """
    service = get_feishu_service()

    if message_type == 'text':
        return service.send_text(**kwargs)
    elif message_type == 'card':
        return service.send_card(**kwargs)
    elif message_type == 'alert':
        return service.send_alert(**kwargs)
    elif message_type == 'daily_report':
        return service.send_daily_report(**kwargs)
    elif message_type == 'weekly_report':
        return service.send_weekly_report(**kwargs)
    elif message_type == 'premarket_report':
        return service.send_premarket_report(**kwargs)
    else:
        logger.error(f"Unknown message type: {message_type}")
        return False
