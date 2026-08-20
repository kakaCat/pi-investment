# 模型训练自动化系统

## 概述

基于quantsys-v2的调度系统，实现ML模型的**自动化训练、评估、版本管理和切换**。

## 架构

```
┌─────────────────────────────────────────────┐
│  Agent OS Scheduler (Cron)                  │
│  • 每周一 03:00 - 智能训练                  │
│  • 每月1号 03:00 - 强制训练                 │
└─────────────────┬───────────────────────────┘
                  │ webhook
                  ↓
┌─────────────────────────────────────────────┐
│  Quantsys-V2 Scheduler Webhook              │
│  /internal/scheduler/webhook                │
└─────────────────┬───────────────────────────┘
                  │ dispatch
                  ↓
┌─────────────────────────────────────────────┐
│  handle_model_train_auto()                  │
│  • 智能判断（是否需要训练）                 │
│  • 数据加载（K线 + 因子）                   │
│  • 特征工程                                 │
│  • 模型训练                                 │
│  • 性能评估                                 │
│  • 版本管理                                 │
│  • 自动切换（可选）                         │
└─────────────────────────────────────────────┘
```

## 功能特性

### 1. 智能训练判断

**触发条件**（满足任一）：
- 模型超过7天未更新
- 模型性能 < 0.55（test_accuracy）
- 无可用模型
- 强制训练（force_train=True）

**跳过条件**：
- 模型新鲜（<7天）且性能良好（>=0.55）

### 2. 自动化流程

1. **数据加载**：从回填后的因子数据加载K线（默认350天）
2. **特征工程**：自动提取技术因子和资金流因子
3. **模型训练**：LightGBM/XGBoost，train/test split
4. **性能评估**：计算train_accuracy和test_accuracy
5. **版本管理**：保存到`live_trading/models/`和DB元数据
6. **自动切换**：新模型性能提升>=1%时自动切换

### 3. 版本管理

**模型文件命名**：`{model_type}_{YYYYMMDD_HHMMSS}.pkl`

**DB记录**：
```sql
quant.ml_models:
  - model_type, version, model_path
  - train_accuracy, test_accuracy
  - train_samples, feature_count
  - training_params (symbols_count, lookback_days, etc.)
  - status (ready/training/failed)
  - train_date
```

**版本解析**：`_resolve_latest_version()` 优先DB记录，回退文件mtime

## 使用方法

### 1. 注册定时任务

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
python tools/register_model_train_task.py
```

**输出**：
```
=== 模型训练任务注册工具 ===

1. 检查现有任务...
已注册的模型训练任务：0 个

2. 注册每周训练任务...
✓ 每周训练任务已注册: 12345

3. 注册每月训练任务...
✓ 每月训练任务已注册: 12346

4. 最终任务列表:
已注册的模型训练任务：2 个
  [✓ 启用] model_train_auto_weekly: 每周一凌晨3点...
       cron: 0 3 * * 1, id: 12345
  [✓ 启用] model_train_auto_monthly: 每月1号凌晨3点...
       cron: 0 3 1 * *, id: 12346
```

### 2. 手动触发训练

#### 方式1：通过webhook（推荐）

```bash
curl -X POST http://localhost:5001/internal/scheduler/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "model_train_auto",
    "description": "手动触发模型训练",
    "params": {
      "model_type": "lightgbm",
      "symbols_limit": 100,
      "force_train": true
    }
  }'
```

#### 方式2：直接调用Python

```bash
cd quantsys-v2
source activate-py313.sh
python -c "
from application.services.scheduler_tasks import handle_model_train_auto
result = handle_model_train_auto({
    'model_type': 'lightgbm',
    'symbols_limit': 50,  # 小规模测试
    'force_train': True
})
print(result)
"
```

### 3. 查看训练历史

```sql
-- 查看所有模型
SELECT model_type, version, train_accuracy, test_accuracy, train_date, status
FROM quant.ml_models
ORDER BY train_date DESC
LIMIT 10;

-- 查看最新模型
SELECT *
FROM quant.ml_models
WHERE model_type = 'lightgbm'
ORDER BY train_date DESC
LIMIT 1;
```

### 4. 管理任务

```bash
# 列出所有任务
curl http://localhost:8080/api/v1/scheduler/tasks

# 禁用任务
curl -X PATCH http://localhost:8080/api/v1/scheduler/tasks/{task_id} \
  -d '{"enabled": false}'

# 删除任务
curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks/{task_id}
```

## 参数配置

### handle_model_train_auto() 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_type` | str | `"lightgbm"` | 模型类型（lightgbm/xgboost） |
| `symbols_limit` | int | `500` | 训练样本股票数 |
| `lookback_days` | int | `350` | 历史数据天数（≈250交易日） |
| `force_train` | bool | `False` | 强制训练（忽略智能判断） |
| `auto_switch` | bool | `True` | 性能提升时自动切换 |
| `test_size` | float | `0.2` | 测试集比例 |

### 调度策略建议

| 场景 | cron | 参数 |
|------|------|------|
| **每周智能训练** | `0 3 * * 1` | `force_train=False, auto_switch=True` |
| **每月强制训练** | `0 3 1 * *` | `force_train=True, auto_switch=False` |
| **数据回填后** | 手动触发 | `symbols_limit=500, force_train=True` |
| **快速测试** | 手动触发 | `symbols_limit=20, force_train=True` |

## 监控与告警

### 训练结果

```json
{
  "action": "model_train_auto",
  "status": "success",
  "model_type": "lightgbm",
  "version": "20260820_030015",
  "train_accuracy": 0.6234,
  "test_accuracy": 0.5812,
  "train_samples": 45000,
  "test_samples": 11250,
  "feature_count": 42,
  "symbols_trained": 480,
  "auto_switched": true,
  "timestamp": "2026-08-20T03:15:22Z"
}
```

### 失败情况

```json
{
  "action": "model_train_auto",
  "status": "failed",
  "error": "数据不足：仅加载30只股票（需>=50）",
  "timestamp": "2026-08-20T03:05:10Z"
}
```

### 跳过情况

```json
{
  "action": "model_train_auto",
  "status": "skipped",
  "reason": "模型20260813_030015仍有效 (age=5d, acc=0.5912)",
  "timestamp": "2026-08-20T03:00:05Z"
}
```

## 故障排查

### 1. 训练失败

**症状**：`status: "failed"`

**排查**：
```bash
# 检查数据可用性
psql -d quant_investment -c "
SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT factor_date)
FROM quant.factor_values
WHERE factor_date >= CURRENT_DATE - INTERVAL '350 days';
"

# 检查后端日志
tail -100 /tmp/quantsys-v2.log | grep "model_train_auto"
```

### 2. 任务未执行

**症状**：定时任务到点未触发

**排查**：
```bash
# 检查Agent OS状态
curl http://localhost:8080/api/v1/health

# 检查任务列表
curl http://localhost:8080/api/v1/scheduler/tasks | jq '.[] | select(.name | contains("model_train"))'

# 检查webhook可达性
curl -X POST http://localhost:5001/internal/scheduler/webhook \
  -d '{"job_type":"ping"}'
```

### 3. 模型性能低

**症状**：`test_accuracy < 0.52`

**原因**：
- 特征失效（市场regime变化）
- 训练数据不足
- 标签噪声过大

**解决**：
- 增加训练样本（symbols_limit）
- 调整lookback_days
- 检查因子质量（data_quality_check）

## 最佳实践

1. **首次使用**：手动触发小规模训练验证流程（symbols_limit=20）
2. **数据回填后**：手动强制训练一次（force_train=True）
3. **每周智能训练**：让系统自动判断是否需要训练
4. **每月定期训练**：保持模型新鲜度，不自动切换（需人工审核）
5. **性能监控**：每次训练后检查test_accuracy，低于0.55需排查
6. **版本管理**：保留最近3个版本的模型文件，定期清理旧版本

## 未来改进

- [ ] 训练完成后发送飞书通知
- [ ] 多模型集成（ensemble）
- [ ] 超参数自动优化（optuna）
- [ ] A/B测试框架（对比新旧模型实盘效果）
- [ ] 模型漂移监控（特征分布变化检测）

---

**版本**：1.0.0  
**日期**：2026-08-20  
**作者**：System
