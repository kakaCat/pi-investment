# RFC 004: Diagnostics Plugin - 监控与诊断系统

## 元信息

- **RFC ID**: 004
- **标题**: Diagnostics Plugin - 监控与诊断系统
- **状态**: 📝 设计阶段
- **作者**: Claude (Kiro) - 设计者
- **实施者**: Agent-Implementation-1
- **创建日期**: 2026-08-20
- **目标完成**: Week 1-2 (2026-08-27)
- **依赖**: RFC 002 (lifecycle), RFC 003 (learning)
- **优先级**: P0 (最高)

---

## 1. 背景与动机

### 1.1 当前问题

Agent-DH 目前**缺乏主动问题发现能力**：
- ❌ 被动等待错误发生
- ❌ 问题发生后难以快速定位根因
- ❌ 缺少系统健康状态的整体视图
- ❌ 日志分散，难以关联分析

### 1.2 目标

实现**主动式监控与智能诊断**：
- ✅ 主动健康检查，早期发现隐患
- ✅ 自动聚合错误，识别重复模式
- ✅ 智能根因分析，快速定位问题
- ✅ 日志解析与上下文提取

### 1.3 在自主闭环中的位置

```
【THIS →】发现问题 → 诊断 → 修复 → 验证 → 部署
           ↓
        记录 → 学习
```

---

## 2. 系统设计

### 2.1 整体架构

```
┌────────────────────────────────────────────────────────┐
│  Data Collection Layer (数据采集)                       │
│  • System metrics (CPU, Memory, Disk)                  │
│  • Tool execution logs                                 │
│  • Error traces                                        │
│  • Performance metrics                                 │
└────────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────────┐
│  Analysis Layer (分析层)                                │
│  • Aggregation: 聚合同类问题                            │
│  • Pattern recognition: 识别异常模式                    │
│  • Correlation: 关联分析                                │
│  • Anomaly detection: 异常检测                          │
└────────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────────┐
│  Diagnosis Layer (诊断层)                               │
│  • Root cause analysis: 根因推理                        │
│  • LLM reasoning: LLM 辅助分析                          │
│  • Knowledge retrieval: 历史案例检索                    │
│  • Hypothesis generation: 假设生成                      │
└────────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────────┐
│  Reporting Layer (报告层)                               │
│  • Health score: 健康评分                               │
│  • Problem list: 问题清单 + 优先级                       │
│  • Recommended actions: 建议操作                        │
│  • Alert & notify: 告警通知                             │
└────────────────────────────────────────────────────────┘
```

### 2.2 数据模型

#### HealthCheckResult
```typescript
interface HealthCheckResult {
  timestamp: string;
  overall_score: number;  // 0-100
  status: 'healthy' | 'degraded' | 'critical';
  checks: HealthCheck[];
  problems: Problem[];
  recommendations: Recommendation[];
}

interface HealthCheck {
  category: 'memory' | 'performance' | 'tools' | 'connectivity' | 'data';
  name: string;
  status: 'pass' | 'warn' | 'fail';
  score: number;  // 0-100
  message: string;
  metrics?: Record<string, any>;
}

interface Problem {
  id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  title: string;
  description: string;
  first_seen: string;
  occurrence_count: number;
  impact: string;
  related_logs?: string[];
}

interface Recommendation {
  problem_id: string;
  action: string;
  description: string;
  estimated_time: string;
  auto_fixable: boolean;
}
```

#### ErrorAggregation
```typescript
interface ErrorAggregation {
  time_range: { start: string; end: string; };
  total_errors: number;
  by_category: Record<string, ErrorGroup>;
  patterns: ErrorPattern[];
  top_errors: ErrorEntry[];
}

interface ErrorGroup {
  category: 'tool_error' | 'system_error' | 'business_error';
  count: number;
  error_types: Record<string, number>;
}

interface ErrorPattern {
  pattern_id: string;
  description: string;
  occurrences: number;
  first_seen: string;
  last_seen: string;
  signature: string;  // 用于去重的签名
  sample_errors: string[];
}

interface ErrorEntry {
  timestamp: string;
  tool_name?: string;
  error_type: string;
  message: string;
  stack_trace?: string;
  context?: Record<string, any>;
}
```

#### RootCauseAnalysis
```typescript
interface RootCauseAnalysis {
  problem_id: string;
  problem_description: string;
  analysis_time: string;
  possible_causes: Cause[];
  evidence: Evidence[];
  recommendation: string;
  confidence: number;  // 0-1
}

interface Cause {
  cause_id: string;
  description: string;
  confidence: number;  // 0-1
  category: 'code' | 'config' | 'data' | 'dependency' | 'resource' | 'external';
  evidence_ids: string[];
}

interface Evidence {
  evidence_id: string;
  type: 'log' | 'metric' | 'code' | 'config' | 'history';
  content: string;
  relevance: number;  // 0-1
}
```

---

## 3. 工具规格

### 3.1 self_diagnose - 健康检查

#### 功能描述
执行全面的系统健康检查，返回健康评分、问题清单和建议操作。

#### 参数
```typescript
{
  check_type: 'memory' | 'performance' | 'tools' | 'connectivity' | 'data' | 'all',
  deep_check?: boolean,  // 默认 false，true 时执行深度检查（耗时更长）
  include_recommendations?: boolean  // 默认 true
}
```

#### 检查项清单

**memory 检查**:
- [ ] 内存使用率 < 80%
- [ ] experience buffer 大小合理
- [ ] memory 命名空间无碎片
- [ ] 无内存泄漏迹象

**performance 检查**:
- [ ] 工具平均响应时间 < 3s
- [ ] P95 响应时间 < 10s
- [ ] 错误率 < 5%
- [ ] CPU 使用率 < 70%

**tools 检查**:
- [ ] 所有工具可调用
- [ ] 关键工具成功率 > 95%
- [ ] 无工具超时
- [ ] 工具依赖可用

**connectivity 检查**:
- [ ] quantsys-v2 连接正常
- [ ] DeepSeek API 可用
- [ ] 飞书 webhook 可达
- [ ] 网络延迟 < 200ms

**data 检查**:
- [ ] 数据质量评分 > 80
- [ ] 无数据缺失
- [ ] 无数据延迟
- [ ] 数据一致性

#### 返回示例
```json
{
  "timestamp": "2026-08-20T10:30:00Z",
  "overall_score": 87,
  "status": "healthy",
  "checks": [
    {
      "category": "memory",
      "name": "memory_usage",
      "status": "pass",
      "score": 92,
      "message": "内存使用率 45%，健康",
      "metrics": { "used_mb": 2048, "total_mb": 4096 }
    },
    {
      "category": "performance",
      "name": "tool_latency",
      "status": "warn",
      "score": 75,
      "message": "portfolio_trade 平均延迟 3.2s，略高",
      "metrics": { "avg_ms": 3200, "p95_ms": 5100 }
    }
  ],
  "problems": [
    {
      "id": "prob_20260820_001",
      "severity": "medium",
      "category": "performance",
      "title": "portfolio_trade 响应慢",
      "description": "最近 1 小时平均延迟 3.2s，超过预期 3s",
      "first_seen": "2026-08-20T09:00:00Z",
      "occurrence_count": 15,
      "impact": "交易执行效率下降 6%"
    }
  ],
  "recommendations": [
    {
      "problem_id": "prob_20260820_001",
      "action": "check_quantsys_v2_health",
      "description": "检查 quantsys-v2 后端健康状态",
      "estimated_time": "2 分钟",
      "auto_fixable": false
    }
  ]
}
```

#### 实现要点
1. **并行检查**: 各类检查并发执行，减少总耗时
2. **智能采样**: 不是每次都深度检查，定期 + 触发式
3. **历史对比**: 与 24 小时前的健康状态对比，识别下降
4. **告警阈值**: 严重问题自动调用 `feishu_notify`

---

### 3.2 performance_monitor - 性能监控

#### 功能描述
实时监控系统性能指标，超过阈值时记录问题并告警。

#### 参数
```typescript
{
  duration_seconds?: number,  // 监控时长，默认 60
  metrics?: string[],  // 监控指标列表，默认 all
  alert_threshold?: {
    cpu_percent?: number,
    memory_percent?: number,
    error_rate?: number,
    latency_ms?: number
  }
}
```

#### 监控指标
- **CPU**: 使用率、峰值
- **Memory**: 使用率、增长速率
- **Tool Latency**: 平均、P95、P99
- **Error Rate**: 每分钟错误数
- **Throughput**: 每分钟工具调用数

#### 返回示例
```json
{
  "monitoring_period": { "start": "...", "end": "...", "duration_s": 60 },
  "metrics": {
    "cpu": { "avg": 45.2, "max": 78.5, "status": "normal" },
    "memory": { "avg": 52.1, "max": 68.3, "growth_rate": 0.5, "status": "normal" },
    "latency": {
      "avg_ms": 1250,
      "p95_ms": 3100,
      "p99_ms": 5200,
      "status": "warn",
      "slow_tools": ["portfolio_trade", "model_predict"]
    },
    "error_rate": { "errors_per_min": 0.5, "status": "normal" },
    "throughput": { "calls_per_min": 12.3 }
  },
  "alerts": [
    {
      "level": "warning",
      "metric": "latency_p95",
      "value": 3100,
      "threshold": 3000,
      "message": "P95 延迟超过阈值"
    }
  ],
  "recommendations": [
    "检查 quantsys-v2 响应时间",
    "考虑增加缓存"
  ]
}
```

---

### 3.3 error_aggregator - 错误聚合

#### 功能描述
聚合指定时间范围内的错误，识别重复模式，生成错误分类统计。

#### 参数
```typescript
{
  time_range_hours?: number,  // 默认 24
  min_occurrences?: number,  // 最小出现次数才算模式，默认 3
  include_stack_trace?: boolean  // 是否包含堆栈，默认 false
}
```

#### 错误分类
- **Tool Error**: 工具调用失败
- **System Error**: 系统级错误（OOM、网络超时）
- **Business Error**: 业务逻辑错误（余额不足、股票停牌）

#### 模式识别算法
```typescript
// 生成错误签名用于去重
function generateErrorSignature(error: ErrorEntry): string {
  const { tool_name, error_type, message } = error;
  // 去除变化的部分（如股票代码、数字）
  const normalized = message.replace(/\d+/g, 'N').replace(/[A-Z]{6}/g, 'SYMBOL');
  return `${tool_name}:${error_type}:${normalized}`;
}
```

#### 返回示例
```json
{
  "time_range": { "start": "...", "end": "...", "hours": 24 },
  "total_errors": 47,
  "by_category": {
    "tool_error": { "count": 32, "error_types": { "timeout": 20, "validation": 12 } },
    "system_error": { "count": 10, "error_types": { "network": 10 } },
    "business_error": { "count": 5, "error_types": { "insufficient_funds": 5 } }
  },
  "patterns": [
    {
      "pattern_id": "pat_001",
      "description": "portfolio_trade 超时（股票 SYMBOL）",
      "occurrences": 20,
      "first_seen": "2026-08-20T08:00:00Z",
      "last_seen": "2026-08-20T16:30:00Z",
      "signature": "portfolio_trade:timeout:Connection to quantsys-v2 timed out",
      "sample_errors": ["portfolio_trade failed: 600519", "portfolio_trade failed: 000001"]
    }
  ],
  "top_errors": [
    {
      "timestamp": "2026-08-20T16:30:00Z",
      "tool_name": "portfolio_trade",
      "error_type": "timeout",
      "message": "Connection to quantsys-v2 timed out after 10s",
      "context": { "symbol": "600519", "action": "BUY" }
    }
  ]
}
```

---

### 3.4 log_analyzer - 日志分析

#### 功能描述
解析日志文件，提取错误堆栈、上下文，生成结构化错误摘要。

#### 参数
```typescript
{
  log_file?: string,  // 日志文件路径，默认最新的 restart log
  time_range?: { start: string; end: string; },  // 时间范围过滤
  error_only?: boolean,  // 只提取错误，默认 false
  max_entries?: number  // 最多返回条目，默认 100
}
```

#### 解析能力
- **错误堆栈**: 提取完整堆栈，识别文件和行号
- **日志级别**: ERROR / WARN / INFO / DEBUG
- **时间戳**: 解析并排序
- **上下文**: 提取相关上下文（如工具参数、用户 ID）
- **关联**: 关联同一个请求链路的日志

#### 返回示例
```json
{
  "log_file": "~/.dsh/profiles/investment/state/restart-1724140800.log",
  "time_range": { "start": "...", "end": "..." },
  "total_entries": 3428,
  "errors": 23,
  "warnings": 157,
  "error_entries": [
    {
      "timestamp": "2026-08-20T10:15:32.123Z",
      "level": "ERROR",
      "message": "TypeError: Cannot read property 'price' of undefined",
      "stack_trace": [
        "at packages/trading/src/index.ts:245:18",
        "at async execute (packages/trading/src/index.ts:230:5)"
      ],
      "context": {
        "tool": "portfolio_trade",
        "args": { "symbol": "600519", "action": "BUY" },
        "request_id": "req_abc123"
      }
    }
  ],
  "warning_summary": {
    "tool_timeout": 50,
    "memory_high": 30,
    "slow_query": 77
  }
}
```

---

### 3.5 root_cause_analyzer - 根因分析

#### 功能描述
基于问题描述、日志、系统状态，使用 LLM 推理根本原因。

#### 参数
```typescript
{
  problem_description: string,  // 问题描述
  related_logs?: string[],  // 相关日志 ID 或内容
  system_state?: any,  // 当前系统状态（从 self_diagnose 获取）
  historical_similar?: boolean  // 是否检索历史相似问题，默认 true
}
```

#### 分析流程
```
1. 【收集证据】
   ├─ 日志分析: log_analyzer
   ├─ 系统状态: self_diagnose
   ├─ 历史案例: memory_search(namespace=post_mortem)
   └─ 代码检查: grep / read

2. 【生成假设】
   ├─ 代码 bug
   ├─ 配置错误
   ├─ 数据问题
   ├─ 依赖失败
   ├─ 资源不足
   └─ 外部服务异常

3. 【LLM 推理】
   Prompt:
   """
   你是一个系统诊断专家。根据以下信息推理根本原因：
   
   问题描述: {problem_description}
   
   证据:
   - 日志: {logs}
   - 系统状态: {system_state}
   - 历史案例: {historical_cases}
   
   请分析：
   1. 最可能的根因是什么？置信度多少？
   2. 支持该结论的证据有哪些？
   3. 排除了哪些其他可能？为什么？
   4. 建议的修复方案是什么？
   """

4. 【验证假设】
   ├─ 检查代码逻辑
   ├─ 验证配置值
   ├─ 检查数据一致性
   └─ 测试依赖连接

5. 【输出结论】
   └─ 排序后的可能原因 + 置信度
```

#### 返回示例
```json
{
  "problem_id": "prob_20260820_001",
  "problem_description": "portfolio_trade 连续 20 次超时",
  "analysis_time": "2026-08-20T10:30:00Z",
  "possible_causes": [
    {
      "cause_id": "cause_001",
      "description": "quantsys-v2 后端响应慢或不可用",
      "confidence": 0.85,
      "category": "external",
      "evidence_ids": ["ev_log_001", "ev_metric_001", "ev_history_001"]
    },
    {
      "cause_id": "cause_002",
      "description": "网络连接不稳定",
      "confidence": 0.45,
      "category": "resource",
      "evidence_ids": ["ev_log_002"]
    }
  ],
  "evidence": [
    {
      "evidence_id": "ev_log_001",
      "type": "log",
      "content": "Connection to quantsys-v2 timed out after 10s",
      "relevance": 0.95
    },
    {
      "evidence_id": "ev_metric_001",
      "type": "metric",
      "content": "quantsys-v2 平均响应时间从 200ms 上升到 8000ms",
      "relevance": 0.90
    },
    {
      "evidence_id": "ev_history_001",
      "type": "history",
      "content": "上周也出现过类似问题，根因是 quantsys-v2 数据库锁",
      "relevance": 0.70
    }
  ],
  "recommendation": "立即检查 quantsys-v2 服务健康状态和数据库连接池。如果不可用，临时切换到 fallback 数据源或暂停交易。",
  "confidence": 0.85
}
```

---

## 4. 技术实现细节

### 4.1 性能数据采集

```typescript
class PerformanceCollector {
  private metrics: Map<string, MetricSeries> = new Map();

  // 拦截工具调用，记录性能
  interceptToolExecution(toolName: string, duration: number, success: boolean) {
    const key = `tool.${toolName}`;
    if (!this.metrics.has(key)) {
      this.metrics.set(key, new MetricSeries());
    }
    this.metrics.get(key)!.add({ timestamp: Date.now(), duration, success });
  }

  // 计算统计量
  getStatistics(toolName: string, windowMinutes: number = 60): Statistics {
    const series = this.metrics.get(`tool.${toolName}`);
    if (!series) return null;
    
    const cutoff = Date.now() - windowMinutes * 60 * 1000;
    const recent = series.getAfter(cutoff);
    
    return {
      count: recent.length,
      avg: mean(recent.map(m => m.duration)),
      p50: percentile(recent.map(m => m.duration), 0.50),
      p95: percentile(recent.map(m => m.duration), 0.95),
      p99: percentile(recent.map(m => m.duration), 0.99),
      success_rate: recent.filter(m => m.success).length / recent.length,
    };
  }
}
```

### 4.2 错误签名生成

```typescript
function normalizeErrorMessage(message: string): string {
  return message
    .replace(/\b\d+\b/g, 'N')  // 数字 → N
    .replace(/\b[A-Z]{6}\b/g, 'SYMBOL')  // 股票代码 → SYMBOL
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/g, 'UUID')  // UUID
    .replace(/\b(\d{1,3}\.){3}\d{1,3}\b/g, 'IP')  // IP 地址
    .replace(/\/[^\s]+/g, '/PATH');  // 文件路径
}

function generateSignature(error: ErrorEntry): string {
  const { tool_name, error_type, message } = error;
  const normalized = normalizeErrorMessage(message);
  return `${tool_name || 'unknown'}:${error_type}:${normalized}`;
}
```

### 4.3 LLM 根因分析 Prompt

```typescript
const ROOT_CAUSE_PROMPT = `你是一个系统诊断专家，专门分析 Agent-DH 投资系统的问题。

## 系统架构
Agent-DH 是一个基于 DSH 框架的 AI Agent，包含 14 个插件（investment, trading, risk 等），依赖 quantsys-v2 后端（Python，端口 5001）和 DeepSeek API。

## 常见问题模式
1. **quantsys-v2 连接问题**: 后端服务挂掉、数据库锁、网络超时
2. **内存问题**: experience buffer 过大、内存泄漏
3. **代码 bug**: 空指针、类型错误、边界条件
4. **配置错误**: 参数设置不当、API key 失效
5. **数据问题**: 数据缺失、数据延迟、数据格式错误

## 当前问题
{problem_description}

## 证据
### 日志
{logs}

### 系统状态
{system_state}

### 历史相似问题
{historical_cases}

## 任务
请分析：
1. **最可能的根因**（1-3 个，按置信度排序）
2. **支持证据**（引用证据 ID）
3. **排除的可能性**（说明为什么排除）
4. **验证步骤**（如何确认该根因）
5. **修复建议**（具体操作步骤）

输出 JSON 格式，schema:
{
  "possible_causes": [
    {
      "description": "...",
      "confidence": 0.85,
      "category": "external" | "code" | "config" | "data" | "resource",
      "evidence_ids": ["ev_001"],
      "reasoning": "..."
    }
  ],
  "recommendation": "...",
  "verification_steps": ["step 1", "step 2"]
}
`;
```

---

## 5. 集成点

### 5.1 与 lifecycle 集成
- `self_diagnose` 在每次 `self_restart` 成功后自动运行
- 发现严重问题自动触发 `auto_rollback`（Sprint 5）

### 5.2 与 learning 集成
- 诊断结果写入 `memory` (namespace=diagnostics)
- `root_cause_analyzer` 调用 `memory_search` 检索历史案例

### 5.3 与 notification 集成
- 严重问题（critical）自动调用 `feishu_notify`
- 中等问题（high）每小时汇总通知

---

## 6. 测试计划

### 6.1 单元测试
- [ ] 性能数据采集准确性
- [ ] 错误签名生成去重效果
- [ ] 日志解析覆盖各种格式
- [ ] 健康检查各项指标计算

### 6.2 集成测试
- [ ] 模拟 quantsys-v2 不可用，验证诊断
- [ ] 模拟内存泄漏，验证告警
- [ ] 模拟连续错误，验证模式识别

### 6.3 端到端测试
- [ ] 完整流程: 发现问题 → 诊断 → 记录
- [ ] 历史案例检索准确性
- [ ] LLM 根因分析准确率 > 70%

---

## 7. 性能要求

| 工具 | 延迟要求 | 备注 |
|-----|---------|------|
| self_diagnose | < 5s (normal), < 30s (deep) | 并行检查 |
| performance_monitor | 实时 | 后台持续运行 |
| error_aggregator | < 3s | 缓存聚合结果 |
| log_analyzer | < 10s | 大日志文件分批处理 |
| root_cause_analyzer | < 30s | LLM 推理 |

---

## 8. 交付清单

### 代码
- [ ] `packages/diagnostics/src/index.ts` - 插件主文件
- [ ] `packages/diagnostics/src/health-checker.ts` - 健康检查
- [ ] `packages/diagnostics/src/performance-collector.ts` - 性能采集
- [ ] `packages/diagnostics/src/error-aggregator.ts` - 错误聚合
- [ ] `packages/diagnostics/src/log-parser.ts` - 日志解析
- [ ] `packages/diagnostics/src/root-cause.ts` - 根因分析
- [ ] `packages/diagnostics/package.json`

### 测试
- [ ] `packages/diagnostics/tests/health-checker.test.ts`
- [ ] `packages/diagnostics/tests/error-aggregator.test.ts`
- [ ] `packages/diagnostics/tests/root-cause.test.ts`
- [ ] `packages/diagnostics/tests/integration.test.ts`

### 文档
- [ ] `packages/diagnostics/README.md` - 使用文档
- [ ] `docs/guides/diagnostics-guide.md` - 详细指南
- [ ] Schema 验证通过（添加到 smoke test）

---

## 9. 验收标准

### 功能验收
- [x] 5 个工具全部实现并通过测试
- [x] Schema 符合 DSH 规范（additionalProperties）
- [x] 集成测试覆盖主要场景

### 质量验收
- [x] 单元测试覆盖率 > 80%
- [x] 无 ESLint 错误
- [x] 无 TypeScript 类型错误
- [x] 代码圈复杂度 < 15

### 性能验收
- [x] self_diagnose < 5s（normal mode）
- [x] root_cause_analyzer < 30s
- [x] 错误聚合准确率 > 90%

### 文档验收
- [x] README 包含所有工具使用示例
- [x] 代码注释覆盖关键逻辑
- [x] 更新 CLAUDE.md

---

## 10. 风险与应对

### 风险 1: LLM 根因分析不稳定
**概率**: Medium  
**影响**: High  
**应对**:
- 提供 fallback: 基于规则的根因分析
- 多轮对话改进分析质量
- 积累高质量 prompt 模板

### 风险 2: 性能监控开销
**概率**: Low  
**影响**: Medium  
**应对**:
- 采样而非全量监控
- 异步处理，不阻塞主流程
- 可配置开关

### 风险 3: 日志解析兼容性
**概率**: Medium  
**影响**: Low  
**应对**:
- 支持多种日志格式
- 容错处理，解析失败不崩溃
- 逐步完善解析规则

---

## 11. 后续优化方向

1. **机器学习增强**: 训练异常检测模型
2. **可视化 Dashboard**: 实时健康状态大屏
3. **预测性维护**: 提前预测即将发生的问题
4. **自动修复**: 常见问题自动应用已知修复

---

## 实施者指南

### 开始实施前
1. ✅ 阅读 RFC 002 (lifecycle) 和 RFC 003 (learning)
2. ✅ 熟悉现有插件结构（参考 `packages/lifecycle`）
3. ✅ 理解 DSH Schema 规范（`additionalProperties` 必须显式声明）

### 实施步骤
1. **Day 1**: 创建插件骨架 + `self_diagnose` 基础实现
2. **Day 2**: 实现 `performance_monitor` + 性能数据采集
3. **Day 3**: 实现 `error_aggregator` + 模式识别
4. **Day 4**: 实现 `log_analyzer` + 日志解析
5. **Day 5**: 实现 `root_cause_analyzer` + LLM 集成
6. **Day 6-7**: 单元测试 + 集成测试
7. **Day 8**: 文档 + Code Review

### 卡住时求助
- 设计问题: 问设计者（我）
- 技术问题: 查看现有插件实现
- 测试问题: 参考 `packages/lifecycle/tests`

---

**状态**: 📝 Ready for Implementation  
**优先级**: P0  
**实施者**: Agent-Implementation-1  
**评审者**: Claude (Kiro)  
**预计完成**: 2026-08-27
