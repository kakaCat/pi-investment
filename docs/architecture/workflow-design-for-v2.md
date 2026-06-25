# quantsys-v2 工作流系统设计

## 设计原则

**工作流由 quantsys-v2 负责，agent-ts 只是调用工具**

- quantsys-v2: 编排工作流、执行决策逻辑、管理状态
- agent-ts: 提供工具接口，被动响应调用
- 定时任务: 触发 quantsys-v2 的工作流 API

---

## 架构设计

```
Crontab (定时触发)
    ↓
quantsys-v2 工作流引擎
    ├── MorningAnalysisWorkflow
    │   ├── 调用 OpponentBehaviorService
    │   ├── 调用 GameAlertService
    │   ├── 调用 DecisionService
    │   └── 发送通知
    │
    ├── RealtimeMonitorWorkflow
    │   ├── 监控预警
    │   ├── 检查池子健康度
    │   └── 紧急通知
    │
    └── DailyLearningWorkflow
        ├── 评估历史决策
        ├── 提取知识
        └── 优化参数
```

---

## 实现方案

### 1. 工作流基础框架

**文件**: `quantsys-v2/application/workflows/base.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime
import logging

class WorkflowStep:
    """工作流步骤"""
    def __init__(self, name: str, service_method, params: Dict = None):
        self.name = name
        self.service_method = service_method
        self.params = params or {}
        self.result = None
        self.status = 'pending'  # pending, running, success, failed
        self.start_time = None
        self.end_time = None
        self.error = None

class Workflow(ABC):
    """工作流基类"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.steps: List[WorkflowStep] = []
        self.context: Dict[str, Any] = {}
        self.logger = logging.getLogger(self.name)
    
    @abstractmethod
    def define_steps(self) -> List[WorkflowStep]:
        """定义工作流步骤"""
        pass
    
    def execute(self) -> Dict[str, Any]:
        """执行工作流"""
        self.logger.info(f"开始执行工作流: {self.name}")
        
        # 定义步骤
        self.steps = self.define_steps()
        
        # 执行每个步骤
        for step in self.steps:
            try:
                self.logger.info(f"执行步骤: {step.name}")
                step.status = 'running'
                step.start_time = datetime.now()
                
                # 执行步骤
                step.result = step.service_method(**step.params)
                
                # 将结果放入上下文
                self.context[step.name] = step.result
                
                step.status = 'success'
                step.end_time = datetime.now()
                
            except Exception as e:
                self.logger.error(f"步骤 {step.name} 失败: {str(e)}")
                step.status = 'failed'
                step.error = str(e)
                step.end_time = datetime.now()
                
                # 决定是否继续
                if not self.handle_error(step, e):
                    break
        
        # 返回执行结果
        return self.get_result()
    
    def handle_error(self, step: WorkflowStep, error: Exception) -> bool:
        """处理错误，返回是否继续执行"""
        # 默认：记录错误但继续执行
        return True
    
    def get_result(self) -> Dict[str, Any]:
        """获取工作流执行结果"""
        return {
            'workflow': self.name,
            'status': 'success' if all(s.status == 'success' for s in self.steps) else 'failed',
            'steps': [
                {
                    'name': s.name,
                    'status': s.status,
                    'duration': (s.end_time - s.start_time).total_seconds() if s.end_time else None,
                    'error': s.error
                }
                for s in self.steps
            ],
            'context': self.context
        }
```

---

### 2. 早盘分析工作流

**文件**: `quantsys-v2/application/workflows/morning_analysis_workflow.py`

```python
from .base import Workflow, WorkflowStep
from ..services.opponent_behavior_service import OpponentBehaviorService
from ..services.game_alert_service import GameAlertService
from ..services.decision_service import DecisionService
from ..services.knowledge_service import KnowledgeService

class MorningAnalysisWorkflow(Workflow):
    """早盘分析工作流"""
    
    def __init__(self):
        super().__init__()
        self.opponent_service = OpponentBehaviorService()
        self.alert_service = GameAlertService()
        self.decision_service = DecisionService()
        self.knowledge_service = KnowledgeService()
    
    def define_steps(self):
        return [
            WorkflowStep(
                name='analyze_opponents',
                service_method=self.opponent_service.analyze_market,
                params={}
            ),
            WorkflowStep(
                name='check_alerts',
                service_method=self.alert_service.check_alerts,
                params={}
            ),
            WorkflowStep(
                name='evaluate_pools',
                service_method=self.evaluate_pools,
                params={}
            ),
            WorkflowStep(
                name='find_opportunities',
                service_method=self.find_opportunities,
                params={}
            ),
            WorkflowStep(
                name='send_report',
                service_method=self.send_morning_report,
                params={}
            )
        ]
    
    def evaluate_pools(self):
        """评估现有池子"""
        # TODO: 获取所有池子
        pools = []  # get_all_pools()
        
        results = []
        for pool in pools:
            # 战场评估
            battlefield = self.battlefield_assessor.assess(pool)
            
            # 健康度检查
            health = self.health_tracker.check(pool)
            
            # 决策逻辑
            if health['score'] < 30 or battlefield['score'] < 40:
                # 关闭池子
                decision = {
                    'action': 'close_pool',
                    'pool_id': pool['id'],
                    'reason': f"健康度{health['score']}, 战场{battlefield['score']}"
                }
                results.append(decision)
                
                # 记录决策
                self.decision_service.record_decision(decision)
        
        return results
    
    def find_opportunities(self):
        """寻找新机会"""
        # 从对手行为分析中获取机会
        opponents = self.context.get('analyze_opponents', {})
        opportunities = opponents.get('game_opportunities', [])
        
        results = []
        for opp in opportunities:
            if opp['confidence'] > 0.8:
                # 查询知识库
                knowledge = self.knowledge_service.query({
                    'context': f"机会类型: {opp['opportunity_type']}"
                })
                
                # 检查操纵风险
                # manipulation = self.manipulation_detector.detect(opp['symbol'])
                
                # 决策逻辑
                if knowledge.get('has_success_case'):
                    decision = {
                        'action': 'create_pool',
                        'symbol': opp['symbol'],
                        'reason': opp['opportunity_type'],
                        'confidence': opp['confidence']
                    }
                    results.append(decision)
                    
                    # 记录决策
                    self.decision_service.record_decision(decision)
        
        return results
    
    def send_morning_report(self):
        """发送早盘报告"""
        # TODO: 集成通知服务
        report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'opponents': self.context.get('analyze_opponents'),
            'alerts': self.context.get('check_alerts'),
            'pool_decisions': self.context.get('evaluate_pools'),
            'opportunities': self.context.get('find_opportunities')
        }
        
        # 发送飞书通知
        # notification_service.send_morning_report(report)
        
        return report
```

---

### 3. 实时监控工作流

**文件**: `quantsys-v2/application/workflows/realtime_monitor_workflow.py`

```python
from .base import Workflow, WorkflowStep

class RealtimeMonitorWorkflow(Workflow):
    """实时监控工作流"""
    
    def define_steps(self):
        return [
            WorkflowStep(
                name='check_critical_alerts',
                service_method=self.check_critical_alerts,
                params={}
            ),
            WorkflowStep(
                name='check_pool_health',
                service_method=self.check_pool_health,
                params={}
            ),
            WorkflowStep(
                name='send_notifications',
                service_method=self.send_notifications,
                params={}
            )
        ]
    
    def check_critical_alerts(self):
        """检查紧急预警"""
        alerts = self.alert_service.check_alerts()
        critical = [a for a in alerts if a['level'] == 'critical']
        return critical
    
    def check_pool_health(self):
        """检查池子健康度"""
        # TODO: 获取所有池子并检查健康度
        dangerous_pools = []
        return dangerous_pools
    
    def send_notifications(self):
        """发送通知"""
        critical_alerts = self.context.get('check_critical_alerts', [])
        dangerous_pools = self.context.get('check_pool_health', [])
        
        # 如果有紧急情况，发送通知
        if critical_alerts or dangerous_pools:
            # notification_service.send_urgent_alert(...)
            pass
```

---

### 4. 工作流 API 端点

**文件**: `quantsys-v2/adapters/inbound/api/routes/workflow.py`

```python
from flask import Blueprint, jsonify
from application.workflows.morning_analysis_workflow import MorningAnalysisWorkflow
from application.workflows.realtime_monitor_workflow import RealtimeMonitorWorkflow

workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/workflows')

@workflow_bp.route('/morning-analysis', methods=['POST'])
def run_morning_analysis():
    """执行早盘分析工作流"""
    workflow = MorningAnalysisWorkflow()
    result = workflow.execute()
    return jsonify(result)

@workflow_bp.route('/realtime-monitor', methods=['POST'])
def run_realtime_monitor():
    """执行实时监控工作流"""
    workflow = RealtimeMonitorWorkflow()
    result = workflow.execute()
    return jsonify(result)

@workflow_bp.route('/daily-learning', methods=['POST'])
def run_daily_learning():
    """执行每日学习工作流"""
    # TODO: 实现 DailyLearningWorkflow
    return jsonify({'status': 'not_implemented'})
```

---

### 5. 定时任务调用工作流 API

**修改**: `scripts/morning_analysis.sh`

```bash
#!/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌅 开始早盘分析工作流"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 调用 quantsys-v2 的工作流 API
RESULT=$(curl -s -X POST http://localhost:5001/api/workflows/morning-analysis)

echo "$RESULT" | jq .

# 提取状态
STATUS=$(echo "$RESULT" | jq -r '.status')

if [ "$STATUS" = "success" ]; then
  echo "✅ 工作流执行成功"
else
  echo "❌ 工作流执行失败"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
```

---

## 文件结构

```
quantsys-v2/
├── application/
│   └── workflows/
│       ├── __init__.py
│       ├── base.py                          # 工作流基类
│       ├── morning_analysis_workflow.py     # 早盘分析
│       ├── realtime_monitor_workflow.py     # 实时监控
│       └── daily_learning_workflow.py       # 每日学习
│
└── adapters/
    └── inbound/
        └── api/
            └── routes/
                └── workflow.py              # 工作流 API
```

---

## 优势

1. **集中管理**: 所有工作流逻辑在 quantsys-v2
2. **易于测试**: Python 单元测试
3. **状态管理**: 工作流状态持久化
4. **错误处理**: 统一的错误处理机制
5. **监控**: 可以记录每个步骤的执行时间
6. **扩展性**: 添加新工作流很简单

---

## agent-ts 的角色

agent-ts 不参与工作流编排，只提供工具：

```typescript
// agent-ts 只是提供工具接口
export const opponentBehaviorTool = {
  name: 'opponent_behavior',
  execute: async () => {
    // 调用 quantsys-v2 API
    return await fetch('http://localhost:5001/api/game/market/opponent-behavior')
  }
}
```

agent-ts 在交互式场景使用（用户问问题时），工作流在自动化场景使用（定时任务）。

---

## 下一步

1. 创建工作流基础框架 (2小时)
2. 实现早盘分析工作流 (3小时)
3. 实现其他工作流 (2小时)
4. 注册 Blueprint (10分钟)
5. 修改定时任务脚本 (30分钟)
6. 测试 (1小时)

**总计**: 1-2天
