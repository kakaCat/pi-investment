# Model Tools V2 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 5 个模型工具从 v1 daemon 迁移到 quantsys-v2 API，修复 model_list 报错

**Architecture:** 三层架构 - 后端添加 3 个新 API 端点 → TypeScript 客户端封装 5 个方法 → 工具层替换 v1 调用为 v2 客户端

**Tech Stack:** Python Flask, TypeScript, PostgreSQL

---

## 文件结构

**后端（quantsys-v2）：**
- `api/ml_routes.py` - 添加 3 个新端点（models, evaluate, monitor）
- `repositories/ml_model_repository.py` - 已有，无需修改

**客户端（TypeScript）：**
- `src/infrastructure/quant/types.ts` - 添加类型定义
- `src/infrastructure/quant/quant-v2-client.ts` - 添加 5 个方法

**工具层（TypeScript）：**
- `src/infrastructure/tools/model/list-tool.ts` - 替换 v1 调用
- `src/infrastructure/tools/model/predict-tool.ts` - 替换 v1 调用
- `src/infrastructure/tools/model/train-tool.ts` - 替换 v1 调用
- `src/infrastructure/tools/model/evaluate-tool.ts` - 替换 v1 调用
- `src/infrastructure/tools/model/monitor-tool.ts` - 替换 v1 调用

**测试：**
- `quantsys-v2/tests/api/test_ml_routes.py` - 后端 API 测试

---

## Task 1: 后端 - 添加 GET /api/ml/models 端点

**Files:**
- Modify: `quantsys-v2/api/ml_routes.py:183-186`

- [ ] **Step 1: 在 ml_routes.py 添加 models 列表端点**

在 `register_ml_routes()` 函数中，`ml_model_info()` 函数之后添加：

```python
    # ── GET /api/ml/models ──────────────────────────────────────

    @app.route("/api/ml/models", methods=["GET"])
    @_ml_error_handler
    def ml_models_list():
        """列出所有模型"""
        model_type = request.args.get("model_type")
        status = request.args.get("status", "ready")
        limit = int(request.args.get("limit", 20))
        
        models = _model_repo.list_models(model_type, status, limit)
        
        return jsonify({
            "success": True,
            "models": _sanitize_for_json(models),
            "total": len(models)
        })
```

- [ ] **Step 2: 启动 v2 服务测试端点**

```bash
cd quantsys-v2 && python api/server.py
```

Expected: 服务启动在 127.0.0.1:5001

- [ ] **Step 3: 测试 API 响应**

```bash
curl "http://127.0.0.1:5001/api/ml/models?status=ready&limit=10"
```

Expected: 返回 JSON，包含 `success: true`, `models: []`, `total: 0`（如果没有模型）

- [ ] **Step 4: 提交**

```bash
git add quantsys-v2/api/ml_routes.py
git commit -m "feat(api): add GET /api/ml/models endpoint"
```

---

## Task 2: 后端 - 添加 GET /api/ml/model/evaluate 端点

**Files:**
- Modify: `quantsys-v2/api/ml_routes.py` (在 Task 1 添加的代码之后)

- [ ] **Step 1: 添加 evaluate 端点**

在 `ml_models_list()` 函数之后添加：

```python
    # ── GET /api/ml/model/evaluate ──────────────────────────────

    @app.route("/api/ml/model/evaluate", methods=["GET"])
    @_ml_error_handler
    def ml_model_evaluate():
        """评估模型性能"""
        model_type = request.args.get("model_type", "xgboost")
        version = request.args.get("version", "latest")
        
        model = _model_repo.get_by_type_version(model_type, version)
        if not model:
            return jsonify({"success": False, "error": "模型不存在"}), 404
        
        # 解析 training_report
        report = model.get("training_report", {})
        if isinstance(report, str):
            report = _json.loads(report)
        
        return jsonify({
            "success": True,
            "evaluation": {
                "model_type": model["model_type"],
                "version": model["version"],
                "metrics": {
                    "train_accuracy": model.get("train_accuracy"),
                    "test_accuracy": model.get("test_accuracy"),
                    "precision": model.get("precision"),
                    "recall": model.get("recall"),
                    "f1_score": model.get("f1_score"),
                    "roc_auc": model.get("roc_auc")
                },
                "training_report": report
            }
        })
```

- [ ] **Step 2: 测试端点**

```bash
curl "http://127.0.0.1:5001/api/ml/model/evaluate?model_type=xgboost&version=latest"
```

Expected: 返回 404 或模型评估数据（如果有模型）

- [ ] **Step 3: 提交**

```bash
git add quantsys-v2/api/ml_routes.py
git commit -m "feat(api): add GET /api/ml/model/evaluate endpoint"
```

---

## Task 3: 后端 - 添加 GET /api/ml/model/monitor 端点

**Files:**
- Modify: `quantsys-v2/api/ml_routes.py` (在 Task 2 添加的代码之后)

- [ ] **Step 1: 添加 monitor 端点（简化版）**

在 `ml_model_evaluate()` 函数之后添加：

```python
    # ── GET /api/ml/model/monitor ────────────────────────────────

    @app.route("/api/ml/model/monitor", methods=["GET"])
    @_ml_error_handler
    def ml_model_monitor():
        """监控模型漂移（简化版）"""
        model_type = request.args.get("model_type", "xgboost")
        version = request.args.get("version", "latest")
        days = int(request.args.get("days", 30))
        
        model = _model_repo.get_by_type_version(model_type, version)
        if not model:
            return jsonify({"success": False, "error": "模型不存在"}), 404
        
        # 简化实现：返回固定的监控结果
        return jsonify({
            "success": True,
            "monitor": {
                "model_type": model["model_type"],
                "version": model["version"],
                "drift_detected": False,
                "drift_score": 0.0,
                "threshold": 0.3,
                "recommendation": "模型监控功能简化版，建议使用 web-frontend 查看详细指标",
                "top_drift_features": [],
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        })
```

- [ ] **Step 2: 测试端点**

```bash
curl "http://127.0.0.1:5001/api/ml/model/monitor?model_type=xgboost&days=30"
```

Expected: 返回 404 或监控数据（如果有模型）

- [ ] **Step 3: 提交**

```bash
git add quantsys-v2/api/ml_routes.py
git commit -m "feat(api): add GET /api/ml/model/monitor endpoint (simplified)"
```

---

## Task 4: TypeScript - 添加类型定义

**Files:**
- Modify: `src/infrastructure/quant/types.ts` (文件末尾)

- [ ] **Step 1: 添加模型相关类型**

在文件末尾添加：

```typescript
// ─── ML Model Types ──────────────────────────────────────────

export interface MLModel {
  id: number;
  model_type: string;
  version: string;
  train_date: string;
  test_accuracy: number;
  f1_score?: number;
  feature_count: number;
  train_samples: number;
  status: string;
}

export interface ListModelsResponse {
  success: boolean;
  models: MLModel[];
  total: number;
  error?: string;
}

export interface ModelMetrics {
  train_accuracy: number;
  test_accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number;
}

export interface ModelEvaluation {
  model_type: string;
  version: string;
  metrics: ModelMetrics;
  training_report: {
    cv_scores?: number[];
    feature_importance?: Record<string, number>;
    confusion_matrix?: number[][];
  };
}

export interface EvaluateModelResponse {
  success: boolean;
  evaluation?: ModelEvaluation;
  error?: string;
}

export interface DriftFeature {
  feature: string;
  drift: number;
}

export interface ModelMonitor {
  model_type: string;
  version: string;
  drift_detected: boolean;
  drift_score: number;
  threshold: number;
  recommendation: string;
  top_drift_features: DriftFeature[];
  checked_at: string;
}

export interface MonitorModelResponse {
  success: boolean;
  monitor?: ModelMonitor;
  error?: string;
}
```

- [ ] **Step 2: 验证类型编译**

```bash
npm run build
```

Expected: 编译成功，无类型错误

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/quant/types.ts
git commit -m "feat(types): add ML model types for v2 API"
```

---

## Task 5: TypeScript - 添加 QuantV2Client 方法

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts` (文件末尾，export 函数区域)

- [ ] **Step 1: 添加 listModels 方法**

在文件末尾的 export 函数区域添加：

```typescript
/**
 * 列出模型
 */
export async function listModels(
  modelType?: string,
  status?: string,
  limit?: number
): Promise<ListModelsResponse> {
  const params = new URLSearchParams();
  if (modelType) params.append("model_type", modelType);
  if (status) params.append("status", status);
  if (limit) params.append("limit", limit.toString());
  
  const url = `/api/ml/models${params.toString() ? `?${params.toString()}` : ""}`;
  return fetchV2<ListModelsResponse>(url, { method: "GET" });
}
```

- [ ] **Step 2: 添加 evaluateModel 方法**

```typescript
/**
 * 评估模型
 */
export async function evaluateModel(
  modelType: string = "xgboost",
  version: string = "latest"
): Promise<EvaluateModelResponse> {
  const params = new URLSearchParams({ model_type: modelType, version });
  
  return fetchV2<EvaluateModelResponse>(
    `/api/ml/model/evaluate?${params.toString()}`,
    { method: "GET" }
  );
}
```

- [ ] **Step 3: 添加 monitorModel 方法**

```typescript
/**
 * 监控模型漂移
 */
export async function monitorModel(
  modelType: string = "xgboost",
  version: string = "latest",
  days: number = 30
): Promise<MonitorModelResponse> {
  const params = new URLSearchParams({
    model_type: modelType,
    version,
    days: days.toString()
  });
  
  return fetchV2<MonitorModelResponse>(
    `/api/ml/model/monitor?${params.toString()}`,
    { method: "GET" }
  );
}
```

- [ ] **Step 4: 添加 trainModel 方法**

```typescript
/**
 * 训练模型（复用现有端点）
 */
export async function trainModel(params: {
  model_type?: string;
  start_date?: string;
  end_date?: string;
  test_size?: number;
  symbols?: string[];
  params?: Record<string, any>;
}): Promise<any> {
  return fetchV2("/api/ml/train", {
    method: "POST",
    body: JSON.stringify(params)
  });
}
```

- [ ] **Step 5: 添加 predictModel 方法**

```typescript
/**
 * 模型预测（复用现有端点）
 */
export async function predictModel(params: {
  model_type?: string;
  version?: string;
  symbols: string[];
  date?: string;
}): Promise<any> {
  return fetchV2("/api/ml/predict", {
    method: "POST",
    body: JSON.stringify(params)
  });
}
```

- [ ] **Step 6: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 7: 提交**

```bash
git add src/infrastructure/quant/quant-v2-client.ts
git commit -m "feat(client): add 5 ML model methods for v2 API"
```

---

## Task 6: 工具迁移 - model_list

**Files:**
- Modify: `src/infrastructure/tools/model/list-tool.ts:37-64`

- [ ] **Step 1: 替换导入和实现**

替换第 8 行的导入：

```typescript
// 删除
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// 添加
import { listModels } from "../../quant/quant-v2-client.js";
```

替换 `execute` 函数（第 37-64 行）：

```typescript
  execute: async (_toolCallId, params: ModelListParams) => {
    const { status = "all" } = params;

    try {
      const response = await listModels(undefined, status === "all" ? undefined : status);
      
      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "获取模型列表失败"
            }, null, 2)
          }],
          details: undefined
        };
      }

      // 格式化输出
      const formatted = {
        success: true,
        total: response.total,
        models: response.models.map(m => ({
          model_type: m.model_type,
          version: m.version,
          train_date: m.train_date,
          accuracy: m.test_accuracy,
          f1_score: m.f1_score,
          features: m.feature_count,
          samples: m.train_samples,
          status: m.status
        }))
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(formatted, null, 2)
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 2: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/tools/model/list-tool.ts
git commit -m "feat(tools): migrate model_list to v2 API"
```

---

## Task 7: 工具迁移 - model_predict

**Files:**
- Modify: `src/infrastructure/tools/model/predict-tool.ts:42-76`

- [ ] **Step 1: 替换导入和实现**

替换第 9 行的导入：

```typescript
// 删除
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// 添加
import { predictModel } from "../../quant/quant-v2-client.js";
```

替换 `execute` 函数（第 42-76 行）：

```typescript
  execute: async (_toolCallId, params: PredictParams) => {
    const { symbol, model_id = "latest", features } = params;

    // 参数验证：symbol 必需
    if (!symbol || symbol.trim() === "") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: "参数错误：symbol 不能为空"
          }, null, 2)
        }],
        details: undefined
      };
    }

    // 市场检测
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`
          }, null, 2)
        }],
        details: undefined
      };
    }

    try {
      const response = await predictModel({
        version: model_id,
        symbols: [symbol]
      });

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response, null, 2)
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 2: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/tools/model/predict-tool.ts
git commit -m "feat(tools): migrate model_predict to v2 API"
```

---

## Task 8: 工具迁移 - model_train

**Files:**
- Modify: `src/infrastructure/tools/model/train-tool.ts:67-100`

- [ ] **Step 1: 替换导入和实现**

替换第 8 行的导入：

```typescript
// 删除
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// 添加
import { trainModel } from "../../quant/quant-v2-client.js";
```

替换 `execute` 函数（第 67 行开始）：

```typescript
  execute: async (_toolCallId, params: TrainModelParams) => {
    const {
      model_type = "xgboost",
      days = 180,
      future_days = 5,
      return_threshold = 0.05,
      symbols,
      cv_splits = 5
    } = params;

    try {
      const response = await trainModel({
        model_type,
        symbols,
        params: {
          days,
          future_days,
          return_threshold,
          cv_splits
        }
      });

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response, null, 2)
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 2: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/tools/model/train-tool.ts
git commit -m "feat(tools): migrate model_train to v2 API"
```

---

## Task 9: 工具迁移 - model_evaluate

**Files:**
- Modify: `src/infrastructure/tools/model/evaluate-tool.ts:35-62`

- [ ] **Step 1: 替换导入和实现**

替换第 8 行的导入：

```typescript
// 删除
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// 添加
import { evaluateModel } from "../../quant/quant-v2-client.js";
```

替换 `execute` 函数（第 35-62 行）：

```typescript
  execute: async (_toolCallId, params: ModelEvaluateParams) => {
    const { model_id = "latest" } = params;

    try {
      const response = await evaluateModel("xgboost", model_id);
      
      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "评估模型失败"
            }, null, 2)
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response.evaluation, null, 2)
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 2: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/tools/model/evaluate-tool.ts
git commit -m "feat(tools): migrate model_evaluate to v2 API"
```

---

## Task 10: 工具迁移 - model_monitor

**Files:**
- Modify: `src/infrastructure/tools/model/monitor-tool.ts:25-54`

- [ ] **Step 1: 替换导入和实现**

替换第 8 行的导入：

```typescript
// 删除
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// 添加
import { monitorModel } from "../../quant/quant-v2-client.js";
```

替换 `execute` 函数（第 25-54 行）：

```typescript
  execute: async (_toolCallId, params: MonitorModelParams) => {
    const { model_id = "latest" } = params;

    try {
      const response = await monitorModel("xgboost", model_id);
      
      if (!response.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: response.error || "监控模型失败"
            }, null, 2)
          }],
          details: undefined
        };
      }

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(response.monitor, null, 2)
        }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `API 调用失败: ${error.message}`
          }, null, 2)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 2: 验证编译**

```bash
npm run build
```

Expected: 编译成功

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/tools/model/monitor-tool.ts
git commit -m "feat(tools): migrate model_monitor to v2 API"
```

---

## Task 11: 集成测试

**Files:**
- Test: 手动测试所有工具

- [ ] **Step 1: 启动 quantsys-v2 服务**

```bash
cd quantsys-v2 && python start_all.py
```

Expected: REST API 启动在 127.0.0.1:5001

- [ ] **Step 2: 启动 TypeScript Agent**

```bash
cd .. && npm run dev
```

Expected: Agent TUI 启动

- [ ] **Step 3: 测试 model_list 工具**

在 Agent 中输入：

```
model_list({ status: "all" })
```

Expected: 返回模型列表或空列表（不再报错 "Method 'list_models' not found"）

- [ ] **Step 4: 测试其他工具（如果有训练好的模型）**

```
model_evaluate({ model_id: "latest" })
model_monitor({ model_id: "latest" })
```

Expected: 返回评估数据或 404（模型不存在）

- [ ] **Step 5: 验证错误处理**

停止 quantsys-v2 服务，再次调用工具：

Expected: 返回友好错误提示（服务不可用）

---

## Task 12: 更新文档

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md 迁移状态**

找到 "v2 迁移" 相关章节，更新：

```markdown
**v2 已迁移工具**：
- `data_fetch_stock`, `data_fetch_kline`, `data_fetch_financial`, `data_fetch_dividend` ✅
- `model_list`, `model_predict`, `model_train`, `model_evaluate`, `model_monitor` ✅ (2026-05-29)
```

- [ ] **Step 2: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: update model tools v2 migration status"
```

---

## Task 13: 最终验证

**Files:**
- Test: 完整端到端测试

- [ ] **Step 1: 运行 TypeScript 测试**

```bash
npm test
```

Expected: 所有测试通过

- [ ] **Step 2: 运行 Python 测试**

```bash
cd quantsys-v2 && pytest tests/api/test_ml_routes.py -v
```

Expected: 所有测试通过（如果有相关测试）

- [ ] **Step 3: 验证构建**

```bash
npm run build
```

Expected: 构建成功，无错误

- [ ] **Step 4: 创建最终提交**

```bash
git add -A
git commit -m "feat: complete model tools v2 migration

- Add 3 new API endpoints (models, evaluate, monitor)
- Add 5 QuantV2Client methods
- Migrate 5 model tools from v1 daemon to v2 API
- Fix model_list 'Method not found' error
- Update documentation"
```

---

## 验收标准

- ✅ 3 个新 API 端点正常工作
- ✅ 5 个工具全部迁移到 v2
- ✅ `model_list` 工具报错已修复
- ✅ 编译无错误
- ✅ 文档已更新

## 预估时间

- 后端 API 端点：30 分钟
- TypeScript 客户端：30 分钟
- 工具迁移：60 分钟
- 测试与验证：30 分钟
- **总计：2.5 小时**
