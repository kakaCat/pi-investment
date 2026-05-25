# L3 模型层实施计划

## 项目信息

- **日期**: 2026-05-25
- **目标**: 实现 L3 模型层的 5 个工具
- **范围**: 后端 daemon 方法 + Agent 层工具 + 测试
- **执行方式**: Subagent-Driven Development

## 背景

后端已有完整的 ML 功能：
- ✅ `MLTrainingService` - 模型训练服务（XGBoost, LightGBM）
- ✅ `SignalPredictor` - 信号预测服务
- ✅ `ConfidenceCalibrator` - 置信度校准
- ✅ CLI 命令：`quant stock +ml-predict`, `quant ml +history`

缺少的部分：
- ❌ Daemon API 方法（train_model, list_models, evaluate_model, monitor_model）
- ❌ Agent 层工具（model_train, model_predict, model_evaluate, model_monitor, model_list）
- ❌ 完整的测试覆盖

## 任务列表

### Task 1: 补充后端 Daemon 方法

**目标**: 在 `quant/quantsys/cli/ml_query.py` 中添加缺失的 daemon 方法

**需要添加的方法**:

1. **train_model** - 训练模型
   ```python
   def _train_model(params: Dict[str, Any]) -> Any:
       """Train a new ML model."""
       from quantsys.ml.training_service import MLTrainingService
       from .context import build_context
       
       ctx = build_context()
       service = MLTrainingService(ctx.db_connection)
       
       # 加载训练数据
       data_df, labels_df = service.load_training_data(
           days=params.get("days", 180),
           future_days=params.get("future_days", 5),
           return_threshold=params.get("return_threshold", 0.05),
           symbols=params.get("symbols")
       )
       
       # 准备特征
       X, y, feature_names = service.prepare_features(data_df)
       
       # 训练模型
       model_type = params.get("model_type", "xgboost")
       if model_type == "xgboost":
           report = service.train_xgboost(X, y, feature_names, n_splits=params.get("cv_splits", 5))
       else:
           raise ValueError(f"Unsupported model type: {model_type}")
       
       # 保存报告
       job_id = params.get("job_id", f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
       service.save_training_report(report, job_id)
       
       return report
   ```

2. **list_models** - 列出模型
   ```python
   def _list_models(params: Dict[str, Any]) -> Any:
       """List all trained models."""
       from pathlib import Path
       import json
       
       model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'
       models = []
       
       for model_file in model_dir.glob("xgboost_model_*.pkl"):
           timestamp = model_file.stem.replace("xgboost_model_", "")
           report_file = model_dir / f"training_report_{timestamp}.json"
           
           if report_file.exists():
               with open(report_file) as f:
                   report = json.load(f)
               models.append({
                   "model_id": timestamp,
                   "model_type": "xgboost",
                   "model_path": str(model_file),
                   "timestamp": report.get("timestamp"),
                   "test_accuracy": report.get("test_metrics", {}).get("accuracy"),
                   "test_f1": report.get("test_metrics", {}).get("f1"),
                   "n_features": report.get("n_features")
               })
       
       # 按时间倒序排序
       models.sort(key=lambda x: x["timestamp"], reverse=True)
       
       return {"models": models, "total": len(models)}
   ```

3. **evaluate_model** - 评估模型
   ```python
   def _evaluate_model(params: Dict[str, Any]) -> Any:
       """Evaluate a trained model."""
       from pathlib import Path
       import json
       
       model_id = params.get("model_id", "latest")
       model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'
       
       if model_id == "latest":
           report_file = model_dir / "training_report_latest.json"
       else:
           report_file = model_dir / f"training_report_{model_id}.json"
       
       if not report_file.exists():
           raise FileNotFoundError(f"Model report not found: {report_file}")
       
       with open(report_file) as f:
           report = json.load(f)
       
       return {
           "model_id": model_id,
           "model_type": report.get("model_type"),
           "timestamp": report.get("timestamp"),
           "data": report.get("data"),
           "cv_results": report.get("cv_results"),
           "test_metrics": report.get("test_metrics"),
           "feature_importance": report.get("feature_importance"),
           "feature_names": report.get("feature_names")
       }
   ```

4. **monitor_model** - 监控模型（特征漂移）
   ```python
   def _monitor_model(params: Dict[str, Any]) -> Any:
       """Monitor model for feature drift."""
       from pathlib import Path
       import json
       import pickle
       import numpy as np
       
       model_id = params.get("model_id", "latest")
       model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'
       
       # 加载模型
       if model_id == "latest":
           model_file = model_dir / "xgboost_latest.pkl"
           report_file = model_dir / "training_report_latest.json"
       else:
           model_file = model_dir / f"xgboost_model_{model_id}.pkl"
           report_file = model_dir / f"training_report_{model_id}.json"
       
       if not model_file.exists():
           raise FileNotFoundError(f"Model not found: {model_file}")
       
       with open(model_file, 'rb') as f:
           model = pickle.load(f)
       
       with open(report_file) as f:
           report = json.load(f)
       
       # 获取训练时的特征重要性
       train_importance = np.array(report.get("feature_importance", []))
       feature_names = report.get("feature_names", [])
       
       # 当前模型的特征重要性
       current_importance = model.feature_importances_
       
       # 计算漂移（欧氏距离）
       drift_score = np.linalg.norm(train_importance - current_importance)
       
       # 找出变化最大的特征
       importance_diff = np.abs(train_importance - current_importance)
       top_drift_indices = np.argsort(importance_diff)[-10:][::-1]
       
       top_drifts = [
           {
               "feature": feature_names[i],
               "train_importance": float(train_importance[i]),
               "current_importance": float(current_importance[i]),
               "drift": float(importance_diff[i])
           }
           for i in top_drift_indices
       ]
       
       return {
           "model_id": model_id,
           "drift_score": float(drift_score),
           "drift_threshold": 0.1,  # 可配置
           "is_drifted": drift_score > 0.1,
           "top_drifts": top_drifts,
           "recommendation": "Retrain model" if drift_score > 0.1 else "Model is stable"
       }
   ```

**注册方法**:
```python
def register_all() -> None:
    register_daemon_method("run_confidence_calibration", _run_confidence_calibration)
    register_daemon_method("predict_signal_confidence", _predict_signal_confidence)
    register_daemon_method("combine_strategy_signals", _combine_strategy_signals)
    register_daemon_method("plot_model_accuracy_trend", _plot_model_accuracy_trend)
    register_daemon_method("plot_equity_curve", _plot_equity_curve)
    register_daemon_method("plot_strategy_comparison", _plot_strategy_comparison)
    register_daemon_method("plot_feature_importance", _plot_feature_importance)
    
    # 新增方法
    register_daemon_method("train_model", _train_model)
    register_daemon_method("list_models", _list_models)
    register_daemon_method("evaluate_model", _evaluate_model)
    register_daemon_method("monitor_model", _monitor_model)
```

**验收标准**:
- ✅ 4 个新方法添加到 `ml_query.py`
- ✅ 所有方法已注册到 daemon
- ✅ 代码符合现有风格
- ✅ 错误处理完善

---

### Task 2: 创建 model_train 工具

**目标**: 创建 `src/infrastructure/tools/model/train-tool.ts`

**工具定义**:
```typescript
export const modelTrainTool: ToolDefinition = {
  name: "model_train",
  label: "训练模型",
  description: "训练机器学习模型（XGBoost/LightGBM），用于股票信号预测",
  parameters: Type.Object({
    model_type: Type.Optional(Type.Union([
      Type.Literal("xgboost"),
      Type.Literal("lightgbm")
    ], { description: "模型类型，默认 xgboost" })),
    days: Type.Optional(Type.Number({ 
      description: "训练数据天数，默认 180" 
    })),
    future_days: Type.Optional(Type.Number({ 
      description: "预测未来N天收益，默认 5" 
    })),
    return_threshold: Type.Optional(Type.Number({ 
      description: "涨幅阈值（小数形式），默认 0.05（5%）" 
    })),
    symbols: Type.Optional(Type.Array(Type.String(), { 
      description: "训练股票列表，不指定则全部" 
    })),
    cv_splits: Type.Optional(Type.Number({ 
      description: "交叉验证折数，默认 5" 
    }))
  }),
  execute: async (conversationId: string, args: any) => {
    const quantsysClient = getQuantsysClient();
    
    try {
      const result = await quantsysClient.train_model({
        model_type: args.model_type || "xgboost",
        days: args.days || 180,
        future_days: args.future_days || 5,
        return_threshold: args.return_threshold || 0.05,
        symbols: args.symbols,
        cv_splits: args.cv_splits || 5
      });
      
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }]
      };
    } catch (error: any) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }]
      };
    }
  }
};
```

**测试用例** (15+):
1. 默认参数训练
2. 指定模型类型（xgboost, lightgbm）
3. 自定义训练天数
4. 自定义预测天数
5. 自定义涨幅阈值
6. 指定训练股票列表
7. 自定义交叉验证折数
8. 参数组合测试
9. 错误处理（无效模型类型）
10. 错误处理（负数参数）
11. 错误处理（daemon 连接失败）
12. 响应格式验证
13. 训练报告字段验证
14. 特征重要性验证
15. 模型保存路径验证

**验收标准**:
- ✅ 工具文件创建
- ✅ 测试文件创建
- ✅ 15+ 测试用例全部通过
- ✅ 覆盖率 > 60%
- ✅ Spec 合规性审查通过
- ✅ 代码质量审查通过

---

### Task 3: 创建 model_predict 工具

**目标**: 创建 `src/infrastructure/tools/model/predict-tool.ts`

**工具定义**:
```typescript
export const modelPredictTool: ToolDefinition = {
  name: "model_predict",
  label: "模型预测",
  description: "使用训练好的模型预测股票信号和置信度",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码" }),
    model_id: Type.Optional(Type.String({ 
      description: "模型ID，默认使用最新模型" 
    })),
    features: Type.Optional(Type.Array(Type.String(), { 
      description: "指定使用的特征，不指定则使用全部" 
    }))
  }),
  execute: async (conversationId: string, args: any) => {
    const quantsysClient = getQuantsysClient();
    
    // 参数验证
    if (!args.symbol) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: "symbol 参数是必需的"
          }, null, 2)
        }]
      };
    }
    
    try {
      const result = await quantsysClient.predict_signal_confidence({
        symbol: args.symbol,
        model_name: args.model_id || "latest",
        features: args.features
      });
      
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }]
      };
    } catch (error: any) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }]
      };
    }
  }
};
```

**测试用例** (15+):
1. 默认参数预测
2. 指定模型ID
3. 指定特征列表
4. A股预测
5. 港股预测
6. 参数组合测试
7. 错误处理（缺少 symbol）
8. 错误处理（无效 symbol）
9. 错误处理（模型不存在）
10. 错误处理（daemon 连接失败）
11. 响应格式验证
12. 置信度范围验证（0-1）
13. 预测信号验证（buy/sell/hold）
14. 特征值验证
15. 多股票批量预测

**验收标准**:
- ✅ 工具文件创建
- ✅ 测试文件创建
- ✅ 15+ 测试用例全部通过
- ✅ 覆盖率 > 60%
- ✅ Spec 合规性审查通过
- ✅ 代码质量审查通过

---

### Task 4: 创建 model_evaluate 工具

**目标**: 创建 `src/infrastructure/tools/model/evaluate-tool.ts`

**工具定义**:
```typescript
export const modelEvaluateTool: ToolDefinition = {
  name: "model_evaluate",
  label: "模型评估",
  description: "评估模型性能，查看训练报告、测试指标、特征重要性",
  parameters: Type.Object({
    model_id: Type.Optional(Type.String({ 
      description: "模型ID，默认评估最新模型" 
    }))
  }),
  execute: async (conversationId: string, args: any) => {
    const quantsysClient = getQuantsysClient();
    
    try {
      const result = await quantsysClient.evaluate_model({
        model_id: args.model_id || "latest"
      });
      
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }]
      };
    } catch (error: any) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }]
      };
    }
  }
};
```

**测试用例** (12+):
1. 评估最新模型
2. 评估指定模型
3. 验证训练数据统计
4. 验证交叉验证结果
5. 验证测试集指标
6. 验证特征重要性
7. 验证混淆矩阵
8. 错误处理（模型不存在）
9. 错误处理（daemon 连接失败）
10. 响应格式验证
11. 指标范围验证
12. 特征数量验证

**验收标准**:
- ✅ 工具文件创建
- ✅ 测试文件创建
- ✅ 12+ 测试用例全部通过
- ✅ 覆盖率 > 60%
- ✅ Spec 合规性审查通过
- ✅ 代码质量审查通过

---

### Task 5: 创建 model_monitor 工具

**目标**: 创建 `src/infrastructure/tools/model/monitor-tool.ts`

**工具定义**:
```typescript
export const modelMonitorTool: ToolDefinition = {
  name: "model_monitor",
  label: "模型监控",
  description: "监控模型特征漂移，检测模型是否需要重新训练",
  parameters: Type.Object({
    model_id: Type.Optional(Type.String({ 
      description: "模型ID，默认监控最新模型" 
    }))
  }),
  execute: async (conversationId: string, args: any) => {
    const quantsysClient = getQuantsysClient();
    
    try {
      const result = await quantsysClient.monitor_model({
        model_id: args.model_id || "latest"
      });
      
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }]
      };
    } catch (error: any) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }]
      };
    }
  }
};
```

**测试用例** (12+):
1. 监控最新模型
2. 监控指定模型
3. 验证漂移分数
4. 验证漂移阈值
5. 验证是否漂移标志
6. 验证 top 漂移特征
7. 验证重训练建议
8. 错误处理（模型不存在）
9. 错误处理（daemon 连接失败）
10. 响应格式验证
11. 漂移分数范围验证
12. 特征漂移排序验证

**验收标准**:
- ✅ 工具文件创建
- ✅ 测试文件创建
- ✅ 12+ 测试用例全部通过
- ✅ 覆盖率 > 60%
- ✅ Spec 合规性审查通过
- ✅ 代码质量审查通过

---

### Task 6: 创建 model_list 工具

**目标**: 创建 `src/infrastructure/tools/model/list-tool.ts`

**工具定义**:
```typescript
export const modelListTool: ToolDefinition = {
  name: "model_list",
  label: "模型列表",
  description: "列出所有训练好的模型及其版本信息",
  parameters: Type.Object({
    status: Type.Optional(Type.String({ 
      description: "过滤状态（all/latest），默认 all" 
    }))
  }),
  execute: async (conversationId: string, args: any) => {
    const quantsysClient = getQuantsysClient();
    
    try {
      const result = await quantsysClient.list_models({
        status: args.status || "all"
      });
      
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }]
      };
    } catch (error: any) {
      return {
        role: "user" as const,
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message
          }, null, 2)
        }]
      };
    }
  }
};
```

**测试用例** (10+):
1. 列出所有模型
2. 只列出最新模型
3. 验证模型数量
4. 验证模型字段
5. 验证时间戳格式
6. 验证模型路径
7. 验证测试指标
8. 错误处理（daemon 连接失败）
9. 响应格式验证
10. 空列表处理

**验收标准**:
- ✅ 工具文件创建
- ✅ 测试文件创建
- ✅ 10+ 测试用例全部通过
- ✅ 覆盖率 > 60%
- ✅ Spec 合规性审查通过
- ✅ 代码质量审查通过

---

### Task 7: 更新工具注册表

**目标**: 在 `src/infrastructure/tools/index.ts` 添加 L3 工具

**修改内容**:
```typescript
// L3 模型层工具
import { modelTrainTool } from "./model/train-tool";
import { modelPredictTool } from "./model/predict-tool";
import { modelEvaluateTool } from "./model/evaluate-tool";
import { modelMonitorTool } from "./model/monitor-tool";
import { modelListTool } from "./model/list-tool";

export const allCustomTools: ToolDefinition[] = [
  // L1 数据管道层
  dataFetchStockTool,
  dataFetchKlineTool,
  dataFetchFinancialTool,
  
  // L2 因子工厂层
  factorCalculateTool,
  
  // L3 模型层
  modelTrainTool,
  modelPredictTool,
  modelEvaluateTool,
  modelMonitorTool,
  modelListTool,
  
  // L4 组合构建层
  portfolioRebalanceTool,
  
  // L5 执行引擎层
  tradeManageOrdersTool,
  
  // L6 监控运维层
  monitorAlertTool,
  
  // Agent 元工具
  ...agentTools
];
```

**验收标准**:
- ✅ 5 个 L3 工具已导入
- ✅ 5 个 L3 工具已注册到 allCustomTools
- ✅ 注释清晰标注 L3 模型层
- ✅ 构建成功无错误

---

### Task 8: 更新文档

**目标**: 更新项目文档反映 L3 模型层的完成

**需要更新的文档**:

1. **CLAUDE.md** - 添加 L3 模型层说明
2. **README.md** - 更新工具数量统计
3. **TOOL_MIGRATION_GUIDE.md** - 添加 L3 工具映射
4. **最终总结报告** - 更新 L3 状态为"已完成"

**验收标准**:
- ✅ 所有文档已更新
- ✅ L3 工具说明完整
- ✅ 示例代码正确
- ✅ Git 提交清晰

---

## 执行策略

### 方式：Subagent-Driven Development

1. **Task 1**: 派发 Python 后端 subagent 补充 daemon 方法
2. **Task 2-6**: 并行派发 5 个 subagent 创建 L3 工具
3. **每个任务**: 实现 → Spec 审查 → 代码质量审查 → 修复 → 重新审查
4. **Task 7-8**: 主 agent 完成注册和文档更新

### 质量保证

- 两阶段审查（Spec + 代码质量）
- 测试覆盖率 > 60%
- 所有测试必须通过
- 代码风格一致

### 时间估算

- Task 1: 30 分钟（后端 daemon 方法）
- Task 2-6: 90 分钟（5 个工具并行）
- Task 7-8: 20 分钟（注册和文档）
- **总计**: ~2.5 小时

## 成功指标

- ✅ 5 个 L3 工具全部实现
- ✅ 4 个后端 daemon 方法补充完成
- ✅ 64+ 测试用例全部通过
- ✅ 平均测试覆盖率 > 60%
- ✅ 所有审查通过
- ✅ 文档完善
- ✅ Git 提交清晰

---

**计划创建时间**: 2026-05-25  
**计划作者**: Kiro AI Agent  
**审核状态**: 待执行
