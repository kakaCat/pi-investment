# V13策略飞书通知系统

## 📋 概述

V13策略飞书通知系统是一个自动化监控系统，用于在2-3周的观察期内验证V13量化模型的有效性。

**核心功能：**
- ✅ 调仓自动通知
- ✅ 5天后预测验证
- ✅ 每日风险检查
- ✅ 每周表现报告
- ✅ 观察期总结

## 🚀 快速开始

### 1. 部署系统

运行自动化部署脚本：

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 设置飞书Webhook环境变量
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"

# 运行部署脚本
./scripts/deploy_feishu_notifications.sh
```

部署脚本会自动：
1. 检查Python环境
2. 验证飞书Webhook配置
3. 创建日志目录
4. 测试通知功能
5. 安装定时任务到crontab

### 2. 手动测试

测试飞书通知：
```bash
cd quantsys-v2
export FEISHU_WEBHOOK_URL="your_webhook_url"

# 测试所有通知类型
python scripts/test_feishu_notification.py --auto
```

测试单个任务：
```bash
# 测试验证通知
python infrastructure/jobs/verification_job.py

# 测试风险检查
python infrastructure/jobs/risk_check_job.py

# 测试周报
python infrastructure/jobs/weekly_report_job.py
```

## 📅 定时任务说明

系统包含4个定时任务：

| 任务 | 执行时间 | 频率 | 说明 |
|------|---------|------|------|
| V13调仓 | 14:25 | 每个交易日 | 检查是否需要调仓并执行 |
| 预测验证 | 15:30 | 每个交易日 | 检查5天前的预测准确性 |
| 风险检查 | 16:00 | 每个交易日 | 检查是否触发止损条件 |
| 周报 | 09:00 | 每周一 | 生成上周表现总结 |

### 查看定时任务

```bash
# 查看已安装的定时任务
crontab -l

# 编辑定时任务
crontab -e

# 删除所有定时任务（危险！）
crontab -r
```

## 📊 通知类型

### 1. 调仓通知

**触发时机：** 每次调仓完成后

**内容包括：**
- 账户状态（总资产、现金、累计收益）
- Top 8预测股票及预测收益率
- 实际买入/卖出操作明细
- 5天后验证提醒日期

### 2. 验证通知

**触发时机：** 调仓后第5个交易日

**内容包括：**
- 预测准确性验证（逐只股票对比）
- 预测正确率统计
- 账户期间收益
- 对比创业板指数表现
- 观察期进度

### 3. 风险预警

**触发条件：**
- 累计收益 < -5%
- 跑输指数 > 5%

**内容包括：**
- 触发条件说明
- 当前账户状态
- 近期胜率和平均收益
- 主要亏损股票
- 建议行动

### 4. 周报

**触发时机：** 每周一早上9点

**内容包括：**
- 本周收益统计
- 交易次数和胜率
- 风控指标（最大回撤、仓位水平）
- 对比基准指数
- 观察期进度
- 下次调仓日期

### 5. 观察期总结

**触发时机：** 完成3个调仓周期后（手动触发）

**内容包括：**
- 整体收益表现
- 交易统计（胜率、盈亏比）
- 预测准确率
- 对比基准指数
- 4项评估指标
- 最终建议（继续/优化/停止）

## 📁 文件结构

```
quantsys-v2/
├── utils/
│   └── feishu_notifier.py          # 飞书通知服务类
├── infrastructure/jobs/
│   ├── v13_trading_job.py          # V13调仓任务
│   ├── verification_job.py         # 预测验证任务
│   ├── risk_check_job.py           # 风险检查任务
│   ├── weekly_report_job.py        # 周报任务
│   └── crontab.example             # Crontab配置示例
├── scripts/
│   ├── test_feishu_notification.py # 通知功能测试脚本
│   └── deploy_feishu_notifications.sh # 自动化部署脚本
├── live_trading/
│   ├── config_simulation.yaml      # 配置文件（含飞书配置）
│   ├── simulation_trader.py        # 模拟交易器（已集成通知）
│   └── logs/                       # 日志目录
│       ├── v13_trading.log
│       ├── verification.log
│       ├── risk_check.log
│       └── weekly_report.log
└── FEISHU_IMPLEMENTATION_SUMMARY.md # 实现总结文档
```

## 📝 日志管理

### 查看日志

```bash
# 实时查看调仓日志
tail -f live_trading/logs/v13_trading.log

# 查看验证日志
tail -f live_trading/logs/verification.log

# 查看风险检查日志
tail -f live_trading/logs/risk_check.log

# 查看周报日志
tail -f live_trading/logs/weekly_report.log
```

### 日志清理

```bash
# 清理超过30天的日志
find live_trading/logs -name "*.log" -mtime +30 -delete

# 手动清空日志
> live_trading/logs/v13_trading.log
> live_trading/logs/verification.log
> live_trading/logs/risk_check.log
> live_trading/logs/weekly_report.log
```

## ⚙️ 配置说明

配置文件位置：`live_trading/config_simulation.yaml`

```yaml
feishu:
  enable: true                      # 是否启用飞书通知
  webhook_url: "${FEISHU_WEBHOOK_URL}"  # Webhook URL（从环境变量读取）
  notifications:
    rebalance: true                 # 调仓通知
    verification: true              # 验证通知
    risk_alert: true                # 风险预警
    weekly_report: true             # 周报
    final_summary: true             # 总结报告
  observation_period:
    enabled: true                   # 启用观察期模式
    cycles: 3                       # 观察3个调仓周期
    stop_loss_threshold: -0.05      # 累计收益<-5%触发预警
    underperform_threshold: 0.05    # 跑输指数5%触发预警
```

## 🔧 故障排查

### 问题1: 通知发送失败

**检查步骤：**
1. 确认FEISHU_WEBHOOK_URL环境变量已设置
2. 测试Webhook是否有效：
   ```bash
   curl -X POST "$FEISHU_WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d '{"msg_type":"text","content":{"text":"测试消息"}}'
   ```
3. 查看日志中的错误信息

### 问题2: 定时任务未执行

**检查步骤：**
1. 确认crontab已安装：`crontab -l`
2. 检查Python路径是否正确
3. 检查环境变量是否在crontab中设置
4. 查看系统日志：`grep CRON /var/log/system.log` (macOS)

### 问题3: 数据库连接失败

**检查步骤：**
1. 确认PostgreSQL服务运行正常
2. 检查数据库配置（.env文件）
3. 测试数据库连接：
   ```bash
   psql -h 127.0.0.1 -p 5432 -U mac -d quant_investment
   ```

## 📞 技术支持

- 文档：[FEISHU_IMPLEMENTATION_SUMMARY.md](../FEISHU_IMPLEMENTATION_SUMMARY.md)
- 配置示例：`infrastructure/jobs/crontab.example`
- 测试脚本：`scripts/test_feishu_notification.py`

## 📜 更新日志

### 2026-06-29
- ✅ 完成飞书通知系统实现
- ✅ 实现验证通知、风险检查、周报任务
- ✅ 创建自动化部署脚本
- ✅ 完成6/6项通知功能测试

### 2026-06-27
- ✅ 创建FeishuNotifier服务类
- ✅ 集成到SimulationTrader
- ✅ 更新配置文件
- ✅ 创建测试脚本

---

**实现完成时间：** 2026-06-29  
**实现人：** Claude (Kiro)
