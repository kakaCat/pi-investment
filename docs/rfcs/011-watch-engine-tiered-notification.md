# RFC 011: WatchEngine 分层提醒与自动升级系统

## 文档信息

- **编号**：RFC 011
- **标题**：WatchEngine 分层提醒与自动升级系统
- **状态**：设计提案（待评审）
- **作者**：w-5b8aac2a（investor）
- **日期**：2026-09-08

---

## 1. 背景与问题

### 1.1 现状痛点

当前 WatchEngine 触发后发送的飞书消息存在以下问题：

**问题 1：层级模糊**
- 所有触发都走同一格式，分不清是"直接提醒"还是"需要 agent 介入"
- 用户收到消息后不知道该做什么（买/卖/观察）

**问题 2：Token 消耗过高**
- 所有触发都可能唤醒 agent，但 80% 的触发只是观察类信息
- agent 分析需要时间（5-10s LLM 推理），简单提醒也要走 LLM 不划算

**问题 3：僵尸规则堆积**
- 44 条规则中 38 条（86%）没有 `expires_at`
- 价格已远离触发位 20%+ 的规则还在监控（如 #91 沪电股份，预案"9/2买点118.10"已过期）
- 波段已完成的规则还在监控（如 #41 中国海油，"波段已完成(30.4→33.7，+10.9%)"）

**问题 4：缺少自动升级机制**
- L0/L1 触发后如果满足特定条件（如触发频率异常、价格偏差过大），应该自动升级为 agent 介入
- 当前完全靠用户手动判断，容易遗漏关键信号

**问题 5：交互未完成**
- 飞书消息中"查看详细"按钮无功能
- 用户无法方便地停止/修改规则

**问题 6：架构腐化风险**
- 多个 agent 并行开发时，各自实现通知逻辑
- 5 个通知实现，3 种消息格式，无法统一维护

---

## 2. 设计目标

1. **减少 Token 消耗**：L0/L1 触发直接发飞书（不消耗 token），只有 L2 触发才唤醒 agent
2. **自动升级机制**：L0/L1 触发满足特定条件时自动升级为 L2（agent 介入）
3. **规则生命周期管理**：默认有效期 + 健康度检查，防止僵尸规则堆积
4. **复用 DDD 通知架构**：WatchEngine 改为调用 `NotificationFacade`，而不是自己实现飞书发送
5. **AI 决策留痕**：agent 的完整决策链（分析→决策→执行→结果）保存到 `decision_audit`，供复盘
6. **架构治理**：通过 CLAUDE.md 约束，让所有 agent 遵循统一的通知架构

---

## 3. 架构设计（DDD 分层）

### 3.1 现有 DDD 通知架构（可复用）

```
domain/notification/
├── models/channel.py           ← NotificationChannel（端口，抽象基类）
├── models/notification.py      ← Notification（领域模型）
└── services/notification_service.py  ← NotificationService（领域服务）

infrastructure/notification/
└── channels/feishu_channel.py  ← FeishuChannel（适配器，实现端口）

application/notification/
└── notification_facade.py      ← NotificationFacade（应用层门面）
    └── send_watch_triggered()  ← 盯盘触发通知的专用方法（已支持 notify_mode 分流）
```

### 3.2 WatchEngine 改造架构

```
domain/watch/                          ← 领域层（新增）
├── models.py
│   ├── WatchRule                      ← 聚合根（规则）
│   ├── Condition                      ← 值对象（条件）
│   ├── ActionHint                     ← 值对象（行动指引）✨ 新增
│   ├── TriggerLevel                   ← 枚举（L0/L1/L2）✨ 新增
│   └── EscalationPolicy               ← 值对象（升级策略）✨ 新增
├── ports.py
│   ├── IWatchRuleRepository
│   ├── IEscalationChecker             ← 升级检查端口 ✨ 新增
│   └── IRuleHealthChecker             ← 规则健康检查端口 ✨ 新增
└── services/
    ├── condition_evaluator.py         ← 条件评估（从 conditions.py 迁移）
    ├── escalation_checker.py          ← 升级判断逻辑 ✨ 新增
    └── rule_health_checker.py         ← 规则健康检查 ✨ 新增

application/services/watch_engine/
├── engine.py                          ← WatchEngine（tick 循环编排）
├── notifier.py                        ← 改造：调用 NotificationFacade
├── dto.py                             ← TriggerPayload（DTO）✨ 新增
└── factory.py                         ← 装配（依赖注入）

infrastructure/scheduler/
└── watch_rule_health_job.py           ← 定时任务：每日规则健康检查 ✨ 新增
```

---

## 4. 核心组件设计

### 4.1 TriggerLevel 枚举（触发层级）

```python
# domain/watch/models.py
from enum import Enum

class TriggerLevel(Enum):
    """触发层级：决定是否需要 agent 介入"""
    L0_MESSAGE = "L0"        # 消息类：纯信息通知，直接发飞书
    L1_OBSERVATION = "L1"    # 观察类：观察提醒，直接发飞书
    L2_ACTION = "L2"         # 行动类：关键操作，发给 agent 决策
```

**层级定义**：

| 层级 | 说明 | Token 消耗 | 示例 |
|------|------|-----------|------|
| L0_MESSAGE | 纯信息通知 | 0 | 板块异动、数据告警 |
| L1_OBSERVATION | 观察提醒 | 0 | 接近触发位、缩量盘整 |
| L2_ACTION | 关键操作 | 有（LLM 推理） | 买卖股票、改规则、撤销规则 |

---

### 4.2 ActionHint 值对象（行动指引）

```python
# domain/watch/models.py
from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass(frozen=True)
class ActionHint:
    """行动指引（值对象）"""
    
    # 触发层级
    trigger_level: TriggerLevel
    
    # 触发后的动作类型
    action_on_trigger: str
    # L0: 'message'（纯信息）
    # L1: 'observe'（观察提醒）
    # L2: 'buy' | 'sell' | 'reduce_position' | 'adjust_rule' | 'delete_rule'
    
    # 是否需要 agent 参与（L2 必为 True）
    requires_agent: bool
    
    # 行动参数（L2 专用）
    position_ref: Optional[str] = None      # empty/hold/reduce/add
    confidence: Optional[str] = None        # A/B/C（对应 R-009）
    max_position_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    adjust_params: Optional[Dict] = None    # adjust_rule 专用
    
    def should_notify_agent(self) -> bool:
        """是否需要唤醒 agent"""
        return self.trigger_level == TriggerLevel.L2_ACTION and self.requires_agent
```

---

### 4.3 EscalationPolicy 值对象（升级策略）

```python
# domain/watch/models.py
@dataclass(frozen=True)
class EscalationPolicy:
    """升级策略：L0/L1 触发满足条件时自动升级为 L2"""
    
    auto_escalate: bool = True
    
    # 触发频率升级
    max_triggers_per_window: Optional[Dict] = None
    # {"count": 3, "window_minutes": 10}
    
    # 价格偏差升级
    price_deviation_pct: Optional[float] = None
    # 5.0（偏差>5%升级）
    
    # 核心区域升级
    core_zones: Optional[List[Dict]] = None
    # [{"low": 4.65, "high": 5.13, "reason": "平台震荡区"}]
    
    # 量能异常升级
    volume_ratio_multiplier: Optional[float] = None
    # 2.0（实际ratio > 阈值×2 升级）
    
    # 多规则共振升级
    multi_rule_confluence: Optional[Dict] = None
    # {"enabled": true, "window_seconds": 60}
```

---

### 4.4 EscalationChecker 领域服务（升级判断）

```python
# domain/watch/services/escalation_checker.py
class EscalationChecker:
    """升级检查器：判断 L0/L1 触发是否应升级为 L2"""
    
    def should_escalate(
        self,
        rule: WatchRule,
        condition: dict,
        quote: QuoteData,
        result: EvalResult,
        recent_triggers: List[TriggerEvent]
    ) -> Optional[str]:
        """检查是否应升级，返回升级原因（None=不升级）"""
        policy = rule.escalation_policy
        if not policy or not policy.auto_escalate:
            return None
        
        # 1. 触发频率升级
        if policy.max_triggers_per_window:
            count = policy.max_triggers_per_window['count']
            window = policy.max_triggers_per_window['window_minutes']
            recent_count = self._count_recent_triggers(rule.id, window)
            if recent_count >= count:
                return f"触发频率异常（{window}分钟内{recent_count}次），可能洗盘/真突破"
        
        # 2. 价格偏差升级
        if policy.price_deviation_pct:
            rule_price = condition['params'].get('price')
            if rule_price:
                deviation = abs(quote.price - rule_price) / rule_price * 100
                if deviation > policy.price_deviation_pct:
                    return f"价格偏差{deviation:.1f}%，原预案位置失效"
        
        # 3. 核心区域升级
        if policy.core_zones:
            for zone in policy.core_zones:
                if zone['low'] <= quote.price <= zone['high']:
                    return f"进入核心区域 {zone['low']}-{zone['high']}（{zone['reason']}）"
        
        # 4. 量能异常升级
        if policy.volume_ratio_multiplier and result.value:
            threshold = condition['params'].get('multiple', 1.5)
            if result.value > threshold * policy.volume_ratio_multiplier:
                return f"量能异常（{result.value:.1f}x vs 阈值{threshold}x），可能主力异动"
        
        # 5. 多规则共振升级
        if policy.multi_rule_confluence and policy.multi_rule_confluence.get('enabled'):
            window = policy.multi_rule_confluence['window_seconds']
            concurrent = self._count_concurrent_triggers(rule.symbol, window)
            if concurrent >= 2:
                return f"多规则共振（{concurrent}条规则同时触发），价格剧烈波动"
        
        return None
```

---

### 4.5 RuleHealthChecker 领域服务（规则健康检查）

```python
# domain/watch/services/rule_health_checker.py
class RuleHealthChecker:
    """规则健康度检查器：每天收盘后评估规则是否还有效"""
    
    def check_all_rules(self) -> List[RuleHealthReport]:
        """检查所有启用规则的健康度"""
        reports = []
        for rule in self.get_enabled_rules():
            report = self._check_rule(rule)
            reports.append(report)
            
            # 自动处理
            if report.status == 'EXPIRED':
                self._disable_rule(rule, reason="已过有效期")
            elif report.status == 'STALE':
                self._disable_rule(rule, reason=f"价格偏差{report.deviation_pct:.1f}%")
            elif report.status == 'OUTDATED':
                self._disable_rule(rule, reason="预案日期已过期")
            elif report.status == 'INACTIVE':
                self._mark_for_review(rule, reason="30天未触发")
        
        return reports
    
    def _check_rule(self, rule) -> RuleHealthReport:
        """检查单条规则健康度"""
        # 1. 检查有效期
        if rule.expires_at and rule.expires_at < datetime.now():
            return RuleHealthReport(rule.id, 'EXPIRED', '已过有效期')
        
        # 2. 检查价格偏差
        current_price = self._get_current_price(rule.symbol)
        trigger_price = self._extract_trigger_price(rule.conditions)
        if trigger_price:
            deviation_pct = abs(current_price - trigger_price) / trigger_price * 100
            if deviation_pct > 20:
                return RuleHealthReport(rule.id, 'STALE', f'价格偏差{deviation_pct:.1f}%')
        
        # 3. 检查预案日期
        if rule.context:
            if self._is_context_outdated(rule.context):
                return RuleHealthReport(rule.id, 'OUTDATED', '预案日期已过期')
        
        # 4. 检查触发活跃度
        last_trigger = self._get_last_trigger(rule.id)
        if last_trigger and (datetime.now() - last_trigger).days > 30:
            return RuleHealthReport(rule.id, 'INACTIVE', '30天未触发')
        
        return RuleHealthReport(rule.id, 'HEALTHY', '正常')
```

**健康度状态**：

| 状态 | 说明 | 处理动作 |
|------|------|---------|
| HEALTHY | 正常 | 继续监控 |
| EXPIRED | 已过有效期 | 自动禁用 |
| STALE | 价格偏差 >20% | 自动禁用（位置失效） |
| OUTDATED | 预案日期已过期 | 自动禁用（如"9/2买点"已过期） |
| INACTIVE | 30天未触发 | 标记审查（不自动禁用，提醒人工） |

---

## 5. AI 决策保存设计（复用 decision_audit）

### 5.1 决策记录流程

```
WatchEngine 触发
  ↓
L1→L2 升级 或 L2 直接触发
  ↓
agent 收到 payload
  ↓
agent 分析（查持仓/对手/板块/regime）
  ↓
agent 决策（执行/调整/拒绝）
  ↓
agent 执行（下单/改规则/撤销）
  ↓
【保存决策记录】→ decision_audit
  ↓
agent 发飞书通知用户（含决策审计ID）
```

### 5.2 决策记录内容

```python
# 复用现有 decision_audit 表
decision_audit(
    action="record",
    decision_type="watch_triggered_action",  # 新类型
    parameters={
        "rule_id": 78,
        "symbol": "600219",
        "trigger_level": "L2",
        "escalated_from": "L1",  # 如果是 L1 升级的
        "escalation_reason": "触发频率异常（10分钟内3次）",
        
        # 触发信息
        "trigger": {
            "condition": "price_break above 5.13 AND volume_surge 1.5x",
            "price": 5.15,
            "volume_ratio": 1.8,
            "change_pct": 1.2
        },
        
        # AI 评估
        "ai_evaluation": {
            "regime": "euphoria",
            "position_limit": "30%",
            "current_position": "0.6%",
            "sector_flow": "+2.1%",
            "opponent_panic_index": 45,
            "has_position": False
        },
        
        # 决策结果
        "decision": {
            "action": "buy",  # buy/sell/adjust_rule/reject
            "reason": "执行预案：买入100股@5.15",
            "confidence": "B"
        },
        
        # 执行结果
        "execution": {
            "order_id": "12345",
            "filled_price": 5.15,
            "filled_quantity": 100,
            "status": "filled"
        }
    },
    reasoning="regime=euphoria 仓位上限30%，当前0.6%余量充足；板块资金+2.1%流入，对手散户恐慌指数45正常；未持有该标的，符合买入条件",
    related_entity_id="600219",
    related_entity_type="stock"
)
```

### 5.3 复盘查询

```python
# 查询某只股票的所有 AI 决策
decision_history(
    entity_id="600219",
    entity_type="stock",
    decision_type="watch_triggered_action"
)

# 返回：
# - 触发信息（规则、条件、价格、量能）
# - AI 评估（regime、板块、对手、持仓）
# - 决策结果（执行/调整/拒绝）
# - 执行结果（订单号、成交价、数量）
# - 审计 ID
```

---

## 6. 数据库表扩展

```sql
-- 规则表增加升级策略字段
ALTER TABLE quant.watch_rules 
ADD COLUMN escalation_policy JSONB DEFAULT '{}';

-- 规则表增加行动指引字段
ALTER TABLE quant.watch_rules 
ADD COLUMN action_hint JSONB DEFAULT '{}';

-- 新规则默认30天有效期（在应用层实现，不改表结构）
-- expires_at 字段已存在

-- 升级历史记录表（可选，P1）
CREATE TABLE quant.watch_escalations (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    trigger_level_from VARCHAR(2) NOT NULL,  -- L0/L1
    trigger_level_to VARCHAR(2) NOT NULL,    -- L2
    escalation_reason TEXT NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 规则健康度历史记录表（可选，P1）
CREATE TABLE quant.watch_rule_health_reports (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,  -- HEALTHY/EXPIRED/STALE/OUTDATED/INACTIVE
    reason TEXT,
    checked_at TIMESTAMP DEFAULT NOW()
);
```

---

## 7. 消息格式设计

### 7.1 L0 消息类（直接发飞书）

```
📢 【消息】600219 南山铝业 (规则#100)
触发：涨幅+3.2%
信息：铝板块联动上涨，关注后续走势

Token 消耗：0
```

### 7.2 L1 观察类（直接发飞书）

```
📊 【观察提醒】600036 招商银行 (规则#76)
触发：跌破38.9进入低吸区38.6-38.9
建议：观察（无需行动）
预案：缩量止跌则建仓首仓≤15%，放量下跌则观望

Token 消耗：0
```

### 7.3 L1 观察类（自动升级为 L2）

```
🔺 【升级提醒】600219 南山铝业 (规则#78)
触发：突破5.13 + 放量确认（量比1.8x）
升级原因：触发频率异常（10分钟内3次），可能洗盘/真突破
已转交 agent 分析...

─────────────
【AI 分析】（agent 处理后追加）
决策：不执行预案，观察为主
理由：洗盘特征明显（反复穿越5.13），等方向明确

─────────────
审计ID：DEC-20260908143022-xxx
复盘查询：decision_history(entity_id="600219")

Token 消耗：有（LLM 推理）
```

### 7.4 L2 行动类（agent 决策后）

```
🚨 【AI 决策】600219 南山铝业 (规则#78)
触发：价格突破5.13 + 放量确认（量比1.8x）
预案：买入（首仓≤10%，止损4.65）

AI 评估：
- regime=euphoria，仓位上限30%，当前0.6%余量充足
- 板块资金+2.1%流入，对手散户恐慌指数45正常
- 持仓检查：未持有该标的

决策：执行预案，买入100股@5.15
执行：已下单（订单#12345）

─────────────
审计ID：DEC-20260908143022-xxx
复盘查询：decision_history(entity_id="600219")

Token 消耗：有（LLM 推理）
```

### 7.5 规则健康检查报告（每日）

```
🧹 【规则健康检查】2026-09-08

自动禁用：
- 过期规则：2 条（#91, #48）
- 失效规则（价格偏差>20%）：1 条（#41）
- 过期预案：1 条（#91）

待人工审查：
- 30天未触发：3 条（#70, #71, #66）

当前规则统计：
- 总数：44 条
- 启用：38 条
- 禁用：6 条
- 健康：35 条
- 异常：3 条
```

---

## 8. 架构治理（CLAUDE.md 约束）

### 8.1 更新根目录 CLAUDE.md

在 `pi-investment/CLAUDE.md` 的 "Development Guidelines" 部分添加：

```markdown
## 架构规范（强制遵守）

### 通知发送

**所有通知必须走 NotificationFacade，禁止直接调用飞书 SDK 或 agent_service**。

#### 强制规则
1. 应用层只能 import `application.notification.notification_facade.NotificationFacade`
2. 禁止 import `infrastructure.notification.channels.*`
3. 禁止直接调用 `requests.post(feishu_webhook_url)`
4. 新通知类型必须先扩展 `NotificationFacade`，再使用

#### 示例

✅ 正确：
```python
from application.notification import NotificationFacade

facade = NotificationFacade(...)
result = facade.send_watch_triggered(
    symbol='600219',
    name='南山铝业',
    price=5.15,
    condition={...},
    message='突破5.13',
    trigger_level='L2',
    action_hint={...}
)
```

❌ 错误：
```python
from infrastructure.notification.channels import FeishuChannel
channel = FeishuChannel(...)
channel.send(...)
```

#### 违规后果
- 代码审查拒绝
- CI 检查失败（如果有）
- 运行时监控告警

#### 参考文档
- 通知开发指南：`docs/guides/notification-development-guide.md`
- WatchEngine 分层设计：`docs/rfcs/011-watch-engine-tiered-notification.md`
```

### 8.2 更新 agent-dh/CLAUDE.md

在 `agent-dh/CLAUDE.md` 的 "Important Notes" 部分添加：

```markdown
### 架构规范（通知发送）

**所有通知必须走 NotificationFacade，禁止直接调用飞书 SDK**。

- 应用层只能 import `application.notification.NotificationFacade`
- 禁止 import `infrastructure.notification.channels.*`
- 新通知类型必须先扩展 NotificationFacade

参考：`pi-investment/CLAUDE.md` 的"架构规范"章节
```

### 8.3 代码结构约束（import 限制）

```python
# infrastructure/notification/channels/__init__.py
# 不导出 FeishuChannel，只导出给装配层用
__all__ = []  # 应用层无法 from infrastructure.notification.channels import FeishuChannel

# application/notification/__init__.py
from .notification_facade import NotificationFacade
__all__ = ['NotificationFacade']  # 只暴露门面，隐藏内部实现
```

---

## 9. 实施步骤

### Phase 1：核心分层与升级（P0，预计 4-6 小时）

**Step 1.1：Domain 层（1 小时）**
- 新建 `domain/watch/models.py`（TriggerLevel、ActionHint、EscalationPolicy）
- 新建 `domain/watch/services/escalation_checker.py`
- 新建 `domain/watch/services/rule_health_checker.py`

**Step 1.2：数据库扩展（0.5 小时）**
- 执行 SQL：`ALTER TABLE watch_rules ADD COLUMN escalation_policy JSONB, ADD COLUMN action_hint JSONB`
- 批量给现有规则补默认有效期（30天）

**Step 1.3：Application 层（1.5 小时）**
- 改造 `application/services/watch_engine/notifier.py`：调用 `NotificationFacade`
- 新建 `application/services/watch_engine/dto.py`（TriggerPayload）

**Step 1.4：引擎集成（1 小时）**
- 改造 `engine.py`：触发后调用 `EscalationChecker` 判断是否升级
- 集成 `NotificationFacade.send_watch_triggered()`

**Step 1.5：规则批量标注（1 小时）**
- 给现有 44 条规则批量标注 `action_hint.trigger_level`（L0/L1/L2）
- 给关键规则配置 `escalation_policy`

**Step 1.6：CLAUDE.md 约束（0.5 小时）**
- 更新 `pi-investment/CLAUDE.md`（架构规范章节）
- 更新 `agent-dh/CLAUDE.md`（Important Notes 章节）

### Phase 2：规则生命周期管理（P1，预计 2-3 小时）

**Step 2.1：定时任务（1 小时）**
- 新建 `infrastructure/scheduler/watch_rule_health_job.py`
- 集成到 `daily_jobs_bootstrap.py`（每日 16:30 收盘后执行）

**Step 2.2：僵尸规则清理（0.5 小时）**
- 一次性脚本：清理现有僵尸规则（价格偏差>20%、预案过期）

**Step 2.3：飞书通知（0.5 小时）**
- 健康度报告飞书通知（每日收盘后）

### Phase 3：前端交互（P2，预计 2-3 小时，可选）

**Step 3.1：「查看详细」功能化（1.5 小时）**
- Web GUI 规则详情页（完整上下文+历史触发+相关持仓）

**Step 3.2：规则操作按钮（1 小时）**
- Web GUI 规则管理页（停止/修改/升级/删除）

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 升级条件误触发 | agent 被频繁唤醒，token 消耗增加 | 升级条件保守化（如触发频率≥3次才升级） |
| 健康度检查误禁用 | 有效规则被误禁用 | INACTIVE 状态不自动禁用，只标记审查 |
| 现有规则批量标注错误 | 规则行为异常 | 批量标注前人工审核，分批执行 |
| NotificationFacade 改造影响其他功能 | 其他通知失效 | 保留旧接口，新接口并行运行 1 周后切换 |
| Agent 不遵循 CLAUDE.md 约束 | 架构腐化 | CLAUDE.md 是 agent 必读文件，违规会被发现 |

---

## 11. 验收标准

### Phase 1 验收
- [ ] L0/L1 触发直接发飞书，不消耗 token
- [ ] L1 触发满足升级条件时自动升级为 L2
- [ ] L2 触发发给 agent，agent 决策后发飞书通知用户（含审计ID）
- [ ] AI 决策保存到 `decision_audit` 表
- [ ] 现有 44 条规则全部标注 trigger_level
- [ ] 飞书消息格式清晰（L0/L1/L2 三种格式，含审计ID）
- [ ] CLAUDE.md 已更新架构规范

### Phase 2 验收
- [ ] 新规则默认 30 天有效期
- [ ] 每日 16:30 自动检查规则健康度
- [ ] 过期/失效规则自动禁用
- [ ] 健康度报告飞书通知

### Phase 3 验收（可选）
- [ ] Web GUI 规则详情页可用
- [ ] Web GUI 规则操作按钮可用

---

## 12. 后续优化方向

1. **升级统计分析**：哪些规则经常升级→优化阈值
2. **用户自定义升级条件**：Web GUI 配置
3. **升级后自动降级**：agent 处理后改回 L1
4. **规则健康度看板**：可视化展示规则健康状态
5. **智能有效期**：根据规则类型自动设置有效期（波段规则 7 天，长期监控 90 天）
6. **AI 决策复盘报告**：每周汇总 agent 决策质量（胜率、盈亏、决策理由）

---

## 13. 参考资料

- 现有 DDD 通知架构：`domain/notification/`
- WatchEngine 现有实现：`application/services/watch_engine/`
- B1/B2 升级记录：commit `b0319187`
- 数据污染修复记录：memory `0b42989e-9f67-45e7-b581-263302014c91`
- 决策审计表：`quant.decision_audit`

---

**文档结束**
