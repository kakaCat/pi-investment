# 盘中监控架构：分层过滤设计

## 问题分析

### ❌ 低效设计（避免）

```
V2采集数据 → Agent每次都调用 → Agent深度分析 → 决策
              ↑
          浪费AI推理
          即使市场无异动也要分析
```

**问题**：
- 💰 成本高：每次都调用DeepSeek API，即使没有异动
- ⏱️ 效率低：Agent处理无用信息，浪费推理时间
- 📊 噪音多：Agent被大量"无事发生"的信号干扰

### ✅ 高效设计（推荐）

```
┌─────────────────────────────────────────────────┐
│  Layer 1: V2前哨（实时监控、初步过滤）            │
├─────────────────────────────────────────────────┤
│  • 实时采集市场数据                              │
│  • 计算量化指标（资金流、情绪指数、波动率）       │
│  • 初步异常检测（阈值触发）                      │
│  • 分类信号：重要/一般/无异常                    │
└─────────────────────────────────────────────────┘
                    ↓
         ┌──────────┴──────────┐
         │                     │
    无异常/一般            重要信号
         │                     │
    不触发Agent          触发Agent
         │                     ↓
    记录日志      ┌─────────────────────────┐
    下次周期      │ Layer 2: Agent指挥官     │
                  │ （深度推理、战略决策）    │
                  ├─────────────────────────┤
                  │ • 多维度信息融合         │
                  │ • 博弈推理（对手意图）   │
                  │ • 战略决策（买/卖/观望） │
                  │ • 生成执行计划           │
                  └─────────────────────────┘
```

## 分层架构设计

### Layer 1: quantsys-v2 前哨层

**职责**：实时监控、初步过滤、异常检测

#### 1.1 定时监控任务

```python
# quantsys-v2/services/monitoring/intraday_monitor.py

class IntradayMonitorService:
    """盘中监控服务 - V2前哨层"""
    
    def __init__(self):
        self.check_interval = 60  # 每60秒检查一次
        self.alert_thresholds = {
            "retail_emotion_extreme": 20,  # 散户情绪<20触发
            "institution_flow_large": 5亿,  # 机构流入/流出>5亿触发
            "manipulation_confidence": 0.7,  # 操纵检测置信度>0.7触发
            "price_gap_large": 0.05,  # 价格偏离>5%触发
        }
    
    async def run_monitoring_cycle(self):
        """执行一次监控周期"""
        alerts = []
        
        # 1. 对手行为检测
        behavior = await self.check_opponent_behavior()
        if behavior.has_alert:
            alerts.append(behavior.to_alert())
        
        # 2. 操纵检测
        manipulation = await self.check_manipulation()
        if manipulation.has_alert:
            alerts.append(manipulation.to_alert())
        
        # 3. 市场风格变化
        style_change = await self.check_market_style_change()
        if style_change.has_alert:
            alerts.append(style_change.to_alert())
        
        # 4. 信号价格偏离
        signal_gaps = await self.check_signal_price_gaps()
        if signal_gaps.has_alert:
            alerts.extend(signal_gaps.to_alerts())
        
        return self._categorize_alerts(alerts)
    
    def _categorize_alerts(self, alerts: List[Alert]) -> Dict:
        """分类告警：critical/high/medium/low"""
        return {
            "critical": [a for a in alerts if a.severity == "critical"],
            "high": [a for a in alerts if a.severity == "high"],
            "medium": [a for a in alerts if a.severity == "medium"],
            "low": [a for a in alerts if a.severity == "low"],
        }
```

#### 1.2 异常检测规则

```python
class OpponentBehaviorCheck:
    """对手行为异常检测"""
    
    async def check(self) -> CheckResult:
        behavior = await self.get_opponent_behavior()
        
        alerts = []
        
        # 规则1：散户极度恐慌
        if behavior.retail.emotion_index < 20:
            alerts.append(Alert(
                type="retail_panic",
                severity="high",
                title="散户极度恐慌",
                data={
                    "emotion_index": behavior.retail.emotion_index,
                    "net_flow": behavior.retail.net_flow,
                },
                reason="散户情绪指数降至18，可能是抄底机会",
                suggest_agent_action="evaluate_buying_opportunity"
            ))
        
        # 规则2：机构大规模出货
        if (behavior.institution.behavior == "distributing" and 
            abs(behavior.institution.net_flow) > 5亿):
            alerts.append(Alert(
                type="institution_distributing",
                severity="critical",
                title="机构大规模出货",
                data={
                    "net_flow": behavior.institution.net_flow,
                    "target_sectors": behavior.institution.target_sectors,
                },
                reason=f"机构流出{abs(behavior.institution.net_flow)/1亿:.1f}亿，可能有负面信息",
                suggest_agent_action="evaluate_exit_urgency"
            ))
        
        # 规则3：游资活跃度高 + 操纵信号
        if behavior.hot_money.activity_level == "high":
            manipulation = await self.check_manipulation_for_targets(
                behavior.hot_money.target_stocks
            )
            if manipulation.detected:
                alerts.append(Alert(
                    type="hot_money_manipulation",
                    severity="high",
                    title="游资操纵风险",
                    data={
                        "target_stocks": behavior.hot_money.target_stocks,
                        "manipulation_stage": manipulation.stage,
                    },
                    reason="游资活跃且检测到拉高出货信号",
                    suggest_agent_action="evaluate_trap_risk"
                ))
        
        return CheckResult(
            has_alert=len(alerts) > 0,
            alerts=alerts
        )
```

#### 1.3 告警上报API

```python
# quantsys-v2/api/routes/monitoring.py

@bp.route('/api/monitoring/alerts', methods=['GET'])
def get_current_alerts():
    """获取当前告警（Agent轮询此接口）"""
    monitor = IntradayMonitorService()
    alerts = monitor.get_pending_alerts()
    
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "has_critical": len(alerts["critical"]) > 0,
        "has_high": len(alerts["high"]) > 0,
        "alerts": alerts,
        "summary": {
            "critical": len(alerts["critical"]),
            "high": len(alerts["high"]),
            "medium": len(alerts["medium"]),
            "low": len(alerts["low"]),
        }
    })

@bp.route('/api/monitoring/alerts/<alert_id>/ack', methods=['POST'])
def acknowledge_alert(alert_id: str):
    """Agent确认已处理某个告警"""
    monitor = IntradayMonitorService()
    monitor.acknowledge_alert(alert_id)
    return jsonify({"status": "ok"})
```

### Layer 2: agent-ts 指挥官层

**职责**：仅处理重要告警，深度推理，战略决策

#### 2.1 告警轮询机制

```typescript
// agent-ts/src/services/monitoring/alert-poller.ts

class AlertPoller {
  private interval = 60_000; // 每60秒轮询一次
  private lastCheckTime: Date | null = null;
  
  async pollAlerts(): Promise<void> {
    // 从V2获取告警
    const response = await fetch(
      `${QUANTSYS_V2_API_URL}/api/monitoring/alerts`
    );
    const { has_critical, has_high, alerts } = await response.json();
    
    // 优先级过滤：只处理 critical 和 high
    if (!has_critical && !has_high) {
      logger.info('[AlertPoller] 无重要告警，跳过Agent分析');
      return;
    }
    
    // 触发Agent深度分析
    const criticalAlerts = alerts.critical || [];
    const highAlerts = alerts.high || [];
    
    if (criticalAlerts.length > 0) {
      await this.handleCriticalAlerts(criticalAlerts);
    }
    
    if (highAlerts.length > 0) {
      await this.handleHighAlerts(highAlerts);
    }
  }
  
  private async handleCriticalAlerts(alerts: Alert[]): Promise<void> {
    logger.info(`[AlertPoller] 处理 ${alerts.length} 个紧急告警`);
    
    for (const alert of alerts) {
      // 构建Agent分析提示词
      const prompt = this.buildAnalysisPrompt(alert);
      
      // 调用Agent深度分析
      const session = await SessionService.createSession({
        type: 'alert_analysis',
        context: { alert }
      });
      
      const decision = await session.analyze(prompt);
      
      // 执行决策
      await this.executeDecision(alert, decision);
      
      // 确认告警已处理
      await this.acknowledgeAlert(alert.id);
    }
  }
  
  private buildAnalysisPrompt(alert: Alert): string {
    switch (alert.type) {
      case 'retail_panic':
        return `
检测到散户极度恐慌：
- 情绪指数: ${alert.data.emotion_index}
- 资金流出: ${alert.data.net_flow / 1亿}亿

请分析：
1. 这是真正的恐慌抛售还是假信号？
2. 我们的股票池中哪些股票值得逢低买入？
3. 建议买入仓位和执行时机？

使用工具：
- pool_manage (list) - 查看当前股票池
- pool_battlefield (pool_id) - 评估池子战场优势
- market_style_detect() - 确认市场风格
`;

      case 'institution_distributing':
        return `
检测到机构大规模出货：
- 流出金额: ${Math.abs(alert.data.net_flow) / 1亿}亿
- 目标板块: ${alert.data.target_sectors.join(', ')}

请分析：
1. 我们持仓中是否有相关板块？
2. 机构出货的可能原因？
3. 应该立即退出还是观望？

使用工具：
- portfolio_status() - 查看当前持仓
- pool_battlefield (pool_id) - 评估池子战场
- opponent_behavior() - 获取完整对手行为
`;

      case 'hot_money_manipulation':
        return `
检测到游资操纵风险：
- 目标股票: ${alert.data.target_stocks.join(', ')}
- 操纵阶段: ${alert.data.manipulation_stage}

请分析：
1. 我们是否持有这些股票？
2. 如果持有，应该立即退出还是等待？
3. 是否有崩盘后的抄底机会？

使用工具：
- portfolio_status() - 查看持仓
- manipulation_detect() - 获取详细操纵信息
`;

      default:
        return `分析告警: ${alert.title}\n数据: ${JSON.stringify(alert.data)}`;
    }
  }
}
```

#### 2.2 智能决策执行

```typescript
// agent-ts/src/services/monitoring/decision-executor.ts

class DecisionExecutor {
  async executeDecision(alert: Alert, decision: AgentDecision): Promise<void> {
    logger.info('[DecisionExecutor] 执行决策', {
      alert_type: alert.type,
      action: decision.action,
    });
    
    switch (decision.action) {
      case 'buy':
        await this.executeBuy(decision);
        break;
      
      case 'sell':
        await this.executeSell(decision);
        break;
      
      case 'adjust_position':
        await this.adjustPosition(decision);
        break;
      
      case 'monitor':
        await this.addToWatchlist(decision);
        break;
      
      case 'no_action':
        logger.info('[DecisionExecutor] Agent决定不采取行动', {
          reason: decision.reason,
        });
        break;
    }
    
    // 记录决策到数据库（用于学习）
    await this.logDecision(alert, decision);
    
    // 发送通知
    await this.notifyUser(alert, decision);
  }
  
  private async executeBuy(decision: AgentDecision): Promise<void> {
    const { symbols, position_pct, entry_price, stop_loss } = decision;
    
    // 生成买入订单
    for (const symbol of symbols) {
      await TradeService.createOrder({
        symbol,
        action: 'buy',
        position_pct,
        entry_price,
        stop_loss,
        reason: decision.reason,
        source: 'intraday_monitoring',
      });
    }
    
    // 飞书通知
    await FeishuService.sendTradeAlert({
      action: 'buy',
      symbols,
      reason: decision.reason,
      confidence: decision.confidence,
    });
  }
}
```

## 信息过滤规则

### 规则矩阵

| 指标类型 | V2检测阈值 | 触发Agent条件 | Agent分析重点 |
|---------|-----------|--------------|--------------|
| **散户情绪** | 持续监控 | <20 或 >80 | 是否抄底/逃顶时机 |
| **机构流向** | 持续监控 | ±5亿以上 | 是否跟随/撤退 |
| **游资活跃** | 持续监控 | 活跃度高 + 操纵信号 | 是否陷阱/机会 |
| **操纵检测** | 每小时扫描 | 置信度>0.7 | 持仓风险评估 |
| **市场风格** | 每30分钟 | 风格切换 | 策略调整 |
| **信号偏离** | 实时计算 | >5% | 是否仍可执行 |
| **池子战场** | 触发式 | 评分<40 | 是否退出池子 |

### 优先级定义

```python
# V2告警严重程度定义

SEVERITY_RULES = {
    "critical": {
        # 立即触发Agent，需紧急决策
        "conditions": [
            ("institution_distributing", "net_flow < -10亿"),
            ("manipulation_detected", "stage == 'distribution' AND in_holdings"),
            ("market_crash", "index_drop > 3%"),
        ],
        "response_time": "立即（<1分钟）",
        "agent_required": True,
    },
    "high": {
        # 尽快触发Agent，需要决策
        "conditions": [
            ("retail_panic", "emotion_index < 20"),
            ("institution_distributing", "net_flow < -5亿"),
            ("manipulation_detected", "stage == 'markup'"),
            ("pool_battlefield_bad", "score < 40"),
        ],
        "response_time": "5分钟内",
        "agent_required": True,
    },
    "medium": {
        # 记录日志，下次周期性分析时处理
        "conditions": [
            ("market_style_change", "bull -> sideways"),
            ("retail_emotion_high", "60 < emotion_index < 80"),
        ],
        "response_time": "30分钟内",
        "agent_required": False,  # 可在周期性分析中处理
    },
    "low": {
        # 仅记录，不触发Agent
        "conditions": [
            ("normal_fluctuation", "all_indicators_normal"),
        ],
        "response_time": "无需响应",
        "agent_required": False,
    },
}
```

## 周期性 vs 事件驱动

### 混合模式

```
┌─────────────────────────────────────────┐
│  V2持续监控（每60秒）                    │
│  ├── 计算指标                           │
│  ├── 异常检测                           │
│  └── 分类告警                           │
└─────────────────────────────────────────┘
              ↓
    ┌─────────┴─────────┐
    │                   │
  有告警             无告警
    │                   │
    ↓                   ↓
┌─────────┐      ┌──────────┐
│ 事件驱动 │      │ 周期性   │
├─────────┤      ├──────────┤
│ critical │      │ 每30分钟 │
│ high     │      │ 摘要分析 │
│         │      │ (可选)   │
│ 立即触发 │      └──────────┘
│ Agent   │
└─────────┘
```

### 实现方式

```typescript
// agent-ts/src/services/monitoring/scheduler.ts

class MonitoringScheduler {
  private eventDrivenPoller: AlertPoller;
  private periodicAnalyzer: PeriodicAnalyzer;
  
  async start(): Promise<void> {
    // 1. 事件驱动：每60秒轮询V2告警
    this.eventDrivenPoller.start({
      interval: 60_000,
      filter: ['critical', 'high'],  // 只处理重要告警
    });
    
    // 2. 周期性分析（可选）：每30分钟做全局分析
    this.periodicAnalyzer.start({
      interval: 30 * 60_000,
      tasks: [
        'opponent_behavior',  // 对手行为全景
        'market_style_detect', // 市场风格
        'pool_health_check',   // 池子健康度
      ],
    });
  }
}
```

## 成本效益分析

### ❌ 无过滤设计

```
监控频率: 每60秒
每日监控: 4小时 × 60次 = 240次
AI调用: 240次 × 100 tokens = 24,000 tokens/天
月成本: 24,000 × 20个交易日 × DeepSeek价格

问题：大部分时间市场无异动，浪费成本
```

### ✅ 分层过滤设计

```
V2监控: 240次/天（免费）
Agent调用: 仅触发时（预估5-10次/天）
AI调用: 10次 × 500 tokens = 5,000 tokens/天
月成本: 5,000 × 20个交易日 × DeepSeek价格

节省: 80% AI成本
```

## 总结

### 设计原则

1. **V2是前哨**：负责实时监控、初步过滤、异常检测
2. **Agent是指挥官**：仅处理重要信息、深度推理、战略决策
3. **分层过滤**：critical/high触发Agent，medium/low记录日志
4. **混合模式**：事件驱动（紧急）+ 周期性（全局分析）

### 关键收益

- 💰 **成本优化**：减少80% AI推理调用
- ⚡ **效率提升**：Agent聚焦重要决策
- 🎯 **质量提升**：减少噪音，提高信号质量
- 🔧 **可维护性**：清晰的职责分工

---

**结论**：V2负责"看"，Agent负责"想"。只有重要的事情才需要深度思考。
