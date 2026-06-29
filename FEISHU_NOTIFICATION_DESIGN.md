# V13模型观察期 - 飞书通知方案

## 通知类型设计

### 1. 调仓通知（每5个交易日）

**触发时机：** V13执行调仓时

**通知内容：**
```
📊 V13策略调仓通知

🗓 调仓日期: 2026-06-30
💰 账户状态:
  • 总资产: ¥100,928.71
  • 现金余额: ¥46,176.71
  • 累计收益: +0.93% (¥928.71)
  • 持仓数量: 6只

🎯 本次预测Top 8:
1. 301292 - 预测+15.81% (¥78.96，太贵买不起)
2. 300383 - 预测+13.94% ✅ 买入400股
3. 300255 - 预测+13.04% ✅ 买入200股
4. 301666 - 预测+11.17% (¥657.99，太贵买不起)
5. 300179 - 预测+11.03% ✅ 保留持仓
6. 300953 - 预测+10.64% (¥128.20，太贵买不起)
7. 301626 - 预测+9.99% (¥345.20，太贵买不起)
8. 300394 - 预测+9.54% (¥318.00，太贵买不起)

📈 实际操作:
买入:
  • 300383: 400股 @ ¥12.11
  • 300255: 200股 @ ¥22.83
卖出:
  • 300342: 200股 @ ¥44.38
  • 300364: 400股 @ ¥23.45

⏰ 5天后验证提醒: 2026-07-07
```

---

### 2. 验证通知（调仓5天后）

**触发时机：** 调仓日+5个交易日

**通知内容：**
```
✅ V13策略验证报告

🗓 原调仓日期: 2026-06-30
📅 验证日期: 2026-07-07 (5个交易日后)

📊 预测准确性验证:
✅ 300383: 预测+13.94% | 实际+8.2% (方向正确)
✅ 300255: 预测+13.04% | 实际+5.1% (方向正确)
❌ 300179: 预测+11.03% | 实际-2.3% (方向错误)

📈 整体表现:
  • 验证股票: 3只
  • 预测正确: 2只 (66.7%)
  • 平均收益: +3.67%
  • 最高收益: +8.2% (300383)
  • 最低收益: -2.3% (300179)

💰 账户变化:
  • 5天前: ¥100,928.71
  • 现在: ¥102,156.34
  • 期间收益: +1.22% (¥1,227.63)

📊 对比创业板指数:
  • V13收益: +1.22%
  • 创业板指数: +0.85%
  • 超额收益: +0.37% ✅

⚠️ 观察期进度: 第1/3个调仓周期
```

---

### 3. 止损预警通知（条件触发）

**触发条件：**
- 累计收益 < -5%
- 单周跑输指数 > 5%

**通知内容：**
```
⚠️ V13策略风险预警

🚨 触发条件: 累计收益跌破-5%

💰 当前状态:
  • 总资产: ¥94,523.45
  • 累计收益: -5.48%
  • 本周收益: -3.2%

📉 与指数对比:
  • V13收益: -5.48%
  • 创业板指数: -1.2%
  • 跑输: -4.28% ⚠️

⚠️ 建议: 立即停止观察，分析原因并优化模型

📊 问题分析:
  • 近3次调仓胜率: 33.3%
  • 平均单股收益: -2.1%
  • 主要亏损股票: XXX, XXX
```

---

### 4. 周报通知（每周一）

**触发时机：** 每周一早上9:00

**通知内容：**
```
📈 V13策略周报 (第1周)

📅 统计周期: 2026-06-23 ~ 2026-06-27

💰 账户表现:
  • 周初: ¥100,000.00
  • 周末: ¥100,928.71
  • 本周收益: +0.93% (¥928.71)

📊 交易统计:
  • 调仓次数: 1次
  • 交易股票: 6只
  • 盈利股票: 4只 (66.7%)
  • 胜率: 66.7%

🎯 选股质量:
  • 预测准确度: 待验证 (5天后)
  • 平均持仓收益: +1.5%

📉 风控指标:
  • 最大回撤: -2.3%
  • 仓位水平: 75%
  • 止损触发: 0次

📊 对比基准:
  • V13收益: +0.93%
  • 创业板指数: +1.2%
  • 超额收益: -0.27% ⚠️

⏭ 下周计划:
  • 下次调仓: 2026-06-30 (周一)
  • 观察期进度: 1/3

---
观察期规则提醒:
⚠️ 累计收益 < -5% → 停止优化
⚠️ 连续2周跑输指数5%+ → 停止分析
```

---

### 5. 观察期总结报告（2-3周后）

**触发时机：** 完成3个调仓周期后

**通知内容：**
```
🎯 V13策略观察期总结报告

📅 观察期间: 2026-06-23 ~ 2026-07-14 (3周)

💰 整体收益:
  • 初始资金: ¥100,000.00
  • 最终资产: ¥103,456.78
  • 累计收益: +3.46% (¥3,456.78) ✅
  • 最大回撤: -2.1%

📊 交易统计:
  • 调仓次数: 3次
  • 总交易: 18笔
  • 盈利交易: 11笔
  • 胜率: 61.1% ✅
  • 平均盈利: +6.2%
  • 平均亏损: -3.1%

🎯 预测准确性:
  • 验证股票: 24只
  • 预测正确: 15只
  • 准确率: 62.5% ✅
  • 平均预测误差: ±4.3%

📈 对比基准:
  • V13收益: +3.46%
  • 创业板指数: +2.1%
  • 超额收益: +1.36% ✅

✅ 评估结果 (4项指标):
1. 胜率 > 50%: ✅ (61.1%)
2. 累计收益 > 0: ✅ (+3.46%)
3. 跑赢指数: ✅ (+1.36%)
4. 最大回撤 < 15%: ✅ (-2.1%)

🎉 结论: 4/4项满足，模型有效！

💡 建议:
✅ 可以继续使用V13策略
✅ 建议优化：添加价格过滤，避免高价股
⚠️ 持续监控：每月复盘一次
```

---

## 技术实现

### 飞书Webhook配置

```python
# config/feishu_config.yaml
feishu:
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
  enable_notifications: true
  notification_types:
    - rebalance          # 调仓通知
    - verification       # 验证通知
    - risk_alert         # 风险预警
    - weekly_report      # 周报
    - final_summary      # 总结报告
```

### 通知发送器

```python
# utils/feishu_notifier.py
import requests
import json
from datetime import datetime

class FeishuNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def send_rebalance_notification(self, data):
        """发送调仓通知"""
        message = self._build_rebalance_message(data)
        return self._send(message)
    
    def send_verification_notification(self, data):
        """发送验证通知"""
        message = self._build_verification_message(data)
        return self._send(message)
    
    def send_risk_alert(self, data):
        """发送风险预警"""
        message = self._build_risk_alert_message(data)
        return self._send(message)
    
    def send_weekly_report(self, data):
        """发送周报"""
        message = self._build_weekly_report_message(data)
        return self._send(message)
    
    def send_final_summary(self, data):
        """发送总结报告"""
        message = self._build_final_summary_message(data)
        return self._send(message)
    
    def _send(self, message):
        """发送消息到飞书"""
        headers = {'Content-Type': 'application/json'}
        payload = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }
        
        response = requests.post(
            self.webhook_url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        return response.json()
```

### 集成到V13交易流程

```python
# live_trading/simulation_trader.py

def rebalance(self, current_date):
    """执行调仓"""
    # ... 原有调仓逻辑 ...
    
    # 调仓完成后发送通知
    if self.config.get('feishu', {}).get('enable_notifications'):
        notifier = FeishuNotifier(self.config['feishu']['webhook_url'])
        
        notification_data = {
            'date': current_date,
            'total_value': self._calculate_total_value_from_portfolio(),
            'cash': self.cash,
            'cumulative_return': (total_value / 100000 - 1),
            'positions': len(self.portfolio),
            'top_stocks': top_stocks,
            'predictions': predictions,
            'trades': trades_executed
        }
        
        notifier.send_rebalance_notification(notification_data)
```

### 定时验证任务

```python
# infrastructure/jobs/verification_job.py

def verify_predictions():
    """5天后验证预测准确性"""
    # 查找5天前的调仓记录
    rebalance_date = get_date_days_ago(5, trading_days_only=True)
    
    # 获取当时的预测
    predictions = get_predictions(rebalance_date)
    
    # 计算实际收益
    actual_returns = calculate_actual_returns(predictions, days=5)
    
    # 对比分析
    analysis = compare_predictions_vs_actual(predictions, actual_returns)
    
    # 发送验证通知
    notifier = FeishuNotifier(webhook_url)
    notifier.send_verification_notification(analysis)
```

### Scheduler配置

```python
# infrastructure/scheduler/init_scheduler_tasks.py

tasks = [
    # 每日检查（工作日14:30）
    {
        'name': 'v13-daily-check',
        'cron_expression': '30 14 * * 1-5',
        'command': 'v13_trading',
        'description': 'V13策略每日检查'
    },
    
    # 验证任务（工作日15:30）
    {
        'name': 'v13-verification',
        'cron_expression': '30 15 * * 1-5',
        'command': 'verify_predictions',
        'description': 'V13预测验证（5天后）'
    },
    
    # 周报任务（每周一9:00）
    {
        'name': 'v13-weekly-report',
        'cron_expression': '0 9 * * 1',
        'command': 'generate_weekly_report',
        'description': 'V13策略周报'
    },
    
    # 风险检查（工作日16:00）
    {
        'name': 'v13-risk-check',
        'cron_expression': '0 16 * * 1-5',
        'command': 'check_risk_alerts',
        'description': 'V13风险预警检查'
    }
]
```

---

## 下一步

需要你提供：
1. **飞书Webhook地址** - 创建一个飞书群机器人
2. **通知偏好** - 是否需要调整通知内容/频率

然后我可以：
1. 实现飞书通知功能
2. 集成到V13交易流程
3. 配置定时任务
4. 测试通知发送
