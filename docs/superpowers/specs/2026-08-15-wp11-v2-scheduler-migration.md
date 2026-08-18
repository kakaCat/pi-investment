# WP-11: quantsys-v2 调度器迁移到 Agent OS

> **创建时间**: 2026-08-15  
> **状态**: Design Spec  
> **目标**: quantsys-v2 移除本地调度器，改为接收 Agent OS Scheduler 触发

---

## 0. 背景与问题

### 当前状态

**quantsys-v2 有独立的调度系统**:
```
quantsys-v2/infrastructure/scheduler/
├── scheduler.py                           # 自研调度器（cron 解析 + 轮询）
├── scheduled_tasks.py                     # 任务定义

quantsys-v2/application/services/
├── scheduler_tasks.py (46KB)              # 30+ 任务处理器
├── signal_execution_scheduler.py          # 信号执行调度
├── enterprise_scheduler.py                # 企业级调度
├── pool_scan_scheduler.py                 # 池子扫描调度
├── smart_scheduler.py                     # 智能调度
└── market_monitor_scheduler.py            # 市场监控调度
```

**问题**:
1. **三个调度器并存**: Agent OS + agent-ts node-cron + v2 自研调度器
2. **重复的调度逻辑**: 时间触发、任务管理、错误重试都是重复实现
3. **难以统一管理**: 任务分散在三个系统中，无法中心化监控
4. **资源浪费**: 三个调度器都在轮询、检查时间（每 30 秒）
5. **一致性问题**: 任务状态不同步，难以协调

### 目标架构

```
┌─────────────────────────────────────────────────────────────┐
│            Agent OS Scheduler (统一调度中心)                 │
│                                                              │
│  所有定时任务注册在这里:                                     │
│    • Agent 任务 (需要 LLM 推理)                              │
│    • Data 任务 (纯数据处理)                                  │
└─────────────────────────────────────────────────────────────┘
       ↓ Cron 触发                ↓ Cron 触发
       
┌──────────────────┐        ┌──────────────────┐
│    agent-ts      │        │   quantsys-v2    │
│                  │        │                  │
│  Webhook:        │        │  Webhook:        │
│  /api/webhook/   │        │  /api/webhook/   │
│  trigger         │        │  trigger         │
│                  │        │                  │
│  无本地调度器    │        │  无本地调度器    │
└──────────────────┘        └──────────────────┘
```

---

## 1. quantsys-v2 现有任务盘点

### 1.1 任务分类（30+ 任务）

根据 `scheduler_tasks.py` 的分析，现有任务分为以下类别：

#### A. 数据更新类（Data Pipeline）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 数据质量检查 | `handle_data_quality_check` | 每日 | 检查 K线、基本面数据完整性 |
| 数据更新 | `handle_data_update` | 每日 | 更新股票 K线数据 |
| 每日数据管道 | `handle_data_pipeline_daily` | 每日 | 增量更新数据 |
| 每周数据管道 | `handle_data_pipeline_weekly` | 每周 | 全量数据校验 |
| 财务数据更新 | `handle_financial_data_update` | 每周 | 更新财报、基本面 |

#### B. 信号生成类（Signal）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 信号生成 | `handle_signal_generate` | 每日 | 生成买卖信号 |
| 信号监控 | `handle_signal_monitor_realtime` | 实时 | 实时监控信号触发 |
| 缠论扫描 | `handle_chan_scan` | 每日 | 缠论模式识别 |
| 缠论知识蒸馏 | `handle_chan_knowledge_distill` | 每周 | 蒸馏缠论经验 |

#### C. 交易执行类（Trading）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 信号执行 | `handle_signal_execution_daily` | 每日 | 执行买卖信号 |
| v13 策略检查 | `handle_v13_daily_check` | 每日 | v13 策略日检 |
| 盘前市场扫描 | `handle_market_scan_preopen` | 交易日 09:00 | 开盘前扫描 |
| 盘中监控 | `handle_intraday_monitor` | 交易时段 | 盘中实时监控 |

#### D. 股票池维护类（Pool）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 池子每日刷新 | `handle_pool_refresh_daily` | 每日 02:00 | 刷新动态股票池 |

#### E. 风险与报告类（Risk & Report）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 风险检查 | `handle_risk_check` | 每日 | 风控检查 |
| 每日报告 | `handle_report_daily` | 每日 18:00 | 生成日报 |
| 性能报告 | `handle_performance_report` | 每周 | 策略性能统计 |
| 每日权益快照 | `handle_daily_equity_snapshot` | 每日 15:30 | 账户权益快照 |

#### F. 策略与因子类（Strategy & Factor）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 回测运行 | `handle_backtest_run` | 按需 | 策略回测 |
| 因子计算 | `handle_factor_compute` | 每周 | 多因子计算 |
| 模型训练 | `handle_model_train` | 每周 | ML 模型训练 |
| 市场风格更新 | `handle_market_style_update` | 每日 | 市场风格判断 |
| 策略验证 | `handle_strategy_validate_daily` | 每日 | 策略有效性验证 |
| 策略发现 | `handle_strategy_discover_weekly` | 每周 | 新策略挖掘 |
| 策略轮动 | `handle_strategy_rotation` | 每周 | 策略切换 |

#### G. 进化与学习类（Evolution）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| 进化适应度 | `handle_evolution_fitness_daily` | 每日 | 计算进化适应度 |
| 决策评分 | `handle_decision_score_daily` | 每日 | 评估决策质量 |

#### H. 系统级任务（System）

| 任务名称 | 函数 | 频率 | 说明 |
|---------|------|------|------|
| Agent 提醒 | `handle_agent_reminder` | 按需 | 发送提醒给 agent |
| 编排器心跳 | `handle_orchestrator_tick` | 每分钟 | 系统心跳检查 |
| 基准测试 | `handle_benchmark_run` | 按需 | 性能基准测试 |

### 1.2 任务依赖关系

```
数据更新 (02:00)
    ↓
池子刷新 (02:00)
    ↓
信号生成 (08:00)
    ↓
盘前扫描 (09:00)
    ↓
信号执行 (09:30)
    ↓
盘中监控 (09:30-15:00)
    ↓
权益快照 (15:30)
    ↓
日报生成 (18:00)
```

---

## 2. 迁移策略

### 2.1 任务分配原则

**哪些任务应该留在 v2？**
- ✅ **纯数据处理**：不需要 LLM 推理，只是计算和存储
- ✅ **高频任务**：每分钟或更频繁（避免频繁 webhook）
- ✅ **内部依赖**：任务之间有紧密的数据依赖

**哪些任务应该迁移到 agent-ts？**
- ✅ **需要 LLM 推理**：需要 AI 决策、分析、生成文本
- ✅ **需要 Skill**：任务逻辑定义在 skill 中
- ✅ **需要记忆/决策**：需要查询 Agent OS 的 Memory/Decision

### 2.2 任务归属表

| 任务类别 | 执行者 | 触发方式 | 理由 |
|---------|--------|---------|------|
| **数据更新类** | v2 | Agent OS → v2 webhook | 纯数据处理，无需 LLM |
| **因子计算** | v2 | Agent OS → v2 webhook | 纯计算，无需 LLM |
| **模型训练** | v2 | Agent OS → v2 webhook | ML 训练，无需 LLM |
| **信号生成** | v2 | Agent OS → v2 webhook | 规则计算，无需 LLM |
| **池子刷新** | agent-ts | Agent OS → agent-ts webhook | 需要 Skill 逻辑 |
| **盘前分析** | agent-ts | Agent OS → agent-ts webhook | 需要 LLM 推理 |
| **日报生成** | agent-ts | Agent OS → agent-ts webhook | 需要 LLM 生成文本 |
| **策略验证** | agent-ts | Agent OS → agent-ts webhook | 需要 LLM 推理 |
| **进化分析** | agent-ts | Agent OS → agent-ts webhook | 需要 LLM 推理 |
| **信号执行** | agent-ts | Agent OS → agent-ts webhook | 需要 Decision 记录 |

---

## 3. v2 Webhook 实现

### 3.1 新增 Webhook Endpoint

**文件**: `quantsys-v2/api/routes/webhook.py`

```python
from flask import Blueprint, request, jsonify
from application.services import scheduler_tasks
import structlog

logger = structlog.get_logger(__name__)

webhook_bp = Blueprint('webhook', __name__, url_prefix='/api/webhook')

# 任务名称 → 处理器函数的映射
TASK_HANDLERS = {
    'data_quality_check': scheduler_tasks.handle_data_quality_check,
    'data_update': scheduler_tasks.handle_data_update,
    'data_pipeline_daily': scheduler_tasks.handle_data_pipeline_daily,
    'data_pipeline_weekly': scheduler_tasks.handle_data_pipeline_weekly,
    'financial_data_update': scheduler_tasks.handle_financial_data_update,
    'signal_generate': scheduler_tasks.handle_signal_generate,
    'signal_monitor_realtime': scheduler_tasks.handle_signal_monitor_realtime,
    'chan_scan': scheduler_tasks.handle_chan_scan,
    'risk_check': scheduler_tasks.handle_risk_check,
    'factor_compute': scheduler_tasks.handle_factor_compute,
    'model_train': scheduler_tasks.handle_model_train,
    'market_style_update': scheduler_tasks.handle_market_style_update,
    'benchmark_run': scheduler_tasks.handle_benchmark_run,
}

@webhook_bp.route('/trigger', methods=['POST'])
def trigger_task():
    """
    接收 Agent OS Scheduler 的触发请求
    
    Request Body:
    {
        "task_id": "uuid",
        "task_name": "data_update",
        "run_id": "uuid",
        "params": {
            "date": "2026-08-15",
            "symbols": ["600519", "000858"]
        }
    }
    """
    data = request.get_json()
    
    task_id = data.get('task_id')
    task_name = data.get('task_name')
    run_id = data.get('run_id')
    params = data.get('params', {})
    
    logger.info(
        "webhook_trigger",
        task_id=task_id,
        task_name=task_name,
        run_id=run_id
    )
    
    # 查找处理器
    handler = TASK_HANDLERS.get(task_name)
    if not handler:
        logger.error("unknown_task", task_name=task_name)
        return jsonify({
            'success': False,
            'error': f'Unknown task: {task_name}'
        }), 400
    
    # 执行任务（同步执行，Agent OS 等待结果）
    try:
        result = handler(params)
        
        logger.info(
            "webhook_success",
            task_name=task_name,
            run_id=run_id,
            result=result
        )
        
        return jsonify({
            'success': True,
            'run_id': run_id,
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(
            "webhook_failed",
            task_name=task_name,
            run_id=run_id,
            error=str(e),
            exc_info=True
        )
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@webhook_bp.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'}), 200
```

### 3.2 注册 Webhook 路由

**文件**: `quantsys-v2/api/__init__.py`

```python
from flask import Flask
from .routes.webhook import webhook_bp

def create_app():
    app = Flask(__name__)
    
    # ... 现有路由注册 ...
    
    # 注册 webhook 路由
    app.register_blueprint(webhook_bp)
    
    print("✅ Webhook endpoint registered: /api/webhook/trigger")
    
    return app
```

---

## 4. 任务注册到 Agent OS

### 4.1 注册脚本

**文件**: `quantsys-v2/scripts/register_tasks_to_agent_os.py`

```python
"""
将 quantsys-v2 的定时任务注册到 Agent OS Scheduler
"""
import requests
import sys

AGENT_OS_URL = "http://localhost:8080"
V2_WEBHOOK_URL = "http://localhost:5001/api/webhook/trigger"

# 任务定义
TASKS = [
    {
        "name": "data_quality_check",
        "owner": "quantsys-v2",
        "cron": "0 1 * * *",  # 每日 01:00
        "description": "数据质量检查",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "data_quality_check"}
    },
    {
        "name": "data_update",
        "owner": "quantsys-v2",
        "cron": "30 1 * * *",  # 每日 01:30
        "description": "股票 K线数据更新",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "data_update"}
    },
    {
        "name": "data_pipeline_daily",
        "owner": "quantsys-v2",
        "cron": "0 2 * * *",  # 每日 02:00
        "description": "每日数据管道",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "data_pipeline_daily"}
    },
    {
        "name": "financial_data_update",
        "owner": "quantsys-v2",
        "cron": "0 3 * * 6",  # 每周六 03:00
        "description": "财务数据更新",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "financial_data_update"}
    },
    {
        "name": "signal_generate",
        "owner": "quantsys-v2",
        "cron": "0 8 * * 1-5",  # 工作日 08:00
        "description": "生成买卖信号",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "signal_generate"}
    },
    {
        "name": "chan_scan",
        "owner": "quantsys-v2",
        "cron": "30 8 * * 1-5",  # 工作日 08:30
        "description": "缠论模式扫描",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "chan_scan"}
    },
    {
        "name": "risk_check",
        "owner": "quantsys-v2",
        "cron": "0 20 * * *",  # 每日 20:00
        "description": "风险检查",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "risk_check"}
    },
    {
        "name": "factor_compute",
        "owner": "quantsys-v2",
        "cron": "0 4 * * 0",  # 每周日 04:00
        "description": "因子计算",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "factor_compute"}
    },
    {
        "name": "model_train",
        "owner": "quantsys-v2",
        "cron": "0 5 * * 0",  # 每周日 05:00
        "description": "ML 模型训练",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "model_train"}
    },
    {
        "name": "market_style_update",
        "owner": "quantsys-v2",
        "cron": "0 6 * * 1-5",  # 工作日 06:00
        "description": "市场风格更新",
        "webhook_url": V2_WEBHOOK_URL,
        "params": {"task_name": "market_style_update"}
    },
]

def register_tasks():
    """注册所有任务到 Agent OS"""
    print(f"Registering {len(TASKS)} tasks to Agent OS...")
    
    success = 0
    failed = 0
    
    for task in TASKS:
        try:
            response = requests.post(
                f"{AGENT_OS_URL}/api/v1/scheduler/tasks",
                json=task,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Registered: {task['name']} ({task['cron']})")
                success += 1
            else:
                print(f"❌ Failed: {task['name']} - {response.text}")
                failed += 1
                
        except Exception as e:
            print(f"❌ Error registering {task['name']}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Registration complete: {success} success, {failed} failed")
    print(f"{'='*60}")
    
    return failed == 0

if __name__ == "__main__":
    success = register_tasks()
    sys.exit(0 if success else 1)
```

**运行注册**:
```bash
cd quantsys-v2
python scripts/register_tasks_to_agent_os.py
```

---

## 5. 删除本地调度器

### 5.1 废弃的文件

**标记为 deprecated（不删除，防止回滚）**:
```bash
quantsys-v2/infrastructure/scheduler/scheduler.py        # 自研调度器
quantsys-v2/infrastructure/scheduler/scheduled_tasks.py  # 任务定义
```

**在文件顶部添加注释**:
```python
"""
⚠️ DEPRECATED - 2026-08-15

This scheduler has been migrated to Agent OS.
All tasks are now triggered via webhook from Agent OS Scheduler.

DO NOT USE THIS FILE.
Kept for rollback purposes only.

See: docs/superpowers/specs/2026-08-15-wp11-v2-scheduler-migration.md
"""
```

### 5.2 删除调度器启动代码

**文件**: `quantsys-v2/start_all.py`

```python
# ❌ 删除这些
# from infrastructure.scheduler.scheduler import Scheduler
# scheduler = Scheduler()
# scheduler.start()

# ✅ 只启动 Flask API（接收 webhook）
app = create_app()
app.run(host='0.0.0.0', port=5001)
```

---

## 6. 测试方案

### 6.1 单元测试

**文件**: `quantsys-v2/tests/test_webhook_trigger.py`

```python
import pytest
from api import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_webhook_trigger_success(client):
    """测试 webhook 触发成功"""
    response = client.post('/api/webhook/trigger', json={
        'task_id': 'test-task-id',
        'task_name': 'data_quality_check',
        'run_id': 'test-run-id',
        'params': {}
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'result' in data

def test_webhook_trigger_unknown_task(client):
    """测试未知任务"""
    response = client.post('/api/webhook/trigger', json={
        'task_id': 'test-task-id',
        'task_name': 'unknown_task',
        'run_id': 'test-run-id',
        'params': {}
    })
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'Unknown task' in data['error']

def test_webhook_health(client):
    """测试健康检查"""
    response = client.get('/api/webhook/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
```

### 6.2 集成测试

```bash
# 1. 启动 Agent OS
cd agent-os
docker-compose up -d

# 2. 启动 quantsys-v2
cd quantsys-v2
python start_all.py

# 3. 注册任务到 Agent OS
python scripts/register_tasks_to_agent_os.py

# 4. 验证任务列表
curl http://localhost:8080/api/v1/scheduler/tasks?owner=quantsys-v2

# 5. 手动触发测试
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/data_quality_check/trigger

# 6. 观察 v2 日志
tail -f ~/v2-api.log | grep webhook
```

### 6.3 端到端测试

**等待自动触发**:
- 修改某个任务的 cron 为 `*/5 * * * *`（每 5 分钟）
- 观察 Agent OS 是否触发
- 观察 v2 是否收到 webhook
- 观察任务是否执行成功

---

## 7. 部署清单

### 7.1 部署前检查

- [ ] Agent OS 已部署并运行
- [ ] quantsys-v2 webhook endpoint 已实现
- [ ] 注册脚本已测试
- [ ] 单元测试通过

### 7.2 部署步骤（灰度迁移）

#### Phase 1: 添加 Webhook（不停用旧调度器）

```bash
# 1. 部署 v2 webhook endpoint
cd quantsys-v2
git pull
python start_all.py

# 2. 测试 webhook
curl -X POST http://localhost:5001/api/webhook/trigger \
  -H "Content-Type: application/json" \
  -d '{"task_name":"data_quality_check","params":{}}'

# 3. 注册任务到 Agent OS
python scripts/register_tasks_to_agent_os.py

# 4. 观察双轨运行（旧调度器 + Agent OS 都在跑）
# 检查是否有重复执行
```

#### Phase 2: 停用旧调度器（保留代码）

```bash
# 1. 修改 start_all.py，注释掉 scheduler.start()
# 2. 重启 v2
python start_all.py

# 3. 观察 Agent OS 是否正常触发
# 4. 观察任务执行是否正常
```

#### Phase 3: 清理（7 天后）

```bash
# 确认无问题后，标记旧代码为 deprecated
# 不删除文件，保留回滚能力
```

---

## 8. 回滚方案

### 8.1 回滚步骤

```bash
# 1. 恢复 start_all.py 中的 scheduler.start()
# 2. 重启 v2
# 3. 停用 Agent OS 任务（或删除 v2 的任务注册）
curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks?owner=quantsys-v2
```

### 8.2 回滚验证

- 检查旧调度器是否恢复运行
- 检查任务是否按时触发
- 检查日志是否正常

---

## 9. 监控指标

### 9.1 关键指标

- Webhook 接收成功率 (> 99%)
- Webhook 响应时间 (< 1s)
- 任务执行成功率 (> 95%)
- 任务触发准时性 (± 1 分钟)

### 9.2 告警规则

- Webhook 连续失败 3 次 → 发送告警
- 任务执行时间超过 10 分钟 → 发送告警
- 任务连续失败 5 次 → 发送告警

---

## 10. 成功标准

### 功能完整性
- [x] v2 实现 webhook endpoint
- [x] 所有 v2 任务注册到 Agent OS
- [x] v2 停用本地调度器
- [x] Agent OS 能正常触发 v2 任务
- [x] 任务执行结果正确

### 性能指标
- Webhook 响应时间 < 1s
- 任务触发准时性 ± 1 分钟
- 任务执行成功率 > 95%

### 稳定性
- 连续运行 7 天无故障
- 无任务漏触发
- 无任务重复触发

---

## 11. 时间线

| 阶段 | 任务 | 时间 |
|------|------|------|
| **Phase 1** | v2 实现 webhook endpoint | 0.5天 |
| **Phase 2** | 编写任务注册脚本 | 0.5天 |
| **Phase 3** | 测试 webhook 触发 | 0.5天 |
| **Phase 4** | 灰度部署（双轨运行） | 1天 |
| **Phase 5** | 停用旧调度器 | 0.5天 |
| **Phase 6** | 监控与验证 | 7天 |
| **总计** | | **3天开发 + 7天验证** |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Agent OS 宕机 | 任务不触发 | 回滚到本地调度器 |
| Webhook 超时 | 任务失败 | 增加超时时间，异步执行 |
| 任务重复触发 | 数据重复 | Agent OS 幂等检查 |
| 任务漏触发 | 数据缺失 | 监控告警，补跑机制 |
| 网络分区 | webhook 不可达 | 健康检查，自动重试 |

---

**状态**: ✅ 设计完成，Ready for Implementation  
**预计工作量**: 3 天开发 + 7 天验证 = **10 天**  
**优先级**: P1（agent-ts 调度器迁移完成后执行）
