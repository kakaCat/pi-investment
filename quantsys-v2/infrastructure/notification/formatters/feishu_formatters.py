"""
盯盘触发通知格式化器

格式化 WatchEngine 触发的通知，包括：
1. 股票名称和代码
2. 触发条件和价格
3. 方向建议（上破/下破）
4. 操作预案
5. 模式标签（直发/AI 分析/降级）

Author: System
Date: 2026-09-02
"""

from typing import Dict, Any
from domain.notification.models.notification import Notification, NotificationType
from .feishu_base_formatter import FeishuFormatter


class WatchTriggeredFormatter(FeishuFormatter):
    """盯盘触发通知格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        """支持盯盘触发类型

        Args:
            notification_type: 通知类型

        Returns:
            bool: 是否支持
        """
        return notification_type == NotificationType.WATCH_TRIGGERED

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化盯盘触发通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables

        # 提取变量
        symbol = vars.get('symbol', 'N/A')
        name = vars.get('name', '')
        price = vars.get('price', 0)
        change_pct = vars.get('change_pct')
        condition = vars.get('condition', {})
        context = vars.get('context', '')
        mode_tag = vars.get('mode_tag', '直发提醒')

        # 构建显示名称
        display = f"{name}（{symbol}）" if name else symbol

        # 构建内容
        lines = [
            f"📡 `{mode_tag}`",
            f"**{display}** 触发盯盘条件"
        ]

        # 添加触发信息
        if notification.content:
            lines.append(f"**触发**：{notification.content}")

        # 添加价格信息
        price_info = f"**当前价格**：¥{price:.2f}"
        if change_pct is not None:
            price_info += f" ({change_pct:+.2f}%)"
        lines.append(price_info)

        # 方向建议
        direction = self._get_direction_advice(condition)
        if direction:
            lines.append(direction)

        # 操作预案
        if context:
            lines.append(f"**预案**：{context}")

        content = "\n".join(lines)

        # 选择颜色
        color = self._get_color_by_condition(condition)

        return self.format_card(
            title=f"💡 盯盘触发 - {display}",
            content=content,
            color=color
        )

    def _get_direction_advice(self, condition: dict) -> str:
        """解读操作建议

        Args:
            condition: 条件字典

        Returns:
            str: 方向建议文本
        """
        if not isinstance(condition, dict):
            return ''

        params = condition.get('params') or {}
        direction = params.get('direction')

        if direction == 'above':
            return '📈 **方向**：上破（强势）——持仓参考止盈/锁利，空仓为买入候选'
        elif direction == 'below':
            return '📉 **方向**：下破（弱势）——持仓警惕止损，空仓暂不介入'

        return ''

    def _get_color_by_condition(self, condition: dict) -> str:
        """根据条件选择颜色

        Args:
            condition: 条件字典

        Returns:
            str: 飞书卡片颜色
        """
        if not isinstance(condition, dict):
            return 'blue'

        params = condition.get('params') or {}
        direction = params.get('direction')

        if direction == 'above':
            return 'green'
        elif direction == 'below':
            return 'red'

        return 'blue'


class StopLossFormatter(FeishuFormatter):
    """止损触发通知格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.STOP_LOSS

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化止损触发通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables

        # 构建内容
        symbol = vars.get('symbol', 'N/A')
        price = vars.get('price', 0)
        stop_loss_pct = vars.get('stop_loss_pct', 0)
        loss_pct = vars.get('loss_pct', 0)

        content = f"""**股票**: {symbol}
**触发价格**: ¥{price:.2f}
**止损阈值**: {stop_loss_pct:.2%}
**当前亏损**: {loss_pct:.2%}

{notification.content}"""

        return self.format_card(
            title=f"🚨 止损触发 - {symbol}",
            content=content,
            color="red"
        )


class TakeProfitFormatter(FeishuFormatter):
    """止盈触发通知格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.TAKE_PROFIT

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化止盈触发通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables

        symbol = vars.get('symbol', 'N/A')
        price = vars.get('price', 0)
        take_profit_pct = vars.get('take_profit_pct', 0)
        profit_pct = vars.get('profit_pct', 0)

        content = f"""**股票**: {symbol}
**触发价格**: ¥{price:.2f}
**止盈阈值**: {take_profit_pct:.2%}
**当前盈利**: {profit_pct:.2%}

{notification.content}"""

        return self.format_card(
            title=f"🎉 止盈触发 - {symbol}",
            content=content,
            color="green"
        )


class DailyReportFormatter(FeishuFormatter):
    """每日报告格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.DAILY_REPORT

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化每日报告通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables

        content = f"""**📈 市场表现**
上证指数: {vars.get('sh_index_change', 'N/A')}
深证成指: {vars.get('sz_index_change', 'N/A')}
北向资金: {vars.get('north_flow', 'N/A')}亿元

**💰 持仓收益**
今日收益: {vars.get('daily_pnl', 'N/A')}
总收益率: {vars.get('total_return', 'N/A')}
持仓股票: {vars.get('position_count', 0)}只

**📊 交易信号**
新增信号: {vars.get('new_signals', 0)}个
优质机会: {vars.get('opportunities', 0)}个"""

        # 风险提示
        if vars.get('risk_alerts'):
            content += "\n\n**⚠️ 风险提示**\n"
            for alert in vars['risk_alerts']:
                content += f"• {alert}\n"

        actions = []
        if vars.get('detail_url'):
            actions.append({
                "label": "查看详情",
                "type": "primary",
                "url": vars['detail_url']
            })

        return self.format_card(
            title=f"📊 每日投资报告 - {vars.get('date', '')}",
            content=content,
            color="blue",
            actions=actions if actions else None
        )


class WeeklyReportFormatter(FeishuFormatter):
    """每周报告格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.WEEKLY_REPORT

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化每周报告通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables
        week = vars.get('week', 'N/A')

        content = f"""**📈 本周表现**
周收益率: {vars.get('weekly_return', 'N/A')}
最大回撤: {vars.get('max_drawdown', 'N/A')}
交易胜率: {vars.get('win_rate', 'N/A')}
累计收益: {vars.get('cumulative_return', 'N/A')}

**🎯 策略表现**
{self._format_strategy_performance(vars.get('strategies', []))}

**🔮 下周展望**
{self._format_outlook(vars.get('outlook', {}))}"""

        actions = []
        if vars.get('detail_url'):
            actions.append({
                "label": "查看详情",
                "type": "primary",
                "url": vars['detail_url']
            })

        return self.format_card(
            title=f"📊 投资周报 - 第{week}周",
            content=content,
            color="blue",
            actions=actions if actions else None
        )

    def _format_strategy_performance(self, strategies: list) -> str:
        """格式化策略表现"""
        if not strategies:
            return "无策略数据"

        lines = []
        for strategy in strategies[:3]:  # 只显示前3个
            name = strategy.get('name', 'Unknown')
            return_rate = strategy.get('return', 'N/A')
            lines.append(f"• {name}: {return_rate}")

        return '\n'.join(lines)

    def _format_outlook(self, outlook: dict) -> str:
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


class MLTrainFormatter(FeishuFormatter):
    """模型训练通知格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.ML_TRAIN

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化模型训练通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        vars = notification.variables
        status = vars.get('status', 'unknown')

        # 根据状态选择颜色和标题
        if status == 'success':
            color = "green"
            title_prefix = "✅"
        elif status == 'failed':
            color = "red"
            title_prefix = "❌"
        else:
            color = "blue"
            title_prefix = "⊙"

        content = notification.content or self._format_train_content(vars)

        return self.format_card(
            title=f"{title_prefix} {notification.title}",
            content=content,
            color=color
        )

    def _format_train_content(self, vars: dict) -> str:
        """格式化训练内容"""
        status = vars.get('status')

        if status == 'success':
            return f"""**模型版本**: {vars.get('version', 'N/A')}
**训练样本**: {vars.get('symbols_trained', 0)} 只股票
**训练准确率**: {vars.get('train_accuracy', 0):.2%}
**测试准确率**: {vars.get('test_accuracy', 0):.2%}
**自动切换**: {'✅ 已切换' if vars.get('auto_switched') else '⊙ 未切换'}"""
        elif status == 'failed':
            return f"""**错误信息**: {vars.get('error', '未知错误')}
**失败时间**: {vars.get('timestamp', 'N/A')}"""
        else:
            return f"""**跳过原因**: {vars.get('reason', '未知原因')}"""


class SystemAlertFormatter(FeishuFormatter):
    """系统告警通知格式化器"""

    def supports_type(self, notification_type: NotificationType) -> bool:
        return notification_type == NotificationType.SYSTEM_ALERT

    def format(self, notification: Notification) -> Dict[str, Any]:
        """格式化系统告警通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 飞书卡片消息载荷
        """
        # 系统告警使用简单格式
        color = self.get_urgency_color(notification.priority.value)

        return self.format_card(
            title=f"ℹ️ {notification.title}",
            content=notification.content,
            color=color
        )
