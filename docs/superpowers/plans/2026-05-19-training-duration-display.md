# 训练时长显示功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在模型训练历史页面添加训练时长显示，包括开始时间、结束时间和格式化的总时长。

**Architecture:** 在Python训练脚本中记录时长信息到training_report JSON，通过现有API传递给React前端显示。采用可选字段设计，向后兼容旧记录。

**Tech Stack:** Python (datetime), Node.js/TypeScript (Express), React (Ant Design), JSON

---

## 文件结构

**修改的文件：**
- `quant/scripts/ml_retrain.py` - 添加训练时长记录逻辑
- `src/api/web/routes/training.ts` - API返回时长字段
- `quant-web/src/components/TrainingHistory.tsx` - 前端显示时长列

**测试文件：**
- `quant/scripts/test_ml_retrain.py` - 验证时长记录功能

---

### Task 1: Python训练脚本添加时长记录

**Files:**
- Modify: `quant/scripts/ml_retrain.py:514-576`

- [ ] **Step 1: 在main函数开始处记录开始时间**

在 `main()` 函数中，在日志输出 "ML 模型重训练任务" 之后添加：

```python
# 在第514行之后添加
start_time = datetime.now()
logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
```

- [ ] **Step 2: 修改save_training_report方法签名，接收时长参数**

修改 `save_training_report` 方法（第367-391行）：

```python
def save_training_report(
    self,
    report: Dict[str, Any],
    feature_names: List[str],
    start_time: datetime = None,
    end_time: datetime = None
):
    """保存训练报告"""
    report['feature_names'] = feature_names
    report['n_features'] = len(feature_names)
    
    # 添加时长信息
    if start_time and end_time:
        report['start_time'] = start_time.isoformat()
        report['end_time'] = end_time.isoformat()
        report['duration_seconds'] = (end_time - start_time).total_seconds()

    # 保存为JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"training_report_{timestamp}.json"
    report_path = os.path.join(self.model_dir, report_filename)

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"训练报告已保存: {report_path}")

    # 同时保存为最新报告
    latest_report_path = os.path.join(self.model_dir, 'training_report_latest.json')
    with open(latest_report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"最新报告已保存: {latest_report_path}")
```

- [ ] **Step 3: 使用try-finally确保时长记录**

修改 `main()` 函数的try-except块（第527-586行）：

```python
try:
    # 创建重训练器
    retrainer = MLRetrainer(db_path)

    # 1. 加载数据
    features_df, labels_df = retrainer.load_training_data(
        days=args.days,
        future_days=args.future_days,
        return_threshold=args.threshold
    )

    # 2. 准备特征
    X, y, feature_names = retrainer.prepare_features(
        features_df,
        labels_df,
        use_feature_engineering=args.use_feature_engineering
    )

    # 3. 训练模型
    training_report = retrainer.train_model(
        X, y,
        model_type=args.model,
        tune_hyperparams=args.tune,
        n_trials=args.trials,
        cv_splits=args.cv_splits
    )

    # 4. 保存报告（添加时长参数）
    end_time = datetime.now()
    retrainer.save_training_report(
        training_report, 
        feature_names,
        start_time=start_time,
        end_time=end_time
    )

    # 5. 打印摘要
    retrainer.print_summary(training_report)

    # 6. 检查模型性能
    test_accuracy = training_report['test_metrics']['accuracy']
    if test_accuracy < 0.55:
        logger.warning("")
        logger.warning("⚠️  警告: 模型准确率低于55%")
        logger.warning("建议:")
        logger.warning("  1. 增加训练数据（--days 参数）")
        logger.warning("  2. 调整涨幅阈值（--threshold 参数）")
        logger.warning("  3. 尝试超参数优化（--tune 参数）")
        logger.warning("  4. 尝试其他模型类型（--model 参数）")
        logger.warning("")

    # 计算并显示总时长
    duration = (end_time - start_time).total_seconds()
    duration_str = f"{int(duration // 60)}分{int(duration % 60)}秒" if duration >= 60 else f"{int(duration)}秒"
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ 训练任务完成")
    logger.info(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"训练时长: {duration_str}")
    logger.info("=" * 60)

except Exception as e:
    logger.error("")
    logger.error("=" * 60)
    logger.error("❌ 训练任务失败")
    logger.error(f"错误: {e}")
    logger.error("=" * 60)
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)
```

- [ ] **Step 4: 验证修改**

运行训练脚本测试：

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python scripts/ml_retrain.py --days 90 --model xgboost
```

Expected: 训练完成后，检查生成的 `training_report_latest.json` 包含 `start_time`, `end_time`, `duration_seconds` 字段

- [ ] **Step 5: 提交Python脚本修改**

```bash
git add quant/scripts/ml_retrain.py
git commit -m "feat(quant): add training duration tracking to ml_retrain script"
```

---

### Task 2: API层添加时长字段支持

**Files:**
- Modify: `src/api/web/routes/training.ts:295-338`

- [ ] **Step 1: 更新history端点返回时长字段**

修改 `/api/training/history` 端点（第295-338行）：

```typescript
// GET /api/training/history - 获取训练历史记录
router.get('/history', async (req, res, next) => {
  try {
    const modelsDir = path.join(__dirname, '../../../../quant/quantsys/ml/models');

    if (!fs.existsSync(modelsDir)) {
      res.json({ history: [] });
      return;
    }

    const files = fs.readdirSync(modelsDir);
    const reportFiles = files
      .filter(f => f.startsWith('training_report_') && f.endsWith('.json') && f !== 'training_report_latest.json')
      .sort()
      .reverse();

    const history = reportFiles.slice(0, 50).map(filename => {
      try {
        const filePath = path.join(modelsDir, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const report = JSON.parse(content);

        return {
          timestamp: report.timestamp,
          start_time: report.start_time,           // 新增
          end_time: report.end_time,               // 新增
          duration_seconds: report.duration_seconds, // 新增
          model_type: report.model_type,
          n_features: report.data?.n_features || 0,
          total_samples: report.data?.total_samples || 0,
          cv_accuracy: report.cv_results?.mean_scores?.accuracy || 0,
          cv_auc: report.cv_results?.mean_scores?.auc || 0,
          test_accuracy: report.test_metrics?.accuracy || 0,
          test_auc: report.test_metrics?.auc || 0,
          class_balance: report.data?.class_balance || 0
        };
      } catch (error) {
        console.warn(`Failed to parse training report ${filename}:`, error);
        return null;
      }
    }).filter(record => record !== null);

    res.json({ history });
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 2: 测试API端点**

启动开发服务器并测试：

```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

在另一个终端测试API：

```bash
curl http://localhost:3000/api/training/history | jq '.'
```

Expected: 返回的JSON中，新训练记录包含 `start_time`, `end_time`, `duration_seconds` 字段，旧记录这些字段为 `null`

- [ ] **Step 3: 提交API修改**

```bash
git add src/api/web/routes/training.ts
git commit -m "feat(api): add training duration fields to history endpoint"
```

---

### Task 3: 前端添加训练时长显示列

**Files:**
- Modify: `quant-web/src/components/TrainingHistory.tsx:6-16,45-117`

- [ ] **Step 1: 更新TypeScript接口**

修改 `TrainingRecord` 接口（第6-16行）：

```typescript
interface TrainingRecord {
  timestamp: string;
  start_time?: string;      // 新增
  end_time?: string;        // 新增
  duration_seconds?: number; // 新增
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

- [ ] **Step 2: 添加时长格式化函数**

在 `TrainingHistory` 组件内部，`columns` 定义之前添加：

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

- [ ] **Step 3: 在表格列定义中添加训练时长列**

在 `columns` 数组中，"训练时间"列之后添加新列（第52行之后）：

```typescript
const columns: ColumnsType<TrainingRecord> = [
  {
    title: '训练时间',
    dataIndex: 'timestamp',
    key: 'timestamp',
    width: 180,
    render: (timestamp: string) => new Date(timestamp).toLocaleString('zh-CN')
  },
  {
    title: '训练时长',
    key: 'duration',
    width: 220,
    render: (record: TrainingRecord) => {
      if (!record.start_time || !record.end_time || record.duration_seconds === undefined) {
        return <span style={{ color: '#999' }}>未记录</span>;
      }
      
      try {
        const startTime = new Date(record.start_time).toLocaleTimeString('zh-CN', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit' 
        });
        const endTime = new Date(record.end_time).toLocaleTimeString('zh-CN', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit' 
        });
        const duration = formatDuration(record.duration_seconds);
        
        return (
          <div>
            <div style={{ fontSize: '12px', color: '#666' }}>
              {startTime} - {endTime}
            </div>
            <div style={{ fontSize: '13px', fontWeight: 500 }}>
              {duration}
            </div>
          </div>
        );
      } catch (error) {
        return <span style={{ color: '#999' }}>-</span>;
      }
    }
  },
  {
    title: '模型类型',
    dataIndex: 'model_type',
    key: 'model_type',
    width: 120,
    render: (type: string) => type.toUpperCase()
  },
  // ... 其他列保持不变
];
```

- [ ] **Step 4: 测试前端显示**

启动前端开发服务器：

```bash
cd /Users/mac/Documents/ai/pi-investment/quant-web
npm run dev
```

在浏览器中访问训练历史页面，验证：
- 新训练记录显示时长信息（开始-结束时间 + 格式化时长）
- 旧训练记录显示"未记录"
- 表格布局正常，列宽合理

Expected: 
- 有时长数据的记录显示类似 "10:07:21 - 10:09:51" 和 "2分30秒"
- 旧记录显示灰色的"未记录"文字

- [ ] **Step 5: 提交前端修改**

```bash
git add quant-web/src/components/TrainingHistory.tsx
git commit -m "feat(web): add training duration column to history table"
```

---

### Task 4: 端到端测试

**Files:**
- Test: All modified files

- [ ] **Step 1: 运行完整训练流程**

启动后端服务：

```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

在另一个终端运行训练：

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python scripts/ml_retrain.py --days 90 --model xgboost
```

Expected: 训练完成，日志显示训练时长

- [ ] **Step 2: 验证training_report JSON格式**

检查生成的报告文件：

```bash
cat /Users/mac/Documents/ai/pi-investment/quant/quantsys/ml/models/training_report_latest.json | jq '{start_time, end_time, duration_seconds, timestamp}'
```

Expected: 输出包含所有四个时间字段，格式正确

- [ ] **Step 3: 验证API返回数据**

测试API端点：

```bash
curl http://localhost:3000/api/training/history | jq '.[0] | {timestamp, start_time, end_time, duration_seconds}'
```

Expected: 最新记录包含时长字段

- [ ] **Step 4: 验证前端显示**

在浏览器中：
1. 访问训练历史页面
2. 检查最新记录的"训练时长"列
3. 检查旧记录显示"未记录"
4. 测试不同时长格式（秒、分秒、小时分）

Expected: 所有显示正常，无控制台错误

- [ ] **Step 5: 测试边界情况**

测试时间格式异常处理：

在浏览器开发者工具Console中：

```javascript
// 模拟异常数据
const testRecord = {
  start_time: 'invalid-date',
  end_time: '2026-05-19T12:00:00',
  duration_seconds: 150
};
```

Expected: 前端不报错，显示"-"或"未记录"

- [ ] **Step 6: 最终提交**

```bash
git add -A
git commit -m "feat: add training duration display feature

- Python: record start_time, end_time, duration_seconds in training reports
- API: return duration fields in /api/training/history endpoint
- Frontend: display duration column with formatted time range and duration
- Backward compatible: old records show '未记录' for missing duration data"
```

---

## 测试验证清单

**功能测试：**
- [ ] 新训练记录包含时长信息
- [ ] 旧训练记录显示"未记录"
- [ ] 时长格式化正确（秒、分秒、小时分）
- [ ] 训练失败时仍记录时长

**兼容性测试：**
- [ ] API不因缺少时长字段报错
- [ ] 前端安全处理undefined值
- [ ] 旧的training_report文件仍可正常读取

**UI测试：**
- [ ] 表格列宽度合理
- [ ] 时间显示格式清晰
- [ ] 不同屏幕尺寸下显示正常
- [ ] 无控制台错误或警告

**性能测试：**
- [ ] 加载50条历史记录无明显延迟
- [ ] 时长格式化不影响渲染性能

---

## 回滚计划

如果需要回滚此功能：

1. 恢复Python脚本：
```bash
git revert <commit-hash>
```

2. 旧的training_report文件不受影响，系统继续正常工作

3. 前端会对所有记录显示"未记录"，但不会报错

---

## 未来优化方向

- 在训练任务实时状态中显示已用时长
- 添加平均训练时长统计卡片
- 支持按时长排序和筛选
- 训练时长趋势图表分析
