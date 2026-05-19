# 模型训练时长显示功能设计

## 概述

在模型训练历史页面添加训练时长显示功能，让用户能够看到每次训练的开始时间、结束时间和总时长。

## 需求

用户希望在训练历史页面看到：
- 训练开始时间
- 训练结束时间  
- 训练总时长（格式化显示）

对于历史记录的处理策略：只为新训练记录时长，旧的历史记录显示"未记录"。

## 架构设计

### 数据流

```
Python训练脚本 → training_report JSON → Node.js API → React前端
```

采用在源头（Python脚本）记录时长的方案，确保所有训练方式（通过API或手动运行）都能记录时长。

## 详细设计

### 1. 数据层（Python训练脚本）

**修改文件：** `quant/scripts/ml_retrain.py` 及相关训练脚本

**实现要点：**
- 训练开始时记录 `start_time = datetime.now()`
- 训练结束时记录 `end_time = datetime.now()`
- 计算 `duration_seconds = (end_time - start_time).total_seconds()`
- 将时间信息保存到 training_report JSON

**新增JSON字段：**
```json
{
  "timestamp": "2026-05-19T12:36:28.941291",
  "start_time": "2026-05-19T12:34:00.123456",
  "end_time": "2026-05-19T12:36:28.941291",
  "duration_seconds": 148.82,
  "success": true,
  "model_type": "xgboost",
  ...
}
```

**字段说明：**
- `timestamp`: 现有字段，训练完成时间（保持不变）
- `start_time`: 新增，训练开始时间（ISO 8601格式）
- `end_time`: 新增，训练结束时间（ISO 8601格式，与timestamp相同）
- `duration_seconds`: 新增，训练总时长（秒，浮点数）

### 2. API层（Node.js）

**修改文件：** `src/api/web/routes/training.ts`

**修改端点：** `GET /api/training/history` (第295-338行)

**实现要点：**
- 读取 training_report JSON 时提取新增字段
- 对于旧记录（没有时长字段），字段值为 `undefined`
- 返回数据兼容新旧格式

**TypeScript接口更新：**
```typescript
interface TrainingHistoryRecord {
  timestamp: string;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  model_type: string;
  n_features: number;
  total_samples: number;
  cv_accuracy: number;
  cv_auc: number;
  test_accuracy: number;
  test_auc: number;
  class_balance: number;
}
```

**数据提取逻辑：**
```typescript
return {
  timestamp: report.timestamp,
  start_time: report.start_time,
  end_time: report.end_time,
  duration_seconds: report.duration_seconds,
  model_type: report.model_type,
  // ... 其他字段
};
```

### 3. 前端UI层（React）

**修改文件：** `quant-web/src/components/TrainingHistory.tsx`

**TypeScript接口更新：**
```typescript
interface TrainingRecord {
  timestamp: string;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  model_type: string;
  n_features: number;
  total_samples: number;
  cv_accuracy: number;
  cv_auc: number;
  test_accuracy: number;
  test_auc: number;
  class_balance: number;
}
```

**新增表格列：**

在"训练时间"列之后添加"训练时长"列：

```typescript
{
  title: '训练时长',
  key: 'duration',
  width: 200,
  render: (record: TrainingRecord) => {
    if (!record.start_time || !record.end_time || !record.duration_seconds) {
      return <span style={{ color: '#999' }}>未记录</span>;
    }
    
    const startTime = new Date(record.start_time).toLocaleTimeString('zh-CN');
    const endTime = new Date(record.end_time).toLocaleTimeString('zh-CN');
    const duration = formatDuration(record.duration_seconds);
    
    return `${startTime} - ${endTime} (${duration})`;
  }
}
```

**时长格式化函数：**
```typescript
const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}秒`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}分${secs}秒`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}小时${minutes}分`;
  }
};
```

**显示示例：**
- 有时长数据：`10:07:21 - 10:09:51 (2分30秒)`
- 无时长数据：`未记录`（灰色文字）

### 4. 错误处理

**Python脚本层：**
- 使用 try-finally 确保即使训练失败也记录时长
- 训练异常时仍然保存 start_time、end_time、duration_seconds

```python
start_time = datetime.now()
try:
    # 训练逻辑
    train_model()
    success = True
except Exception as e:
    success = False
    error = str(e)
finally:
    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()
    save_report({
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_seconds': duration_seconds,
        'success': success,
        ...
    })
```

**API层：**
- 安全读取可选字段，不存在时返回 `undefined`
- 不因缺少时长字段而报错

**前端层：**
- 检查字段存在性再渲染
- 时间解析失败时显示"-"而不是报错
- 使用可选链操作符避免 undefined 错误

### 5. 测试验证

**测试场景：**

1. **新训练记录测试**
   - 启动一次新训练
   - 验证 training_report JSON 包含 start_time、end_time、duration_seconds
   - 验证前端正确显示时长信息

2. **旧记录兼容性测试**
   - 查看现有历史记录
   - 验证旧记录显示"未记录"
   - 验证不会因缺少字段而报错

3. **时长格式化测试**
   - 测试短时长（<60秒）：显示"X秒"
   - 测试中等时长（1-60分钟）：显示"X分Y秒"
   - 测试长时长（>60分钟）：显示"X小时Y分"

4. **UI布局测试**
   - 验证新列宽度合理
   - 验证表格不会因内容过长而错位
   - 验证在不同屏幕尺寸下显示正常

5. **异常情况测试**
   - 训练失败时仍能记录时长
   - 时间格式异常时显示"-"
   - API返回错误时前端正常处理

## 实现顺序

1. 修改Python训练脚本，添加时长记录
2. 修改API端点，读取并返回时长字段
3. 修改前端组件，添加时长显示列
4. 运行一次新训练，验证完整流程
5. 检查旧记录显示是否正常

## 向后兼容性

- 旧的 training_report JSON 文件不包含时长字段，前端显示"未记录"
- API 和前端都使用可选字段（`?:`），不会因缺少字段而报错
- 不需要迁移或修改现有历史数据

## 未来扩展

可能的扩展方向：
- 在训练任务卡片中也显示时长
- 添加平均训练时长统计
- 按时长排序功能
- 训练时长趋势图表
