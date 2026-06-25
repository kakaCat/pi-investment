# 🚀 PI Investment 自主化下一步实施计划

## 目标
让 agent 大脑能够 24/7 自主运行，持续在股票市场赚钱。

---

## 📋 P0 实施计划（1周内）

### Task 1: 配置定时任务 (1小时)

**目标**: 让定时任务脚本自动运行

**步骤**:
```bash
# 1. 配置 crontab
crontab -e

# 2. 添加任务
0 9 * * 1-5 /Users/mac/Documents/ai/pi-investment/scripts/morning_analysis.sh >> /tmp/morning_analysis.log 2>&1
*/5 9-15 * * 1-5 /Users/mac/Documents/ai/pi-investment/scripts/realtime_monitor.sh >> /tmp/realtime_monitor.log 2>&1
0 18 * * * /Users/mac/Documents/ai/pi-investment/scripts/daily_learning.sh >> /tmp/daily_learning.log 2>&1

# 3. 验证
crontab -l
```

**交付**: crontab 已配置，定时任务自动运行

---

### Task 2: 实现飞书通知服务 (半天)

**目标**: agent 做重要决策时通知人类

**文件**: `agent-ts/src/infrastructure/notification/feishu-service.ts`

**实现**:
```typescript
import axios from 'axios'

export class FeishuNotificationService {
  private webhook: string
  
  constructor(webhook: string) {
    this.webhook = webhook
  }
  
  async sendDecisionNotification(decision: {
    action: string
    symbol: string
    reason: string
    confidence: number
  }) {
    await this.send({
      title: '🤖 Agent 重要决策',
      content: `
动作: ${decision.action}
标的: ${decision.symbol}
理由: ${decision.reason}
置信度: ${decision.confidence}%
      `
    })
  }
  
  async sendAlert(alert: {
    level: string
    title: string
    message: string
  }) {
    const emoji = alert.level === 'critical' ? '🚨' : '⚠️'
    await this.send({
      title: `${emoji} ${alert.title}`,
      content: alert.message
    })
  }
  
  async sendDailyReport(report: {
    date: string
    decisions: number
    pnl: number
    pools: number
    alerts: number
  }) {
    await this.send({
      title: '📊 Agent 每日报告',
      content: `
日期: ${report.date}
决策次数: ${report.decisions}
盈亏: ${report.pnl}
池子数: ${report.pools}
预警: ${report.alerts}
      `
    })
  }
  
  private async send(msg: { title: string; content: string }) {
    await axios.post(this.webhook, {
      msg_type: 'text',
      content: {
        text: `${msg.title}\n${msg.content}`
      }
    })
  }
}
```

**集成**: 在 agent 决策时调用通知服务

**交付**: 关键决策、预警、每日报告自动发送飞书

---

### Task 3: 编写早盘分析工作流 (1天)

**目标**: agent 早上9点自动执行完整的早盘分析

**文件**: `agent-ts/src/workflows/morning-analysis-workflow.ts`

**实现**:
```typescript
export class MorningAnalysisWorkflow {
  async execute() {
    console.log('🌅 开始早盘分析...')
    
    // 1. 分析对手行为
    console.log('📊 分析对手行为...')
    const opponents = await opponentBehaviorTool()
    
    // 2. 检查预警
    console.log('🚨 检查博弈预警...')
    const alerts = await gameAlertTool()
    const criticalAlerts = alerts.filter(a => a.level === 'critical')
    
    // 3. 评估现有池子
    console.log('🏊 评估现有池子...')
    const pools = await listPools()
    
    for (const pool of pools) {
      const battlefield = await battlefieldAssessmentTool(pool.id)
      const health = await poolHealthTool(pool.id)
      
      console.log(`池子 ${pool.name}: 健康度=${health.score}, 战场评分=${battlefield.score}`)
      
      // 决策：是否需要调整
      if (health.score < 40) {
        console.log(`⚠️ 池子 ${pool.name} 健康度低，需要处理`)
        await this.handleUnhealthyPool(pool, health, battlefield)
      }
    }
    
    // 4. 寻找新机会
    console.log('🔍 寻找新机会...')
    const opportunities = opponents.game_opportunities || []
    
    for (const opp of opportunities) {
      if (opp.confidence > 0.7) {
        console.log(`💡 发现机会: ${opp.opportunity_type}, 置信度=${opp.confidence}`)
        await this.evaluateOpportunity(opp)
      }
    }
    
    // 5. 发送报告
    console.log('📧 发送早盘分析报告...')
    await this.sendMorningReport({
      opponents,
      alerts: criticalAlerts,
      pools,
      opportunities
    })
    
    console.log('✅ 早盘分析完成')
  }
  
  private async handleUnhealthyPool(pool, health, battlefield) {
    // 查询知识库：历史类似情况怎么处理的？
    const knowledge = await knowledgeQueryTool({
      context: `池子健康度低：${health.score}`
    })
    
    // 决策规则
    if (health.score < 30 || battlefield.score < 40) {
      console.log(`❌ 决策：关闭池子 ${pool.name}`)
      await closePool(pool.id)
      await notificationService.sendDecisionNotification({
        action: '关闭池子',
        symbol: pool.name,
        reason: `健康度${health.score}，战场评分${battlefield.score}`,
        confidence: 90
      })
    } else {
      console.log(`⚙️ 决策：调整池子 ${pool.name}`)
      await adjustPool(pool.id, { reason: 'health_low' })
    }
    
    // 记录决策
    await decisionTrackingTool({
      decision_type: 'adjust_pool',
      context: { pool, health, battlefield, knowledge }
    })
  }
  
  private async evaluateOpportunity(opp) {
    // 查询知识库
    const knowledge = await knowledgeQueryTool({
      context: `机会类型：${opp.opportunity_type}`
    })
    
    // 检查是否有操纵风险
    const manipulation = await manipulationDetectTool(opp.symbol)
    
    // 决策规则
    if (
      opp.confidence > 0.8 &&
      manipulation.risk === 'low' &&
      knowledge.hasSuccessCase
    ) {
      console.log(`✅ 决策：创建新池子 ${opp.symbol}`)
      await createPool({
        symbol: opp.symbol,
        reason: opp.opportunity_type
      })
      await notificationService.sendDecisionNotification({
        action: '创建池子',
        symbol: opp.symbol,
        reason: opp.opportunity_type,
        confidence: opp.confidence * 100
      })
      
      // 记录决策
      await decisionTrackingTool({
        decision_type: 'create_pool',
        context: { opp, knowledge, manipulation }
      })
    } else {
      console.log(`⏸️  暂不创建：${opp.symbol}`)
    }
  }
  
  private async sendMorningReport(data) {
    await notificationService.sendDailyReport({
      date: new Date().toISOString().split('T')[0],
      decisions: data.pools.length,
      pnl: 0, // TODO: 计算今日盈亏
      pools: data.pools.length,
      alerts: data.alerts.length
    })
  }
}
```

**调用**: 在 `scripts/morning_analysis.sh` 中调用

**交付**: 早上9点自动执行完整的早盘分析流程

---

### Task 4: 编写实时监控工作流 (半天)

**目标**: 每5分钟自动检查预警并响应

**文件**: `agent-ts/src/workflows/realtime-monitor-workflow.ts`

**实现**:
```typescript
export class RealtimeMonitorWorkflow {
  async execute() {
    // 1. 检查预警
    const alerts = await gameAlertTool()
    const critical = alerts.filter(a => a.level === 'critical')
    
    // 2. 处理紧急预警
    for (const alert of critical) {
      console.log(`🚨 紧急预警: ${alert.title}`)
      
      if (alert.alert_type === 'risk') {
        await this.handleRiskAlert(alert)
      } else if (alert.alert_type === 'opportunity') {
        await this.handleOpportunityAlert(alert)
      }
    }
    
    // 3. 检查池子健康度
    const pools = await listPools()
    for (const pool of pools) {
      const health = await poolHealthTool(pool.id)
      if (health.score < 30) {
        console.log(`🚨 池子 ${pool.name} 健康度危险`)
        await notificationService.sendAlert({
          level: 'critical',
          title: '池子健康度危险',
          message: `${pool.name} 健康度 ${health.score}`
        })
      }
    }
  }
  
  private async handleRiskAlert(alert) {
    // 风险预警处理逻辑
    await notificationService.sendAlert({
      level: 'critical',
      title: alert.title,
      message: alert.message
    })
  }
  
  private async handleOpportunityAlert(alert) {
    // 机会预警处理逻辑
  }
}
```

**交付**: 每5分钟自动监控并响应预警

---

### Task 5: 进程守护配置 (1小时)

**目标**: agent 崩溃后自动重启

**方案1: pm2**
```bash
# 安装pm2
npm install -g pm2

# 启动agent
cd agent-ts
pm2 start dist/index.js --name pi-agent

# 设置开机自启
pm2 save
pm2 startup

# 监控
pm2 monit
```

**方案2: systemd**
```bash
# 创建服务文件
sudo nano /etc/systemd/system/pi-agent.service

# 启动服务
sudo systemctl enable pi-agent
sudo systemctl start pi-agent
```

**交付**: agent 进程守护，崩溃自动重启

---

## ✅ 验证标准

完成后，系统应该能够：

1. ✅ 每天早上9点自动执行早盘分析
2. ✅ 每5分钟自动监控预警
3. ✅ 每天下午6点自动执行学习
4. ✅ 重要决策自动发送飞书通知
5. ✅ agent 崩溃后自动重启
6. ✅ 人类通过飞书监督 agent 运行

---

## 📊 预期效果

- agent 24/7 自主运行
- 每天自动分析、决策、学习
- 人类只需要监督，不需要干预
- 系统持续在股票市场赚钱

---

**下一步**: 开始实施 Task 1 - 配置定时任务
