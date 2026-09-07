"""
Business Metrics for Prometheus

定义所有业务指标：进化引擎、调度器、Agent、数据源
"""
from prometheus_client import Counter, Histogram, Gauge

# ==================== 进化引擎指标 ====================

# 决策打分完成数量
evolution_decision_scored_total = Counter(
    'evolution_decision_scored_total',
    'Total number of decisions scored',
    ['account']
)

# 决策打分耗时
evolution_decision_score_duration_seconds = Histogram(
    'evolution_decision_score_duration_seconds',
    'Time spent scoring decisions',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# 踏空捕获数量
evolution_missed_opportunities_total = Counter(
    'evolution_missed_opportunities_total',
    'Total number of missed opportunities captured',
    ['days']
)

# 适应度计算完成
evolution_fitness_computed_total = Counter(
    'evolution_fitness_computed_total',
    'Total number of fitness computations',
    ['account']
)

# 适应度得分
evolution_fitness_score = Gauge(
    'evolution_fitness_score',
    'Current fitness score',
    ['account', 'type']
)

# 进化引擎错误
evolution_errors_total = Counter(
    'evolution_errors_total',
    'Total number of evolution engine errors',
    ['service', 'error_type']
)

# ==================== 调度器指标 ====================

# 调度任务执行次数
scheduler_job_runs_total = Counter(
    'scheduler_job_runs_total',
    'Total number of job runs',
    ['job', 'status']
)

# 调度任务耗时
scheduler_job_duration_seconds = Histogram(
    'scheduler_job_duration_seconds',
    'Job execution duration in seconds',
    ['job', 'phase'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

# 调度器状态
scheduler_orchestrator_phase = Gauge(
    'scheduler_orchestrator_phase',
    'Current orchestrator phase',
    ['state']
)

# 错过的任务
scheduler_misfires_total = Counter(
    'scheduler_misfires_total',
    'Total number of misfired jobs',
    ['job']
)

# ==================== Agent 指标 ====================

# Agent 决策数量
agent_decisions_total = Counter(
    'agent_decisions_total',
    'Total number of agent decisions',
    ['agent_id', 'action']
)

# Agent 会话时长
agent_session_duration_seconds = Histogram(
    'agent_session_duration_seconds',
    'Agent session duration in seconds',
    ['session_type'],
    buckets=[60.0, 300.0, 600.0, 1800.0, 3600.0]
)

# Agent 工具调用
agent_tool_calls_total = Counter(
    'agent_tool_calls_total',
    'Total number of agent tool calls',
    ['tool']
)

# Agent 错误
agent_errors_total = Counter(
    'agent_errors_total',
    'Total number of agent errors',
    ['error_type']
)


# ==================== 辅助函数 ====================

def record_evolution_scored(account: str, count: int = 1):
    """记录决策打分完成"""
    evolution_decision_scored_total.labels(account=account).inc(count)


def record_evolution_fitness(account: str, fitness_type: str, score: float):
    """记录适应度得分"""
    evolution_fitness_score.labels(account=account, type=fitness_type).set(score)


def record_scheduler_job_run(job: str, status: str):
    """记录调度任务执行"""
    scheduler_job_runs_total.labels(job=job, status=status).inc()


def record_scheduler_job_duration(job: str, phase: str, duration: float):
    """记录调度任务耗时"""
    scheduler_job_duration_seconds.labels(job=job, phase=phase).observe(duration)


def record_agent_decision(agent_id: str, action: str):
    """记录 Agent 决策"""
    agent_decisions_total.labels(agent_id=agent_id, action=action).inc()


def record_agent_tool_call(tool: str):
    """记录 Agent 工具调用"""
    agent_tool_calls_total.labels(tool=tool).inc()
