"""
飞书通知服务

用于V13策略的自动通知：
1. 调仓通知
2. 验证通知（5天后）
3. 风险预警
4. 周报
5. 观察期总结
"""

import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书通知服务"""

    def __init__(self, webhook_url: str, enable: bool = True):
        """
        初始化飞书通知服务

        Args:
            webhook_url: 飞书Webhook地址
            enable: 是否启用通知
        """
        self.webhook_url = webhook_url
        self.enable = enable

        if not webhook_url or webhook_url.startswith("${"):
            self.enable = False
            logger.warning("飞书Webhook未配置，通知功能已禁用")

    def send_text(self, text: str) -> bool:
        """
        发送文本消息

        Args:
            text: 文本内容

        Returns:
            是否发送成功
        """
        if not self.enable:
            logger.debug("飞书通知已禁用，跳过发送")
            return False

        try:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": text
                }
            }

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=10
            )

            result = response.json()
            if result.get('code') == 0:
                logger.info("飞书通知发送成功")
                return True
            else:
                logger.error(f"飞书通知发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"飞书通知发送异常: {e}")
            return False

    def send_rebalance_notification(self, data: Dict[str, Any]) -> bool:
        """
        发送调仓通知

        Args:
            data: 调仓数据
                - date: 调仓日期
                - total_value: 总资产
                - cash: 现金
                - cumulative_return: 累计收益率
                - positions: 持仓数量
                - top_stocks: Top股票列表 [(symbol, predicted_return, weight)]
                - buy_trades: 买入交易 [(symbol, shares, price)]
                - sell_trades: 卖出交易 [(symbol, shares, price)]

        Returns:
            是否发送成功
        """
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        total_value = data.get('total_value', 0)
        cash = data.get('cash', 0)
        cumulative_return = data.get('cumulative_return', 0)
        positions = data.get('positions', 0)
        top_stocks = data.get('top_stocks', [])
        buy_trades = data.get('buy_trades', [])
        sell_trades = data.get('sell_trades', [])

        # 构建消息
        message = f"""📊 V13策略调仓通知

🗓 调仓日期: {date}
💰 账户状态:
  • 总资产: ¥{total_value:,.2f}
  • 现金余额: ¥{cash:,.2f}
  • 累计收益: {cumulative_return*100:+.2f}% (¥{(total_value - 100000):,.2f})
  • 持仓数量: {positions}只

🎯 本次预测Top 8:"""

        for i, (symbol, pred_return, weight, note) in enumerate(top_stocks[:8], 1):
            status = "✅" if "买入" in note or "保留" in note else "❌"
            message += f"\n{i}. {symbol} - 预测{pred_return*100:+.2f}% {status} {note}"

        if buy_trades or sell_trades:
            message += "\n\n📈 实际操作:"

        if buy_trades:
            message += "\n买入:"
            for symbol, shares, price in buy_trades:
                message += f"\n  • {symbol}: {shares}股 @ ¥{price:.2f}"

        if sell_trades:
            message += "\n卖出:"
            for symbol, shares, price in sell_trades:
                message += f"\n  • {symbol}: {shares}股 @ ¥{price:.2f}"

        # 计算验证日期（5个交易日后）
        from datetime import timedelta
        verify_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
        message += f"\n\n⏰ 5天后验证提醒: {verify_date}"

        return self.send_text(message)

    def send_verification_notification(self, data: Dict[str, Any]) -> bool:
        """
        发送验证通知（5天后）

        Args:
            data: 验证数据
                - rebalance_date: 原调仓日期
                - verify_date: 验证日期
                - predictions: 预测结果列表 [(symbol, pred_return, actual_return)]
                - initial_value: 调仓时总资产
                - current_value: 当前总资产
                - period_return: 期间收益率
                - index_return: 指数收益率
                - cycle: 第几个周期

        Returns:
            是否发送成功
        """
        rebalance_date = data.get('rebalance_date')
        verify_date = data.get('verify_date')
        predictions = data.get('predictions', [])
        initial_value = data.get('initial_value', 0)
        current_value = data.get('current_value', 0)
        period_return = data.get('period_return', 0)
        index_return = data.get('index_return', 0)
        cycle = data.get('cycle', 1)

        # 统计准确率
        correct = sum(1 for _, pred, actual in predictions if (pred > 0) == (actual > 0))
        accuracy = correct / len(predictions) * 100 if predictions else 0
        avg_return = sum(actual for _, _, actual in predictions) / len(predictions) if predictions else 0

        message = f"""✅ V13策略验证报告

🗓 原调仓日期: {rebalance_date}
📅 验证日期: {verify_date} (5个交易日后)

📊 预测准确性验证:"""

        for symbol, pred_return, actual_return in predictions:
            direction = "✅" if (pred_return > 0) == (actual_return > 0) else "❌"
            message += f"\n{direction} {symbol}: 预测{pred_return*100:+.2f}% | 实际{actual_return*100:+.2f}%"

        message += f"""

📈 整体表现:
  • 验证股票: {len(predictions)}只
  • 预测正确: {correct}只 ({accuracy:.1f}%)
  • 平均收益: {avg_return*100:+.2f}%

💰 账户变化:
  • 5天前: ¥{initial_value:,.2f}
  • 现在: ¥{current_value:,.2f}
  • 期间收益: {period_return*100:+.2f}% (¥{current_value - initial_value:,.2f})

📊 对比创业板指数:
  • V13收益: {period_return*100:+.2f}%
  • 创业板指数: {index_return*100:+.2f}%
  • 超额收益: {(period_return - index_return)*100:+.2f}% {"✅" if period_return > index_return else "⚠️"}

⚠️ 观察期进度: 第{cycle}/3个调仓周期"""

        return self.send_text(message)

    def send_risk_alert(self, data: Dict[str, Any]) -> bool:
        """
        发送风险预警

        Args:
            data: 风险数据
                - trigger: 触发条件
                - total_value: 当前总资产
                - cumulative_return: 累计收益率
                - weekly_return: 本周收益
                - index_return: 指数收益
                - win_rate: 胜率
                - avg_return: 平均收益
                - losing_stocks: 主要亏损股票

        Returns:
            是否发送成功
        """
        trigger = data.get('trigger', '未知')
        total_value = data.get('total_value', 0)
        cumulative_return = data.get('cumulative_return', 0)
        weekly_return = data.get('weekly_return', 0)
        index_return = data.get('index_return', 0)
        win_rate = data.get('win_rate', 0)
        avg_return = data.get('avg_return', 0)
        losing_stocks = data.get('losing_stocks', [])

        message = f"""⚠️ V13策略风险预警

🚨 触发条件: {trigger}

💰 当前状态:
  • 总资产: ¥{total_value:,.2f}
  • 累计收益: {cumulative_return*100:+.2f}%
  • 本周收益: {weekly_return*100:+.2f}%

📉 与指数对比:
  • V13收益: {cumulative_return*100:+.2f}%
  • 创业板指数: {index_return*100:+.2f}%
  • 跑输: {(cumulative_return - index_return)*100:+.2f}% ⚠️

📊 交易统计:
  • 近3次调仓胜率: {win_rate*100:.1f}%
  • 平均单股收益: {avg_return*100:+.2f}%"""

        if losing_stocks:
            message += "\n  • 主要亏损股票: " + ", ".join(losing_stocks)

        message += "\n\n⚠️ 建议: 立即停止观察，分析原因并优化模型"

        return self.send_text(message)

    def send_weekly_report(self, data: Dict[str, Any]) -> bool:
        """
        发送周报

        Args:
            data: 周报数据
                - week: 第几周
                - start_date: 开始日期
                - end_date: 结束日期
                - initial_value: 周初资产
                - final_value: 周末资产
                - weekly_return: 本周收益率
                - rebalance_count: 调仓次数
                - trade_count: 交易次数
                - win_count: 盈利股票数
                - win_rate: 胜率
                - avg_position_return: 平均持仓收益
                - max_drawdown: 最大回撤
                - position_level: 仓位水平
                - stop_loss_count: 止损次数
                - index_return: 指数收益
                - excess_return: 超额收益
                - next_rebalance_date: 下次调仓日期
                - observation_progress: 观察期进度

        Returns:
            是否发送成功
        """
        week = data.get('week', 1)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_value = data.get('initial_value', 0)
        final_value = data.get('final_value', 0)
        weekly_return = data.get('weekly_return', 0)
        rebalance_count = data.get('rebalance_count', 0)
        trade_count = data.get('trade_count', 0)
        win_count = data.get('win_count', 0)
        total_stocks = data.get('total_stocks', 0)
        win_rate = win_count / total_stocks * 100 if total_stocks > 0 else 0
        avg_position_return = data.get('avg_position_return', 0)
        max_drawdown = data.get('max_drawdown', 0)
        position_level = data.get('position_level', 0)
        stop_loss_count = data.get('stop_loss_count', 0)
        index_return = data.get('index_return', 0)
        excess_return = data.get('excess_return', 0)
        next_rebalance_date = data.get('next_rebalance_date', '')
        observation_progress = data.get('observation_progress', '')

        message = f"""📈 V13策略周报 (第{week}周)

📅 统计周期: {start_date} ~ {end_date}

💰 账户表现:
  • 周初: ¥{initial_value:,.2f}
  • 周末: ¥{final_value:,.2f}
  • 本周收益: {weekly_return*100:+.2f}% (¥{final_value - initial_value:,.2f})

📊 交易统计:
  • 调仓次数: {rebalance_count}次
  • 交易股票: {total_stocks}只
  • 盈利股票: {win_count}只 ({win_rate:.1f}%)
  • 胜率: {win_rate:.1f}%

🎯 选股质量:
  • 平均持仓收益: {avg_position_return*100:+.2f}%

📉 风控指标:
  • 最大回撤: {max_drawdown*100:.1f}%
  • 仓位水平: {position_level*100:.0f}%
  • 止损触发: {stop_loss_count}次

📊 对比基准:
  • V13收益: {weekly_return*100:+.2f}%
  • 创业板指数: {index_return*100:+.2f}%
  • 超额收益: {excess_return*100:+.2f}% {"✅" if excess_return > 0 else "⚠️"}

⏭ 下周计划:
  • 下次调仓: {next_rebalance_date}
  • 观察期进度: {observation_progress}

---
观察期规则提醒:
⚠️ 累计收益 < -5% → 停止优化
⚠️ 连续2周跑输指数5%+ → 停止分析"""

        return self.send_text(message)

    def send_final_summary(self, data: Dict[str, Any]) -> bool:
        """
        发送观察期总结报告

        Args:
            data: 总结数据
                - start_date: 开始日期
                - end_date: 结束日期
                - initial_capital: 初始资金
                - final_value: 最终资产
                - cumulative_return: 累计收益率
                - max_drawdown: 最大回撤
                - rebalance_count: 调仓次数
                - total_trades: 总交易笔数
                - winning_trades: 盈利交易数
                - win_rate: 胜率
                - avg_win: 平均盈利
                - avg_loss: 平均亏损
                - verified_stocks: 验证股票数
                - correct_predictions: 预测正确数
                - prediction_accuracy: 预测准确率
                - avg_prediction_error: 平均预测误差
                - strategy_return: 策略收益
                - index_return: 指数收益
                - excess_return: 超额收益
                - criterion_1: 胜率>50%
                - criterion_2: 累计收益>0
                - criterion_3: 跑赢指数
                - criterion_4: 最大回撤<15%
                - passed_count: 通过指标数
                - conclusion: 结论
                - suggestion: 建议

        Returns:
            是否发送成功
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_capital = data.get('initial_capital', 100000)
        final_value = data.get('final_value', 0)
        cumulative_return = data.get('cumulative_return', 0)
        max_drawdown = data.get('max_drawdown', 0)
        rebalance_count = data.get('rebalance_count', 0)
        total_trades = data.get('total_trades', 0)
        winning_trades = data.get('winning_trades', 0)
        win_rate = data.get('win_rate', 0)
        avg_win = data.get('avg_win', 0)
        avg_loss = data.get('avg_loss', 0)
        verified_stocks = data.get('verified_stocks', 0)
        correct_predictions = data.get('correct_predictions', 0)
        prediction_accuracy = data.get('prediction_accuracy', 0)
        avg_prediction_error = data.get('avg_prediction_error', 0)
        strategy_return = data.get('strategy_return', 0)
        index_return = data.get('index_return', 0)
        excess_return = data.get('excess_return', 0)
        criterion_1 = data.get('criterion_1', False)
        criterion_2 = data.get('criterion_2', False)
        criterion_3 = data.get('criterion_3', False)
        criterion_4 = data.get('criterion_4', False)
        passed_count = data.get('passed_count', 0)
        conclusion = data.get('conclusion', '')
        suggestion = data.get('suggestion', '')

        weeks = (datetime.strptime(end_date, '%Y-%m-%d') -
                datetime.strptime(start_date, '%Y-%m-%d')).days // 7

        message = f"""🎯 V13策略观察期总结报告

📅 观察期间: {start_date} ~ {end_date} ({weeks}周)

💰 整体收益:
  • 初始资金: ¥{initial_capital:,.2f}
  • 最终资产: ¥{final_value:,.2f}
  • 累计收益: {cumulative_return*100:+.2f}% (¥{final_value - initial_capital:,.2f}) {"✅" if cumulative_return > 0 else "❌"}
  • 最大回撤: {max_drawdown*100:.1f}%

📊 交易统计:
  • 调仓次数: {rebalance_count}次
  • 总交易: {total_trades}笔
  • 盈利交易: {winning_trades}笔
  • 胜率: {win_rate*100:.1f}% {"✅" if win_rate > 0.5 else "❌"}
  • 平均盈利: {avg_win*100:+.2f}%
  • 平均亏损: {avg_loss*100:+.2f}%

🎯 预测准确性:
  • 验证股票: {verified_stocks}只
  • 预测正确: {correct_predictions}只
  • 准确率: {prediction_accuracy*100:.1f}%
  • 平均预测误差: ±{avg_prediction_error*100:.1f}%

📈 对比基准:
  • V13收益: {strategy_return*100:+.2f}%
  • 创业板指数: {index_return*100:+.2f}%
  • 超额收益: {excess_return*100:+.2f}% {"✅" if excess_return > 0 else "❌"}

✅ 评估结果 (4项指标):
1. 胜率 > 50%: {"✅" if criterion_1 else "❌"} ({win_rate*100:.1f}%)
2. 累计收益 > 0: {"✅" if criterion_2 else "❌"} ({cumulative_return*100:+.2f}%)
3. 跑赢指数: {"✅" if criterion_3 else "❌"} ({excess_return*100:+.2f}%)
4. 最大回撤 < 15%: {"✅" if criterion_4 else "❌"} ({max_drawdown*100:.1f}%)

🎉 结论: {passed_count}/4项满足，{conclusion}

💡 建议:
{suggestion}"""

        return self.send_text(message)


# 便捷函数
def create_notifier_from_config(config: Dict[str, Any]) -> Optional[FeishuNotifier]:
    """
    从配置创建通知器

    Args:
        config: 配置字典

    Returns:
        FeishuNotifier实例，如果未配置则返回None
    """
    feishu_config = config.get('feishu', {})

    if not feishu_config.get('enable', False):
        logger.info("飞书通知未启用")
        return None

    webhook_url = feishu_config.get('webhook_url', '')

    # 从环境变量读取
    if webhook_url.startswith('${') and webhook_url.endswith('}'):
        import os
        env_var = webhook_url[2:-1]
        webhook_url = os.getenv(env_var, '')

    if not webhook_url:
        logger.warning("飞书Webhook未配置")
        return None

    return FeishuNotifier(webhook_url, enable=True)
