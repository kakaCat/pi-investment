# 因子数据停更问题根本性修复方案

**发现时间**: 2026-08-28 00:23  
**发现人**: w-5b8aac2a (investor)  
**影响**: 因子数据停在 8-20/8-21，6 天未更新，影响 model_predict/factor_calculate/策略信号的技术面维度

## 问题根因

**症状**: 34 个因子中 7 个过期（adx/cci/ma60/mfi14/momentum_52w_high/momentum_6m/volatility_20），全部因子最新数据停在 8-20/8-21

**根因**: 因子计算管道失效
- Agent OS 有 `factor_compute_daily` 定时任务（08:00 工作日），enabled=true
- 任务触发但执行失败（或静默失败未写执行记录）
- **无失败重试机制**、**无主动告警**、**工具层无 freshness 校验** → 6 天后才通过人工巡检发现

**风险**: model_predict/factor_calculate 等工具拿到陈旧数据也不报错 → **静默毒化选股质量**

## 三层根本解决方案

### 第一层：管道自动化 + 失败重试 ⚠️ 待实施

**目标**: 任务失败后自动重试，避免单次故障导致长期停更

**修复**:
1. Agent OS scheduler 加**任务失败重试机制**（现在只 fire-and-forget）
   - 失败后写执行记录（带 error），supply observability
   - 重试策略：失败后 1h/2h/4h 指数回退，3 次全失败才告警
2. 补充执行日志（GET /api/v1/scheduler/executions 要能查到失败任务）

**工作量**: 2-3 小时  
**负责方**: Agent OS 后端  
**优先级**: 🟠 P1

### 第二层：数据质量监控 + 主动告警 ⚠️ 待实施

**目标**: 质检发现异常时主动告警，不等人工巡检

**修复**:
1. `data_quality_check_daily` (16:00) 检测到 stale_days > 3 时**主动触发飞书告警**（高优）
2. 每日质检 summary 推送到飞书（近 7 日数据健康度 dashboard）
3. 因子计算任务失败后立即告警（不等到 16:00）

**实现位置**: quantsys-v2 后端 `services/data_quality.py` 调用 notification API  
**工作量**: 30 分钟  
**负责方**: quantsys-v2 后端  
**优先级**: 🔴 P0

### 第三层：防御性设计 + 降级策略 ✅ 已实施（部分）

**目标**: 工具层拒绝陈旧数据，防静默毒化

**已实施**:
1. ✅ **factor_calculate 工具加 freshness 校验**（2026-08-28 00:37）
   - 因子数据 > 3 天返回 warning（degraded mode）
   - 因子数据 > 7 天抛错拒绝服务（error: "因子数据过期拒绝服务：..."）
   - 输出带 `freshness_warnings` / `degraded` 字段
   - 代码位置: `agent-dh/packages/factor/src/index.ts` (line 95-119)

**待实施**:
2. ⚠️ **model_predict 工具加 freshness 提示**
   - 后端 `/api/models/predict` 应检查输入特征的 factor_date，返回 freshness_warning
   - 或工具层在 description 里提醒"模型预测依赖因子数据新鲜度，陈旧数据会降低预测可信度"
   
3. ⚠️ **策略层降级策略**
   - 因子不可用时，策略自动降级到"纯价格/成交量"维度
   - 禁用因子依赖的技术面信号（如 RSI 超卖、MACD 金叉）
   - 文档化因子依赖树：哪些工具/策略依赖因子

**工作量**: 1-2 小时  
**负责方**: agent-dh 插件 + quantsys-v2 后端  
**优先级**: 🟡 P2

## 立即行动项

| # | 任务 | 负责方 | 工作量 | 优先级 | 状态 |
|---|---|---|---|---|---|
| 1 | 一次性补录因子数据（8-22 至 8-27） | 后端手动 | 5 分钟 | 🔴 P0 | ⚠️ 待执行 |
| 2 | data_quality_check → 飞书告警接入 | quantsys-v2 | 30 分钟 | 🔴 P0 | ⚠️ 待开发 |
| 3 | factor_calculate freshness 校验 | agent-dh | 30 分钟 | 🟠 P1 | ✅ 已完成 |
| 4 | Agent OS scheduler 失败重试机制 | Agent OS | 2-3 小时 | 🟠 P1 | ⚠️ 待开发 |
| 5 | model/strategy 降级策略 | quantsys-v2 | 2 小时 | 🟡 P2 | ⚠️ 待设计 |

## 补录操作指南（给后端）

### 方案 A：手动触发 Agent OS 任务

```bash
# 1. 查任务 ID
curl -s http://localhost:8080/api/v1/scheduler/tasks | jq '.tasks[] | select(.name=="factor_compute_daily") | .id'

# 2. 触发任务
curl -X POST "http://localhost:8080/api/v1/scheduler/tasks/{task_id}/trigger"

# 3. 查执行日志
curl -s http://localhost:8080/api/v1/scheduler/executions?limit=5
```

如果 Agent OS API 不工作，改用方案 B。

### 方案 B：直接调 quantsys-v2 因子计算接口

```bash
# 补录 8-22 至 8-27 的因子（假设有批量接口）
curl -X POST "http://localhost:5001/api/v1/factors/compute" \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2026-08-22", "end_date": "2026-08-27", "force": true}'
```

如果没有批量接口，用 Python 脚本逐日调用：

```python
import requests
from datetime import date, timedelta

base = date(2026, 8, 22)
for i in range(6):  # 8-22 至 8-27
    d = base + timedelta(days=i)
    if d.weekday() < 5:  # 工作日
        r = requests.post(f'http://localhost:5001/api/v1/factors/compute',
                          json={'date': d.isoformat()})
        print(d, r.status_code, r.json().get('message'))
```

## 验证清单

补录完成后验证：

```bash
# 1. 查因子最新日期
curl -s "http://localhost:5001/api/v1/data/quality?data_type=factor" | jq '.factor_freshness'

# 2. 用 factor_calculate 工具测试（应无 degraded warning）
# 通过 DSH web UI 或 CLI 调用 factor_calculate symbol=600519

# 3. 确认没有 stale > 3 的因子
```

## 文档更新

- [x] 本文档（FACTOR-FRESHNESS-ROOT-FIX.md）
- [ ] 补充 `docs/operations/data-pipeline-monitoring.md`（数据管道监控 SOP）
- [ ] 补充 `docs/rfcs/005-data-freshness-framework.md`（数据新鲜度框架设计，推广到行情/财务等其他数据）

## 参考

- Agent OS scheduler tasks API: `http://localhost:8080/api/v1/scheduler/tasks`
- Data quality report 输出示例: `data_quality_report(data_type='all', days=3)`
- factor_calculate 源码: `agent-dh/packages/factor/src/index.ts` line 42-97

---

**状态**: 第三层（防御）已部分实施，第一、二层待后端配合  
**下一步**: 后端执行补录 + 告警接入（30 分钟工作量），然后进入常规监控流程
