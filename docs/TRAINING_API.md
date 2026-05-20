# 模型训练 API 文档

## 概述

模型训练API提供了通过HTTP接口训练机器学习模型的能力，支持参数配置、任务状态查询、日志查看和历史报告管理。

## API 端点

### 1. 启动训练任务

**POST** `/api/training/start`

启动一个新的模型训练任务。

#### 请求体

```json
{
  "days": 90,
  "model": "xgboost",
  "cvSplits": 5,
  "useFeatureEngineering": true
}
```

**参数说明：**

- `days` (number, 可选): 训练数据天数，范围 30-365，默认 90
- `model` (string, 可选): 模型类型，可选值：`xgboost`、`lightgbm`、`random_forest`，默认 `xgboost`
- `cvSplits` (number, 可选): 交叉验证折数，范围 2-10，默认 5
- `useFeatureEngineering` (boolean, 可选): 是否使用高级特征工程（49个特征），默认 `true`。设为 `false` 则使用原始特征（38个）

#### 响应

```json
{
  "success": true,
  "data": {
    "taskId": "train_1737273600000",
    "status": "running",
    "message": "Training started successfully"
  }
}
```

#### 示例

```bash
# 使用高级特征训练（推荐）
curl -X POST http://localhost:3001/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "days": 90,
    "model": "xgboost",
    "cvSplits": 5,
    "useFeatureEngineering": true
  }'

# 使用原始特征训练
curl -X POST http://localhost:3001/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "days": 90,
    "model": "xgboost",
    "cvSplits": 5,
    "useFeatureEngineering": false
  }'
```

---

### 2. 查询训练状态

**GET** `/api/training/status/:taskId`

查询指定训练任务的状态和结果。

#### 路径参数

- `taskId` (string): 训练任务ID

#### 响应

```json
{
  "success": true,
  "data": {
    "id": "train_1737273600000",
    "status": "completed",
    "progress": 100,
    "startTime": "2026-05-19T12:00:00.000Z",
    "endTime": "2026-05-19T12:05:30.000Z",
    "params": {
      "days": 90,
      "model": "xgboost",
      "cvSplits": 5,
      "useFeatureEngineering": true
    },
    "result": {
      "metrics": {
        "accuracy": 0.8214,
        "precision": 0.3254,
        "recall": 0.1307,
        "f1": 0.1802,
        "auc": 0.6314
      },
      "n_features": 49,
      "feature_names": ["month", "bb_width", "is_quarter_end", "..."]
    }
  }
}
```

**状态值：**
- `running`: 训练进行中
- `completed`: 训练成功完成
- `failed`: 训练失败

#### 示例

```bash
curl http://localhost:3001/api/training/status/train_1737273600000
```

---

### 3. 获取训练日志

**GET** `/api/training/logs/:taskId`

获取指定训练任务的实时日志。

#### 路径参数

- `taskId` (string): 训练任务ID

#### 响应

```json
{
  "success": true,
  "data": {
    "taskId": "train_1737273600000",
    "logs": [
      "开始训练...",
      "加载数据: 90天",
      "特征工程: 提取49个特征",
      "交叉验证: 5折",
      "..."
    ]
  }
}
```

#### 示例

```bash
curl http://localhost:3001/api/training/logs/train_1737273600000
```

---

### 4. 获取所有训练任务

**GET** `/api/training/tasks`

获取所有训练任务的列表（当前会话）。

#### 响应

```json
{
  "success": true,
  "data": [
    {
      "id": "train_1737273600000",
      "status": "completed",
      "progress": 100,
      "startTime": "2026-05-19T12:00:00.000Z",
      "endTime": "2026-05-19T12:05:30.000Z",
      "params": {
        "days": 90,
        "model": "xgboost",
        "cvSplits": 5,
        "useFeatureEngineering": true
      }
    }
  ]
}
```

#### 示例

```bash
curl http://localhost:3001/api/training/tasks
```

---

### 5. 获取历史训练报告列表

**GET** `/api/training/reports`

获取最近20个历史训练报告的摘要信息。

#### 响应

```json
{
  "success": true,
  "data": [
    {
      "filename": "training_report_20260519_112505.json",
      "timestamp": "20260519_112505",
      "metrics": {
        "accuracy": 0.8214,
        "precision": 0.3254,
        "recall": 0.1307,
        "f1": 0.1802,
        "auc": 0.6314
      },
      "params": {
        "days": 90,
        "model": "xgboost",
        "cv_splits": 5
      },
      "n_features": 49
    }
  ]
}
```

#### 示例

```bash
curl http://localhost:3001/api/training/reports
```

---

### 6. 获取特定训练报告详情

**GET** `/api/training/report/:filename`

获取指定训练报告的完整详情，包括特征重要性等。

#### 路径参数

- `filename` (string): 报告文件名，如 `training_report_20260519_112505.json`

#### 响应

```json
{
  "success": true,
  "data": {
    "timestamp": "2026-05-19 11:25:05",
    "params": {
      "days": 90,
      "model": "xgboost",
      "cv_splits": 5
    },
    "metrics": {
      "accuracy": 0.8214,
      "precision": 0.3254,
      "recall": 0.1307,
      "f1": 0.1802,
      "auc": 0.6314
    },
    "feature_names": ["month", "bb_width", "is_quarter_end", "..."],
    "n_features": 49,
    "feature_importance": [
      {"feature": "month", "importance": 0.0777},
      {"feature": "bb_width", "importance": 0.0672},
      {"feature": "is_quarter_end", "importance": 0.0608}
    ]
  }
}
```

#### 示例

```bash
curl http://localhost:3001/api/training/report/training_report_20260519_112505.json
```

---

## 完整使用流程示例

### 1. 启动训练

```bash
TASK_ID=$(curl -s -X POST http://localhost:3001/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"days": 90, "model": "xgboost", "cvSplits": 5, "useFeatureEngineering": true}' \
  | jq -r '.data.taskId')

echo "训练任务ID: $TASK_ID"
```

### 2. 轮询状态

```bash
while true; do
  STATUS=$(curl -s http://localhost:3001/api/training/status/$TASK_ID | jq -r '.data.status')
  PROGRESS=$(curl -s http://localhost:3001/api/training/status/$TASK_ID | jq -r '.data.progress')
  
  echo "状态: $STATUS, 进度: $PROGRESS%"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 5
done
```

### 3. 获取结果

```bash
curl -s http://localhost:3001/api/training/status/$TASK_ID | jq '.data.result'
```

### 4. 查看日志

```bash
curl -s http://localhost:3001/api/training/logs/$TASK_ID | jq -r '.data.logs[]'
```

---

## 特征对比

### 原始特征（38个）
- 直接从数据库读取的技术指标
- 包括：RSI、MACD、MA、BOLL、ATR等
- 性能基准：accuracy ~79.93%, AUC ~0.60

### 高级特征（49个，推荐）
- 通过FeatureEngineer生成的衍生特征
- 包括8类特征：
  - 基础特征（价格、成交量）
  - 收益率特征（1日、5日、20日收益）
  - 波动率特征（历史波动率、ATR比率）
  - 技术指标特征（RSI、MACD、布林带）
  - 成交量特征（成交量比率、价量关系）
  - 时间特征（月份、星期、季度末）
  - 统计特征（偏度、峰度）
  - 交叉特征（趋势×成交量、RSI×均线比率）
- 性能提升：accuracy ~82.14%, AUC ~0.63（+5.3%）

---

## 错误处理

所有API在出错时返回统一格式：

```json
{
  "success": false,
  "error": "错误信息"
}
```

常见错误：
- `400 Bad Request`: 参数验证失败
- `404 Not Found`: 任务或报告不存在
- `500 Internal Server Error`: 服务器内部错误

---

## 注意事项

1. **训练时间**：根据数据量和模型复杂度，训练可能需要几分钟到十几分钟
2. **并发限制**：建议同时只运行一个训练任务，避免资源竞争
3. **任务持久化**：当前任务状态仅保存在内存中，服务器重启后会丢失。历史报告文件会持久化保存
4. **Python环境**：确保服务器环境中有Python 3和必要的依赖包（xgboost、pandas、numpy等）
5. **数据库**：训练需要访问 `quant/quantsys/data/stocks.db` 数据库

---

## 前端集成建议

### React组件示例

```typescript
// TrainingPage.tsx
import { useState } from 'react';

interface TrainingParams {
  days: number;
  model: 'xgboost' | 'lightgbm' | 'random_forest';
  cvSplits: number;
  useFeatureEngineering: boolean;
}

export function TrainingPage() {
  const [params, setParams] = useState<TrainingParams>({
    days: 90,
    model: 'xgboost',
    cvSplits: 5,
    useFeatureEngineering: true
  });
  
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [progress, setProgress] = useState<number>(0);
  const [result, setResult] = useState<any>(null);

  const startTraining = async () => {
    const response = await fetch('http://localhost:3001/api/training/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    
    const data = await response.json();
    if (data.success) {
      setTaskId(data.data.taskId);
      setStatus('running');
      pollStatus(data.data.taskId);
    }
  };

  const pollStatus = async (id: string) => {
    const interval = setInterval(async () => {
      const response = await fetch(`http://localhost:3001/api/training/status/${id}`);
      const data = await response.json();
      
      if (data.success) {
        setStatus(data.data.status);
        setProgress(data.data.progress);
        
        if (data.data.status === 'completed') {
          setResult(data.data.result);
          clearInterval(interval);
        } else if (data.data.status === 'failed') {
          clearInterval(interval);
        }
      }
    }, 3000);
  };

  return (
    <div>
      <h1>模型训练</h1>
      
      {/* 参数配置表单 */}
      <form onSubmit={(e) => { e.preventDefault(); startTraining(); }}>
        <label>
          训练天数:
          <input 
            type="number" 
            value={params.days} 
            onChange={(e) => setParams({...params, days: parseInt(e.target.value)})}
            min={30}
            max={365}
          />
        </label>
        
        <label>
          模型类型:
          <select 
            value={params.model}
            onChange={(e) => setParams({...params, model: e.target.value as any})}
          >
            <option value="xgboost">XGBoost</option>
            <option value="lightgbm">LightGBM</option>
            <option value="random_forest">Random Forest</option>
          </select>
        </label>
        
        <label>
          交叉验证折数:
          <input 
            type="number" 
            value={params.cvSplits}
            onChange={(e) => setParams({...params, cvSplits: parseInt(e.target.value)})}
            min={2}
            max={10}
          />
        </label>
        
        <label>
          <input 
            type="checkbox"
            checked={params.useFeatureEngineering}
            onChange={(e) => setParams({...params, useFeatureEngineering: e.target.checked})}
          />
          使用高级特征工程（推荐）
        </label>
        
        <button type="submit" disabled={status === 'running'}>
          开始训练
        </button>
      </form>
      
      {/* 训练状态 */}
      {status === 'running' && (
        <div>
          <p>训练进行中...</p>
          <progress value={progress} max={100}>{progress}%</progress>
        </div>
      )}
      
      {/* 训练结果 */}
      {status === 'completed' && result && (
        <div>
          <h2>训练完成</h2>
          <p>准确率: {(result.metrics.accuracy * 100).toFixed(2)}%</p>
          <p>精确率: {(result.metrics.precision * 100).toFixed(2)}%</p>
          <p>召回率: {(result.metrics.recall * 100).toFixed(2)}%</p>
          <p>F1分数: {(result.metrics.f1 * 100).toFixed(2)}%</p>
          <p>AUC: {result.metrics.auc.toFixed(4)}</p>
          <p>特征数量: {result.n_features}</p>
        </div>
      )}
    </div>
  );
}
```

---

## 性能监控

建议在前端添加以下监控指标：

1. **训练时长**：记录从开始到完成的时间
2. **模型性能趋势**：对比历史训练结果，绘制性能曲线
3. **特征重要性可视化**：展示Top 20特征的重要性柱状图
4. **参数对比**：不同参数组合的性能对比表格

---

## 下一步优化

1. **WebSocket支持**：实时推送训练进度和日志
2. **任务队列**：支持多个训练任务排队执行
3. **模型版本管理**：标记和回滚模型版本
4. **自动调参**：集成超参数优化（如Optuna）
5. **分布式训练**：支持多机并行训练
