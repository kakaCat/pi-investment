# 企业级工作流方案建议

## 当前问题

Shell 脚本工作流存在的问题：
1. **难以维护**: 逻辑分散在多个脚本
2. **测试困难**: 无法单元测试
3. **调试不便**: 错误追踪困难
4. **扩展性差**: 添加新功能需要修改多个地方

---

## 推荐方案

### 方案 1: Airflow（推荐用于企业级）

**优点**:
- 完整的工作流调度框架
- 可视化 DAG
- 任务依赖管理
- 失败重试
- 监控告警
- 企业级成熟方案

**实现**:
```python
# dags/morning_analysis.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def analyze_opponents():
    # 调用 API 或工具
    pass

def check_alerts():
    pass

def evaluate_pools():
    pass

with DAG('morning_analysis', 
         schedule_interval='0 9 * * 1-5',
         start_date=datetime(2026, 6, 26)) as dag:
    
    task1 = PythonOperator(task_id='analyze_opponents', 
                          python_callable=analyze_opponents)
    task2 = PythonOperator(task_id='check_alerts',
                          python_callable=check_alerts)
    task3 = PythonOperator(task_id='evaluate_pools',
                          python_callable=evaluate_pools)
    
    task1 >> task2 >> task3
```

---

### 方案 2: Temporal（推荐用于复杂流程）

**优点**:
- 微服务工作流编排
- 长期运行任务
- 状态持久化
- 容错能力强
- 代码即流程

**实现**:
```typescript
// workflows/morning-analysis.ts
import { proxyActivities } from '@temporalio/workflow'

const activities = proxyActivities({
  startToCloseTimeout: '5 minutes'
})

export async function morningAnalysisWorkflow() {
  const opponents = await activities.analyzeOpponents()
  const alerts = await activities.checkAlerts()
  const pools = await activities.evaluatePools(opponents, alerts)
  await activities.sendReport(pools)
}
```

---

### 方案 3: Prefect（Python 原生）

**优点**:
- Python 原生，简单易用
- 动态工作流
- 现代化 UI
- 轻量级

**实现**:
```python
from prefect import flow, task

@task
def analyze_opponents():
    # ...
    return opponents

@task
def check_alerts():
    # ...
    return alerts

@task
def evaluate_pools(opponents, alerts):
    # ...
    return decisions

@flow
def morning_analysis():
    opponents = analyze_opponents()
    alerts = check_alerts()
    decisions = evaluate_pools(opponents, alerts)
    return decisions
```

---

### 方案 4: agent-ts 内置工作流引擎（最简单）

**优点**:
- 集成在 agent 系统内
- TypeScript 类型安全
- 无需额外部署
- 维护简单

**实现**:
```typescript
// agent-ts/src/workflows/workflow-engine.ts

export class WorkflowEngine {
  async execute(workflow: Workflow) {
    try {
      for (const step of workflow.steps) {
        const result = await this.executeStep(step)
        step.result = result
        await this.saveState(workflow)
      }
    } catch (error) {
      await this.handleError(workflow, error)
    }
  }
}

// 工作流定义
const morningAnalysis = {
  name: 'morning_analysis',
  steps: [
    { name: 'analyze_opponents', tool: opponentBehaviorTool },
    { name: 'check_alerts', tool: gameAlertTool },
    { name: 'evaluate_pools', tool: poolEvaluationTool }
  ]
}
```

---

## 对比分析

| 方案 | 复杂度 | 维护性 | 企业级 | 适用场景 |
|------|--------|--------|--------|----------|
| Shell脚本 | 低 | 差 | ❌ | 原型验证 |
| agent-ts内置 | 中 | 中 | ⚠️ | 小型系统 |
| Prefect | 中 | 好 | ✅ | Python团队 |
| Temporal | 高 | 好 | ✅ | 复杂流程 |
| Airflow | 中 | 好 | ✅ | 批处理任务 |

---

## 推荐决策

### 短期（现在）
使用 **agent-ts 内置工作流引擎**：
- 简单、集成度高
- 无需额外部署
- 快速实现

### 中期（3-6个月）
迁移到 **Prefect** 或 **Airflow**：
- 系统成熟后需要更好的监控
- 团队扩大需要更好的协作
- 需要可视化工作流

### 长期（1年+）
考虑 **Temporal**：
- 业务复杂度增加
- 需要跨服务编排
- 需要长期运行的任务

---

## 实施建议

### Phase 1: agent-ts 内置工作流引擎

**时间**: 1-2天

**实现**:
1. 创建 WorkflowEngine 类
2. 定义工作流 DSL
3. 集成现有工具
4. 添加日志和错误处理

**优势**:
- 快速上线
- 代码统一
- 易于调试

---

### Phase 2: 迁移到企业级框架

**时间**: 1-2周

**步骤**:
1. 评估 Airflow vs Prefect
2. 搭建基础设施
3. 迁移现有工作流
4. 添加监控告警

---

## 下一步

建议：
1. 先用 crontab + agent-ts 工作流引擎快速实现
2. 积累经验后评估企业级框架
3. 根据团队规模和复杂度选择最终方案

**核心原则**: 先让系统跑起来，再优化架构
